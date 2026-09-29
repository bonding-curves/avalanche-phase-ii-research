---
title: "Appropriate Summary Statistics for Evaluating the Historical Fit of System Dynamics Models"
description: "Sterman splits a model's mean square error into bias, unequal variation, and unequal covariation, so a fit report says whether the error is systematic or noise."
---

The contract's validation targets are a correlation, an error in percentage points, trend direction, and timing. None of them says where the error comes from. Sterman gives a decomposition of mean square error into three parts: a constant offset, a wrong amplitude, and a failure to track point by point. Each part points to a different fix, so the decomposition makes a fit report something the modelers can act on.

## Citation

John D. Sterman. 1984. Appropriate Summary Statistics for Evaluating the Historical Fit of System Dynamics Models. Dynamica 10, part II, Winter 1984: 51 to 66. <https://systemdynamics.org/wp-content/uploads/assets/dynamica/volume-10/10-2/4.pdf>. The article has no DOI.

## Question and method

The paper asks which summary statistics suit models whose parameters are not fitted to the aggregate history they are compared with. It rejects $R^2$ for this use, since the whole simulated history is effectively an out-of-sample forecast. It recommends the root mean square percent error and Theil's decomposition of the mean square error between simulated $S_t$ and actual $A_t$:

$$\frac{1}{n}\sum_t (S_t - A_t)^2 = (\bar S - \bar A)^2 + (s_S - s_A)^2 + 2(1 - r)\,s_S\,s_A,$$

where $s$ is a standard deviation and $r$ the correlation of the two series. Dividing each term by the total gives three shares that sum to one:

$$U^M = \frac{(\bar S - \bar A)^2}{\text{MSE}}, \quad U^S = \frac{(s_S - s_A)^2}{\text{MSE}}, \quad U^C = \frac{2(1 - r)\,s_S\,s_A}{\text{MSE}}.$$

A large bias share $U^M$ or variation share $U^S$ means systematic error. A large covariation share $U^C$ means the model follows the trend and amplitude but not every fluctuation.

## Main result

The application is an energy-economy model run from 1950 to 2050 and compared with about 30 years of data. Selected rows of the paper's Table 3:

| Variable | RMSPE, % | $U^M$ | $U^S$ | $U^C$ |
| --- | --- | --- | --- | --- |
| Real private investment | 11.7 | 0.02 | 0.10 | 0.88 |
| Real energy price | 14.0 | 0.58 | 0.00 | 0.42 |
| Net energy consumption | 9.7 | 0.16 | 0.62 | 0.22 |
| Real consumption | 4.7 | 0.54 | 0.29 | 0.17 |
| Primary energy consumption | 4.0 | 0.04 | 0.05 | 0.91 |

For investment, "only 2% of the mean-square-error is due to bias". Nearly two-thirds of the error in net energy consumption is unequal variation. Sterman traces it to a constant 80% efficiency assumption, where actual efficiency fell from 88% in 1950 to 70% in 1977. The paper states that these "are not tests of validity, but are summary statistics", and that historical fit is a weak test among many.

## What it gives this research

1. A fit decomposition for deliverable [2.4](/Phase-II/Milestones/Milestone-2/2-4-Validation-Confirmation/). Report the root mean square error of the simulated **[staking ratio](/Phase-II/Wiki/Reference/Glossary-and-Notation)** with its three Theil shares. A high bias share points to a level error, such as a wrong outside yield. A high variation share points to a response that is too strong or too weak. A high covariation share with a small total error is the acceptable case.
2. A diagnostic that links back to the model. The energy example shows the method: a large share in one component was traced to one assumption in one equation.

## Limits for Avalanche

Point-by-point statistics suit series without strong cycles, and the paper warns they do not suit models of oscillatory modes. Avalanche's staking ratio is smooth at weekly grain, so that warning matters less here than for daily flows. The statistics describe fit and do not test it, so they sit beside the tests of [Barlas](/Phase-II/Wiki/Collections/Supplementary-Research-Papers/1996-Model-Validity-in-System-Dynamics) rather than replacing them.
