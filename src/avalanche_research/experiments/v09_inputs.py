"""The v0.9 holders variant's inputs from a pin: the v0.8.1 candidate's delegation tables and the funds at the origin.

The candidate's tables come from :mod:`~avalanche_research.experiments.v081_inputs`, from the two runs a verified pin
names. The funds come from the issuers' published histories, ``etf-issuers.avax-fund-history``: each fund's AVAX held
on the last valuation day at or before the origin. The pin does not name that run yet, so :func:`fund_holdings_at` takes
the run by name or the newest checked one and :func:`prepare_holders` records which in the table's ``attrs``. The three
figures no history gives, the share a fund stakes, the stake it puts on each validator and the band of durations it
commits for, are the record's on 27 October 2026, held in ``FUND_RULES`` with their evidence, and a sweep's ``holders``
setting may replace the staked share.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

import duckdb
import pandas as pd

from avalanche_research import datasets
from avalanche_research.experiments.v081_inputs import candidate_tables, pinned_inputs
from avalanche_research.model.holder_lifecycle import fund_table
from avalanche_research.model.variants import VARIANTS, Prepared

HOLDERS = "v0.9 holders"
FUND_HISTORY_DATASET = "etf-issuers.avax-fund-history"
AVAX = 10**9
# Per fund: the share of holdings staked, the stake per validator in AVAX, and the duration band in days, with evidence.
# BAVA's validators are the only fund validators traced on chain: 11 held 1,786,084 AVAX at 00:15 UTC on 27 October 2026,
# 66.9% of the 2,670,012 AVAX the fund reported for 26 October, in 25 commitments since Helicon of 15.1 to 19.1 days
# (the Milestone 2 brief, insight DI5). VanEck reports a staked share of 0.80 on its VAVX page (etf-snapshot runs).
# 21Shares reported 78.27% staked on 15 October 2026, one API read. The other two funds take BAVA's stake per validator
# and band, since nothing in the record traces theirs.
FUND_RULES = {
    "BAVA": {"staked_share": 0.669, "validator_stake_avax": 162_371, "min_days": 15, "max_days": 19,
             "evidence": "BAVA's 11 validators, 1,786,084 AVAX, 66.9% of holdings, commitments of 15.1 to 19.1 days, 27 October 2026 (DI5)"},
    "VAVX": {"staked_share": 0.80, "validator_stake_avax": 162_371, "min_days": 15, "max_days": 19,
             "evidence": "VanEck's published staked share 0.80 (etf-snapshot 2026-10-26); stake per validator and band taken from BAVA"},
    "AVAX": {"staked_share": 0.7827, "validator_stake_avax": 162_371, "min_days": 15, "max_days": 19,
             "evidence": "21Shares' reported staked share 78.27% on 15 October 2026, one API read; stake per validator and band taken from BAVA"},
}
TICKER_NAMES = {"BAVA": "Bitwise BAVA", "VAVX": "VanEck VAVX", "AVAX": "21Shares Avalanche ETP"}


def fund_history_parquet(run: str | None = None, root: Path | None = None) -> tuple[Path, str]:
    """The fund history run's Parquet path and name: the named run, or the newest checked one."""
    chosen = datasets.select_run(FUND_HISTORY_DATASET, run=run, newest=run is None, root=root)
    name = chosen["run"] if isinstance(chosen, dict) else str(chosen)
    return datasets.parquet_path(FUND_HISTORY_DATASET, name, root), name


def fund_holdings_at(history_parquet: str | Path, origin: date, rules: dict = FUND_RULES) -> pd.DataFrame:
    """The ``fund_holdings`` table at ``origin``: each fund in ``rules`` with AVAX held on its last valuation day at or
    before the origin, in nAVAX. A fund with no valuation by then is left out."""
    rows = []
    for ticker, rule in rules.items():
        found = duckdb.execute(
            "SELECT valuation_date, avax_held FROM read_parquet(?) WHERE ticker = ? AND avax_held IS NOT NULL "
            "AND valuation_date <= ?::DATE ORDER BY valuation_date DESC LIMIT 1", [str(history_parquet), ticker, origin.isoformat()]).fetchall()
        if not found:
            continue
        held = found[0][1]
        rows.append({"fund": TICKER_NAMES.get(ticker, ticker), "holdings_navax": round(float(held) * AVAX),
                     "staked_share": float(rule["staked_share"]), "validator_stake_navax": int(rule["validator_stake_avax"]) * AVAX,
                     "min_days": int(rule["min_days"]), "max_days": int(rule["max_days"])})
    table = fund_table(rows)
    table.attrs["origin"] = origin.isoformat()
    table.attrs["history"] = str(history_parquet)
    return table


def prepare_holders(pin: Path, origin: date, draws: int = 0, draw_seed: int = 0, root: Path | None = None,
                    fund_run: str | None = None, **tables) -> Prepared:
    """The v0.9 holders variant prepared at ``origin`` from the runs ``pin`` names, with the funds at the origin from
    the fund history run ``fund_run`` or the newest checked one."""
    inputs = pinned_inputs(pin, root)
    history, run_name = fund_history_parquet(fund_run, root)
    funds = fund_holdings_at(history, origin)
    funds.attrs["run"] = run_name
    return VARIANTS[HOLDERS].prepare(str(inputs.periods), origin, inputs.periods_run, draws, draw_seed,
                                     delegations=candidate_tables(str(inputs.periods), str(inputs.delegators), origin),
                                     funds=funds, **tables)
