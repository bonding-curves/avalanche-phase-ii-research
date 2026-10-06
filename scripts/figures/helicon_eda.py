#!/usr/bin/env python3
"""Descriptive Helicon analysis on explicit, verified p3-helicon-etf runs.

Run from the delivered checkout with its frozen data runs installed::

    uv run --group notebook --group model python scripts/figures/helicon_eda.py OUTPUT

No capture, latest-run selection, fit or causal inference is performed. Tables use
transaction commitments unless explicitly labelled validator cycles. AVAX-days
are gross committed stake times duration, not distinct capital or observed exposure.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from avalanche_research import datasets
from avalanche_research.mechanisms import BoundedHarmonicFrontier

ACTIVATION = pd.Timestamp("2026-09-22 15:00:00")
EXPECTED = {
    "derived.helicon-commitments": "helicon-commitments-2026-10-06",
    "derived.staking-periods": "staking-periods-2026-10-06",
    "derived.operators": "operators-2026-10-06",
    "derived.operator-attributions": "operator-attributions-2026-10-06",
    "p-chain-rpc.blocks": "p-chain-blocks-2026-10-06",
}
BANDS = ["2–<7", "7–<14", "14–<30", "30–<90", "90–<180", "180–365+"]


def frontier():
    return BoundedHarmonicFrontier.through(2000, 14, s_floor_avax=500, p=1.282,
                                         label="Proposed admission frontier")


def load_inputs(pin: Path):
    frozen = json.loads(pin.read_text())
    records = {item["dataset_id"]: item for item in frozen["runs"]}
    paths, checked, receipts = {}, [], {}
    for dataset, run in EXPECTED.items():
        item = records[dataset]
        if item["run"] != run:
            raise ValueError(f"Unexpected pinned run for {dataset}")
        receipt = datasets.receipt(dataset, run)
        receipts[dataset] = receipt
        if receipt["build"]["dataset_id"] != dataset:
            raise ValueError(f"Dataset mapping mismatch: {dataset}")
        if receipt["capture"]["capture_id"] != item["capture_id"]:
            raise ValueError(f"Capture mismatch: {dataset}")
        path = datasets.parquet_path(dataset, run)
        body = path.read_bytes()
        if len(body) != item["bytes"] or hashlib.sha256(body).hexdigest() != item["sha256"]:
            raise ValueError(f"Pinned bytes/hash mismatch: {dataset}")
        paths[dataset] = path
        checked.append(item)
    con = duckdb.connect()
    try:
        v = con.execute("SELECT * FROM read_parquet(?) WHERE role='validator'",
                        [str(paths["derived.staking-periods"])]).df()
        d = con.execute("SELECT * FROM read_parquet(?) WHERE role='delegator' AND start_time>=?",
                        [str(paths["derived.staking-periods"]), ACTIVATION - pd.Timedelta(days=30)]).df()
        b = con.execute("SELECT transaction_hash, tx_type, unsigned_tx, block_time FROM read_parquet(?)",
                        [str(paths["p-chain-rpc.blocks"])]).df()
    finally:
        con.close()
    h = datasets.load("derived.helicon-commitments", EXPECTED["derived.helicon-commitments"])
    o = datasets.load("derived.operators", EXPECTED["derived.operators"])
    a = datasets.load("derived.operator-attributions", EXPECTED["derived.operator-attributions"])
    if h.duplicated(["transaction_hash", "cycle_number"]).any():
        raise ValueError("Duplicate validator cycle key")
    if v.transaction_hash.duplicated().any() or d.transaction_hash.duplicated().any():
        raise ValueError("Duplicate transaction commitment")
    named = a[a.tier.isin(["AS1", "AS2", "AS3"]) & a.name.notna() &
              a.operator_id.notna()].sort_values("attribution_id")
    names = dict(zip(named.operator_id, named.name))
    ids = sorted(o.operator_id.dropna().unique())
    groups = {oid: names.get(oid, f"Group {i:04d}") for i, oid in enumerate(ids, 1)}
    node_group = dict(zip(o.node_id, o.operator_id.map(groups)))
    for frame in (h, v):
        frame["operator_group"] = frame.node_id.map(node_group).fillna("Unknown")
        frame["avax_days"] = frame.stake_avax * frame.duration_days
    reward_owners = {}
    for row in b[b.tx_type.str.contains("Delegator", na=False)].itertuples():
        tx = json.loads(row.unsigned_tx)
        owners = tx.get("rewardsOwner", {}).get("addresses", [])
        reward_owners[row.transaction_hash] = [owner.removeprefix("P-") for owner in owners]
    benqi = set(a.loc[a.tier.isin(["AS1", "AS2", "AS3"]) & (a.name == "BENQI") &
                      (a.subject_kind == "reward-address"), "subject"])
    d["reward_owner_observed"] = d.transaction_hash.isin(reward_owners)
    d["delegator_group"] = ["BENQI" if benqi.intersection(reward_owners.get(tx, [])) else
                            "Other observed" if tx in reward_owners else "Unknown reward owner"
                            for tx in d.transaction_hash]
    d["avax_days"] = d.stake_avax * d.duration_days
    meta = {"pin_name": frozen["name"], "runs": checked, "activation_utc": str(ACTIVATION),
            "validator_last_start_utc": str(v.start_time.max()),
            "cycle_last_start_utc": str(h.cycle_start.max()),
            "delegator_last_start_utc": str(d.start_time.max()),
            "block_observation_end_utc": str(b.block_time.max()),
            "cycle_snapshot_asof_utc": str(pd.Timestamp(receipts["derived.helicon-commitments"]["capture"]["as_of"]).tz_localize(None)),
            "cycle_max_snapshot_gap_hours": receipts["derived.helicon-commitments"]["build"]["summary"]["max_snapshot_gap_hours"],
            "frontier": {"floor_avax": 500, "p": 1.282, "anchor_14d_avax": 2000,
                         "at_2d_avax": frontier().min_stake_avax(2), "at_365d_avax": 500}}
    return h, v, d, meta


def bands(frame):
    return pd.cut(frame.duration_days, [0, 7, 14, 30, 90, 180, np.inf],
                  labels=BANDS, right=False)


def summary(frame, key):
    return frame.groupby(key, observed=True, dropna=False).agg(
        count=("stake_avax", "size"), avax=("stake_avax", "sum"),
        avax_days=("avax_days", "sum"), median_days=("duration_days", "median"),
        median_avax=("stake_avax", "median")).reset_index()


def mix(pre, post):
    rows = []
    for label, frame in [("Pre 30d transactions", pre), ("Post transactions", post)]:
        f = frame.assign(duration_band=bands(frame))
        t = summary(f, "duration_band")
        t.insert(0, "population", label)
        for column in ["count", "avax", "avax_days"]:
            t[f"{column}_share"] = t[column] / t[column].sum()
            t[f"{column}_cdf"] = t[f"{column}_share"].cumsum()
        rows.append(t)
    return pd.concat(rows, ignore_index=True)


def renewal_outcomes(validators, cycles, observed_end):
    """Ended transaction periods with complete, inclusive seven-day follow-up.

    A subsequent transaction or observed auto-renew cycle on the same node is
    evidence of continuation. Later endings are censored, not classified as exits.
    """
    eligible = validators[(validators.end_time >= ACTIVATION) &
                          (validators.end_time <= observed_end - pd.Timedelta(days=7))].copy()
    starts = validators.groupby("node_id").start_time.apply(list).to_dict()
    cycle_starts = cycles.groupby("node_id").cycle_start.apply(list).to_dict()
    eligible["new_transaction_within_7d"] = [
        any(row.end_time <= start <= row.end_time + pd.Timedelta(days=7)
            for start in starts.get(row.node_id, [])) for row in eligible.itertuples()]
    eligible["renewed_within_7d"] = [
        any(row.end_time <= start <= row.end_time + pd.Timedelta(days=7)
            for start in starts.get(row.node_id, []) + cycle_starts.get(row.node_id, []))
        for row in eligible.itertuples()]
    return eligible


def delegation_parents(delegations, validators):
    """Join declared parent transactions, then check closed interval containment.

    Missing parents are retained. Multiple declared parents are refused because
    selecting an arbitrary historical validator schedule would alter the result.
    """
    columns=["transaction_hash","duration_days","stake_avax","delegation_fee_rate","start_time","end_time"]
    if validators.transaction_hash.duplicated().any():
        raise ValueError("Multiple schedules for declared validator transaction")
    parent=validators[columns].rename(columns={c:"parent_"+c for c in columns})
    joined=delegations.merge(parent,left_on="validator_transaction_hash",
                             right_on="parent_transaction_hash",how="left",validate="many_to_one")
    joined["parent_found"]=joined.parent_transaction_hash.notna()
    joined["contained"]=joined.parent_found&(joined.start_time>=joined.parent_start_time)&(joined.end_time<=joined.parent_end_time)
    return joined


def analyse(h, v, d, meta):
    post = v[v.start_time >= ACTIVATION].copy()
    pre = v[v.start_time.between(ACTIVATION - pd.Timedelta(days=30), ACTIVATION, inclusive="left")].copy()
    dp = d[d.start_time >= ACTIVATION].copy()
    db = d[d.start_time < ACTIVATION].copy()
    tables, prose = {}, {}
    missing = post[~post.transaction_hash.isin(h.transaction_hash)].copy()
    tables["reconciliation"] = missing[["transaction_hash", "start_time", "duration_days", "stake_avax"]]
    h["below_proposed"] = h.stake_avax < h.duration_days.map(frontier().min_stake_avax)
    tables["H1"] = summary(h.assign(band=bands(h)), ["band", "below_proposed"])
    below = h[h.below_proposed]
    gap = h[(h.duration_days > 7) & (h.duration_days < 14)]
    prose["H1"] = (f"The cycle dataset has {len(h)} rows, including {(h.cycle_number == 1).sum()} first cycles and {(h.cycle_number > 1).sum()} later cycles. "
                    f"{len(below)} cycles carrying {below.stake_avax.sum():,.3f} repeated-commitment AVAX fall below the exact proposed frontier. "
                    f"There are {len(gap)} cycles strictly between 7 and 14 days. The 210 transaction population has three additional October 6 starts after the cycle dataset's last observed start.")
    tables["H2"] = mix(pre, post)
    prose["H2"] = "The table separates count, gross commitment AVAX and AVAX-days, with cumulative shares in ascending duration bands. Before uses 30 days and after uses the observed post-activation window, so these are duration mixes rather than equal-window volumes. Repeated-cycle weights are excluded from this transaction comparison."
    counts = v[v.start_time < ACTIVATION].groupby("node_id").size()
    hx = h.assign(prior_transactions=h.node_id.map(counts).fillna(0).astype(int),
                  duration_class=np.where(h.duration_days <= 7, "2 to 7 days", np.where(h.duration_days >= 14, "14+ days", "Over 7 to under 14 days")))
    tables["H3"] = hx[["transaction_hash", "cycle_number", "node_status", "duration_class", "duration_days", "stake_avax", "previous_duration_days", "delegation_fee_rate", "operator_group", "prior_transactions"]]
    short = hx[hx.duration_days <= 7]
    prose["H3"] = (f"The at-most-seven-day subset has {len(short)} cycles and {short.stake_avax.sum():,.3f} repeated-commitment AVAX. "
                   "The row table preserves prior duration, fee, current attributed group and pre-activation transaction count per node. Current reward-address grouping is descriptive and does not identify beneficial owners or historic availability.")
    chains = h.groupby("transaction_hash").agg(cycles=("cycle_number", "size"),
        max_cycle_number=("cycle_number", "max"), observed_days=("duration_days", "sum"),
        first_start=("cycle_start", "min"), last_end=("cycle_end", "max"),
        stake_avax=("stake_avax", "first"), flagged_cycles=("auto_renewed", "sum"))
    tables["H4"] = chains.reset_index()
    prose["H4"] = (f"There are {int(h.auto_renewed.sum())} auto-renew-flagged cycles but {(h.cycle_number > 1).sum()} later cycles, so the flag and observed renewal are distinct measures. "
                   f"The most-renewed observed transaction contains {int(chains.cycles.max())} cycles totalling {chains.loc[chains.cycles.idxmax(),'observed_days']:.3f} scheduled days. "
                   "Observed chain duration sums scheduled cycles and includes future scheduled time, rather than measuring elapsed lock time or a completed realized yield.")
    previous = v.sort_values(["node_id", "start_time", "transaction_hash"]).copy()
    previous["previous_duration_days"] = previous.groupby("node_id").duration_days.shift()
    yr = previous[previous.start_time.between(ACTIVATION-pd.Timedelta(days=365), ACTIVATION, inclusive="left") & previous.previous_duration_days.notna()]
    transitions=[]
    for label, f in [("Post returning cycles",h[h.node_status=="returning"]), ("Pre year transactions",yr)]:
        f=f.copy(); f["old_band"]=pd.cut(f.previous_duration_days,[0,7,14,30,90,180,np.inf],labels=BANDS,right=False)
        f["new_band"]=bands(f); f["direction"]=np.where(f.duration_days-f.previous_duration_days < -1/24,"Shorter",np.where(f.duration_days-f.previous_duration_days > 1/24,"Longer","Within one hour"))
        t=summary(f,["old_band","new_band","direction"]);t.insert(0,"population",label);transitions.append(t)
    tables["H5"]=pd.concat(transitions,ignore_index=True)
    prose["H5"]="The duration transition matrix uses a one-hour tolerance to distinguish shorter, longer and essentially unchanged choices. The post table uses the cycle source's prior-duration field, whereas the prior-year transaction table reconstructs consecutive commitments on each node. That difference in units prevents a claim that the matrices estimate the same renewal probability."
    end=pd.Timestamp(meta["block_observation_end_utc"])
    windows=[("Pre 30d",ACTIVATION-pd.Timedelta(days=30),ACTIVATION), ("Pre 90d",ACTIVATION-pd.Timedelta(days=90),ACTIVATION), ("Post",ACTIVATION,end), ("Same dates 2025",ACTIVATION-pd.DateOffset(years=1),end-pd.DateOffset(years=1))]
    pace=[]
    for label,lo,hi in windows:
        f=v[v.start_time.between(lo,hi,inclusive="left")];exposure=(hi-lo).total_seconds()/86400
        pace.append({"window":label,"days":exposure,"transactions":len(f),"avax":f.stake_avax.sum(),"transactions_per_day":len(f)/exposure,"avax_per_day":f.stake_avax.sum()/exposure})
    renewal_end=min(end,pd.Timestamp(meta["cycle_snapshot_asof_utc"]))
    meta["renewal_common_observation_end_utc"]=str(renewal_end)
    eligible=renewal_outcomes(v,h,renewal_end)
    tables["H6"]=pd.DataFrame(pace)
    tables["H6_renewals"]=eligible[["node_id","transaction_hash","end_time","stake_avax","new_transaction_within_7d","renewed_within_7d"]]
    tables["H6_daily"]=post.assign(day=post.start_time.dt.floor("D")).groupby("day").agg(transactions=("stake_avax","size"),avax=("stake_avax","sum")).reset_index()
    prose["H6"]=(f"Exposure-normalized pace uses the observed block clock through {end} UTC, including fractional first and last days. "
                   f"{len(eligible)} ended transaction periods on {eligible.node_id.nunique()} nodes have a mature seven-day follow-up, and {int((~eligible.renewed_within_7d).sum())} periods on {eligible.loc[~eligible.renewed_within_7d,'node_id'].nunique()} nodes have no subsequent transaction or observed cycle start within seven days. "
                   f"Negative renewal checks mature against the common source clock {renewal_end} UTC and combine transaction and cycle starts, preserving a separate new-transaction flag. Snapshot gaps reach {meta['cycle_max_snapshot_gap_hours']} hours, so unobserved short cycles and future renewal remain possible.")
    tables["H7"]=pd.DataFrame([{"population":label,"transactions":len(f),"avax":f.stake_avax.sum(),"top10_avax":f.nlargest(10,"stake_avax").stake_avax.sum(),"top10_share":f.nlargest(10,"stake_avax").stake_avax.sum()/f.stake_avax.sum()} for label,f in [("Pre 30d",pre),("Post",post)]])
    prose["H7"]="The ten-largest-commitment share measures concentration among gross new transaction commitments. It does not identify ten operators or concentration in active stake. Both the numerator and total AVAX are retained for each window."
    tables["H8"]=summary(h.assign(fee_class=np.where(h.delegation_fee_rate==1,"100% fee","Below 100% fee")),["fee_class"])
    tables["H8_mix"]=summary(h.assign(fee_class=np.where(h.delegation_fee_rate==1,"100% fee","Below 100% fee"),band=bands(h)),["fee_class","band"])
    prose["H8"]="A 100% delegation fee assigns all potential delegation rewards to the validator. The table compares its cycles with other fee rates by count, duration and repeated-commitment AVAX. A fee choice alone does not establish a private validator identity or motive."
    reward=post.copy();reward["potential_simple_annual_pct"]=100*reward.potential_reward_avax/reward.stake_avax*365/reward.duration_days
    tables["H9"]=reward[["transaction_hash","start_time","duration_days","stake_avax","potential_reward_avax","potential_simple_annual_pct"]]
    tables["H9_summary"]=reward.assign(band=bands(reward)).groupby("band",observed=True).agg(count=("stake_avax","size"),avax=("stake_avax","sum"),median_potential_pct=("potential_simple_annual_pct","median")).reset_index()
    prose["H9"]="Annualized potential reward is calculated from the admitted transaction's recorded potential reward, stake and original scheduled duration. All post starts fall inside the ACP-285 ramp, so date and duration vary together. This table does not measure rewards actually paid, explain validator choices or identify a response to the ramp. Cycle-level rewards remain unallocated and no per-cycle earned return is inferred for auto-renewing transactions."
    tables["H10"]=mix(db,dp)
    tables["H10_groups"]=summary(dp,["delegator_group"])
    prose["H10"]=(f"The post population contains {len(dp):,} delegation transactions, with a minimum duration of {dp.duration_days.min():.6f} days. "
                    "The table separates BENQI's AS1 reward-owner attribution from other observed owners and missing owner evidence. Delegation coverage ends before validator coverage, and the 14-day protocol minimum is unchanged.")
    dexposure=(d.start_time.max()-ACTIVATION).total_seconds()/86400
    tables["H11"]=pd.DataFrame([{"population":label,"days":days,"count":len(f),"avax":f.stake_avax.sum(),"count_per_day":len(f)/days,"avax_per_day":f.stake_avax.sum()/days} for label,f,days in [("Pre 30d",db,30),("Post observed starts",dp,dexposure)]])
    tables["H11_size"]=dp.groupby("delegator_group").stake_avax.describe().reset_index()
    prose["H11"]="Pace is normalized by 30 pre days and the elapsed post window through the last observed delegation start. The latter endpoint is a coverage proxy, not evidence of capture completeness up to that time. Size quantiles are shown separately for attributed BENQI and the remaining coverage groups."
    joined=delegation_parents(dp,v)
    tables["H12"]=joined[["transaction_hash","validator_transaction_hash","duration_days","stake_avax","parent_found","contained","parent_duration_days","parent_stake_avax","parent_delegation_fee_rate"]]
    matched=joined[joined.parent_found].copy();matched["parent_duration_band"]=pd.cut(matched.parent_duration_days,[0,7,14,30,90,180,np.inf],labels=BANDS,right=False)
    tables["H12_summary"]=matched.groupby(["parent_duration_band","parent_delegation_fee_rate"],observed=True).agg(count=("stake_avax","size"),avax=("stake_avax","sum"),parent_nodes=("node_id","nunique"),median_parent_avax=("parent_stake_avax","median")).reset_index()
    prose["H12"]=(f"{int(joined.parent_found.sum()):,} of {len(joined):,} delegations join their declared parent validator transaction, and {int(joined.contained.sum()):,} lie within that parent's scheduled interval. "
                    f"Zero have multiple declared parent rows, and {int((joined.parent_duration_days<14).sum())} joined delegations target parents scheduled for less than 14 days. "
                    "Parent rows describe original transaction schedules, so auto-renewed-cycle containment would require an explicit cycle-interval join if violations appear.")
    tables["H13"]=summary(dp,["delegator_group"])
    tables["H13"]["count_share"]=tables["H13"]["count"]/len(dp);tables["H13"]["avax_share"]=tables["H13"].avax/dp.stake_avax.sum()
    tables["H13_nodes"]=summary(dp,["delegator_group","node_id"])
    tables["H13_duration"]=summary(dp.assign(band=bands(dp)),["delegator_group","band"])
    bn=dp[dp.delegator_group=="BENQI"]
    prose["H13"]=(f"BENQI has {len(bn):,} post delegation transactions carrying {bn.stake_avax.sum():,.3f} AVAX, sent to {bn.node_id.nunique()} distinct nodes. "
                   "Its name uses permitted AS1 reward-owner evidence from the pinned attribution run. This counts repeated commitments and receiving nodes rather than distinct users or beneficial owners.")
    common=d.start_time.max();vp=post[post.start_time<=common];dc=dp[dp.start_time<=common]
    tables["H14"]=pd.DataFrame([{"population":label,"role":role,"count":len(f),"avax":f.stake_avax.sum(),"avax_days":f.avax_days.sum(),"window_days":days,"avax_days_committed_per_calendar_day":f.avax_days.sum()/days} for label,role,f,days in [("Pre 30d","Validator",pre,30),("Pre 30d","Delegator",db,30),("Common post window","Validator",vp,dexposure),("Common post window","Delegator",dc,dexposure)]])
    prose["H14"]="AVAX-days sum full scheduled duration times stake for new transactions, even when the lock extends beyond the observation window. Validator and delegator post rates use the same endpoint at the last observed delegation start. These gross commitments neither measure distinct capital nor the integral of active network stake."
    tables["H15"]=h.groupby(["operator_group","node_status"],dropna=False).agg(cycles=("stake_avax","size"),nodes=("node_id","nunique"),avax=("stake_avax","sum"),median_days=("duration_days","median"),min_days=("duration_days","min"),max_days=("duration_days","max")).reset_index()
    prose["H15"]="The operator table reports cycles, distinct nodes and repeated-commitment AVAX for each current group and node-status label. Only AS1 to AS3 attribution records supply public group names and all other operators are numbered. Current grouping does not make these groups retrospective causal training categories."
    tables["H16"]=pd.DataFrame([{"check":"Delegation reward-owner missing","count":int((~dp.reward_owner_observed).sum()),"avax":dp.loc[~dp.reward_owner_observed,"stake_avax"].sum()}, {"check":"Post cycles at <=2.01 days","count":int((h.duration_days<=2.01).sum()),"avax":h.loc[h.duration_days<=2.01,"stake_avax"].sum()}, {"check":"Post cycle duration nonpositive or stake nonpositive","count":int(((h.duration_days<=0)|(h.stake_avax<=0)).sum()),"avax":0}, {"check":"Parent interval containment violations","count":int((joined.parent_found&~joined.contained).sum()),"avax":joined.loc[joined.parent_found&~joined.contained,"stake_avax"].sum()}])
    prose["H16"]="Additional checks examine a two-day ridge, reward-owner missingness, nonpositive plotting values and parent-interval violations. Every tested count remains in the table, including zero findings. The data cannot establish an institutional-capital inflow or motivation from stake size, fee or a two-week before-and-after comparison."
    meta.update({"cycles":len(h),"first_cycles":int((h.cycle_number==1).sum()),"later_cycles":int((h.cycle_number>1).sum()),"validator_post_transactions":len(post),"validator_pre30_transactions":len(pre),"delegator_post_transactions":len(dp),"delegator_pre30_transactions":len(db),"missing_from_cycle_run_transactions":len(missing),"parent_missing":int((~joined.parent_found).sum()),"parent_containment_violations":int((joined.parent_found&~joined.contained).sum()),"benqi_post_delegations":len(bn),"benqi_post_avax":float(bn.stake_avax.sum()),"renewal_mature_periods":len(eligible),"renewal_no_observed_start_within7d":int((~eligible.renewed_within_7d).sum()),"below_proposed_cycles":len(below),"below_proposed_repeated_avax":float(below.stake_avax.sum())})
    return tables,prose,meta


def execute(out: Path, pin: Path):
    out.mkdir(parents=True,exist_ok=True)
    h,v,d,meta=load_inputs(pin);tables,prose,meta=analyse(h,v,d,meta)
    for name,frame in tables.items():
        frame.to_csv(out/f"{name}.csv",index=False,float_format="%.12g")
    (out/"helicon-analysis.json").write_text(json.dumps({"provenance":meta,"interpretation":prose},indent=2,sort_keys=True)+"\n")
    return h,v,d,tables,prose,meta


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output",type=Path)
    parser.add_argument("--pin",type=Path,default=Path("data/pins/p3-helicon-etf.json"))
    args=parser.parse_args();execute(args.output,args.pin)
