# 2. A model connects a question to a test

*Draft for review.*

Changing a reward formula changes a sequence of future choices. Arithmetic determines the return offered to a commitment, but participation depends on who enters, renews, leaves or returns. A model combines those mechanisms so their joint consequences can be examined.

The research question determines what must be represented. For v0.8.0, that question is how reward designs change validator own stake, participation and reward promises. A model intended to study consensus attacks, AVAX price formation or delegation markets would need additional mechanisms and evidence.

## State and transitions make the explanation executable

A **state** contains the quantities carried from one simulated time to the next. An **input** supplies information or conditions from outside the model. A **parameter** configures a process. An **output measure** summarizes a path. Keeping these roles separate makes a comparison interpretable.

The model is a discrete-time stochastic population model with individual node and period records. Its daily transitions generate aggregate stake and count. This combines a stocks-and-flows description with node-level statistical decisions. The resulting aggregate trajectory is an implication of those decisions, rather than an independently fitted line through total stake.

In [cadCAD](https://github.com/cadCAD-org/cadCAD/blob/master/documentation/README.md), policy functions produce signals and state-update functions produce the next state. A partial state update block groups updates with a defined information order. This project also has six internal daily stages. An internal stage is not automatically a separate cadCAD block. The [architecture chapter](architecture.md) explains their composition.

[Param](https://param.holoviz.org/en/docs/latest/user_guide/Parameters.html) declares settings, bounds and metadata. It catches incompatible configurations and makes a model's settings inspectable. These checks establish configuration properties. Statistical evidence is still needed to judge the processes being configured.

## Protocol mechanisms and behavioural models need different evidence

A reward formula can be checked against the protocol's integer arithmetic and recorded potential rewards. A renewal probability needs evidence about decisions. The first is a specification-reproduction problem. The second is an inference and prediction problem.

Renewal, delayed return and daily arrivals use likelihood-based statistical fits. Duration choices and the stake hurdle use empirical distributions and conditional counts. A **likelihood** evaluates how probable the observations are under a statistical model. An empirical distribution instead retains observed choice patterns directly. Calling every component a likelihood fit would hide this difference.

Calibration uses only information available by the origin. The origin is the last observed day supplying the initial state and fitting data. Time windows, definitions of renewal and return, and treatment of incomplete follow-up are design decisions. They affect what the model learns and must be retained with its source identity.

## A counterfactual needs a behavioural response

A **counterfactual** asks how outcomes would differ under an alternative condition. Historical choices under one reward menu do not, by themselves, specify choices under a changed menu. Renewal and entry response coefficients supply that link.

The working coefficients are informed by preliminary dollar-reward regressions and depend on an interpretation of price variation. Market conditions can affect both rewards and participation. The [response evidence](../../content/Phase%20II/Wiki/Memos/drafts/2026-10-30-research/evidence.md#response-estimates) therefore supports scenario exploration with explicit qualifications. It does not establish a universally identified causal elasticity.

A paired design holds the input state, conditions, fitted draw and keyed randomness in common. Pairing reduces unrelated stochastic differences. It does not eliminate structural error, omitted mechanisms or confounding in the response estimate.

## Different uncertainty enters at different places

Daily choices vary even with fixed settings. Estimated parameters vary because the historical sample is finite. Renewal behaviour can drift across historical windows. Outside yields and response specifications describe alternative economic conditions. Model structure can also be wrong.

| Uncertainty | Representation | Interpretation |
| --- | --- | --- |
| Daily randomness | Renewals, returns, arrivals and choice draws | Variation between paths conditional on one model |
| Fitting uncertainty | Node and time-block resampling, parameter draws | Variation supported by the declared resampling design |
| Drift | Run-level renewal shift | Variation estimated between fitting windows |
| Scenario uncertainty | Outside yields and response settings | Conditions whose probabilities have not necessarily been estimated |
| Structural uncertainty | Alternative components and future extensions | A source of error only partly represented in existing runs |

The stake hurdle stays at its fitted point estimate in v0.8.0. Interval bands therefore omit its fitting uncertainty. Pooling scenarios also does not turn them into a probability distribution over the future unless probabilities have been justified.

## Evaluation must match the claim

Software tests check implementation behaviour. Reward reconstruction checks protocol calculations. Numerical replay checks that a result can be reproduced. Forecast evaluation checks predictions against later observations. Causal evidence supports behavioural responses to intervention. Preference evaluation judges outcomes against chosen goals.

Each provides evidence for a different statement. A repeated simulation can reproduce a poor model exactly. A model can forecast total stake reasonably while misrepresenting a policy response. An attractive utility score can violate a participation safeguard. The [evaluation chapter](analysis.md) keeps these tests distinct.

A complete research cycle states the question, explains its relevance, declares the hypothesis and design, executes the experiment, examines the outcomes and identifies the next question. A separate methodology reflection asks whether the model and research direction remain appropriate. The [bounded cycle example](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/examples/research-cycle/README.md) makes that separation concrete.

[Manual contents](README.md)
