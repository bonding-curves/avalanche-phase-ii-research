---
title: "Helicon figures for the brief"
description: "Four panels in two matched pairs, with logarithmic duration and stake axes."
date: 2026-10-29
status: draft
---

Four panels are supplied as **two matched pairs**: before/after scatter and before/after KDE. Both duration and stake axes are logarithmic. Each panel includes the five requested totals and AVAX-day marginal histograms.

| Pair | Print image | Editable vector |
| --- | --- | --- |
| Scatter | [300 dpi PNG](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/report-exports/helicon-scatter.png) | [SVG](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/report-exports/helicon-scatter.svg) |
| KDE | [300 dpi PNG](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/report-exports/helicon-kde.png) | [SVG](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/report-exports/helicon-kde.svg) |

[Download the two-page PDF](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/report-exports/helicon-report-figures.pdf) to review both pairs at their intended size.

Place each pair at **170 mm wide × 115 mm high**, preserving its aspect ratio. Use SVG where supported, or PNG otherwise. Stack the pairs vertically or on successive pages. Reducing them into a four-panel grid makes the labels too small.

## Scatter

![Before and after Helicon, shown as adjacent scatterplots with logarithmic duration and stake axes.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/report-exports/helicon-scatter.png)

Suggested caption: **New validator commitments before and after Helicon.** Each point is one transaction. Bubble area is proportional to the square root of scheduled AVAX-days, with one size scale across eras. Both axes are logarithmic. Marginal bars show each bin's share of the era's AVAX-days.

## KDE

![Before and after Helicon, shown as adjacent AVAX-day weighted density plots with the same axes and marginal histograms.](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/report-exports/helicon-kde.png)

Suggested caption: **Where scheduled AVAX-days concentrate.** Density is weighted by AVAX-days, with the same smoothing widths of 1.5 days and 0.12 log₁₀-AVAX in both eras and 16 logarithmically spaced colour bands. Both axes are logarithmic. No pre-Helicon commitment lasted less than 14 days. Smoothing below 14 days before Helicon and 2 days after is hidden. Marginal bars show exact AVAX-day shares.

The KDE is calculated in days and log stake and normalised to 100% per era before the display mask. Hidden tails are not redistributed, so the visible density integrates to less than 100%. Other smoothed tails can extend beyond observed commitments.

Both pairs compare equal 34-day, 9-hour windows around 22 September 2026, 15:00 UTC, through 26 October. These are gross scheduled commitments, including future days and potentially repeated capital. The comparison does not establish a causal effect. See the [data, definitions and methods](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/) for exact windows and exclusions.

## Reproduction

From the repository root, use the included extract:

```bash
uv run --group notebook --with matplotlib==3.10.8 python \
  scripts/figures/helicon_report_exports.py \
  'content/Phase II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments'
```

The generator verifies the extract hash and writes these five graphics files plus the [export specification](/Phase-II/Wiki/Memos/drafts/2026-10-30-research/helicon-commitments/report-exports/export-spec.json). No source-data refresh or model run is required.
