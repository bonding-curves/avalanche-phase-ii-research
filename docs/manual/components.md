# 4. The daily model, component by component

*Draft for review.*

[Manual contents](README.md)

The released `v0.8.0` variant is `StakeLifecycle`. It represents five choices: whether to renew, whether to return later, how many first-time nodes enter, how long to stake and how much to stake. Protocol arithmetic then prices the commitments these choices create. This chapter follows that sequence from preparation to the next state.

The [module reference](modules.md) lists every Python file and its defined components. Here, source links identify the implementation of each active process. Optional interfaces and older variants are distinguished from the released path.

## Prepare the origin before simulating it

[`variants.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/variants.py) selects a version and constructs its `Prepared` inputs. [`fitted_lifecycle.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/fitted_lifecycle.py) assembles training events, origin state, empirical choice tables and parameter draws. Preparation reads authenticated local data. It does not contact providers.

The origin state includes active periods, nodes eligible to return, previously accepted future starts and the protocol supply counter. The training data distinguish renewals within seven days, later returns and first-ever entries. Follow-up and cutoff rules prevent incomplete future observations from being treated as completed decisions. These definitions determine which event reaches each fit.

`Prepared` allows fitting work to be reused across scenarios. Its draw bank must be passed explicitly when constructing simulations. A model constructed at generic class defaults is not equivalent to the prepared release.

## Protocol arithmetic supplies the offered reward

[`domain/protocol`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/domain/protocol/__init__.py) contains integer reward calculations and separate protocol operations such as uptime settlement, delegation constraints and automatic renewal. Configuration types specify rates, timestamps and upgrade parameters. This kernel provides a checkable protocol reference.

[`mechanisms/reward.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/mechanisms/reward.py) exposes `RewardMechanism`. `ChainReward` follows the configured chain formula. `ACP285Ramp` changes the minimum consumption rate over a stated interval. `TenureBoost` and `QuadraticReward` alter the reward's shape or scale. Param settings expose their choices and bounds.

The lifecycle calls `potential_reward_navax` for newly started periods. This calculates a promise, not a realized payment after an uptime test. Other protocol functions do not become simulated behaviour merely because the package contains them. In particular, the released own-stake model does not simulate a separate delegation population, uptime process or admission-choice stage.

![Potential rewards depend on commitment duration and the reward formula.](assets/content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/assets/reward-duration.png)
*Figure 2. Annualized potential reward as a percentage of stake at a fixed 465 million AVAX supply counter. The curves compare the pre-Helicon formula with the completed ACP-285 ramp, before integer rounding. Payment still depends on eligibility.*

## Renewal decides which ending periods continue

[`parts/renewal.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/renewal.py) contains `RenewalLogit`, fitting and the renewal stage. Historical endings supply a binary outcome. Covariates include tenure, prior return, duration and stake bands. A penalized logistic fit limits unstable coefficients in sparse or separable groups. The released candidate excludes its optional own-node renewal-record feature.

For a node whose period ends, the simulation modifies its fitted renewal log-odds:

$$
\log\!\left(\frac{p}{1-p}\right)=\eta_{\mathrm{fit}}+\delta_{\mathrm{run}}+\beta_{\mathrm{renew}}\,\Delta y.
$$

Here $p$ is renewal probability, $\eta_{\mathrm{fit}}$ the fitted covariate predictor, $\delta_{\mathrm{run}}$ a run-level drift term and $\Delta y$ the yield gap in percentage points. The response coefficient is supplied, rather than estimated during this fit. A keyed uniform turns the probability into a decision.

The historical seven-day definition groups prompt continuation as renewal. The simulator makes the decision at expiry. It does not explicitly simulate each waiting day within that classification interval. This timing approximation should be considered when analyzing short-lived participation changes.

## Return gives departed nodes another opportunity

[`parts/return_hazard.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/return_hazard.py) implements `ReturnLogitHazard`. Its observations are eligible node-days outside the set. The fit uses time-out bins, stake bands and node-history indicators, with regularization across adjacent time bins and history terms.

[`parts/returns.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/returns.py) advances elapsed time and samples the return decision. The released hazard is zero through day seven and after day 365. A returning node re-enters through duration and stake choice. Nodes leaving the return window stop receiving opportunities in this process.

There is no direct reward-gap coefficient in this return equation. Reward changes can still affect population histories through other decisions. The older cellwise `ReturnHazard` class is retained as an alternative, rather than the runtime hazard selected by `v0.8.0`.

## Arrivals generate first-ever nodes

[`parts/arrivals.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/arrivals.py) fits a daily first-entry count. A negative-binomial distribution allows counts to vary more than a Poisson distribution with the same mean. The Poisson limit is available when excess variation disappears.

The scenario changes the fitted mean by a factor $\exp(\beta_{\mathrm{entry}}\Delta y)$. The implementation caps that mean at 100. It does not impose a hard limit of 100 on every realized count. One day-keyed uniform selects the count through the distribution's inverse cumulative probability.

New arrivals receive node identities and draw their duration and stake from first-entry laws. They are distinct from previously observed nodes returning after an absence. Entry counts measure NodeIDs, rather than newly founded operating businesses.

## Duration precedes stake choice

[`parts/continuation.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/continuation.py) draws the next duration for renewals and returns from empirical transitions. Four previous-duration groups are used: at most 20, 40 and 100 days, then longer periods. An empty group falls back to the pooled moves. First entries draw from the first-commitment table.

[`stake_lifecycle.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/stake_lifecycle.py) replaces the parent continuation stage so that duration is chosen before stake. The next-duration group can therefore condition stake choice. Neither choice directly optimizes against a changed yield gap in this release.

[`parts/duration_transition.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/duration_transition.py) also contains an optional fitted duration sampler. That sampler is not enabled in the released variant. Its five-band helper is used by the stake hurdle, which explains why the file appears in the dependency path without making its alternative sampler active.

## The stake hurdle separates staying from changing

[`parts/stake_choice.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/stake_choice.py) first decides whether to keep the reference stake. It then samples a changed log-stake ratio when a change is selected. Renewal and return use previous stake as the reference. Entry uses 2,000 AVAX.

Renewal and return cells combine ten previous-stake bands with five next-duration bands. Entry uses duration bands alone. Smoothed keep probabilities avoid treating an observed zero as an impossible event. Changed-ratio samples fall back from the joint cell to duration, then context when support is below 50 observations, with a prior fallback when empty. Final amounts are integers bounded between 2,000 and 3,000,000 AVAX.

This is an empirical conditional law with an explicit keep-or-change structure. Its `log_prob` evaluates smoothed probabilities across 103 categories, rather than a continuous probability density. The law is fixed across released parameter draws, so its estimation uncertainty is absent from the reported draw bank. Its accepted fitting domain also does not replace timestamp-specific protocol admission checks.

## Two reward calculations use different supply references

[`response.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/response.py) compares the annual rate on a standard 30-day commitment with the frozen fitting-window menu. The difference is centered for the change in outside yield. Renewal uses a typical renewal tenure and entry uses zero tenure. These calendar-day gaps use the origin supply counter.

The reward stage instead prices actual new commitments using the evolving day-start counter. It uses the simulated stake, duration and tenure. Thus, response and promise calculations intentionally have different supply references. A `ChainReward` scenario need not have a zero response gap when an upgrade or outside-yield change moves its future menu away from the fitted reference.

## Six stages produce one daily update

[`parts/stages.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/stages.py) orders the pipeline. Each stage reads day-start state and the named outputs of earlier stages. The final signal supplies one lifecycle cadCAD policy block. The engine adds an invariant-check block.

| Order | Stage | Produces |
| --- | --- | --- |
| 1 | Renewal | Ending periods, continuation decisions and periods that remain open |
| 2 | Returns | Eligible out-of-set nodes and sampled returns |
| 3 | Arrivals | First-ever entry count and new node identities |
| 4 | Continuation | Durations and stakes of renewed, returned and arriving nodes |
| 5 | Rewards | Full new reward promises, started stake, stake-days and offered rate |
| 6 | Assembly | Next active and out-of-set arrays, plus daily accounting signals |

Previously accepted starts join the active population on their scheduled dates. They are not priced again as newly accepted commitments. Assembly retains continuing periods, adds today's choices and then scheduled starts. Stake, duration, history and node keys move together so subsequent choices refer to the correct nodes.

[`engine.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/engine.py) configures cadCAD, applies updates and returns a long trajectory table. Invariants check stake bounds and totals, return ages, supply-cap conditions and consistency with the counter. These checks detect impossible numerical states. They do not establish that the behavioural equations describe the economy well.

## Fitting uncertainty and daily randomness serve different purposes

The parameter-draw machinery resamples nodes for renewal and return fits, uses 28-day blocks for arrival counts and supplies a run-level renewal shift. Empirical continuation and entry tables are resampled by node. A draw is constructed once per run, rather than fitted again to each simulated outcome.

[`streams.py`](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/streams.py) keys randomness by seed, run, purpose, node and decision or day. One branch therefore does not consume another node's random number. Matched experiments can share these keys and parameter draws even when their histories diverge. The experiment still has to verify matching inputs and settings.

A specification hash binds declared settings and input content. It does not bind every function body or dependency. A reproducible record therefore also needs the source commit, locked environment and output hashes.

## Trace a change through the whole system

Consider lowering the reward formula's minimum consumption rate. The offered duration menu changes. Renewal and entry gaps may fall relative to the fitted reference, reducing renewal probabilities and first-entry means under positive response settings. The resulting mix of continuing, returning and new nodes changes duration and stake draws. The reward stage prices their new commitments, and assembly carries the population forward. Repeating this process generates the path summarized by the KPIs.

Some effects are absent by construction: the return hazard has no direct yield response, stake and duration lack a direct price response, and no endogenous AVAX market or operating-business model intervenes. These omissions help define the next experiments and constrain interpretation of the current ones.

## Discuss design decisions with their consequences

| Decision | Consequence to examine | Suitable evaluation |
| --- | --- | --- |
| Daily transitions with noon pricing | Intraday ordering is approximated | Boundary and replay checks against timestamped records |
| Seven-day renewal and one-year return window | A classification allocates events to different fits | Sensitivity to event definitions and follow-up |
| Penalized logits and binned histories | Sparse estimates are stabilized at the cost of structure | Held-out event scores and calibration by group |
| Empirical duration and stake laws | Historical support constrains future choices | Distribution scores, tail checks and conditional diagnostics |
| Supplied reward responses | Counterfactual participation depends on external evidence | Identification review and broad response scenarios |
| Fixed stake-hurdle estimate | Intervals omit that component's fitting uncertainty | Resampling extension and interval comparison |
| Origin supply in response gaps | Behaviour does not fully track evolving reward headroom | An alternative-clock experiment |
| Own-stake population | Delegator income and operator ownership are incomplete | Add data and evaluate an explicit expanded variant |

These are implementation choices and evaluation proposals. A complete historical explanation of why each alternative was selected requires its decision record. Where that record is missing, the manual should not invent one.
