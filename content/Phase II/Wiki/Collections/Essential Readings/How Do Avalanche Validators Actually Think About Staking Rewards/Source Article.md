---
title: "Source Article"
source_title: "How Do Avalanche Validators Actually Think About Staking Rewards?"
description: "Faithful local reproduction of the canonical LinkedIn article."
date: 2026-04-28
author: "Siyu (Eric) Lu, PhD"
canonical_url: "https://www.linkedin.com/pulse/how-do-avalanche-validators-actually-think-staking-rewards-lu-phd-q9igc"
source_id: "lit:eric-validator-rewards"
source_type: article
source_record: "source.json"
build_receipt: "receipts/build.json"
capture_sha256: "97207b7a110a52a1953045a3b9a5373615a2e4cc5d4d3fbe5a19aecf2bbb1818"
topics: [Avalanche, validator economics, staking rewards, ACP-275, ACP-285]
---

**Article** · Siyu (Eric) Lu, PhD · Published April 28, 2026 · [Original article on LinkedIn](https://www.linkedin.com/pulse/how-do-avalanche-validators-actually-think-staking-rewards-lu-phd-q9igc)

![How Do Avalanche Validators Actually Think About Staking Rewards?](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/raw/assets/cover.jpg)

At the Avalanche Foundation, we are in the process of evolving how we support and develop the ecosystem. A core part of that evolution is building a more rigorous, evidence-based foundation for the decisions we make, whether that means how we allocate grants, how we measure ecosystem health, or how we evaluate proposed changes to protocol mechanics.

Rather than relying on stylized assumptions about how ecosystem participants behave, we try to recover actual preferences from on-chain data and use those estimates to inform decisions before they are implemented. This article applies that approach to [ACP-275](https://github.com/avalanche-foundation/ACPs/discussions/274) and [ACP-285](https://github.com/avalanche-foundation/ACPs/pull/285).

The ACPs propose lowering the minimum staking duration on Avalanche's primary network and adjusting the yield curve parameters that govern staking rewards. Both are plausible levers for improving network flexibility and validator participation. But their actual effects depend on something the aggregate data cannot tell us directly: how validators and delegators actually form preferences over yield, duration, and fees. We believe that using a joint structural estimation covering 278 weeks of P-chain data, roughly 375,000 delegator observations, and 1.5 million validator choice-set alternatives.

The central finding reframes how we think about the policy levers at hand: validators optimize over annualized yield, not total period income. That single result changes which parameter actually drives behavior, and by how much.

## The Question

Avalanche validators lock up AVAX and choose how long to stake and what fee to charge delegators. Recent ACPs propose lowering the minimum staking duration and adjusting the yield curve. Whether these changes reshape validator behavior depends on two fundamental questions:

1. How do delegators trade off delegation rewards, fees, and duration?
1. How do validators trade off staking rewards income, delegation fee income, and duration?

We answer this using a joint structural estimation of delegator and validator staking preferences, covering 278 weeks of P-chain data, roughly 375,000 delegator observations, and 1.5 million validator choice-set alternatives.

## The Model

We treat the staking market as two-sided. Delegators are consumers choosing from a menu of validator-duration "products," picking based on APY, lock-up length, validator size, and track record. Using Berry (1994), we recover delegator preferences from aggregate market shares. We find delegators prefer higher APY, shorter durations, and larger validators, with particular aversion to long lock-ups during volatile periods (see Appendix A).

Validators are the supply side. They earn staking rewards from their own stakes by choosing the duration, and at the same time earn delegation fees from delegated stake by choosing duration and fee configurations. We model this using McFadden's (1974) conditional logit, where each validator picks the configuration maximizing expected utility: yield income plus fee income minus the optionality cost of locking capital. The two sides connect through adaptive expectations: validators forecast their delegation using the estimated delegator model (see Appendix B).

Two key assumptions simplify the framework. First, delegators are infinitesimal price-takers whose individual choices do not affect the supply side. Second, validators must stake a fixed amount (i.e., no choice of stake size), which is consistent with observed validator behavior and the institutional constraints active validators have described in conversations with the Foundation. Third, both delegators and validators evaluate staking configurations based on annualized yield, a specification that is strongly favored by the data relative to alternatives and discussed further in the estimation results below.

## Estimation Procedure and Results

We follow a three-stage estimation procedure:

1. Estimate delegator preferences using delegator choice data,
1. Compute expected delegated stake using the estimated delegator preferences under all possible validator staking configurations,
1. Estimate validator preferences using the observed validator chosen staking configurations.

**Delegator preferences.** Delegators value higher APY and shorter lock-ups, with a clear tradeoff between the two: since both enter utility in log form (coefficients of +0.44 on log APY and -0.64 on log weeks), a 1% increase in staking duration requires roughly a 1.5% increase in net APY to leave a delegator indifferent. They also strongly prefer larger validators (coefficient +0.29 on log stake), consistent with a pattern where delegators treat larger nodes as safer or more reliable. Market conditions matter: the negative interaction between duration and AVAX volatility (-0.62) means delegators become substantially more averse to long lock-ups when volatility rises, shortening their preferred durations in turbulent periods (see Appendix A for full coefficients).

It is worth noting that the delegator model's R-squared of 0.202 is modest in absolute terms. This is expected in BLP-style market share regressions, where the object of interest is the recovered preference coefficients rather than overall fit, and where market-level aggregation limits the explanatory power of any single specification. The coefficient estimates are precisely identified and economically interpretable; the fit statistic should be read in that context.

**Validator preferences.** Validators trade off yield income, fee income, and duration, with a strong preference for higher annualized yield and a well-defined cost of locking capital. The marginal rate of substitution is approximately 0.8 percentage points per year of additional annualized yield per extra week of staking duration. This number is remarkably stable: it varies by less than 7% across low, medium, and high price-volatility environments, indicating that validators have consistent, well-defined preferences over the yield-duration tradeoff regardless of market conditions. The optionality cost of locking capital (duration multiplied by volatility) is significant and negative, confirming that validators internalize the risk of being locked in during volatile periods. Interestingly, fee income enters negatively in the APY specification, suggesting validators view fee revenue as a secondary consideration that they trade off against yield when choosing configurations (see Appendix B and C for full coefficients and MRS tables).

## Policy Simulations

We simulate scenarios varying two levers: minimum staking duration and min_consumption_rate (the yield curve parameter controlling how steeply short durations are penalized).

**Lowering minimum duration alone** barely changes average duration but produces a 53% decline in delegation. This result reflects a mechanical constraint: delegators cannot delegate to validators whose staking duration falls below two weeks. It is important to note that this scenario isolates the duration change without any accompanying yield curve adjustment; The combined scenarios below show a materially different picture.

**Lowering min_consumption_rate alone** (0.10 to 0.08) shifts validators to 68% longer durations (10.0 to 16.9 weeks) and increases delegation by 46%. The mechanism: lowering this parameter compresses short-duration APY while barely affecting long-duration APY, pushing APY-focused validators toward longer stakes.

**Combined effects** produce graduated responses. At min_consumption_rate = 0.09, average duration rises to 12.5 weeks; at 0.08, to 16.7 weeks; at 0.07, to 20.9 weeks. Delegation ratios decline in all combined scenarios (40% decline in the primary scenario), though substantially less than the 53% decline from duration reduction alone.

## Recommendations and Caveats

Our estimates are most consistent with coupling lower minimum staking duration with a moderate min_consumption_rate reduction in the range of 0.08 to balance duration effects against delegation declines. More drastic reductions produce extreme duration shifts in parameter regions where the model's out-of-sample reliability is lower, and should be treated with additional caution.

These findings come with important limitations. Both short minimum durations and lower min_consumption_rate values are outside the historical data; results are directional, not precise. The log-linear functional form may amplify behavioral responses in out-of-sample regions (the jump from 12.5 to 20.9 weeks over a 0.02 parameter change warrants caution). The model captures static equilibrium, not dynamic adjustment. And all combined scenarios predict delegation declines whose magnitudes depend on assumptions about delegator substitution.

Conversations with active validators would help ground-truth the central finding: do validators actually think in APY terms? The structural estimation strongly favors this interpretation, but direct evidence would strengthen the policy foundation.

---

## Conclusion

The central finding is that validators think in APY terms. Once you accept that framing, the policy implications follow directly. The yield curve is the primary lever shaping staking behavior; the minimum duration floor is secondary. Lowering the minimum duration alone barely moves the distribution. Adjusting min_consumption_rate does, by compressing short-duration APY and pushing APY-focused validators toward longer commitments. The two levers are complements, but they are not symmetric.

As with the equilibrium tokenomics framework we outlined previously, the value of this analysis is not that it answers what the optimal parameters are. It is that it gives us a disciplined basis for asking the question. The simulations identify a tradeoff that intuition alone would miss: combined interventions produce meaningful duration lengthening, but also delegation declines whose magnitudes sit at the edge of the historical data. A moderate min_consumption_rate reduction to approximately 0.08 is where our estimates suggest the directional goals of ACP-285 can be achieved while limiting exposure to the model's out-of-sample sensitivity.

These results should inform protocol deliberation, not substitute for it. Conversations with active validators remain an important complement to what the structural estimates can tell us. And as Avalanche's staking parameters continue to evolve, monitoring how delegation behavior responds to any implemented changes will help sharpen the empirical foundation for the next round of design decisions. Protocol design is iterative. So is the research that informs it.

Over the coming weeks and months, I will be sharing more research and analysis across the topics at the Avalanche Foundation: tokenomics and value accrual, validator economics, ecosystem measurement, and grants program design. If there are areas where deeper analysis would be useful to you, whether that is a specific mechanism, an open question in the ecosystem, or a topic you think deserves more rigorous treatment, I would welcome that input in the comments.

Thank you for reading and we look forward to discussing more with you.

*Disclaimer: This article is for informational and research purposes only and does not constitute investment advice, an offer, or a solicitation. The analysis reflects hypothetical modeling based on historical data and should not be relied upon as a prediction of future performance.*

## Appendix A: Delegator Estimation

### Estimation Approach

MNL log-odds via Berry (1994) inversion. Weekly market shares are computed from delegation volumes, then log-odds (relative to the outside option of not delegating) are regressed on product characteristics using OLS.

![Table A1. Delegator model — fit statistics](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/raw/assets/figure-01.png)

![Table A2. Delegator MNL log-odds coefficient estimates](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/raw/assets/figure-02.png)

Delegators prefer higher APY, shorter durations, and larger validators. The negative log(weeks) x volatility interaction indicates delegators are especially averse to long commitments during volatile periods. The only insignificant feature is the volatility level effect itself.

---

## Appendix B: Validator Estimation

![Table B1. Validator model specification comparison](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/raw/assets/figure-03.png)

The APY-thinking spec achieves roughly 3x better pseudo R-squared and vastly lower AIC/BIC with the same number of parameters.

### Validator Utility Function

![Validator utility function](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/raw/assets/figure-04.png)

where X_i denotes interaction terms between the core variables and the same exogenous state variables. log(52/w) captures renewal cost, which diminishes as staking duration increases. The term sigma \* w_i captures the optionality cost of locking up stakes.

![Table B2. APY-thinking specification — core coefficients](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/raw/assets/figure-05.png)

log_apy_income (36.6) and renewal_cost (5.4) are both large and highly significant. optionality_cost is negative and significant, meaning validators are worse off when locked into stakes during periods when the option value of that capital is high.

---

## Appendix C: Marginal Rate of Substitution

The MRS measures how much additional annualized yield a validator requires to accept one more week of validation duration, holding utility constant. Evaluated at the median point (9-week duration, 2,000 AVAX stake, 10% fee, median price/volatility):

![Table C. Marginal Rate of Substitution (yield vs. duration)](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/raw/assets/figure-06.png)

Under the APY-thinking spec, validators require approximately 0.80-0.85 percentage points per year of additional annualized yield to accept one more week of staking duration. This is remarkably stable across market conditions, varying by less than 7% across the full price-volatility grid. This consistency indicates well-defined, stable preferences over the yield-duration tradeoff.

Under the period-yield spec, the MRS is erratic: it flips sign in low-volatility environments (negative MRS implies validators would pay to extend duration, which is economically implausible) and exceeds 180 pp/yr in high-volatility regimes. This instability reflects the poor identification of yield in the period-yield model.

---

## Appendix D: Simulation Scenarios and Results

### Protocol Yield Formula

![Protocol yield formula](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/raw/assets/figure-07.png)

where kappa(t) is the time-varying reward pool scarcity factor, d is duration, T is max duration, r_min = min_consumption_rate, and r_max = max_consumption_rate.

### Scenario Definitions

1. **Scenario 1 (Baseline)**: Current protocol parameters (min validation = 2 weeks, r_min = 0.10, r_max = 0.12\$).
1. **Scenario 2 (Short Validation Duration)**: Lower minimum validation duration to 2/7 weeks (~2 days), keeping the yield curve unchanged (r_min = 0.10).
1. **Scenario 3 (Lower r_min = 0.08)**: Reduce min_consumption_rate from 0.10 to 0.08 without changing the minimum duration.
1. **Scenario 4 (Short Duration + r_min = 0.08)**: Combine both interventions.
1. **Scenario 5 (Short Duration + r_min = 0.09)**: Combined intervention with a smaller yield curve change.
1. **Scenario 6 (Short Duration + r_min = 0.07)**: Combined intervention with a larger yield curve change.

### Validation Duration Distribution (APY-Thinking Model)

Validation Duration Distribution

![Validation Duration Distribution — APY-thinking Model](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/raw/assets/figure-08.png)

The baseline concentrates around 5-13 weeks. Lowering r_min shifts mass rightward. At r_min = 0.07 (Scenario 6), validators concentrate in 20-52 week durations as short-duration APY collapses. The graduated response from r_min = 0.09 through 0.07 is visible as a progressive rightward shift. The sawtooth-shape towards the longer duration is due to discretization of the choice grid to reduce computation time.

### Validation Yield Distribution

Validation Yield Distribution

![Validation Yield Distribution — APY-thinking Model](/Phase-II/Wiki/Collections/Essential-Readings/How-Do-Avalanche-Validators-Actually-Think-About-Staking-Rewards/raw/assets/figure-09.png)

Unlike the period-yield model, the yield distribution reshapes as r_min decreases: scenarios with lower r_min develop broader, leftward-shifted distributions as validators split across different duration-yield combinations. The behavioral response (longer durations) partially offsets the mechanical yield decline. The sawtooth-shape towards the longer duration is due to discretization of the choice grid to reduce computation time.

### Extrapolation Caveat

All counterfactual scenarios involve extrapolation beyond the historical data in two dimensions: (1) the minimum staking duration of 2/7 weeks has never been used on Avalanche's P-chain, and (2) min_consumption_rate values below 0.10 have never been in effect.

The sensitivity analysis across r_min in {0.09, 0.08, 0.07} illustrates this concern: average validation duration shifts from 12.5 weeks to 20.9 weeks from a 0.02 change in r_min. This high sensitivity is an artifact of the log-linear functional form of the validator utility function, which fits the historical data well but may not extrapolate reliably to parameter regions far from the estimation sample. These simulation results are best interpreted as directional indicators of policy effects rather than precise point estimates.

---
