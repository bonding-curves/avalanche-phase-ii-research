#!/usr/bin/env python3
"""Draw every pinned post-Helicon cycle and delegation without clipping.

    uv run --with matplotlib==3.10.8 --group notebook --group model python scripts/figures/helicon_scatter.py OUTPUT

Writes PNG, an all-points CSV and a verified provenance JSON. Delegation density
panels separate AS1-attributed BENQI, other observed owners and unknown owners.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from helicon_eda import ACTIVATION, analyse, frontier, load_inputs
from matplotlib.colors import LogNorm


def invalid_points(points):
    """Return every point that cannot appear on positive logarithmic axes."""
    return points[(points.duration_days<=0)|(points.stake_avax<=0)|
                  ~np.isfinite(points.duration_days)|~np.isfinite(points.stake_avax)]


def draw(out: Path, pin: Path):
    out.mkdir(parents=True, exist_ok=True)
    h,v,d,meta=load_inputs(pin)
    _,_,meta=analyse(h,v,d,meta)
    pre=v[v.start_time.between(ACTIVATION-pd.Timedelta(days=30), ACTIVATION, inclusive="left")]
    dp=d[d.start_time>=ACTIVATION]
    rows=[]
    for label,frame,start in [("Pre30 validator transactions",pre,"start_time"),
                              ("Post validator cycles",h,"cycle_start"),
                              ("Post delegation transactions",dp,"start_time")]:
        f=frame.copy();f["population"]=label;f["start_utc"]=f[start]
        for col in ["cycle_number","auto_renewed","node_status","delegator_group"]:
            if col not in f:f[col]=pd.NA
        rows.append(f[["population","transaction_hash","node_id","start_utc","duration_days","stake_avax","cycle_number","auto_renewed","node_status","delegator_group"]])
    points=pd.concat(rows,ignore_index=True)
    invalid=invalid_points(points)
    if len(invalid):raise ValueError(f"{len(invalid)} nonpositive or missing plotting points")
    points.to_csv(out/"helicon-scatter.csv",index=False,float_format="%.12g")
    groups=["BENQI","Other observed"]
    if (dp.delegator_group=="Unknown reward owner").any():
        groups.append("Unknown reward owner")
    fig=plt.figure(figsize=(12,10.5),layout="constrained")
    grid=fig.add_gridspec(2,len(groups),height_ratios=[1.25,1])
    top=fig.add_subplot(grid[0,:])
    top.scatter(pre.duration_days,pre.stake_avax,c="#b8b8b8",s=12,alpha=.38,label=f"Pre 30d (n={len(pre)})")
    for status,color in [("returning","#2967a1"),("new","#ce7723")]:
        f=h[h.node_status==status];top.scatter(f.duration_days,f.stake_avax,c=color,s=26,alpha=.78,label=f"{status.title()} nodes (n={len(f)} cycles)")
    other=h[~h.node_status.isin(["returning","new"])]
    if len(other):top.scatter(other.duration_days,other.stake_avax,c="#666666",s=26,label="Unknown node status")
    auto=h[h.auto_renewed.fillna(False)]
    top.scatter(auto.duration_days,auto.stake_avax,facecolors="none",edgecolors="#161616",marker="s",s=72,linewidths=1.1,label=f"Auto-renew flag (n={len(auto)})")
    curve=np.geomspace(2,365,400)
    top.plot(curve,[frontier().min_stake_avax(x) for x in curve],c="#943d75",linewidth=2,label="Proposed frontier")
    top.axhline(2000,c="#242424",linestyle="--",linewidth=1,label="Current minimum: 2,000 AVAX")
    top.set_title(f"Validator commitments since Helicon: {len(h)} cycles, {int((h.cycle_number==1).sum())} first cycles\nSnapshot as of {meta['cycle_snapshot_asof_utc']} UTC; last start {meta['cycle_last_start_utc']} UTC",loc="left",fontsize=11)
    top.legend(fontsize=11,loc="upper center",bbox_to_anchor=(.5,-.16),
               ncol=2,frameon=False,borderaxespad=0)
    bottom=[]
    xmax=max(365,float(points.duration_days.max()))*1.03
    for i,group in enumerate(groups):
        ax=fig.add_subplot(grid[1,i]);f=dp[dp.delegator_group==group];bottom.append(ax)
        if len(f):
            density=ax.hist2d(f.duration_days,f.stake_avax,bins=[np.geomspace(2*.97,xmax,55),np.geomspace(dp.stake_avax.min()*.85,dp.stake_avax.max()*1.2,55)],norm=LogNorm(),cmap="Blues" if group=="BENQI" else "Oranges")
            fig.colorbar(density[3],ax=ax,label="Transactions per bin",shrink=.8)
        else:
            ax.text(.5,.5,"No transactions",transform=ax.transAxes,ha="center")
        ax.axvline(14,c="#242424",linestyle="--",linewidth=1)
        ax.set_title(f"{group}: n={len(f):,}",fontsize=10)
        ax.set_ylim(dp.stake_avax.min()*.85,dp.stake_avax.max()*1.2)
    for ax in [top,*bottom]:
        ax.set_xscale("log");ax.set_yscale("log");ax.set_xlim(min(2*.97,points.duration_days.min()*.97),xmax)
        ax.set_xticks([2,7,14,30,90,365],labels=["2","7","14","30","90","365"])
        ax.set_xlabel("Duration in days (log scale)");ax.set_ylabel("Stake in AVAX (log scale)")
        ax.grid(alpha=.16,which="major");ax.spines[["top","right"]].set_visible(False)
    top.set_ylim(min(450,pre.stake_avax.min()*.8,h.stake_avax.min()*.8),max(pre.stake_avax.max(),h.stake_avax.max())*1.25)
    fig.suptitle("Helicon: scheduled duration and stake of every observed commitment",fontsize=14)
    fig.text(.5,-.025,"Delegation density: darker cells contain more transactions; dashed line marks the unchanged 14-day minimum.\n"
             f"{len(dp):,} delegations; last start {meta['delegator_last_start_utc']} UTC. Blue: BENQI; orange: other observed owners.\n"
             "Runs: helicon-commitments-2026-10-06 (cycles); staking-periods-2026-10-06 (transactions).\n"
             "Proposed frontier: exact bounded harmonic curve, floor 500 AVAX, p=1.282, anchored at 2,000 AVAX at 14 days.\n"
             "Three October 6 validator transactions are absent from the older cycle run. All positive points included.\n"
             "Density panels use separate scales. Current attributions describe reward owners, not distinct users.",ha="center",va="top",fontsize=10)
    fig.savefig(out/"helicon-scatter.png",dpi=160,bbox_inches="tight",metadata={"Software":"Helicon descriptive analysis"})
    plt.close(fig)
    meta["plot_points"]={"pre30_validator_transactions":len(pre),"post_validator_cycles":len(h),"post_delegation_transactions":len(dp),"invalid":len(invalid),"out_of_nominal_2_365_range":int(((points.duration_days<2)|(points.duration_days>365)).sum())}
    (out/"helicon-scatter-runs.json").write_text(json.dumps(meta,indent=2,sort_keys=True)+"\n")


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("output",type=Path)
    p.add_argument("--pin",type=Path,default=Path("data/pins/p3-helicon-etf.json"))
    a=p.parse_args();draw(a.output,a.pin)
