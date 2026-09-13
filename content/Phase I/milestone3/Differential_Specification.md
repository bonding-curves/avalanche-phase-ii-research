---
title: Differential Specification
---

> [!info] Historical source
> Imported from the pinned BCRG research repository. Source claims and dates are preserved, not revalidated. Navigation and Markdown formatting were migrated; original bytes are archived outside the site.


**Last Updated:** November 28, 2025
**Draft Stage:** 3rd Draft

# Avalanche Differential Specification and Protocol Architecture

This specification provides the mathematical framework for Avalanche's economic dynamics. For conceptual foundations, see [Systems Engineering Perspective](/Phase-I/milestone2/Avalanche-Economic-Model-A-Systems-Engineering-Perspective.md). For subsystem state variables and parameters, see [Subsystem Analysis](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md). Current network metrics are sourced from the [Data Snapshot](/Phase-I/data/snapshot-2025-11-28.md).

***

## 1. Overview

This differential specification characterizes how the Avalanche economic system evolves over time, providing a mathematical framework for understanding system dynamics that may be governable, environmental, relational, or mechanistic. The specification builds upon the [Avalanche Economic Network exploratory analysis](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md) developed in previous milestones and seeks to formalize the state dynamics and feedback loops inherent in the Avalanche network.

The Avalanche network represents a complex adaptive dynamical system where technical and economic components influence each other continuously. This creates distinct economic challenges and opportunities that require sophisticated control-theoretic understanding to navigate effectively. This specification provides formal and analytic contexts through which to analyze the unique architecture of the AVAX Token, the Primary Network, and application-specific Layer 1 blockchains (L1s).

Building on the [foundational economic concepts](/Phase-I/milestone1/Economic-Taxonomy.md) (Milestone 1) and [systems engineering perspective](/Phase-I/milestone2/Avalanche-Economic-Model-A-Systems-Engineering-Perspective.md) (Milestone 2), this differential specification provides a rigorous mathematical framework consisting of coupled differential equations that model the dynamic interactions between token supply, staking behavior, fee markets, and the L1 ecosystem. The specification transforms qualitative understanding into mathematical relationships, enabling systematic analysis of how financial and governance interfaces can impact network behavior.

***

## 2. Mathematical Framework

This section provides comprehensive reference tables for all variables, equations, and parameters used throughout the specification.

### 2.1 State Variables

| Variable                  | Units    | Subsystem    | Description                                 |
| ------------------------- | -------- | ------------ | ------------------------------------------- |
| total\_staked             | AVAX     | Staking      | Total AVAX locked in staking                |
| validator\_staked         | AVAX     | Staking      | AVAX staked directly by validators          |
| delegator\_staked         | AVAX     | Staking      | AVAX delegated to validators                |
| staking\_apr              | %        | Staking      | Current annualized staking return           |
| validator\_count          | Integer  | Staking      | Number of active validators                 |
| total\_supply             | AVAX     | Token Supply | Total minted AVAX (approaches MAX\_SUPPLY)  |
| circulating\_supply       | AVAX     | Token Supply | Liquid AVAX available for transactions      |
| locked\_supply            | AVAX     | Token Supply | AVAX locked in vesting or contracts         |
| cumulative\_burned        | AVAX     | Token Supply | Total AVAX permanently destroyed            |
| issuance\_rate            | AVAX/day | Token Supply | Rate of new AVAX creation                   |
| gas\_price                | nAVAX    | Fee Dynamics | Current price per unit gas                  |
| excess\_gas               | gas      | Fee Dynamics | Accumulated gas above target (drives price) |
| gas\_consumed             | gas/s    | Fee Dynamics | Current network gas consumption rate        |
| fee\_burn\_rate           | AVAX/day | Fee Dynamics | Rate of fee burning on Primary Network      |
| network\_utilization      | %        | Fee Dynamics | gas\_consumed / TARGET\_GAS\_RATE           |
| l1\_count                 | Integer  | L1 Ecosystem | Number of active L1 blockchains             |
| l1\_validator\_count      | Integer  | L1 Ecosystem | Total validators across all L1s             |
| l1\_fee\_burn\_rate       | AVAX/day | L1 Ecosystem | Rate of L1 fee burning                      |
| proposed\_acp\_count      | Integer  | Governance   | ACPs in proposed stage                      |
| implementable\_acp\_count | Integer  | Governance   | ACPs ready for implementation               |
| activated\_acp\_count     | Integer  | Governance   | ACPs successfully activated                 |
| stale\_acp\_count         | Integer  | Governance   | ACPs that became inactive                   |

For detailed subsystem decomposition, see the [Subsystem Analysis](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md).

### 2.2 Dynamic Functions

#### Staking Functions

| Function                        | Description                         | Specification                                                            |
| ------------------------------- | ----------------------------------- | ------------------------------------------------------------------------ |
| staking\_inflow()               | Rate of new AVAX entering staking   | See Section 4.1                                                          |
| unstaking\_outflow()            | Rate of AVAX leaving staking        | See Section 4.1                                                          |
| validator\_staking\_inflow()    | New validator stake deposits        | Validator portion of staking\_inflow()                                   |
| validator\_unstaking\_outflow() | Validator stake withdrawals         | Validator portion of unstaking\_outflow()                                |
| delegator\_staking\_inflow()    | New delegations                     | Delegator portion of staking\_inflow()                                   |
| delegator\_unstaking\_outflow() | Delegation withdrawals              | Delegator portion of unstaking\_outflow()                                |
| reward\_distribution()          | Total staking rewards per unit time | Protocol mechanism (Section 2.4)                                         |
| validator\_rewards()            | Rewards to validators               | reward\_distribution() × validator\_share                                |
| delegator\_rewards()            | Rewards to delegators               | reward\_distribution() × (1 - validator\_share) × (1 - COMMISSION\_RATE) |

For participant role analysis, see the [Participant Roles Taxonomy](/Phase-I/milestone1/Participant-Roles-Taxonomy.md).

#### Population Functions

| Function                 | Description            | Specification   |
| ------------------------ | ---------------------- | --------------- |
| validator\_entry\_rate() | New validators joining | See Section 4.1 |
| validator\_exit\_rate()  | Validators leaving     | See Section 4.1 |
| l1\_creation\_rate()     | New L1s deployed       | See Section 4.4 |
| l1\_abandonment\_rate()  | L1s discontinued       | See Section 4.4 |

#### Supply Functions

| Function               | Description                   | Specification      |
| ---------------------- | ----------------------------- | ------------------ |
| unlock\_rate()         | Vested tokens becoming liquid | Exogenous schedule |
| proposal\_rate()       | New ACPs submitted            | Community activity |
| implementation\_rate() | ACPs moving to activation     | Governance process |
| stale\_rate()          | ACPs becoming inactive        | Timeout mechanism  |

### 2.3 Differential Equations

The following equations define how state variables evolve over time.

#### Staking Dynamics

| Variable          | Law of Motion                                                                                                                              |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------------ |
| total\_staked     | d(total\_staked)/dt = staking\_inflow() − unstaking\_outflow() + AVG\_RESTAKE\_RATE × reward\_distribution()                               |
| validator\_staked | d(validator\_staked)/dt = validator\_staking\_inflow() − validator\_unstaking\_outflow() + VALIDATOR\_RESTAKE\_RATE × validator\_rewards() |
| delegator\_staked | d(delegator\_staked)/dt = delegator\_staking\_inflow() − delegator\_unstaking\_outflow() + DELEGATOR\_RESTAKE\_RATE × delegator\_rewards() |
| validator\_count  | d(validator\_count)/dt = validator\_entry\_rate() − validator\_exit\_rate()                                                                |

See the [Staking Dynamics subsystem analysis](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md#1-staking-dynamics-subsystem) for detailed state variable specifications.

#### Token Supply Dynamics

| Variable            | Law of Motion                                                                     |
| ------------------- | --------------------------------------------------------------------------------- |
| total\_supply       | d(total\_supply)/dt = issuance\_rate, subject to total\_supply ≤ MAX\_SUPPLY      |
| circulating\_supply | d(circulating\_supply)/dt = issuance\_rate − d(total\_staked)/dt + unlock\_rate() |
| cumulative\_burned  | d(cumulative\_burned)/dt = fee\_burn\_rate + l1\_fee\_burn\_rate                  |
| issuance\_rate      | issuance\_rate = reward\_distribution()                                           |

The burn mechanism is analyzed in the [Token Supply subsystem](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md#2-token-supply-subsystem) and [Economic Taxonomy](/Phase-I/milestone1/Economic-Taxonomy.md).

#### Fee Dynamics (ACP-103)

| Variable        | Law of Motion                                                                                                             |
| --------------- | ------------------------------------------------------------------------------------------------------------------------- |
| excess\_gas     | d(excess\_gas)/dt = gas\_consumed − TARGET\_GAS\_RATE                                                                     |
| gas\_price      | gas\_price = MIN\_GAS\_PRICE × exp(excess\_gas / FEE\_ADJUSTMENT\_CONSTANT)                                               |
| fee\_burn\_rate | fee\_burn\_rate = gas\_price × gas\_consumed                                                                              |
| gas\_consumed   | gas\_consumed = bytes × BANDWIDTH\_WEIGHT + reads × READ\_WEIGHT + writes × WRITE\_WEIGHT + compute\_us × COMPUTE\_WEIGHT |

These equations implement [ACP-103: Dynamic Fees](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/103-dynamic-fees.md). For context on the proposal, see our [ACP Summaries](/Phase-I/milestone2/ACP-Summaries.md).

#### L1 Ecosystem Dynamics (ACP-77)

| Variable             | Law of Motion                                                                                                          |
| -------------------- | ---------------------------------------------------------------------------------------------------------------------- |
| l1\_count            | d(l1\_count)/dt = l1\_creation\_rate() − l1\_abandonment\_rate()                                                       |
| l1\_fee\_burn\_rate  | l1\_fee\_burn\_rate = l1\_validator\_fee() × l1\_validator\_count                                                      |
| l1\_validator\_fee() | L1\_BASE\_FEE\_RATE × exp(max(0, l1\_validator\_count − TARGET\_L1\_VALIDATOR\_CAPACITY) / L1\_FEE\_SCALING\_CONSTANT) |

These equations implement [ACP-77: Reinventing Subnets](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/77-reinventing-subnets.md), which replaced one-time staking with continuous fees. See the [L1 Ecosystem subsystem analysis](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md#4-l1-ecosystem-subsystem).

#### Governance Dynamics

| Variable              | Law of Motion                                                                          |
| --------------------- | -------------------------------------------------------------------------------------- |
| proposed\_acp\_count  | d(proposed\_acp\_count)/dt = proposal\_rate() − implementation\_rate() − stale\_rate() |
| activated\_acp\_count | d(activated\_acp\_count)/dt = implementation\_rate()                                   |
| stale\_acp\_count     | d(stale\_acp\_count)/dt = stale\_rate()                                                |

For governance mechanism analysis, see the [Governance subsystem](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md#5-governance-subsystem) and [Mechanism Taxonomy](/Phase-I/milestone1/Mechanism-Taxonomy.md).

**Conservation Laws:**

* total\_staked = validator\_staked + delegator\_staked
* circulating\_supply + total\_staked + locked\_supply ≤ total\_supply

**Note on L1 Validators (Post-Etna):** Following [ACP-77](/Phase-I/milestone2/ACP-Summaries.md#acp-77) activation in December 2024, L1 validators are no longer required to validate the Primary Network. This decoupling removed the constraint `l1_validator_count ≤ validator_count` for modern L1s using the continuous fee model.

### 2.4 Parameters and Constants

#### Protocol Constants

| Parameter              | Value            | Description                      |
| ---------------------- | ---------------- | -------------------------------- |
| MAX\_SUPPLY            | 720,000,000 AVAX | Hard cap on total supply         |
| MIN\_VALIDATOR\_STAKE  | 2,000 AVAX       | Minimum to become validator      |
| MAX\_VALIDATOR\_STAKE  | 3,000,000 AVAX   | Maximum stake per validator      |
| MIN\_STAKE\_DURATION   | 14 days          | Minimum staking period           |
| MAX\_STAKE\_DURATION   | 365 days         | Maximum staking period           |
| MIN\_CONSUMPTION\_RATE | 10%              | Reward rate for minimum duration |
| MAX\_CONSUMPTION\_RATE | 12%              | Reward rate for maximum duration |
| MINTING\_PERIOD        | 365 days         | Annualization period             |

These parameters are defined in the [Avalanche Whitepaper](https://www.avalabs.org/whitepapers) and analyzed in our [Economic Taxonomy](/Phase-I/milestone1/Economic-Taxonomy.md).

#### Fee Mechanism Parameters (ACP-103)

| Parameter                 | Value        | Description                     |
| ------------------------- | ------------ | ------------------------------- |
| MIN\_GAS\_PRICE           | 1 nAVAX      | Floor price per gas unit        |
| FEE\_ADJUSTMENT\_CONSTANT | 2,164,043    | Controls price adjustment speed |
| TARGET\_GAS\_RATE         | 50,000 gas/s | Equilibrium utilization target  |
| BANDWIDTH\_WEIGHT         | 1            | Gas per byte                    |
| READ\_WEIGHT              | 1,000        | Gas per state read              |
| WRITE\_WEIGHT             | 1,000        | Gas per state write             |
| COMPUTE\_WEIGHT           | 4            | Gas per microsecond             |

Source: [ACP-103 specification](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/103-dynamic-fees.md). The multidimensional approach follows similar principles to Ethereum's [EIP-1559](https://eips.ethereum.org/EIPS/eip-1559).

#### L1 Fee Parameters (ACP-77)

| Parameter                       | Value         | Description                     |
| ------------------------------- | ------------- | ------------------------------- |
| L1\_BASE\_FEE\_RATE             | 512 nAVAX/s   | Base rate ≈ 1.33 AVAX/month     |
| L1\_FEE\_SCALING\_CONSTANT      | 1,246,488,515 | Controls fee escalation         |
| TARGET\_L1\_VALIDATOR\_CAPACITY | 10,000        | Threshold before fee escalation |

Source: [ACP-77 specification](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/77-reinventing-subnets.md).

#### Behavioral Parameters

| Parameter                | Value | Description                           |
| ------------------------ | ----- | ------------------------------------- |
| VALIDATOR\_RESTAKE\_RATE | 70%   | Validator reward re-staking           |
| DELEGATOR\_RESTAKE\_RATE | 50%   | Delegator reward re-staking           |
| AVG\_RESTAKE\_RATE       | 67%   | Weighted average                      |
| COMMISSION\_RATE         | 2-20% | Validator fee on delegator rewards    |
| STAKING\_SENSITIVITY     | 0.1   | Response strength to APR differential |
| OPPORTUNITY\_COST        | 5%    | External yield benchmark              |

For analysis of how external conditions affect these parameters, see [Avalanche Economy relative to the Open Economy](/Phase-I/milestone1/Avalanche-Economy-relative-to-the-Open-Economy.md).

#### Derived Formulas

**Effective Consumption Rate** (duration-dependent reward multiplier):

```
effective_consumption_rate(duration) = MIN_CONSUMPTION_RATE +
    (MAX_CONSUMPTION_RATE - MIN_CONSUMPTION_RATE) ×
    (duration - MIN_STAKE_DURATION) / (MAX_STAKE_DURATION - MIN_STAKE_DURATION)
```

**Reward Distribution** (official Avalanche formula):

```
reward_distribution() = (MAX_SUPPLY - total_supply) ×
    (total_staked / total_supply) ×
    (avg_stake_duration / MINTING_PERIOD) ×
    effective_consumption_rate(avg_stake_duration)
```

**Staking APR**:

```
staking_apr = (reward_distribution() / total_staked) × 365
```

### 2.5 Subsystem Coupling Matrix

This matrix shows direct dependencies between subsystems. For the full multigraph model, see [Subsystem Analysis and MultiGraph](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md).

| Source ↓ / Target → | Staking                                      | Token Supply                   | Fee Dynamics                  | L1 Ecosystem                            | Governance            |
| ------------------- | -------------------------------------------- | ------------------------------ | ----------------------------- | --------------------------------------- | --------------------- |
| **Staking**         | —                                            | issuance\_rate ∝ total\_staked | staking\_apr affected by fees | l1\_validator\_count ≤ validator\_count | Stake-weighted voting |
| **Token Supply**    | staking\_apr ∝ (MAX\_SUPPLY - total\_supply) | —                              | —                             | —                                       | —                     |
| **Fee Dynamics**    | Real APR = staking\_apr - fee\_impact        | cumulative\_burned ↑           | —                             | Combined burn rate                      | Fee parameter changes |
| **L1 Ecosystem**    | Validator capacity demand                    | l1\_fee\_burn\_rate            | L1 transaction volume         | —                                       | L1 track proposals    |
| **Governance**      | MIN\_VALIDATOR\_STAKE, durations             | Consumption rates              | Fee parameters                | L1 fee parameters                       | —                     |

**Primary Feedback Loops:**

| Loop              | Type        | Mechanism                                         | Key Variables                     |
| ----------------- | ----------- | ------------------------------------------------- | --------------------------------- |
| Staking Dilution  | Balancing   | staking\_apr ↓ as total\_staked ↑                 | total\_staked, staking\_apr       |
| Fee Burning       | Reinforcing | Activity ↑ → Burns ↑ → Scarcity ↑ → Value ↑       | gas\_consumed, cumulative\_burned |
| Supply Exhaustion | Balancing   | issuance\_rate → 0 as total\_supply → MAX\_SUPPLY | total\_supply, issuance\_rate     |
| L1 Growth         | Reinforcing | l1\_count ↑ → Activity ↑ → Value ↑ → l1\_count ↑  | l1\_count, l1\_fee\_burn\_rate    |

### 2.6 System Architecture

![Avalanche Differential Specification System Architecture](/Phase-I/milestone3/diff-spec.png)

***

## 3. Component Specification

This section classifies system components by their nature and controllability. For the full component taxonomy, see [Mechanism Taxonomy](/Phase-I/milestone1/Mechanism-Taxonomy.md).

### 3.1 Environmental Processes

External forces modeled as exogenous inputs. These drive the system but are not controlled by the protocol.

| Process             | Description               | Primary Effects                             |
| ------------------- | ------------------------- | ------------------------------------------- |
| transaction\_volume | Demand for block space    | gas\_consumed, fee\_burn\_rate              |
| market\_conditions  | AVAX price, sentiment     | staking\_inflow(), validator\_entry\_rate() |
| l1\_demand          | Developer interest in L1s | l1\_creation\_rate()                        |
| macro\_rates        | External interest rates   | OPPORTUNITY\_COST benchmark                 |
| cross\_chain\_flows | Bridge activity           | circulating\_supply pressure                |

For analysis of external economic forces, see [Avalanche Economy relative to the Open Economy](/Phase-I/milestone1/Avalanche-Economy-relative-to-the-Open-Economy.md).

### 3.2 Behavioral Processes

Participant responses to system state. These are endogenous but not directly controlled.

| Behavior                | Agent           | Response Function                                                |
| ----------------------- | --------------- | ---------------------------------------------------------------- |
| Staking decision        | Token holders   | staking\_inflow() responds to (staking\_apr - OPPORTUNITY\_COST) |
| Validator participation | Node operators  | validator\_entry\_rate() responds to profitability               |
| Delegation choice       | Passive stakers | Selects validators by performance and commission                 |
| L1 development          | Builders        | l1\_creation\_rate() responds to L1 economics                    |
| Fee bidding             | Users           | Transaction timing based on gas\_price                           |

For detailed participant analysis, see [Participant Roles Taxonomy](/Phase-I/milestone1/Participant-Roles-Taxonomy.md).

### 3.3 Controlled Mechanisms

Protocol-level controls that can be adjusted through governance.

| Control            | Mechanism                                            | Governance Path    |
| ------------------ | ---------------------------------------------------- | ------------------ |
| Inflation policy   | effective\_consumption\_rate bounds                  | Standard Track ACP |
| Fee adjustment     | FEE\_ADJUSTMENT\_CONSTANT, TARGET\_GAS\_RATE         | Standard Track ACP |
| L1 fees            | L1\_BASE\_FEE\_RATE, TARGET\_L1\_VALIDATOR\_CAPACITY | Standard Track ACP |
| Stake requirements | MIN\_VALIDATOR\_STAKE, duration bounds               | Standard Track ACP |
| Reward formula     | reward\_distribution() parameters                    | Standard Track ACP |

For the full ACP process and recent proposals, see [ACP Summaries](/Phase-I/milestone2/ACP-Summaries.md).

***

## 4. System Dynamics

This section explains how each subsystem evolves and specifies the behavioral response functions.

### 4.1 Staking Dynamics

The staking subsystem governs AVAX flow between liquid and staked states. For subsystem details, see [Staking Dynamics](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md#1-staking-dynamics-subsystem).

**Behavioral Response Functions:**

Staking inflow responds to the APR differential using a bounded sigmoid:

```
staking_inflow() = STAKING_SENSITIVITY × circulating_supply ×
    max(0, tanh(staking_apr - OPPORTUNITY_COST))
```

Unstaking outflow increases when opportunity cost exceeds staking returns:

```
unstaking_outflow() = STAKING_SENSITIVITY × total_staked ×
    max(0, tanh(OPPORTUNITY_COST - staking_apr))
```

Validator entry depends on expected profitability:

```
validator_profit = (validator_rewards() / validator_count) - operational_cost
validator_entry_rate() = base_entry × max(0, tanh(validator_profit / threshold))
```

Validator exit accelerates when profitability becomes negative:

```
validator_exit_rate() = base_exit × max(0, tanh(-validator_profit / threshold))
```

**Equilibrium Behavior:**

At equilibrium, net stake change is zero. The system finds a staking ratio where:

* staking\_apr ≈ OPPORTUNITY\_COST (adjusted for risk premium)
* Validator profitability covers operational costs
* Target range: 50-60% of circulating\_supply staked

**Stability:** The staking system is self-correcting. Higher staking dilutes staking\_apr, reducing incentives and allowing the ratio to stabilize.

### 4.2 Token Supply Dynamics

The token supply subsystem tracks AVAX creation and destruction. For subsystem details, see [Token Supply](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md#2-token-supply-subsystem).

**Supply Evolution:**

Total supply grows via staking rewards but is hard-capped:

```
d(total_supply)/dt = issuance_rate    if total_supply < MAX_SUPPLY
d(total_supply)/dt = 0                 if total_supply = MAX_SUPPLY
```

As total\_supply approaches MAX\_SUPPLY, the factor (MAX\_SUPPLY - total\_supply) in reward\_distribution() naturally reduces issuance toward zero.

**Circulating Supply:**

Circulating supply is squeezed between issuance (increasing) and staking (decreasing):

```
circulating_supply = total_supply - total_staked - locked_supply
```

**Deflationary Crossover:**

The network becomes net deflationary when:

```
fee_burn_rate + l1_fee_burn_rate > issuance_rate
```

Current state (November 2025): \~1,500 AVAX/day burned vs \~49,000 AVAX/day issued. Crossover requires \~33× increase in fee activity, or equivalent issuance reduction as total\_supply approaches MAX\_SUPPLY. Note: Burn rates have tripled during 2025, indicating positive momentum toward sustainability.

### 4.3 Fee Market Dynamics

The fee subsystem implements [ACP-103](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/103-dynamic-fees.md) congestion pricing. For subsystem details, see [Fee Dynamics](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md#3-fee-dynamics-subsystem).

**Excess Gas Accumulator:**

The key insight is that gas\_price depends on cumulative excess utilization:

```
d(excess_gas)/dt = gas_consumed - TARGET_GAS_RATE
```

When gas\_consumed > TARGET\_GAS\_RATE, excess\_gas accumulates, driving prices up. When gas\_consumed < TARGET\_GAS\_RATE, excess\_gas drains, and prices fall.

**Exponential Price Adjustment:**

The exponential mechanism provides:

* **Floor guarantee**: gas\_price ≥ MIN\_GAS\_PRICE always
* **Rapid congestion response**: Prices rise exponentially under sustained load
* **Smooth decay**: Prices return gradually to baseline

This mechanism is similar to [EIP-1559](https://eips.ethereum.org/EIPS/eip-1559) but extended to multiple resource dimensions.

**Dynamic Gas Limits (ACP-176):** The Octane upgrade (April 2025) introduced validator-driven adjustment of TARGET\_GAS\_RATE via [ACP-176](/Phase-I/milestone2/ACP-Summaries.md#acp-176). Block builders signal preferred target, and the network converges where 50% of stake weight wants increase vs. decrease. This enables market-discovered capacity rather than centrally-planned limits.

**Multidimensional Gas:**

ACP-103 prices four resource dimensions independently:

* Bandwidth: bytes transmitted
* State reads: storage lookups
* State writes: storage modifications
* Compute: execution time

This ensures resource-heavy transactions pay proportionally, preventing resource exhaustion attacks.

### 4.4 L1 Ecosystem Dynamics

The L1 subsystem tracks application-specific blockchain activity under [ACP-77](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/77-reinventing-subnets.md). For subsystem details, see [L1 Ecosystem](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md#4-l1-ecosystem-subsystem).

**L1 Lifecycle Functions:**

L1 creation responds to economic viability:

```
l1_creation_rate() = base_creation × demand_factor × exp(-l1_validator_fee() / fee_threshold)
```

L1 abandonment increases when fees exceed value:

```
l1_abandonment_rate() = base_abandonment × max(0, l1_validator_fee() - l1_revenue) / l1_revenue
```

**Continuous Fee Mechanism:**

ACP-77 replaces one-time stake with continuous fees:

* Base rate: L1\_BASE\_FEE\_RATE ≈ 1.33 AVAX/month per validator
* Escalation: Fees increase exponentially when l1\_validator\_count exceeds TARGET\_L1\_VALIDATOR\_CAPACITY

This right-sizes the validator set to actual L1 demand.

**Validator Architecture (Post-Etna):**

Following [ACP-77](/Phase-I/milestone2/ACP-Summaries.md#acp-77), L1 validators operate independently of Primary Network validation. Modern L1s define their own validator sets through smart contract-based validator managers, enabling:

* Custom staking requirements (PoA, PoS, or hybrid)
* Reduced hardware requirements (only P-Chain sync needed)
* Full economic sovereignty

Legacy L1s (pre-Etna) still require Primary Network validation.

### 4.5 Governance Dynamics

The governance subsystem manages protocol evolution through ACPs. For subsystem details, see [Governance](/Phase-I/milestone2/Subsystem_Analysis_and_MultiGraph.md#5-governance-subsystem) and [ACP Summaries](/Phase-I/milestone2/ACP-Summaries.md).

**Proposal Flow:**

```
Proposed → Implementable → Activated
    ↓
  Stale
```

**Hysteresis Constraints:**

To prevent destabilizing oscillations, parameter changes are rate-limited:

* Minimum interval between changes to the same parameter
* Maximum change magnitude per governance cycle
* Cooldown periods after significant changes

These constraints ensure the system has time to equilibrate between adjustments.

***

## 5. Equilibrium and Stability Analysis

This section analyzes system equilibria and stability properties. For hypothesis testing approaches, see [Economic Hypotheses](/Phase-I/milestone4/economic_hypotheses.md).

### 5.1 Staking Equilibrium

At equilibrium, d(total\_staked)/dt = 0:

```
staking_inflow() + AVG_RESTAKE_RATE × reward_distribution() = unstaking_outflow()
```

This occurs when staking\_apr balances against OPPORTUNITY\_COST. The equilibrium staking ratio depends on:

* External yield environment (OPPORTUNITY\_COST)
* Protocol reward parameters (consumption rates)
* Risk premium demanded by stakers

**Target Range:** 50-60% of circulating\_supply staked

* Below 50%: Security concerns (insufficient economic security)
* Above 60%: Liquidity concerns (insufficient tokens for network utility)

**Stability Analysis:** The staking system exhibits strong negative feedback. Perturbations self-correct:

* If total\_staked increases → staking\_apr decreases → staking\_inflow() decreases → system returns to equilibrium

### 5.2 Fee Market Equilibrium

At equilibrium, d(excess\_gas)/dt = 0:

```
gas_consumed = TARGET_GAS_RATE
excess_gas = 0
gas_price = MIN_GAS_PRICE
```

The fee market is stable for reasonable demand patterns. The exponential mechanism provides strong restoring force:

* Congestion → Higher prices → Reduced demand → Return to target
* Low demand → Lower prices (bounded by MIN\_GAS\_PRICE) → Increased demand → Return to target

### 5.3 Supply Equilibrium

**Long-term Trajectory:**

As total\_supply → MAX\_SUPPLY:

```
reward_distribution() → 0
issuance_rate → 0
```

The system transitions to a purely deflationary regime where:

* d(total\_supply)/dt = 0
* d(cumulative\_burned)/dt = fee\_burn\_rate + l1\_fee\_burn\_rate > 0
* circulating\_supply gradually decreases

**Sustainability Requirement:**

For long-term validator incentives post-issuance, fee revenue must cover costs:

```
(fee_burn_rate + l1_fee_burn_rate) × validator_share ≥ validator_count × operational_cost
```

### 5.4 System-Wide Stability Properties

1. **Boundedness:** All state variables are bounded
   * total\_supply ≤ MAX\_SUPPLY
   * total\_staked ≤ total\_supply
   * gas\_price ≥ MIN\_GAS\_PRICE (no upper bound, but demand-limited)

2. **Negative Feedback Dominance:** Primary loops are balancing
   * Staking-APR loop prevents runaway staking
   * Fee-demand loop prevents sustained congestion

3. **Conservation Laws:** Provide consistency constraints
   * Token accounting: circulating\_supply + total\_staked + locked\_supply ≤ total\_supply
   * Stake accounting: total\_staked = validator\_staked + delegator\_staked

4. **Governance Hysteresis:** Prevents rapid oscillations
   * Rate limits on parameter changes
   * Minimum intervals between adjustments

***

## 6. Performance Indicators

| Category      | Indicator               | Formula                                                                  | Target                |
| ------------- | ----------------------- | ------------------------------------------------------------------------ | --------------------- |
| **Security**  | Staking ratio           | total\_staked / circulating\_supply                                      | 50-60%                |
| **Security**  | Validator count         | validator\_count                                                         | >1,000                |
| **Security**  | Stake decentralization  | 1 - HHI(validator\_stakes)                                               | >0.99                 |
| **Economic**  | Net inflation           | (issuance\_rate - fee\_burn\_rate - l1\_fee\_burn\_rate) / total\_supply | Decreasing            |
| **Economic**  | Burn ratio              | (fee\_burn\_rate + l1\_fee\_burn\_rate) / issuance\_rate                 | Increasing toward 1.0 |
| **Economic**  | Validator profitability | validator\_rewards() / validator\_count - costs                          | >0                    |
| **Stability** | APR variance            | Var(staking\_apr) over time                                              | Low                   |
| **Stability** | Fee market efficiency   | Corr(gas\_consumed, gas\_price)                                          | High                  |
| **Growth**    | L1 adoption             | d(l1\_count)/dt                                                          | Positive              |
| **Growth**    | Network utilization     | gas\_consumed / TARGET\_GAS\_RATE                                        | 0.8-1.2               |

For detailed hypothesis testing on these indicators, see [Economic Hypotheses](/Phase-I/milestone4/economic_hypotheses.md).

***

## 7. Insights into the Avalanche Economy

### 7.1 Security

The validator subsystem achieves security through economic incentives rather than pure altruism. The reward\_distribution() mechanism creates wealth-gaining opportunities for honest behavior, while slashing (not modeled here) creates wealth-reducing consequences for faults.

**Key insight:** The staking\_apr must exceed OPPORTUNITY\_COST by a sufficient risk premium to attract the target 50-60% staking ratio. If external yields rise significantly, governance may need to adjust consumption rates to maintain security.

**Relevant equations:** staking\_inflow(), validator\_entry\_rate(), staking\_apr calculation

For participant incentive analysis, see [Participant Roles Taxonomy](/Phase-I/milestone1/Participant-Roles-Taxonomy.md).

### 7.2 Sustainability

Long-term sustainability requires the system to function as issuance\_rate approaches zero. The transition path depends on fee activity growth:

**Current state (November 2025):** Burn ratio ≈ 3% (1,500/49,000 AVAX/day)
**Required for balance:** Burn ratio = 100%
**Path:** \~33× increase in fee activity, OR natural issuance reduction as total\_supply → MAX\_SUPPLY
**Positive signal:** Burn rate tripled during 2025 (from \~500 to \~1,500 AVAX/day)

The fee\_burn\_rate + l1\_fee\_burn\_rate must eventually sustain validator economics without inflation subsidies.

**Relevant equations:** reward\_distribution() decay, fee\_burn\_rate, l1\_fee\_burn\_rate

### 7.3 Value Creation

The L1 ecosystem serves as the primary value creation engine. Each L1 represents real economic activity that:

* Generates l1\_fee\_burn\_rate (deflationary pressure)
* Demands l1\_validator\_count (security load)
* Creates utility that attracts users to the broader ecosystem

**Key insight:** The [ACP-77](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/77-reinventing-subnets.md) continuous fee mechanism aligns L1 incentives with network health. L1s that generate value can sustain fees; those that don't will naturally sunset.

**Relevant equations:** l1\_creation\_rate(), l1\_fee\_burn\_rate, l1\_validator\_fee()

### 7.4 Stability

The system achieves stability through multiple mechanisms:

1. **Automatic stabilizers:** The exponential fee mechanism (gas\_price equation) and diminishing reward formula (reward\_distribution()) provide automatic correction.

2. **Governance levers:** Parameters like FEE\_ADJUSTMENT\_CONSTANT, TARGET\_GAS\_RATE, and consumption rates allow adaptive response to changing conditions.

3. **Hysteresis:** Rate limits on governance changes prevent overcorrection and oscillation.

**Key insight:** The coupling matrix (Section 2.5) reveals that Fee Dynamics affects all other subsystems. Fee parameter changes require careful analysis of cross-subsystem impacts.

For external stability factors, see [Avalanche Economy relative to the Open Economy](/Phase-I/milestone1/Avalanche-Economy-relative-to-the-Open-Economy.md).

***

## 8. Conclusion

This differential specification provides the mathematical foundation for understanding Avalanche's economic dynamics. Key findings:

1. **Staking equilibrium** naturally stabilizes around 50-60% when staking\_apr balances external opportunity costs. The tanh-bounded behavioral functions ensure stable convergence.

2. **Fee markets** self-regulate through the exponential mechanism. The excess\_gas accumulator provides memory that smooths price adjustments.

3. **Supply trajectory** is well-defined: issuance\_rate decays as total\_supply approaches MAX\_SUPPLY, transitioning the network from inflationary to deflationary.

4. **L1 economics** under [ACP-77](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/77-reinventing-subnets.md) create sustainable value capture through continuous fees rather than one-time stakes.

5. **Cross-subsystem coupling** is manageable. The primary feedback loops are balancing (self-correcting), and governance hysteresis prevents destabilizing oscillations.

The framework enables:

* **Simulation:** All equations can be implemented in modeling tools ([cadCAD](https://cadcad.org), [radCAD](https://github.com/CADLabs/radCAD))
* **Prediction:** Trajectory analysis under different scenarios
* **Optimization:** Parameter tuning for specific objectives
* **Monitoring:** Real-time health assessment via performance indicators

Future work should extend this specification to include:

* Slashing dynamics and their deterrent effects
* Cross-chain bridge flows and their impact on circulating\_supply
* Detailed validator operational cost models
* Agent-based simulation validation

For the complete research context, see the [Project Overview](/Phase-I/about/Project-Proposal.md).

***

## References

\[1] Avalanche Platform. (2020). [Avalanche Whitepaper](https://www.avalabs.org/whitepapers).

\[2] Avalanche Foundation. [ACP-103: Dynamic Fees](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/103-dynamic-fees.md). Avalanche Community Proposals.

\[3] Avalanche Foundation. [ACP-77: Reinventing Subnets](https://github.com/avalanche-foundation/ACPs/blob/main/ACPs/77-reinventing-subnets.md). Avalanche Community Proposals.

\[4] Buterin, V. et al. (2021). [EIP-1559: Fee Market Change](https://eips.ethereum.org/EIPS/eip-1559). Ethereum Improvement Proposals.

\[5] BlockScience. [cadCAD: Computer-Aided Design for Complex Systems](https://cadcad.org).

\[6] CADLabs. [Ethereum Economic Model](https://github.com/CADLabs/ethereum-economic-model). A cadCAD model for Ethereum's economic system.

\[7] Ogata, K. (2010). Modern Control Engineering. Prentice Hall.

\[8] Astrom, K. J., & Murray, R. M. (2021). [Feedback Systems: An Introduction for Scientists and Engineers](https://www.cds.caltech.edu/~murray/amwiki/index.php/Main_Page). Princeton University Press.
