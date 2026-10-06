"""Stakes, rewards, and the supply counter rebuilt from a P-Chain block walk: a second source for four Snowflake datasets.

Each table has the columns of the Snowflake dataset it backs up, so a derived table reads either without change:

| Dataset | Backs up |
| --- | --- |
| ``derived.p-chain-validator-stakes`` | ``snowflake.primary-validator-stakes`` |
| ``derived.p-chain-delegator-stakes`` | ``snowflake.primary-delegator-stakes`` |
| ``derived.p-chain-staking-rewards`` | ``snowflake.primary-staking-rewards`` |
| ``derived.p-chain-staking-supply`` | ``snowflake.primary-staking-supply`` |

A fifth table, ``derived.p-chain-staking-cycles``, has no share counterpart: one row per cycle of each ACP-236 auto-renewed
validator, the grain at which such a validator's periods, rewards, and restaking happen from Helicon on.

The supply counter is replayed block by block with the protocol kernel. A new stake adds its potential reward, computed
from the supply before it (``protocol.start_stake``), and a stake that ends unrewarded, an abort, removes its potential
reward (``protocol.supply_after_stake_end``). The counter at the walk's first block is not read from any provider: it is
the one value whose replay ends exactly on the node's own counter at the walk's last height, ``node_supply`` in the walk's
receipt, found by bisection because the replay never decreases as the starting value rises. A stake that started before
the walk and ends unrewarded removes the potential reward the Data API records for it, since the walk never saw it start.

A stake's acceptance and start are its block's time and its end the transaction's declared end, as in the share. Its
rewarded flag is known once the walk holds the commit or abort after its reward transaction, and null before. Reward
rows of stakes that started before the walk take the stake's type, node, times, and potential reward from the Data API
record, and every reward row takes the realized reward from the node's reward outputs.

A delegation's validator is the newest period on its node that contains it: one the walk saw start, one the Data API
records, one the Data API lists as ended, or one the node lists as current in its newest or any earlier snapshot run. A
validator that started before the walk is known only from the last two. Once it ends, the ended list should hold it, but
the Data API's list has missed validators (one that ended 2026-10-03 left 19 delegations without their validator), so
every earlier snapshot of the node's current list is read too.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import duckdb

from . import __version__, datasets
from .catalog import (
    DataError,
    canonical_bytes,
    contract_hash,
    dataset,
    load_catalog,
    now,
    sha256,
)
from .model import protocol
from .model.types import ModelError
from .snowflake import (
    DELEGATOR_STAKES,
    STAKING_REWARDS,
    STAKING_SUPPLY,
    VALIDATOR_STAKES,
)

VALIDATORS_ID = "derived.p-chain-validator-stakes"
DELEGATORS_ID = "derived.p-chain-delegator-stakes"
REWARDS_ID = "derived.p-chain-staking-rewards"
SUPPLY_ID = "derived.p-chain-staking-supply"
CYCLES_ID = "derived.p-chain-staking-cycles"
DATASET_IDS = (VALIDATORS_ID, DELEGATORS_ID, REWARDS_ID, SUPPLY_ID, CYCLES_ID)
CYCLE_COLUMNS = {
    "validator_transaction_hash": "VARCHAR", "node_id": "VARCHAR", "cycle": "INTEGER", "start_time": "TIMESTAMP", "end_time": "TIMESTAMP",
    "weight_navax": "BIGINT", "potential_reward_navax": "BIGINT", "auto_compound_shares": "INTEGER", "next_period_seconds": "BIGINT",
    "reward_transaction_hash": "VARCHAR", "rewarded": "BOOLEAN", "delegatee_reward_navax": "BIGINT",
    "restaked_validation_navax": "BIGINT", "restaked_delegatee_navax": "BIGINT",
    "withdrawn_validation_navax": "BIGINT", "withdrawn_delegatee_navax": "BIGINT",
}
DATASET_ID = VALIDATORS_ID
SOURCE_ID = "derived"
EARLIER_CURRENT = "earlier-current-validators"
INPUTS = {
    "blocks": "p-chain-rpc.blocks",
    "staking-records": "data-api.p-chain-staking-transactions",
    "reward-utxos": "p-chain-rpc.reward-utxos",
    "current-validators": "p-chain-rpc.current-validators",
    "validators-completed-recent": "data-api.validators-completed-recent",
}
SPECS = {
    VALIDATORS_ID: ("p-chain-validator-stakes", VALIDATOR_STAKES.table_columns),
    DELEGATORS_ID: ("p-chain-delegator-stakes", DELEGATOR_STAKES.table_columns),
    REWARDS_ID: ("p-chain-staking-rewards", STAKING_REWARDS.table_columns),
    SUPPLY_ID: ("p-chain-staking-supply", STAKING_SUPPLY.table_columns),
    CYCLES_ID: ("p-chain-staking-cycles", CYCLE_COLUMNS),
}
PRIMARY_SUBNET = "11111111111111111111111111111111LpoYY"
VALIDATOR_TYPES = ("AddValidatorTx", "AddPermissionlessValidatorTx", "AddAutoRenewedValidatorTx")
DELEGATOR_TYPES = ("AddDelegatorTx", "AddPermissionlessDelegatorTx")
PRIMARY_STAKE_TYPES = ("AddValidatorTx", "AddPermissionlessValidatorTx", "AddDelegatorTx", "AddPermissionlessDelegatorTx")
LOWEST_SUPPLY = 360_000_000 * 10**9
AUTO_RENEW_TYPES = ("RewardAutoRenewedValidatorTx", "SetAutoRenewedValidatorConfigTx")


def _spec(dataset_id: str) -> tuple[str, dict[str, str]]:
    if dataset_id not in SPECS:
        raise DataError(f"unknown dataset: {dataset_id}")
    return SPECS[dataset_id]


def capture_preview(dataset_id: str, output: Path, parameters: dict[str, str] | None = None) -> dict[str, Any]:
    raise DataError(f"{dataset_id} is derived; use `avalanche data derive`")


capture = build_preview = build = capture_preview


def _describe(input_id: str, dataset_id: str, run: str | None, root: Path | None) -> dict[str, Any]:
    record = datasets.receipt(dataset_id, run, root)
    parquet = datasets.parquet_path(dataset_id, record["run"], root)
    body = parquet.read_bytes()
    return {
        "input_id": input_id, "dataset_id": dataset_id, "run": record["run"],
        "capture_id": record["capture"]["capture_id"], "contract_sha256": record["capture"].get("contract_sha256"),
        "captured_at": record["capture"].get("completed_at"), "rows": record["build"].get("summary", {}).get("rows"),
        "parquet": parquet.name, "bytes": len(body), "sha256": sha256(body), "path": parquet,
        **({"node_supply": record["capture"].get("node_supply"), "to_height": record["capture"].get("to_height")} if input_id == "blocks" else {}),
    }


def select_inputs(pinned: dict[str, str] | None, root: Path | None) -> list[dict[str, Any]]:
    """Each input pinned by ``dataset_id=run``, or its newest run. The staker captures must read the chosen walk."""
    pinned = pinned or {}
    unknown = sorted(set(pinned) - set(INPUTS.values()))
    if unknown:
        raise DataError(f"not an input of the P-Chain backup tables: {', '.join(unknown)}")
    inputs = [_describe(input_id, dataset_id, pinned.get(dataset_id), root) for input_id, dataset_id in INPUTS.items()]
    # Every earlier snapshot of the current list, oldest first, so a validator that ended is still known.
    current = next(item for item in inputs if item["input_id"] == "current-validators")
    earlier = [_describe(EARLIER_CURRENT, current["dataset_id"], item["run"], root) for item in datasets.runs(current["dataset_id"], root)
               if item["run"] != current["run"]]
    inputs.extend(sorted((item for item in earlier if (item["captured_at"] or "") <= (current["captured_at"] or "")),
                         key=lambda item: (item["captured_at"] or "", item["run"])))
    walk = inputs[0]
    for item in inputs[1:3]:
        blocks_capture = datasets.receipt(item["dataset_id"], item["run"], root)["capture"].get("blocks_capture_id")
        if blocks_capture != walk["capture_id"]:
            raise DataError(f"{item['dataset_id']} run {item['run']} reads another walk than {walk['run']}")
    if not walk.get("node_supply") or walk["node_supply"]["height"] != walk["to_height"]:
        raise DataError(f"walk {walk['run']} has no node supply counter at its last height; walk to the head")
    return inputs


BASE58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def node_id(value: str) -> str:
    """A node ID as every other table writes it. The node's JSON prints an AddAutoRenewedValidatorTx's nodeID as hex
    bytes; the usual form is ``NodeID-`` and CB58, base58 of the bytes and the last four bytes of their SHA-256."""
    if value.startswith("NodeID-"):
        return value
    try:
        raw = bytes.fromhex(value.removeprefix("0x"))
    except ValueError as error:
        raise DataError(f"a node ID is neither NodeID- nor hex: {value}") from error
    data = raw + hashlib.sha256(raw).digest()[-4:]
    number, text = int.from_bytes(data, "big"), ""
    while number:
        number, digit = divmod(number, 58)
        text = BASE58[digit] + text
    return "NodeID-" + "1" * (len(data) - len(data.lstrip(b"\0"))) + text


def _utc(seconds: int) -> datetime:
    return datetime.fromtimestamp(seconds, UTC).replace(tzinfo=None)


def _addresses(owner: Any) -> list[str]:
    addresses = (owner or {}).get("addresses") or []
    return [address.removeprefix("P-") for address in addresses]


def _load(inputs: list[dict[str, Any]]) -> dict[str, Any]:
    paths = {item["input_id"]: str(item["path"]) for item in inputs}
    connection = duckdb.connect()
    try:
        walk = connection.execute(
            "SELECT block_height, block_time, block_type, tx_index, transaction_hash, tx_type, staked_navax, unsigned_tx"
            " FROM read_parquet(?) ORDER BY block_height, tx_index NULLS FIRST", [paths["blocks"]]).fetchall()
        records = {row[0]: row for row in connection.execute("SELECT * FROM read_parquet(?)", [paths["staking-records"]]).fetchall()}
        paid = {row[0]: row for row in connection.execute("SELECT * FROM read_parquet(?)", [paths["reward-utxos"]]).fetchall()}
        # The newest snapshot first, so its periods win; earlier snapshots only add validators it no longer lists.
        snapshots = [paths["current-validators"]] + [str(item["path"]) for item in inputs if item["input_id"] == EARLIER_CURRENT]
        current = [row for path in snapshots for row in connection.execute(
            "SELECT transaction_hash, node_id, start_time, end_time FROM read_parquet(?)", [path]).fetchall()]
        ended = connection.execute(
            "SELECT transaction_hash, node_id, start_time, end_time FROM read_parquet(?) WHERE validation_status = 'completed'",
            [paths["validators-completed-recent"]]).fetchall()
    finally:
        connection.close()
    oldest_end = min((row[3] for row in ended), default=None)
    if walk and (oldest_end is None or oldest_end > walk[0][1]):
        raise DataError(f"the ended-validator list reaches back to {oldest_end}, after the walk's start {walk[0][1]}; "
                        "a delegation to a validator that ended between them would lose its validator")
    parsed = [_stake(row) for row in walk]
    reward_of = [json.loads(row[7]) if row[5] in AUTO_RENEW_TYPES else json.loads(row[7])["txID"] if row[5] == "RewardValidatorTx" else None
                 for row in walk]
    return {"walk": walk, "parsed": parsed, "reward_of": reward_of, "records": records, "paid": paid, "current": current, "ended": ended}


def _stake(row: tuple[Any, ...]) -> dict[str, Any] | None:
    """A Primary Network stake started by one walk transaction: its fields, or None for any other transaction."""
    height, block_time, _, index, tx_hash, tx_type, staked_navax, unsigned_json = row
    if tx_type not in (*VALIDATOR_TYPES, *DELEGATOR_TYPES):
        return None
    unsigned = json.loads(unsigned_json)
    if tx_type == "AddAutoRenewedValidatorTx":
        node, weight, end = node_id(unsigned["nodeID"]), staked_navax, int(block_time.replace(tzinfo=UTC).timestamp()) + int(unsigned["period"])
        shares, owner = unsigned["delegationShares"], unsigned["validationRewardsOwner"]
        renewal = {"auto_compound_shares": int(unsigned["autoCompoundRewardShares"]), "period": int(unsigned["period"])}
    else:
        renewal = {}
        if unsigned.get("subnetID", PRIMARY_SUBNET) != PRIMARY_SUBNET:
            return None
        validator = unsigned["validator"]
        node, weight, end = validator["nodeID"], int(validator["weight"]), int(validator["end"])
        shares = unsigned.get("shares")
        owner = unsigned.get("validationRewardsOwner", unsigned.get("rewardsOwner")) if tx_type in VALIDATOR_TYPES else None
    stake_outputs = unsigned.get("stake") or []
    funding: dict[str, int] = {}
    for item in stake_outputs:
        output = item.get("output") or {}
        while "amount" not in output and isinstance(output.get("output"), dict):
            output = output["output"]
        for address in _addresses(output):
            funding[address] = funding.get(address, 0) + int(output["amount"])
    start = block_time
    return {
        "transaction_hash": tx_hash, "accepted_at": block_time, "block_height": height, "tx_index": index, "tx_type": tx_type,
        "node_id": node, "start_time": start, "end_time": _utc(end), "duration_seconds": end - int(start.replace(tzinfo=UTC).timestamp()),
        "stake_navax": weight, "shares": shares, "reward_addresses": _addresses(owner) if owner is not None else None,
        "staked_utxo_count": len(stake_outputs), "utxo_stake_navax": staked_navax if stake_outputs else None,
        "delegator_address": min(funding, key=lambda address: (-funding[address], address)) if funding else None,
        "delegator_address_count": len(funding),
        **renewal,
    }


def replay(loaded: dict[str, Any], start_supply: int) -> dict[str, Any]:
    """The walk replayed from one starting counter: every stake with its potential reward, every closed stake with
    its outcome, the counter after each block, and each staking transaction's place in its block's supply changes.

    An ACP-236 auto-renewed validator (AvalancheGo v1.15.0 proposal_tx_executor.go RewardAutoRenewedValidatorTx and
    restakeAutoRenewedValidatorOnCommit) ends each cycle with a reward transaction. On an abort its cycle's reward is
    removed and it leaves. On a commit with a next period, the auto-compound share of the cycle's reward and of the
    delegation fees its delegators paid in the cycle is restaked, and the next cycle starts at the cycle's end with a
    potential reward on the new weight, added to the counter (``protocol.auto_renew_restake``, ``auto_renew_next_cycle``).
    A committed delegation to it adds the fee share of the delegation's reward (``protocol.split_reward``)."""
    supply = start_supply
    stakes: dict[str, dict[str, Any]] = {}
    closed: dict[str, dict[str, Any]] = {}
    renewing: dict[str, dict[str, Any]] = {}
    cycles: list[dict[str, Any]] = []
    walk = loaded["walk"]
    # The starting counter is the counter after the block below the walk.
    after_block: dict[int, int] = {walk[0][0] - 1: start_supply} if walk else {}
    block_deltas: dict[int, list[tuple[int | None, str | None, int]]] = {}
    pending: tuple[tuple[Any, ...], str] | None = None
    for position, row in enumerate(walk):
        height, block_time, block_type, index, tx_hash, tx_type, _, _ = row
        if pending is not None and block_type in ("commit", "abort"):
            reward_row, staking_hash = pending
            rewarded = block_type == "commit"
            if isinstance(staking_hash, dict):
                supply = _end_cycle(renewing, cycles, staking_hash, reward_row, rewarded, supply, block_deltas, height)
                pending = None
            else:
                if staking_hash in stakes:
                    potential = stakes[staking_hash]["potential_reward_navax"]
                else:
                    record = loaded["records"].get(staking_hash)
                    potential = record[7] if record is not None and record[1] in PRIMARY_STAKE_TYPES else 0
                    if potential is None:
                        raise DataError(f"stake {staking_hash} ended and has no potential reward in the Data API record")
                if not rewarded and potential:
                    supply = protocol.supply_after_stake_end(supply, potential, False)
                    block_deltas.setdefault(reward_row[0], []).append((reward_row[3], reward_row[4], -potential))
                delegation = stakes.get(staking_hash)
                if rewarded and delegation is not None and delegation["tx_type"] in DELEGATOR_TYPES:
                    for validator in renewing.values():
                        if validator["node_id"] == delegation["node_id"]:
                            validator["delegatee"] += protocol.split_reward(potential, validator["delegation_shares"])[0]
                closed[staking_hash] = {"reward_row": reward_row, "rewarded": rewarded, "potential": potential}
                pending = None
        elif pending is not None:
            raise DataError(f"the reward proposal before block {height} is followed by neither a commit nor an abort")
        if tx_type == "RewardValidatorTx" or tx_type == "RewardAutoRenewedValidatorTx":
            pending = (row, loaded["reward_of"][position])
        elif tx_type == "SetAutoRenewedValidatorConfigTx":
            config = loaded["reward_of"][position]
            if config["txID"] not in renewing:
                raise DataError(f"block {height} configures auto-renewed validator {config['txID']}, which the walk did not see start")
            renewing[config["txID"]].update(auto_compound_shares=int(config["autoCompoundRewardShares"]), period=int(config["period"]))
        stake = loaded["parsed"][position]
        if stake is not None:
            try:
                reward, supply = protocol.start_stake(block_time.replace(tzinfo=UTC), stake["duration_seconds"], stake["stake_navax"], supply)
            except ModelError as error:
                raise DataError(f"stake {tx_hash} cannot start from counter {supply}: {error}") from error
            stakes[tx_hash] = {**stake, "potential_reward_navax": reward}
            block_deltas.setdefault(height, []).append((index, tx_hash, reward))
            if tx_type == "AddAutoRenewedValidatorTx":
                renewing[tx_hash] = {"node_id": stake["node_id"], "weight": stake["stake_navax"], "potential": reward, "delegatee": 0,
                                     "end": stake["end_time"].replace(tzinfo=UTC), "delegation_shares": stake["shares"],
                                     "auto_compound_shares": stake["auto_compound_shares"], "period": stake["period"]}
                renewing[tx_hash]["row"] = _cycle_row(tx_hash, renewing[tx_hash], 1, block_time.replace(tzinfo=UTC))
                cycles.append(renewing[tx_hash]["row"])
        if position + 1 == len(walk) or walk[position + 1][0] != height:
            after_block[height] = supply
    return {"supply": supply, "stakes": stakes, "closed": closed, "after_block": after_block, "block_deltas": block_deltas, "cycles": cycles}


def _cycle_row(tx_hash: str, validator: dict[str, Any], index: int, start: datetime) -> dict[str, Any]:
    """A running cycle: its outcome columns stay null until its reward transaction and the commit or abort after it."""
    return {"validator_transaction_hash": tx_hash, "node_id": validator["node_id"], "cycle": index, "start_time": start.replace(tzinfo=None),
            "end_time": validator["end"].replace(tzinfo=None), "weight_navax": validator["weight"], "potential_reward_navax": validator["potential"],
            "auto_compound_shares": validator["auto_compound_shares"], "next_period_seconds": None, "reward_transaction_hash": None,
            "rewarded": None, "delegatee_reward_navax": None, "restaked_validation_navax": None, "restaked_delegatee_navax": None,
            "withdrawn_validation_navax": None, "withdrawn_delegatee_navax": None}


def _end_cycle(renewing: dict[str, dict[str, Any]], cycles: list[dict[str, Any]], reward: dict[str, Any], reward_row: tuple[Any, ...],
               rewarded: bool, supply: int, block_deltas: dict[int, list[tuple[int | None, str | None, int]]], height: int) -> int:
    """The counter after an auto-renewed validator's cycle ends with a commit or an abort, and the cycle's outcome.

    On an abort the cycle's reward is forfeited and the delegation fees are paid out (mintRewardOnAbort). On a commit
    with a next period the auto-compound share of both is restaked and the rest paid; on a commit without one, the
    validator leaves and all is paid."""
    validator = renewing.get(reward["txID"])
    if validator is None:
        raise DataError(f"block {reward_row[0]} ends a cycle of auto-renewed validator {reward['txID']}, which the walk did not see start")
    if int(reward["timestamp"]) != int(validator["end"].timestamp()):
        raise DataError(f"the cycle of {reward['txID']} ends at {reward['timestamp']}, not at the replayed end {validator['end']}")
    row = validator["row"]
    row.update(reward_transaction_hash=reward_row[4], rewarded=rewarded, delegatee_reward_navax=validator["delegatee"],
               next_period_seconds=validator["period"], auto_compound_shares=validator["auto_compound_shares"])
    if not rewarded:
        supply = protocol.supply_after_stake_end(supply, validator["potential"], False)
        block_deltas.setdefault(reward_row[0], []).append((reward_row[3], reward_row[4], -validator["potential"]))
        row.update(restaked_validation_navax=0, restaked_delegatee_navax=0, withdrawn_validation_navax=0, withdrawn_delegatee_navax=validator["delegatee"])
        del renewing[reward["txID"]]
    elif validator["period"] > 0:
        restaked, delegatee, paid, paid_delegatee = protocol.auto_renew_restake(
            validator["potential"], validator["delegatee"], validator["auto_compound_shares"], validator["weight"])
        weight = validator["weight"] + restaked + delegatee
        start = validator["end"]
        end, potential, supply_after = protocol.auto_renew_next_cycle(validator["end"], validator["period"], weight, supply)
        block_deltas.setdefault(height, []).append((None, None, supply_after - supply))
        row.update(restaked_validation_navax=restaked, restaked_delegatee_navax=delegatee, withdrawn_validation_navax=paid,
                   withdrawn_delegatee_navax=paid_delegatee)
        validator.update(weight=weight, end=end, potential=potential, delegatee=0)
        validator["row"] = _cycle_row(reward["txID"], validator, row["cycle"] + 1, start)
        cycles.append(validator["row"])
        supply = supply_after
    else:
        row.update(restaked_validation_navax=0, restaked_delegatee_navax=0, withdrawn_validation_navax=validator["potential"],
                   withdrawn_delegatee_navax=validator["delegatee"])
        del renewing[reward["txID"]]
    return supply


def solve_start(loaded: dict[str, Any], anchor: int) -> tuple[int, int, dict[str, Any]]:
    """The lowest and highest starting counters whose replay ends on the anchor, and the lowest one's replay."""
    def reach(start: int) -> int:
        try:
            return replay(loaded, start)["supply"]
        except DataError:
            return anchor + 1

    # The replay adds nearly the same amount from any nearby start, so the start is close to the anchor minus what a
    # replay from the anchor adds. Bisect within a trillion nAVAX of that, or over the whole range if it is not there.
    estimate = 2 * anchor - reach(anchor)
    bracket = (estimate - 10**12, estimate + 10**12)
    if not reach(bracket[0]) < anchor <= reach(bracket[1]):
        bracket = (LOWEST_SUPPLY, anchor)

    def first_at_least(target: int) -> int:
        low, high = bracket
        while low < high:
            middle = (low + high) // 2
            if reach(middle) >= target:
                high = middle
            else:
                low = middle + 1
        return low

    lowest = first_at_least(anchor)
    result = replay(loaded, lowest)
    if result["supply"] != anchor:
        raise DataError(f"no starting counter replays to the node's counter {anchor}; the nearest reaches {result['supply']}")
    highest = first_at_least(anchor + 1) - 1
    return lowest, highest, result


def _validators(loaded: dict[str, Any], result: dict[str, Any]) -> list[tuple[Any, ...]]:
    """Validator periods a delegation can fall in: the walk's, the Data API's records and ended list, and the node's current ones."""
    periods = {tx_hash: (stake["node_id"], stake["start_time"], stake["end_time"])
               for tx_hash, stake in result["stakes"].items() if stake["tx_type"] in VALIDATOR_TYPES}
    for tx_hash, record in loaded["records"].items():
        if record[1] in ("AddValidatorTx", "AddPermissionlessValidatorTx", "AddAutoRenewedValidatorTx"):
            periods.setdefault(tx_hash, (record[2], record[5], record[6]))
    for tx_hash, node, start, end in [*loaded["ended"], *loaded["current"]]:
        periods.setdefault(tx_hash, (node, start, end))
    return [(tx_hash, *period) for tx_hash, period in periods.items()]


def tables(loaded: dict[str, Any], result: dict[str, Any]) -> dict[str, list[tuple[Any, ...]]]:
    """The four tables' rows, in their Snowflake column order."""
    def avax(value: int | None) -> float | None:
        return None if value is None else value / 1e9

    def outcome(tx_hash: str) -> bool | None:
        return result["closed"][tx_hash]["rewarded"] if tx_hash in result["closed"] else None

    by_node: dict[str, list[tuple[Any, ...]]] = {}
    for period in _validators(loaded, result):
        by_node.setdefault(period[1], []).append(period)
    validators, delegators, supply_rows = [], [], []
    for tx_hash, stake in result["stakes"].items():
        days = stake["duration_seconds"] / 86400
        common = (tx_hash, stake["accepted_at"], stake["block_height"], stake["tx_type"], stake["node_id"])
        potential = stake["potential_reward_navax"]
        if stake["tx_type"] in VALIDATOR_TYPES:
            addresses = stake["reward_addresses"] or []
            validators.append((*common, stake["start_time"], stake["end_time"], days, stake["stake_navax"], avax(stake["stake_navax"]),
                               stake["shares"], None if stake["shares"] is None else stake["shares"] / 1e6, potential, avax(potential),
                               outcome(tx_hash), json.dumps(addresses, separators=(",", ":")), addresses[0] if addresses else None,
                               len(addresses), stake["staked_utxo_count"], stake["utxo_stake_navax"]))
        else:
            containing = [period for period in by_node.get(stake["node_id"], []) if period[2] <= stake["start_time"] and period[3] >= stake["end_time"]]
            containing.sort(key=lambda period: (-period[2].timestamp(), period[0]))
            delegators.append((*common, containing[0][0] if containing else None, stake["delegator_address"], stake["delegator_address_count"],
                               stake["start_time"], stake["end_time"], days, stake["stake_navax"], avax(stake["stake_navax"]),
                               potential, avax(potential), outcome(tx_hash), stake["staked_utxo_count"], stake["utxo_stake_navax"]))
        if stake["tx_type"] in PRIMARY_STAKE_TYPES:
            height = stake["block_height"]
            deltas = result["block_deltas"][height]
            prior = sum(delta for index, _, delta in deltas if index is not None and index < stake["tx_index"])
            previous = result["after_block"].get(height - 1)
            supply_rows.append((tx_hash, stake["accepted_at"], stake["tx_type"], height, stake["tx_index"], previous,
                                result["after_block"][height], prior, sum(delta for _, _, delta in deltas),
                                None if previous is None else previous + prior))
    rewards = []
    for staking_hash, closed in result["closed"].items():
        reward_row = closed["reward_row"]
        stake = result["stakes"].get(staking_hash)
        record = loaded["records"].get(staking_hash)
        if stake is not None:
            period = (stake["tx_type"], stake["node_id"], stake["start_time"], stake["end_time"])
        elif record is not None and record[1] in PRIMARY_STAKE_TYPES:
            period = (record[1], record[2], record[5], record[6])
        else:
            period = (None, None, None, None)
        potential = closed["potential"] if period[0] is not None else None
        # The outcome is the walk's own; only a stake the Data API names as outside the Primary Network has none, as in the share.
        outcome = None if record is not None and record[1] not in PRIMARY_STAKE_TYPES and stake is None else closed["rewarded"]
        count, realized = (loaded["paid"][staking_hash][1:3] if staking_hash in loaded["paid"] else (0, 0))
        rewards.append((reward_row[4], reward_row[1], reward_row[0], staking_hash, *period, outcome,
                        potential, avax(potential), realized, avax(realized),
                        None if potential is None else realized - potential, None if potential is None else avax(realized - potential), count))
    return {
        VALIDATORS_ID: sorted(validators, key=lambda row: (row[1], row[0])),
        DELEGATORS_ID: sorted(delegators, key=lambda row: (row[1], row[0])),
        REWARDS_ID: sorted(rewards, key=lambda row: (row[1], row[0])),
        SUPPLY_ID: sorted(supply_rows, key=lambda row: (row[1], row[0])),
        CYCLES_ID: sorted((tuple(cycle[name] for name in CYCLE_COLUMNS) for cycle in result["cycles"]), key=lambda row: (row[0], row[2])),
    }


def compute(inputs: list[dict[str, Any]]) -> tuple[dict[str, list[tuple[Any, ...]]], dict[str, Any]]:
    loaded = _load(inputs)
    walk = inputs[0]
    lowest, highest, result = solve_start(loaded, walk["node_supply"]["supply_navax"])
    rows = tables(loaded, result)
    missing = [staking_hash for staking_hash in result["closed"] if staking_hash not in result["stakes"] and staking_hash not in loaded["records"]]
    summary = {
        "start_supply_navax": lowest,
        "start_supply_solutions": highest - lowest + 1,
        "end_supply_navax": result["supply"],
        "end_height": walk["to_height"],
        "stakes_started": len(result["stakes"]),
        "stakes_closed": len(result["closed"]),
        "stakes_closed_unrewarded": sum(not item["rewarded"] for item in result["closed"].values()),
        "auto_renewed_cycles": len(result["cycles"]),
        "auto_renewed_cycles_ended": sum(cycle["rewarded"] is not None for cycle in result["cycles"]),
        "closed_stakes_without_record": len(missing),
        "delegations_without_validator": sum(row[5] is None for row in rows[DELEGATORS_ID]),
        "rows": {dataset_id: len(value) for dataset_id, value in rows.items()},
    }
    return rows, summary


def parameters() -> dict[str, Any]:
    return {
        "supply_rule": "the walk's first counter is the one whose replay with protocol.start_stake and protocol.supply_after_stake_end ends on the node's counter at the walk's last height",
        "start_rule": "a stake's acceptance and start are its block's time, and its end is the transaction's declared end",
        "earlier_stakes": "a stake that started before the walk takes its potential reward from the Data API record",
        "kernel": "avalanche_research.model.protocol at AvalancheGo 70bd6d0",
    }


def derive(dataset_id: str, output: Path, pinned: dict[str, str] | None = None, root: Path | None = None) -> dict[str, Any]:
    """Build one of the four tables into a new run directory holding ``capture/`` and ``dataset/``."""
    table, columns = _spec(dataset_id)
    if output.exists():
        raise DataError(f"output already exists: {output}")
    catalog = load_catalog()
    definition = dataset(catalog, dataset_id)
    inputs = select_inputs(pinned, root)
    rows, summary = compute(inputs)
    completed_at = now()
    records = [{key: value for key, value in item.items() if key != "path"} for item in inputs]
    identity = sha256(canonical_bytes({"completed_at": completed_at, "inputs": records}))
    capture_receipt = {
        "schema_version": "derived-capture/v1", "capture_id": f"capture:{SOURCE_ID}:{completed_at}:{identity[:12]}",
        "dataset_id": dataset_id, "source_id": SOURCE_ID, "completed_at": completed_at,
        "contract_sha256": contract_hash(catalog, dataset_id), "tool": f"avalanche-research@{__version__}",
        "inputs": records, "parameters": parameters(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=f".{output.name}.", dir=output.parent))
    try:
        (temporary / "capture").mkdir()
        (temporary / "dataset").mkdir()
        (temporary / "capture" / "capture.json").write_bytes(canonical_bytes(capture_receipt))
        parquet = temporary / "dataset" / f"{table}.parquet"
        _write(parquet, columns, rows[dataset_id])
        build_receipt = {
            "schema_version": "derived-build/v1", "dataset_id": dataset_id, "dataset_schema": definition["fields"],
            "source_capture_id": capture_receipt["capture_id"], "completed_at": now(), "tool": f"avalanche-research@{__version__}",
            "summary": {**summary, "rows": len(rows[dataset_id])},
            "outputs": [{"path": parquet.name, "bytes": parquet.stat().st_size, "sha256": sha256(parquet.read_bytes())}],
        }
        (temporary / "dataset" / "build.json").write_bytes(canonical_bytes(build_receipt))
        os.replace(temporary, output)
    except Exception:
        shutil.rmtree(temporary, ignore_errors=True)
        raise
    return {"capture": capture_receipt, "build": build_receipt}


def _write(parquet: Path, columns: dict[str, str], rows: list[tuple[Any, ...]]) -> None:
    connection = duckdb.connect()
    try:
        connection.execute(f"CREATE TABLE rows({', '.join(f'{name} {kind}' for name, kind in columns.items())})")
        if rows:
            connection.executemany(f"INSERT INTO rows VALUES ({', '.join('?' for _ in columns)})", rows)
        connection.execute("COPY rows TO ? (FORMAT PARQUET, COMPRESSION ZSTD)", [str(parquet)])
    finally:
        connection.close()


def check(capture_dir: Path, dataset_dir: Path | None = None, against: Path | None = None, root: Path | None = None) -> dict[str, Any]:
    """Inputs unchanged, contract unchanged, and a rebuild from the recorded inputs gives the same rows. With ``--against``
    the built Snowflake dataset this table backs up: every row both hold, over the hours both cover, is equal."""
    try:
        receipt = json.loads((capture_dir / "capture.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise DataError(f"unreadable capture receipt: {error}") from error
    dataset_id = receipt.get("dataset_id")
    if receipt.get("schema_version") != "derived-capture/v1" or dataset_id not in SPECS:
        raise DataError(f"not a P-Chain backup table capture: {capture_dir}")
    table, columns = SPECS[dataset_id]
    catalog = load_catalog()
    findings: list[str] = []
    checked = ["input run hashes", "catalog contract"]
    if receipt.get("contract_sha256") != contract_hash(catalog, dataset_id):
        findings.append("catalog contract changed since the capture")
    root_dir = datasets.RUNS if root is None else root
    inputs = []
    for item in receipt.get("inputs", []):
        parquet = root_dir / item["run"] / "dataset" / item["parquet"]
        if not parquet.is_file() or sha256(parquet.read_bytes()) != item["sha256"]:
            findings.append(f"input run missing or changed: {item['run']}")
        inputs.append({**item, "path": parquet})
    summary: dict[str, Any] = {}
    if dataset_dir is not None:
        checked.extend(["build hashes", "columns", "rebuild from inputs"])
        built = json.loads((dataset_dir / "build.json").read_text(encoding="utf-8"))
        parquet = dataset_dir / f"{table}.parquet"
        if built.get("source_capture_id") != receipt["capture_id"] or sha256(parquet.read_bytes()) != built["outputs"][0]["sha256"]:
            findings.append("build does not belong to this capture or its Parquet hash differs")
        connection = duckdb.connect()
        try:
            actual = connection.execute("SELECT * FROM read_parquet(?)", [str(parquet)]).fetchall()
            names = [row[0] for row in connection.execute("DESCRIBE SELECT * FROM read_parquet(?)", [str(parquet)]).fetchall()]
        finally:
            connection.close()
        if names != list(columns) or names != [field["name"] for field in dataset(catalog, dataset_id)["fields"]]:
            findings.append("columns differ from the backed-up contract or the catalog")
        summary.update(built.get("summary", {}))
        if not findings:
            rows, _ = compute(inputs)
            if sorted(map(repr, actual)) != sorted(map(repr, rows[dataset_id])):
                findings.append("a rebuild from the recorded inputs differs")
    if against is not None and dataset_id not in OVERLAP:
        raise DataError(f"{dataset_id} backs up no share dataset, so it takes no --against directory")
    if against is not None:
        checked.append("overlap equality with the backed-up Snowflake dataset")
        overlap = compare(dataset_dir / f"{table}.parquet", against, dataset_id)
        summary["overlap"] = overlap
        if overlap["differing_rows"] or overlap["missing_in_backup"] or overlap["missing_in_share"]:
            findings.append(f"the overlap with the share differs: {overlap['differing_rows']} rows differ, "
                            f"{overlap['missing_in_backup']} are missing here, {overlap['missing_in_share']} are missing in the share")
    return {"dataset_id": dataset_id, "capture_id": receipt["capture_id"], "status": "pass" if not findings else "attention",
            "checked": checked, "summary": summary, "findings": findings}


# The key, the time column, and the columns the share cannot know after it stopped: a flag or amount settled later.
OVERLAP = {
    VALIDATORS_ID: ("transaction_hash", "accepted_at", ("rewarded",)),
    DELEGATORS_ID: ("transaction_hash", "accepted_at", ("rewarded",)),
    REWARDS_ID: ("reward_transaction_hash", "rewarded_at", ()),
    SUPPLY_ID: ("transaction_hash", "accepted_at", ()),
}


def compare(backup: Path, share_dir: Path, dataset_id: str) -> dict[str, Any]:
    """Row-for-row equality over the hours both tables cover: from the later first time to the earlier last time. A
    column the share leaves null because its load stopped (``rewarded``) is compared only where the share has it."""
    key, clock, settled = OVERLAP[dataset_id]
    share = next(share_dir.glob("*.parquet"), None)
    if share is None:
        raise DataError(f"no Parquet in {share_dir}")
    columns = list(SPECS[dataset_id][1])
    connection = duckdb.connect()
    try:
        connection.execute(f"CREATE VIEW b AS SELECT * FROM read_parquet('{str(backup).replace(chr(39), chr(39) * 2)}')")
        connection.execute(f"CREATE VIEW s AS SELECT * FROM read_parquet('{str(share).replace(chr(39), chr(39) * 2)}')")
        low, high = connection.execute(f"SELECT greatest((SELECT min({clock}) FROM b), (SELECT min({clock}) FROM s)),"
                                       f" least((SELECT max({clock}) FROM b), (SELECT max({clock}) FROM s))").fetchone()
        window = f"{clock} BETWEEN ? AND ?"
        both = connection.execute(f"SELECT count(*) FROM b JOIN s USING ({key}) WHERE b.{clock} BETWEEN ? AND ?", [low, high]).fetchone()[0]
        missing_backup = connection.execute(f"SELECT count(*) FROM s WHERE {window} AND {key} NOT IN (SELECT {key} FROM b)", [low, high]).fetchone()[0]
        missing_share = connection.execute(f"SELECT count(*) FROM b WHERE {window} AND {key} NOT IN (SELECT {key} FROM s)", [low, high]).fetchone()[0]
        conditions = [f"b.{name} IS DISTINCT FROM s.{name}" if name not in settled else f"(s.{name} IS NOT NULL AND b.{name} IS DISTINCT FROM s.{name})"
                      for name in columns if name != key]
        per_column = {name: connection.execute(f"SELECT count(*) FROM b JOIN s USING ({key}) WHERE b.{clock} BETWEEN ? AND ? AND {condition}",
                                               [low, high]).fetchone()[0]
                      for name, condition in zip([name for name in columns if name != key], conditions)}
        differing = connection.execute(f"SELECT count(*) FROM b JOIN s USING ({key}) WHERE b.{clock} BETWEEN ? AND ? AND ({' OR '.join(conditions)})",
                                       [low, high]).fetchone()[0]
    finally:
        connection.close()
    return {"from": str(low), "to": str(high), "rows_in_both": both, "missing_in_backup": missing_backup, "missing_in_share": missing_share,
            "differing_rows": differing, "differing_by_column": {name: count for name, count in per_column.items() if count}}
