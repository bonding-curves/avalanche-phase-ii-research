---
title: "F1 · Validator commitments around Helicon"
description: "An equal-window comparison of new validator commitments before and after activation."
date: 2026-10-29
status: draft
---

How did the amount and duration of new validator commitments differ around Helicon? This figure compares every new commitment starting in two equal windows around activation, through 26 October 2026. Each point represents one validator staking transaction.

[Open the interactive figure](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/interactive.html) to compare the eras side by side. Choose scatter or AVAX-days KDE from the dropdown. Duration bars sit above each plot. Stake bars sit between the AVAX axis label on the far left and the main plot, with AVAX tick labels on the right. Both eras share scales and linked zoom and pan. Each plot lists its totals and observation-window length. The HTML works offline after download.

![F1. Stake amount against commitment duration in two adjacent plots, before Helicon on the left and after Helicon on the right.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/f1.png)

Short commitments appear after activation, but account for little of the scheduled AVAX-days. Of 514 post-Helicon commitments, 109 last less than seven days. They represent **21.2% of commitments, 8.7% of committed AVAX and 0.33% of AVAX-days**. None of the 440 pre-Helicon commitments lasts less than seven days.

| Measure | Before Helicon | After Helicon |
| --- | ---: | ---: |
| New validator commitments | 440 | 514 |
| Distinct validator nodes | 309 | 342 |
| Gross AVAX committed | 107.65 million | 117.48 million |
| Scheduled AVAX-days | 5.31 billion | 6.17 billion |
| Median commitment duration | 17.79 days | 15.94 days |
| Stake-weighted mean duration | 49.36 days | 52.52 days |

The median commitment is shorter after activation, while the stake-weighted mean is longer. The two measures answer different questions: the median describes the middle transaction, while the weighted mean gives each AVAX the same weight. The scatterplot shows substantial overlap among commitments of at least 14 days.

## Reading the comparison

Duration defaults to a linear axis, with a toggle for logarithmic positioning in both eras and their top histograms. Stake amount stays logarithmic. The duration toggle changes positioning only: records, weights, bin totals and KDE smoothing stay fixed. Log duration starts at 1.8 days and clips smoothed tails below that value. Bubble **area** is proportional to the square root of AVAX-days, which equal stake multiplied by scheduled duration. Four times the AVAX-days gives twice the bubble area. Both cohorts share the same scale. The size legend shows reference AVAX-day values, and the provenance file gives the exact mapping. Exact overlapping points remain in place, so visible circles understate the number of commitments. Hover details report overlaps within each cohort.

The **KDE** is a smoothed distribution weighted by each commitment's actual AVAX-days. Each era is normalised to 100%, with common density levels, so it compares where commitments concentrate rather than their total volume. Twenty-six contour bands use logarithmic spacing to reveal low-density regions. The marginal bars show exact percentages of each era's AVAX-days per bin, with common bins and bar scales. Thin coloured outlines make nonempty tiny bars visible without inflating their values. Empty bins have no bar. Hover a bar for its AVAX-days and commitment count. A wide bar covers a wider interval, so compare bar heights and hover values rather than visual bar area.

Smoothing takes place in days and log stake, with fixed Gaussian widths of 3 days and 0.20 log₁₀-AVAX in both eras. Duration histograms use weekly bins with additional edges at 2, 14, 30, 90, 180 and 365 days. Blue contours identify before Helicon and orange contours identify after, with identical density levels and relative colour intensity. Each KDE spans the full plotted rectangle, 0–410 days and 1,600–7M AVAX, with each kernel normalised within that rectangle. Smoothed tails can extend beyond observed or protocol bounds and do not establish that commitments occurred there. These widths are display choices, not estimated behavioural responses. The [Bokeh statistical plotting guide](https://docs.bokeh.org/en/latest/docs/user_guide/topics/stats.html) illustrates the histogram and contour rendering used here.

The windows are **19 August 06:00–22 September 15:00 UTC** and **22 September 15:00–27 October 00:00 UTC**, each 34 days and 9 hours. A window includes its start and excludes its end. Cohorts use commitment start time, rather than transaction acceptance time.

Delegations and later automatic renewal cycles are excluded. The same node, and potentially the same capital, can appear in several new transactions. These totals measure gross scheduled commitments, including future days. They do not measure distinct capital, realized lock time or net growth in live stake. The comparison describes observed choices and does not isolate Helicon's causal effect.

## Data and reproduction

[Download all 954 plotted records](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/commitments.csv), [exact aggregates](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/summary.json), [source identities and rules](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/provenance.json), or the [SVG](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/f1.svg).

The frozen `staking-periods-2026-10-27` run supplies the transaction records. Every post-window transaction agrees exactly with its first cycle in `helicon-commitments-2026-10-27`, including node, dates, stake and duration. Input hashes and the extract hash are recorded in the provenance file.

From the repository root, rebuild the figures and aggregates from the included extract:

```bash
uv run --group notebook --with matplotlib==3.10.8 python \
  scripts/figures/helicon_commitment_comparison.py \
  'content/Phase II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments'
```

Add `--extract` only when the two named source runs are installed. That option verifies their hashes and reconciles the post-period transactions against first cycles before recreating the extract. No provider request or model fit is performed.
