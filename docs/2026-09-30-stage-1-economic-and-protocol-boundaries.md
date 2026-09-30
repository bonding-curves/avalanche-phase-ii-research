# Stage 1: Economic and Protocol Boundary Specification

**Repository:** `avalanche-phase-ii-research`  
**Subsystem:** Avalanche Primary Network Consensus & PlatformVM  
**Document Type:** Formal Stage 1 Deliverable (Economic & Boundary Calibration)  
**Parent Work Plan:** [docs/2026-09-30-admission-frontier-technical-work-plan.md](file:///home/hash/Hub/Projects/avalanche-phase-ii-research/docs/2026-09-30-admission-frontier-technical-work-plan.md)  
**Status:** Completed Draft  

---

## 1. Executive Summary

This document fulfills **Stage 1: Establish the Economic and Protocol Boundaries** of the canonical mechanism design work plan for the Duration-Dependent PoS Admission Frontier:

$$S_{\min}(d) = S_{\mathrm{floor}} + \Delta S \cdot \eta(d)^p, \quad \Delta S = S_{\mathrm{short}} - S_{\mathrm{floor}}$$

Stage 1 answers one central question:

> **What should the two ends of the curve mean?**

We establish the boundary quadruple:

$$(d_{\min}, d_{\max}, S_{\mathrm{floor}}, S_{\mathrm{short}})$$

by evaluating verified PlatformVM consensus constraints, empirical validator operating cost structures, liquid staking outside options, and capital-time security invariants.

---

## 2. Protocol Regimes & Duration Boundaries ($d_{\min}, d_{\max}$)

The duration domain is bounded by the state transition rules of PlatformVM:

$$d \in [d_{\min}, d_{\max}]$$

Because the final activation regime depends on governance scheduling (ACP-273 / Helicon status), we carry two parallel scenarios:

### Regime A (Helicon / ACP-273 Target Activation)
* **$d_{\min} = 2\text{ days}$ ($48\text{ hours} = 172{,}800\text{ seconds}$):** Enacted in `ava-labs/avalanchego/genesis/params.go` (`HeliconMinStakeDuration`) and ACP-273.
* **$d_{\max} = 365\text{ days}$ ($31{,}536{,}000\text{ seconds}$):** PlatformVM maximum staking horizon (`genesis/genesis_mainnet.go` `MaxStakeDuration`).
* **$d_{\mathrm{del},\min} = 14\text{ days}$ ($1{,}209{,}600\text{ seconds}$):** PlatformVM minimum delegation horizon (`txs/executor/staker_tx_verification_helpers.go` `MinDelegationDuration`).

### Regime B (Legacy Baseline Benchmark)
* **$d_{\min} = 14\text{ days}$ ($336\text{ hours}$):** Legacy minimum staking tenure (`MinStakeDuration`).
* **$d_{\max} = 365\text{ days}$:** Identical.
* **$d_{\mathrm{del},\min} = 14\text{ days}$:** Identical.

---

## 3. Economic Determination of the Long-Duration Floor ($S_{\mathrm{floor}}$)

The terminal floor $S_{\mathrm{floor}}$ is the minimum self-stake required at maximum commitment duration ($d_{\max} = 365\text{ days}$).

### 3.1 The Solvency Condition
For a validator of type $\theta_i$, operating at $S = S_{\mathrm{floor}}$ for duration $d_{\max}$ is economically viable if the expected net return exceeds the validator's outside option:

$$V_i(S_{\mathrm{floor}}, d_{\max}) = \text{Rewards} - \text{Operating Cost} - \text{Capital Opportunity Cost} \ge 0$$

Formally:

$$S_{\mathrm{floor}} \cdot \text{ARR}(365\text{d}) \cdot P_{\mathrm{AVAX}} - C_{\mathrm{op}} - S_{\mathrm{floor}} \cdot r_{\mathrm{outside}} \cdot P_{\mathrm{AVAX}} \ge 0$$

Solving for $S_{\mathrm{floor}}$:

$$S_{\mathrm{floor}} \ge \frac{C_{\mathrm{op}}}{(\text{ARR}(365\text{d}) - r_{\mathrm{outside}}) \cdot P_{\mathrm{AVAX}}}$$

where:
* $\text{ARR}(365\text{d}) = 6.383\%$: Annualized staking reward rate under ACP-285 at current circulating supply ($470\text{M AVAX}$), evaluated via `avalanche_research.model.protocol.primary_network_reward`.
* $r_{\mathrm{outside}} = 4.15\%$: Capital opportunity cost, benchmarked to the 30-day trailing APY of liquid staking tokens (sAVAX / ggAVAX) and DeFi lending yields.
* $\Delta r = \text{ARR}(365\text{d}) - r_{\mathrm{outside}} = 6.383\% - 4.15\% = 2.233\%$: Net annual yield spread earned by running a standalone validator rather than holding liquid staked tokens.
* $C_{\mathrm{op}}$: Annual validator operating cost in USD.
* $P_{\mathrm{AVAX}}$: Market price of AVAX in USD.

### 3.2 Operator Cost Structures ($C_{\mathrm{op}}$)
We model three empirical operator classes:
1. **Home Bare-Metal Operator:** Amortized hardware (dedicated 8-core mini-PC / NUC, 32GB RAM, 2TB NVMe SSD at $\$600$ amortized over 3 years = $\$200/\text{yr}$) plus incremental residential electricity and broadband ($\$15/\text{mo} = \$180/\text{yr}$). Total: **$\$380/\text{year}$**.
2. **Budget Commercial Cloud VPS:** High-reliability budget cloud instance (e.g., Hetzner CCX33 / AX42, Contabo, OVH) at $\$45/\text{month}$. Total: **$\$540/\text{year}$**.
3. **Standard Commercial Cloud VPS:** Tier-1 cloud instance (e.g., AWS c6g.2xlarge, GCP c2d-highcpu-8) at $\$60 - \$100/\text{month}$. Total: **$\$720/\text{year}$**.

### 3.3 Empirical Viability Grid
Using `research/scripts/calibrate_stage1_boundaries.py`, we evaluate minimum viable $S_{\mathrm{floor}}$ across prices and cost structures:

#### Liquid Staking Opportunity Cost Scenario ($\Delta r = 2.233\%$, benchmarked to sAVAX 4.15%)
| Operator Class | $C_{\mathrm{op}}$ ($/\text{yr}$) | $P = \$15$ | $P = \$20$ | $P = \$25$ | $P = \$30$ | $P = \$40$ | $P = \$50$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Home Bare-Metal** | $\$380$ | $1{,}135\text{ AVAX}$ | $851\text{ AVAX}$ | $681\text{ AVAX}$ | $567\text{ AVAX}$ | $425\text{ AVAX}$ | $340\text{ AVAX}$ |
| **Budget Cloud VPS** | $\$540$ | $1{,}612\text{ AVAX}$ | $1{,}209\text{ AVAX}$ | $967\text{ AVAX}$ | $806\text{ AVAX}$ | $605\text{ AVAX}$ | $484\text{ AVAX}$ |
| **Standard Cloud VPS** | $\$720$ | $2{,}150\text{ AVAX}$ | $1{,}612\text{ AVAX}$ | $1{,}290\text{ AVAX}$ | $1{,}075\text{ AVAX}$ | $806\text{ AVAX}$ | $645\text{ AVAX}$ |

#### Cash Break-Even Scenario ($r_{\mathrm{outside}} = 0\%$, nominal dollar solvency ignoring opportunity cost)
| Operator Class | $C_{\mathrm{op}}$ ($/\text{yr}$) | $P = \$15$ | $P = \$20$ | $P = \$25$ | $P = \$30$ | $P = \$40$ | $P = \$50$ |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Home Bare-Metal** | $\$380$ | $397\text{ AVAX}$ | $298\text{ AVAX}$ | $238\text{ AVAX}$ | $198\text{ AVAX}$ | $149\text{ AVAX}$ | $119\text{ AVAX}$ |
| **Budget Cloud VPS** | $\$540$ | $564\text{ AVAX}$ | $423\text{ AVAX}$ | $338\text{ AVAX}$ | $282\text{ AVAX}$ | $212\text{ AVAX}$ | $169\text{ AVAX}$ |
| **Standard Cloud VPS** | $\$720$ | $752\text{ AVAX}$ | $564\text{ AVAX}$ | $451\text{ AVAX}$ | $376\text{ AVAX}$ | $282\text{ AVAX}$ | $226\text{ AVAX}$ |

### 3.4 Findings on $S_{\mathrm{floor}}$ Selection
* **Lower Bound Candidate ($S_{\mathrm{floor}} = 500\text{ AVAX}$):**
  * Fully covers cash operating costs for home operators down to $P_{\mathrm{AVAX}} = \$12$, and budget VPS down to $P_{\mathrm{AVAX}} = \$17$.
  * Achieves full economic parity with liquid staking at $P_{\mathrm{AVAX}} \ge \$34$ for home operators. At $P = \$25$, home operators face an opportunity cost drag of only $-\$101/\text{year}$ relative to sAVAX, but remain cash-flow positive ($+\$418/\text{year}$ nominal profit).
  * Directly fulfills the community accessibility goal of ACP-49.
* **Conservative Candidate ($S_{\mathrm{floor}} = 1{,}000\text{ AVAX}$):**
  * Guarantees complete economic opportunity-cost viability for home operators at $P_{\mathrm{AVAX}} \ge \$17$, and budget VPS operators at $P_{\mathrm{AVAX}} \ge \$24$.
  * Provides a resilient solvency cushion against bear market price compressions.
* **Conclusion:** The defensible empirical range for $S_{\mathrm{floor}}$ is **$[500, 1{,}000]\text{ AVAX}$**.

---

## 4. Short-End Admission Boundary ($S_{\mathrm{short}}$)

$S_{\mathrm{short}}$ is the minimum self-stake required at the shortest protocol staking duration $d_{\min}$.

### 4.1 The Legacy Capital-Time Benchmark
In legacy PlatformVM:
$$S_{\mathrm{legacy}} = 2{,}000\text{ AVAX}, \quad d_{\min,\mathrm{legacy}} = 14\text{ days}$$
The historical capital-time commitment invariant is:
$$K_{\mathrm{baseline}} = 2{,}000\text{ AVAX} \times 14\text{ days} = 28{,}000\text{ AVAX-days}$$

If the protocol activates $d_{\min} = 2\text{ days}$ (Regime A) and demands that a 2-day validator post an identical capital-time product to legacy:
$$S_{\mathrm{short}}^{\mathrm{iso}} = \frac{K_{\mathrm{baseline}}}{d_{\min}} = \frac{28{,}000\text{ AVAX-days}}{2\text{ days}} = 14{,}000\text{ AVAX}$$

### 4.2 Security Cushion & Anti-Churn Boundary
A strict iso-commitment benchmark assumes that an attacker or high-frequency churner experiences the same operational friction per stint. However, rolling 2-day stints generates $7\times$ higher transaction volume on P-Chain than rolling 14-day stints.

If governance requires a security cushion to suppress high-frequency turnover (e.g., flash arbitrage or ETF redemption facilities):
$$S_{\mathrm{short}}^{\mathrm{elevated}} = 20{,}000\text{ AVAX} \quad (K = 40{,}000\text{ AVAX-days})$$
At $20{,}000\text{ AVAX}$, a 2-day validator must post $+42.9\%$ more capital-time commitment than the legacy 14-day baseline, providing robust resistance against ephemeral churn.

### 4.3 Conclusion on $S_{\mathrm{short}}$
* Under Regime A ($d_{\min} = 2\text{ days}$): **$S_{\mathrm{short}} \in [14{,}000, 20{,}000]\text{ AVAX}$**.
* Under Regime B ($d_{\min} = 14\text{ days}$): **$S_{\mathrm{short}} = S_{\min}(14\text{d}) = 2{,}000\text{ AVAX}$** (identical to legacy).

---

## 5. Formal Stage 1 Boundary Parameter Table

The table below synthesizes the complete boundary specification with epistemic status labels as required by Stage 1:

| Parameter | Symbol | Plausible Value / Range | Unit | Status Label | Derivation / Source Rationale |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Minimum Staking Duration (Target)** | $d_{\min}$ (Regime A) | $2.0$ ($48\text{ hours}$) | Days | **Confirmed Protocol Input** | `genesis/params.go` (`HeliconMinStakeDuration`), ACP-273. |
| **Minimum Staking Duration (Legacy)** | $d_{\min}$ (Regime B) | $14.0$ ($336\text{ hours}$) | Days | **Confirmed Protocol Input** | `genesis/genesis_mainnet.go` (`MinStakeDuration`). |
| **Maximum Staking Duration** | $d_{\max}$ | $365.0$ ($8{,}760\text{ hours}$) | Days | **Confirmed Protocol Input** | `genesis/genesis_mainnet.go` (`MaxStakeDuration`). |
| **Minimum Delegation Duration** | $d_{\mathrm{del},\min}$ | $14.0$ ($336\text{ hours}$) | Days | **Confirmed Protocol Input** | `txs/executor/staker_tx_verification_helpers.go`. |
| **Long-Duration Floor (Lower)** | $S_{\mathrm{floor},\mathrm{min}}$ | $500.0$ | AVAX | **Design Assumption** | ACP-49 target; cash break-even for home stakers down to $\$12$ AVAX. |
| **Long-Duration Floor (Upper)** | $S_{\mathrm{floor},\mathrm{max}}$ | $1{,}000.0$ | AVAX | **Empirical Estimate** | Economic opportunity-cost break-even for budget VPS at $\$24.20$ AVAX. |
| **Short-Duration Barrier (Iso)** | $S_{\mathrm{short},\mathrm{iso}}$ | $14{,}000.0$ | AVAX | **Design Assumption** | Capital-time parity ($28{,}000\text{ AVAX-days} / 2\text{ days}$). |
| **Short-Duration Barrier (Secure)** | $S_{\mathrm{short},\mathrm{sec}}$ | $20{,}000.0$ | AVAX | **Design Assumption** | $+42.9\%$ capital cushion against high-frequency churn. |
| **Target Hard-Fork Activation** | — | Helicon vs Post-Helicon | — | **Unresolved External Input** | Governed by Foundation / Ava Labs release schedule; carried as scenario. |
| **PlatformVM Consensus Budget** | $L_{\mathrm{budget}}$ | Latency envelope | ms | **Unresolved External Input** | Governed by Ava Labs consensus engineering; carried as scenario. |

---

## 6. Hand-off to Stage 2

With the boundary quadruple $(d_{\min}, d_{\max}, S_{\mathrm{floor}}, S_{\mathrm{short}})$ established:
* **Stage 2 Work:** Analyze historical telemetry from `01-renewal-panel.parquet` to evaluate how validators trade off duration, reward, and delegation friction, and identify the candidate pivot region $d_{\mathrm{pivot}}$.
