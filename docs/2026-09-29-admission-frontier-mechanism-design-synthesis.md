# Technical Specification & Architectural Synthesis: The Consensus Admission Frontier ($S_{\min}(d)$)

| Metadata | Value |
| :--- | :--- |
| **Document ID** | SPEC-2026-09-ADMISSION-SYNTHESIS |
| **Revision** | Rev 1.0 (Formal Mechanism Design, Trade-offs & Epistemic Boundaries) |
| **Status** | WORKING RESEARCH SYNTHESIS |
| **Methodology** | Algorithmic Mechanism Design, Systems Engineering (Buede / NASA SP-2016-6105 Rev 2) |
| **Target Subsystem** | Avalanche Primary Network Consensus Verification (`vms/platformvm`) |
| **Target Review** | Avalanche Foundation Strategic Architecture Review (October 2026) |
| **Author(s)** | BCRG Research Lane |

---

## 1. Executive Summary: The "Bouncer" Mechanism

This specification provides an independent, end-to-end audit of the **Duration-Dependent Admission Frontier ($S_{\min}(d)$)** proposed for the Avalanche Primary Network.

### 1.1 What the Mechanism Is
The admission frontier is fundamentally **the bouncer at the protocol door**. It is a deterministic, state-validation rule inside `vms/platformvm` that evaluates every incoming validator transaction (`AddPermissionlessValidatorTx`):

$$\text{Admit}(S, d) = \begin{cases} 1, & \text{if } S \ge S_{\min}(d) \\ 0, & \text{if } S < S_{\min}(d) \end{cases}$$

It does **not** distribute staking rewards; it does **not** pay out subsidies; and it does **not** steer macro duration through psychological APY incentives. Its sole operational responsibility is to enforce an entrance condition: **if an operator demands short-duration liquidity (e.g., 48 hours for ETF redemption facilities), they must post a substantial capital anchor ($S_{\text{short}}$) so that consensus security is never compromised.**

---

## 2. Hard Protocol Constraints `[Protocol Ground Truth]`

Any viable admission mechanism must operate strictly within the non-negotiable physical constraints of the Avalanche consensus engine:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   HARD CONSENSUS CONSTRAINTS (PLATFORMVM)              │
├──────────────────────────┬──────────────────────┬──────────────────────┤
│ Constraint               │ Consensus Rule       │ Operational Reality  │
├──────────────────────────┼──────────────────────┼──────────────────────┤
│ 1. Duration Limits       │ d in [d_min, d_max]  │ d_min = 48h (ACP-273)│
│                          │                      │ d_max = 365d (Code)  │
├──────────────────────────┼──────────────────────┼──────────────────────┤
│ 2. Delegator Firewall    │ d_del >= 14d AND     │ Stakers < 14d get    │
│                          │ d_del <= d_val       │ 0% delegations       │
├──────────────────────────┼──────────────────────┼──────────────────────┤
│ 3. Integer Arithmetic    │ Atomic nAVAX &       │ Zero floating-point  │
│                          │ Nanoseconds          │ drift across CPUs    │
├──────────────────────────┼──────────────────────┼──────────────────────┤
│ 4. Weight Cap            │ W_i <= W_max         │ Max stake weight cap │
│                          │                      │ (3,000,000 AVAX)     │
└──────────────────────────┴──────────────────────┴──────────────────────┘
```

### 2.1 The 14-Day Delegator Firewall Invariant
The single most critical structural feature of the protocol is the **Delegator Firewall**:
* **ACP-273** lowered the minimum *validator* self-stake tenure to $d_{\min} = 48\text{ hours}$.
* **ACP-273 left delegators untouched:** $d_{\text{delegator}} \ge 14\text{ days}$.
* PlatformVM strictly enforces:
  $$d_{\text{delegator}} \le d_{\text{validator}}$$

**The Consequence:** Any validator operating in the sub-14-day window ($d < 14\text{ days}$) **cannot receive any delegated capital**. They must supply $100\%$ of their consensus weight from their own balance sheet. Over $97\%$ of network staked capital is tied to delegations and liquid staking contracts (e.g. BENQI). Therefore, the sub-14-day window is physically quarantined to solo, proprietary capital.

---

## 3. Core System Objectives: Why the Mechanism Exists

The admission frontier is designed to achieve exactly three protocol objectives:

### Objective 1: Short-Duration Sybil Parity
* **The Vulnerability:** If minimum self-stake is reduced (e.g. toward $S_{\text{floor}}$) while minimum duration is reduced to $d_{\min} = 48\text{ hours}$ as uncoupled static numbers, an attacker can register a consensus slot with $K_{\text{decoupled}} = S_{\text{floor}} \cdot d_{\min}$. This causes a severe collapse in capital-time commitment relative to the historical baseline ($K_{\text{baseline}} \equiv S_{\text{baseline}} \cdot d_{\text{baseline}}$), allowing an attacker to operate dozens of consensus identities for the historical cost of one.
* **The Objective:** Enforce that at minimum tenure, total capital-time commitment preserves or exceeds historical parity:
  $$K(d_{\min}) = S_{\min}(d_{\min}) \cdot d_{\min} \ge K_{\text{baseline}}$$

### Objective 2: Retail Entry Relief at Maximum Commitment
* **The Problem:** The legacy static entry barrier ($S_{\text{baseline}}$) forces all validators—even those locking capital for a full year—to post the same high capital threshold, creating an unnecessary barrier for sovereign, independent node operators.
* **The Objective:** Allow operators committing for the maximum annual tenure ($d_{\max} = 365\text{ days}$) to access a reduced capital threshold:
  $$\lim_{d \to d_{\max}} S_{\min}(d) = S_{\text{floor}} < S_{\text{baseline}}$$

### Objective 3: Off-Peak State Churn Defense
* **The Problem:** When network transaction fees are at their minimum floor ($g(t) \to g_{\min}$), transaction gas costs provide zero economic friction against bot-driven identity spinning.
* **The Objective:** Impose an unconditional capital opportunity cost on short-duration slots by requiring $S_{\text{short}}$ at $d_{\min}$, ensuring that high-frequency key registration and expiration is economically restrained even when transaction fees are negligible.

---

## 4. The 2 Bouncer KPIs: How to Verify Effectiveness

Because the admission frontier is a bouncer and not an economic incentive program, its performance is measured by **two operational pass/fail criteria**:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   THE 2 CANONICAL BOUNCER KPIS                         │
├───────┬──────────────────────────┬──────────────────────┬──────────────┤
│ KPI   │ Operational Question     │ Formal Metric Target │ Failure Mode │
├───────┼──────────────────────────┼──────────────────────┼──────────────┤
│ KPI 1 │ Did anyone enter 48h     │ Count(d < 14d AND    │ Subsidized   │
│       │ slots with cheap stake?  │       S < S_short)   │ 48h Sybil    │
│       │                          │       == 0           │ Attack       │
├───────┼──────────────────────────┼──────────────────────┼──────────────┤
│ KPI 2 │ Did we stop rapid churn  │ N_churn(off-peak)    │ High-Freq    │
│       │ when gas fees are zero?  │ <= N_baseline        │ State Spam   │
└───────┴──────────────────────────┴──────────────────────┴──────────────┘
```

* **Why Seat Decentralization ($\text{HHI}$) Was Dropped as a Goal:**  
  Independent small nodes (<6,000 AVAX) represent less than 1% to 2.8% of total consensus capital. In Snowman's stake-weighted consensus sampling, their voting weight is near-zero. Raising entry barriers on short durations does not harm consensus security; it protects the network from ephemeral churn. Small nodes are monitored as a safety check, not as an optimization target for the bouncer.

---

## 5. Required Mathematical Properties of $S_{\min}(d)$

To function as a predictable, non-exploitable protocol gate, any candidate curve $S(d)$ must strictly satisfy four calculus and boundary properties:

1. **Strict Monotonic Decay:**
   $$\frac{d S_{\min}(d)}{dd} < 0 \quad \forall d \in [d_{\min}, d_{\max}]$$
   *Meaning:* Extending duration must always reduce or maintain the required self-stake. No paradoxical ranges where committing longer requires more capital.

2. **Strict Convexity:**
   $$\frac{d^2 S_{\min}(d)}{dd^2} > 0 \quad \forall d \in [d_{\min}, d_{\max}]$$
   *Meaning:* The discount rate $\left|\frac{dS}{dd}\right|$ is steepest at short durations (penalizing transient membership) and smoothly flattens out as tenors extend toward long-term horizons.

3. **Exact Boundary Interpolation:**
   $$S_{\min}(d_{\min}) = S_{\text{short}}, \quad S_{\min}(d_{\max}) = S_{\text{floor}}$$
   *Meaning:* The curve must connect the starting anchor and terminal floor identically, with zero asymptotic overshoot or artificial cliff truncations.

4. **Low Parameter Complexity:**
   The formula must contain at most $2\text{--}3$ tunable parameters ($\Theta = \{S_{\text{short}}, S_{\text{floor}}, p\}$) to ensure governance transparency and avoid overfitting.

---

## 6. Audit of Candidate Functional Curve Families

Four distinct mathematical functional families were evaluated against these required properties:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   CANDIDATE CURVE FAMILIES AUDIT                       │
├───────────────────┬────────────────────────────────────────────────────┤
│ Family            │ Mathematical Formulation                           │
├───────────────────┼────────────────────────────────────────────────────┤
│ 1. Pure           │ S_1(d) = max( S_floor,  K_baseline / d )           │
│    Iso-Commitment │                                                    │
├───────────────────┼────────────────────────────────────────────────────┤
│ 2. Standard       │ S_2(d) = S_floor + (S_short - S_floor) /           │
│    Hyperbolic     │                  [ 1 + alpha * (d - d_min) ]       │
├───────────────────┼────────────────────────────────────────────────────┤
│ 3. Generalized    │ S_3(d) = S_floor + (S_short - S_floor) *           │
│    Power-Law      │                  [ (d_max - d) / (d_max - d_min) ]^p│
├───────────────────┼────────────────────────────────────────────────────┤
│ 4. Bounded        │ S_4(d) = S_floor + (S_short - S_floor) *           │
│    Harmonic       │        [ (1/d - 1/d_max) / (1/d_min - 1/d_max) ]^p │
└───────────────────┴────────────────────────────────────────────────────┘
```

### 6.1 Family 1: Pure Iso-Commitment
* **Formula:** $S_1(d) = \max\left(S_{\text{floor}}, \frac{K_{\text{baseline}}}{d}\right)$
* **Calculus Audit:**
  - Satisfies monotonicity $\frac{dS}{dd} \le 0$.
  - Fails strict convexity: it hits the floor $S_{\text{floor}}$ at an early cutoff duration ($d_{\text{clamp}} = K_{\text{baseline}} / S_{\text{floor}}$).
* **The Fatal Flaw:** For all durations beyond $d_{\text{clamp}}$ (which represents over $80\%$ of the allowable domain $[d_{\min}, d_{\max}]$), the curve is completely flat:
  $$S_1(d) = S_{\text{floor}} \quad \forall d \ge d_{\text{clamp}}$$
  There is zero capital incentive to commit for 180 days or 365 days versus 60 days.
* **Verdict:** **REJECTED**.

### 6.2 Family 2: Standard Hyperbolic Decay
* **Formula:** $S_2(d) = S_{\text{floor}} + \frac{S_{\text{short}} - S_{\text{floor}}}{1 + \alpha (d - d_{\min})}$
* **Calculus Audit:**
  - Satisfies monotonicity and strict convexity.
  - Boundary check at $d = d_{\min}$: $S(d_{\min}) = S_{\text{short}}$ (Exact).
  - Boundary check at $d = d_{\max}$:
    $$S(d_{\max}) = S_{\text{floor}} + \frac{S_{\text{short}} - S_{\text{floor}}}{1 + \alpha (d_{\max} - d_{\min})}$$
* **The Fatal Flaw (The Heavy Tail):**  
  As shown by asymptotic scaling analysis, the hyperbolic term decays as an algebraic $O(1/d)$ tail. Because $d_{\max} = 365$ is a finite integer (not infinity), this tail does **not** vanish. If $\alpha$ is calibrated to provide reasonable relief at intermediate durations, the curve overshoots $S_{\text{floor}}$ at 365 days by over $50\%$. Clamping it to $S_{\text{floor}}$ requires an artificial discontinuity cliff.
* **Verdict:** **REJECTED**.

### 6.3 Family 3: Generalized Power-Law Decay
* **Formula:** $S_3(d) = S_{\text{floor}} + (S_{\text{short}} - S_{\text{floor}}) \cdot \left[ \frac{d_{\max} - d}{d_{\max} - d_{\min}} \right]^p$
* **Calculus Audit:**
  - Exactly interpolates $S(d_{\min}) = S_{\text{short}}$ and $S(d_{\max}) = S_{\text{floor}}$.
* **The Fatal Flaw (Hockey-Stick Distortion):**  
  Because the base $\frac{d_{\max} - d}{d_{\max} - d_{\min}}$ is linear in $d$, achieving a steep drop at short durations requires an extreme exponent ($p > 6$). This creates a severe "hockey stick" distortion: the stake requirement remains excessively elevated across the entire first 30 days, failing to provide practical liquidity relief.
* **Verdict:** **REJECTED**.

### 6.4 Family 4: Bounded Harmonic P-Decay (Selected Optimal Design)
* **Formula:**
  $$S_4(d) = S_{\text{floor}} + (S_{\text{short}} - S_{\text{floor}}) \cdot \left[ \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}} \right]^p$$
  where $p$ is derived analytically from an intermediate pivot knot $(d_{\text{pivot}}, S_{\text{baseline}})$:
  $$p = \frac{\ln\left( \frac{S_{\text{baseline}} - S_{\text{floor}}}{S_{\text{short}} - S_{\text{floor}}} \right)}{\ln\left( \frac{\frac{1}{d_{\text{pivot}}} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}} \right)}$$
* **Calculus Audit:**
  1. **Exact Boundary Interpolation:**  
     - At $d = d_{\min}$: $\frac{1/d_{\min} - 1/d_{\max}}{1/d_{\min} - 1/d_{\max}} = 1 \implies S(d_{\min}) = S_{\text{short}}$ identically.
     - At $d = d_{\max}$: $\frac{1/d_{\max} - 1/d_{\max}}{1/d_{\min} - 1/d_{\max}} = 0 \implies S(d_{\max}) = S_{\text{floor}}$ identically.
  2. **Regularized Asymptotics:** Subtracting the pole $1/d_{\max}$ in the numerator eliminates Candidate 2's heavy tail without artificial steps.
  3. **Turnover Kernel Alignment:** The kernel $\frac{1}{d} - \frac{1}{d_{\max}}$ directly reflects the turnover frequency of consensus staking ($f = 1/d$).
  4. **Exponent Stability:** Yields a stable, smooth exponent ($p \approx 0.60\text{--}0.65$) that provides continuous convexity across all intermediate durations.
* **Verdict:** **SELECTED CANONICAL FORMULATION**.

---

## 7. Trade-offs & Strategic Decisions: Why We Went This Way

```
┌────────────────────────────────────────────────────────────────────────┐
│                   KEY MECHANISM DESIGN DECISIONS                       │
├──────────────────────────┬──────────────────────┬──────────────────────┤
│ Design Decision          │ Alternative Rejected │ Primary Justification│
├──────────────────────────┼──────────────────────┼──────────────────────┤
│ 1. Coupled Continuous    │ Uncoupled Static     │ Decoupled parameters │
│    Admission Frontier    │ Floor (Flat 500)     │ create a 96.4% Sybil │
│                          │                      │ commitment collapse. │
├──────────────────────────┼──────────────────────┼──────────────────────┤
│ 2. Quantized Fixed-Point │ Continuous Float     │ Floating-point math  │
│    Integer Brackets      │ in Consensus Engine  │ causes non-determinis│
│                          │                      │ across CPU arches.   │
├──────────────────────────┼──────────────────────┼──────────────────────┤
│ 3. Tinbergen Separation  │ Single Lever Trying  │ Whales hold >99% of  │
│    (S(d) vs ACP-285)     │ to Solve All Goals   │ stake; duration lift │
│                          │                      │ requires yield carrot│
├──────────────────────────┼──────────────────────┼──────────────────────┤
│ 4. Pure Bouncer Framing  │ Behavioral Welfare   │ Micro-nodes hold <1% │
│    (Drop Retail Target)  │ Program for Nodes    │ stake; hosting drag  │
│                          │                      │ makes 500 AVAX unviab│
└──────────────────────────┴──────────────────────┴──────────────────────┘
```

1. **Why Not Flat Minimum Stake Across All Durations?**  
   If governance adopts flat parameters ($S_{\min} = S_{\text{floor}}$ and $d_{\min} = 48\text{h}$), any node can enter consensus for $K = S_{\text{floor}} \cdot 48\text{h}$, opening massive Sybil surfaces and generating severe P-Chain state write churn.
2. **Why Not Discrete Tiers Without an Underlying Continuous Formula?**  
   Arbitrary step tiers without an underlying continuous function create severe boundary arbitrage (e.g. 13 days 23 hours requiring 18,000 AVAX, while 14 days requires 2,000 AVAX). Operators exploit these cliffs via timing games. The continuous curve ensures that quantized brackets are mathematically grounded and monotonically fair.
3. **Why Drop Behavioral Utility Modeling?**  
   Historical telemetry contains zero market regime changes where APY shifted independently to identify validator price elasticity. Relying on qualitative interview quotes treats subjective opinion as engineering fact. The mechanism must be grounded in physical consensus invariants, not speculative behavioral curves.

---

## 8. What We Claim vs. What Cannot Be Achieved

To maintain strict scientific and professional integrity during stakeholder reviews, we enforce a clean demarcation of protocol boundaries:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   PROTOCOL CAPABILITY BOUNDARIES                       │
├─────────────────────────────────────────┬──────────────────────────────┤
│ WHAT THE MECHANISM CAN ACHIEVE (CLAIMS) │ WHAT CANNOT BE ACHIEVED      │
├─────────────────────────────────────────┼──────────────────────────────┤
│ ✅ Guarantees 48h Sybil parity:         │ ❌ Cannot steer whale lockup │
│    K(48h) >= K_baseline                 │    duration (ACP-285 lever)  │
├─────────────────────────────────────────┼──────────────────────────────┤
│ ✅ Suppresses off-peak validator set    │ ❌ Cannot make small nodes   │
│    churn when transaction fees = 0      │    profitable (VPS drag)     │
├─────────────────────────────────────────┼──────────────────────────────┤
│ ✅ Delivers capital entry relief for    │ ❌ Cannot alter BENQI 14-day │
│    annual commitments (S_floor)         │    smart contract cadence    │
├─────────────────────────────────────────┼──────────────────────────────┤
│ ✅ Preserves the 14-day Delegator       │ ❌ Cannot control terminal   │
│    Firewall boundary                    │    token inflation schedule  │
└─────────────────────────────────────────┴──────────────────────────────┘
```

### 8.1 What the Mechanism CAN Achieve (Our Claims)
1. **Guaranteed 48-Hour Sybil Parity:** By enforcing $S(d_{\min}) = S_{\text{short}}$, no operator can acquire active consensus sampling slots without locking a capital-time commitment equal to or greater than the historical Mainnet baseline ($K_{\text{baseline}}$).
2. **Off-Peak State Churn Suppression:** When network gas fees are at their minimum floor, the substantial capital requirement at short durations economically deters bots from repeatedly cycling validator registrations.
3. **Annual Capital Relief for Sovereign Operators:** Operators willing to commit for 365 days access the lower threshold $S_{\text{floor}}$, cutting capital entry barriers for long-term participants.
4. **Quarantine Isolation:** Guarantees that short-duration ETF and market-maker liquidity facilities are 100% self-funded, preventing short-term volatility from spilling into the retail delegation market.

### 8.2 What the Mechanism CANNOT Achieve (Non-Claims & Boundaries)
1. **Cannot Steer Macro Whale Duration:** The admission frontier is an entry barrier. Large institutional entities holding 181,000 to 1,750,000+ AVAX easily clear any entry barrier. Sizing $S_{\text{short}}$ higher does not extend whale lockups; whale duration is governed exclusively by **ACP-285 annualized reward rate ($\text{ARR}$) steepening**.
2. **Cannot Subsidize Small Node Hardware Costs:** A validator holding 500 AVAX earns ~40 AVAX/year. With dedicated VPS hosting costing $\$40\text{--}\$60/\text{month}$, small solo nodes run at a net loss unless AVAX trades above $\$15\text{--}\$20$. The admission frontier lowers the capital barrier, but it cannot alter off-chain hosting drag.
3. **Cannot Alter Institutional Delegation Cadences:** Liquid staking pools (BENQI managing 18.1M AVAX) operate on a continuous 14-day rolling reallocation loop. The admission frontier cannot force LST smart contracts to extend delegation terms beyond 14 days.
4. **Cannot Replace Emission Subsidies:** Managing the security transition as issuance approaches the 720M AVAX cap requires protocol fee burns (ACP-283, ACP-103) and L1 fee capture (ACP-77).

---

## 9. Grounding in Live Helicon Mainnet Telemetry

The proposal is directly validated by Mainnet state captured between **22 September and 29 September 2026** following the activation of Helicon (ACP-273):

1. **The 48-Hour Auto-Renewal Exploitation:**  
   In the first 48 hours, **two validators immediately entered under the 48-hour rule at ~2,000 AVAX (the current static floor), and both auto-renewed**.  
   *Protocol Proof:* This proves that without $S_{\min}(d)$, short-term nodes immediately exploit 48-hour liquidity with minimal capital commitments ($4{,}000\text{ AVAX-days}$ instead of $28{,}000\text{ AVAX-days}$).
2. **Bimodal Whale Independence:**  
   The largest commitments were **two institutional nodes locking ~1,750,000 AVAX each for ~198 days**.  
   *Protocol Proof:* Large institutional capital operates on an entirely different scale, verifying that macro duration is completely uncoupled from the entry threshold.
3. **100% Quarantine Compliance:**  
   Delegations remained strictly at $\ge 14\text{ days}$. The two 48-hour nodes received 0 AVAX in delegations, confirming that the PlatformVM Delegator Firewall is fully operational in production.
4. **Foundation Stakeholder Direction:**  
   The Foundation CIO and Lead Economist noted on the agenda:  
   > *"We don’t really have a quantitative expectation. The new flow will most likely come from ETFs though. So it might be helpful to check if there is a notable NAV increase in AVAX ETF, or ETFs with AVAX as a constituent."*  
   The admission frontier acts as the **protective perimeter** that allows ACP-273 to serve ETF redemption liquidity without compromising network security.

---

## 10. Conclusion & Next Steps

* **Mathematical Recommendation:** Adopt **Candidate Family 4 (Bounded Harmonic P-Decay)** as the canonical formulation for `vms/platformvm`.
* **Systems Architecture:** Verify that the admission frontier functions strictly as the **bouncer** evaluated against the **2 Bouncer KPIs**, leaving duration steering to ACP-285.
* **Next Implementation Step:** Complete the discrete integer fixed-point quantization schedule in Go (`vms/platformvm/admission.go`) and execute the multi-week cadCAD validation sweep under the *Stationary Continuous Arrival Invariant*.

---

*Authored under the BCRG Systems Engineering Framework.*  
*Canonical Reference: [`docs/2026-09-29-admission-frontier-mechanism-design-synthesis.md`](file:///home/hash/Hub/Projects/avalanche-phase-ii-research/docs/2026-09-29-admission-frontier-mechanism-design-synthesis.md)*
