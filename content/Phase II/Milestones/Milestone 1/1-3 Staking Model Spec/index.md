---
title: "1.3 Staking Model Spec"
description: "The formal specification of staking model v0.7, a simplified model of the Primary Network staking subsystem that follows every validator commitment day by day, with behavioral state variables for renewal and entry."
status: delivered
source: signed-grant-agreement
tags: ["model-structure", "staking-duration-and-liquidity", "issuance-and-rewards"]
---

## Contract requirement

> Simplified model focused on staking subsystem with behavioral state variables

Milestone 1 success criterion:

> Preliminary Validation Report delivered and approved by Avalanche team

Quoted from the [Signed Grant Agreement](/Phase-II/Milestones/Milestone-0/Signed-Grant-Agreement).

## Status

Delivered for review. This page specifies staking model v0.7 as released under the tag `model-v0.7.0`, completely enough that a reader with this page and the staking record can rebuild it. It closes with the model's lineage and the changes in the v0.8 candidate, which is under test and not yet released.

## Result

The specification follows the ODD protocol (Overview, Design concepts, Details) of Grimm and others (2020), the standard for describing simulations that follow individual entities. It runs from the model's purpose through its state, structure, daily step, equations, checks, inputs, boundary, implementation and parameters, then says how it is verified, where v0.7 came from, and what v0.8 changes.

### Purpose and unit

Model v0.7 has two purposes. The first is to compare reward designs for the Primary Network by their effect on validators and on the AVAX the protocol issues. The second is to forecast validator stake and the validator count from a given date. It is judged against two patterns in the record. Its protocol layer must reproduce the P-Chain's daily ledger exactly, and its behavioral layer should forecast stake and count better than simple benchmarks.

The model's unit is the **validator commitment**: one staking transaction in which a **node**, a protocol identity, locks an amount of its own AVAX, the **self-stake**, from a start time to an end time chosen when the commitment is added. While one of its commitments is active, the node is a **validator**. The reward on a commitment is fixed when it starts and paid when it ends.

The state is held per commitment, rather than as network totals, for three reasons. First, each commitment has its own end date, so a change in reward reaches total stake only as commitments end, over weeks and months. Second, large and small validators behave differently. Commitments over 100,000 AVAX are 9.6% of commitments but 94.3% of the AVAX committed. Third, the reward on each new commitment depends on the supply already promised as reward, which the model must track as commitments start. A model of totals would hide all three. Following each commitment carries them and makes each assumption explicit and testable on its own.

The model is a **simplified** model of the staking subsystem in a stated sense. It follows validator commitments only. Delegations, operators, uptime failures and outside yields are left out, and the [boundary](#boundary) section lists each with the version that brings it in.

### Entities, state variables and scales

The model has one entity, the open validator commitment. Each open commitment $i$ carries three state variables. Its **stake** $s_i$ is the AVAX it locks, held in **nAVAX**, one billionth of an AVAX, the unit in which the P-Chain records stake and rewards. Its **days left** $d_i$ count down to its end. Its **tenure** $n_i$ is the number of commitments its node has completed, a measure of the node's track record.

The model's state on day $t$ is the set of open commitments plus five totals.

| State variable | Symbol | Unit | Set at the origin from |
| --- | --- | --- | --- |
| Open commitments, each with stake, days left and tenure | $\{(s_i, d_i, n_i)\}$ | nAVAX, days, count | The commitments open at the origin |
| Validator stake, the sum of $s_i$ over open commitments | $V_t$ | AVAX, held in nAVAX | Their total |
| Active validators, the number of open commitments | $K_t$ | count | Their number |
| P-Chain supply counter | $S_t$ | AVAX, held in nAVAX | The counter at the last stake start before the origin |
| Issuance on the day | $I_t$ | AVAX, held in nAVAX | Zero |
| Yield gap on the day, at the renewal tenure | $g_t$ | percentage points | Zero |

*Table 1. The state of model v0.7.*

The **supply counter** $S_t$ is the running total the P-Chain keeps of the genesis supply plus every reward promised, including the full potential reward of each open commitment from the moment it starts. Fees burned do not lower it, so it is not the realized supply. **Issuance** $I_t$ is the potential reward added to the counter on day $t$. The **yield gap** is defined in the laws of motion.

Time moves in steps of one UTC day. A run starts at an **origin**, 23:59:59 UTC on a chosen day, and covers 30 to 180 days. Each setting is run 20 times with different random draws.

### Behavioral state variables

The contract asks for a model with behavioral state variables. The proposal named three behavioral rates that should move with conditions rather than stay fixed: a stake rate, an unstake rate and a restake rate. In v0.7 these are carried by two behavioral rates, set each day by the reward design, and acting on the per-commitment state above.

| Proposal's rate | Model v0.7 | Symbol | Acts on |
| --- | --- | --- | --- |
| Stake rate | Entry rate: new commitments started a day | $\lambda_t$ | Adds commitments with tenure zero |
| Restake rate | Renewal probability: the chance an ending commitment renews on the same node | $p_t$ | Commitments whose days left reach zero |
| Unstake rate | One minus the renewal probability | $1 - p_t$ | The same commitments, which then leave |

*Table 2. The proposal's behavioral rates and the v0.7 variables that carry them.*

A **renewal** is a new commitment on the same node that starts within seven days after the previous one ends. A commitment that is not a renewal is an **entry**. Two **behavior blocks**, the model's units of decision, act on the per-commitment state. The renewal block decides whether each commitment whose days left reach zero renews, which resets its days left and adds one to its tenure. The entry block decides how many new commitments start, each with a stake, days left and tenure zero. Tenure enters behavior through the yield gap, priced at the **renewal tenure** $\tau$, so that a design that rewards tenure is priced for the validators it would reach.

Two differences from the proposal follow from the data. The proposal's restake rate was a response to the gain from compounding. In v0.7 a renewal keeps its stake, so compounded rewards are not represented. The proposal's unstake rate responded to external yields. In v0.7 both rates respond to the gap between a design's reward and the chain's own, so any outside option common to every design cancels out of a comparison. The model measures what a design changes relative to the chain's rule, not the absolute level of staking.

### What moves what

Two diagrams show the model's structure before the equations. The stock-and-flow diagram, in the notation of system dynamics, shows the quantities that accumulate and the flows that change them. The causal loop diagram shows the feedback between quantities.

![Stock and flow of model v0.7](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/stock-and-flow.png)

*Figure 1. Stock and flow of model v0.7. Stocks are boxes, flows are double pipes through a valve, clouds are sources and sinks outside the model, and thin blue arrows carry information. Active validator stake fills with entrants and scheduled starts and drains with endings that do not renew. A renewal leaves the stake unchanged but is priced like an entrant. The supply counter fills with issuance, the reward on every renewal and entrant. Source: model v0.7 at tag `model-v0.7.0`.*

![Causal loops of model v0.7](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/causal-loops.png)

*Figure 2. Causal loops of model v0.7. A plus sign means two quantities move in the same direction, a minus sign that they move in opposite directions. Loop B1 is balancing: issuance raises the counter, which lowers the reward on the next stake. Loop B2, dashed, would carry the counter's effect into behavior. It is open in v0.7, because the yield gap is priced at the origin's counter, not at the live counter. Source: model v0.7 at tag `model-v0.7.0`.*

Loop B1 is the protocol's own brake on issuance, and the model carries it exactly. Loop B2 is open. In v0.7 a design's effect on behavior is fixed by the design and the date, not by how much has been issued since the origin. Over 180 days the counter moves by about 1%, so the effect is small, but a later version should close the loop.

### The daily step

Each simulated day runs the same nine steps in a fixed order. Only steps 4 and 5 draw random numbers, from a stream that belongs to that day of that run.

1. Price the day's yield gaps, at the renewal tenure $\tau$ for renewal and at tenure zero for entry.
2. Set the day's renewal probability $p_t$ and entry rate $\lambda_t$ from the gaps and the responses.
3. Age every commitment one day. Those with no days left end today.
4. Each ending commitment renews with probability $p_t$, keeping its stake and drawing a new duration, or leaves.
5. A random number of new commitments enter, each drawing a stake and a duration.
6. Price every renewal and entrant at the previous day's counter. The sum of their potential rewards is the day's issuance.
7. Commitments accepted before the origin that start today join, adding stake but, in v0.7, no issuance.
8. Add issuance to the counter, then recount active validators and validator stake.
9. Check the four invariants.

![The daily step of model v0.7](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/daily-step.png)

*Figure 3. The nine steps of one simulated day. Shaded steps draw random numbers, and steps 1 and 6 use the protocol's exact reward formula. Source: model v0.7 at tag `model-v0.7.0`.*

### Laws of motion

This section gives the equations that each day's step applies. The first is the protocol's reward formula, which every other equation uses.

**Reward formula.** For a stake $s$ committed for $D$ days, starting when the supply counter stands at $S$, the protocol pays

$$
\text{reward}(s, D, S) = (C - S)\cdot\frac{s}{S}\cdot\frac{D}{P}\cdot r(D), \qquad r(D) = r_{\min} + (r_{\max} - r_{\min})\,\frac{D}{P} \tag{1}
$$

where $C$ is the supply cap of 720 million AVAX, $P$ the 365-day **minting period**, and $r(D)$ the **consumption rate**, which rises from $r_{\min}$ for the shortest commitment to $r_{\max}$ for a full year. Before Helicon $r_{\min}$ was 10% and $r_{\max}$ 12%. ACP-285 lowers $r_{\min}$ to 7.5% for stakes that start after its 90-day ramp. A **reward design** is a replacement for Equation 1, and a design may also read the node's tenure $n$. The model evaluates Equation 1 in integer nAVAX, with the same order of integer divisions as the node software.

Two features of Equation 1 shape the model. Every new stake adds to $S$, which lowers the reward on the next one, so issuance dampens itself. And the annual rate a validator earns is approximately $\frac{C-S}{S}\,r(D)$, which does not depend on how much AVAX is staked in total. A validator that leaves does not raise the rate of those that stay.

**Stake and supply counter.** Let $\mathcal{E}_t$ be the commitments that end on day $t$, $\mathcal{R}_t \subseteq \mathcal{E}_t$ those that renew, $\mathcal{N}_t$ the entrants, and $\mathcal{Q}_t$ the commitments accepted before the origin that start on day $t$, the **scheduled starts**. Validator stake and the supply counter move by

$$
V_{t} = V_{t-1} - \sum_{i \in \mathcal{E}_t \setminus \mathcal{R}_t} s_i + \sum_{j \in \mathcal{N}_t \cup \mathcal{Q}_t} s_j \tag{2}
$$

$$
S_{t} = S_{t-1} + I_t, \qquad I_t = \sum_{k \in \mathcal{R}_t \cup \mathcal{N}_t} \text{reward}(s_k, D_k, n_k, S_{t-1}) \tag{3}
$$

where the reward is Equation 1 under the design being run, in integer nAVAX, $D_k$ is the duration drawn for commitment $k$, and $n_k$ its node's tenure after the start, zero for an entrant. A renewal keeps its stake, so it does not appear in Equation 2, but it is priced again in Equation 3. The active validator count is $K_t = K_{t-1} - |\mathcal{E}_t \setminus \mathcal{R}_t| + |\mathcal{N}_t| + |\mathcal{Q}_t|$.

Scheduled starts appear in Equation 2 but not in Equation 3. That is a simplification. On the chain, a commitment accepted before the origin adds its potential reward to the counter on its start day. Before the Durango upgrade a stake could be accepted up to 11.7 days before it started, so at origins before Durango the model's counter runs slightly low for the first two weeks. From Durango on, stakes start when they are accepted and the case does not arise.

**Renewal.** Each ending commitment renews independently with the day's probability:

$$
\operatorname{logit} p_t = \operatorname{logit} p_0 + \beta_R\, g^R_t, \qquad \Pr(i \in \mathcal{R}_t) = p_t \text{ for each } i \in \mathcal{E}_t \tag{4}
$$

**Entry.** The number of entrants is a Poisson count:

$$
|\mathcal{N}_t| \sim \operatorname{Poisson}(\lambda_t), \qquad \lambda_t = \min\!\left(100,\; \lambda_0\, e^{\beta_E\, g^E_t}\right) \tag{5}
$$

where $\operatorname{logit} p = \ln\frac{p}{1-p}$, $p_0$ and $\lambda_0$ are the renewal probability and entry rate measured before the origin, and $\beta_R$ and $\beta_E$ are the **responses**: the change in the log-odds of renewal, and in the log of the entry rate, per percentage point of yield gap.

**Yield gaps.** The yield gaps are

$$
g^R_t = 100\,\big[\rho(t, \tau) - \rho_0(t, \tau)\big], \qquad g^E_t = 100\,\big[\rho(t, 0) - \rho_0(t, 0)\big] \tag{6}
$$

where $\rho(t, n)$ is the design's annual rate for a 30-day stake of a node with tenure $n$ started on day $t$, priced at the origin's counter $S_0$, and $\rho_0$ is the chain's own rule as it runs, which applies ACP-285 to stakes started since Helicon. The renewal gap is priced at the renewal tenure $\tau$ and the entry gap at no tenure, so a reward for tenure cannot attract entrants who would not receive it. Under the chain's own rule both gaps are zero, and the model's behavior reduces to the observed rates.

**Why these two forms.** The logit keeps the renewal probability between 0 and 1 for any gap, and with a response of zero it returns exactly the rate observed before the origin. The Poisson count is the simplest model of a daily number of arrivals, with one parameter, the rate. Both are the simplest forms that reproduce the observed rates. Neither form's response is validated by the record before Helicon, which held one reward curve and so cannot test it. The Poisson form is also too narrow. A Poisson count varies as much as its mean, but within each era from Banff to Fortuna the daily number of entries varied 3.7 to 13.5 times as much. That is one reason v0.7's forecast ranges are too narrow. v0.8 replaces the single renewal probability with a logit fitted on tenure, return after a gap, duration and stake, and the Poisson count of entries with a negative binomial count of first-ever nodes, whose variance can exceed its mean, plus a separate rate at which nodes that left return.

**The response is not identified.** The reward rule did not change between the network's launch and Helicon, and under the chain's own rule the yield gap is zero. The record before Helicon therefore cannot identify $\beta_R$ and $\beta_E$. The model sets them by assumption and sweeps them at 0, 0.1 and 0.3, and every comparison of designs is reported across that range.

**Draws.** A renewing commitment keeps its stake, adds one to its node's tenure, and draws a new duration uniformly from the **duration pool**, the durations of all commitments started in the year before the origin. An entrant draws its stake from the **entrant stake pool**, the stakes of that year's entries, and its duration from the same duration pool, independently, with tenure zero. A node returning after more than seven days away is an entrant too, so it also starts again at tenure zero, which undervalues returning nodes under a design that rewards tenure.

### Invariants

An **invariant** is a condition that must hold on every day of every run. Four are checked at the end of each day, and the first failure stops the run:

1. Every stake is non-negative.
2. Validator stake equals the sum of the open commitments.
3. The supply counter is within the 720 million AVAX cap.
4. Validator stake is within the supply counter.

### Initialization and inputs

Everything the model knows comes from the staking record up to the origin. Origins on or after 19 November 2025 at 16:00 UTC, when the Granite upgrade activated, are refused. The period from Granite to Helicon is held back from every fit and score, and is scored once on 27 October 2026 by a script fixed in advance. Table 3 gives each input with its value at one origin, the Fortuna upgrade.

| Input | Value at the Fortuna origin, 8 April 2025 | How it is measured |
| --- | --- | --- |
| Open commitments | 1,488 holding 188.16 million AVAX | Commitments started by the origin and ending after it |
| Renewal probability $p_0$ | 81.68% | Share of commitments ending in the 365 days up to seven days before the origin whose node started another within seven days |
| Entry rate $\lambda_0$ | 7.61 a day | Entries in the year before the origin, divided by 365. Entries include nodes returning after more than seven days away |
| Duration pool and entrant stake pool | 16,132 and 2,777 draws | Starts and entries in that year |
| Renewal tenure $\tau$ | 9 commitments | Median tenure of renewing validators, plus one |
| Supply counter $S_0$ | 456.93 million AVAX | Counter at the last stake start before the origin |
| Responses $\beta_R$, $\beta_E$ | 0, 0.1 and 0.3 | Assumed and swept |

*Table 3. The model's inputs.*

### Boundary

A model's boundary is the line between what it computes and what it takes as given or leaves out. Figure 4 sets out both for v0.7.

![What model v0.7 takes in, simulates, reports and leaves out](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/boundary.png)

*Figure 4. The boundary of model v0.7: the inputs taken in at the origin (left), what is simulated each day (centre), what each run reports (right), and what is left out (dashed box). Source: model v0.7 at tag `model-v0.7.0`.*

The research library that holds the model also implements the protocol's other staking rules, each citing the Avalanche Community Proposal (ACP) that introduced it and the lines of AvalancheGo, the node software, that enforce it. Among them are delegation fees, the uptime requirement raised to 90% by [ACP-267](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-267-Uptime-Requirement/), the 48-hour minimum commitment of [ACP-273](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-273-Minimum-Validator-Duration/), auto-renewed staking under [ACP-236](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-236-Auto-Renewed-Staking/), the delegation multiplier of [ACP-247](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-247-Delegation-Multiplier/), and the L1 validator and P-Chain fees. v0.7's simulation uses only the reward formula, the supply counter, and the ramp of [ACP-285](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-285-Minimum-Consumption-Rate/) inside the chain's own rule. It reads the mainnet reward constants, and the stake limits of 2,000 and 3,000,000 AVAX enter only through the stakes in the data.

### Implementation

The model is the class `ValidatorLifecycle` in the research library `avalanche_research`, in `src/avalanche_research/model/lifecycle.py`, released as tag `model-v0.7.0` at commit `087484b`. It runs on **cadCAD** 0.5.3, a Python framework for simulating systems whose state changes through a fixed order of policies and state updates. A day is one partial state update block: one policy computes the day's renewals, entrants and issuance, and update functions write the state. Every setting is declared with **Param** 2.4, a library that gives each setting a type, bounds and documentation, so a value outside its bounds fails before a run starts.

Every run writes one long table, a row per run, day and variable, with the settings, the model version and a **specification hash**. The hash covers the model class, every setting and a content hash of each input table, so two runs with the same hash used the same model, settings and input bytes. Day $t$ of run $r$ draws from a random stream seeded by the base seed, $r$ and $t$, so every design and response in a sweep starts from the same seeds. Their draws stay paired only until a decision differs between them. After that, the day's later draws shift, so differences between designs mix the design's effect with run noise.

![The cadCAD update block of model v0.7](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/canvas.png)

*Figure 5. The model's one update block per day, in the notation of the CADLabs Ethereum Economic Model. The policy reads the open commitments and the supply counter and decides the day's renewals, entrants and pricing. Its signals pass to four update functions, which write the state the next day reads. Each box gives a plain name and, beneath it, the name in the code. Source: model v0.7 at tag `model-v0.7.0`.*

### Parameters

Table 5 lists every setting of `ValidatorLifecycle` at tag `model-v0.7.0`, with the bounds Param enforces and where its value comes from.

| Setting | In the code | Default | Bounds | Source of the value used |
| --- | --- | --- | --- | --- |
| Renewal probability $p_0$ | `renewal_probability` | The renewal block's default | 0 to 1 | Measured at each origin |
| Entry rate $\lambda_0$ (starts a day) | `entry_rate_per_day` | 5.0 | 0 to 100 | Measured at each origin |
| Renewal response $\beta_R$ (log-odds per percentage point) | `renewal_response` | 0 | −2 to 2 | Assumed, swept at 0, 0.1 and 0.3 |
| Entry response $\beta_E$ (log of the rate per percentage point) | `entry_response` | 0 | −2 to 2 | Assumed, swept at 0, 0.1 and 0.3 |
| Renewal tenure $\tau$ (commitments) | `renewal_tenure` | 4 | 0 to 100 | Measured at each origin: median tenure of renewing validators, plus one |
| Supply counter at the origin $S_0$ (nAVAX) | `supply0_navax` | 450 million AVAX | 1 nAVAX to 720 million AVAX | Measured at each origin |
| Reward design | `mechanism` | The chain's rule | | Set by the experiment |
| Open commitments: stake, days left, tenure | `initial_stakes`, `initial_days_left`, `initial_periods_done` | | | Measured at each origin |
| Scheduled commitments: start day, stake, duration | `scheduled_start_day`, `scheduled_stakes`, `scheduled_days` | | | Measured at each origin |
| Duration pool and entrant stake pool | `draw_durations`, `draw_stakes` | | | The year before the origin |
| Days simulated | `timesteps` | 90 | 1 to 3,650 | Set by the experiment: 30 to 180 |
| Runs | `runs` | 20 | 1 or more | 20 |
| Base seed | `seed` | 0 | 0 or more | 0 |
| Days per step | `dt` | 1 | Only 1 | One UTC day |

*Table 5. The model's settings.*

### How the specification is verified

**Verification** asks whether the code does what this specification says, and comes before any experiment. The reward formula, run in integer nAVAX, reproduces the chain's recorded potential reward exactly on 3,769,919 of 3,769,920 stakes that started when they were accepted, before the held-back period. The **replay**, which feeds every recorded start, end and reward payment through the model's accounting with no behavior, equals the chain's daily ledger to the nAVAX on all 1,896 complete days from 10 September 2020 to 18 November 2025. Every simulated day checks the four invariants, the library's tests check the reward formula on 72 fixed combinations of stake, duration and start, and every run records its specification hash. Whether the behavioral layer is right is a separate question, **validation**, which scores the model's forecasts against what happened. The [Preliminary Validation Report](/Phase-II/Milestones/Milestone-1/Preliminary-Validation-Report/) gives the verification results in full and the validation of v0.7's forecasts.

### Lineage

Model v0.7 is the first released version built on a tested library. The first package, versions 0.4.3 to 0.6, modelled the network in aggregates and cohorts. It was retired at a restart in September 2026 in favor of a library whose protocol layer is tested against the chain.

| Version | Date | What it added |
| --- | --- | --- |
| v0.4.3 | Shown 3 July 2026 | The whole network as one aggregate, with behavior set by hand |
| v0.5 | Tagged 14 July 2026 | Stake cohorts by days to expiry, with 70% of each expiring cohort renewing |
| v0.6 | Shown 28 August 2026 | Cohorts by segment and stage, and delegation as a separate lifecycle |
| Prototype v0 | 28 and 30 September 2026 | The restart: each validator commitment followed day by day, with the exact reward formula |
| v0.7 | Tagged 1 October 2026 | Released. One observed renewal probability and entry rate per origin, with the response swept |
| v0.8 candidate | Scored 5 October 2026 | Renewal fitted by track record and stake, returns after a gap, fitted entry |

*Table 6. The model's versions.*

![Avalanche staking model versions, from the first package to version 1.0](/Phase-II/Milestones/Milestone-1/1-3-Staking-Model-Spec/lineage.png)

*Figure 6. The model's versions. Filled circles are built, the blue circle is v0.7, and open circles are planned, with the call at which each is shown. Source: the v0.7 research report of 8 October 2026, which the Foundation holds.*

### What v0.8 changes

The v0.8 candidate is under test and not released as a tagged version. The candidate reported here is at commit `1c891a4` of the research library. It keeps v0.7's unit, the validator commitment, its exact protocol layer, its engine and its replay, and replaces the two observed rates with four behavior blocks estimated from the decisions before each origin. The first three are fitted by likelihood, and the fourth draws from observed moves.

1. **Renewal.** A logit on the node's tenure, whether it returned after a gap, the committed duration and the stake.
2. **Arrivals.** A negative binomial count of nodes that have never validated.
3. **Returns.** A daily rate at which a node that left starts again, by its stake and days away.
4. **Continuation.** The next duration and stake of a node that renews or returns, drawn from nodes with a similar habit.

Table 7 sets out each change.

| Element | v0.7 | v0.8 candidate |
| --- | --- | --- |
| Unit | Each validator commitment | Each commitment with its node's history, plus each node that left the active set in the past 365 days |
| State per commitment | Stake, days left, tenure | Adds whether it began after a return, its own duration, and whether its node already has a next commitment scheduled |
| State outside the active set | None | A pool of nodes that left, each with its last stake, days out, tenure and last duration |
| Renewal | One observed probability | Fitted logit with 12 terms |
| Entry | Poisson count of all non-renewal starts, mean capped at 100 a day | Negative binomial count of first-ever nodes, mean not capped |
| Exit and return | A commitment that does not renew leaves for good. A return counts as entry | A node that does not renew enters the pool, can return by the fitted daily rate, and leaves the pool after 365 days |
| Duration | Drawn from all starts of the year before the origin | By previous duration for renewals and returns, from first-ever commitments for arrivals |
| Stake | A renewal keeps its stake. Entrants draw from the year's entries | Previous stake times a drawn ratio, kept within 2,000 and 3,000,000 AVAX |
| Commitment with a scheduled successor | Drew a renewal | Makes no renewal draw. The scheduled commitment takes over |
| Entry response $\beta_E$ | Scales all entry | Scales first-ever arrivals only. Returns do not respond to the yield gap |
| Invariants | Four, with stakes non-negative | Five: stakes within 2,000 and 3,000,000 AVAX, and no node out of the set more than 365 days, added to the other three |
| Protocol layer, engine, replay | | Unchanged |

*Table 7. Changes from v0.7 to the v0.8 candidate.*

Forecasts are scored by **scaled error**: a forecast's absolute error divided by the series' mean absolute one-day change before the origin. Lower is better. Table 8 compares the v0.8 candidate with v0.7 and three simple forecasts on validator stake.

| Validator stake, mean scaled error | 30 days | 90 days | 180 days |
| --- | --- | --- | --- |
| v0.8 candidate | 6.30 | 8.39 | 7.73 |
| v0.7 | 7.94 | 15.49 | 20.15 |
| Holding today's value | 6.80 | 7.58 | 9.80 |
| Extending the 180-day trend | 7.49 | 9.71 | 14.91 |
| Weekly time-series fit | 7.14 | 8.40 | 12.29 |

*Table 8. Validator stake mean scaled error, using 19, 18 and 17 eligible development origins at 30, 90 and 180 days, respectively. The v0.8 row uses 20 runs with base seed 0. The 200-run forecast uses ten 20-run batches with base seeds 0 to 9, and its mean scaled errors are 5.87, 8.47 and 7.91. Every batch is below all three simple forecasts at 30 and 180 days and above holding today's value at 90 days. At 90 days, 2 of the 10 batches are below the weekly fit's 8.40 and 8 are above it, with batch means from 8.11 to 8.92. Source: the v0.7 research report of 8 October 2026, which the Foundation holds, Table 8.*

On mean scaled error, the v0.8 candidate halves v0.7's error at 90 days and is lower than every simple forecast at 30 and 180 days. At 90 days it is near the weekly fit in the 20-run batch shown, its 200-run error is slightly higher than the weekly fit, and both remain behind holding today's value. These are descriptive comparisons, without a claim of statistical equivalence. The candidate does not improve the validator count. Checks of its predictions of renewal within seven days miss their tolerance of three percentage points, both month by month and for first and seventh commitments. Its response to reward is still assumed, as in v0.7, and returns do not respond at all. It becomes a release only by passing a test written before its results are seen.

### Glossary

The terms this specification introduces, in alphabetical order.

- **Behavior block.** One decision in the model, with its own form and inputs: renewal and entry in v0.7.
- **Duration pool, entrant stake pool.** The durations of all starts, and the stakes of all entries, in the year before the origin, from which the model draws.
- **Entry.** A commitment that is not a renewal, including a node returning after more than seven days away.
- **Invariant.** A condition checked at the end of every simulated day, whose failure stops the run.
- **Issuance.** The potential rewards added to the supply counter when commitments start.
- **Origin.** The moment, 23:59:59 UTC on a chosen day, from which a run starts. The model knows only the record up to it.
- **Renewal.** A new commitment on the same node that starts within seven days after the previous one ends.
- **Renewal tenure.** The tenure at which the renewal yield gap is priced: the median tenure of renewing validators, plus one.
- **Replay.** Feeding the recorded commitments through the model's accounting, with no behavior, to compare with the chain's daily ledger.
- **Response.** How strongly renewal and entry move with the yield gap, per percentage point.
- **Supply counter.** The P-Chain's running total of the genesis supply and every reward promised, read by the reward formula.
- **Tenure.** The number of commitments a node has completed.
- **Validator commitment.** One staking transaction in which a node locks its own AVAX from a start to an end time.
- **Yield gap.** A design's annual reward rate minus the chain's own, in percentage points, for a 30-day stake started that day.

The project's full glossary is in [Glossary and Notation](/Phase-II/Wiki/Reference/Glossary-and-Notation).

## How it was built

The model is tag `model-v0.7.0` of the research library, at commit `087484b`. The Foundation's repository holds the same model code and its tests on its `phase-ii` branch at commit `4597b8a`. The protocol rules follow the ACP texts at commit `b80ea34` of the ACPs repository and AvalancheGo at commit `70bd6d0`, and calculations use whole-number arithmetic in the same order as the node software. The inputs at every origin are measured from the staking periods run `staking-periods-2026-09-30`, and the replay compares with the daily ledger run `avax-monetary-daily-2026-09-30`. [Data](/Phase-II/Wiki/Reference/Data) explains the datasets and how each number traces to a checked run. The values in this page are those of the v0.7 research report of 8 October 2026, which the Foundation holds, and the diagrams are drawn from the model's code at the tag.

## Open questions

1. **The size of the response.** The record before Helicon cannot identify how renewal and entry respond to a change in reward. Helicon's scheduled ramp is the first change to the reward rule, and using it to estimate or bound the response needs a design written before the data are examined. Until then, every comparison of designs is reported across assumed responses.
2. **Stakes that started after acceptance.** Before Durango a stake could be accepted and start later. For those stakes the reward formula matches the recorded reward in only 19% to 25% of cases. The likely cause is the input: the chain priced these stakes at the counter on their start day, while the record holds the counter on their acceptance day.
3. **Scope of L1 mechanisms.** The L1 validator fee and the P-Chain dynamic fees are implemented in the protocol library but sit outside the staking subsystem. Should later versions carry them, or leave them as scenario inputs?
