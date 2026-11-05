"""The Snowflake client the share's captures use: the named connection, the session record, values as JSON, and the
query text. The share's datasets and their capture are ``sources.snowflake``.

The Avalanche Foundation's own account is reached with a key pair instead of a named connection: ``connect_foundation``
signs in with the private key file that ``AVALANCHE_FOUNDATION_SNOWFLAKE_KEY`` names, by default
``~/.snowflake/bcrg_rsa_key.p8``. The key is read by the connector and never enters a capture, a receipt or the output.
Its datasets are ``sources.foundation``."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from ...core.catalog import DATA_DIR, DataError

CONNECTION_VARIABLE = "AVALANCHE_SNOWFLAKE_CONNECTION"
DEFAULT_CONNECTION = "avalanche"
QUERY_TAG = "avalanche-phase-ii-research"
SESSION_SQL = "SELECT CURRENT_ROLE(), CURRENT_WAREHOUSE(), CURRENT_DATABASE(), CURRENT_SCHEMA(), CURRENT_VERSION()"
FETCH_SIZE = 10_000
FOUNDATION_KEY_VARIABLE = "AVALANCHE_FOUNDATION_SNOWFLAKE_KEY"
DEFAULT_FOUNDATION_KEY = "~/.snowflake/bcrg_rsa_key.p8"


@dataclass(frozen=True)
class KeyPairAccount:
    """A Snowflake account read with a key pair: the account, user, read-only role and warehouse. No secret."""

    account: str
    user: str
    role: str
    warehouse: str

    def describe(self) -> str:
        return f"account {self.account}, user {self.user}, role {self.role}, warehouse {self.warehouse}, key from ${FOUNDATION_KEY_VARIABLE}"


# The Foundation's account holding Allium's Avalanche database and the Foundation's Gross Chain Product database.
FOUNDATION_ACCOUNT = KeyPairAccount("RYPQXPJ-AVALANCHE_FOUNDATION", "EXT_BCRG", "AF_AVALANCHE_GCP_READER", "AF_WAREHOUSE_X_SMALL")


def connection_name() -> str:
    return os.environ.get(CONNECTION_VARIABLE, DEFAULT_CONNECTION)


def foundation_key_path() -> Path:
    return Path(os.environ.get(FOUNDATION_KEY_VARIABLE, DEFAULT_FOUNDATION_KEY)).expanduser()


def connect_foundation(name: str, timeout: float, account: KeyPairAccount = FOUNDATION_ACCOUNT) -> Any:
    """Open a read-only key-pair connection to the Foundation's account. ``name`` is the account's description, as
    the capture preview reports it, and only checks that the caller means this account."""
    if name != account.describe():
        raise DataError(f"unknown key-pair connection: {name}")
    try:
        import snowflake.connector
    except ImportError as error:
        raise DataError(
            "snowflake-connector-python is not installed; run: uv sync --locked --extra snowflake"
        ) from error
    key = foundation_key_path()
    if not key.is_file():
        raise DataError(f"no private key file at the path ${FOUNDATION_KEY_VARIABLE} names, or at its default")
    try:
        return snowflake.connector.connect(
            account=account.account,
            user=account.user,
            role=account.role,
            warehouse=account.warehouse,
            authenticator="SNOWFLAKE_JWT",
            private_key_file=str(key),
            login_timeout=int(timeout),
            network_timeout=int(timeout),
            session_parameters={"QUERY_TAG": QUERY_TAG, "STATEMENT_TIMEOUT_IN_SECONDS": int(timeout)},
        )
    except snowflake.connector.errors.Error as error:
        raise DataError(f"Snowflake key-pair connection to {account.account} failed: {error}") from error


def connect(name: str, timeout: float) -> Any:
    """Open a Snowflake connection through the connector's named-connection configuration."""
    try:
        import snowflake.connector
    except ImportError as error:
        raise DataError(
            "snowflake-connector-python is not installed; run: uv sync --locked --extra snowflake"
        ) from error
    try:
        return snowflake.connector.connect(
            connection_name=name,
            login_timeout=int(timeout),
            network_timeout=int(timeout),
            session_parameters={"QUERY_TAG": QUERY_TAG, "STATEMENT_TIMEOUT_IN_SECONDS": int(timeout)},
        )
    except snowflake.connector.errors.Error as error:
        raise DataError(f"Snowflake connection {name!r} failed: {error}") from error


def _connector_error(error: BaseException) -> bool:
    return type(error).__module__.startswith("snowflake.")


def read_sql(query: dict[str, Any]) -> str:
    try:
        return (DATA_DIR / query["sql"]).read_text(encoding="utf-8")
    except OSError as error:
        raise DataError(f"missing query text: {query['sql']}") from error


def _json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc).replace(tzinfo=None)
        spec = "seconds" if value.microsecond == 0 else "microseconds"
        return value.isoformat(timespec=spec) + "Z"
    if isinstance(value, date):
        return value.isoformat()
    raise DataError(f"unsupported value type from Snowflake: {type(value).__name__}")


def _session(connection: Any) -> dict[str, Any]:
    cursor = connection.cursor()
    try:
        cursor.execute(SESSION_SQL)
        role, warehouse, database, schema, version = cursor.fetchall()[0]
    finally:
        cursor.close()
    return {"role": role, "warehouse": warehouse, "database": database, "schema": schema, "server_version": version}
