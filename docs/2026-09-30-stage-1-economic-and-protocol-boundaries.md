# Stage 1: Establish the Economic and Protocol Boundaries

**Repository:** `avalanche-phase-ii-research`  
**Subsystem:** Avalanche Primary Network Consensus & PlatformVM  
**Document Type:** Stage 1 Research Deliverable  
**Parent Work Plan:** [docs/2026-09-30-admission-frontier-technical-work-plan.md](file:///home/hash/Hub/Projects/avalanche-phase-ii-research/docs/2026-09-30-admission-frontier-technical-work-plan.md)  
**Status:** Completed Draft  

---

## 1. Stage 1 Question

> **What should the two ends of the curve mean?**

This stage establishes the boundary quadruple:

$$(d_{\min}, d_{\max}, S_{\mathrm{floor}}, S_{\mathrm{short}})$$

The values are established by analyzing protocol constraints, empirical validator cost accounting, liquid staking outside options, and capital-time security benchmarks.

---

## 2. Protocol Regimes and Duration Boundaries ($d_{\min}, d_{\max}$)

The duration domain is governed by PlatformVM state verification rules:

$$d \in [d_{\min}, d_{\max}]$$

Because final activation depends on governance scheduling (ACP-273 / Helicon status), we carry two parallel scenarios rather than treating the choice as a blocker:

### Regime A: Helicon / ACP-273 Target Activation
* **$d_{\min} = 2.0\text{ days}$ ($48\text{ hours}$):** Confirmed protocol rule in `genesis/params.go` (`HeliconMinStakeDuration`) and ACP-273.
* **$d_{\max} = 365.0\text{ days}$:** Confirmed protocol upper bound in `genesis/genesis_mainnet.go` (`MaxStakeDuration`).
* **$d_{\mathrm{del},\min} = 14.0\text{ days}$:** Confirmed delegation minimum in `txs/executor/staker_tx_verification_helpers.go`.

### Regime B: Legacy Baseline Benchmark
* **$d_{\min} = 14.0\text{ days}$ ($336\text{ hours}$):** Historical minimum staking tenure (`MinStakeDuration`).
* **$d_{\max} = 365.0\text{ days}$:** Identical.
* **$d_{\mathrm{del},\min} = 14.0\text{ days}$:** Identical.

---

## 3. Estimating the Economic Floor ($S_{\mathrm{floor}}$)

The terminal floor $S_{\mathrm{floor}}$ is the minimum self-stake required at maximum duration ($d_{\max} = 365\text{ days}$).

### 3.1 Solvency Condition
A validator of type $\theta_i$ is economically viable at $S_{\mathrm{floor}}$ if:

$$\text{Rewards} - \text{Operating Cost} - \text{Capital Opportunity Cost} \ge 0$$

Formally:

$$S_{\mathrm{floor}} \cdot \text{ARR}(365\text{d}) \cdot P_{\mathrm{AVAX}} - C_{\mathrm{op}} - S_{\mathrm{floor}} \cdot r_{\mathrm{outside}} \cdot P_{\mathrm{AVAX}} \ge 0$$

Solving for $S_{\mathrm{floor}}$:

$$S_{\mathrm{floor}} \ge \frac{C_{\mathrm{op}}}{(\text{ARR}(365\text{d}) - r_{\mathrm{outside}}) \cdot P_{\mathrm{AVAX}}}$$

where:
* $\text{ARR}(365\text{d}) = 6.383\%$: Annualized staking reward rate under ACP-285 at current circulating supply ($470\text{M AVAX}$), evaluated via `avalanche_research.model.protocol.primary_network_reward`.
* $r_{\mathrm{outside}} = 4.15\%$: Benchmark opportunity cost of capital, based on trailing 30-day liquid staking yield (sAVAX / ggAVAX).
* $\Delta r = \text{ARR}(365\text{d}) - r_{\mathrm{outside}} = 2.233\%$: Net annual yield spread earned by validating rather than holding liquid staked tokens.
* $C_{\mathrm{op}}$: Annual validator operating cost in USD.
* $P_{\mathrm{AVAX}}$: Market price of AVAX in USD.

### 3.2 Operator Cost Archetypes ($C_{\mathrm{op}}$)
* **Home Bare-Metal:** Amortized mini-PC ($600 over 3 years = $200/yr) + residential utilities ($180/yr) = **$\$380/\text{year}$**.
* **Budget Commercial Cloud VPS:** Dedicated budget instance (e.g., Hetzner CCX33 / AX42) at $45/month = **$\$540/\text{year}$**.
* **Standard Commercial Cloud VPS:** Tier-1 cloud instance (e.g., AWS c6g.2xlarge, GCP) at $60–$100/month = **$\$720/\text{year}$**.

### 3.3 Viability Grid
Evaluated using `research/scripts/calibrate_stage1_boundaries.py`:

#### Full Economic Opportunity Cost Viability ($\Delta r = 2.233\%$, relative to sAVAX 4.15%)
| Operator Class | $C_{\mathrm{op}}$ ($/\text{yr}$) | $P = \$15$ | $P = \$20$ | $P = \$25$ | $P = \$30$ | $P = \$40$ | $P = \$50$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Home Bare-Metal** | $\$380$ | $1{,}135\text{ AVAX}$ | $851\text{ AVAX}$ | $681\text{ AVAX}$ | $567\text{ AVAX}$ | $425\text{ AVAX}$ | $340\text{ AVAX}$ |
| **Budget Cloud VPS** | $\$540$ | $1{,}612\text{ AVAX}$ | $1{,}209\text{ AVAX}$ | $967\text{ AVAX}$ | $806\text{ AVAX}$ | $605\text{ AVAX}$ | $484\text{ AVAX}$ |
| **Standard Cloud VPS** | $\$720$ | $2{,}150\text{ AVAX}$ | $1{,}612\text{ AVAX}$ | $1{,}290\text{ AVAX}$ | $1{,}075\text{ AVAX}$ | $806\text{ AVAX}$ | $645\text{ AVAX}$ |

#### Cash Break-Even Viability ($r_{\mathrm{outside}} = 0\%$, nominal dollar solvency)
| Operator Class | $C_{\mathrm{op}}$ ($/\text{yr}$) | $P = \$15$ | $P = \$20$ | $P = \$25$ | $P = \$30$ | $P = \$40$ | $P = \$50$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Home Bare-Metal** | $\$380$ | $397\text{ AVAX}$ | $298\text{ AVAX}$ | $238\text{ AVAX}$ | $198\text{ AVAX}$ | $149\text{ AVAX}$ | $119\text{ AVAX}$ |
| **Budget Cloud VPS** | $\$540$ | $564\text{ AVAX}$ | $423\text{ AVAX}$ | $338\text{ AVAX}$ | $282\text{ AVAX}$ | $212\text{ AVAX}$ | $169\text{ AVAX}$ |
| **Standard Cloud VPS** | $\$720$ | $752\text{ AVAX}$ | $564\text{ AVAX}$ | $451\text{ AVAX}$ | $376\text{ AVAX}$ | $282\text{ AVAX}$ | $226\text{ AVAX}$ |

### 3.4 Economic Floor Range
The purpose is to establish a plausible range, not one single number:
* **Lower Bound ($500\text{ AVAX}$, ACP-49 candidate):**
  * Fully self-sustaining on cash operating costs for home operators down to $P_{\mathrm{AVAX}} = \$12$, and budget VPS down to $P_{\mathrm{AVAX}} = \$17$.
  * Breaks even against liquid staking at $P_{\mathrm{AVAX}} \ge \$34$ for home operators.
* **Upper Bound ($1{,}000\text{ AVAX}$, Conservative candidate):**
  * Fully breaks even against liquid staking for home operators at $P_{\mathrm{AVAX}} \ge \$17$, and budget VPS operators at $P_{\mathrm{AVAX}} \ge \$24.20$.
* **Plausible Economic Range:** **$S_{\mathrm{floor}} \in [500, 1{,}000]\text{ AVAX}$**.

---

## 4. Constraining the Short-End Barrier ($S_{\mathrm{short}}$)

$S_{\mathrm{short}}$ is the minimum self-stake required at minimum duration $d_{\min}$.

### 4.1 Legacy Capital-Time Benchmark
Under legacy PlatformVM:
$$K_{\mathrm{baseline}} = 2{,}000\text{ AVAX} \times 14\text{ days} = 28{,}000\text{ AVAX-days}$$
Under Regime A ($d_{\min} = 2\text{ days}$), matching this legacy commitment benchmark yields:
$$S_{\mathrm{short}}^{\mathrm{iso}} = \frac{28{,}000\text{ AVAX-days}}{2\text{ days}} = 14{,}000\text{ AVAX}$$

### 4.2 Elevated Anti-Churn Hurdle
If the protocol requires a higher barrier to suppress high-frequency churn from ephemeral arbitrageurs:
$$S_{\mathrm{short}}^{\mathrm{elevated}} = 20{,}000\text{ AVAX} \quad (K = 40{,}000\text{ AVAX-days}, \text{ a } +42.9\% \text{ hurdle})$$

* Under Regime A ($d_{\min} = 2\text{ days}$): **$S_{\mathrm{short}} \in [14{,}000, 20{,}000]\text{ AVAX}$**.
* Under Regime B ($d_{\min} = 14\text{ days}$): **$S_{\mathrm{short}} = 2{,}000\text{ AVAX}$**.

---

## 5. Formal Stage 1 Output Table

| Parameter | Symbol | Plausible Value / Range | Unit | Epistemic Status Label | Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Minimum Staking Duration (Target)** | $d_{\min}$ (Regime A) | $2.0$ ($48\text{ hours}$) | Days | **Confirmed protocol input** | `genesis/params.go` (`HeliconMinStakeDuration`), ACP-273. |
| **Minimum Staking Duration (Legacy)** | $d_{\min}$ (Regime B) | $14.0$ ($336\text{ hours}$) | Days | **Confirmed protocol input** | `genesis/genesis_mainnet.go` (`MinStakeDuration`). |
| **Maximum Staking Duration** | $d_{\max}$ | $365.0$ | Days | **Confirmed protocol input** | `genesis/genesis_mainnet.go` (`MaxStakeDuration`). |
| **Minimum Delegation Duration** | $d_{\mathrm{del},\min}$ | $14.0$ | Days | **Confirmed protocol input** | `staker_tx_verification_helpers.go`. |
| **Long-Duration Floor (Range)** | $S_{\mathrm{floor}}$ | $[500.0, 1{,}000.0]$ | AVAX | **Empirical estimate** | Cash solvency down to $\$12$ AVAX ($500\text{ AVAX}$) and full LST break-even at $\$24$ AVAX ($1{,}000\text{ AVAX}$). |
| **Short-Duration Barrier (Regime A)** | $S_{\mathrm{short}}$ | $[14{,}000.0, 20{,}000.0]$ | AVAX | **Design assumption** | Legacy capital-time parity ($14\text{k}$) vs. elevated anti-churn barrier ($20\text{k}$). |
| **Short-Duration Barrier (Regime B)** | $S_{\mathrm{short}}$ | $2{,}000.0$ | AVAX | **Design assumption** | Legacy baseline barrier at 14 days. |
| **Target Hard-Fork Activation** | — | Helicon vs. Post-Helicon | — | **Unresolved external input** | Carried as scenario (Regime A vs Regime B). |
| **Validated Consensus Latency Budget** | $L_{\mathrm{budget}}$ | Latency envelope | ms | **Unresolved external input** | Carried as scenario; depends on Ava Labs capacity telemetry. |
