# Outputs of the staking model

`model.engine.run` returns one long table, and `model.kpis` derives a daily table and a table of measures from it. Each row below is one output of the fitted lifecycle or of a model built on it, with its unit and the group of settings that makes it appear. The module `model.schema` holds the entries, and its function `render` writes this table.

Placements:

- `identifier`: a column of its own on every row of the long table, which names the row.
- `variable`: a value of the long table's `variable` column, whose amount is in the `value` column, one row per run, day and variable.
- `float`: a column of its own in the long table, one value per run and day, repeated on each of that day's rows.
- `kpi`: a value of the `measure` column of the table of key performance indicators that the function `kpis.kpi_table` returns, whose number is in its `value` column, one row per horizon in days and operating-cost level.
- `kpi_column`: a column of its own in the table of key performance indicators that the function `kpis.kpi_table` returns.
- `daily`: a column of the daily table that the function `kpis.run_daily_table` builds from one run of the long table, one row per day, beside the run's state variables and the float columns a measure reads.

Groups:

- `always`: every run of the fitted lifecycle and of every model built on it.
- `delegations`: a model with delegations, such as the v0.8.1 candidate.
- `turnover`: a run with the `record_turnover` setting switched on.
- `revenue`: a run with revenue funding, which is a reward rule that pays from the revenue pool, a revenue stream set above zero by the `revenue_avax_pa` setting, or the `count_revenue_in_supply` setting switched on.
- `price`: a run with a price path, set by the `price0_usd`, `price_drift_pa` and `price_volatility_pa` settings.
- `holders`: a holder model with the `holders` setting given, such as the v0.9 holders variant.

| Name | Placement | Group | Dtype | Unit | Description |
| --- | --- | --- | --- | --- | --- |
| `simulation` | identifier | always | int64 | an index from 0, no unit | The setting combination of a sweep, one per model, and 0 for a single run. |
| `run` | identifier | always | int64 | an index from 1, no unit | The Monte Carlo run within the setting combination, each with its own random draws. |
| `timestep` | identifier | always | int64 | days since the origin, a whole number | The day the row describes: 0 is the state at the end of the origin day and t the state at the end of day origin + t. |
| `time` | identifier | always | float64 | days since the origin, timestep times `dt` | The model time of the row, which equals the timestep because the lifecycle clock is one UTC day per step. |
| `variable` | identifier | always | object (str) | text, no unit | The name of the whole-number state variable whose amount the row's `value` holds. |
| `value` | identifier | always | int64 | the unit of the row's variable, listed in that variable's entry | The exact whole-number amount of the row's variable at the end of the row's day. |
| `specification` | identifier | always | object (str) | text, 16 hexadecimal characters, no unit | The first 16 characters of the SHA-256 hash of everything that decides the result: the model class, the run controls, the settings and the hashes of the input tables. |
| `model_version` | identifier | always | object (str) | text, no unit | The model version of the package that made the table. |
| `active_validators` | variable | always | int64 | a count of validator commitments, a stock at the end of the day | The validator commitments open at the end of the day. |
| `active_validator_stake_navax` | variable | always | int64 | nAVAX, 10^-9 AVAX, a stock at the end of the day | The validators' own stake in the commitments open at the end of the day, without delegations. |
| `returning_nodes` | variable | always | int64 | a count of nodes, a stock at the end of the day | The nodes out of the active set that left within the last 365 days and can still return. |
| `supply_navax` | variable | always | int64 | nAVAX, 10^-9 AVAX, a stock at the end of the day | The P-Chain supply counter that the reward formula reads: the supply at the origin plus every potential reward minted since, and the part paid from revenue when `count_revenue_in_supply` is set. Realized total supply, which subtracts burned fees, is lower. |
| `issued_navax` | variable | always | int64 | nAVAX, 10^-9 AVAX on the day, a flow | The potential rewards minted on the day for the commitments started that day, counted at their start as the supply counter counts them. Under revenue funding the count holds only the minted part, and in a model with delegations it holds the delegators' rewards as well as the validators'. |
| `started_stake_navax` | variable | always | int64 | nAVAX, 10^-9 AVAX on the day, a flow | The stake of the validator commitments the model started on the day, without the commitments accepted before the origin that start that day. |
| `nakamoto_third_nodes` | variable | always | int64 | a count of nodes, at the end of the day | The fewest nodes whose open own stake, each node's commitments summed, exceeds one third of all open validator own stake, and 0 when nothing is open. |
| `yield_gap_pp` | float | always | float64 | percentage points of stake a year, a difference of two annual rates, on the day | The reward gap renewal reads on the day: the design's annual rate for a 30-day stake at the renewal tenure above the fitted reward formula's rate, less the outside yield's change from its fitting-window level, and less the share a funding rule left unpaid. The value at timestep 0 is 0. |
| `started_stake_days_navax` | float | always | float64 | nAVAX times days on the day, a flow | The stake of each validator commitment the model started on the day times its committed days, summed. |
| `offered_rate_30d` | float | always | float64 | a fraction of stake a year, 0.07 for 7% a year, on the day | The annual rate the reward rule offers a 30-day stake with no tenure, priced at noon of the day at the supply counter of the start of the day. The value at timestep 0 is missing, NaN. |
| `active_delegations` | variable | delegations | int64 | a count of delegations, a stock at the end of the day | The delegations open at the end of the day. |
| `active_delegated_stake_navax` | variable | delegations | int64 | nAVAX, 10^-9 AVAX, a stock at the end of the day | The stake of the delegations open at the end of the day. |
| `benqi_delegated_stake_navax` | variable | delegations | int64 | nAVAX, 10^-9 AVAX, a stock at the end of the day | The stake of the open delegations of BENQI, the liquid staking provider. |
| `<key>_delegated_stake_navax` | variable | delegations | int64 | nAVAX, 10^-9 AVAX, a stock at the end of the day | One variable per operator named at the origin other than BENQI, with `<key>` the operator's key: the stake of the open delegations that operator owns. A model with no named operator has none. |
| `validator_issued_navax` | variable | delegations | int64 | nAVAX, 10^-9 AVAX on the day, a flow | The potential rewards minted on the day for the validator commitments started that day, the validators' part of `issued_navax`. |
| `delegator_issued_navax` | variable | delegations | int64 | nAVAX, 10^-9 AVAX on the day, a flow | The potential rewards minted on the day for the delegations placed that day, the delegators' part of `issued_navax`. Delegations open or accepted at the origin add none. |
| `unplaced_delegations` | variable | delegations | int64 | a count of delegations on the day, a flow | The new delegations drawn on the day that were not made, because no validator had room for them or the unstaked supply did not cover their stake. |
| `ended_validators` | variable | turnover | int64 | a count of validator commitments on the day, a flow | The validator commitments whose period ended on the day, renewed or not. |
| `renewed_validators` | variable | turnover | int64 | a count of validator commitments on the day, a flow | The commitments that ended on the day and renewed at once on the same node, after the supply limit. |
| `first_ever_validators` | variable | turnover | int64 | a count of validator commitments on the day, a flow | The commitments started on the day by nodes with no earlier commitment that are not returns, with those accepted before the origin and due that day. |
| `revenue_paid_navax` | variable | revenue | int64 | nAVAX, 10^-9 AVAX on the day, a flow | The part of the day's priced rewards paid from the revenue pool instead of minted. |
| `unpaid_need_navax` | variable | revenue | int64 | nAVAX, 10^-9 AVAX on the day, a flow | The revenue share of the day's priced rewards that the pool could not pay and the rule left unpaid. A rule that mints the shortfall leaves 0. |
| `revenue_pool_navax` | variable | revenue | int64 | nAVAX, 10^-9 AVAX, a stock at the end of the day | The revenue pool after the day's inflow of one 365th of `revenue_avax_pa` and the day's payments. |
| `price_usd` | float | price | float64 | US dollars per AVAX, at the end of the day | The AVAX price on the run's seeded price path, which starts at `price0_usd` on the origin day. |
| `etf_holdings_navax` | variable | holders | int64 | nAVAX, 10^-9 AVAX, a stock at the end of the day | The AVAX the funds of `fund_holdings` hold, summed, after the day's growth by their drift plus the price elasticity times the day's log return of the price. |
| `etf_validators` | variable | holders | int64 | a count of validators, a stock at the end of the day | The validators the model made for the funds that are open at the end of the day. |
| `etf_validator_stake_navax` | variable | holders | int64 | nAVAX, 10^-9 AVAX, a stock at the end of the day | The own stake of the validators the model made for the funds that are open at the end of the day. |
| `liquid_staking_stake_navax` | variable | holders | int64 | nAVAX, 10^-9 AVAX, a stock at the end of the day | The liquid staking provider's open delegated stake, which equals `benqi_delegated_stake_navax`. |
| `nakamoto_third_operators` | variable | holders | int64 | a count of operators, at the end of the day | The fewest operators whose weight, own stake plus the delegations on their validators, exceeds one third of all weight. A fund's model-made validators count as one operator, and every other node as its own. |
| `lst_target_navax` | float | holders | float64 | nAVAX, 10^-9 AVAX, a target stock held as a float, at the end of the day | The liquid staking provider's target stock of delegated stake, grown each day by its drift plus the gap elasticity times the change in the liquid staker's yield gap since the origin. The provider starts delegations to bring its stake up to the target. |
| `liquid_staking_share` | float | holders | float64 | a share of all stake, own and delegated, 0 to 1, at the end of the day | The liquid staking provider's open delegated stake over all open stake, validators' own and delegated. |
| `effective_operators` | float | holders | float64 | a number of operators, at least 1 when anything is staked, at the end of the day | One over the Herfindahl index of the operators' shares of weight, own stake plus delegations, and 0 when nothing is staked. |
| `supply_counter_navax` | daily | always | int64 | nAVAX, 10^-9 AVAX, a stock at the end of the day | The run's `supply_navax`, the P-Chain supply counter, under the name the chain's daily table gives it. |
| `issued_all_roles_navax` | daily | delegations | int64 | nAVAX, 10^-9 AVAX on the day, a flow | The run's `issued_navax` in a model with delegations, validators' and delegators' rewards minted on the day. The daily table's `issued_navax` then holds `validator_issued_navax`, validators only, as the chain's table does. |
| `burned_navax` | daily | always | float64 | nAVAX, 10^-9 AVAX, AVAX burned on the day, a flow | The transaction fees burned on the day. After the origin the function `kpis.with_realized_supply` holds it at the mean daily burn it is given, and a daily table without that step has no such column. |
| `total_supply_navax` | daily | always | float64 | nAVAX, 10^-9 AVAX, a stock at the end of the day | Realized total supply, minted less burned. After the origin the function `kpis.with_realized_supply` builds it from the supply at the origin plus each day's issuance of every role less the burn, and a daily table without that step has no such column. |
| `measure` | kpi_column | always | object (str) | text, no unit | The name of the row's measure, one of the `kpi` entries. |
| `horizon_days` | kpi_column | always | int64 | days after the origin | The horizon the measure reads up to, counted in days from the origin. |
| `cost_level` | kpi_column | always | object (str) | text, no unit | The operating-cost level of a `return_margin` row, and the empty string on every other row. |
| `value` | kpi_column | always | float64 | the unit of the row's measure, listed in that measure's `kpi` entry | The number of the row's measure at the row's horizon and cost level. |
| `issued_navax` | kpi | always | float64 | nAVAX, 10^-9 AVAX, minted from the day after the origin to the horizon, a flow summed | The validators' issuance over the horizon, as the 64-bit float that issuance saved divides. A run with delegations counts its validators' part, `validator_issued_navax`. |
| `issuance_saved` | kpi | always | float64 | a share of the baseline's issuance over the same days, negative when the run issues more | One minus the run's issuance over the baseline's, the same run under the chain's rule. Given only with a baseline. |
| `validator_stake_retained` | kpi | always | float64 | a ratio of validator stake to the baseline's at the horizon, 1 when equal | The validator stake at the horizon over the baseline's. Given only with a baseline. |
| `validator_stake_navax` | kpi | always | float64 | nAVAX, 10^-9 AVAX, a stock at the end of the horizon day | The validators' own stake at the horizon. |
| `lowest_validator_stake_navax` | kpi | always | float64 | nAVAX, 10^-9 AVAX, the lowest end-of-day stock from the day after the origin to the horizon | The lowest validator stake of any day of the horizon. |
| `active_validators` | kpi | always | float64 | a count of validator commitments at the end of the horizon day | The validators active at the horizon. |
| `active_validators_retained` | kpi | always | float64 | a ratio of active validators to the baseline's at the horizon, 1 when equal | The validators active at the horizon over the baseline's. Given only with a baseline. |
| `net_inflation` | kpi | always | float64 | a share of realized total supply at the horizon, over the 365 days that end at the horizon | Issuance less burn over the 365 days that end at the horizon, over realized total supply at the horizon. |
| `net_inflation_on_rewards_paid` | kpi | always | float64 | a share of realized total supply at the horizon, over the 365 days that end at the horizon | Net inflation with the rewards the chain paid in place of issuance. Only the chain's table has rewards paid. |
| `validator_staking_ratio` | kpi | always | float64 | a share of realized total supply, 0 to 1, at the horizon | The validators' own stake at the horizon over realized total supply. |
| `staking_ratio_with_delegations` | kpi | delegations | float64 | a share of realized total supply, 0 to 1, at the horizon | The validators' own stake plus delegated stake at the horizon over realized total supply. |
| `nakamoto_coefficient` | kpi | always | float64 | a count of nodes at the horizon | The fewest nodes whose own stake exceeds one third of all validator own stake, at the horizon. |
| `liquid_staking_share` | kpi | holders | float64 | a share of all stake, own and delegated, 0 to 1, at the horizon | The liquid staking provider's delegated stake over all stake at the horizon. |
| `nakamoto_operators` | kpi | holders | float64 | a count of operators at the horizon | The fewest operators whose weight, own stake plus delegations, exceeds one third of all weight, at the horizon. |
| `effective_operators` | kpi | holders | float64 | a number of operators at the horizon | One over the Herfindahl index of operator weights at the horizon. |
| `earned_rate` | kpi | always | float64 | a fraction of stake a year, 0.07 for 7% a year | The annual reward rate on the commitments started over the horizon: 365 times issuance over stake-days. |
| `return_margin` | kpi | always | float64 | a fraction of stake a year, one row per operating-cost level | The earned rate less the competing yield and the operating cost, each a fraction of stake a year. |
| `stake_weighted_duration` | kpi | always | float64 | days | The committed days of the commitments started over the horizon, weighted by their stake. |
| `reward_rate_volatility` | kpi | always | float64 | percentage points of stake a year, a sample standard deviation | The sample standard deviation of `offered_rate_30d` over the horizon, times 100. |
| `stake_volatility` | kpi | always | float64 | natural-log units a day, a sample standard deviation | The sample standard deviation of the daily change in the natural log of validator stake, from the origin to the horizon. |
| `worst_30_day_stake_fall` | kpi | always | float64 | a share of the stake 30 days earlier, negative for a fall | The largest fall in validator stake over any 30 days from the origin to the horizon. |
| `issuance_half_life` | kpi | always | float64 | years | The years for the issuance left under the supply cap to halve at the pace of the last 365 days, or of the horizon when it is shorter. |
| `burn_to_issuance` | kpi | always | float64 | AVAX burned per AVAX of rewards paid, a ratio | The AVAX burned per AVAX of rewards paid over the complete days of the horizon. Only the chain's table has rewards paid. |
| `price_usd` | kpi | price | float64 | US dollars per AVAX at the horizon | The AVAX price at the horizon, from the run's price path. |
| `cost_of_attack_third_usd` | kpi | price | float64 | US dollars at the horizon's price | The dollars of fresh stake an attacker needs to hold one third of all stake at the horizon, enough to halt the chain: half of the honest stake, own and delegated, times the price. |
| `cost_of_attack_two_thirds_usd` | kpi | price | float64 | US dollars at the horizon's price | The dollars of fresh stake an attacker needs to hold two thirds of all stake at the horizon, enough to finalize at will: twice the honest stake, own and delegated, times the price. |
| `security_cover` | kpi | price | float64 | a ratio of US dollars to US dollars, above 1 when an attack costs more | The cost of a one-third attack over the dollar value the stake is asked to secure. Given only with `secured_value_usd`. |

Every other column of the long table is a Param setting of the model, one column per setting, holding the setting's value for the row's setting combination. A setting's unit is in its `doc` string, and the function `schema.setting_names` lists the settings of a model.
