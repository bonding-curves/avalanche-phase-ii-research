# Avalanche Validator Digital Twin & Stage 4 Simulation Engine

Empirical simulation engine evaluating the Duration-Dependent PoS Admission Frontier mechanism:

$$S_{\min}(d) = S_{\mathrm{floor}} + (S_{\mathrm{short}} - S_{\mathrm{floor}}) \cdot \left[ \eta(d) \right]^p$$

where $\eta(d) = \frac{1/d - 1/d_{\max}}{1/d_{\min} - 1/d_{\max}}$.

---

## 1. Data Inputs

The simulation operates on a three-layer empirical data architecture:

- **Layer A (Full Historical Foundation):**
  - `research/data/01-renewal-panel.parquet`: 57,067 staking periods (Genesis 2020-09-10 to present).
  - `research/data/15-all-nodes-archetype.parquet`: 7,635 unique historical Primary Network nodes with lifespan, peak bond, median duration, and operator address clusters.
- **Layer B (Current-Regime Initialization):**
  - 602 live active validator nodes from `15-all-nodes-archetype.parquet` (`LIVE_NOW == 1`) matched to their active staking stints in `01-renewal-panel.parquet` (`is_right_censored == 1`).
  - 453 unique operator entity clusters (`operator_address`).
- **Layer C (Post-ACP-285 / Helicon):**
  - Isolates reward schedule observations for downstream empirical calibration of yield elasticity as renewal cycles mature.

---

## 2. State Variables

Each validator in the active population is modeled as a `ValidatorRecord`:

- `node_id`: Machine identity (`NodeID-...`).
- `self_bond_avax`: Validator self-bonded stake in AVAX.
- `total_duration_days`: Selected commitment duration $d \in [2, 365]$.
- `remaining_days`: Time until current staking period expiry.
- `commission_fee`: Delegation fee rate (default 2% commercial/institutional, 5% solo).
- `delegations_received_avax`: Delegated capital stock bound to the node.
- `uptime_days`: Accumulated active validation days.
- `is_active`: Boolean status in the consensus set.
- `operator_address`: Entity address clustering multi-node deployments.
- `profile`: Empirical classification into Profile A, B, or C.
- `tenure_days`: Cumulative historical validation lifespan.
- `streak_count`: Number of consecutive renewal stints without gap.

Macroeconomic and network state variables:
- `staked_supply_avax`: Aggregate consensus weight ($S_{\mathrm{total}} + D_{\mathrm{total}}$).
- `bonded_self_stake_avax`: Total validator self-stake.
- `circulating_supply_avax`: Minted liquid AVAX supply (initialized to 473.6M AVAX).
- `staking_ratio`: Consensus participation ratio ($S_{\mathrm{staked}} / S_{\mathrm{circulating}}$).

---

## 3. Behavioral Rules

### Baseline Empirical Replay
- Expiring validators renew according to empirical profile priors:
  - Profile A (Solo / Capital-Constrained): 84.6% renewal probability.
  - Profile B (Commercial Delegator-Facing): 88.6% renewal probability.
  - Profile C (Institutional / Ecosystem): 92.2% renewal probability.
- Renewing validators draw durations from their profile's empirical frequency distribution.
- Entrants arrive via a Poisson process matching the empirical historical rate (mean 21.25 nodes/week).

### Mechanism-Aware Behavioral Response
- **Admissibility Barrier:** Duration $d$ is available to validator $i$ if and only if $S_{\min}(d) \le S_i$.
- **Illiquidity Friction:** If a validator's preferred duration is blocked by $S_{\min}(d)$, they incur an illiquidity penalty proportional to the log lockup extension ratio.
- **Bounded Yield-Sensitivity Scenarios:**
  - **Scenario Y1 (Low Sensitivity):** Habitual persistence. Moves to shortest feasible duration; zero yield chasing ($\beta_{\mathrm{yield}} = 0.0, \beta_{\mathrm{lockup}} = 1.5$).
  - **Scenario Y2 (Moderate Sensitivity):** Proportional substitution balancing ACP-285 yield spreads against lockup cost ($\beta_{\mathrm{yield}} = 12.0, \beta_{\mathrm{lockup}} = 1.0$).
  - **Scenario Y3 (High Sensitivity):** Aggressive yield optimization toward peak tenures ($\beta_{\mathrm{yield}} = 30.0, \beta_{\mathrm{lockup}} = 0.5$).

---

## 4. Measures of Effectiveness (MOEs)

All outcomes are quantified strictly in consensus, economic, and network terms:

1. **MOE 1: Validator-Set Stability ($S_N$):**
   $$S_N = \frac{\sigma(N)}{\bar{N}}$$
2. **MOE 2: Validator Churn & Renewal Dynamics ($\lambda_{\mathrm{turnover}}, \lambda_{\mathrm{short}}$):**
   $$\lambda_{\mathrm{turnover}}(t) = \frac{A(t) + E(t)}{2N(t)}, \qquad \lambda_{\mathrm{short}} = \text{churn on } d < 14\text{d}$$
3. **MOE 3: Stake Concentration across Nodes and Clustered Operators:**
   $$HHI_{\mathrm{node}} = \sum s_i^2 \times 10{,}000, \qquad HHI_{\mathrm{operator}} = \sum \omega_j^2 \times 10{,}000$$
   $$C_{10,\mathrm{operator}} = \sum_{j=1}^{10} \omega_{(j)}, \qquad C_{20,\mathrm{operator}} = \sum_{j=1}^{20} \omega_{(j)}$$
4. **MOE 4: Economic Viability Across Validator Profiles ($V_{\mathrm{profile}, k}$):**
   Fraction of validators within Profile $k$ maintaining positive net operating margins (staking revenue minus server infrastructure costs).
5. **MOE 5: Network-Capacity Pressure ($H_{\mathrm{cap}}$):**
   Operational safety headroom against Ava Labs capacity benchmarks ($N_{\max} = 2{,}000$ nodes, $\lambda_{\max} = 0.50$ churn/week):
   $$H_{\mathrm{cap}} = \min\left(1 - \frac{\max N}{N_{\max}}, \; 1 - \frac{\max \lambda}{\lambda_{\max}}\right)$$

---

## 5. Scenario Parameters

- **Policy Hurdles:** $S_{\mathrm{floor}} \in \{500, 2{,}000\}$ AVAX, $S_{\mathrm{short}} \in \{10{,}000, 14{,}000, 20{,}000\}$ AVAX.
- **Curvature Exponents:** $p = 1.0$ (canonical linear harmonic), $p \in \{1.5, 2.0\}$ (nonlinear convex candidates).
- **Macroeconomic Stress Assumptions:** Asset price at $25 AVAX (baseline stress) and $15 AVAX (depressed valuation stress).

---

## 6. How to Reproduce Baseline Replay and Sweeps

### Run Tests:
```bash
python3 -m pytest tests/test_admission_simulation.py
```

### Run Baseline Replay & Sweep:
```bash
python3 research/scripts/run_stage4_simulation.py
```
Outputs are written to `research/data/stage4_exploratory_sweep_results.csv`.
