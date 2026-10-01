---
title: "BENQI interview evidence analysis"
description: "Private draft linking Hansen's machine-transcribed statements to topic codes, reproducible checks, and bounded model hypotheses."
date: 2026-09-30
status: draft
owner: project-manager
interview_id: mh-2026-08-31-benqi-liquid-staking-interview
---

# BENQI interview evidence analysis

Hansen describes two different decisions: managing a liquid staking service's redemption needs and choosing how to stake his personal AVAX. Those decisions should remain separate in the model. The observed funding address is sufficiently concentrated to warrant its own analysis stratum, conditional on the inferred BENQI attribution. This interview supports candidate decision rules. It does not estimate population preferences, response coefficients, or future adoption.

This is the private `I2` draft requested in the modeling thread on September 30 at 18:40. Shawn authorized preparation of this analysis. Participant permission for Foundation delivery, scientific acceptance, and promotion into Phase II remain unrecorded here. No source bytes were changed.

## Source and interpretation boundary

The [transcript](/Phase-II/Interviews/BENQI-2026-08-31/transcript) covers 603 segments and approximately 65 minutes from August 31, 2026 at 19:00:42 America/New_York. `transcript.json` is the segment-level authority. It records zero seconds of audio review. Hansen and Hash are likely speaker assignments, while Shawn's microphone track is named. Exact quotations below retain machine wording and spelling. Timestamps are elapsed recording time, truncated to seconds from `start_ms`, rather than the beginning of the longer merged Markdown turn.

The transcript uses variants such as “Banky,” “SFOX,” and “Essovox.” BENQI and sAVAX in the analysis are contextual interpretations, not silent transcript corrections. Several segments appear to merge a question into an answer. Audio review is needed before treating those passages as verified quotations. The existing minutes, narrative, and meeting summary are derived interpretations, not independent corroboration.

| Source | SHA-256 checked for this draft |
| --- | --- |
| `transcript.json` | `e7e028ba5a067ccc7a558b48bfdfd63d81059a39559f5807b0a5bb535326bd49` |
| `transcript.md` | `742b8460d66fc1def82eaf298adcff59314dadbab6f8c9823b4c84af8cdbe41d` |

## Claims by topic

The `VT1` to `VT8` codes come from the interview plan. A checked address fact can corroborate an action, but cannot establish its motivation.

### C1. Business and personal objectives are different (VT1, VT2)

> “For the Essovox business side, we just take a skim off the total amount of stake that comes through.” [14:31, `seg-0125`]
>
> “So we prioritize increasing Essovox TVL as much as we can, and minimizing costs.” [14:37, `seg-0126`]

**Claim.** The service seeks assets under management and low costs. Hansen separates this from the personal economic decision in `seg-0124` and `seg-0133`.

**Checkability and result.** P-Chain holdings and flows are observable after address attribution. Corporate objectives and fee income require product terms and business records. No objective or income check was performed.

**Model implication.** Separate the operator's service objective from the owner's personal staking policy. Do not infer either objective solely from address activity.

### C2. Product scale and delegation dominance (VT1, VT5)

> “I'm happy to dig through the questions if you want, but I think it's probably useful to discuss how we do it for SOVAX first, since it's about 10% or 12% of stake.” [06:52, `seg-0056`]
>
> “Yes, but that's because we chose to do delegations, right?” [42:19, `seg-0360`]

**Claim.** The product is large and deliberately delegates. The second quote answers Hash's question about “93% of all the delegations” in `seg-0357` to `seg-0359`. That is a count, not an AVAX share.

**Checkability and result.** `E1` reproduces 93.33% of observed delegation events across the full dataset. At August 31 day-end, `E2` finds 18.266M AVAX, 48.806% of delegated stake and 8.604% of total active stake, from this funding address's delegations alone. The latter omits validator self-stake, so it neither confirms nor disproves the stated 10% to 12% product total.

**Model implication.** Analyze this funding address separately, and distinguish event counts from capital weights. A count share cannot set its share of model capital or its share of independent economic actors.

### C3. Short delegations and longer validators manage liquidity (VT3)

> “So we primarily—well, in the current state, before the Helicon upgrade, we have been just doing 14 to 18-day stakes delegations because we prioritize liquidity for users.” [07:15, `seg-0057`]
>
> “So yeah, we prioritize liquidity, and we try to have a mix of long-term validators just so we can raise the yield a little bit.” [08:10, `seg-0064`]

**Claim.** Short delegations provide liquidity alongside longer validator commitments.

**Checkability and result.** `E3` finds funding-address delegation durations from 14 days to 17.0032986 days. This corroborates short durations, with a more precise upper bound than the account given. No date-matched validator-duration mix was measured in this check. Chain durations alone do not prove the liquidity motive.

**Model implication.** Separate validator and delegation duration distributions, and add a redemption constraint as a hypothesis requiring product-flow data. Use observed durations as moments, not the rounded interview interval as a hard rule.

### C4. Two days is an intention with an implementation delay (VT3, VT4, VT7)

> “We are probably leaning towards just reducing all state towards two days, just because the delta between two-day APR and 14-day APR is in like 20 bits or five bits.” [08:32, `seg-0067`]
>
> “If it plays out, it'll probably take months for us to implement” [09:20, `seg-0074`]

**Claim.** A possible response, not a completed operational change. Hansen says he cannot remember the rate difference (`seg-0068`). “Nothing undecided” in `seg-0073` is ambiguous machine wording and cannot establish a firm decision.

**Checkability and result.** The delegation dataset's latest acceptance is September 20 at 23:57:53 UTC, before Helicon. It cannot test this response. The source-linked model kernel distinguishes the 48-hour validator minimum from the continuing 14-day delegation minimum (`E5`). Two-day implementation therefore requires identifying a feasible validator strategy, not assuming two-day delegations.

**Model implication.** Test delayed and no-change scenarios with role-specific duration limits. Neither the adoption fraction nor the delay distribution is calibrated by this statement.

### C5. Five or six validators and mostly open-network delegation (VT1, VT5)

> “Like what's the what's the cost structure like And now we run like five or six validators on our own.” [12:11, `seg-0099`]
>
> “We, but we delegate the majority of the stake to the open network.” [06:44, `seg-0054`]

**Claim.** A small self-run fleet and substantial delegation to others.

**Checkability and result.** `E4` finds 62.919% of the address's day-end delegated AVAX on nodes whose latest recorded reward address is BENQI-labelled. This is not a date-matched ownership test. It cannot show who ran a node or whose capital it used on August 31. The operator run has 255 historically observed nodes and four active nodes under that proxy at its own later snapshot, which does not settle the interview-date “five or six.”

**Model implication.** Keep node, reward-address group, ownership, and capital source distinct. Run allocation scenarios with and without the inferred operator group. Do not assert an ownership change “since 2026” without a period-specific address history.

### C6. Cloud costs exceed a claimed benchmark (VT2)

> “I don't know what the amounts are, but it's significantly higher than whatever Avalabs claims.” [12:20, `seg-0100`]
>
> “Our AWS and GCP though is a lot higher since before.” [12:30, `seg-0102`]

**Claim.** A qualitative cost comparison, attributed to engineers in `seg-0101`, without an amount or benchmark source.

**Checkability and result.** Cloud bills, hardware specifications, redundancy, staffing, and the benchmark are off-chain. None was supplied or checked.

**Model implication.** Leave costs uncertain and scenario-based. No monthly per-node cost or break-even AVAX price can be estimated from this passage.

### C7. Redemption churn may rise with liquidity (VT3, VT8)

> “Well, what I'm thinking actually is, you know, I mentioned our churn rate, something like five to eight percent.” [13:18, `seg-0110`]
>
> “I feel like the rate of unstaking will increase when we do this.” [13:26, `seg-0112`]

**Claim.** An approximate churn level and a forecast of higher redemptions. The earlier estimate was “8%, maybe less” (`seg-0060`). No denominator or time unit is given.

**Checkability and result.** Product mint/redemption events and accounting definitions are needed. P-Chain delegation turnover is not automatically user churn. No product-event check was performed.

**Model implication.** Do not set a daily or annual exit hazard to 5% to 8%. Define the unit and window before introducing a redemption parameter.

### C8. Upgrade revenue loss and TVL compensation (VT2, VT4)

> “So moving into a two-day stake reduces our revenue by 24.6, so it's pretty fucked.” [25:56, `seg-0231`]
>
> “But I need to find a way to increase our TVL by a quarter, by 25%, just to get back to where we were before.” [26:03, `seg-0232`]

**Claim.** A forecast revenue reduction and a stated compensating growth target. The preceding “24” and “0.3% anyway” are split across `seg-0229` and `seg-0230`. The unit for 24.6 is absent from the quoted segment.

**Checkability and result.** No revenue model, schedule, or baseline was provided. As an arithmetic check only, a 24.6% reduction would need 32.63% more TVL under constant linear revenue per unit: `1 / (1 - 0.246) - 1`. A 25% increase would restore 94.25% of baseline. This does not establish which revenue definition Hansen intended.

**Model implication.** Obtain the fee and reward calculation before using these numbers. Preserve the discrepancy rather than convert it into a calibrated target.

### C9. Personal duration and outside option (VT3, VT6)

> “I used to do monthly, but I'm going to do fortnightly.” [34:43, `seg-0292`]
>
> “I prioritize liquidity now.” [34:56, `seg-0294`]
>
> “Sell the box, buy something else.” [35:36, `seg-0297`]
>
> “Although I've not done that.” [35:40, `seg-0299`]

**Claim.** A personal duration intention and a contemplated alternative, distinguished from executed sales. Upside volatility is mentioned in `seg-0295`.

**Checkability and result.** Personal addresses are not identified. No personal stake or sale history was checked.

**Model implication.** Liquidity and volatility can define competing personal policies. They supply no estimated threshold or population weight.

### C10. Allocation bots use capacity, duration, and stake (VT5)

> “what their stake duration is, how much stake they have, and then we delegate to them accordingly.” [37:03, `seg-0306`]
>
> “I think it's like 8,000 or something.” [37:17, `seg-0308`]
>
> “I can't remember what we have in the docs.” [37:18, `seg-0309`]

**Claim.** The preceding segment (`seg-0305`) describes bots inspecting available capacity. The tentative 8,000 AVAX requirement and uptime explanation in `seg-0310` need documentation and audio confirmation.

**Checkability and result.** Event-time capacity is present in the observed dataset. A test would compare selected nodes to the feasible alternatives at each acceptance, then examine duration, self-stake, uptime, fees, and governance direction. No such choice comparison was rerun for this draft. Aggregate shares and durations do not test the bot rule or demonstrate indifference to fees or yield.

**Model implication.** Treat capacity as a feasibility constraint and the stated selection features as hypotheses. Do not hard-code an 8,000 AVAX threshold or uniform choice from this interview.

### C11. Governance votes and greater capacity may broaden participation (VT5, VT7)

> “Basically, if you hold, if you stake your Qi, you have a pro rata share, pro rata vote of where delegations can go to.” [40:22, `seg-0346`]
>
> “I feel like the 4X multiple is overly restrictive.” [38:36, `seg-0327`]

**Claim.** Governance can direct delegations, and a larger delegation multiple could motivate smaller validators to promote themselves (`seg-0343`, `seg-0351` to `seg-0354`).

**Checkability and result.** Vote allocations and contract rules could be matched to P-Chain flows. No governance-contract or counterfactual-capacity check was performed.

**Model implication.** Compare governance-directed and other allocation channels. A capacity change alone does not identify entry, sales effort, fees, or concentration effects.

### C12. Delegation fees transfer revenue to validators (VT2, VT5)

> “Give me a second, I have to… As it stands, we leak \$270,000 to validators a year.” [42:51, `seg-0365`]
>
> “The idea was that we wanted to give back.” [43:22, `seg-0367`]

**Claim.** Annual fee expense and a network-support motive. The earlier guess was \$300K (`seg-0364`), then revised to \$270,000.

**Checkability and result.** Fee rates and realized rewards could support an AVAX-denominated expense estimate, with a stated valuation date and exclusion of internal transfers. No annual fee or USD conversion check was performed.

**Model implication.** Model validator fee receipts and product fee expense consistently. Neither the dollar estimate nor the stated motive establishes a fixed charitable allocation rule.

### C13. Longer lockup requires a large reward and low emissions could trigger exit (VT4, VT6, VT8)

> “Yeah, I guess I want 10% or 12%.” [46:25, `seg-0387`]
>
> “If I'm—if I'm—if you goes to 2%, I might as well sell everything and just hold hype.” [48:51, `seg-0417`]

**Claim.** Responses to a hypothetical year-long commitment and reduced emissions. Hash's prompt mixes absolute yield and a spread (`seg-0385`). The 10% or 12% cannot safely be interpreted as a spread, percentage-point increment, APR, or APY. The 2% denominator is also unresolved.

**Checkability and result.** Stated preferences require clarification and later observed choices. No quantitative reward-response or exit check was performed.

**Model implication.** These motivate sensitivity scenarios, not an elasticity, tanh curve, exit probability, or calibrated long-duration threshold.

### C14. Renewal automation reduces friction, without a verified implementation claim (VT3, VT7)

> “Yeah, I mean, it's good if they implement it.” [56:05, `seg-0506`]
>
> “It's more useful for the ETFs, because if you do two-day stake, then you'd want to, yeah.” [56:10, `seg-0507`]

**Claim.** Approval of automation and a perceived institutional use case. The exchange also contains uncertainty about whether it is in Helicon (`seg-0500` to `seg-0505`).

**Checkability and result.** Transaction-type histories could measure adoption. No automatic-renewal adoption query was run for this draft. The conversation is not proof that the feature was active on the interview date.

**Model implication.** Distinguish operational renewal friction from willingness to renew. Do not assign all short-duration validators to an automated policy.

### C15. Demand and competing assets shape confidence (VT6, VT8)

> “Because you're talking about wanting to... wanting to fix the supply side when there is a demand side issue.” [48:04, `seg-0408`]

**Claim.** A participant's explanation of the ecosystem problem, not an independently tested causal finding. Product/security discussion, Ignite history, stablecoin proposals, and later ecosystem commentary add context but do not identify staking-response coefficients. Hash's stablecoin design and value-leakage estimates are interviewer propositions, not Hansen's empirical evidence.

**Checkability and result.** Demand requires defined usage, capital-flow, and price observables. None was checked for this claim.

**Model implication.** Separate exogenous market scenarios from protocol reward effects. Avoid attributing every entry or exit to an ACP.

## Reproduced checks and their limits

These are independent reads of existing built data for this draft, not a new backend capture or modeling fit. All three Parquet hashes matched their build receipts, and each existing `check.json` reported `status: pass`. That status validates its documented structural checks, not participant attribution or causal interpretation.

| ID | Input run and verified Parquet SHA-256 |
| --- | --- |
| `E1`–`E4` | `observed-delegations-2026-09-28`, `82335ff61fba6e5a9bdbba7472a077bde5985c111684a26bf453d3ae071726fa` |
| `E2` | `avax-monetary-daily-2026-09-30`, `838a3df7e74bec49cdc198c1432d39654a529a3dac9f20909be0ee37236dfe3e` |
| `E4` | `operators-2026-09-30`, `31036a9f8ddb9b7f8d55f5e594513311a3b1447f8e4745c1222321ab9ad0abfc` |

**E1. Delegation count.** The full observed dataset spans acceptance times from 2020-09-22 02:00:00 through 2026-09-20 23:57:53 UTC. The inferred funding address has 6,585,312 of 7,056,204 rows, or 93.3266%. Restricting acceptance to January 1, 2022 onward keeps the numerator but changes the denominator to 6,952,752, or 94.7152%. The memo's 93.3% should not be described as the January-2022-onward share.

**E2. Stake snapshot.** At 2026-08-31 23:59:59 UTC, using active intervals `start_time, end_time)`, the address has 21,272 active delegations and 18,266,482.0834 AVAX. The ledger's same-day closing balances are 37,426,733.3545 delegated AVAX and 174,884,627.3887 validator AVAX. The address's delegations are 48.8060% of the delegated total and 8.6036% of the combined total. The ledger row reports complete stake coverage. Validator self-stake belonging to the product has not been added.

**E3. Duration.** All 6,585,312 address rows have durations between 1,209,600 and 1,469,085 seconds: 14.0 to 17.0032986 days. “About 14 to 17 days” is supported. An exact 17-day ceiling is not.

**E4. Reward-address proxy.** Joining those day-end active delegations to `operators.node_id`, where `operator_id` is the node's latest recorded reward address, finds 11,493,067.0904 AVAX on the BENQI-labelled group, or 62.9189%. At August 31 00:00:00 UTC, the corresponding values are 11,420,709.4246 of 18,271,919.2340 AVAX, or 62.5042%. This reproduces the memo's rounded 62.5% under its midnight cutoff, not the ledger's day-end cutoff. Use one cutoff for numerator and denominator. Latest reward addresses are a retrospective proxy, so neither value proves August 31 ownership.

**E5. Protocol feasibility.** The client model's source-linked `src/avalanche_research/model/protocol.py`, function `min_stake_duration_seconds`, retains 14 days for delegators and switches validators to 48 hours at Helicon. It cites AvalancheGo revision `70bd6d063b7343fd2cd8217200aaf77b57f19f68`, `getDelegatorRules` and `primaryNetworkValidatorMinStakeDuration`. This draft inspected the kernel definition, not a new mainnet transaction or fresh upstream-code verification.

The [Snowpeer capture record supports the address inference. The client attribution records `OA3` and `OA4` classify the reward-address label and funding-address mapping as `INFERENCE`. This draft did not independently confirm the addresses with BENQI. Preserve that qualification wherever the organization is named.

### Reproduction recipe

In the client research checkout with the three pinned runs available, open DuckDB and define `d`, `m`, and `o` as the tables below. Read each run's `dataset/build.json` and compare its `outputs[].sha256` with the Parquet file before running the queries. Inspect its `dataset/check.json` separately. No network fetch is needed.

```sql
CREATE VIEW d AS SELECT * FROM read_parquet(
  'data/runs/observed-delegations-2026-09-28/dataset/observed-delegations.parquet');
CREATE VIEW m AS SELECT * FROM read_parquet(
  'data/runs/avax-monetary-daily-2026-09-30/dataset/avax-monetary-daily.parquet');
CREATE VIEW o AS SELECT * FROM read_parquet(
  'data/runs/operators-2026-09-30/dataset/operators.parquet');
CREATE VIEW b AS SELECT * FROM d WHERE delegator_address =
  'avax1tnuesf6cqwnjw7fxjyk7lhch0vhf0v95wj5jvy';

-- E1: explicit full-window and January-2022-onward denominators
SELECT count(*) AS all_events,
       count(*) FILTER (WHERE concentrated_address) AS address_events,
       100.0 * count(*) FILTER (WHERE concentrated_address) / count(*) AS pct
FROM d;
SELECT count(*) AS all_events,
       count(*) FILTER (WHERE concentrated_address) AS address_events,
       100.0 * count(*) FILTER (WHERE concentrated_address) / count(*) AS pct
FROM d WHERE accepted_at >= TIMESTAMP '2022-01-01';
-- E3: duration bounds in seconds
SELECT count(*), min(duration_seconds), max(duration_seconds) FROM b;
SELECT min(accepted_at), max(accepted_at) FROM d;

-- E2: day-end active delegation AVAX and comparable ledger balances
SELECT count(*), sum(stake_avax) FROM b
WHERE start_time <= TIMESTAMP '2026-08-31 23:59:59'
  AND end_time > TIMESTAMP '2026-08-31 23:59:59';
SELECT active_delegated_stake_wei / 1e18 AS delegated_avax,
       active_validator_stake_wei / 1e18 AS validator_avax,
       stake_coverage, complete
FROM m WHERE date_utc = DATE '2026-08-31';

-- E4: both snapshot times, latest-reward-address proxy
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

## Evidence needed before model-input promotion

| ID | Missing evidence | Effect on model inputs |
| --- | --- | --- |
| `R1` | Audio review, speaker resolution, and clarification of ambiguous rates and thresholds | Quotes stay machine-transcript evidence, and thresholds stay unspecified. |
| `R2` | Confirmed addresses, interview-date reward owners, operator control, and capital ownership | Address grouping remains an inference and cannot establish internal versus external allocation. |
| `R3` | Defined redemption churn, fee economics, costs, and product-flow history | No churn hazard, cost distribution, revenue elasticity, or withdrawal constraint is estimated. |
| `R4` | Post-Helicon behavior and feasible alternatives at each allocation time | Intentions do not become adoption rates or causal reward sensitivities. |
| `R5` | A varied participant sample and reviewed coding | One participant cannot establish ecosystem prevalence or behavioral-type weights. |
| `R6` | Recorded participant delivery permission, Hash's interpretation review, and Shawn's promotion | This named, quoted draft remains private. |

The [methodology draft](/Phase-II/Interviews/BENQI-2026-08-31/methodology-draft) defines the next evidence and review sequence. None of these checks authorizes fitting or publication.
