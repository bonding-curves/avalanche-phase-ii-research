---
title: "Sensitivity Analysis Report"
description: "Milestone 2 of Avalanche Phase II tests reward designs on a model of every validator. At the first measured responses, ACP-285's ramp started early saves 12.8% of one year's issuance and keeps 98.7% of validator stake, and the Foundation's thresholds choose among minimum rates."
status: delivered
source: signed-grant-agreement
tags: ["parameter-selection-under-uncertainty", "sensitivity-analysis", "model-validation"]
---

## The reward rule sets issuance and validators' response sets its stake cost

Avalanche's reward rule decides how much AVAX the network issues, and validators' response to the reward decides how much stake that issuance holds. A response is the change in the log-odds that a validator renews within 7 days, or in the log rate at which new validators arrive, for each percentage point of the annual reward rate on a 30-day stake. The first measured responses, from the network's history, are about 0.025 for renewal and 0.04 for entry. ACP-285 is the Avalanche Community Proposal that lowers the minimum consumption rate of the reward formula from 10% to 7.5% over 90 days from the Helicon upgrade of 22 September 2026, and the chain's rule is the reward rule as the chain applies it, with ACP-285 from Helicon. In the central case, at the measured responses and an outside yield, the return validators could earn elsewhere, of 5% a year, starting ACP-285's ramp on 18 November 2025 instead of at Helicon saves 12.8% of one year's issuance against the chain's rule and keeps 98.7% of validators' own stake, as medians of 50 paired runs. ACP-285's minimum consumption rate of 7.5% pays a 48-hour stake about 4.1% of its stake a year. Across responses swept from 0 to 0.1, the best score under working weights falls at minimum consumption rates of 6% to 7%, which pay a 48-hour stake about 3.3% to 3.8% of its stake a year. Every threshold holds in 90% of runs only near 9% to 9.5%, about 4.9% to 5.2% of stake a year, with 7.5% between, so the Foundation's thresholds choose the setting. Against the rule before ACP-285, whose minimum rate stayed at 10%, ACP-285 issues 16.1% less over ten years of paired model scenarios and keeps 89.4% of validators' own stake.

| Deliverable | What it delivered |
| --- | --- |
| 2.1 PSUU Infrastructure | A sweep pipeline with a receipt per run |
| 2.2 Simulation Execution | Nearly 200,000 simulated years, against 50,000 agreed |
| 2.3 KPI Computation | Measures on every run, scored on five goals |
| 2.4 Validation Confirmation | Stake forecasts that beat six simple benchmarks |
| 2.5 Sensitivity Analysis | Each input's share of outcome variance |
| 2.6 Risk Surface Map | The settings and markets where goals fail |
| 2.7 Workshop #1 | The 13 November elicitation of thresholds and weights |
| 2.8 Collaborative Mechanism Design | A four-hook reward interface |

## Introduction

The Avalanche Foundation's grant proposal asks under what governance configurations Avalanche's staking incentives sustain validator and delegator participation across bull markets, bear markets and competing DeFi yields, while maintaining the security guarantees required by a multi-billion dollar network. A validator is a node whose owner locks AVAX as stake to take part in agreeing transactions, a delegator locks AVAX behind a validator without running one, and a governance configuration is a set of reward-rule parameters the community can change by vote.

A change tried on the live network answers that question slowly and at high cost. Its effect appears over months, as staking periods end and validators decide whether to renew. It reaches every validator at once, so no untreated group shows what would have happened without it, and undoing it needs another vote and another upgrade. A model tested against the network's full history lets the Foundation apply each change across many sampled futures first. Parameter Selection Under Uncertainty, or PSUU, sweeps the parameters the Foundation controls against the conditions it does not, and reports which values meet the network's goals across all of them.

Milestone 1 built the record of every staking period since September 2020 and the first model of validator behaviour fitted to it. Milestone 2 ran that model in one-year sweeps of 132,800 and 67,087 runs, nearly 200,000 simulated years, and in five-year and ten-year sweeps.

![Figure 1](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-01-f242.png)
*Figure 1. Over six years and eight named upgrades, Avalanche's supply grew by 30% while the share held as validators' own stake fell from its peak of 69% to 37%. The validators holding it fell by two thirds from their 2024 peak, and stake barely followed a 46-fold swing in the AVAX price. A reward rule must be judged both by how much stake it holds and by how many validators hold it.*


## Avalanche pays for its security by issuing AVAX from the room under its cap

Avalanche pays validators in newly issued AVAX, at a rate fixed when each staking period starts. A staking period is one commitment of an amount of AVAX for a length of time, from 14 days to one year before the Helicon upgrade of 22 September 2026 and from 48 hours to one year since. Let $C$ be the supply cap of 720 million AVAX, $S$ the P-Chain's supply counter when the stake starts, which is the genesis supply plus every reward already promised, $a$ the stake in AVAX, $d$ the period's length in days and $T$ one year of 365 days. A validator that meets its uptime requirement receives

$$
R(a, d, S) = (C - S)\,\frac{a}{S}\,\frac{d}{T}\,r(d), \qquad r(d) = r_{\min} + (r_{\max} - r_{\min})\,\frac{d}{T}.
$$

The parameters $r_{\min}$ and $r_{\max}$ are the minimum and maximum consumption rates, which set how fast rewards consume the room under the cap, $C - S$ (AvalancheGo, vms/platformvm/reward/calculator.go). Dividing the reward by the stake and the fraction of a year gives the annual yield

$$
\rho(d, S) = r(d)\,\phi(S), \qquad \phi(S) = \frac{C - S}{S},
$$

in percent of stake a year. The cap term $\phi$ was 1 at genesis, so the launch consumption rates of 10% and 12% were then the yields of the shortest and the one-year stake in percent of stake a year. The cap term was 0.544 at the supply of 466.4 million AVAX on 26 October 2026, when a one-year stake earned 6.52% of its stake a year.
The stake held by other validators appears nowhere in $\rho$.

Let $K$ be the total AVAX staked and $I$ the AVAX issued as rewards in a year. The cost of security is $I/K$, the AVAX issued for each AVAX of stake held, in percent a year. Each staked AVAX earns $\rho$ whatever $K$ is, so $I/K$ equals the stake-weighted average of $\rho$, which the rule and the durations validators choose set together. The cost of attack is a separate quantity, the value an attacker must lock to control a decisive share of the stake. A design that saves issuance lowers the cost of security, and the stake it keeps sets how far the cost of attack falls.

![Figure 2](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-02-f244.png)
*Figure 2. The AVAX that Avalanche issues as staking rewards is one quantity read two ways: against all AVAX staked, delegations included, it is the reward rate, 6.1% of stake a year in the year to 26 October 2026, and against total supply it is gross inflation, 2.8% of supply a year. Since 2021 inflation has halved while the reward rate fell by a quarter, because all AVAX staked, delegations included, fell from 68% to 46% of total supply.*

ACP-285, an Avalanche Community Proposal activated at Helicon, lowers $r_{\min}$ from 10% to 7.5% and leaves $r_{\max}$ at 12% (ACP-285, Reduce Minimum Consumption Rate). The cut in annual yield is $\Delta\rho(d) = 2.5 \times (1 - d/T)\,\phi(S)$ percentage points, largest for the shortest period and zero at one year. Each new stake reads $r_{\min}$ at its start time, and $r_{\min}$ falls linearly over 90 days from 10% at Helicon to 7.5% for stakes started on or after 21 December 2026 (Avalanche Builder Hub, Helicon Upgrade). A stake keeps its starting rate throughout. At the supply of 26 October 2026, a 48-hour stake's yield, in percent of stake a year, falls from 5.44% to 4.09% and a 14-day stake's from 5.48% to 4.17%, while a one-year stake keeps 6.52%. The premium for a one-year over a 14-day commitment therefore widens from 1.05 to 2.35 percentage points a year.

## The model computes rewards exactly and fits validators' choices to the record

Model v0.8.0 simulates Avalanche's validators as a population of staking periods, each one validator's commitment of its own AVAX for a chosen duration. The population advances one day at a time from the chain's state on 18 November 2025, when 819 validators held 160.3 million AVAX of their own stake and the P-Chain's supply counter stood at 465 million AVAX. In state-space form the model is $x_{t+1} = f(x_t, u_t, \omega_t, \lambda, \theta)$. Here $x_t$ is the state on day $t$, $u_t$ the reward rule and outside yield in force, $\omega_t$ the day's random draws, $\lambda$ the fitted behavioural parameters and $\theta = (\theta_R, \theta_E)$ the responses of renewal and entry to reward. A reward design changes $u_t$ and nothing else. Each day runs six stages in order: renewal, return, arrivals, duration and stake, reward and supply, and assembly of the next state. A second block checks five invariants and stops the run on any failure.

![Figure 3](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-03-f220.png)
*Figure 3. Model v0.8.0 holds validators as two stocks, open staking periods and nodes out of the set, moved by four flows fitted from the chain record. Supply is a counter that the reward rule raises by exact protocol arithmetic, and the response of renewal and arrivals to the offered reward rate is swept.*

![Figure 4](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-04-f229.png)
*Figure 4. Each simulated day runs six stages in a fixed order, four drawing chance and two exact, then updates the state and checks five invariants, such as every stake lying between 2,000 and 3,000,000 AVAX. Every random number is keyed by its purpose and the node, so a design and its twin under the chain's rule share every draw.*

The reward stage repeats the protocol's integer arithmetic in the protocol's order. Of the 3,769,920 stakes that started when the chain accepted them and before 19 November 2025, the model reproduces the reward of 3,769,919 to the last nAVAX, a billionth of an AVAX. Issuance in the model is therefore the protocol's issuance for the periods that start.

Validators' choices are five fitted distributions, each fitted only on decisions before the origin, the date a run starts. Each run refits renewal, return and arrivals on a fresh resample of the record, so the spread across runs carries the uncertainty of the fit as well as chance. The continuous ranked probability score, CRPS, scores a whole forecast distribution against the outcome, and lower is better.

| Decision | Process | Estimation | Window | Evaluation |
| --- | --- | --- | --- | --- |
| Renewal | Logit on tenure, duration and stake, with the response | Ridge-penalised maximum likelihood | 365 days | Log loss 0.4505 against 0.4916, better at 19 of 19 origins |
| Return | Discrete-time hazard in six day bins | Penalised maximum likelihood | 730 days | 90-day stake CRPS lower by 0.652 |
| Arrival | Negative binomial daily count, with the response | Maximum likelihood | 365 days | Poisson rejected in every era |
| Duration | Draw from past moves with the same previous duration | Empirical resampling | 365 days | Parametric alternative forecast worse |
| Stake | Hurdle that keeps the stake or rescales it | Empirical shares and quantiles | 365 days | 90-day stake CRPS lower by 0.172 |

Renewal shows how a block works. A period $i$ ending on day $t$ renews within seven days with probability $\sigma(x_i'\beta + \theta_R\, g_t + u_r)$, where $\sigma(z) = 1/(1 + e^{-z})$. The vector $x_i$ holds thirteen indicators of tenure, duration and stake, $\beta$ their fitted weights, and $u_r$ a shift held for the whole run. The reward gap $g_t$ is the design's annual rate on a 30-day stake less the chain rule's, in percentage points, adjusted for any change in the outside yield. At the origin the window held 14,977 endings by 2,968 nodes, and 78.6% of those endings renewed. The fitted probability for a small node is 0.50 after its first period and 0.81 after its second.

The responses are in log-odds of renewing, or log arrival rate, per percentage point of the annual rate on a 30-day stake. The sweeps varied both from 0 to 0.1, with a stress level of 0.3. On 28 October 2026, 51,707 renewal decisions by 7,216 nodes before 19 November 2025 gave a first measured renewal response of 0.025, with a 95% range of about 0 to 0.06. From 6,825 first commitments, entry measured 0.04, about 0 to 0.09. Both rest on AVAX price swings from \$3.65 to \$87.50 by quarterly mean, under the assumption that a dollar of reward from price weighs like a dollar from the rate. At 0.025, ACP-285's full ramp lowers renewal from 80% by about 0.5 percentage points. Milestone 1's pages said the record cannot measure the response to reward. The AVAX price and outside yields varied enough to give these first measurements, and those pages will be corrected.

Every design run has a twin under the chain's rule with the same seed, parameter draw and scenario. The chain's rule is the rule before ACP-285 until Helicon, day 308 of a run, and ACP-285's ramp after it. Keyed draws give the twins common random numbers, so $\mathrm{Var}(Y_d - Y_0) = \mathrm{Var}(Y_d) + \mathrm{Var}(Y_0) - 2\,\mathrm{Cov}(Y_d, Y_0)$ shrinks as the paired measures move together. Issuance saved is $1 - I_d/I_0$ and stake kept is $W_d/W_0$, for AVAX issued $I$ and validator stake $W$ at the horizon. All 1,024 runs at zero response kept exactly their twin's stake.

## 2.1 PSUU Infrastructure

Parameter Selection Under Uncertainty, PSUU, is BlockScience's method for choosing protocol parameters by running a model across settings and conditions and reporting which settings meet stated goals across the sampled futures (Paruch and Shorish, 2021). Each run combines governance levers, such as ACP-285's minimum consumption rate, scenarios, such as the outside yield, the fitted behavioural parameters drawn for the run, and a seed for the daily draws. Within each design and outside yield, the lever values come from a Sobol sequence, a quasi-random sequence that fills the range more evenly than independent draws. Saltelli's arrangement of those points lets the variance of each result be divided among its inputs.

![Figure 5](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-05-f219.png)
*Figure 5. Every table the model is fitted on comes from one pinned copy of the P-Chain record, and nothing dated on or after 19 November 2025 enters a fit or the choice of model. Each number in the analysis traces through the sweep to that pin.*

A design file fixes every row before any run starts. Each run writes its output with a SHA-256 hash, a digest that changes under any change to the file. A receipt names the code commit, the pinned input tables and every hash, and the analysis refuses any output whose hash differs from its receipt, so an altered input cannot enter a result. The model code and the run configuration are on the Foundation's repository, on branch `milestone-2`.

## 2.2 Simulation Execution

Every run starts from the chain's state on 18 November 2025. A minimum consumption rate of 7.5% pays a 48-hour stake about 4.1% of its stake a year, and a rate of 10% pays about 5.5% of its stake a year.

| Sweep | Trajectories | Horizon | What varies |
| --- | ---: | --- | --- |
| First one-year sweep, 14 October 2026 | 132,800 | 1 year | Four designs, outside yields of 3%, 5%, 7% and 10% a year, both responses 0 to 0.1 |
| Second one-year sweep | 67,087 | 1 year | Four parameters of the protocol's reward rule, bear, neutral and bull markets |
| Central case | 50 pairs | 1 year | ACP-285's ramp at measured responses, outside yield 5% a year |
| Five-year sweep | 8,192 | 5 years | Ramp floor 5% to 10%, outside yields of 3% and 5% a year, half of the runs twins |
| Ten-year sweep | 16,384 | 10 years | Ramp floor and quadratic duration curve |

The two one-year sweeps alone ran 199,887 trajectories, nearly 200,000 simulated years, against the 50,000 trajectories the agreement asks for. Beyond one year the runs are model scenarios read as paired shares, because v0.8.0 holds the 2024 to 2025 arrival pattern fixed while stake falls under every rule. Against the rule before it, ACP-285 issues 13.8% less over 5 years with 92.5% of validator stake kept, and 16.1% less over 10 years with 89.4% kept.

![Figure 6](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-06-L3.png)
*Figure 6. Issuance saved and validator stake kept by ACP-285's ramp against the chain's rule, in three bands of its floor, from 180 days to 5 years after 18 November 2025. The three bands stay close in the first year and spread apart after Helicon, so the trade between issuance saved and stake kept grows with the horizon. Responses are swept from 0 to 0.1.*

## 2.3 KPI Computation

Every simulated trajectory is reduced to fourteen measures at 180 and 365 days, none reading the held-back period from 19 November 2025. The paired measures compare the design run $d$ with its twin $0$ under the chain's rule. Issuance saved is $\rho_I = 1 - I_d/I_0$, where $I$ is the AVAX issued to validators' own stake over the horizon. Stake kept is $\rho_W = W_d/W_0$, where $W$ is validators' own locked AVAX at the horizon. The ratio $\rho_W/(1-\rho_I)$ equals the twin's cost of security $I_0/W_0$ divided by the design's.

The five goals trace to the grant proposal, ACP-285's aims and Eric Lu's choice of aims on 14 August 2026.

| Goal | Measures, against the twin | A run passes when |
| --- | --- | --- |
| G1 Security holds | Stake kept, worst 30-day stake fall | $\rho_W \ge 0.95$, and the fall is at most 2 percentage points of stake deeper |
| G2 Validators stay and stay spread | Validators kept, Nakamoto coefficient, return margin | At least 95% kept, at most one node fewer and 1 percentage point of stake a year of margin lost |
| G3 Holders pay less | Issuance saved, net inflation | $\rho_I > 0$, and net inflation at most 5% of supply a year |
| G4 Security per AVAX issued | $\rho_W/(1-\rho_I)$ | At least 1 |
| G5 Longer staking | Stake-weighted commitment length | At least 99% of the twin's |

The Nakamoto coefficient is the fewest validators holding over a third of validators' stake. The return margin is the reward rate earned less the outside yield and an operating cost of 1.5%, each in % of stake a year. Net inflation is a year's issuance less the fees burned, as a share of total supply.

Each measure $m$ scores a clipped-linear utility $u(m) = \min\{1, \max\{0, (m - m_0)/(m_1 - m_0)\}\}$. The utility is 0 at a floor $m_0$ the network should not accept and 1 at a target $m_1$ that meets the goal. Issuance saved scores 0.65 at 13% of the twin's issuance, against a target of 20% of it. Goal utilities are weighted means, with stake kept and issuance saved counted twice within G1 and G3. The combined utility weights G1 to G4 at 1 and G5 at 0.5 until the Foundation sets its own at Workshop 1.

A half-point cell of minimum rate with at least 30 runs meets the goals when 90% of its runs pass every goal at once across the swept responses and outside yields. This pass rule screens settings before the combined utility ranks them.

![Figure 7](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-07-f012.png)
*Figure 7. Every run is scored against one objective, to buy the most validator security for each AVAX issued. The objective splits into five goals and nine scored measures, each with a pass line and a score from 0 to 1. All measures except net inflation compare a run with its twin under the chain's rule, so a design is judged by what it changes.*

## 2.4 Validation Confirmation

Model v0.8.0 forecasts validator stake with lower loss than six simple benchmark forecasts at 30, 90 and 180 days, on 19, 18 and 17 past forecast dates from July 2022 to October 2025. At each date every behavioural part is refitted on the earlier record, and 200 runs are simulated forward. The benchmarks are the value on the forecast date, the recent drift, an autoregression of weekly changes, the first two spread by the series' own past changes, and a local-level time-series model.

Each forecast is a distribution, so it is scored by the continuous ranked probability score, CRPS, a score for whole forecast distributions. For cumulative distribution $F$ and realised stake $y$, $\mathrm{CRPS}(F,y) = \int (F(z) - \mathbf{1}\{z \ge y\})^2\,dz$, which rewards closeness and penalises needless width. Dividing it by the mean absolute one-day change before the forecast date puts it in typical daily moves, and lower is better.

| Validator stake, scaled CRPS in typical daily moves | 30 days | 90 days | 180 days |
| --- | --- | --- | --- |
| Model v0.8.0 | 4.41 | 5.15 | 5.54 |
| Value on the forecast date, spread by its past changes | 5.38 | 5.69 | 7.54 |
| Local-level model | 5.48 | 6.86 | 9.34 |


At 180 days the model's score is 27% lower than the best benchmark's, with a one-sided p-value of 0.04 on 17 dates in a Diebold-Mariano test, which allows for overlapping windows. For the count of active validators the model ranks third at 30 days and second at 90 and 180 days.

A rule written on 6 October 2026, before any score existed, admitted a change to the model only if it forecast its own decisions better on held-out events and left no forecast significantly worse. Three of eight candidate changes passed.

The held-back test scores the model once on a period never used to fit or choose it, from the Granite upgrade on 19 November 2025 to Helicon on 22 September 2026. It compares 90-day forecasts of validators' own stake from eight dates with three point benchmarks by mean absolute scaled error. The rule was frozen on 27 October 2026, and the score will be presented at Workshop 1.

Forecast skill is the criterion because the Foundation asked for a standard to choose a model by. Eric Lu said on 31 July 2026, "I never expect the model can fit the … time series." The agreement names goodness of fit above 90% correlation for this deliverable, but validator stake is integrated of order one, its level the running sum of its changes. A simulated pair of independent random walks correlates at 0.85 on its levels and 0.01 on its daily changes, so the held-back output reports correlation as a supplementary statistic.

![Figure 8](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-08-f221.png)
*Figure 8. Model v0.8.0 forecasts validator stake better than six standard benchmark forecasts at 30, 90 and 180 days, and the validator count third best at 30 days and second best at 90 and 180 days. Each score is the mean continuous ranked probability score over 19, 18 and 17 forecast dates before 19 November 2025, in units of the mean one-day change before each date.*

## 2.5 Sensitivity Analysis

A reward design's own setting decides the issuance it saves, and validators' response to reward decides the stake that saving costs. The analysis attributes each outcome's variation in the first sweep, 132,800 one-year runs, to four inputs. The inputs are the design's setting, such as the target minimum consumption rate of ACP-285's ramp, the outside yield, and the renewal and entry responses. Each response was swept from 0 to 0.1, in log-odds of renewing within 7 days or log arrival rate, per percentage point of the annual reward rate on a 30-day stake. Every outcome is a paired share of the run's twin under the chain's rule on the same seed and parameter draw.

| Method run | Question | Result for the ramp at one year |
| --- | --- | --- |
| Spearman rank correlation, 1,000 bootstrap resamples of whole Saltelli units | Direction of each effect | −0.98 between minimum rate and issuance saved at every outside yield |
| Sobol indices, Saltelli first-order and Jansen total estimators, $N = 512$ base points | Variance share of each input | About 96% of the variance of issuance saved from the minimum rate, where converged |
| One-way random-effects share, 64 points run 8 times each | Variance share of chance | About half of the variance of stake kept |
| Classification tree, cost-complexity pruning, nested cross-validation | When every goal holds | Figure 9 |
| Random forest, 300 trees, permutation importance | Ranking of inputs | Minimum rate first, renewal response second |
| Binned means, checked against partial dependence | Each goal along the minimum rate | Figure 11 |

The first-order Sobol index $S_i = \mathrm{Var}(E[Y \mid X_i]) / \mathrm{Var}(Y)$ is the share of the variance of outcome $Y$ that input $X_i$ explains alone. A group of indices, one per design, outside yield, horizon and measure, converges when no index in it moves by more than 0.02 as $N$ doubles from 256 to 512. Of 512 groups, 310 converged, 190 did not and 12 are undefined. Stake kept splits about a third to the minimum rate, a sixth to the renewal response and a half to chance with the uncertainty of the fitted parameters.

![Figure 9](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-09-f222.png)
*Figure 9. Every goal holds in 89% of runs with a minimum consumption rate above 8.20% and at most 9.84% a year, and in at most 10% of runs at or below 6.48% a year. Between 6.48% and 7.29% a year the renewal response decides, and the measured response of about 0.025 falls on the weak side of the split at 0.041. The tree sorts 85% of held-out runs correctly, against 56% for always guessing the larger outcome.*

The utility map places each outside-yield panel's best cell at minimum rates of 5% to 7% a year and renewal responses of 0 to 0.02, with mean combined utility of 0.80 to 0.82. Those cells sit below the renewal response of about 0.025 measured on 28 October 2026, which falls in the row from 0.02 to 0.04, where utility at 5% to 7.5% a year is 0.75 to 0.81.

![Figure 10](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-10-f223.png)
*Figure 10. Combined utility of the five goals is highest at minimum consumption rates of 5% to 7% a year and falls toward 10% a year at every outside yield. The outside yield moves the best cell less than the rate does.*

A higher minimum rate raises the security and participation goals G1 and G2 and lowers G3 to G5, so combined utility, averaged over every response and outside yield, peaks at 0.77 at 6% to 6.5% a year. The second sweep ranks the protocol rule's maximum rate as the next strongest lever, a direction that model v0.8.1 reruns.

![Figure 11](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-11-f224.png)
*Figure 11. A higher minimum consumption rate raises goals G1 and G2 and lowers goals G3 to G5. Combined utility peaks at 0.77 at 6% to 6.5% a year, about 3.3% to 3.6% of stake a year for a 48-hour stake.*

## 2.6 Risk Surface Map

Over the swept responses, the thresholds and the weighted score favour different minimum rates, with ACP-285's 7.5% a year between them, which pays a 48-hour stake about 4.1% of its stake a year. Let $A$ be the event that a run meets every threshold, and $c$ a half-point cell of minimum rate. The best weighted score lies at 6% to 7% a year, about 3.3% to 3.8% of stake a year for a 48-hour stake, and peaks at 0.77. The global range $\mathcal{R} = \{c : P(A \mid c) \ge 0.9\}$ holds only 9% to 9.5% a year, about 4.9% to 5.2% of stake a year, where 93% of runs pass. ACP-285's rate scores within about 0.04 of the best utility and meets every threshold in 40% to 53% of runs. These tiers are results over responses of 0 to 0.1 and set no new recommended rate.

![Figure 12](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-12-f225.png)
*Figure 12. Each percentage point lower in the ramp's minimum consumption rate saves about 5.5 percentage points more of one year's issuance and gives up about 1.3 points of validator stake. At the measured responses, the ramp started early at 7.5% a year saves 12.8% of issuance and keeps 98.7% of stake.*

At the first measured responses, renewal about 0.025 and entry about 0.04, the ramp started early at 7.5% a year saves 12.8% of one year's issuance against the chain's rule. The ramp keeps 98.7% of validator stake, over 50 paired runs at a 5% outside yield. The sweep's runs at 7.25% to 7.75% a year save 13.3% of issuance and keep 97.2% of stake, averaged over responses of 0 to 0.1. At the measured responses, a ramp to 6% a year saves 20.6% of issuance and keeps 97.0% of stake.

![Figure 13](/Phase-II/Milestones/Milestone-2/Sensitivity-Analysis-Report/figure-13-f046.png)
*Figure 13. The rate with the highest combined utility, 6% to 6.5% a year, lies below the 9% to 9.5% a year at which every goal holds in 90% of runs. ACP-285's 7.5% a year falls between them.*

The outside yield decides where validators' return margin fails. The margin is $M = \bar r - y - c$, with earned rate $\bar r$, outside yield $y$ and operating cost $c = 1.5\%$, each in percent of stake a year. The margin is negative in every run at outside yields of 7% and 10% a year, and in at least 91% of runs at 5% a year. Validators in model v0.8.0 respond to the gap between the design's reward and the chain rule's, adjusted for changes in the outside yield, so a negative margin under every design moves the ranking of designs little and marks the market conditions in which a revenue-funded reward is worth testing. The patient rule induction method found 189 of its 197 confirmed failure boxes spanning every input.

Market conditions leave the ranking unchanged in model v0.8.0, which has no AVAX price, because each market shifts a design and its twin alike.

## 2.7 Workshop #1

Workshop 1 on Friday 13 November 2026 replaces the working goals, thresholds and weights used throughout Milestone 2 with the Foundation's own. The Foundation sets thresholds first, because a threshold is the minimum acceptable outcome on one goal and decides which reward settings are acceptable at all. Weights follow, stating how much of one goal the Foundation would give up for another, and they rank only the settings that pass. The order matters because, over the swept range of responses, the setting that meets every threshold in 90% of runs has a higher minimum consumption rate than the setting with the best weighted score. A worksheet records the decisions in one row for each goal of section 2.3, with its measure, threshold, weight, the Foundation's reason and who agreed, and the rows are read back before the call ends. The call of Friday 30 October 2026 walks through the whole model first, so that the 13 November hour is spent on decisions.

## 2.8 Collaborative Mechanism Design

Any reward rule the Foundation proposes enters the model as one class, a code template, without changing the rest of a simulated day. The class changes the chain's reward formula through one or more of four hooks, each a method that replaces one factor. The config hook sets the minimum and maximum consumption rates in force on each date, and ACP-285's ramp uses it. The numerator hook sets how the rate rises with duration, for the quadratic curve. The multiplier hook scales a reward by the node's completed staking periods, for the tenure boost. The funding hook splits a reward into minted AVAX, AVAX paid from a revenue pool and an unpaid remainder.

The chain's rule, the ramp, the quadratic curve and the tenure boost are released on the Foundation repository's `milestone-2` branch. The funding hook, the revenue-funded rule and the protocol's governance rule are prototypes. Each rule must equal the chain's rule to the nAVAX, a billionth of an AVAX, at its neutral setting before any sweep. Revenue-funded rewards, proposed by Eric Lu on 28 August 2026, are the first timed evaluation, from Monday 2 to Friday 6 November 2026 within the agreement's five business days. No revenue source is fixed yet, so the evaluation sweeps the pool's share of rewards and reports correlation tables with confidence ratings and tiers.


## Milestone 3 scores reward settings against the Foundation's thresholds by 15 January 2027

The held-back test is scored for Workshop 1. It forecasts validators' stake 90 days ahead from eight dates between the Granite upgrade on 19 November 2025 and Helicon on 22 September 2026, a period no fit has seen. Model v0.8.1 adds delegations, a limit that keeps total stake within the AVAX holders have left unstaked, and a feedback that slows new stake as unstaked supply empties. The governance-rule results, upper bounds until then, are rerun on v0.8.1. Model v0.9 adds the AVAX price and distinct holder types, so that market conditions reach the results through the dollar value of rewards. A validator's chosen duration does not yet respond to reward, so the goal of longer commitments is fully tested only when v0.10 adds that response. The five- and ten-year comparisons are rerun on these versions, because v0.8.0 holds the 2024 to 2025 arrival pattern fixed. Milestone 3 runs from 1 to 11 December 2026 and from 4 to 15 January 2027. The code reaches the Foundation on 11 December, Workshop 2 is on Friday 8 January 2027, and the final report follows around 15 January 2027.


## Annex A. Notation

| Symbol | Meaning | Units |
| --- | --- | --- |
| $C$ | Supply cap, 720,000,000 AVAX | AVAX |
| $S$, $S_0$ | Supply counter, the P-Chain's running total of supply that prices each new staking period, and its value on the origin day | AVAX |
| $a$, $d$ | Stake and duration of one staking period, with $d$ from 48 hours to one year | AVAX, days |
| $T$ | Minting period | 365 days |
| $r_{\min}$, $r_{\max}$ | Minimum and maximum consumption rates, parameters of the reward formula | Share of $C - S$ a year |
| $g_t$ | Reward gap, defined in Annex B | Percentage points of the annual rate on a 30-day stake |
| $\theta_R$, $\theta_E$ | Renewal and entry responses to reward | Log-odds, or log arrival rate, per percentage point of $g_t$, swept from 0 to 0.1 |
| $y_t$, $y_0$ | Outside yield on day $t$ and over the fitting window | % of stake a year |
| $I_d$, $I_0$, $W_d$, $W_0$ | Issuance over the horizon, and validators' own stake at the horizon, in a design run and in its twin under the chain's rule | AVAX |
| $u_g$, $w_g$, $U$ | Utility of goal $g$, its weight, and the combined utility $\sum_g w_g u_g$ | 0 to 1 |

The reward $R$ fixed when a period starts, the cost of security, issuance saved $\rho_I$ and stake kept $\rho_W$ are

$$
R = \min\Big\{C - S,\ (C - S)\,\frac{a}{S}\,\frac{d}{T}\,r(d)\Big\}, \qquad r(d) = r_{\min} + (r_{\max} - r_{\min})\,\frac{d}{T}, \qquad \frac{I}{K}, \qquad \rho_I = 1 - \frac{I_d}{I_0}, \qquad \rho_W = \frac{W_d}{W_0},
$$

where $I$ is the AVAX issued in a year and $K$ the total stake held.

## Annex B. Behaviour model

The model is the stochastic system $x_{t+1} = f(x_t, u_t, \omega_t;\ \lambda, \theta)$, in which six ordered daily stages $f$ update the state $x_t$. The input $u_t$ is the reward rule and outside yield in force, and $\omega_t$ are keyed random draws. Each run draws $\lambda$, a bootstrap refit of the blocks below, and $\theta = (\theta_R, \theta_E)$. A reward design changes only $u_t$.

Renewal is a logit for each staking period $i$ that ends on day $t$:

$$
P(\text{renew}_i = 1 \mid x_i) = \sigma(x_i'\beta + \theta_R\, g_t + u_r), \qquad \sigma(z) = \frac{1}{1 + e^{-z}}.
$$

Here $x_i$ holds thirteen indicators of tenure, duration and stake, and $u_r \sim N(0, \sigma_u^2)$ shifts each run for drift between quarters. Ridge-penalised maximum likelihood with a $N(0, 1)$ prior fits $\beta$ on the 14,977 endings by 2,968 nodes in the 365 days before 18 November 2025. The second-period coefficient is 1.457, with 95% intervals of 1.268 to 1.646 by the Laplace approximation and 1.277 to 1.652 by 300 node-clustered bootstrap refits.


Return is a daily hazard $h(\ell) = \sigma(z'\gamma)$ on day $\ell$ after an ending without renewal, for $7 < \ell \le 365$, where $z$ holds day-bin, stake and history indicators. Penalised binomial maximum likelihood fits $\gamma$ over node-days at risk in the 730 days before the origin, with a $N(0, 0.5^2)$ random-walk prior across six day bins.

First-ever arrivals on day $t$ are a negative binomial count:

$$
N_t \sim \mathrm{NegBin}(m_t, k), \qquad m_t = \min(100,\ \mu\, e^{\theta_E g_t}), \qquad \mathrm{Var}(N_t) = m_t + \frac{m_t^2}{k}.
$$

Maximum likelihood on the 365 daily counts before the origin gives the baseline mean $\hat\mu = 3.89$ nodes a day and the dispersion $\hat k = 0.49$.


Duration is drawn from the year's observed moves with a previous duration in the same bin, split at 20, 40 and 100 days. Stake is a hurdle. With probability $p_b = (n_b - m_b + 1)/(n_b + 2)$, where cell $b$ held $n_b$ decisions and $m_b$ changes, the stake stays at its previous value $a_0$. Otherwise $a_1 = \min\{3{,}000{,}000,\ \max\{2{,}000,\ \lfloor a_0 e^{q} \rfloor\}\}$, with $q$ drawn from the cell's observed log changes.

A design reaches behaviour only through the reward gap

$$
g_t = 100\,\big(r_D(30, S_0;\ t) - r_M(30, S_0;\ t)\big) - (y_t - y_0),
$$

where $r_D$ and $r_M$ are the annual rates on a 30-day stake under the design and under the rule in force over the fitting window. On 28 October 2026 the AVAX price swings before 19 November 2025 gave first measurements of 0.025 for renewal and 0.04 for entry. The measurements assume that a dollar of reward from price weighs like a dollar from the rate.

## Annex C. Validation

Skill at a horizon of $h$ days is $\mathrm{SS}_h = 1 - \bar L_{\text{model}, h} / \bar L_{\text{ref}, h}$, the share of the reference's mean loss removed. The loss is the continuous ranked probability score, CRPS, which for an ensemble of $m$ runs $v_i$ and outcome $y$ is

$$
\mathrm{CRPS} = \frac{1}{m}\sum_{i=1}^{m} |v_i - y| - \frac{1}{2m^2}\sum_{i=1}^{m}\sum_{j=1}^{m} |v_i - v_j|,
$$

divided by $\bar\delta_T$, the mean absolute one-day change in validator stake before origin $T$. The six references are persistence, drift and a weekly autoregression, two of them also dressed with past changes, and a local-level model. Nineteen, eighteen and seventeen origins from July 2022 to October 2025 are scored at 30, 90 and 180 days. A Diebold-Mariano test with the Harvey, Leybourne and Newbold correction counts overlapping windows through a lag truncation $q$.

The rule dated 6 October 2026 adopts a candidate component only if its held-out log loss falls, with a paired-bootstrap $p < 0.05$, at 14 or more of 19 origins. Its calibration error must be at most 0.02, and its system forecasts must satisfy

$$
\Delta < 2.2 \quad \text{and} \quad \min_c p^{\text{worse}}_c \ge 0.05/6,
$$

where $\Delta$ is the change in mean scaled CRPS for stake at 90 days and $p^{\text{worse}}_c$ tests for worse loss in each of six cells.

The held-back test, frozen on 27 October 2026, covers 19 November 2025 to 22 September 2026. It forecasts validators' own stake 90 days ahead from eight origins. The score compares the forecast $\hat y_{T+h}$ with realised stake $y$ by the mean absolute scaled error, MASE, $|\hat y_{T+h} - y_{T+h}| \big/ \tfrac{1}{T-1}\sum_{t=2}^{T}|y_t - y_{t-1}|$, against persistence, drift and the autoregression. The verdict is PASS when the model's mean MASE beats every reference with a test significant at 5% and $q = 4$. A reference that scores as well or better gives FAIL, and any other case gives INCONCLUSIVE.

## Annex D. Sensitivity estimators

Sobol indices come from two Sobol matrices $A$ and $B$ of $N = 512$ rows and the hybrids $A_B^{(i)}$, which take column $i$ from $B$. With $f(\cdot)_j$ the outcome of row $j$, and $\bar f$ and $\hat V$ the mean and variance of the $2N$ outcomes of $A$ and $B$,

$$
\hat S_i = \frac{1}{N\hat V}\sum_{j=1}^{N}\big(f(B)_j - \bar f\big)\big(f(A_B^{(i)})_j - f(A)_j\big), \qquad \hat S_{T_i} = \frac{1}{2N\hat V}\sum_{j=1}^{N}\big(f(A)_j - f(A_B^{(i)})_j\big)^2,
$$

the centred Saltelli first-order form and the Jansen total form, both run in the team's own code. No second-order index was estimated. An outcome's indices converge when none moves by more than 0.02 from $N = 256$ to $N = 512$. Of 2,024 index entries, 1,267 converged, 733 failed and 24 were undefined. The 512 canonical measure groups, which merge seven return-margin aliases, split into 310 converged, 190 failed and 12 undefined.


The noise share $\eta = \hat\sigma^2_w / (\hat\sigma^2_w + \max(\hat\sigma^2_b, 0))$ uses the within-point and between-point variances $\hat\sigma^2_w$ and $\hat\sigma^2_b$ of 64 design points per design and outside yield, each run eight times. Forests of 300 trees rank inputs by permutation importance. The patient rule induction method, PRIM, peels 5% of a box's runs per step.

## Annex E. Reproduction

The code is on the Foundation repository's `milestone-2` branch, with model v0.8.0 tagged at commit b18a4a2:

```sh
git clone --branch milestone-2 git@github.com:AVL-Foundation/ext-bcrg-validator-research.git
cd ext-bcrg-validator-research
uv sync --locked --group model --group notebook
uv run pytest -q
uv run avalanche model describe
```

Every run writes a receipt that binds its outputs to the code commit, its settings and the SHA-256 cryptographic digests of its pinned inputs. Repeating a simulation needs the pinned input snapshots, which are not yet distributed with the repository.
