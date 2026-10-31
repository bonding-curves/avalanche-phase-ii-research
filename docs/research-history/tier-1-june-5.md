# Tier-1 Results & Notebook Series — Meeting Prep 2026-06-05

Historical edition. Context added 30 October 2026.

The June meeting brief presents an early comparison of linear and quadratic reward formulas, with model diagrams, outcome distributions and trajectory plots. The source labels the model 0.3.2. It also discloses an uncalibrated behavioural sensitivity and omitted supply growth. Its rankings therefore describe that historical simulation, with its stated assumptions.

The claim that directions are firm does not establish how validators would respond on the network. The [October methodology](../review/2026-10-30/modeling.md#4-the-response-to-reward-is-separate-from-habitual-behaviour) separates fitted habits from assumed responses to rewards. The [October results](../review/2026-10-30/results.md) use model v0.8.0 and a different experiment.

The body is dated 5 June, but the recovered version includes edits through 1 July. It is not an authenticated copy of the exact pre-read available on the meeting day.

## Source record

The source records creation on June 5, 2026 1:21 AM and last editing on July 1, 2026 1:34 AM. Its timezone is unspecified. The creator field names Shawn Anderson, which does not establish sole authorship. The preserved export is labelled 1 July 2026.

The body names BCRG Engineering as its sender and Eric Lu as its recipient. Its stated date is 5 June 2026. The source alone does not establish when it was shared or accepted.

[Original Markdown as text](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/original-37660ed9-0ab7-800b-91d4-c2c4e5b43e03.txt) · [Source identities and hashes](assets/content/Phase%20II/Wiki/Research%20History/manifest.json) · [Research chronology](README.md)

The reading edition changes heading depth, metadata line breaks and local image routes. Earlier repository-file links lead to a list of their original URLs. The retained text download preserves the exported bytes.

## Original text

<!-- historical-original:start -->
### Tier-1 Results & Notebook Series — Meeting Prep 2026-06-05

Created By: Shawn Anderson  
Creation Time: June 5, 2026 1:21 AM  
Last Edited Time: July 1, 2026 1:34 AM  
Sprint: Sprint 3  

### MEMO: Tier-1 Sweep Results and Trajectory Analysis — 2026-06-05

**Date**: 2026-06-05  
**To**: Eric Lu, Avalanche Foundation  
**From**: BCRG Engineering  
**Subject**: Sprint #3 enabled the development of simulation infrastructure by implementing a full cadcad model along with KPIs and Goals from aggregated metrics for analyzing different lockup yield curves.  

We report the first valid Tier-1 parameter sweep of the Avalanche staking model: 41,472 simulated trajectories spanning the governance×environment grid, fully reproducible (git SHA and seed recorded per run; milestone tag `v0.3.2-tier1`). **Section 1** presents the model structure and the headline results. The quadratic $Y(d)$ reward curve (ACP-273 Open Question 2) produces a higher mean staking ratio than the chain's current linear curve (Θ 0.548 vs 0.513) and a smaller validator profitability shortfall (−0.008 vs −0.023), evaluated across the full swept space. **Section 2** presents the same sweep at trajectory resolution, including a paired twin-comparison analysis: across 20,736 configuration pairs that differ only in the reward curve, the quadratic never produces a lower staking ratio than the linear, on any of the 366 simulated days. **Section 3** indexes the notebook series. Two qualifications hold throughout: the behavioral sensitivity parameter is not yet calibrated against historical data (INC-004), so we treat directions as firm and magnitudes as provisional; and the model does not yet include validator entry/exit or supply growth from emissions (INC-010). Both are scheduled work with named dependencies on the agenda for this meeting.

---

### 1 · Model Structure and Headline Results

#### 1.1 The Simulation Engine: Differential Model Specification

`[image: 07-differential-spec.png]`

![07-differential-spec.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/07-differential-spec.png)

The figure shows the simulation engine in the differential-specification form used across the cadCAD community. The model executes as four Partial State Update Blocks (PSUBs) in fixed order once per simulated day. Within each column, cylinders denote state variables read as inputs, dashed boxes denote parameters, diamonds denote policy functions (the decision logic), and capsules denote state-update functions (the bookkeeping that writes the next state). Every node corresponds one-to-one to a function in the `avalanche_model` package.

The daily cycle proceeds as follows. Block 0 advances the AVAX price by one step of a geometric Brownian motion. Block 1 evaluates the staker behavioral response: the policy compares the current staking reward rate against the external opportunity cost and emits stake entry and exit flows. Block 2 recomputes network-level state from the new totals — the staking ratio and the reward rate itself. Block 3 accounts for the rewards emitted. Iterating this cycle 365 times produces one trajectory.

Two properties of the implementation are visible structurally in the diagram. First, circulating supply appears as an input-only variable: no update function writes it, which records open incident INC-010 (emissions do not yet grow the supply; results over horizons beyond one year would read optimistic). Second, Block 3's cumulative-rewards update reads the previous day's emission value, which is the correct cadCAD semantics — all update functions within a block read the incoming state, not each other's outputs.

#### 1.2 From Governance Levers to Foundation Goals: The System Map

`[image: 05-system-map.png]`

![05-system-map.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/05-system-map.png)

The system map places the simulation engine in its decision context. Reading left to right: the parameters governance can set (governance levers) and the parameters the environment sets (market conditions) feed the per-timestep policies; policies drive state updates; the daily state series reduce to five per-trajectory Key Performance Indicators (KPIs); and the KPIs score the three Foundation goals. The KPI-to-goal assignment shown is the one implemented in the codebase: validator profitability scores G1 (incentive alignment); APR volatility and staking volatility score G2 (participation distribution); staking ratio and validator count score G3 (network security).

One structural fact conditions the interpretation of every result below. The Avalanche reward rate has no direct dependence on the staking ratio: the protocol sets rates as a function of commitment duration and supply scarcity only. There is no feedback controller in the protocol that steers the staking ratio toward a target. Regulation of the staking ratio therefore happens entirely through staker behavior — the comparison of the offered yield against the external opportunity cost. This is why the behavioral calibration milestone (M1c) is the precision bottleneck for every staking-ratio claim in this memo, and why the validator interviews and the second-regime data acquisition appear as agenda items: they identify the behavioral parameters that the protocol-side mathematics cannot.

#### 1.3 Headline Results: The Tier-1 First Look (model 0.3.2, data SHA f96edcc)

The sweep evaluates every combination of the governance levers (reward-curve form, consumption-rate bounds, duration bounds, validator reward share) against every tested environment (opportunity cost, price volatility, representative commitment duration): 41,472 configurations, one 365-day trajectory each. Each trajectory reduces to five KPI scalars. We verify each number below mechanically against the results tensor before the memo ships; a verification gate fails the build if any stated number drifts from the data by more than 0.005.

- **Θ = 0.531 ± 0.088** across 41,472 configurations; 42% of the policy space lands in the [50–60%] target band for the staking ratio.
- **Quadratic vs linear**: mean Θ 0.548 vs 0.513; mean validator profitability −0.008 vs −0.023. The proposal outperforms the status quo on both axes, evaluated across the full space rather than at a tuned point.
- **The consumption-rate floor is a weak lever**: raising r_min from 7% to 10% raises mean Θ by approximately 0.6 percentage points in total. Changing the curve form moves the same statistic approximately six times as much. Curve shape dominates floor level in this design space.
- **Validator profitability is negative across most of the space**: against a 5% opportunity cost, mean profitability is below zero under both curves for most tested configurations (sign-crossings exist; maximum +0.036). We flag this as a finding for discussion rather than a model defect — it quantifies the wedge the duration levers are intended to close.
- **Standing qualifications**: the model contains no validator entry/exit process, and the behavioral sensitivity is not yet calibrated (INC-004). Directions and orderings are robust; magnitudes are provisional pending M1c.

#### 1.4 The Staking-Ratio Distribution by Curve

`[image: 01-theta-quad-vs-linear.png]`

![01-theta-quad-vs-linear.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/01-theta-quad-vs-linear.png)

Each trajectory reduces to its time-averaged staking ratio; the figure shows the distribution of that statistic over all 41,472 trajectories, split by reward curve, with the [50–60%] target band shaded. Two observations. First, the quadratic distribution sits to the right of the linear distribution; the dashed rules mark the per-curve medians (0.505 linear, 0.536 quadratic), and the means cited in §1.3 (0.513, 0.548) show the same ordering. Second, both distributions are wide. The width is not sampling noise — the sweep is deterministic — but the genuine range of outcomes across the swept space, which deliberately includes both hostile environments (high external yields) and favorable ones. A policy evaluation that reported only the central tendency would understate how much the environment, rather than the lever, determines the outcome.

#### 1.5 The Profitability Distribution: A Negative Result Reported Directly

`[image: 02-profitability-quad-vs-linear.png]`

![02-profitability-quad-vs-linear.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/02-profitability-quad-vs-linear.png)

The same construction for the validator-profitability KPI, defined as the trajectory mean of the realized staking yield minus the external opportunity-cost rate. Most of the probability mass sits below zero under both curves: across the majority of tested configurations, validating does not beat a 5% outside option in this model. We report this directly because it is decision-relevant: it locates the parameter regions where incentive alignment (goal G1) fails, and it quantifies how far the duration levers must move yields to close the gap. The quadratic reduces the mean shortfall from −0.023 to −0.008, and the mass visible in positive territory (clusters between +0.02 and +0.036) marks the configurations that already cross into profitability. The per-curve medians (dashed) summarize the same ordering.

#### 1.6 The Object Under Study: The Two Reward Schedules

`[image: 06-actual-curve-pair.png]`

![06-actual-curve-pair.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/06-actual-curve-pair.png)

The two schedules every result above compares, computed from the model's reward functions rather than sketched. The blue line is the chain's current consumption rate, C(d): a linear interpolation between the floor r_min and the ceiling r_max as a function of stake duration, expressed as a per-year rate that the protocol then prorates by the stake's fraction of the minting period. The orange line is the ACP-273 Open Question 2 quadratic, Y(d): a convex schedule that is already the full duration multiplier — proration is composed into the function and must not be applied a second time. (That distinction is incident INC-005; our implementation follows the Option 2 reading, under which Y(d) is the effective annual yield. Confirming this reading is item 2d on today's agenda.) The two schedules share endpoints and differ in between: the quadratic pays less than the linear for short commitments and concentrates yield on long ones. Every comparative result in this memo is downstream of that difference.

#### 1.7 The Empirical Substrate: One Year of Daily Staking Data

`[image: 13-nb04-daily-series-panel.png]`

![13-nb04-daily-series-panel.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/13-nb04-daily-series-panel.png)

The simulation's starting conditions and calibration targets come from this data: one year of daily staking series from the silver-layer manifest (Snowflake, CoinGecko, Snowpeer; window chosen 100% post-Etna so no regime change contaminates it — the dashed rule marks the Granite upgrade). Top to bottom: cumulative gross stake (see below), active validator and delegator counts, the AVAX price, circulating supply, and the stake entry/net-flow series. Two features of this picture matter for interpreting everything above. First, the series that vary are what anchor the model's genesis state and will anchor its behavioral calibration. Second, the limitations are visible directly in the data itself. The top panel reads in billions of AVAX against a 420M circulating supply because the column accumulates stake entries without netting exits — the exit series is currently a stub — so the panel carries timing information (when stake arrived) but not level information (the network's actual staked balance is approximately 245M AVAX). The circulating-supply panel is flat for the analogous reason: a constant-propagated snapshot rather than a daily series. Both are known issues on the M1b list that the Snowflake access request (Path Forward, item 1) unblocks. The data-foundations notebook (04) documents this substrate column by column, including the identifiability diagnostic that motivates the calibration data asks.

#### 1.8 The Reward Budget and the Staking Premium

`[image: 14-nb01-supply-and-yield.png]`

![14-nb01-supply-and-yield.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/14-nb01-supply-and-yield.png)

Two panels connect the protocol mathematics to the live economy. The top panel shows circulating supply against the 720M AVAX hard cap: supply sits at roughly 60% of the cap, leaving 288M AVAX of issuance headroom. That headroom is the scarcity term in the reward formula — the same (SupplyCap − S̄)/S̄ factor that appears in the differential specification's Block 2 — so this panel is the reward budget drawn from chain data: as issuance approaches the cap and Primary-Network fees burn supply outright, the budget tightens. The bottom panel shows the staking reward rate against the FRED Fed funds rate; the shaded gap is the staking premium, which widened from roughly 1.0 to 1.7 percentage points over the window as the macro rate eased. That premium is precisely the spread the behavioral model's entry/exit response runs on — the model's stakers compare these two lines. One disclosed caveat carries over from §1.7: the staking APR shown is a snapshot constant pending the daily series (the M1b pull), while the risk-free leg is the fresh daily FRED series.

---

### 2 · Trajectory-Level Analysis: The Sweep at Daily Resolution

Section 1 compresses each simulated year to scalar KPIs. This section presents the same sweep at daily resolution — 41,472 paths of the staking ratio, 366 days each — in five views. Each view answers a distinct question: what individual trajectories look like (§2.1), how the full distribution evolves (§2.2), where trajectories concentrate (§2.3), which configurations drive the curve effect (§2.4), and what the effect is under controlled comparison (§2.5).

#### 2.1 Individual Trajectories: A Sample of the Raw Output

`[image: 08-spaghetti.png]`

![08-spaghetti.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/08-spaghetti.png)

Each thread is one simulated staking economy over 366 days, beginning from the measured genesis state of the network (Θ ≈ 0.583; staked supply, circulating supply, validator count, and price anchored to the 2026-05-21 silver-layer snapshot). The figure samples 180 of the 41,472 trajectories, colored by reward curve, and overlays each curve's median computed across all trajectories. The dispersion from a common starting point reflects the breadth of the swept space: trajectories declining toward Θ ≈ 0.3 correspond to environments where high external yields draw stake away; trajectories rising toward Θ ≈ 1.0 correspond to configurations whose rewards over-lock the supply. Both extremes are outside the target band, which is why goal G3 specifies a band rather than a maximum: the staking ratio can fail high as well as low.

#### 2.2 The Full Distribution Over Time: Quantile Fans

`[image: 09-fan.png]`

![09-fan.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/09-fan.png)

The same data with no sampling: for each simulated day we compute the 5th, 25th, 50th, 75th, and 95th percentiles of the staking ratio across all trajectories, per curve. The light band spans the central 90% of trajectories, the dark band the central 50%, and the solid line the median. At day 0 the two fans coincide by construction — every trajectory starts from the same genesis state. They separate as the simulated year progresses: the quadratic's median remains near the target band while the linear's declines below 0.45. The separation grows approximately monotonically, which indicates a persistent flow effect (the curves induce different stake entry/exit rates day after day) rather than a one-time level shift. We consider this the most faithful single-figure summary of the Tier-1 sweep.

#### 2.3 Trajectory Density: Where the Paths Concentrate

`[image: 10-density.png]`

![10-density.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/10-density.png)

Each cell counts the trajectories passing through that (day, staking-ratio) coordinate, on a logarithmic color scale; the figure aggregates all 41,472 paths with no sampling or averaging. The prominent horizontal striping requires correct interpretation: the stripes are families of configurations that share the levers determining the staking path and therefore travel identical trajectories. They are an artifact of the sweep's deterministic execution — under incident INC-011, price stochasticity does not yet propagate into staking decisions, so no within-configuration spread exists — and not emergent attractors of the dynamics. We include the figure because it makes the deterministic structure of the current model version visible at a glance, which is the honest baseline against which the Tier-2 stochastic robustness pass (queued behind this analysis) will be read.

#### 2.4 Decomposition by Commitment Duration: Where the Curve Effect Lives

`[image: 11-small-multiples.png]`

![11-small-multiples.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/11-small-multiples.png)

The fan construction of §2.2, faceted by the representative commitment duration — the stake duration at which the reward schedule is evaluated in a given configuration. The decomposition localizes the curve effect. At 30- and 90-day commitments the two curves' bands nearly coincide: both schedules pay little for short stakes, so the policy choice is approximately irrelevant there. At 180 days the bands separate; at 365 days the quadratic clearly outperforms. This is the design intent of the proposal expressed in the dynamics — the quadratic concentrates yield on long commitments, so its advantage appears exactly where long commitments are economically on the table. It also identifies the highest-leverage empirical question in the project: the realized advantage on the live network depends on the distribution of actual stake durations, which is the subject of the [validator-interview protocol](tier-1-june-5.md#historical-reference-1) and the duration-distribution question (Q-dur) in the discussion queue.

#### 2.5 Controlled Comparison: Paired Configuration Twins

`[image: 12-paired-diff.png]`

![12-paired-diff.png](assets/content/Phase%20II/Wiki/Briefs/historical/tier-1-june-5/figures/12-paired-diff.png)

The sweep's full-factorial design pairs every configuration with an exact twin: identical environment and identical levers except the reward curve. This permits a controlled comparison free of composition effects — for each of the 20,736 pairs, on each day, we compute the staking-ratio difference (quadratic world minus linear world) and plot the distribution of that difference. The bands span the 5th–95th and 25th–75th percentiles of pairs; the line is the median; the dashed rule marks zero (no effect).

The result is one-sided: across all 20,736 pairs and all 366 days, the difference never goes below zero. The median final-day difference is modest (+0.4 percentage points); the upper tail reaches +28 percentage points in configurations combining long commitment durations with reward-sensitive environments. The one-sidedness has a mechanical explanation rather than a statistical one: over this parameter grid, the quadratic's effective yield is greater than or equal to the linear's prorated yield at every duration, so the behavioral response can only move the staking ratio upward. The simulation confirms an inequality the schedule definitions imply — which is evidence the machinery is wired correctly, and it bounds the policy claim precisely: within this model, adopting the quadratic carries no downside on the staking-ratio axis. The open questions are the magnitude of the effect (pending behavioral calibration, INC-004) and the profitability–security trade-off documented in §1.5.

---

### 3 · The Notebook Series

The research series documents the work end to end in four canonical notebooks. Each is rendered with code cells stripped and reads top to bottom on GitHub:

| Notebook | What it covers |
| --- | --- |
| [01 · Inteline in the BCRG's methodology. Houration-distribution quew do these tools contribute to a "reproducible and auditable" recroduction](tier-1-june-5.md#historical-reference-2) | Conceptual orientation — the Avalanche staking subsystem, the validator/delegator coupled market, the Lu (2026a) equilibrium framing, Phase II scope |
| [02 · cadCAD Model](tier-1-june-5.md#historical-reference-3) | The simulation engine — state variables, parameter taxonomy (protocol / governance / environment / behavioral), policy and state-update functions, stochastic drivers, and a toy trajectory run on the real package |
| [03 · PSUU Framework](tier-1-june-5.md#historical-reference-4) | The methodology — Parameter Selection Under Uncertainty: the KPI tensor, the two-tier sweep design, goal aggregation, and the living Tier-1 scoreboard (§9) |
| [04 · Data Foundations](tier-1-june-5.md#historical-reference-5) | The data substrate — silver-layer staking series, signal census, the data-starvation identifiability diagnostic, and the fresh FRED opportunity-cost series |

#### Synchronization

- **Repo**: [AVL-Foundation/ext-bcrg-validator-research](https://github.com/AVL-Foundation/ext-bcrg-validator-research) (review-gated mirror of BCRG engineering)
- **Milestone tag**: `v0.3.2-tier1`
- **Slack**: #ext-bcrg-af (live)
- **Incident log**: [docs/incident-log.md](tier-1-june-5.md#historical-reference-6) — every numbered incident cited in this memo (INC-004, INC-005, INC-009, INC-010, INC-011, INC-013), each with root cause, status, and the resolving commit where closed

#### Path Forward

1. **~~Snowflake access** — a reader account for `AVALANCHE_PRIMARY_NETWORK_DATA`, or we place a card on our own account. This gates the M1b live data pull (daily APR, real exits, true active counts), which gates honest behavioral calibration.~~
    1. I got access
2. **Requests sent to snowpeer**:
    1. Historical daily staking APR (/v1/series/staking-apr or similar) — the single highest-value series for us; our behavioural calibration needs a daily reward-rate history
    and currently only has a point-in-time snapshot.
    2. Historical daily active stake + active validator/delegator counts — lets us compute a true daily staking ratio instead of bracketing it from snapshots.
    3. Daily stake entries/exits breakdown — exits especially; entries we can derive, exits we cannot.
    4. Bug report: /v1/monetary/circulating-supply returns {"amount":0} — we currently fall back to CoinGecko market-cap ÷ price. Happy to share repro details.
3. **Validator interviews** — the [protocol is drafted](tier-1-june-5.md#historical-reference-1) (8 questions, each mapped to the parameter it identifies); we request the contact list and schedule 6–8 interviews against the single-regime identification gap.
    1. Starting this in July
    

Following Tier-1 analysis: the Tier-2 robustness pass (top-N configurations × 4 behavioral forms × 30 Monte Carlo runs), the INC-010 supply-growth closure, and the M1c calibration milestone.

---

**Version**: 2.1 (Memocratic Record)

### Historical references

The original links below name earlier project references. Their availability has not been established. The text above links here, and the original export retains every URL.

#### Historical reference 1

`https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/main/docs/validator-interview-protocol.md`

#### Historical reference 2

`https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/main/notebooks/research/exports/01-introduction.ipynb`

#### Historical reference 3

`https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/main/notebooks/research/exports/02-cadcad-model.ipynb`

#### Historical reference 4

`https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/main/notebooks/research/exports/03-psuu-framework.ipynb`

#### Historical reference 5

`https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/main/notebooks/research/exports/04-data-foundations.ipynb`

#### Historical reference 6

`https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/main/docs/incident-log.md`
<!-- historical-original:end -->
