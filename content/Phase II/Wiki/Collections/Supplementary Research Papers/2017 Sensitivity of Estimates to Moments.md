---
title: "Measuring the Sensitivity of Parameter Estimates to Estimation Moments"
description: "Andrews, Gentzkow, and Shapiro give a matrix that shows which moments drive each estimated parameter and predicts the bias from a given violation of the model's assumptions."
---

A calibrated model fits many moments at once, and a reader cannot see which ones set a given parameter. This paper gives a matrix that answers that question and costs almost nothing to compute. It is the table the Foundation asked for at the Milestone 1 review, parameters against moments, made quantitative.

## Citation

Isaiah Andrews, Matthew Gentzkow, and Jesse M. Shapiro. 2017. Measuring the Sensitivity of Parameter Estimates to Estimation Moments. The Quarterly Journal of Economics 132, no. 4: 1553 to 1592. DOI [10.1093/qje/qjx023](https://doi.org/10.1093/qje/qjx023). Open working paper version: NBER Working Paper 20673, revised May 2017, <https://www.nber.org/papers/w20673>.

## Question and method

The paper asks how a reader can see which moments drive a structural estimate, and predict the bias a specific violation of the model's assumptions would cause. For an estimator that minimizes $\hat g(\theta)^\top W \hat g(\theta)$, with $G$ the derivative of the moments with respect to the parameters, the sensitivity matrix is

$$\Lambda = -\left(G^\top W G\right)^{-1} G^\top W.$$

Row $k$ of $\Lambda$ says how much parameter $k$ moves per unit change in each moment. If an alternative model would shift the moments by $\Delta g$, the local bias in the estimates is approximately $\Lambda\,\Delta g$. $G$ and $W$ are already computed during estimation, so $\Lambda$ adds no new estimation.

| | Moment 1 | Moment 2 | Moment 3 | Moment 4 |
| --- | --- | --- | --- | --- |
| Parameter A | large | small | small | small |
| Parameter B | small | large | large | small |

The table above is the form of the output. Each cell of $\Lambda$ is filled with a number, and a reader sees that parameter A rests on moment 1 and parameter B on moments 2 and 3.

## Main result

The paper applies $\Lambda$ to three published models. The results below are from the May 2017 working paper.

| Application | Finding |
| --- | --- |
| DellaVigna, List, and Malmendier, 2012, social pressure in giving | Estimated social pressure is USD 0.14, standard error USD 0.08. If 1% of households give USD 10 for reasons outside the model, the estimate is overstated by about 5%. At 10% of households it is overstated by more than 50% |
| Gourinchas and Parker, 2002, consumption over the life cycle | If shopping intensity varies with age, the discount factor is overstated by 0.4 percentage points and risk aversion understated by about a third |
| Berry, Levinsohn, and Pakes, 1995, automobile demand | A violation of one supply-side exclusion biases the estimated markup of 0.33 down by 17 percentage points, a corrected 0.50 |

## What it gives this research

1. A published parameter-to-moment table for deliverable [1.4](/Phase-II/Milestones/Milestone-1/1-4-Behavioral-Calibration/). $\Lambda$ shows which two or three moments set each behavioral parameter, such as the lock-up cost or the renewal rate.
2. A robustness check for deliverable [2.4](/Phase-II/Milestones/Milestone-2/2-4-Validation-Confirmation/). For a named doubt, for example that 2025 exits were driven by operators leaving for reasons outside the model, $\Lambda\,\Delta g$ says how far each parameter would move.

## Limits for Avalanche

$\Lambda$ is local. It is accurate near the baseline assumptions, and the authors recommend a full sensitivity analysis for large departures. The Avalanche model's moments sit on different scales, such as a share, a count of weeks, and a ratio, and the paper notes that the units of $\Lambda$ depend on the units of the moments. Comparing which moment matters most therefore needs moments on a common scale. When the model is simulated, $G$ must come from finite differences run with common random numbers, or simulation noise will swamp it.
