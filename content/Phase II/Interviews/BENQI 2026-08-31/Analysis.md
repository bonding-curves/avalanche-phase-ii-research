---
title: "BENQI interview evidence analysis"
description: "Hansen's statements, checked delegation evidence, and the limits of the resulting staking hypotheses."
date: 2026-10-01
---

# BENQI interview evidence analysis

Hansen describes two different decisions: managing a liquid staking service's redemption needs and choosing how to stake his personal AVAX. Those decisions should remain separate in the model. The observed funding address is sufficiently concentrated to warrant its own analysis stratum, conditional on the inferred BENQI attribution. This interview supports candidate decision rules. It does not estimate population preferences, response coefficients, or future adoption.

Read the [interview summary](/Phase-II/Interviews/BENQI-2026-08-31/) and the [interview method](/Phase-II/Interviews/Interview-Method) for context. This analysis was published on October 1, 2026. The full transcript is withheld pending Hansen's consent.

## Source and interpretation boundary

The machine transcript covers 603 segments and approximately 65 minutes from August 31, 2026 at 19:00:42 America/New_York. The preserved segment-level export records zero seconds of audio review. Hansen and Hash are likely speaker assignments, while Shawn's microphone track is named. Exact quotations below retain machine wording and spelling. Timestamps are elapsed recording time, truncated to whole seconds from each source segment's start.

The transcript uses variants such as “Banky,” “SFOX,” and “Essovox.” BENQI and sAVAX in the analysis are contextual interpretations, not silent transcript corrections. Several segments appear to merge a question into an answer. Audio review is needed before treating those passages as verified quotations. The existing minutes, narrative, and meeting summary are derived interpretations, not independent corroboration.

## Claims by topic

Claims are grouped by the topics in the [interview method](/Phase-II/Interviews/Interview-Method). A checked address fact can corroborate an action, but cannot establish its motivation.

### Business and personal objectives are different

> “For the Essovox business side, we just take a skim off the total amount of stake that comes through.” [14:31]
>
> “So we prioritize increasing Essovox TVL as much as we can, and minimizing costs.” [14:37]

**Claim.** The service seeks assets under management and low costs. Hansen separates this from the personal economic decision in 14:27 and 15:14.

**Checkability and result.** P-Chain holdings and flows are observable after address attribution. Corporate objectives and fee income require product terms and business records. No objective or income check was performed.

**Model implication.** Separate the operator's service objective from the owner's personal staking policy. Do not infer either objective solely from address activity.

### Product scale and delegation dominance

> “I'm happy to dig through the questions if you want, but I think it's probably useful to discuss how we do it for SOVAX first, since it's about 10% or 12% of stake.” [06:52]
>
> “Yes, but that's because we chose to do delegations, right?” [42:19]

**Claim.** The product is large and deliberately delegates. The second quote answers Hash's question about “93% of all the delegations” in 41:56 to 42:11. That is a count, not an AVAX share.

**Checkability and result.** The delegation-count check reproduces 93.33% of observed delegation events across the full dataset. At August 31 day-end, the stake-snapshot check finds 18.266M AVAX, 48.806% of delegated stake and 8.604% of total active stake, from this funding address's delegations alone. The latter omits validator self-stake, so it neither confirms nor disproves the stated 10% to 12% product total.

**Model implication.** Analyze this funding address separately, and distinguish event counts from capital weights. A count share cannot set its share of model capital or its share of independent economic actors.

### Short delegations and longer validators manage liquidity

> “So we primarily—well, in the current state, before the Helicon upgrade, we have been just doing 14 to 18-day stakes delegations because we prioritize liquidity for users.” [07:15]
>
> “So yeah, we prioritize liquidity, and we try to have a mix of long-term validators just so we can raise the yield a little bit.” [08:10]

**Claim.** Short delegations provide liquidity alongside longer validator commitments.

**Checkability and result.** The duration check finds funding-address delegation durations from 14 days to 17.0032986 days. This corroborates short durations, with a more precise upper bound than the account given. No date-matched validator-duration mix was measured in this check. Chain durations alone do not prove the liquidity motive.

**Model implication.** Separate validator and delegation duration distributions, and add a redemption constraint as a hypothesis requiring product-flow data. Use observed durations as moments, not the rounded interview interval as a hard rule.

### Two days is an intention with an implementation delay

> “We are probably leaning towards just reducing all state towards two days, just because the delta between two-day APR and 14-day APR is in like 20 bits or five bits.” [08:32]
>
> “If it plays out, it'll probably take months for us to implement” [09:20]

**Claim.** A possible response, not a completed operational change. Hansen says he cannot remember the rate difference (08:49). “Nothing undecided” in 09:18 is ambiguous machine wording and cannot establish a firm decision.

**Checkability and result.** The delegation dataset's latest acceptance is September 20 at 23:57:53 UTC, before Helicon. It cannot test this response. The published protocol reference distinguishes the 48-hour validator minimum from the continuing 14-day delegation minimum (the protocol-feasibility check). Two-day implementation therefore requires identifying a feasible validator strategy, not assuming two-day delegations.

**Model implication.** Test delayed and no-change scenarios with role-specific duration limits. Neither the adoption fraction nor the delay distribution is calibrated by this statement.

### Five or six validators and mostly open-network delegation

> “Like what's the what's the cost structure like And now we run like five or six validators on our own.” [12:11]
>
> “We, but we delegate the majority of the stake to the open network.” [06:44]

**Claim.** A small self-run fleet and substantial delegation to others.

**Checkability and result.** The reward-address check finds 62.919% of the address's day-end delegated AVAX on nodes whose latest recorded reward address is BENQI-labelled. This is not a date-matched ownership test. It cannot show who ran a node or whose capital it used on August 31. The node-attribution extract contains 255 historically observed nodes and four active nodes under that proxy at its own later snapshot, which does not settle the interview-date “five or six.”

**Model implication.** Keep node, reward-address group, ownership, and capital source distinct. Run allocation scenarios with and without the inferred operator group. Do not assert an ownership change “since 2026” without a period-specific address history.

### Cloud costs exceed a claimed benchmark

> “I don't know what the amounts are, but it's significantly higher than whatever Avalabs claims.” [12:20]
>
> “Our AWS and GCP though is a lot higher since before.” [12:30]

**Claim.** A qualitative cost comparison, attributed to engineers in 12:26, without an amount or benchmark source.

**Checkability and result.** Cloud bills, hardware specifications, redundancy, staffing, and the benchmark are off-chain. None was supplied or checked.

**Model implication.** Leave costs uncertain and scenario-based. No monthly per-node cost or break-even AVAX price can be estimated from this passage.

### Redemption churn may rise with liquidity

> “Well, what I'm thinking actually is, you know, I mentioned our churn rate, something like five to eight percent.” [13:18]
>
> “I feel like the rate of unstaking will increase when we do this.” [13:26]

**Claim.** An approximate churn level and a forecast of higher redemptions. The earlier estimate was “8%, maybe less” (07:39). No denominator or time unit is given.

**Checkability and result.** Product mint/redemption events and accounting definitions are needed. P-Chain delegation turnover is not automatically user churn. No product-event check was performed.

**Model implication.** Do not set a daily or annual exit hazard to 5% to 8%. Define the unit and window before introducing a redemption parameter.

### Upgrade revenue loss and TVL compensation

> “So moving into a two-day stake reduces our revenue by 24.6, so it's pretty fucked.” [25:56]
>
> “But I need to find a way to increase our TVL by a quarter, by 25%, just to get back to where we were before.” [26:03]

**Claim.** A forecast revenue reduction and a stated compensating growth target. The preceding “24” and “0.3% anyway” are split across 25:49 and 25:54. The unit for 24.6 is absent from the quoted segment.

**Checkability and result.** No revenue model, schedule, or baseline was provided. As an arithmetic check only, a 24.6% reduction would need 32.63% more TVL under constant linear revenue per unit: `1 / (1 - 0.246) - 1`. A 25% increase would restore 94.25% of baseline. This does not establish which revenue definition Hansen intended.

**Model implication.** Obtain the fee and reward calculation before using these numbers. Preserve the discrepancy rather than convert it into a calibrated target.

### Personal duration and outside option

> “I used to do monthly, but I'm going to do fortnightly.” [34:43]
>
> “I prioritize liquidity now.” [34:56]
>
> “Sell the box, buy something else.” [35:36]
>
> “Although I've not done that.” [35:40]

**Claim.** A personal duration intention and a contemplated alternative, distinguished from executed sales. Upside volatility is mentioned in 35:01.

**Checkability and result.** Personal addresses are not identified. No personal stake or sale history was checked.

**Model implication.** Liquidity and volatility can define competing personal policies. They supply no estimated threshold or population weight.

### Allocation bots use capacity, duration, and stake

> “what their stake duration is, how much stake they have, and then we delegate to them accordingly.” [37:03]
>
> “I think it's like 8,000 or something.” [37:17]
>
> “I can't remember what we have in the docs.” [37:18]

**Claim.** The preceding segment (36:38) describes bots inspecting available capacity. The tentative 8,000 AVAX requirement and uptime explanation in 37:21 need documentation and audio confirmation.

**Checkability and result.** Event-time capacity is present in the observed dataset. A test would compare selected nodes to the feasible alternatives at each acceptance, then examine duration, self-stake, uptime, fees, and governance direction. No such choice comparison was run for this analysis. Aggregate shares and durations do not test the bot rule or demonstrate indifference to fees or yield.

**Model implication.** Treat capacity as a feasibility constraint and the stated selection features as hypotheses. Do not hard-code an 8,000 AVAX threshold or uniform choice from this interview.

### Governance votes and greater capacity may broaden participation

> “Basically, if you hold, if you stake your Qi, you have a pro rata share, pro rata vote of where delegations can go to.” [40:22]
>
> “I feel like the 4X multiple is overly restrictive.” [38:36]

**Claim.** Governance can direct delegations, and a larger delegation multiple could motivate smaller validators to promote themselves (39:46, 41:19 to 41:41).

**Checkability and result.** Vote allocations and contract rules could be matched to P-Chain flows. No governance-contract or counterfactual-capacity check was performed.

**Model implication.** Compare governance-directed and other allocation channels. A capacity change alone does not identify entry, sales effort, fees, or concentration effects.

### Delegation fees transfer revenue to validators

> “Give me a second, I have to… As it stands, we leak \$270,000 to validators a year.” [42:51]
>
> “The idea was that we wanted to give back.” [43:22]

**Claim.** Annual fee expense and a network-support motive. The earlier guess was \$300K (42:44), then revised to \$270,000.

**Checkability and result.** Fee rates and realized rewards could support an AVAX-denominated expense estimate, with a stated valuation date and exclusion of internal transfers. No annual fee or USD conversion check was performed.

**Model implication.** Model validator fee receipts and product fee expense consistently. Neither the dollar estimate nor the stated motive establishes a fixed charitable allocation rule.

### Longer lockup requires a large reward and low emissions could trigger exit

> “Yeah, I guess I want 10% or 12%.” [46:25]
>
> “If I'm—if I'm—if you goes to 2%, I might as well sell everything and just hold hype.” [48:51]

**Claim.** Responses to a hypothetical year-long commitment and reduced emissions. Hash's prompt mixes absolute yield and a spread (45:55). The 10% or 12% cannot safely be interpreted as a spread, percentage-point increment, APR, or APY. The 2% denominator is also unresolved.

**Checkability and result.** Stated preferences require clarification and later observed choices. No quantitative reward-response or exit check was performed.

**Model implication.** These motivate sensitivity scenarios, not an elasticity, tanh curve, exit probability, or calibrated long-duration threshold.

### Renewal automation reduces friction, without a verified implementation claim

> “Yeah, I mean, it's good if they implement it.” [56:05]
>
> “It's more useful for the ETFs, because if you do two-day stake, then you'd want to, yeah.” [56:10]

**Claim.** Approval of automation and a perceived institutional use case. The exchange also contains uncertainty about whether it is in Helicon (55:43 to 55:56).

**Checkability and result.** Transaction-type histories could measure adoption. No automatic-renewal adoption query was run for this analysis. The conversation is not proof that the feature was active on the interview date.

**Model implication.** Distinguish operational renewal friction from willingness to renew. Do not assign all short-duration validators to an automated policy.

### Demand and competing assets shape confidence

> “Because you're talking about wanting to... wanting to fix the supply side when there is a demand side issue.” [48:04]

**Claim.** A participant's explanation of the ecosystem problem, not an independently tested causal finding. Product/security discussion, Ignite history, stablecoin proposals, and later ecosystem commentary add context but do not identify staking-response coefficients. Hash's stablecoin design and value-leakage estimates are interviewer propositions, not Hansen's empirical evidence.

**Checkability and result.** Demand requires defined usage, capital-flow, and price observables. None was checked for this claim.

**Model implication.** Separate exogenous market scenarios from protocol reward effects. Avoid attributing every entry or exit to an ACP.

## Reproduced checks and their limits

These are independent reads of existing built data for this analysis, not a new backend capture or modeling fit. All three Parquet hashes matched their build receipts, and each existing dataset check receipt reported `status: pass`. That status validates its documented structural checks, not participant attribution or causal interpretation.

| Checked extract | Verified Parquet SHA-256 |
| --- | --- |
| Delegation observations | `82335ff61fba6e5a9bdbba7472a077bde5985c111684a26bf453d3ae071726fa` |
| Daily monetary ledger | `838a3df7e74bec49cdc198c1432d39654a529a3dac9f20909be0ee37236dfe3e` |
| Node attribution | `31036a9f8ddb9b7f8d55f5e594513311a3b1447f8e4745c1222321ab9ad0abfc` |

**Delegation count.** The full observed dataset spans acceptance times from 2020-09-22 02:00:00 through 2026-09-20 23:57:53 UTC. The inferred funding address has 6,585,312 of 7,056,204 rows, or 93.3266%. Restricting acceptance to January 1, 2022 onward keeps the numerator but changes the denominator to 6,952,752, or 94.7152%. The full-history percentage must not be described as the January-2022-onward share.

**Stake snapshot.** At 2026-08-31 23:59:59 UTC, using active intervals `[start_time, end_time)`, the address has 21,272 active delegations and 18,266,482.0834 AVAX. The ledger's same-day closing balances are 37,426,733.3545 delegated AVAX and 174,884,627.3887 validator AVAX. The address's delegations are 48.8060% of the delegated total and 8.6036% of the combined total. The ledger row reports complete stake coverage. Validator self-stake belonging to the product has not been added.

**Duration.** All 6,585,312 address rows have durations between 1,209,600 and 1,469,085 seconds: 14.0 to 17.0032986 days. “About 14 to 17 days” is supported. An exact 17-day ceiling is not.

**Reward-address proxy.** Joining those day-end active delegations to `operators.node_id`, where `operator_id` is the node's latest recorded reward address, finds 11,493,067.0904 AVAX on the BENQI-labelled group, or 62.9189%. At August 31 00:00:00 UTC, the corresponding values are 11,420,709.4246 of 18,271,919.2340 AVAX, or 62.5042%. The rounded 62.5% describes the midnight cutoff. The comparable day-end share is 62.9189%. Use one cutoff for numerator and denominator. Latest reward addresses are a retrospective proxy, so neither value proves August 31 ownership.

**Protocol feasibility.** [ACP-273: Minimum Validator Duration](/Phase-II/Wiki/Collections/Economic-ACPs/ACP-273-Minimum-Validator-Duration/) documents the 48-hour validator minimum after Helicon and the continuing 14-day delegator minimum. This rule check is not evidence of a completed BENQI strategy change.

The funding-address and latest-reward-address labels are inferred attribution. They have not been independently confirmed with BENQI. Preserve that qualification wherever the organization is named. See the [data reference](/Phase-II/Wiki/Reference/Data) and [data manifest](/Phase-II/Milestones/Milestone-1/1-2-Data-Manifest/) for dataset definitions and provenance requirements.

### Reproduction recipe

The SQL below uses DuckDB and three separately supplied Parquet extracts: delegation observations, the daily monetary ledger, and node attribution. These extracts are not attached to this interview page. Obtain the matching extracts through the project's data delivery process, check the hashes above against the files and build receipts, and inspect the structural check results before running the queries. The filenames below are local placeholders for those exports, not download links. A newer capture may produce different results.

```sql
CREATE VIEW d AS SELECT * FROM read_parquet(
  'delegation-observations.parquet');
CREATE VIEW m AS SELECT * FROM read_parquet(
  'monetary-ledger.parquet');
CREATE VIEW o AS SELECT * FROM read_parquet(
  'node-attribution.parquet');
CREATE VIEW b AS SELECT * FROM d WHERE delegator_address =
  'avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy';

-- Delegation-count check: explicit full-window and January-2022-onward denominators
SELECT count(*) AS all_events,
       count(*) FILTER (WHERE delegator_address = 'avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy') AS address_events,
       100.0 * count(*) FILTER (WHERE delegator_address = 'avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy') / count(*) AS pct
FROM d;
SELECT count(*) AS all_events,
       count(*) FILTER (WHERE delegator_address = 'avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy') AS address_events,
       100.0 * count(*) FILTER (WHERE delegator_address = 'avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy') / count(*) AS pct
FROM d WHERE accepted_at >= TIMESTAMP '2022-01-01';
-- Duration check: duration bounds in seconds
SELECT count(*), min(duration_seconds), max(duration_seconds) FROM b;
SELECT min(accepted_at), max(accepted_at) FROM d;

-- Stake-snapshot check: day-end active delegation AVAX and comparable ledger balances
SELECT count(*), sum(stake_avax) FROM b
WHERE start_time <= TIMESTAMP '2026-08-31 23:59:59'
  AND end_time > TIMESTAMP '2026-08-31 23:59:59';
SELECT active_delegated_stake_wei / 1e18 AS delegated_avax,
       active_validator_stake_wei / 1e18 AS validator_avax,
       stake_coverage, complete
FROM m WHERE date_utc = DATE '2026-08-31';

-- Reward-address check: both snapshot times, latest-reward-address proxy
WITH snapshots(cutoff) AS (VALUES
  (TIMESTAMP '2026-08-31 00:00:00'),
  (TIMESTAMP '2026-08-31 23:59:59')),
sums AS (
  SELECT s.cutoff, sum(b.stake_avax) AS address_avax,
         sum(b.stake_avax) FILTER (WHERE o.operator_id =
           'avax19zfygxaf59stehzedhxjesads0p5jdvfeedal0') AS matched_avax
  FROM snapshots s JOIN b
    ON b.start_time <= s.cutoff AND b.end_time > s.cutoff
  LEFT JOIN o USING (node_id)
  GROUP BY s.cutoff)
SELECT cutoff, address_avax, matched_avax,
       100.0 * matched_avax / address_avax AS matched_pct
FROM sums ORDER BY cutoff;
```

## Evidence needed before estimating model parameters

| Missing evidence | Effect on model inputs |
| --- | --- |
| Audio review, speaker resolution, and clarification of ambiguous rates and thresholds | Quotes stay machine-transcript evidence, and thresholds stay unspecified. |
| Confirmed addresses, interview-date reward owners, operator control, and capital ownership | Address grouping remains an inference and cannot establish internal versus external allocation. |
| Defined redemption churn, fee economics, costs, and product-flow history | No churn hazard, cost distribution, revenue elasticity, or withdrawal constraint is estimated. |
| Post-Helicon behavior and feasible alternatives at each allocation time | Intentions do not become adoption rates or causal reward sensitivities. |
| A varied participant sample and reviewed coding | One participant cannot establish ecosystem prevalence or behavioral-type weights. |

The [interview method](/Phase-II/Interviews/Interview-Method) defines the evidence and review sequence. Publication of this analysis does not resolve these limits or establish fitted behavior parameters.
