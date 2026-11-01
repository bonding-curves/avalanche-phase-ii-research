# Variational Derivation of the Bounded Harmonic Admission Frontier

## Abstract

This paper provides the complete mathematical derivation and economic foundation for Avalanche's duration-dependent validator admission frontier $S_{\min}(d)$. Starting from the first-principles requirement that capital-time commitment $C(d) = S_{\min}(d) \cdot d$ must never fall below the historical baseline of $28{,}000\text{ AVAX-days}$, we prove that the exponent $p = \frac{468}{365} \approx 1.28219$ is the unique parameter that makes day 14 the global minimum of the commitment score across the full staking domain $d \in [2, 365]$. Furthermore, we connect this result to Juan P. Madrigal-Cianci's variational AMM theory (*From Curves to Options*, SSRN 6991580), formulating staking admission as an obstacle problem in the calculus of variations and showing how the Bounded Harmonic Frontier acts as a smooth, regularized relaxation that prevents artificial validator clustering.

---

## 1. The Core Design Question

How much AVAX should a validator be required to stake if we want shorter commitments to require more capital, while ensuring that no commitment is too cheap in terms of capital multiplied by time?

Under Durango and Fortuna, Avalanche enforced a flat admission rule:
$$S_{\min} = 2{,}000\text{ AVAX}, \quad d \ge 14\text{ days}$$

Multiplying stake by duration yields the commitment score:
$$C = \text{Stake} \times \text{Days} = 2{,}000 \times 14 = 28{,}000\text{ AVAX-days}$$

With the Helicon upgrade activating 48-hour staking ($d_{\min} = 2\text{ days}$), maintaining a flat $2{,}000\text{ AVAX}$ requirement would allow a 2-day validator seat for only:
$$2{,}000 \times 2 = 4{,}000\text{ AVAX-days}$$

This represents an $85.7\%$ reduction in capital-time commitment, creating a severe Sybil vulnerability and encouraging high-frequency churn on the P-Chain consensus layer.

### Protocol Design Objectives
1. **Short-Duration Protection**: At $d = 2\text{ days}$, the commitment score must satisfy $C(2) \ge 28{,}000\text{ AVAX-days}$.
2. **Backward Compatibility**: At $d = 14\text{ days}$, the minimum stake must equal exactly $2{,}000\text{ AVAX}$ ($C(14) = 28{,}000$).
3. **Decentralized Retail Access**: At $d = 365\text{ days}$, the minimum stake should drop to a hardware floor of $S_{\text{floor}} = 500\text{ AVAX}$.
4. **Global Invariance**: The commitment score must never dip below $28{,}000\text{ AVAX-days}$ anywhere on $d \in [2, 365]$.

---

## 2. Functional Form of the Bounded Harmonic Frontier

To interpolate between $S(2)$, $S(14) = 2{,}000$, and $S(365) = 500$, we define the normalized harmonic decay variable:
$$\eta(d) = \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}}$$

For $d_{\min} = 2$ and $d_{\max} = 365$:
$$\eta(d) = \frac{\frac{1}{d} - \frac{1}{365}}{\frac{1}{2} - \frac{1}{365}} = \frac{365 - d}{365 \cdot d} \cdot \frac{730}{363}$$

Evaluating $\eta$ at the anchor point $d_{\text{anchor}} = 14$:
$$\eta(14) = \frac{365 - 14}{365 \cdot 14} \cdot \frac{730}{363} = \frac{351}{5110} \cdot \frac{730}{363}$$

Taking the ratio $\frac{\eta(d)}{\eta(14)}$ eliminates the endpoint normalization constants:
$$\frac{\eta(d)}{\eta(14)} = \frac{\frac{365 - d}{365 \cdot d}}{\frac{365 - 14}{365 \cdot 14}} = \frac{14(365 - d)}{d(365 - 14)} = \frac{14(365 - d)}{351 \cdot d}$$

The admission frontier is defined as:
$$S(d) = S_{\text{floor}} + (S_{\text{anchor}} - S_{\text{floor}}) \left[ \frac{\eta(d)}{\eta(14)} \right]^p$$

Substituting $S_{\text{floor}} = 500$, $S_{\text{anchor}} = 2{,}000$:
$$S(d) = 500 + 1500 \left[ \frac{14(365 - d)}{351 \cdot d} \right]^p$$

---

## 3. Exact Analytical Derivation of $p = \frac{468}{365}$

The commitment score function is:
$$C(d) = S(d) \cdot d = 500 \cdot d + 1500 \cdot d \left[ \frac{14(365 - d)}{351 \cdot d} \right]^p$$

At $d = 14$, $C(14) = 2{,}000 \times 14 = 28{,}000\text{ AVAX-days}$. 

For $C(d) \ge 28{,}000$ to hold for all durations, $C(d)$ must reach its stationary minimum at $d = 14$. The first-order condition requires:
$$\left. \frac{dC}{dd} \right|_{d=14} = 0$$

### Step-by-Step Differentiation
Let $f(d) = \frac{14(365 - d)}{351 \cdot d} = \frac{14}{351} \left( \frac{365}{d} - 1 \right)$. Note that $f(14) = 1$.

The derivative of $f(d)$ is:
$$f'(d) = \frac{14}{351} \left( -\frac{365}{d^2} \right)$$

Evaluating at $d = 14$:
$$f'(14) = \frac{14}{351} \left( -\frac{365}{14^2} \right) = -\frac{365}{351 \cdot 14}$$

Now, differentiate $C(d) = 500 \cdot d + 1500 \cdot d \cdot [f(d)]^p$ using the product rule:
$$\frac{dC}{dd} = 500 + 1500 [f(d)]^p + 1500 \cdot d \cdot p [f(d)]^{p-1} f'(d)$$

Evaluate at $d = 14$ where $f(14) = 1$:
$$\left. \frac{dC}{dd} \right|_{d=14} = 500 + 1500(1) + 1500(14) \cdot p (1) \left( -\frac{365}{351 \cdot 14} \right)$$
$$\left. \frac{dC}{dd} \right|_{d=14} = 2000 - 1500 \cdot p \cdot \frac{365}{351}$$

Setting the derivative to zero:
$$2000 - 1500 \cdot p \cdot \frac{365}{351} = 0$$
$$1500 \cdot p \cdot \frac{365}{351} = 2000$$
$$p = \frac{2000}{1500} \cdot \frac{351}{365} = \frac{4}{3} \cdot \frac{351}{365}$$

Since $351 = 3 \times 117$:
$$p = \frac{4 \times 117}{365} = \frac{468}{365} \approx 1.28219178$$

### General Closed-Form Equation
For any anchor stake $S_{\text{anchor}}$, floor $S_{\text{floor}}$, anchor duration $d_{\text{anchor}}$, and maximum duration $d_{\max}$:
$$\boxed{p^* = \left( \frac{S_{\text{anchor}}}{S_{\text{anchor}} - S_{\text{floor}}} \right) \left( 1 - \frac{d_{\text{anchor}}}{d_{\max}} \right)}$$

---

## 4. Uniqueness and Global Optimality Proof

To confirm that $d = 14$ is a strict local minimum, compute the second derivative $\frac{d^2C}{dd^2}$ at $d = 14$ with $p = p^*$:
$$\left. \frac{d^2C}{dd^2} \right|_{d=14, p=p^*} = \frac{S_{\text{anchor}}(S_{\text{anchor}} d_{\text{anchor}} - S_{\text{floor}} d_{\max})}{d_{\text{anchor}}(d_{\text{anchor}} - d_{\max})(S_{\text{anchor}} - S_{\text{floor}})}$$
$$\left. \frac{d^2C}{dd^2} \right|_{d=14} = \frac{103{,}000}{2{,}457} \approx +41.921 > 0$$

Because $\frac{d^2C}{dd^2} > 0$, $d = 14$ is a strict local minimum.

### Global Monotonicity of $C'(d)$
Analyzing $C'(d)$ across the entire domain $d \in [2, 365]$:
- For $d \in [2, 14)$: $\frac{dC}{dd} < 0$. $C(d)$ is strictly decreasing.
- At $d = 14$: $\frac{dC}{dd} = 0$. $C(14) = 28{,}000\text{ AVAX-days}$.
- For $d \in (14, 365]$: $\frac{dC}{dd} > 0$. $C(d)$ is strictly increasing up to $C(365) = 182{,}500\text{ AVAX-days}$.

### Uniqueness Ruling
- **If $p < \frac{468}{365}$**: $\left. \frac{dC}{dd} \right|_{d=14} > 0$. The slope at 14 is positive, meaning that immediately to the left ($d < 14$), $C(d) < 28{,}000$. Short-duration commitments violate the Sybil parity barrier. (At $p = 1.0$, $C(2) = 22{,}718\text{ AVAX-days}$).
- **If $p > \frac{468}{365}$**: $\left. \frac{dC}{dd} \right|_{d=14} < 0$. The slope at 14 is negative, meaning that immediately to the right ($d > 14$), $C(d) < 28{,}000$. Medium-duration commitments violate the Sybil parity barrier. (At $p = 1.5$, $C(20.1) = 27{,}121\text{ AVAX-days}$).

Therefore, $p = \frac{468}{365}$ is the **unique exponent** that satisfies $C(d) \ge 28{,}000\text{ AVAX-days}$ across the entire domain.

---

## 5. Connection to Juan Madrigal-Cianci's Variational AMM Theory

In *From Curves to Options: A Variational Theory of Optimal Market Making* (SSRN 6991580), Juan Madrigal-Cianci formulates AMM design as an infinite-dimensional calculus of variations problem over liquidity density $\ell(p)$:
$$\max_{\ell(p)} \int \left[ \text{TraderSurplus}(p, \ell(p)) + \text{LPSurplus}(p, \ell(p)) \right] \pi(p)\,dp \quad \text{s.t.} \quad \int \ell(p)\,dp \le B$$

### Critical Structural Distinctions Between AMMs and PoS Staking
1. **Payoff Curvature & LVR**: In Juan's AMM, pool value $V(p)$ is strictly concave in spot price ($V''(p) = -\ell(p) \le 0$) due to continuous rebalancing against arbitrageurs, enabling Carr-Madan options spanning. A PoS validator holds a linear delta-1 spot position ($V(p) = S \cdot p \implies V''(p) = 0$). There is no inventory rebalancing and zero LVR.
2. **The True Option Sold by Validators**: A validator locking AVAX for duration $d$ forgoes an **American switching/stopping option** over stochastic external yields $r_{\text{ext}}(t)$ (e.g. Aave, alternative Layer 1 yields).
3. **Boundary Censoring vs Interior Stationarity**: The historical 65% concentration at 14 days is a boundary KKT corner solution ($\mu_{\min} > 0$ on $d \ge 14$), not an interior Euler-Lagrange optimum ($\frac{\delta \mathcal{J}}{\delta \ell} = 0$). It must be analyzed as a censored Bayesian inverse problem.

### Staking Admission as an Obstacle Problem
The protocol's variational problem can be stated as:
$$\min_{S(d)} \int_{d_{\min}}^{d_{\max}} \left[ \frac{1}{2} (S'(d))^2 + \lambda(d) S(d) + \text{Cost}(S(d), d) \right] dd \quad \text{s.t.} \quad S(d) \ge \psi(d)$$

where the obstacle function is:
$$\psi(d) = \max\left( \frac{28{,}000}{d}, 500 \right)$$

The exact obstacle curve $\psi(d)$ has a non-differentiable corner (kink) at $d = 56\text{ days}$ (where $\frac{28{,}000}{56} = 500$). An admission policy with a kink induces artificial clustering of validators at the kink. 

The Bounded Harmonic Frontier with $p = \frac{468}{365}$ is the **unique smooth variational regularizer** that:
1. Enforces $S(d) \ge \psi(d)$ globally without ever violating the obstacle.
2. Touches the obstacle tangentially at $d = 14\text{ days}$ with zero first derivative.
3. Interpolates smoothly to the hardware floor $S_{\text{floor}} = 500$ at $d = 365\text{ days}$ without kinks or clustering penalties.

---

## 6. Quantitative Evaluation

The table below reports numerical evaluations across the candidate admission designs:

| Design | Stake at 2d | Score at 2d | Score at 14d | Score at 365d | Min Score (Day) | Violates Sybil Barrier? | Violates HW Floor? | Roughness $\int (S'')^2$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Status Quo Flat (2,000 AVAX)** | 2,000 | 4,000 | 28,000 | 730,000 | 4,000 (2.0d) | **YES (Deficit: 24,000)** | NO | $0.0$ |
| **Pure Hyperbola ($28{,}000/d$)** | 14,000 | 28,000 | 28,000 | 28,000 | 28,000 (all) | NO | **YES (Stake: 76.7)** | $1.61 \times 10^7$ |
| **Piecewise Obstacle ($\max[28k/d, 500]$)** | 14,000 | 28,000 | 28,000 | 182,500 | 28,000 (2-56d) | NO | NO | $1.61 \times 10^7$ (Kink at 56d) |
| **Bounded Harmonic ($p = 1.000$)** | 11,359 | 22,718 | 28,000 | 182,500 | 22,718 (2.0d) | **YES (Deficit: 5,282)** | NO | $9.81 \times 10^6$ |
| **Bounded Harmonic ($p^* = 1.282$)** | **19,484** | **38,968** | **28,000** | **182,500** | **28,000 (14.0d)** | **NO (Deficit: 0)** | **NO** | $5.65 \times 10^7$ (Smooth) |
| **Bounded Harmonic ($p = 1.500$)** | 29,717 | 59,434 | 28,000 | 182,500 | 27,121 (20.1d) | **YES (Deficit: 879)** | NO | $2.01 \times 10^8$ |

---

## 7. Next Steps: From Constraint Satisfaction to Joint Welfare Maximization

The exponent $p = \frac{468}{365} \approx 1.28219$ satisfies the Sybil parity constraint. To establish full economic optimality in the sense of Juan's paper:
1. **Stackelberg Bilevel Optimization**: Formulate validator duration supply $\pi(d \mid S_{\min}, r)$ as an endogenous agent response to the protocol's boundary levers.
2. **$\chi^2$-DRO Ambiguity Sets**: Use Juan's distributionally robust optimization technique to regularize the frontier against macro outside-yield regime shifts.
3. **Out-of-Sample Empirical Validation**: Execute the pre-registered holdout test on **October 27, 2026** against quarantined post-Granite and post-Helicon on-chain records.
