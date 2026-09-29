# Avalanche Research Documentation Index

This directory contains research specifications, architectural memos, and systems engineering frameworks for Avalanche Primary Network consensus economics.

---

## Canonical Stage 4 Architecture (Active Specifications)

These documents represent the **approved, current state of the research** (September 29, 2026). All ongoing modeling, cadCAD parameter calibration, and Go implementation work trace directly to this canonical suite:

1. **[Formal Mechanism Design: Duration-Dependent PoS Admission Frontier ($S_{\min}(d)$)](./2026-09-29-formal-mechanism-design-admission-frontier.md)**
   * **Scope:** Core mathematical specification of the admission gate.
   * **Key Results:** Decoupling Axiom (Bouncer vs. Carrot), axiomatic elimination of Families 1–3, formal derivation of **Family 4: Bounded Harmonic P-Decay**, Sybil economics ($m \cdot c_{\text{op}} \cdot d_{\max}$), and discrete-event cadCAD renewal specification ($\tau_{\text{rem}, i} \sim \mathcal{U}(1, d_i)$).
   * **Subsystem:** `vms/platformvm`.

2. **[Systems Engineering Specification: Formal KPI Architecture & Evaluation Framework](./2026-09-29-systems-engineering-kpi-framework.md)**
   * **Scope:** 5-Axiom metric selection framework defining the canonical **3-MOE + 2-TPM Architecture**.
   * **Calibration Lead Directive:** Directly guides empirical calibration of the parameter triple $\Theta = (S_{\text{short}}, S_{\text{floor}}, p)$ across MOE 1 (Sybil Parity $R_{\text{sybil}}$), MOE 2 (Terminal Friction $F_{\text{terminal}}$), and MOE 3 (Off-Peak Turnover $N_{\text{turnover}}$).

3. **[Interactive Admission Frontier Digital Twin](./admission_frontier_digital_twin.html)**
   * **Scope:** Interactive browser-based simulation twin and parameter explorer.
   * **Capabilities:** Real-time parameter slider sweeps, candidate curve comparisons, live Axioms 1–5 compliance scorecard, marginal elasticity profiles $\varepsilon_{S, d}$, and governance presets.
   * **Local Server Mirror:** `research/plots/admission_frontier_digital_twin.html`.

---

## Active Calibration Scope: The Bounded Harmonic P-Decay Frontier

The admission filter is governed by the Bounded Harmonic P-Decay curve:

$$S_{\min}(d) = S_{\text{floor}} + (S_{\text{short}} - S_{\text{floor}}) \cdot \left[ \frac{\frac{1}{d} - \frac{1}{d_{\max}}}{\frac{1}{d_{\min}} - \frac{1}{d_{\max}}} \right]^p$$

### Parameter Search Domain
* **$d_{\min} = 2 \text{ days}$** (Fixed protocol duration lower bound, ACP-273).
* **$d_{\max} = 365 \text{ days}$** (Fixed protocol duration upper bound, PlatformVM).
* **$K_{\text{baseline}} = 28{,}000 \text{ AVAX-days}$** (Legacy anchor: $2{,}000 \text{ AVAX} \times 14 \text{ days}$).
* **$S_{\text{short}} \in [14{,}000, 20{,}000] \text{ AVAX}$** (Short-end self-stake anchor; bounds MOE 1).
* **$S_{\text{floor}} \in [500, 2{,}000] \text{ AVAX}$** (Terminal self-stake floor; satisfies MOE 2 identically).
* **$p \in [1.00, 3.00]$** (Curvature decay exponent; dampens MOE 3 off-peak churn and sets 14d retail delegation gate).

---

## Archival / Superseded Documents (Context Only)

> [!NOTE]
> The following documents reflect exploratory research milestones prior to the September 29, 2026 Stage 4 consolidation. They are preserved for auditability and history, but should **not** be used for parameter calibration or implementation decisions:
>
> - `2026-09-22-admission-frontier-and-duration-lift-memo.md` (Exploratory draft prior to Bouncer/Carrot policy instrument decoupling).
> - `2026-09-25-Avalanche-Primary-Network-Cryptoeconomic-Policy-Architecture-Notion-Memo.md` (Draft memo integrating unratified ACP proposals).
> - `acp-duration-dependent-admission-frontier.md` (Earlier community ACP draft preceding the axiomatic elimination of Families 1–3).
