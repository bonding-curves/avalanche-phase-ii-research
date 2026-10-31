# Complete Python module reference

*Draft for review.*

The package contains 188 Python files. This reference parses source without importing the modules being inventoried. Each entry gives the module's source description and its defined classes and functions. Imported compatibility names appear separately. A source description describes code, not scientific acceptance. The [architecture](architecture.md) and [component explanations](components.md) identify the released execution path and development alternatives.

## __init__.py

Avalanche Phase II research tools.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/__init__.py)

Imported components: `PackageNotFoundError`, `version`.

## admission_frontier.py

Mathematical models and protocol-level invariants for duration-dependent entry stake frontiers.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/admission_frontier.py)

| Component | Purpose from source |
| --- | --- |
| `CurveFamily` (class) | Mathematical functional form for the duration-stake admission frontier. |
| `AdmissionConfig` (class) | Parameter specification for the duration-dependent admission frontier. |
| `s_min_hyperbolic` (function) | Compute minimum stake requirement using hyperbolic decay: |
| `s_min_iso_commitment` (function) | Compute minimum stake requirement under constant Capital-Time invariant: |
| `s_min_power_law` (function) | Compute minimum stake requirement using generalized power-law decay: |
| `evaluate_admission_frontier` (function) | Generate comprehensive evaluation metrics for a duration-dependent admission schedule. |
| `evaluate_historical_eligibility` (function) | Calculate the share of historical validator self-bonds that would qualify under S_min(d). |

## analysis/__init__.py

Analysis of authenticated model outputs, separate from simulation and fitting.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/__init__.py)

## analysis/cart.py

Grouped nested CART on complete caller-declared labels and design blocks.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/cart.py)

| Component | Purpose from source |
| --- | --- |
| `Refused` (class) | The complete declared design cannot be assessed under this contract. |
| `_aligned` (function) | Implementation helper. Open its source for the algorithm. |
| `_scope` (function) | One frozen family/yield/horizon; row provenance remains caller-owned. |
| `_bootstrap` (function) | Resample complete units using the caller's fixed joint index matrix. |
| `analyze_cart` (function) | Frozen MM2 classification with paired-unit OOF uncertainty. |
| `_reg_splits` (function) | Implementation helper. Open its source for the algorithm. |
| `_reg_fit` (function) | Implementation helper. Open its source for the algorithm. |
| `_reg_select` (function) | Implementation helper. Open its source for the algorithm. |
| `analyze_regression_cart` (function) | Continuous-KPI descriptive trees and honest grouped OOF MSE/R2. |
| `_has_explicit_mask` (function) | Implementation helper. Open its source for the algorithm. |
| `_text` (function) | Implementation helper. Open its source for the algorithm. |
| `_strings` (function) | Implementation helper. Open its source for the algorithm. |
| `_integer` (function) | Implementation helper. Open its source for the algorithm. |
| `_support` (function) | Implementation helper. Open its source for the algorithm. |
| `_splits` (function) | Implementation helper. Open its source for the algorithm. |
| `_fit` (function) | Implementation helper. Open its source for the algorithm. |
| `_metrics` (function) | Implementation helper. Open its source for the algorithm. |
| `_select` (function) | Implementation helper. Open its source for the algorithm. |
| `_tree_receipt` (function) | Implementation helper. Open its source for the algorithm. |
| `analyze_mm2` (function) | Return JSON-compatible nested-CV receipts and a descriptive fitted CART. |

## analysis/decision_summary.py

Pure decision summaries for predeclared sweep scopes.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/decision_summary.py)

| Component | Purpose from source |
| --- | --- |
| `ContractError` (class) | An input violates an explicit summary contract. |
| `_require` (function) | Implementation helper. Open its source for the algorithm. |
| `_groups` (function) | Implementation helper. Open its source for the algorithm. |
| `confidence_ratings` (function) | Rate a relationship across every declared response cell. |
| `sign_reversals` (function) | Compare adjacent grid bands, retaining unassessable edges. |
| `clustered_mean_interval` (function) | Finite row-weighted mean with caller-supplied whole-unit resampling. |
| `clustered_pass_share` (function) | Boolean pass share and its separate conditional cluster interval. |
| `pass_share_flags` (function) | Exact inclusive 90/70/50 lines and strict outside-[5,95]% screen. |
| `threshold_outcomes` (function) | Long primary/alternative flags from already cost-rescored wide rows. |
| `summarize_pass_shares` (function) | Summarize cells within ONE independent family/yield resampling scope. |
| `design_rankings` (function) | Rank family means under each family's declared A/B input distribution. |
| `point_estimates` (function) | Observed A-only maximum issuance saved, ties by numeric source index. |
| `select_and_confirm` (function) | Select one frozen A candidate and confirm it once on B. |

## analysis/explainer_pairs.py

Pure matched trajectory values in natural units, without statistical inference.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/explainer_pairs.py)

| Component | Purpose from source |
| --- | --- |
| `PairingError` (class) | The input cannot preserve the declared matched trajectory identities. |
| `_require` (function) | Implementation helper. Open its source for the algorithm. |
| `_ids` (function) | Implementation helper. Open its source for the algorithm. |
| `_numeric` (function) | Implementation helper. Open its source for the algorithm. |
| `units_metadata` (function) | Return fresh JSON-serializable source/output units and reconstruction limits. |
| `_w8` (function) | Implementation helper. Open its source for the algorithm. |
| `matched_natural_units` (function) | Return complete design/baseline/delta rows sorted by horizon and index. |

## analysis/explainer_tiers.py

Expose saved recommendation evidence and separately scoped family context.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/explainer_tiers.py)

| Component | Purpose from source |
| --- | --- |
| `_sign` (function) | Implementation helper. Open its source for the algorithm. |
| `_index` (function) | Implementation helper. Open its source for the algorithm. |
| `_recommendations` (function) | Implementation helper. Open its source for the algorithm. |
| `tier_cell_detail` (function) | Return 13 explicitly qualified cells per saved recommendation record. |

## analysis/m2_associations.py

Milestone 2 rank adapters on authenticated, complete wide tables.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/m2_associations.py)

| Component | Purpose from source |
| --- | --- |
| `_numeric` (function) | Implementation helper. Open its source for the algorithm. |
| `_integers` (function) | Implementation helper. Open its source for the algorithm. |
| `_configuration` (function) | Implementation helper. Open its source for the algorithm. |
| `_validated` (function) | Implementation helper. Open its source for the algorithm. |
| `_bases` (function) | Canonical A/B membership; the upstream consumer owns source authentication. |
| `_draws` (function) | Implementation helper. Open its source for the algorithm. |
| `_digest` (function) | Implementation helper. Open its source for the algorithm. |
| `_counts` (function) | Implementation helper. Open its source for the algorithm. |
| `_rank_spec` (function) | Implementation helper. Open its source for the algorithm. |
| `_weighted_ranks` (function) | Implementation helper. Open its source for the algorithm. |
| `_batch` (function) | All inputs/KPIs share ranks, control projections and multiplicity weights. |
| `_relationships` (function) | Implementation helper. Open its source for the algorithm. |
| `analyze_associations` (function) | Return (long rows, metadata), using full and nine-cell A/B populations. |
| `benjamini_hochberg` (function) | BH-adjust one complete declared matrix of externally qualified p-values. |

## analysis/m2_contract.py

Explicit scopes and frozen scientific constants for the M2 analysis.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/m2_contract.py)

| Component | Purpose from source |
| --- | --- |
| `ContractError` (class) | An analysis input cannot satisfy its declared scientific scope. |
| `response_band` (function) | Equal-width unit-coordinate bands with explicit endpoint ownership. |
| `row_metadata` (function) | Preserve all labels and physical inputs, never infer role from output. |
| `rescore_costs` (function) | Affine cost transformation; the original zero margin remains intact. |
| `failure_labels` (function) | The frozen goal/limit labels, with equality retained as a pass. |

## analysis/m2_resampling.py

Whole-unit resampling with caller-owned random state and explicit scope.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/m2_resampling.py)

| Component | Purpose from source |
| --- | --- |
| `draw_indices` (function) | Implementation helper. Open its source for the algorithm. |
| `validate_indices` (function) | Implementation helper. Open its source for the algorithm. |
| `indices_sha256` (function) | Implementation helper. Open its source for the algorithm. |
| `scope_draws` (function) | One shared matrix per Saltelli family/yield; original i fixes ordering. |
| `cluster_statistics` (function) | Ratio of sums after expanding complete clusters, not means of means. |
| `replicated_noise_share` (function) | Nonnegative one-way random-effects variance share from complete repeats. |

## analysis/m2_sensitivity.py

Full Saltelli MM3 adapter with supplied joint-base resampling, no new draws.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/m2_sensitivity.py)

| Component | Purpose from source |
| --- | --- |
| `_hybrids` (function) | Implementation helper. Open its source for the algorithm. |
| `_batch_indices` (function) | Vectorized equivalent of sobol._indices for leading bootstrap dimension. |
| `analyze_sensitivity` (function) | Return (long rows, metadata) for each complete family/yield design. |

## analysis/m2_tables.py

Complete paired KPI tables with original design labels and cost views.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/m2_tables.py)

| Component | Purpose from source |
| --- | --- |
| `analysis_table` (function) | One row per source trajectory/horizon, including matched relative KPIs. |

## analysis/paired_sweep.py

Authenticate paired sweep outputs and reconstruct their relative KPIs.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/paired_sweep.py)

| Component | Purpose from source |
| --- | --- |
| `ContractError` (class) | An input differs from the caller's complete, frozen analysis contract. |
| `_require` (function) | Implementation helper. Open its source for the algorithm. |
| `_integer` (function) | Implementation helper. Open its source for the algorithm. |
| `Bundle` (class) | Implementation helper. Open its source for the algorithm. |
| `_mechanism` (function) | Implementation helper. Open its source for the algorithm. |
| `_control_metadata` (function) | Implementation helper. Open its source for the algorithm. |
| `validate_pairing` (function) | Check every declared baseline, including its seed, draw and responses. |
| `read_bundle` (function) | Read exactly the four externally pinned files before parsing their contents. |
| `rehearsal_selection` (function) | Propose the declared small subset, preserving original and local indices. |
| `expected_cells` (function) | Implementation helper. Open its source for the algorithm. |
| `validate_outputs` (function) | Validate complete cell accounting and exact producer row identities. |
| `read_outputs` (function) | Authenticate a complete receipt and hash-checked Parquet snapshots. |
| `relative_kpis` (function) | Reconstruct each design row's three ratios from its matched baseline. |
| `control_checks` (function) | Apply only the E2 zero and active controls present in the frozen subset. |

## analysis/prim.py

Deterministic numeric peeling/pasting PRIM with A discovery and B confirmation.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/prim.py)

| Component | Purpose from source |
| --- | --- |
| `Refused` (class) | Incomplete or misaligned caller input cannot be analysed. |
| `_masked` (function) | Implementation helper. Open its source for the algorithm. |
| `_input` (function) | Implementation helper. Open its source for the algorithm. |
| `_inside` (function) | Implementation helper. Open its source for the algorithm. |
| `_stats` (function) | Implementation helper. Open its source for the algorithm. |
| `_candidate` (function) | Implementation helper. Open its source for the algorithm. |
| `_canonical` (function) | Implementation helper. Open its source for the algorithm. |
| `_selection_key` (function) | Implementation helper. Open its source for the algorithm. |
| `_search` (function) | Implementation helper. Open its source for the algorithm. |
| `discover_confirm` (function) | Choose an A-qualified box, then confirm its unchanged bounds on B once. |

## analysis/rank_associations.py

Synthetic MM1 rank associations on caller-validated, complete memory tables.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/rank_associations.py)

| Component | Purpose from source |
| --- | --- |
| `ContractError` (class) | Unsupported input or owner resampling/outcome policy. |
| `Resampling` (class) | Implementation helper. Open its source for the algorithm. |
| `_names` (function) | Implementation helper. Open its source for the algorithm. |
| `_finite` (function) | Implementation helper. Open its source for the algorithm. |
| `_validate` (function) | Implementation helper. Open its source for the algorithm. |
| `_coefficient` (function) | Implementation helper. Open its source for the algorithm. |
| `_point` (function) | Implementation helper. Open its source for the algorithm. |
| `_draw_indices` (function) | Global units: a block crossing variant/response strata travels together. |
| `analyze_mm1` (function) | Per variant/response Spearman and PRCC plus conditional percentile intervals. |

## analysis/report_figures.py

Standalone Bokeh figures over exact report-summary frames.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/report_figures.py)

| Component | Purpose from source |
| --- | --- |
| `FigureContractError` (class) | A summary lacks fields needed for an honest figure. |
| `_require` (function) | Implementation helper. Open its source for the algorithm. |
| `_source` (function) | Implementation helper. Open its source for the algorithm. |
| `_table` (function) | Implementation helper. Open its source for the algorithm. |
| `_hover` (function) | Implementation helper. Open its source for the algorithm. |
| `_star_label` (function) | Implementation helper. Open its source for the algorithm. |
| `_panels` (function) | Implementation helper. Open its source for the algorithm. |
| `_wrap` (function) | Implementation helper. Open its source for the algorithm. |
| `correlation_heatmap` (function) | Signed coefficient cells, explicit missing values and unqualified stars. |
| `_tree_positions` (function) | Implementation helper. Open its source for the algorithm. |
| `tree_figure` (function) | Descriptive final trees; OOF validation belongs in its separate table. |
| `sobol_figure` (function) | First/total indices with raw intervals, including values outside [0,1]. |
| `region_figure` (function) | Saved points and optional two-dimensional projection of frozen boxes. |
| `design_ranking_figure` (function) | Family means and p10/p90 run spread, never mislabeled as mean CIs. |
| `recommendation_table` (function) | Display the exact exported recommendation rows and unsupported states. |
| `write_standalone_html` (function) | Write self-contained HTML with inline Bokeh resources, no CDN request. |

## analysis/report_summaries.py

Consumer-facing summaries of saved results, without fitting or inference.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/report_summaries.py)

| Component | Purpose from source |
| --- | --- |
| `selector` (function) | Serialize an explicit source-row predicate without inventing missing data. |
| `paired_margin_fields` (function) | DR3's margin is the paired difference bound, never a difference of bounds. |
| `found_label` (function) | Implementation helper. Open its source for the algorithm. |
| `tree_top_input` (function) | Descriptive final-tree importance, distinct from held-out prediction skill. |
| `recommendation_reversal_fields` (function) | A sign-change grid does not identify reversal of an optimum or fixed box. |
| `contract_dispositions` (function) | Implementation helper. Open its source for the algorithm. |
| `correction_summary_rows` (function) | Materialize DR11 cells with explicit source scopes and unsupported states. |

## analysis/sobol.py

MM3 synthetic structured first/total Sobol calculator. No I/O or design generation.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/analysis/sobol.py)

| Component | Purpose from source |
| --- | --- |
| `ContractError` (class) | Incomplete, incompatible or undefined analysis input. |
| `Coupling` (class) | Implementation helper. Open its source for the algorithm. |
| `Receipt` (class) | Implementation helper. Open its source for the algorithm. |
| `_names` (function) | Implementation helper. Open its source for the algorithm. |
| `_reject_masked` (function) | Inspect missingness before NumPy can strip/stringify masks. |
| `_array` (function) | Implementation helper. Open its source for the algorithm. |
| `_sha` (function) | Implementation helper. Open its source for the algorithm. |
| `_digest` (function) | Implementation helper. Open its source for the algorithm. |
| `design_hash` (function) | Pin normalized binary64 structured coordinates and declared row/column order. |
| `outputs_hash` (function) | Pin all paired outputs plus statuses; this is integrity, not provenance proof. |
| `_validate` (function) | Implementation helper. Open its source for the algorithm. |
| `_indices` (function) | Pooled A/B ddof=0 variance, centered B Saltelli first and Jansen total. |
| `analyze` (function) | First/total indices and percentile base-block intervals per input/KPI. |

## atomic.py

Moved to ``avalanche_research.sources.atomic``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/atomic.py)

Imported components: `alias`.

## attributions.py

Moved to ``avalanche_research.datasets.derived.attributions``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/attributions.py)

Imported components: `alias`.

## binance.py

Moved to ``avalanche_research.sources.binance``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/binance.py)

Imported components: `alias`.

## builderhub.py

Moved to ``avalanche_research.sources.builderhub``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/builderhub.py)

Imported components: `alias`.

## catalog.py

Moved to ``avalanche_research.core.catalog``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/catalog.py)

Imported components: `alias`.

## catx.py

Moved to ``avalanche_research.sources.catx``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/catx.py)

Imported components: `alias`.

## cblocks.py

Moved to ``avalanche_research.sources.cblocks``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/cblocks.py)

Imported components: `alias`.

## cchain_rpc.py

Moved to ``avalanche_research.sources.cchain_rpc``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/cchain_rpc.py)

Imported components: `alias`.

## cli.py

Command-line interface for Avalanche Phase II research.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/cli.py)

| Component | Purpose from source |
| --- | --- |
| `module_for` (function) | Implementation helper. Open its source for the algorithm. |
| `parse_parameters` (function) | Implementation helper. Open its source for the algorithm. |
| `envelope` (function) | Implementation helper. Open its source for the algorithm. |
| `emit` (function) | Implementation helper. Open its source for the algorithm. |
| `finish` (function) | Implementation helper. Open its source for the algorithm. |
| `code_commit` (function) | The commit of the git checkout this package's source is tracked in, marked when tracked files under src differ from it, or "unknown" outside a checkout. |
| `show_version` (function) | Implementation helper. Open its source for the algorithm. |
| `cli` (function) | Inspect and reproduce Avalanche Phase II research. |
| `data` (function) | Inspect, retrieve, build, and check research data. |
| `list_data` (function) | List implemented sources and datasets. |
| `describe` (function) | Describe one source or dataset ID. |
| `fetch` (function) | Fetch one immutable source capture into a new directory. |
| `build` (function) | Build a normalized Parquet dataset from a capture. |
| `derive` (function) | Build a derived dataset from built runs into a new run directory with capture and dataset receipts. |
| `check_data` (function) | Check capture integrity, optional built output, and an optional reference cross-check. |
| `data_freshness` (function) | Read the newest record of each source live; any older than 36 hours, or unreadable, is a finding. |
| `list_runs` (function) | List built runs under data/runs for one dataset or for every dataset. |
| `data_pin` (function) | Write data/pins/NAME.json: one checked run per dataset, with its capture ID and Parquet hash. |
| `data_pin_check` (function) | Confirm every run a pin file names still exists, is unchanged, and still passes its check. |
| `manifest` (function) | Show the declared dataset manifest. |
| `model` (function) | Run, inspect and check the staking model and its source-linked protocol rules. |
| `describe_model` (function) | Show the mainnet staking parameters, upgrade schedule, and mechanism sources. |
| `model_reward` (function) | Compute the Primary Network potential reward for one stake. |
| `model_sweep` (function) | Run a sweep design file: one Parquet file per row under OUT, and the sweep's receipt beside them. |
| `model_run` (function) | Run one scenario from a pin file: one origin, model and seed, written as a one-row sweep under OUT. |
| `check_model` (function) | Recompute every captured potential reward from the formula and report disagreement by regime. |
| `main` (function) | Implementation helper. Open its source for the algorithm. |

## clist.py

Moved to ``avalanche_research.sources.clist``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/clist.py)

Imported components: `alias`.

## clist_daily.py

Moved to ``avalanche_research.datasets.derived.clist_daily``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/clist_daily.py)

Imported components: `alias`.

## coingecko.py

Moved to ``avalanche_research.sources.coingecko``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/coingecko.py)

Imported components: `alias`.

## core/__init__.py

The bottom layer: errors, hashing, units, the clock, the data catalog and each dataset's contract.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/core/__init__.py)

## core/aliases.py

Keep an old import path working after its module moves.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/core/aliases.py)

| Component | Purpose from source |
| --- | --- |
| `alias` (function) | Make ``old_name`` resolve to the module at ``new_name`` and return that module. |

## core/catalog.py

The data catalog: loading it, and each dataset's contract and its hash.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/core/catalog.py)

| Component | Purpose from source |
| --- | --- |
| `load_catalog` (function) | Implementation helper. Open its source for the algorithm. |
| `input_kind` (function) | ``endpoints`` for a REST source, ``queries`` for a database share, ``inputs`` for a derived source. |
| `contract` (function) | The parts of the catalog a capture depends on: the dataset's inputs and its fields. |
| `contract_hash` (function) | Implementation helper. Open its source for the algorithm. |
| `source` (function) | Implementation helper. Open its source for the algorithm. |
| `dataset` (function) | Implementation helper. Open its source for the algorithm. |

## core/clock.py

The current time as receipts record it, instants read in UTC, and the lockbox boundary.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/core/clock.py)

| Component | Purpose from source |
| --- | --- |
| `now` (function) | Implementation helper. Open its source for the algorithm. |
| `as_utc` (function) | Implementation helper. Open its source for the algorithm. |

## core/errors.py

The package's two error types.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/core/errors.py)

| Component | Purpose from source |
| --- | --- |
| `DataError` (class) | The requested data operation could not complete safely. |
| `ModelError` (class) | A protocol rule was asked to evaluate an input outside its domain. |

## core/hashing.py

The canonical JSON bytes and the hash that dataset contracts, receipts and pins are compared by.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/core/hashing.py)

| Component | Purpose from source |
| --- | --- |
| `canonical_bytes` (function) | Implementation helper. Open its source for the algorithm. |
| `sha256` (function) | Implementation helper. Open its source for the algorithm. |

## core/lockbox.py

The lockbox token: the only key that lets the model fit, select or tune on rows from the boundary on.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/core/lockbox.py)

| Component | Purpose from source |
| --- | --- |
| `Unseal` (class) | Proof that the unseal tag was on the remote when the token was issued. |
| `remote_tag` (function) | The tag's object id on the remote, or None when the remote has no such tag. |
| `issue` (function) | Implementation helper. Open its source for the algorithm. |
| `require` (function) | Refuse rows that reach the boundary unless a token built by ``issue`` is given. A token is an accident guard: it proves the unseal tag was on the remote when issued, not that the holder is the only scorer. |

## core/units.py

Units as AvalancheGo uses them: amounts in nAVAX integers, rates in millionths, durations in seconds.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/core/units.py)

Imported components: `annotations`.

## dataapi.py

Moved to ``avalanche_research.sources.dataapi``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/dataapi.py)

Imported components: `alias`.

## datasets/__init__.py

Notebook-facing access to built datasets by catalog ID.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/__init__.py)

| Component | Purpose from source |
| --- | --- |
| `_read_json` (function) | Implementation helper. Open its source for the algorithm. |
| `_try_json` (function) | Implementation helper. Open its source for the algorithm. |
| `runs` (function) | Built runs, newest capture first, for one dataset or for every dataset. |
| `_capture_time` (function) | A run's capture completion as an aware UTC instant, or None when it is missing or unreadable. |
| `select_run` (function) | Exactly one run chosen by exactly one rule, verified, with its capture, build and input identities. |
| `_select` (function) | Implementation helper. Open its source for the algorithm. |
| `readings` (function) | The built runs a capture's parameters name, for a capture module that declares ``READS``. |
| `receipt` (function) | The capture and build receipts of the named run, or of the newest build (the migration route). |
| `parquet_path` (function) | Path of the built Parquet file after verifying it against the build receipt. |
| `load` (function) | The built table as a pandas DataFrame with the catalog's types. |
| `canonical_view_name` (function) | The full catalog ID with dots and hyphens as underscores: ``p-chain-rpc.blocks`` becomes ``p_chain_rpc_blocks``. |
| `view_name` (function) | ``snowflake.primary-validator-stakes`` becomes ``validator_stakes``; ``coingecko.avax-market-daily`` becomes ``avax_market_daily``. |
| `views` (function) | View name to selected run for every dataset that has a built run (or the named run): each dataset under its canonical name, and under its older short name too when no other selected dataset shares that short name. |
| `connect` (function) | A DuckDB connection with one view per built dataset, so notebooks can join by the keys the datasets carry. |

## datasets/derived/__init__.py

Derived observations: tables built from captured runs, each with its own dataset ID, receipt and check.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/__init__.py)

## datasets/derived/attributions.py

Operator attributions: one row per name or role attached to a reward address, a funding address, or a node.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/attributions.py)

| Component | Purpose from source |
| --- | --- |
| `load_attributions` (function) | The curated rows and the file's hash, after the standard's rules: known tiers, classes, and subject kinds, one row per ID, a correction that names an existing row, and no EVIDENCE on an AS4 label or AS5 clustering alone. |
| `named_agents` (function) | Reward address to (name, evidence) for ``derived.operators``: the address's named row that no later row replaces, or "unnamed operator" when every row about it leaves the name open. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_input` (function) | Implementation helper. Open its source for the algorithm. |
| `compute` (function) | Implementation helper. Open its source for the algorithm. |
| `derive` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | The file still hashes as recorded, every named agent of the operator table has a classed row, every attributed reward address is an operator, and a rebuild gives the same rows. |

## datasets/derived/clist_daily.py

``derived.c-chain-evm-burn-daily``: the daily EVM fees of the C-Chain, from every built Data API block list run.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/clist_daily.py)

| Component | Purpose from source |
| --- | --- |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `daily_rows` (function) | One row per complete UTC day, in the share's columns. The first and last listed days are partial and left out. |
| `union_blocks` (function) | Every block of the given block list runs once, by height. A block two runs list differently is an error. |
| `derive` (function) | The daily table from every built block list run, or the one pinned. |
| `check` (function) | A rebuild from the recorded input is equal, and with ``--against`` a built ``snowflake.c-chain-evm-burn-daily``, every day both hold has the same burn. |

## datasets/derived/cycle_accounting.py

Cycle-recognised rewards and effective validator weights, preserving transaction grain.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/cycle_accounting.py)

| Component | Purpose from source |
| --- | --- |
| `columns` (function) | Implementation helper. Open its source for the algorithm. |
| `exists` (function) | Implementation helper. Open its source for the algorithm. |
| `records` (function) | Implementation helper. Open its source for the algorithm. |
| `prepare` (function) | Create cycle_events, monetary_reward_events and effective_stake_intervals. |

## datasets/derived/delegation_inputs.py

Delegation inputs at a model origin: the delegations open at the origin instant, each open validator's room for more delegation, and the year of delegation flows before it, by day and one row per started delegation. A model with delegations starts from this state, and its delegation blocks are fitted on these flows.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/delegation_inputs.py)

| Component | Purpose from source |
| --- | --- |
| `origin_instant` (function) | Implementation helper. Open its source for the algorithm. |
| `_connect` (function) | Implementation helper. Open its source for the algorithm. |
| `open_delegations` (function) | Every delegation open at the origin instant, with days left to its end and its validator's fee rate. |
| `validator_room` (function) | Every validator period open at the origin instant, its delegations open then, its weight limit and its room. |
| `scheduled` (function) | Validator and delegation periods accepted by the origin instant that start after it. |
| `flows` (function) | Daily delegation starts and ends in the ``days`` UTC days up to the origin day, BENQI's apart from the rest. |
| `refusals` (function) | Counts of the source conditions ``build`` refuses, each zero for valid inputs. |
| `starts` (function) | Every delegation started in the ``days`` UTC days up to the origin instant, one row each: its stake, its committed days from start to its stated end, BENQI's flag by the rule above, and its acceptance time. The daily flows' starts are these rows counted by day. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | The open delegations against the replay's stocks on the origin day, and room never below zero after Apricot 3. |

## datasets/derived/gci_monthly.py

``derived.gci-monthly``: one row per month of the Gross Chain Income study, from its captured inputs.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/gci_monthly.py)

| Component | Purpose from source |
| --- | --- |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_monthly_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `monthly_rows` (function) | The monthly table, over the months every input covers whole. |
| `derive` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | The monthly table: inputs unchanged and a rebuild equal. |

## datasets/derived/helicon.py

Validation commitments after Helicon: one row per validation cycle started at or after activation.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/helicon.py)

| Component | Purpose from source |
| --- | --- |
| `bin_case` (function) | The duration bin of an expression in days. |
| `_reject` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `_describe` (function) | Implementation helper. Open its source for the algorithm. |
| `select_inputs` (function) | The staking-period log pinned by ``dataset_id=run`` or its newest run, then every current snapshot run, oldest first. |
| `as_of_time` (function) | The newest snapshot capture time: the table holds every cycle observed up to this instant. |
| `_quoted` (function) | Implementation helper. Open its source for the algorithm. |
| `load_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `compute` (function) | Implementation helper. Open its source for the algorithm. |
| `_iso` (function) | Implementation helper. Open its source for the algorithm. |
| `_bins` (function) | Implementation helper. Open its source for the algorithm. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `comparison` (function) | Validator periods started in the COMPARISON_DAYS before activation, by the same bins. |
| `snapshot_gaps` (function) | The longest wait in hours between consecutive snapshots from the last one before activation on. Above 48 hours a minimum-length cycle can start and end unobserved. |
| `parameters` (function) | Implementation helper. Open its source for the algorithm. |
| `derive` (function) | Build the commitment table into a new run directory holding ``capture/`` and ``dataset/``. |
| `read_capture` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Verify the input runs still hash as recorded, the contract is unchanged, and the build holds: one row per cycle, every cycle starts at or after activation and lasts at least the Helicon minimum, every renewal starts where the previous cycle ended, and a rebuild from the recorded inputs gives the same rows. |

## datasets/derived/identity.py

Identity v0: dated identity edges and the operator groups they give at any instant, using only evidence before it.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/identity.py)

| Component | Purpose from source |
| --- | --- |
| `edges` (function) | One row per validator stake and reward address it names, earliest first. |
| `evidence_window` (function) | When evidence became public, as naive UTC: one instant for a time of day, the whole UTC day for a date alone. |
| `dated_names` (function) | AS1 evidence attributions of reward addresses not replaced by a later row, each dated by the identity events that name it: ``named_from`` is the earliest end of their evidence windows, from which the name surely applies, and ``evidence_from`` the earliest start, when it may first have been public. Both are minima, so the window does not depend on the order of the events. |
| `utc_naive` (function) | The stake log's times are naive UTC. An aware instant is converted to UTC first. |
| `groups` (function) | Every node with an edge dated on or before ``at``: its group by the addresses of its latest stake by then, the group's size, its name when one is dated by then, and every such name. At ``tier="AS1"`` only named addresses join nodes. |
| `resolve` (function) | The group of one node at ``at``: its id, members and name, or None when the node has no edge yet. |

## datasets/derived/market_layer.py

The market layer: what a validator could know when it made each commitment, one row per validator period.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/market_layer.py)

| Component | Purpose from source |
| --- | --- |
| `_quoted` (function) | Implementation helper. Open its source for the algorithm. |
| `decisions` (function) | Validator periods with the node's previous period, the delegations open on it at the decision, and its room. |
| `menu_rates` (function) | The protocol's annual rate for each menu duration, at each decision's stake, start and supply counter. |
| `upgrade_crossed` (function) | The first upgrade activated after a period's start and before its end, or None. |
| `as_of` (function) | Each series' last recorded value on a UTC day before the decision day. Days with no value, such as market holidays in the Treasury series, are skipped rather than read as missing. The price series repeats some dates, and the last observation of a day is taken. |
| `_observed_as_of` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |

## datasets/derived/monetary.py

The AVAX monetary daily ledger: one row per UTC date with issuance, burns by chain, realized supply, and active stake.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/monetary.py)

| Component | Purpose from source |
| --- | --- |
| `accounting_connection` (function) | A bounded connection with private spill storage, closed before its scratch directory is removed. |
| `_reject` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `_describe` (function) | Implementation helper. Open its source for the algorithm. |
| `_cycle_reference` (function) | Resolve the parent's exact recorded dependency, never a newest-run lookup. |
| `select_inputs` (function) | The input runs: one per single input, every current run per many-input. |
| `_window` (function) | The [start, end) UTC dates a Snowflake capture's query was bound with, or a seamed table is complete for. |
| `_input_order` (function) | Implementation helper. Open its source for the algorithm. |
| `load_inputs` (function) | Whole-row winners with their source runs; refuse conflicting equal-time/equal-authority rows. |
| `_epoch_date` (function) | Implementation helper. Open its source for the algorithm. |
| `compute` (function) | Build ``ledger`` from the input views: one row per UTC date from genesis to the burn-daily run's last day. |
| `burn_component_findings` (function) | Integer identities on the ledger. Gap repairs are an included subset of C-EVM, not another chain. |
| `_plain` (function) | Implementation helper. Open its source for the algorithm. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `gap_fee_agreement` (function) | Gap blocks whose fees both the Data API record and a node's receipts give, and how many of those differ. |
| `checkpoints` (function) | Each Data API supply snapshot against the ledger's cumulative totals through the day before and through its day. |
| `_cycle_diagnostic_amounts` (function) | Time/height-bounded recognition, held fees and current reservations. None retains the ordinary-only path. |
| `rewards_reconciliation` (function) | The API against recognised rewards, held delegation fees and earned current open shares. |
| `checkpoint_allowance` (function) | The AVAX a Data API total may sit outside the ledger's bracket for that day. |
| `judge_checkpoint` (function) | ``result`` with its gap and verdict under the current allowance, from the API value and the ledger's bracket it stores. The check judges from these values, so a run built under an earlier allowance is judged under this one. |
| `_bracket` (function) | Implementation helper. Open its source for the algorithm. |
| `counter_check` (function) | The last counter against genesis, recognised rewards, held fees and current reward reservations. |
| `derive` (function) | Implementation helper. Open its source for the algorithm. |
| `read_capture` (function) | Implementation helper. Open its source for the algorithm. |
| `_check_cycle_projection` (function) | Replay only recorded inputs and compare both published projections, without any newest-run resolution. |
| `check` (function) | Input hashes, the contract, daily conservation, supply continuity, coverage, and the provider checkpoints. |

## datasets/derived/monetary_periods.py

The monetary ledger summarized by network upgrade period: the upgrade-period table the validator study reads.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/monetary_periods.py)

| Component | Purpose from source |
| --- | --- |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `periods` (function) | (regime, start) from genesis through every upgrade, as naive UTC text. |
| `_inputs` (function) | The ledger's exact ordinary source and, for the new basis, its authenticated cycle companion. |
| `compute` (function) | Implementation helper. Open its source for the algorithm. |
| `_validate_parent_projection` (function) | Authenticate exact cycle event times against the recorded source walk, not only daily issuance sums. |
| `_totals` (function) | The ledger's own issuance and burn over all its days, in AVAX. |
| `derive` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Inputs unchanged, a rebuild equal, and the periods' issuance and burns summing to the ledger's. |

## datasets/derived/nodes.py

The node table: one row per Primary Network validator node, every attribute computed once from the staking-period log.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/nodes.py)

| Component | Purpose from source |
| --- | --- |
| `_reject` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `select_inputs` (function) | The input runs: pinned by ``dataset_id=run`` or the newest built run of each input. |
| `as_of_time` (function) | The validator capture time: the instant the clocks are clipped at. |
| `cycles_of` (function) | Nothing for a log with the Helicon cycle columns, else one cycle per period. |
| `load_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `compute` (function) | Implementation helper. Open its source for the algorithm. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `derive` (function) | Build the node table into a new run directory holding ``capture/`` and ``dataset/``. |
| `read_capture` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Verify the input runs still hash as recorded, the contract is unchanged, and the build holds: one row per node, every node has a reward address, the clocks are ordered, and the periods and rewards reconcile to the period log. |

## datasets/derived/observed_quotes.py

Strict prior observed-time price quotes, without a publication-availability claim.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/observed_quotes.py)

| Component | Purpose from source |
| --- | --- |
| `_sha256` (function) | Implementation helper. Open its source for the algorithm. |
| `normalize_utc` (function) | Validate known nonnumeric clocks and normalize them to nanosecond UTC. |
| `_value_identity` (function) | Implementation helper. Open its source for the algorithm. |
| `select_quotes` (function) | Return one strictly earlier whole price row per unique ``quote_key``. |

## datasets/derived/operators.py

Operators and fleets: one row per validator node with two groupings, so validator types can be fitted on operators.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/operators.py)

| Component | Purpose from source |
| --- | --- |
| `_agents_values` (function) | Implementation helper. Open its source for the algorithm. |
| `fleet_key` (function) | The fleet signature: entry and exit bucketed into ``weeks``-week UTC periods from Monday 2020-09-07, and the fee. |
| `stability_sql` (function) | Nodes whose fleet co-members change when the week bucket widens from FLEET_WEEKS to ``weeks``. |
| `_reject` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `_describe` (function) | Implementation helper. Open its source for the algorithm. |
| `select_inputs` (function) | The node table pinned by ``dataset_id=run``, or its newest run. |
| `_quoted` (function) | Implementation helper. Open its source for the algorithm. |
| `load_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `compute` (function) | Implementation helper. Open its source for the algorithm. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `parameters` (function) | Implementation helper. Open its source for the algorithm. |
| `derive` (function) | Build the table into a new run directory holding ``capture/`` and ``dataset/``. |
| `read_capture` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Verify the input run still hashes as recorded, the contract is unchanged, and the build holds: every node of the node table assigned exactly once, every node with an operator and a fleet, and a rebuild from the input gives the same rows. |

## datasets/derived/opportunity.py

What else AVAX could earn each day, beside what the protocol pays for staking it.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/opportunity.py)

| Component | Purpose from source |
| --- | --- |
| `_reject` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `select_inputs` (function) | The newest built run of each input, or the run ``pinned`` names for its dataset. |
| `native_rates` (function) | Approximate rates using realised ledger supply, explicitly distinct from the protocol counter. |
| `compute` (function) | ``result`` from the input views ``ledger``, ``tbill``, ``treasury`` and ``pools``. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `_load` (function) | Implementation helper. Open its source for the algorithm. |
| `derive` (function) | Build the table into a new run directory holding ``capture/`` and ``dataset/``. |
| `read_capture` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Input hashes, the contract, one row per day and series, and the table rebuilt from its inputs row for row. |

## datasets/derived/pburns.py

P- and X-Chain burns per UTC day from the nodes' own blocks: a second source for ``snowflake.primary-burn-daily``.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/pburns.py)

| Component | Purpose from source |
| --- | --- |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `l1_balance` (function) | The AVAX a transaction deposits into L1 validator balances. |
| `_select` (function) | Implementation helper. Open its source for the algorithm. |
| `compute` (function) | Implementation helper. Open its source for the algorithm. |
| `derive` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Inputs unchanged and a rebuild equal. With ``--against`` a built ``snowflake.primary-burn-daily``: every date and chain both hold has the same burn, L1 deposit, and L1 fee. |

## datasets/derived/pstaking.py

Stakes, rewards, and the supply counter rebuilt from a P-Chain block walk: a second source for four Snowflake datasets.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/pstaking.py)

| Component | Purpose from source |
| --- | --- |
| `_spec` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_describe` (function) | Implementation helper. Open its source for the algorithm. |
| `select_inputs` (function) | Each input pinned by ``dataset_id=run``, or its newest run. The staker captures must read the chosen walk. |
| `node_id` (function) | A node ID as every other table writes it. The node's JSON prints an AddAutoRenewedValidatorTx's nodeID as hex bytes; the usual form is ``NodeID-`` and CB58, base58 of the bytes and the last four bytes of their SHA-256. |
| `_utc` (function) | Implementation helper. Open its source for the algorithm. |
| `_addresses` (function) | Implementation helper. Open its source for the algorithm. |
| `_load` (function) | Implementation helper. Open its source for the algorithm. |
| `_stake` (function) | A Primary Network stake started by one walk transaction: its fields, or None for any other transaction. |
| `replay` (function) | The walk replayed from one starting counter: every stake with its potential reward, every closed stake with its outcome, the counter after each block, and each staking transaction's place in its block's supply changes. |
| `_cycle_row` (function) | A running cycle: its outcome columns stay null until its reward transaction and the commit or abort after it. |
| `_end_cycle` (function) | The counter after an auto-renewed validator's cycle ends with a commit or an abort, and the cycle's outcome. |
| `solve_start` (function) | The lowest and highest starting counters whose replay ends on the anchor, and the lowest one's replay. |
| `_validators` (function) | Validator periods a delegation can fall in: the walk's, the Data API's records and ended list, and the node's current ones. |
| `tables` (function) | The four tables' rows, in their Snowflake column order. |
| `compute` (function) | Implementation helper. Open its source for the algorithm. |
| `parameters` (function) | Implementation helper. Open its source for the algorithm. |
| `derive` (function) | Build one of the four tables into a new run directory holding ``capture/`` and ``dataset/``. |
| `_write` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Inputs unchanged, contract unchanged, and a rebuild from the recorded inputs gives the same rows. With ``--against`` the built Snowflake dataset this table backs up: every row both hold, over the hours both cover, is equal. |
| `compare` (function) | Row-for-row equality over the hours both tables cover: from the later first time to the earlier last time. A column the share leaves null because its load stopped (``rewarded``) is compared only where the share has it. |

## datasets/derived/scenario_inputs.py

Scenario inputs for revenue-funded rewards: one row per UTC day of the price, the chain's burns and issuance, fees and revenue, and every competing yield, from the series already captured. A model reads price paths, competing yields and a revenue path from here instead of from each source.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/scenario_inputs.py)

| Component | Purpose from source |
| --- | --- |
| `_quoted` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `_legacy_build` (function) | Implementation helper. Open its source for the algorithm. |
| `_observed_build` (function) | Implementation helper. Open its source for the algorithm. |

## datasets/derived/seam.py

Share rows before the seam, backup rows from it: one table per Snowflake dataset that stays current when the share stops.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/seam.py)

| Component | Purpose from source |
| --- | --- |
| `table_name` (function) | Implementation helper. Open its source for the algorithm. |
| `columns` (function) | Implementation helper. Open its source for the algorithm. |
| `resolve` (function) | The dataset and run to read for an input: its seamed table when one is built and neither is pinned. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `select_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `_view` (function) | Implementation helper. Open its source for the algorithm. |
| `p_seam` (function) | The first instant any of the share's four staking tables is incomplete, within its last day, or its last row. |
| `_conditions` (function) | Implementation helper. Open its source for the algorithm. |
| `compute` (function) | Create ``seamed`` and return the seam and the overlap comparison. Raises when the backup has not matched the share. |
| `_describe_rewards` (function) | Fill the stake columns of backup reward rows the walk could not describe from the share's stake rows. |
| `_window` (function) | [start, end) UTC dates the table is complete for: from the share query's start to the backup's last whole day. |
| `_load` (function) | Implementation helper. Open its source for the algorithm. |
| `derive` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Inputs unchanged, and a rebuild from them gives the same rows and the same seam. |

## datasets/derived/staking_periods.py

Derived datasets: deterministic transformations of built runs of other catalog datasets.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/staking_periods.py)

| Component | Purpose from source |
| --- | --- |
| `_reject` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `upgrade_schedule` (function) | Implementation helper. Open its source for the algorithm. |
| `select_inputs` (function) | The input runs: pinned by ``dataset_id=run`` or the newest built run of each input. |
| `load_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `compute` (function) | Build ``stakes`` from the input views, then fill ``kernel_reward_navax`` row by row from the protocol formula. |
| `reward_horizon` (function) | The latest reward the log holds: a period that ended later cannot have a reward row yet. The capture time is not used, because a seamed or lagging input holds data well short of when it was built. |
| `summarize` (function) | Counts over ``periods``; ``as_of`` is the latest reward the log holds, which separates ended periods from open ones. |
| `derive` (function) | Build the derived dataset into a new run directory holding ``capture/`` and ``dataset/``. |
| `read_capture` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Verify the input runs still hash as recorded, the contract and upgrade schedule are unchanged, and the build holds. |

## datasets/derived/subnets.py

Subnet and L1 validation by node: one row per node and Subnet, with the Subnet's L1 conversion.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/subnets.py)

| Component | Purpose from source |
| --- | --- |
| `_reject` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `_describe` (function) | Implementation helper. Open its source for the algorithm. |
| `select_inputs` (function) | Each input's run pinned by ``dataset_id=run``, or its newest run. |
| `_quoted` (function) | Implementation helper. Open its source for the algorithm. |
| `load_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `compute` (function) | Implementation helper. Open its source for the algorithm. |
| `_iso` (function) | Implementation helper. Open its source for the algorithm. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `parameters` (function) | Implementation helper. Open its source for the algorithm. |
| `derive` (function) | Build the table into a new run directory holding ``capture/`` and ``dataset/``. |
| `read_capture` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Verify the input runs still hash as recorded, the contract is unchanged, and the build holds: one row per node and Subnet, no Subnet period starting after its Subnet converted, every Subnet period inside a Primary Network period of the same node, and a rebuild from the recorded inputs gives the same rows. |

## datasets/derived/uptime_hourly.py

``derived.validator-uptime-hourly``: every built Builder Hub uptime capture merged into one row per node per hour.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/uptime_hourly.py)

| Component | Purpose from source |
| --- | --- |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_inputs` (function) | Every built capture under the current contract, oldest first, with the hash of its hourly table. |
| `_union` (function) | Implementation helper. Open its source for the algorithm. |
| `derive` (function) | Merge every capture: the newest capture's value for each node-hour, with how many captures held it and whether they agreed. |
| `check_derived` (function) | ``BC8``: the inputs still hash as recorded, and the table holds every node-hour of every input exactly once. |
| `check` (function) | ``BC8``, as ``check_derived``. |

## datasets/derived/weeks.py

The validator-week panel and the observed delegations it is read against, derived from the staking-period log.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/derived/weeks.py)

| Component | Purpose from source |
| --- | --- |
| `max_weight_sql` (function) | A validator's weight limit at a week start: five times its stake, and from Apricot Phase 3 at most 3M AVAX. AvalancheGo v1.4.5 checked only the factor until Apricot Phase 3 restored the cap (observed-delegations record RR2). |
| `_reject` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `inputs_of` (function) | Implementation helper. Open its source for the algorithm. |
| `select_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `load_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `quote` (function) | The protocol kernel's annualized reward rate of a 25 AVAX delegation starting at the cutoff (decision SD9). |
| `with_observed_market_prices` (function) | Named successor of a weekly market table using strictly earlier quotes at most24h old. |
| `compute` (function) | Build ``panel`` and ``observed`` from the input views. ``known_until`` drops every transaction accepted from then on, which is how the check proves that earlier rows do not depend on later events. |
| `reason_counts` (function) | Delegations per reason code, the null code named ``offered`` or ``eligible``, so each set sums to the row count. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `derive` (function) | Build one of the two tables into a new run directory holding ``capture/`` and ``dataset/``. |
| `read_capture` (function) | Implementation helper. Open its source for the algorithm. |
| `invariance` (function) | Rows for weeks before ``cutoff`` built from every input against the same rows built from transactions accepted before ``cutoff`` only. No row in either set and not the other proves no early row reads a later event. |
| `check` (function) | Input hashes, the contract, the columns, one row per key, every delegation accounted for, and the append-future rule: early rows rebuilt from truncated inputs equal the full build's. |

## datasets/pins.py

Pinned input sets: a named list of built runs that a model or study reads, frozen with each run's hashes.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/datasets/pins.py)

| Component | Purpose from source |
| --- | --- |
| `_check_status` (function) | Implementation helper. Open its source for the algorithm. |
| `_resolve` (function) | The full commit a revision names in ``repo``, or None. |
| `code_findings` (function) | What no longer holds for a pin's code: a commit that does not resolve here, or a ref that points elsewhere. |
| `pin` (function) | Write ``<directory>/<name>.json`` for these datasets. Every pinned run must have passed its check. |
| `read` (function) | Implementation helper. Open its source for the algorithm. |
| `entry_findings` (function) | What no longer matches for one pinned run: missing, a changed Parquet file, another dataset or capture, or a check that no longer passes. |
| `verify` (function) | What no longer matches: a missing run, a changed Parquet file, a check that no longer passes, or named code that no longer resolves. |
| `runs` (function) | Dataset ID to pinned run, for a reader that passes it to ``datasets.load``. |

## defillama.py

Moved to ``avalanche_research.sources.defillama``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/defillama.py)

Imported components: `alias`.

## derived.py

Moved to ``avalanche_research.datasets.derived.staking_periods``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/derived.py)

Imported components: `alias`.

## domain/__init__.py

The chain's rules and every measure, as functions of tables passed in. Nothing here loads data.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/domain/__init__.py)

## domain/keys.py

The key behind a signed C-Chain transaction, and that key's EVM and P-Chain addresses.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/domain/keys.py)

| Component | Purpose from source |
| --- | --- |
| `_rotate` (function) | Implementation helper. Open its source for the algorithm. |
| `_permute` (function) | Implementation helper. Open its source for the algorithm. |
| `keccak256` (function) | Ethereum's Keccak-256, the original padding, not SHA3-256. |
| `_rlp` (function) | Implementation helper. Open its source for the algorithm. |
| `_length` (function) | Implementation helper. Open its source for the algorithm. |
| `_integer` (function) | Implementation helper. Open its source for the algorithm. |
| `_hex_bytes` (function) | Implementation helper. Open its source for the algorithm. |
| `_add` (function) | Implementation helper. Open its source for the algorithm. |
| `_multiply` (function) | Implementation helper. Open its source for the algorithm. |
| `signing_hash` (function) | The hash the sender signed, and the recovery ID, for a legacy EIP-155 or an EIP-1559 transaction. |
| `recover_public_key` (function) | Implementation helper. Open its source for the algorithm. |
| `_bech32` (function) | Implementation helper. Open its source for the algorithm. |
| `addresses` (function) | The signer's EVM address and P-Chain address. Raises when the recovered EVM address is not the sender. |

## domain/protocol/__init__.py

Source-linked Avalanche Primary Network staking and reward rules.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/domain/protocol/__init__.py)

| Component | Purpose from source |
| --- | --- |
| `reward_config_for_stake_start` (function) | ACP-285 ramp: vms/platformvm/reward/calculator.go configForStakeStart. |
| `potential_reward` (function) | vms/platformvm/reward/calculator.go Calculate, with the Go big-integer operation order. |
| `primary_network_reward` (function) | vms/platformvm/reward/calculator.go primaryNetworkCalculator.Calculate: ACP-285 applied per stake start. |
| `annualized_reward_rate` (function) | Reward per unit staked, scaled to the minting period. Matches the ARR tables in ACP-285. |
| `split_reward` (function) | vms/platformvm/reward/calculator.go Split: (amount from shares, remainder). |
| `supply_after_stake_start` (function) | Current supply after a stake starts: the potential reward is added before it is earned. |
| `supply_after_stake_end` (function) | Current supply after a stake ends: unchanged when rewarded, minus the potential reward when not. |
| `start_stake` (function) | (potential reward, current supply after the start) for one Primary Network stake. |
| `start_stakes_in_order` (function) | Potential rewards and the final current supply for stakes (start, duration seconds, amount) in event order. |
| `effective_stake_start` (function) | When a stake starts: the requested start before Durango, the chain time of acceptance from Durango (ACP-41). |
| `staker_start_time_error` (function) | Before Durango a stake's requested start must be strictly after the chain time. From Durango it is ignored. |
| `promote_pending_stakes` (function) | Potential rewards, in input order, and the final supply for pending stakes (tx type, start, end, amount). |
| `min_stake_duration_seconds` (function) | Minimum Primary Network stake duration for a stake verified at chain time ``at``, by role. |
| `delegation_within_validator_period` (function) | A delegation must lie inside its validator's current period, bounds included. |
| `delegation_window_open` (function) | Whether a delegation of the minimum delegator duration starting at ``delegation_start`` fits the validator. |
| `uptime_requirement` (function) | ACP-267: 90% for validation periods starting at or after Helicon, else the genesis 80%. |
| `uptime_fraction` (function) | Uptime as the node's up time over the time since its validator period started, 1 for an empty window. |
| `uptime_passes` (function) | Whether a stake ending now is rewarded: uptime at or above the requirement for the validator's start. |
| `validator_rewards_at_end` (function) | (validation reward paid, delegation fees paid) when a non-renewing validator ends. |
| `delegator_rewards_at_end` (function) | (delegator reward, validator fee) when a delegation ends, judged on its validator's uptime. |
| `delegation_fee_deferred` (function) | Whether a validator's delegation fees wait until its own end. Keyed to the validator's start, not the delegation's: AvalancheGo 70bd6d0 vms/platformvm/txs/executor/proposal_tx_executor.go L668 (Cortina). |
| `settle_delegation_fee` (function) | (fee paid at the delegation's end, validator's accrued delegatee reward after) for one rewarded delegation. |
| `auto_renew_continues` (function) | Whether an ACP-236 validator starts another cycle at its cycle end. |
| `auto_renew_exit_rewards` (function) | (validation rewards paid, delegatee rewards paid) when an ACP-236 validator leaves at a cycle end. |
| `auto_renew_restake` (function) | (restaked validation, restaked delegatee, withdrawn validation, withdrawn delegatee) at a renewal. |
| `auto_renew_next_cycle` (function) | (cycle end, potential reward, current supply after) for the next ACP-236 cycle. |
| `max_validator_weight_navax` (function) | Total weight a validator may carry: self stake plus delegations up to the multiplier, capped by the maximum stake. |
| `with_scenario_upgrade` (function) | The schedule with one hypothetical upgrade added in time order, for policy scenarios such as ACP-247. |
| `delegation_multiplier` (function) | Delegation allowed per unit of self-stake at the chain time a delegation is verified: 4, or 24 once a scenario schedule has activated ACP-247. |
| `delegation_weight_limit_navax` (function) | Total weight a delegation may not push its validator above, at the chain time of verification. |
| `peak_validator_weight_navax` (function) | Largest total weight on a validator between ``start`` and ``end`` given its delegations (start, end, weight). |
| `over_delegated` (function) | AvalancheGo 70bd6d0 staker_tx_verification_helpers.go L120-L141 overDelegated: peak weight plus the new delegation above the limit (delegation_weight_limit_navax) rejects the delegation. |
| `validator_admission_error` (function) | First parameter rule a Primary Network validator breaks, or None. ``start`` is the effective start: the chain time of verification from Durango, the requested start before it. |
| `auto_renewed_validator_admission_error` (function) | First rule an AddAutoRenewedValidatorTx breaks, or None. |
| `auto_renewed_config_error` (function) | First rule a SetAutoRenewedValidatorConfigTx period breaks, or None. A period of 0 requests exit. |
| `delegator_admission_error` (function) | First rule a Primary Network delegation breaks, or None. ``start`` is the effective start. |
| `gas_price` (function) | minPrice * e^(excess / K) by the EIP-4844 fake exponential, capped at MaxUint64. |
| `fee_excess_after` (function) | Excess after ``seconds`` at a constant usage: (current - target) per second, floored at 0, capped at MaxUint64. AvalancheGo 70bd6d0 vms/platformvm/validators/fee/fee.go L29-L44 AdvanceTime and vms/components/gas/gas.go L28-L56. |
| `l1_validator_fee_navax` (function) | nAVAX one active L1 validator pays over ``seconds`` with a constant active count, capped at MaxUint64. |
| `l1_validator_seconds_remaining` (function) | Seconds an L1 validator balance lasts before the validator is deactivated, capped at ``max_seconds``. |
| `p_chain_gas` (function) | Gas of a transaction: its complexity dimensions weighted and summed. |
| `p_chain_fee_state_after` (function) | (capacity, excess) after ``seconds`` without transactions: capacity refills at MaxPerSecond up to MaxCapacity and excess drains at TargetPerSecond to 0. AvalancheGo 70bd6d0 vms/components/gas/state.go L29-L42 AdvanceTime, applied each block at vms/platformvm/txs/executor/state_changes.go L325-L338. |
| `p_chain_consume_gas` (function) | (capacity, excess) after a block consumes ``gas``: capacity falls and excess rises, capped at MaxUint64. |
| `p_chain_tx_fee_navax` (function) | Fee burned by one P-Chain transaction, such as a stake or an ACP-236 config change. |
| `subnet_validator_admission_error` (function) | First rule an AddSubnetValidatorTx breaks, or None. ``start`` is the effective start. |
| `describe` (function) | Implementation helper. Open its source for the algorithm. |

## domain/protocol/types.py

Typed units, parameters, upgrades, and mechanism descriptions for the Avalanche staking subsystem.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/domain/protocol/types.py)

| Component | Purpose from source |
| --- | --- |
| `RewardConfig` (class) | Mirror of vms/platformvm/reward/config.go Config. |
| `StakingConfig` (class) | Mirror of genesis/params.go StakingConfig. |
| `ValidatorFeeConfig` (class) | Mirror of vms/platformvm/validators/fee/fee.go Config: the ACP-77 continuous L1 validator fee. |
| `DynamicFeeConfig` (class) | Mirror of vms/components/gas/config.go Config: the ACP-103 P-Chain gas fee. |
| `Upgrade` (class) | Implementation helper. Open its source for the algorithm. |
| `UpgradeSchedule` (class) | Ordered network upgrades. Activation is inclusive: an event at the activation instant is activated. |
| `Mechanism` (class) | One protocol rule, the upgrade that changes it, what its activation is keyed by, and its sources. |

## etf.py

Moved to ``avalanche_research.sources.etf``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/etf.py)

Imported components: `alias`.

## experiments/__init__.py

Experiments: design tables, the run pool, and the evidence receipt every model run carries. v0, unreviewed.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/experiments/__init__.py)

## experiments/receipt.py

The evidence receipt of a model run: what ran, on which inputs, with which seeds, what it checked, and what it made.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/experiments/receipt.py)

| Component | Purpose from source |
| --- | --- |
| `specification_hash` (function) | The engine's hash of a specification: sha256 of its sorted JSON, first 16 hex digits. |
| `table_sha256` (function) | A hash of the long table that does not depend on row order or on a file format: sorted rows as CSV. |
| `code_commit` (function) | The commit the code ran from, and whether tracked source files differed from it. |
| `build` (function) | The receipt of one run or sweep. ``conservation`` holds one entry per check: name, passed, worst error, tolerance. |
| `row_file_sha256` (function) | A hash of a row file's contents, not its bytes: every column but the measured worker memory, which differs between identical reruns, with rows sorted on every column and written as CSV. Parquet metadata does not enter it. |
| `_base_specifications` (function) | Implementation helper. Open its source for the algorithm. |
| `_file_hashes` (function) | Implementation helper. Open its source for the algorithm. |
| `build_sweep` (function) | The receipt of a sweep whose rows the runner wrote under ``out``, one Parquet file per row. It lists every base model's specification, one for each origin and model. |
| `check` (function) | What makes the receipt unfit as evidence. An empty list means it stands. |
| `write` (function) | Write the receipt only if it stands. A receipt whose pins fail ``pin-check`` is refused. |

## experiments/sweep.py

A sweep from a design file: rows, base models built from pinned data, the row runner, and the sweep's receipt.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/experiments/sweep.py)

| Component | Purpose from source |
| --- | --- |
| `builder` (function) | The base model for an origin and model name, from the pinned staking periods, with ``draws`` attached to a v0.8 base when given. |
| `rows` (function) | The design's rows, crossed with its origins and models, with the index running over the whole design. |
| `KpiReducer` (class) | One row per run, KPI, horizon and cost level, from each run's daily table after the chain's table to its origin. By default a measure whose inputs the run does not produce is left out. ``missing='raise'`` refuses it. |
| `kpi_reducer` (function) | The design's KPI reducer with the chain's daily table for each origin, or None when it keeps daily paths. |
| `load_draws` (function) | The design's table of parameter draws, or None. Its required ``draws_sha256`` must match the file. |
| `pinned_periods` (function) | The staking periods' Parquet path and run that a pin names, after the whole pin verifies. |
| `scenario` (function) | A one-row design: one origin, one model and one seed from a pin file. |
| `run` (function) | Run the design, a file or its dictionary, into ``out`` and write ``receipt.json`` beside its rows. ``pin`` replaces the design's pin file. Returns the receipt. |

## freshness.py

How fresh each data source is: the time of its newest record, read live, against a 36-hour limit.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/freshness.py)

| Component | Purpose from source |
| --- | --- |
| `_utc` (function) | Implementation helper. Open its source for the algorithm. |
| `_post` (function) | Implementation helper. Open its source for the algorithm. |
| `p_chain_head` (function) | Implementation helper. Open its source for the algorithm. |
| `tenderly_head` (function) | Implementation helper. Open its source for the algorithm. |
| `data_api_p_head` (function) | Implementation helper. Open its source for the algorithm. |
| `metrics_point` (function) | Implementation helper. Open its source for the algorithm. |
| `snowflake_tables` (function) | The newest row of each share table, or the error that stopped the read. |
| `walk_newest` (function) | The newest record of this repository's own latest built walk. |
| `probes` (function) | Each source's name and a call that returns the time of its newest record. |
| `measure` (function) | One row per source: its newest record, its age in hours, and fresh, stale, known stale, or error. |

## gci.py

Moved to ``avalanche_research.sources.gci``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/gci.py)

Imported components: `alias`.

## gci_monthly.py

Moved to ``avalanche_research.datasets.derived.gci_monthly``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/gci_monthly.py)

Imported components: `alias`.

## helicon.py

Moved to ``avalanche_research.datasets.derived.helicon``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/helicon.py)

Imported components: `alias`.

## mechanisms/__init__.py

Mechanisms: tunable Param versions of the rules governance could change.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/mechanisms/__init__.py)

Imported components: `AdmissionRule`, `BoundedHarmonicFrontier`, `ChainAdmission`, `ACP285Ramp`, `ChainReward`, `QuadraticReward`, `RewardMechanism`, `TenureBoost`.

## mechanisms/admission.py

Admission mechanisms as Param classes: which validator stakes the chain accepts, by duration.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/mechanisms/admission.py)

| Component | Purpose from source |
| --- | --- |
| `AdmissionRule` (class) | Which validator stakes are admitted. The base class is the chain's flat minimum. |
| `ChainAdmission` (class) | Mainnet: 2,000 AVAX minimum for any duration in the allowed range. |
| `BoundedHarmonicFrontier` (class) | Hash's admission frontier, the bounded harmonic curve of 2026-09-29. |

## mechanisms/cohort.py

A reference cohort of real stakes, grouped so every mechanism can reprice it quickly.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/mechanisms/cohort.py)

| Component | Purpose from source |
| --- | --- |
| `with_tenure` (function) | Staking periods accepted inside ``window``, each with its tenure and whole-day duration. |
| `validator_periods` (function) | Individual validator periods inside ``window``, for rules that judge each stake on its own. |
| `group_stakes` (function) | Periods inside ``window`` summed by role, whole-day duration, and tenure, for rules linear in stake. |
| `load_periods` (function) | The columns ``group_stakes`` needs, read from a built ``derived.staking-periods`` file. |

## mechanisms/reward.py

Reward mechanisms as Param classes.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/mechanisms/reward.py)

| Component | Purpose from source |
| --- | --- |
| `RewardMechanism` (class) | The potential reward of one stake. The base class is the chain's rule. |
| `ChainReward` (class) | Mainnet as it runs: the linear rate, with ACP-285 applied at each stake's start since Helicon. |
| `ACP285Ramp` (class) | ACP-285's ramp with its target and length as settings. The defaults are the chain since Helicon. |
| `TenureBoost` (class) | A reward that rises with a validator's tenure, the Foundation's written research question of 2026-05-07. |
| `QuadraticReward` (class) | A rate convex in duration: rate(d) = min + (max - min) * (d / T) ** exponent. |

## metrics.py

Moved to ``avalanche_research.sources.metrics``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/metrics.py)

Imported components: `alias`.

## model/__init__.py

Avalanche staking subsystem model: typed units, source-linked protocol rules, and checks.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/__init__.py)

## model/backtest.py

Recompute captured potential rewards from the protocol formula and report disagreement by regime.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/backtest.py)

| Component | Purpose from source |
| --- | --- |
| `_parquet` (function) | Implementation helper. Open its source for the algorithm. |
| `backtest` (function) | Recompute potential_reward_navax for every validator and delegator row from the formula. |

## model/blocks.py

Behaviour blocks: one Param class per decision, with a shared interface.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/blocks.py)

| Component | Purpose from source |
| --- | --- |
| `behavioural` (function) | A behavioural parameter with its source and evidence in the Param metadata. |
| `BehaviourBlock` (class) | One decision of one kind of agent. |
| `Renewal` (class) | Whether a validator commitment that ends is followed by a new one on the same node within seven days. |
| `_outcomes` (function) | Observed yes or no decisions, one per input row. Anything else is refused. |
| `check_writers` (function) | Refuse a set of blocks in which two write the same state variable. |
| `check_sources` (function) | Refuse a block with a numeric parameter that has no declared source, or an unlabelled instance value. |

## model/delegated_lifecycle.py

The fitted validator lifecycle with delegations, and delegator rewards counted in issuance.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/delegated_lifecycle.py)

| Component | Purpose from source |
| --- | --- |
| `_integral` (function) | Whether one value is exactly a whole number: an integer, or a finite float or Decimal with no fraction. A boolean, text or a missing value is not. |
| `_whole` (function) | ``values`` as int64, refusing any that is not a whole number in int64's range, checked before the cast, rather than truncating or wrapping it. |
| `_identified` (function) | Refuse a missing or blank transaction hash in ``values``, before anything is matched by it. |
| `_closing_days` (function) | Each named operator's closing day as a float, infinite when it does not close (a missing value). A day given is read exactly and must be a whole number within int64, checked before any conversion. |
| `_operators` (function) | Each delegation's named operator row, -1 for none, from an ``operator`` column or none. |
| `_validator_keys` (function) | Implementation helper. Open its source for the algorithm. |
| `DelegatedLifecycle` (class) | Validator commitments, the nodes out of the set, and the delegations on the active validators. |
| `_days_after` (function) | The UTC day, counted from the origin, whose end is the first at or after each time. |
| `_validator_order` (function) | The validator periods behind the fitted lifecycle's ``initial`` and ``scheduled`` rows, each with its transaction hash and stake: those open at the origin's last instant, and those accepted by it that start after it. |
| `delegation_inputs` (function) | This model's delegation inputs at ``origin`` from the origin's delegation tables, ``open``, ``validators`` and ``scheduled``, and the fitted lifecycle's ``state`` (``initial``, ``scheduled`` and their ``transactions``) built from the same periods. |
| `delegation_terms` (function) | The delegations that started in the 365 days to the origin's last instant, in start order, each with its stake, its whole days from the day it starts to the day it ends, and whether it is BENQI's: funded by ``benqi_funding`` and accepted at or after ``benqi_from``. Its end counts its last cycle. Each row keeps its ``transaction_hash``, by which a consumer matches it to the same delegation in another table. The model reads only the other columns. |
| `historical_flow` (function) | The flow block fitted to the daily delegation starts of the 365 UTC days to the origin day, a day with none counting as zero. Each row's count is checked as a whole, non-negative number before any sum, and so is the total, so no daily sum can pass int64. |

## model/delegation_blocks.py

The delegation blocks: how many delegations start each day, and which validator each one goes to.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/delegation_blocks.py)

| Component | Purpose from source |
| --- | --- |
| `DelegationFlow` (class) | How many delegations start each day, and how many of them are BENQI's. |
| `_set_ids` (function) | Implementation helper. Open its source for the algorithm. |
| `_group_log_softmax` (function) | Implementation helper. Open its source for the algorithm. |
| `_ConditionalChoice` (class) | A conditional logit over one choice set per decision: utility is ``design(inputs) @ coefficients``. |
| `_log_capacity` (function) | Implementation helper. Open its source for the algorithm. |
| `DelegatorChoice` (class) | The validator a delegator other than BENQI chooses: utility = fee * fee share + log_capacity * log capacity. |
| `BenqiAllocation` (class) | The validator BENQI delegates to among the eligible ones of its set: probability proportional to remaining capacity to the power ``capacity_power``. The inputs are ``remaining_navax`` for each eligible validator. |

## model/designs.py

Design rows for a sweep: each row is one complete setting of the model, yielded whole, so a runner never needs to know how rows were chosen.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/designs.py)

| Component | Purpose from source |
| --- | --- |
| `row_id` (function) | The row's identity: a hash of the base specification hash and the row, 16 hex digits. |
| `settings` (function) | The model settings a row changes: everything but its identity and the keys that pick its base model. |
| `check_origins` (function) | Refuse a design with an origin inside the validation lockbox, before any model is built. |
| `cartesian` (function) | Every combination of ``levels``, in the order the keys are given. |
| `sobol` (function) | ``2**m`` scrambled Sobol rows in ``bounds``, from row ``start`` on. A design extended or resumed from ``start`` yields the same rows as one generated whole. |
| `design_hash` (function) | One hash of a whole design's row ids, in order, so the design can be reviewed and fixed before launch. |
| `check_cardinality` (function) | Refuse a design with the wrong number of rows, or with two rows that are the same setting. |
| `no_effect` (function) | The swept settings that moved no output in a pilot: holding every other setting fixed, every level gave the same ``outcome`` at every (variable, timestep, run). Under the chain's own reward rule both responses fail this, because the yield gap they multiply is zero. |

## model/engine.py

Run a cadCAD model whose settings are Param declarations, and return one long table.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/engine.py)

| Component | Purpose from source |
| --- | --- |
| `InvariantError` (class) | A state broke one of its model's invariants. |
| `SimulationModel` (class) | A cadCAD model described by Param settings, an initial state, and partial state update blocks. |
| `_plain` (function) | A setting as plain data. A Param object becomes its class and settings, without its generated name. |
| `_digest` (function) | A content hash of an input table or array, so the specification hash changes when the inputs do. |
| `_column_value` (function) | A setting as a table cell. A Param object shows its label, with a short settings hash when another object in the same sweep shares the label but not the settings, so their rows never merge. |
| `_execute` (function) | Implementation helper. Open its source for the algorithm. |
| `_long_table` (function) | Implementation helper. Open its source for the algorithm. |
| `run` (function) | Execute one model and return its long table. |
| `sweep` (function) | Execute the model once for every combination of the values in ``grid``. |

## model/evaluation.py

Scoring a forecast from an origin against the validation protocol's naive benchmarks.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/evaluation.py)

| Component | Purpose from source |
| --- | --- |
| `_before` (function) | Implementation helper. Open its source for the algorithm. |
| `actual_at` (function) | The realized value ``horizon_days`` after the origin. |
| `persistence` (function) | ``N1``: the value at the origin. |
| `drift` (function) | ``N2``: the origin value plus ``horizon_days`` times the mean daily change over ``window_days`` before it. |
| `reduced_form` (function) | ``N3``: an AR(1) on weekly changes, fitted by least squares on weeks ending at the origin, then iterated. |
| `benchmarks` (function) | Each benchmark's forecast at each horizon, one row per benchmark and horizon. |
| `mase_scale` (function) | The mean absolute one-day change up to the origin, the denominator of the scaled error. |
| `scaled_error` (function) | The absolute error in units of the mean one-day change before the origin. |
| `diebold_mariano` (function) | Whether forecast A has lower expected loss than forecast B. |
| `_sorted` (function) | Implementation helper. Open its source for the algorithm. |
| `crps_ensemble` (function) | ``E\|X - y\| - E\|X - X'\| / 2`` for the sample, by the sorted-sample identity. |
| `crps_normal` (function) | The CRPS of a normal forecast: ``sd * (z * (2 Phi(z) - 1) + 2 phi(z) - 1 / sqrt(pi))``. |
| `pit` (function) | The forecast's probability below the realized value, counting half of any probability exactly on it. |
| `central_interval` (function) | The central interval holding ``level`` of the forecast, by the linear quantile rule. |
| `interval_score` (function) | The width plus ``2 / alpha`` times any miss, ``alpha = 1 - level`` (Gneiting and Raftery, 2007). |
| `dressed` (function) | ``N1d`` or ``N2d``: a benchmark spread by every ``horizon_days`` change that ends by the origin. |
| `_local_level_filter` (function) | Log-likelihood, filtered level and its variance, conditioning on the first value. |
| `fit_local_level` (function) | Maximum-likelihood fit of ``y[t] = mu[t] + eps``, ``mu[t+1] = mu[t] + eta``. |
| `local_level` (function) | ``N4``: the mean and standard deviation of the local-level forecast fitted on every day to the origin. |
| `distribution_scores` (function) | CRPS, PIT, 50% and 80% coverage, the 80% interval score and width, with CRPS, score and width over ``scale``. |
| `dm_horizon` (function) | The Diebold-Mariano horizon: one plus the most later origins that fall inside one forecast's window. |
| `chronological` (function) | ``origins`` sorted by their dates in ``dates``, a mapping or Series from origin to date, for lagged tests. |
| `_real` (function) | A column of real numbers as floats. Other types, and integers too large to hold exactly as floats, are refused, since converting them would lose information. |
| `_flag` (function) | A test result as True, False or None. NumPy booleans count as booleans, and any other value is refused. |
| `_utc_days` (function) | Each value as a naive UTC midnight. A date or datetime is read on its own, a zoned one in UTC, and text only in the forms ``_ISO_DAY`` allows; any other type or text, or any instant that is not a UTC midnight, is refused, so an origin is always one calendar day. |
| `adoption_verdict` (function) | Whether a challenger block replaces the incumbent, by a rule fixed before either is scored. |

## model/fitted_blocks.py

The fitted lifecycle model's behaviour blocks, under the path they had before they moved to one module per part.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/fitted_blocks.py)

Imported components: `annotations`, `Mapping`, `lgamma`, `optimize`, `special`, `stats`, `Arrivals`, `_negative_binomial_log_prob`, `AVAX`, `DURATION_EDGES`, `RENEWAL_DAYS`, `RETURN_DAYS`, `BehaviourBlock`, `_outcomes`, `behavioural`, `MOVE_STAKE_EDGES`, `Continuation`, `NODE_PRIOR_GRID`, `RENEWAL_STAKE_EDGES`, `RENEWAL_TERMS`, `TENURE_BINS`, `RenewalLogit`, `_coefficient`, `_newton`, `renewal_design`, `tenure_bin`, `RETURN_CELLS`, `RETURN_DAY_EDGES`, `RETURN_STAKE_EDGES`, `ReturnHazard`, `_hazard`, `return_cell`.

## model/fitted_lifecycle.py

v0.8: the validator lifecycle with behaviour fitted to the chain before an origin.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/fitted_lifecycle.py)

| Component | Purpose from source |
| --- | --- |
| `_array` (function) | Implementation helper. Open its source for the algorithm. |
| `_column` (function) | A column as an array, or zeros when the frame does not have it, as for a table built before ``returns`` existed. |
| `FittedLifecycle` (class) | Validator commitments and the nodes out of the active set, stepped one UTC day at a time from an origin. |
| `nakamoto_third_nodes` (function) | The fewest nodes whose open stake together exceeds one third of all open stake, each node's commitments summed by its key. Zero when nothing is open. |
| `_continuation_tables` (function) | Implementation helper. Open its source for the algorithm. |
| `resampled_tables` (function) | ``moves`` and ``first`` resampled by ``node_code``, as many nodes as each holds, from the run's ``continuation_resample`` stream under ``resample_seed``. |
| `_drawn` (function) | ``block`` with every parameter that ``row`` holds under ``prefix`` replaced, labelled as that run's draw. |
| `node_resample` (function) | Row indices of a bootstrap by node: as many nodes as there are, drawn with replacement, each with all its rows. |
| `window_tau` (function) | The SD of the renewal log-odds shift between quarters, net of binomial noise. |
| `renewal_quarters` (function) | Each calendar quarter of renewal endings that ended seven days before ``through_us``, so every ending in it is labelled, and that holds at least 200 endings: its count, its observed share renewed, and the mean probability ``renewal`` gives the same endings. |
| `window_sd_from_quarters` (function) | τ from a :func:`renewal_quarters` table, and its source. With fewer than eight quarters it is the assumed 0.18, the median of earlier in-sample estimates. |
| `window_sd` (function) | τ at ``origin``: the drift of the renewal log-odds between quarters, net of binomial noise, measured against the origin's fitted ``renewal`` block on every labelled quarter before the origin. An origin in the lockbox is refused. |
| `arrival_block_sample` (function) | A moving-block bootstrap of daily counts: whole runs of ``block_days`` consecutive days, drawn with replacement and joined, the last cut so the sample is as long as ``counts``. Whole blocks keep the week-to-week correlation that resampling single days would break. For 365 days that is 14 blocks, the last cut to one day. |
| `_prefixed` (function) | Implementation helper. Open its source for the algorithm. |
| `parameter_draws` (function) | ``n`` draws of every fitted block parameter, one row per run, for the ``draws`` input of :class:`FittedLifecycle`. |
| `clipped_draws` (function) | The number of draws with any renewal log-odds term at the fit's ±20 clip, where a separable cell in a resample sends a coefficient to its bound. The node record's prior strength and the renewal shift are not log-odds terms. |
| `_day` (function) | Implementation helper. Open its source for the algorithm. |
| `decided_by_us` (function) | The last instant of the origin's UTC day in microseconds, by which every move in the origin's tables started. |
| `fit_durations` (function) | The duration band transition fitted on the moves of the 365 days before the origin, the same moves the continuation table holds, without its day record. See :func:`~avalanche_research.model.parts.duration_transition.fit_moves`. |
| `_fit_return_history` (function) | Implementation helper. Open its source for the algorithm. |
| `fit_return_history` (function) | The logit return hazard on the node's own history, fitted on the return block's own spells: the endings without renewal in the 730 days before the origin, each followed until it returned or the origin came. See :class:`~avalanche_research.model.parts.return_hazard.ReturnLogitHazard`. |
| `_whole_days` (function) | A timestamp in microseconds as the UTC day whose end is the first at or after it, as the replay counts days. |
| `validator_periods` (function) | Validator commitments that started by ``through_us``, each with its node's neighbours and the terms the blocks read. |
| `renewal_endings` (function) | The renewal decisions of commitments that ended after ``after_us`` and by ``through_us``, as ``AM2`` counts them. |
| `renewal_inputs` (function) | The inputs :class:`RenewalLogit` reads, from rows of :func:`renewal_endings`. Without ``node_record`` they leave out the count of returns, so a fit on them leaves out the node's own renewal record. |
| `_moved` (function) | The rows of :func:`validator_periods` whose node's next commitment, not overlapping them, started after ``cutoff`` less 365 days and by ``cutoff``: the renewals and returns of the year to the cutoff. |
| `_move_table` (function) | The duration and stake before and after each move in rows of :func:`_moved`, with the node. |
| `_first_ever` (function) | The rows of :func:`validator_periods` that are a node's first commitment and started in the 365 UTC days to ``day``, that is after the end of ``day`` less 365 days and by the end of ``day``. |
| `TrainingEvents` (class) | Everything a v0.8 fit reads from the staking periods at one origin, with each node as an integer ``node_code`` shared across the tables, so a bootstrap can resample nodes. |
| `state_from_rows` (function) | Build the released initial state from already admitted rows, without fitting a block. |
| `origin_state` (function) | Public-at-origin state only; never recompute fitted blocks or continuation distributions. |
| `training_events` (function) | The events :func:`fitted_inputs` fits on, read from staking periods that started by the origin's end. Its ``state`` also holds ``transactions``: the transaction hash of each row of ``initial`` and ``scheduled``, in their order, by which a model with delegations matches its own tables to these rows. The model inputs leave it out. |
| `checked_stake_decisions` (function) | ``table`` if every row lies in the stake model's fit domain and was decided before the lockbox. Otherwise ValueError. |
| `_stake_digest` (function) | Implementation helper. Open its source for the algorithm. |
| `_stake_table` (function) | Implementation helper. Open its source for the algorithm. |
| `stake_decisions` (function) | The stake decisions of the 365 days to the origin's end, one table per context: ``"renewal"``, ``"return"`` and ``"entry"``. |
| `split_at_line` (function) | The endings at or below ``large_above_avax`` and those above it, for the renewal and renewal_large blocks. |
| `fit_blocks` (function) | Every input of a v0.8 run, with its blocks fitted on ``events``. See :func:`fitted_inputs`. |
| `fitted_inputs` (function) | Every input of a v0.8 run from ``origin``, fitted on staking periods that started by the origin's end. |

## model/kpis.py

The key performance indicators of a run or of the chain, each one function of a daily table.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/kpis.py)

| Component | Purpose from source |
| --- | --- |
| `MissingColumn` (class) | A KPI's input column is not in the daily table. |
| `Threshold` (class) | Where a KPI fails. ``level`` is a fixed line, or None when the line is one minus the KPI ``complement_of``. |
| `Kpi` (class) | Implementation helper. Open its source for the algorithm. |
| `_day` (function) | Implementation helper. Open its source for the algorithm. |
| `_require` (function) | Implementation helper. Open its source for the algorithm. |
| `_one_row_a_day` (function) | Implementation helper. Open its source for the algorithm. |
| `_finite` (function) | Refuse an infinite value. A missing value is left to the caller. |
| `_same_origin` (function) | Refuse to read a chain table's started commitments from another origin than the one it was built for. |
| `_rows` (function) | The rows from ``first`` to ``last`` inclusive, every day present once, every value finite, and every value present when ``complete``. |
| `_run` (function) | Days 1 to ``horizon`` after the origin. |
| `_at_horizon` (function) | Implementation helper. Open its source for the algorithm. |
| `_nonzero` (function) | Implementation helper. Open its source for the algorithm. |
| `issued_navax` (function) | The run's issuance from the day after the origin to the horizon, in nAVAX, in the column's own type: the sum ``issuance_saved`` reads. |
| `_issued_as_divided` (function) | ``issued_navax`` as the 64-bit float ``issuance_saved`` divides, the value ``kpi_table`` gives. |
| `issuance_saved` (function) | One minus the run's issuance over the baseline's, from the day after the origin to the horizon. |
| `validator_stake_retained` (function) | Validator stake at the horizon over the baseline's. |
| `validator_stake_at_horizon` (function) | Validator stake at the horizon, in nAVAX. |
| `lowest_validator_stake` (function) | The lowest validator stake from the day after the origin to the horizon, in nAVAX. |
| `active_validators` (function) | Validators active at the horizon. |
| `active_validators_retained` (function) | Validators active at the horizon over the baseline's. |
| `_complete_days` (function) | The rows of complete ledger days. With the ledger's ``ledger_complete`` flag, a complete day missing a value is refused and an incomplete day is skipped. Without the flag, a missing value marks an incomplete day. |
| `mean_daily_burn` (function) | The mean burn of the 365 complete days that end at the origin, skipping days without a burn. |
| `with_realized_supply` (function) | The table with burn and realized supply filled after the origin: the burn held fixed, and supply equal to the starting supply plus the run's issuance less that burn, day by day. Days up to the origin are unchanged. |
| `_supplied` (function) | Implementation helper. Open its source for the algorithm. |
| `net_inflation` (function) | Issuance less burn over the 365 days that end at the horizon, over realized supply at the horizon. |
| `validator_staking_ratio` (function) | Validator stake at the horizon, with delegated stake when asked, over realized supply. |
| `nakamoto_count` (function) | The fewest holders whose stakes together exceed one third of the total. |
| `nakamoto_coefficient` (function) | The fewest nodes whose self-stake exceeds one third of all validator self-stake, at the horizon. |
| `earned_rate` (function) | The annual reward rate on the commitments started in the run: 365 times issuance over stake-days. |
| `return_margin` (function) | The earned rate less the competing yield and the operating cost, each a share of stake a year. |
| `stake_weighted_duration` (function) | Committed days of the commitments started in the run, weighted by stake. |
| `reward_rate_volatility` (function) | The standard deviation of the rate offered to a 30-day stake, in percentage points. |
| `_stake_from_origin` (function) | Implementation helper. Open its source for the algorithm. |
| `stake_volatility` (function) | The standard deviation of the daily change in the log of validator stake, from the origin to the horizon. |
| `worst_30_day_stake_fall` (function) | The largest fall in validator stake over any 30 days from the origin to the horizon, as a negative share. |
| `issuance_half_life` (function) | Years for the issuance left under the cap to halve at the pace of the last ``min(365, horizon)`` days. |
| `burn_to_issuance` (function) | AVAX burned per AVAX of rewards paid, over the complete days of the window. The chain only. |
| `kpi_table` (function) | Every KPI at each horizon, one row per measure, horizon and cost level. |
| `run_daily_table` (function) | One run of the engine's long table as a daily table, after the chain's days up to the origin when given. |
| `_start_day` (function) | The UTC day whose 23:59:59 is the first at or after a timestamp, as the replay counts days. |
| `chain_daily_table` (function) | The chain's daily table for a run from ``origin``, every day before ``through``, which may not pass the held-back test period. |

## model/lifecycle.py

A first validator lifecycle model: commitments end on schedule, renew or leave, and new ones enter.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/lifecycle.py)

| Component | Purpose from source |
| --- | --- |
| `Entry` (class) | How many validator commitments that are not renewals start each day. |
| `ValidatorLifecycle` (class) | Validator commitments from an origin, stepped one UTC day at a time. |
| `_day` (function) | Implementation helper. Open its source for the algorithm. |
| `origin_inputs` (function) | Inputs for a run from ``origin``, read only from staking periods started at or before the origin's end. |
| `score` (function) | Mean simulated count and stake at each horizon against the actual and against persistence. |
| `actual_path` (function) | Active validators and validator stake by day, accumulated from the replay's daily events. |

## model/lockbox_evaluation.py

Fixed-fit evaluation of the released validator model, with separate state and label clocks.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/lockbox_evaluation.py)

| Component | Purpose from source |
| --- | --- |
| `_hash_file` (function) | Implementation helper. Open its source for the algorithm. |
| `_json` (function) | Strict JSON values, retaining undefined/infinite metrics as explicit nulls. |
| `request_window` (function) | Validate all requested support before reading any input file or constructing a fit. |
| `monthly_origins` (function) | Implementation helper. Open its source for the algorithm. |
| `verified_inputs` (function) | Verify declared immutable files and producer metadata, without selecting a newest run. |
| `matching_training_slices` (function) | Compare keyed public schedules using exact integers/timestamps, including accepted future starts. |
| `validate_training_information` (function) | Refuse fit-eligible rows whose public clock is missing or later than the frozen cut. |
| `realized_daily` (function) | Only complete observed validator stocks before the exclusive daily end; no reward labels. |
| `frozen_fingerprint` (function) | Implementation helper. Open its source for the algorithm. |
| `at_origin` (function) | Replace state only. Preserve source receipts, fitted tables, blocks and bootstrap rows. |
| `configured_fit_binding` (function) | Validate the declared numerical identity before any input is opened. |
| `verify_frozen_fit` (function) | Check exact reconstructed fit/draw bytes before any realized or later-state read. |
| `cell_scores` (function) | Score one admitted case against every declared point and dressed benchmark. |
| `primary_verdict` (function) | Existing point-loss/significance rule, with undefined inference stated explicitly. |
| `contract_diagnostics` (function) | Reported own-stake/count diagnostics; never relabel these as total bonded AVAX. |
| `distribution_comparisons` (function) | Supplementary CRPS skill and dependence-aware comparisons, never a replacement verdict. |
| `binary_loss` (function) | Implementation helper. Open its source for the algorithm. |
| `behaviour_table` (function) | Frozen point-block renewal and conditional return checks, with matured labels and fixed baselines. |
| `evaluate` (function) | Evaluate an already-frozen released preparation. No fit occurs at a later state origin. |
| `report` (function) | Implementation helper. Open its source for the algorithm. |
| `evaluation_specification` (function) | Read the declared design without opening data or constructing a fit. |
| `prepare_fixed_fit` (function) | Shared pre-boundary-only preparation for scoring and the pre-marker preflight. |
| `verify_input_pins_unchanged` (function) | Implementation helper. Open its source for the algorithm. |
| `preflight_fit` (function) | Verify an adopted fit on the runner before its one-shot marker, without a token or labels. |
| `score` (function) | Single manifest entrypoint. Verify the frozen fit before state or realized-label access. |

## model/operator_events.py

Named operators in the delegated lifecycle: which delegations each one owns, and when it closes, from the operator events known at an origin.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/operator_events.py)

| Component | Purpose from source |
| --- | --- |
| `NamedOperators` (class) | The named operators known at one origin. ``operators``: one row per operator with a named address, its name, a key for state variable names, and the day it closes, or None. ``addresses``: one row per named address, its operator, and the naive UTC instant from which it is named. |
| `load` (function) | The operator events and attributions, as the files list them. |
| `surely_public` (function) | The naive UTC instant from which evidence was surely public: the instant itself, or the end of a date's UTC day. |
| `utc_naive` (function) | An instant as naive UTC: one with an offset is converted to UTC first, and one without is taken as UTC. |
| `origin_instant` (function) | The origin's last instant, 23:59:59 UTC, as naive UTC. |
| `known_events` (function) | The schedulable events whose evidence was surely public by the origin's last instant. |
| `key` (function) | A name for state variables: the operator's name in lower case, with every other run of characters as one underscore. |
| `replaced_at` (function) | The attributions replaced by a row public by the origin's last instant: public from the earliest of its citing identity events' evidence and the end of the day it was captured. |
| `named_operators` (function) | The operators named at ``origin`` by the identity events known then, with the day each closes by the shutdown events known then. The files are read when ``events`` or ``attributions`` is not given. |
| `owners` (function) | Each delegation's row of ``named.operators``: the operator whose named address funds it, when it was accepted at or after that address's naming instant, else -1. An acceptance time with an offset is converted to UTC, and one without is UTC already. |

## model/parts/__init__.py

The fitted lifecycle model's behaviour, one module per part.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/__init__.py)

## model/parts/arrivals.py

Arrivals: how many nodes start their first-ever validator commitment each day, a negative binomial count.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/arrivals.py)

| Component | Purpose from source |
| --- | --- |
| `Arrivals` (class) | How many nodes start their first-ever validator commitment each day: a negative binomial count. |
| `_negative_binomial_log_prob` (function) | Implementation helper. Open its source for the algorithm. |
| `arrivals_stage` (function) | The daily arrivals stage: the count of first-ever nodes today, from one uniform keyed by the day with the entry response to the yield gap, and their node keys. |

## model/parts/base.py

The contract every behaviour part follows, and the constants more than one part reads.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/base.py)

Imported components: `annotations`, `BehaviourBlock`, `_outcomes`, `behavioural`.

## model/parts/continuation.py

Continuation: the next duration and stake of a node that renews or returns.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/continuation.py)

| Component | Purpose from source |
| --- | --- |
| `Continuation` (class) | The next duration and stake of a node that renews or returns, drawn from the same node moves before the origin. |
| `continuation_stage` (function) | The daily continuation stage: every commitment that starts today, in the order renewed, returned, arrived. |

## model/parts/delegations.py

Delegations: the stage that ages, starts and places delegations on the day's validators, and mints their rewards.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/delegations.py)

| Component | Purpose from source |
| --- | --- |
| `DelegationSetup` (class) | What the delegations stage reads besides the state and the day: the three blocks, every validator's fee in millionths, the delegation multiplier, the node keys of BENQI's validators, the terms new delegations draw from, BENQI's and the others', each as stakes, days and the named operator row that owns the delegation, the placement batch size, BENQI's row among the named operators, -1 when it is not named, and for each named operator row the day counted from the origin from which it makes no new delegation, infinite when it does not close. |
| `limits` (function) | Each validator's weight limit at ``chain_time``. |
| `on_validators` (function) | Each delegation's row among the validators, or -1 when its validator is not active. |
| `stake_on` (function) | Stake per validator row, leaving out delegations whose row is -1. |
| `_choose` (function) | The validator row each delegation chooses on ``room``, or -1 when none of ``candidates`` has room for it. |
| `place` (function) | Place the day's delegations in batches of ``setup.batch``. Returns the order in which they were accepted and each one's validator row, -1 when unplaced. ``room`` is reduced in place by every accepted stake. |
| `delegations_stage` (function) | The daily delegations stage. Returns the assembly's next state with the delegations added, and issuance as the day's validator rewards plus its delegator rewards. |

## model/parts/duration_transition.py

The next commitment's duration for a node that renews or returns: a fitted transition between duration bands.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/duration_transition.py)

| Component | Purpose from source |
| --- | --- |
| `duration_band` (function) | The band of each duration in whole days: 0 is under 21 days, 4 is 200 days or more. |
| `persistence_matrix` (function) | The persistence forecast as a transition matrix: the last band with probability ``1 - floor``, and the floor shared equally among the other four bands. |
| `persistence_log_prob` (function) | The log-likelihood of the next bands under persistence. With the default floor of 0.01, a repeated band scores log 0.99 and a change of band log 0.0025. |
| `duration_moves` (function) | The node moves whose next commitment started after ``after_us`` and by ``through_us``. |
| `_dirichlet_evidence` (function) | The log marginal likelihood of each row's counts under a Dirichlet prior with those pseudo-counts, summed. |
| `_whole_days` (function) | Durations as whole days from 1 to 365. Anything else is refused rather than truncated or kept. |
| `DurationTransition` (class) | The next duration band given the last, then the exact day from the band's own record. |
| `fit_moves` (function) | The transition fitted on a moves table with ``previous_days`` and ``next_days``, every move of which started by ``decided_by_us``, so a table that reaches 2025-11-19 16:00 UTC is refused. The block holds no day record: the fitted lifecycle draws the exact day from the moves of its own run. |

## model/parts/renewal.py

Renewal: whether an ending commitment renews on the same node within seven days.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/renewal.py)

| Component | Purpose from source |
| --- | --- |
| `tenure_bin` (function) | The tenure bin of a commitment from the node's completed commitments before it: 0 is a first commitment. |
| `renewal_design` (function) | One row per ending commitment, one column per term of :data:`RENEWAL_TERMS`. |
| `_coefficient` (function) | Implementation helper. Open its source for the algorithm. |
| `RenewalLogit` (class) | Renewal within seven days on the same node: logit P = intercept + tenure + after a return + duration + stake. |
| `_newton` (function) | The penalized logit's mode and its penalized log-likelihood. The intercept, column 0, is not penalized. |
| `_penalized` (function) | The logit's log-likelihood at ``beta`` less the normal prior's penalty. |
| `renewal_stage` (function) | The daily renewal stage: the commitments that end today, and which of them renew on the same node. |

## model/parts/return_hazard.py

Returns on the node's own history: a daily logit hazard that a node out of the set starts a new commitment.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/return_hazard.py)

| Component | Purpose from source |
| --- | --- |
| `return_design` (function) | One row per node-day, one column per term of :data:`RETURN_LOGIT_TERMS`. |
| `_penalty` (function) | The priors as a penalty matrix on the terms: the random walk on the day bins, the ridge on the rest. |
| `_coefficient` (function) | Implementation helper. Open its source for the algorithm. |
| `ReturnLogitHazard` (class) | Whether a node that did not renew starts a new commitment today, after more than seven days out. |
| `_objective` (function) | The binomial log-likelihood of ``y`` returns in ``n`` node-days at ``beta``, less the priors' penalty. |
| `_newton` (function) | The penalized binomial logit's mode by Newton steps, each halved until it does not lower the objective. |

## model/parts/returns.py

Returns: whether a node that did not renew starts a new commitment, a daily hazard after more than seven days out.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/returns.py)

| Component | Purpose from source |
| --- | --- |
| `return_cell` (function) | The hazard cell of each node out of the set: stake band times days since its last commitment ended. |
| `_hazard` (function) | Implementation helper. Open its source for the algorithm. |
| `ReturnHazard` (class) | Whether a node that did not renew starts a new commitment today, after more than seven days out. |
| `returns_stage` (function) | The daily returns stage: one more day out for every node out of the set, and which of them return today, each by one uniform keyed by the node and the day. The return block reads each node's stake and days out, and may read its record: its completed commitments and how many of them were returns. |

## model/parts/stages.py

The fitted lifecycle's daily step as an ordered list of stages.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/stages.py)

| Component | Purpose from source |
| --- | --- |
| `RunBlocks` (class) | One run's blocks: fitted, or built from the run's row of parameter draws. |
| `RunSettings` (class) | What every day of every run reads: the large-holder line, the yield-gap responses, the reward rule, and the commitments accepted by the origin that start after it, one array per column. |
| `Day` (class) | What a stage reads besides the state: timestep ``t``, noon UTC of the day it steps to, the run's keyed draws, the run's blocks, the day's yield gaps for renewal and entry, and the run's settings. |
| `run_stages` (function) | Run ``stages`` in order on one day and return the last stage's output. |
| `rewards_stage` (function) | The rewards minted for every commitment started today, priced by the reward rule at the day's supply, with the started commitments' stake and stake-days and the annual rate the rule offers a 30-day stake with no tenure at that supply. The scheduled commitments due today are not started here, so none of these counts them. |
| `assembly_stage` (function) | The next state's commitments and nodes out of the set. Open commitments that do not end today stay, followed by those started today and the scheduled ones due today. A node out of the set stays out until it returns or its 365 days pass, followed by the nodes whose commitment ended today without renewal. The rewards stage's outputs pass through. |

## model/parts/stake_choice.py

Empirical stake hurdle and its discrete observable-cell score.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/parts/stake_choice.py)

| Component | Purpose from source |
| --- | --- |
| `table_sha256` (function) | Proposed adapter encoding: compact UTF-8 JSON columns and ordered rows. |
| `_has_bool` (function) | Implementation helper. Open its source for the algorithm. |
| `_masked` (function) | Implementation helper. Open its source for the algorithm. |
| `_vector` (function) | Implementation helper. Open its source for the algorithm. |
| `_integers` (function) | Implementation helper. Open its source for the algorithm. |
| `_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `_stake_band` (function) | Implementation helper. Open its source for the algorithm. |
| `_quantiles` (function) | Portable float64 interpolation, no extrapolation or FMA requirement. |
| `_changed` (function) | Implementation helper. Open its source for the algorithm. |
| `_cell_ids` (function) | Implementation helper. Open its source for the algorithm. |
| `_integer_edges` (function) | First legal integer stake in each log bin, using the score's own log. |
| `_cdf_stake` (function) | Measure of v whose floored/clamped changed stake is below thresholds. |
| `_smooth` (function) | Implementation helper. Open its source for the algorithm. |
| `_Cell` (class) | Implementation helper. Open its source for the algorithm. |
| `StakeChoice` (class) | Fit-only empirical hurdle, with 50-change pooling within each context. |

## model/protocol.py

Moved to ``avalanche_research.domain.protocol``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/protocol.py)

Imported components: `alias`.

## model/replay.py

Replay recorded staking periods through the cadCAD engine and compare with the monetary ledger.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/replay.py)

| Component | Purpose from source |
| --- | --- |
| `daily_events` (function) | One row per UTC day before ``through``: stake and count changes by role, and rewards paid. |
| `Replay` (class) | Recorded stake starts, ends, and rewards, stepped one UTC day at a time. |
| `compare` (function) | The replayed long table against the ledger on every complete day, exactly, in wei and counts. |

## model/response.py

The rate gap a behaviour response acts on: a design's change from the reward menu the blocks were fitted under.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/response.py)

| Component | Purpose from source |
| --- | --- |
| `FittedMenu` (class) | The chain's rule as it stood at the end of a fitting window, held there whatever the stake's start. |
| `response_gap_pp` (function) | The design's annual rate minus the fitted menu's, in percentage points, for a 30-day stake started at noon UTC on ``day`` at ``supply_navax`` and ``completed_periods`` of tenure. |

## model/runner.py

A streaming sweep runner: design rows run one per task in a bounded process pool, each finished row written to its own Parquet file, so a 50,000-run sweep never holds more than a few rows in memory and resumes after a stop.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/runner.py)

| Component | Purpose from source |
| --- | --- |
| `finished_ids` (function) | Row ids with complete, authenticated files. Unauthenticated or changed files refuse resume. |
| `_init` (function) | Implementation helper. Open its source for the algorithm. |
| `model_settings` (function) | A row's settings as the model takes them: a ``mechanism`` given by class name, or by a mapping with ``name`` and keyword settings, becomes that reward mechanism from ``avalanche_research.mechanisms``. |
| `_simulate` (function) | Implementation helper. Open its source for the algorithm. |
| `_write` (function) | Implementation helper. Open its source for the algorithm. |
| `_build_child` (function) | Implementation helper. Open its source for the algorithm. |
| `build_apart` (function) | Build one base model in a forked child process. The child writes the model's pickle to ``base_path`` and its specification beside it, and the parent reads only the specification. Returns the pickle's path, the specification hash and the specification. A child that fails raises here, with the child's traceback already on stderr. |
| `run_sweep` (function) | Run every row not yet finished under ``out``. Returns counts and timing. ``stop_after`` stops after that many rows are written, to test resume. ``reducer``, a module-level function or a picklable callable, turns a row's long table and the row into the rows to keep, such as one row of KPIs per run; without it the row keeps the daily paths of ``variables``. |
| `_run_pickled` (function) | Implementation helper. Open its source for the algorithm. |
| `run_design` (function) | A whole design across origins and models. The design is checked (row count, repeated settings, lockbox origins), each base model is built once per origin and model in a child process, and ``design.json`` with every row id and the design hash is written before the first row runs. Rows then run group by group into ``out``. The totals carry each group's base specification under ``base_specifications``, in group order. |
| `_run_groups` (function) | Implementation helper. Open its source for the algorithm. |
| `worker_memory` (function) | A worker's memory as ``base + per_run * runs``, fitted by least squares to a pilot's peak memory per row. |
| `available_mib` (function) | Memory available now, in MiB, as the kernel estimates it (``MemAvailable``). Read at launch, since free memory on a shared machine moves with other jobs. |
| `size_pool` (function) | Workers that fit in ``available_mib`` after ``reserve_mib`` for the parent and the system, at most one per CPU. |
| `read_sweep` (function) | Every finished row's paths, ordered by design index, run, timestep and variable. |

## model/stake_lifecycle.py

Fitted stake hurdle behind an explicit lifecycle switch.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/stake_lifecycle.py)

| Component | Purpose from source |
| --- | --- |
| `_sha256` (function) | Implementation helper. Open its source for the algorithm. |
| `stake_law_record` (function) | Every fitted value and source, including the historical entry-score law. |
| `fitted_stake_settings` (function) | Fit checked producer tables without changing their original CSV attrs. |
| `StakeLifecycle` (class) | FittedLifecycle with a duration-conditioned stake law explicitly enabled. |
| `build_stake_candidate` (function) | Variant build callable: candidate-a inputs plus the checked stake law. |

## model/streams.py

Keyed random numbers: every draw a pure function of (seed, run, purpose, keys).

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/streams.py)

| Component | Purpose from source |
| --- | --- |
| `purpose_id` (function) | A stable 63-bit id from a declared purpose's name. Order-free. |
| `_splitmix` (function) | Implementation helper. Open its source for the algorithm. |
| `node_keys` (function) | int64 node keys ``kind << 48 \| t << 24 \| index``. Kind 0 is open at the origin, 1 out of the set, 2 scheduled, 3 a first-ever arrival on day ``t``. |
| `Streams` (class) | All randomness of one run. Plain data, so it pickles to any worker and replays anywhere. |

## model/types.py

Moved to ``avalanche_research.domain.protocol.types``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/types.py)

Imported components: `alias`.

## model/variants.py

The model variants the development scores run, by name, and how each is built at an origin.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/variants.py)

| Component | Purpose from source |
| --- | --- |
| `Prepared` (class) | A variant's inputs at one origin: the model's settings and input tables, and for a variant that reads draws, its draw table, the renewal shift's SD and that SD's source. |
| `Variant` (class) | A named model variant: its model class, what it is, and how its inputs are built at an origin from the staking periods, the name of the run they came from, the number of draws and the draw seed. |
| `Switches` (class) | The choices the v0.8 candidates differ in. The defaults are v0.8. |
| `switched_inputs` (function) | Every input of a v0.8 run fitted on ``events`` under ``switches``. |
| `_chain_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `_fitted` (function) | Implementation helper. Open its source for the algorithm. |
| `_fitted_with_draws` (function) | Implementation helper. Open its source for the algorithm. |
| `_stake_point` (function) | Implementation helper. Open its source for the algorithm. |
| `_stake_on` (function) | The stake hurdle on the blocks ``switches`` fit. With draws, every other block redraws per run under the same switches and the hurdle stays at its point estimate, as ``v0.8-a stake u`` does. |
| `_delegated_stub` (function) | Implementation helper. Open its source for the algorithm. |
| `_delegated_events` (function) | Implementation helper. Open its source for the algorithm. |

## model/versions.py

The model's versions as the Foundation sees them: one capability per version, each shown on one call.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/model/versions.py)

| Component | Purpose from source |
| --- | --- |
| `Version` (class) | Implementation helper. Open its source for the algorithm. |

## monetary.py

Moved to ``avalanche_research.datasets.derived.monetary``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/monetary.py)

Imported components: `alias`.

## monetary_periods.py

Moved to ``avalanche_research.datasets.derived.monetary_periods``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/monetary_periods.py)

Imported components: `alias`.

## nodes.py

Moved to ``avalanche_research.datasets.derived.nodes``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/nodes.py)

Imported components: `alias`.

## operators.py

Moved to ``avalanche_research.datasets.derived.operators``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/operators.py)

Imported components: `alias`.

## opportunity.py

Moved to ``avalanche_research.datasets.derived.opportunity``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/opportunity.py)

Imported components: `alias`.

## palette.py

Stable light-chart quantity hues with stroke patterns for duration weighting.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/palette.py)

## pblocks.py

Moved to ``avalanche_research.sources.pblocks``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/pblocks.py)

Imported components: `alias`.

## pburns.py

Moved to ``avalanche_research.datasets.derived.pburns``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/pburns.py)

Imported components: `alias`.

## pchain.py

Moved to ``avalanche_research.sources.pchain``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/pchain.py)

Imported components: `alias`.

## pins.py

Moved to ``avalanche_research.datasets.pins``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/pins.py)

Imported components: `alias`.

## pool_history.py

Moved to ``avalanche_research.sources.pool_history``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/pool_history.py)

Imported components: `alias`.

## practice/__init__.py

Practice models from the UCLA modeling class, written in the staking model's conventions.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/practice/__init__.py)

## practice/allee.py

The Allee effect, UCLA Life Science 30A lectures 6.1, 7.2, and 11.2: X' = b X (1 - X/K) (X/A - 1).

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/practice/allee.py)

| Component | Purpose from source |
| --- | --- |
| `p_growth` (function) | Implementation helper. Open its source for the algorithm. |
| `s_animals` (function) | Implementation helper. Open its source for the algorithm. |
| `Allee` (class) | A population with a minimum viable size, stepped by Euler's method. |

## practice/bathtub.py

The bathtub, UCLA Life Science 30A lecture 4.1: a faucet fills the tub and the drain empties it in proportion to the level. X' = inflow - k X. Its one equilibrium, inflow / k, is stable.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/practice/bathtub.py)

| Component | Purpose from source |
| --- | --- |
| `p_faucet` (function) | Implementation helper. Open its source for the algorithm. |
| `p_drain` (function) | Implementation helper. Open its source for the algorithm. |
| `s_water` (function) | Implementation helper. Open its source for the algorithm. |
| `Bathtub` (class) | Water in a tub, in gallons, stepped by Euler's method. |

## practice/birth_death.py

Birth and death, UCLA Life Science 30A lectures 4.2, 4.3, and 4.6: X' = b X - d X = (b - d) X.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/practice/birth_death.py)

| Component | Purpose from source |
| --- | --- |
| `p_births` (function) | Implementation helper. Open its source for the algorithm. |
| `p_deaths` (function) | Implementation helper. Open its source for the algorithm. |
| `s_animals` (function) | Implementation helper. Open its source for the algorithm. |
| `BirthDeath` (class) | A population with constant per-capita birth and death rates, stepped by Euler's method. |

## practice/logistic.py

Logistic growth, UCLA Life Science 30A lectures 4.6, 5.2, 6.1, and 7.2: births in proportion to the population, less crowding in proportion to its square. X' = b X - (b / K) X^2. Equilibria at 0, unstable, and at K, stable.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/practice/logistic.py)

| Component | Purpose from source |
| --- | --- |
| `p_growth` (function) | Implementation helper. Open its source for the algorithm. |
| `p_crowding` (function) | Implementation helper. Open its source for the algorithm. |
| `s_rabbits` (function) | Implementation helper. Open its source for the algorithm. |
| `Logistic` (class) | A population limited by crowding, stepped by Euler's method. |

## practice/mass_action.py

Mass action chemistry, UCLA Life Science 30A lecture 4.7: the reversible reaction X + Y <-> Z.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/practice/mass_action.py)

| Component | Purpose from source |
| --- | --- |
| `p_forward` (function) | Implementation helper. Open its source for the algorithm. |
| `p_backward` (function) | Implementation helper. Open its source for the algorithm. |
| `s_add` (function) | Implementation helper. Open its source for the algorithm. |
| `MassAction` (class) | Concentrations of X, Y, and Z, as fractions of volume, stepped by Euler's method. |

## practice/shark_tuna.py

Shark and tuna, UCLA Life Science 30A lectures 4.2, 4.4, 5.3: Lotka-Volterra predator and prey.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/practice/shark_tuna.py)

| Component | Purpose from source |
| --- | --- |
| `p_tuna_births` (function) | Implementation helper. Open its source for the algorithm. |
| `p_hunting` (function) | Implementation helper. Open its source for the algorithm. |
| `p_shark_deaths` (function) | Implementation helper. Open its source for the algorithm. |
| `s_tuna` (function) | Implementation helper. Open its source for the algorithm. |
| `s_sharks` (function) | Implementation helper. Open its source for the algorithm. |
| `SharkTuna` (class) | Sharks and tuna, in the lecture's units, stepped by Euler's method. |

## pstakers.py

Moved to ``avalanche_research.sources.pstakers``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/pstakers.py)

Imported components: `alias`.

## pstaking.py

Moved to ``avalanche_research.datasets.derived.pstaking``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/pstaking.py)

Imported components: `alias`.

## ptx.py

Moved to ``avalanche_research.sources.ptx``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/ptx.py)

Imported components: `alias`.

## reproduction.py

Source-comparable calculations for published Avalanche economic research.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/reproduction.py)

| Component | Purpose from source |
| --- | --- |
| `figure7_frame` (function) | Compare Eric Lu's Figure 7 period-return formula with the integer protocol kernel. |
| `figure8_observed_bins` (function) | Bin observed commitment durations by count and cumulative self-stake. |

## research.py

Read-only orientation from the checkout's file inventory, without research data imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/research.py)

| Component | Purpose from source |
| --- | --- |
| `_git` (function) | Implementation helper. Open its source for the algorithm. |
| `_is_project` (function) | Implementation helper. Open its source for the algorithm. |
| `_find_root` (function) | Implementation helper. Open its source for the algorithm. |
| `_inventory` (function) | Implementation helper. Open its source for the algorithm. |
| `_title` (function) | Read a simple scalar YAML title, never the page body or a YAML object. |
| `_Node` (class) | Implementation helper. Open its source for the algorithm. |
| `_build` (function) | Implementation helper. Open its source for the algorithm. |
| `_visible` (function) | Implementation helper. Open its source for the algorithm. |
| `_label` (function) | Implementation helper. Open its source for the algorithm. |
| `_lines` (function) | Implementation helper. Open its source for the algorithm. |
| `research` (function) | Orient in the wiki and source checkout without loading research data. |
| `tree` (function) | Print tracked wiki pages, repository structure, or both (the default). |

## research_cycle.py

One bounded, preregistered research cycle using the portable first experiment.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/research_cycle.py)

| Component | Purpose from source |
| --- | --- |
| `CycleError` (class) | An invalid definition, incomplete execution or unauthenticated artifact. |
| `digest` (function) | Implementation helper. Open its source for the algorithm. |
| `encoded` (function) | Implementation helper. Open its source for the algorithm. |
| `fingerprint` (function) | Implementation helper. Open its source for the algorithm. |
| `now` (function) | Implementation helper. Open its source for the algorithm. |
| `load` (function) | Implementation helper. Open its source for the algorithm. |
| `atomic` (function) | Implementation helper. Open its source for the algorithm. |
| `inside` (function) | Implementation helper. Open its source for the algorithm. |
| `lock` (function) | Implementation helper. Open its source for the algorithm. |
| `number` (function) | Implementation helper. Open its source for the algorithm. |
| `at` (function) | Implementation helper. Open its source for the algorithm. |
| `predicate` (function) | Implementation helper. Open its source for the algorithm. |
| `definition` (function) | Resolve one hypothesis and bind the complete delivered driver/input code. |
| `artifacts` (function) | Implementation helper. Open its source for the algorithm. |
| `execute` (function) | Implementation helper. Open its source for the algorithm. |
| `evaluate` (function) | Implementation helper. Open its source for the algorithm. |
| `readback` (function) | Implementation helper. Open its source for the algorithm. |
| `run` (function) | Implementation helper. Open its source for the algorithm. |
| `reflect` (function) | Attach an explicit authored outer review of a completed inner cycle. |
| `main` (function) | Implementation helper. Open its source for the algorithm. |

## rest.py

Moved to ``avalanche_research.sources.capture.rest``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/rest.py)

Imported components: `alias`.

## seam.py

Moved to ``avalanche_research.datasets.derived.seam``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/seam.py)

Imported components: `alias`.

## snowflake.py

Moved to ``avalanche_research.sources.snowflake``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/snowflake.py)

Imported components: `alias`.

## snowpeer.py

Moved to ``avalanche_research.sources.snowpeer``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/snowpeer.py)

Imported components: `alias`.

## sources/__init__.py

Captures: each module talks to one outside provider and writes a captured run. ``capture`` holds the shared clients.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/__init__.py)

## sources/atomic.py

Capture and check C-Chain atomic AVAX burns from transaction-level Data API records.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/atomic.py)

| Component | Purpose from source |
| --- | --- |
| `_window` (function) | Implementation helper. Open its source for the algorithm. |
| `_endpoint` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_resume` (function) | The page records of a kept walk, each page verified against its record, so the walk continues after them. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `_amount` (function) | Implementation helper. Open its source for the algorithm. |
| `_utxo_amount` (function) | Implementation helper. Open its source for the algorithm. |
| `read_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `_summary` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/binance.py

AVAX daily candles from Binance's public data archive, the full history since AVAX began trading.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/binance.py)

| Component | Purpose from source |
| --- | --- |
| `_end` (function) | Implementation helper. Open its source for the algorithm. |
| `_bases` (function) | Implementation helper. Open its source for the algorithm. |
| `files` (function) | One monthly file for every month closed before end's month, then one daily file for each earlier day of that month. |
| `_download` (function) | Implementation helper. Open its source for the algorithm. |
| `_published` (function) | The hash in a CHECKSUM file, which reads '<sha256>  <file name>'. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `_candle_time` (function) | Open time in milliseconds before 2025 and in microseconds from 2025 on. |
| `read_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `_summary` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `cross_check` (function) | Each day's USDT open against CoinGecko's USD price at the same midnight. |
| `check` (function) | With ``--against`` a built coingecko.avax-market-daily dataset directory: the USDT open against the USD price. |

## sources/builderhub.py

Builder Hub validator uptime: capture, build and check. The merged hourly table is ``uptime_hourly``.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/builderhub.py)

| Component | Purpose from source |
| --- | --- |
| `_endpoint` (function) | Implementation helper. Open its source for the algorithm. |
| `_request` (function) | One GET. Builder Hub's list route answers a JSON array, which the shared REST layer does not accept. |
| `_parameters` (function) | Implementation helper. Open its source for the algorithm. |
| `_previous` (function) | The previous capture: ``auto`` for the newest built run, ``none``, or a run name, as the command line resolved it. |
| `_listed_nodes` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_read_lines` (function) | The complete detail lines of a kept capture. A line cut off mid-write is dropped and the file cut back to the rest. |
| `_import` (function) | Wrap a capture taken by the 2026-09-24 preservation script, whose lines hold only node_id and body. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `_fetch_counted` (function) | A request retried with doubling waits, about two and a half minutes in all, when refused, dropped, or answered 5xx. |
| `_fetch` (function) | Implementation helper. Open its source for the algorithm. |
| `read_capture` (function) | The receipt, the list, and the detail lines, verified against the receipt's hashes. |
| `_bucket` (function) | ``2026-09-10T09:00:00Z`` or ``2026-09-11 00:00:00`` as naive UTC. |
| `_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `_verify_outputs` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Finding codes: ``BC1`` completeness, ``BC2`` identity, ``BC3`` series shape, ``BC4`` fallback answers, ``BC9`` nodes the source could not serve, and with ``--against`` a previous capture's dataset ``BC5`` continuity and ``BC6`` agreement, and a same-day ``p-chain-rpc.current-validators`` dataset ``BC7`` node set. ``--against`` repeats, so one check runs all three. A finding under BC1, BC2, BC3, or BC5 means the day's history is incomplete. The runner treats those as failure and the others as attention. |

## sources/capture/__init__.py

Clients shared by the providers: the REST transport, with its retries, limits and response receipts.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/capture/__init__.py)

## sources/capture/rest.py

Immutable capture of REST endpoint responses declared in the data catalog.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/capture/rest.py)

| Component | Purpose from source |
| --- | --- |
| `_data_api_key` (function) | Implementation helper. Open its source for the algorithm. |
| `_request` (function) | Fetch one endpoint. A JSON body turns the request into a POST; content selects the response validation. |
| `_paged` (function) | Follow ``page['token_field']`` in each JSON response as ``page['token_parameter']`` on the next request. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `read_capture` (function) | Implementation helper. Open its source for the algorithm. |

## sources/capture/snowflake.py

The Snowflake client the share's captures use: the named connection, the session record, values as JSON, and the query text. The share's datasets and their capture are ``sources.snowflake``.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/capture/snowflake.py)

| Component | Purpose from source |
| --- | --- |
| `connection_name` (function) | Implementation helper. Open its source for the algorithm. |
| `connect` (function) | Open a Snowflake connection through the connector's named-connection configuration. |
| `_connector_error` (function) | Implementation helper. Open its source for the algorithm. |
| `read_sql` (function) | Implementation helper. Open its source for the algorithm. |
| `_json_value` (function) | Implementation helper. Open its source for the algorithm. |
| `_session` (function) | Implementation helper. Open its source for the algorithm. |

## sources/catx.py

Archive and check C-Chain atomic transactions by hash from a public node, for burns the Data API cannot settle.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/catx.py)

| Component | Purpose from source |
| --- | --- |
| `cb58` (function) | Avalanche's CB58: base58 of the bytes followed by the last four bytes of their SHA-256. |
| `_hashes` (function) | Implementation helper. Open its source for the algorithm. |
| `_endpoint` (function) | Implementation helper. Open its source for the algorithm. |
| `_payload` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `decode_import` (function) | (AVAX in, inputs, AVAX out, outputs) of a signed C-Chain import, codec version 0. Every byte must be read. |
| `read_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `_summary` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/cblocks.py

Capture the fees of the C-Chain blocks the Snowflake share cannot account for, from either of two sources.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/cblocks.py)

| Component | Purpose from source |
| --- | --- |
| `_parameters` (function) | Implementation helper. Open its source for the algorithm. |
| `_spec` (function) | Implementation helper. Open its source for the algorithm. |
| `_endpoint` (function) | Implementation helper. Open its source for the algorithm. |
| `_batch` (function) | Implementation helper. Open its source for the algorithm. |
| `_reading` (function) | Implementation helper. Open its source for the algorithm. |
| `gap_heights` (function) | The heights a gaps run lists, ascending. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_resume` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `_integer` (function) | Implementation helper. Open its source for the algorithm. |
| `_row` (function) | (height, hash, timestamp, date, transactions, gas used, base fee, fees) from one captured line. |
| `_hex` (function) | Implementation helper. Open its source for the algorithm. |
| `read_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `_summary` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_json_summary` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | With ``--against`` the built gaps dataset directory: every captured block is one the gaps run lists. |

## sources/cchain_rpc.py

Archive and check C-Chain blocks and transaction receipts missing from the Snowflake share.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/cchain_rpc.py)

| Component | Purpose from source |
| --- | --- |
| `_height` (function) | Implementation helper. Open its source for the algorithm. |
| `_endpoint` (function) | Implementation helper. Open its source for the algorithm. |
| `_payload` (function) | Implementation helper. Open its source for the algorithm. |
| `_hex` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `read_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/clist.py

Capture every C-Chain block from now back to a UTC date from the Data API's block list, and the daily EVM fees from it.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/clist.py)

| Component | Purpose from source |
| --- | --- |
| `_c_row` (function) | Implementation helper. Open its source for the algorithm. |
| `_p_row` (function) | Implementation helper. Open its source for the algorithm. |
| `_endpoint` (function) | Implementation helper. Open its source for the algorithm. |
| `_parameters` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_url` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `read_rows` (function) | Every listed block on or after from_date once, from pages that chain by token. |
| `_gaps` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_write` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | The block list: pages chain by token and each block appears once. |

## sources/coingecko.py

CoinGecko AVAX market data: typed daily table with log returns and 30-day realized volatility.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/coingecko.py)

| Component | Purpose from source |
| --- | --- |
| `load_capture` (function) | Read the captured response and build the typed daily table in DuckDB. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `cross_check` (function) | Compare midnight prices with the DefiLlama price dataset built in reference_dir. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/dataapi.py

Avalanche Data API datasets: the current AVAX supply snapshot.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/dataapi.py)

| Component | Purpose from source |
| --- | --- |
| `load_capture` (function) | Implementation helper. Open its source for the algorithm. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `reconcile` (function) | Compare the API's genesis plus cumulative rewards with the Snowflake protocol supply counter. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/defillama.py

DefiLlama datasets: the AVAX daily price history with CoinGecko lineage.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/defillama.py)

| Component | Purpose from source |
| --- | --- |
| `_transform_sql` (function) | Implementation helper. Open its source for the algorithm. |
| `load_capture` (function) | Read every captured window and build the typed price table in DuckDB. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/etf.py

AVAX exchange-traded products: net asset value, shares, and AVAX held, as each issuer publishes them.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/etf.py)

| Component | Purpose from source |
| --- | --- |
| `sec_user_agent` (function) | Implementation helper. Open its source for the algorithm. |
| `_check_dataset` (function) | Implementation helper. Open its source for the algorithm. |
| `_headers` (function) | Implementation helper. Open its source for the algorithm. |
| `_default_opener` (function) | One cookie jar per capture: VanEck sets session cookies on the first block and expects them on the next. |
| `_decode` (function) | Implementation helper. Open its source for the algorithm. |
| `_bava_data` (function) | The fund record embedded in the BAVA page's Next.js data. |
| `_validate` (function) | Implementation helper. Open its source for the algorithm. |
| `_request` (function) | Implementation helper. Open its source for the algorithm. |
| `_fetch` (function) | A request retried with growing waits when the connection fails; a malformed answer fails at once. |
| `_raw_path` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `read_capture` (function) | The receipt and each endpoint's parsed answer, verified against the receipt's hashes and the current contract. |
| `_number` (function) | VanEck's display strings: ``20,724,615``, ``$21.82``, ``80.00``, ``5.93%``. |
| `_us_date` (function) | Implementation helper. Open its source for the algorithm. |
| `_captured_at` (function) | Implementation helper. Open its source for the algorithm. |
| `_ratio` (function) | Implementation helper. Open its source for the algorithm. |
| `_bava_avax` (function) | BAVA's AVAX units and their basket weight. |
| `_bava_snapshot` (function) | Implementation helper. Open its source for the algorithm. |
| `_vavx_snapshot` (function) | Implementation helper. Open its source for the algorithm. |
| `_ts_avax_line` (function) | Implementation helper. Open its source for the algorithm. |
| `_ts_snapshot` (function) | Implementation helper. Open its source for the algorithm. |
| `_sec_instants` (function) | GAVA's instant facts by period end, keeping the latest filing's value where a later filing restates one. |
| `_sec_row` (function) | Implementation helper. Open its source for the algorithm. |
| `snapshot_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `history_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `_load` (function) | Implementation helper. Open its source for the algorithm. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `_off` (function) | True when two amounts differ by more than the tolerance, relative to the reference. |
| `nav_share_gaps` (function) | Fund and date of each row whose NAV per share times shares is off its net assets by more than the tolerance. |
| `_findings` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/gci.py

Inputs for the Gross Chain Income study, and one checked monthly table built from them.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/gci.py)

| Component | Purpose from source |
| --- | --- |
| `_table` (function) | Implementation helper. Open its source for the algorithm. |
| `_endpoint` (function) | Implementation helper. Open its source for the algorithm. |
| `_months` (function) | Implementation helper. Open its source for the algorithm. |
| `_next_month` (function) | Implementation helper. Open its source for the algorithm. |
| `_last_complete_month` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_Node` (class) | One JSON-RPC call at a time to the gateway, retried with a doubling wait, paced, with block times cached. |
| `_month_record` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `_hex_int` (function) | Implementation helper. Open its source for the algorithm. |
| `read_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `_write` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `_tb3ms_findings` (function) | Monthly means of DTB3 against FRED's own monthly average TB3MS, within 0.01 points. |
| `check` (function) | Captures: hashes, the month-end block rule, and for the bill rate the monthly means against TB3MS. |

## sources/metrics.py

Avalanche Metrics API daily series: Primary Network staking totals and C-Chain activity.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/metrics.py)

| Component | Purpose from source |
| --- | --- |
| `SeriesSpec` (class) | Implementation helper. Open its source for the algorithm. |
| `spec_for` (function) | Implementation helper. Open its source for the algorithm. |
| `_metric_of` (function) | Implementation helper. Open its source for the algorithm. |
| `load_capture` (function) | Read every captured window, refuse incomplete pages, and pivot the series into one row per day. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `reconcile` (function) | Compare the staking series with daily active counts and weights rebuilt from the Snowflake stake datasets. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/pblocks.py

Walk P-Chain blocks by height from a public node, a source independent of the Snowflake share.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/pblocks.py)

| Component | Purpose from source |
| --- | --- |
| `_parameters` (function) | Implementation helper. Open its source for the algorithm. |
| `_chain` (function) | Implementation helper. Open its source for the algorithm. |
| `_node` (function) | Implementation helper. Open its source for the algorithm. |
| `_endpoint` (function) | Implementation helper. Open its source for the algorithm. |
| `_payload` (function) | Implementation helper. Open its source for the algorithm. |
| `_read_receipt` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_retried` (function) | One JSON-RPC call, retried with a doubling wait while the node refuses or drops it, about four minutes in all. |
| `_head` (function) | Implementation helper. Open its source for the algorithm. |
| `_current_supply` (function) | The node's Primary Network supply counter and the height it holds for, the anchor of the supply reconstruction. |
| `_kept` (function) | The records and lines of a kept or earlier walk, cut back to the longest prefix where each line matches its record. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `_node_ranges` (function) | The heights each node answered in the walk this one extends. |
| `_result_block` (function) | Implementation helper. Open its source for the algorithm. |
| `_transactions` (function) | The block's transactions in order: a proposal block's one transaction, or a standard block's list. |
| `tx_type` (function) | The transaction type named by the fields the node's JSON carries; an unknown set of fields is an error. |
| `_amount` (function) | The amount of one input or output, through a stakeable lock if there is one. |
| `_avax` (function) | Implementation helper. Open its source for the algorithm. |
| `x_tx_type` (function) | The X-Chain transaction type named by the fields the node's JSON carries; an unknown set of fields is an error. |
| `_rows` (function) | One row per transaction of one captured block, or one row without a transaction for a block that has none. |
| `read_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `_summary` (function) | Implementation helper. Open its source for the algorithm. |
| `_chain_findings` (function) | Every block's parent is the block one height below it, and every block and transaction id appears once. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/pchain.py

Avalanche P-Chain RPC datasets: the current Primary Network validator snapshot.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/pchain.py)

| Component | Purpose from source |
| --- | --- |
| `load_capture` (function) | Read the captured JSON-RPC response and build the typed validator table in DuckDB. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `reconcile` (function) | Reconcile the snapshot against the Snowflake validator dataset by staking transaction hash. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/pool_history.py

DefiLlama yield histories for the opportunity-cost study: daily pool charts and the lending and borrowing snapshot.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/pool_history.py)

| Component | Purpose from source |
| --- | --- |
| `_path` (function) | Implementation helper. Open its source for the algorithm. |
| `_load_history` (function) | Implementation helper. Open its source for the algorithm. |
| `_load_lend_borrow` (function) | Implementation helper. Open its source for the algorithm. |
| `load_capture` (function) | Type the captured responses into ``rows`` for the receipt's dataset. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/pstakers.py

Capture, for every staking period a P-Chain block walk sees end, the stake's own record and the reward it paid.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/pstakers.py)

| Component | Purpose from source |
| --- | --- |
| `_spec` (function) | Implementation helper. Open its source for the algorithm. |
| `_endpoint` (function) | Implementation helper. Open its source for the algorithm. |
| `_parameters` (function) | Implementation helper. Open its source for the algorithm. |
| `_reading` (function) | Implementation helper. Open its source for the algorithm. |
| `staking_hashes` (function) | The staking transactions the walk's reward transactions close, in walk order. With ``unrewarded-before-walk``, only those closed by an abort that the walk did not see start. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `_call` (function) | The URL and JSON body of the one request for a staking transaction. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `_earlier` (function) | An earlier capture's records and lines for the wanted stakes, each checked against the earlier receipt. |
| `_utc` (function) | Implementation helper. Open its source for the algorithm. |
| `reward_outputs` (function) | (count, AVAX sum) of reward UTXOs in hex: codec version, UTXO id, asset id, then a TransferOutput or a StakeableLockOut around one, and the hex encoding's 4-byte checksum. |
| `_row` (function) | Implementation helper. Open its source for the algorithm. |
| `read_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `_summary` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/ptx.py

Archive and check P-Chain transactions by hash from a public node, for burns the Snowflake share cannot settle.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/ptx.py)

| Component | Purpose from source |
| --- | --- |
| `_hashes` (function) | Implementation helper. Open its source for the algorithm. |
| `_endpoint` (function) | Implementation helper. Open its source for the algorithm. |
| `_payload` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `_avax` (function) | Sum of AVAX amounts and count over one input or output list of the node's transaction JSON. |
| `read_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `_summary` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/snowflake.py

Avalanche Snowflake share capture, transformation, and validation.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/snowflake.py)

| Component | Purpose from source |
| --- | --- |
| `DatasetSpec` (class) | One Snowflake dataset: its capture columns, typed table, and SQL checks. |
| `_avax_range` (function) | Implementation helper. Open its source for the algorithm. |
| `spec_for` (function) | Implementation helper. Open its source for the algorithm. |
| `query_definition` (function) | Implementation helper. Open its source for the algorithm. |
| `resolve_parameters` (function) | Implementation helper. Open its source for the algorithm. |
| `capture_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `capture` (function) | Implementation helper. Open its source for the algorithm. |
| `read_capture` (function) | Verify a capture's receipt, query text, and result hash, and return the receipt. |
| `load_capture` (function) | Read the compressed capture into DuckDB with the declared types and build the typed rows table. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `read_parquet` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/snowpeer.py

Snowpeer capture, transformation, and validation.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/snowpeer.py)

| Component | Purpose from source |
| --- | --- |
| `_number` (function) | Implementation helper. Open its source for the algorithm. |
| `transform` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/treasury.py

US Treasury daily par yield curve rates from the Treasury's public XML feed.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/treasury.py)

| Component | Purpose from source |
| --- | --- |
| `parse_feed` (function) | Rows of (date, tenor, maturity, rate as a fraction) from one year's Atom feed. |
| `load_capture` (function) | Parse every captured yearly feed and build the typed long table in DuckDB. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/validators_api.py

Avalanche Data API validator datasets: the active set with uptime and capacity, and the completed history with rewards.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/validators_api.py)

| Component | Purpose from source |
| --- | --- |
| `_reject` (function) | Implementation helper. Open its source for the algorithm. |
| `load_capture` (function) | Read the captured pages and build the typed validator table in DuckDB. One page per JSON line. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `reconcile_active` (function) | Two observers of one set: the RPC snapshot's nodes must be present, and uptime and delegated weight must agree. |
| `reconcile_completed` (function) | Every completed validation present in the Snowflake validator capture must name the same first reward address, stake, and reward. The API's reward is the potential reward whether or not the validation passed: on 2026-09-22 it equalled Snowflake's potential reward on all 56,963 validations, including the 1,397 Snowflake records as unrewarded, so pass or fail comes from Snowflake alone. When the delegator capture sits beside the validator capture, the API's delegated amount and delegator count must equal the sum and count of every delegation to the validation. When the full history's parquet sits there, every validation shared with it must read the same, which is the daily sweep's overlap check. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## sources/yields.py

DefiLlama pool yields filtered to Avalanche and major proof-of-stake staking products.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/sources/yields.py)

| Component | Purpose from source |
| --- | --- |
| `load_capture` (function) | Read the captured pools response, keep Avalanche pools and proof-of-stake products, and type them. |
| `summarize` (function) | Implementation helper. Open its source for the algorithm. |
| `build_preview` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `check` (function) | Implementation helper. Open its source for the algorithm. |

## staking_cohorts.py

Accepted staking commitments, summarized by calendar interval or upgrade era.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/staking_cohorts.py)

| Component | Purpose from source |
| --- | --- |
| `denominator_options` (function) | Show the selected calendar unit without changing the underlying view keys. |
| `_era_bucket_sql` (function) | Implementation helper. Open its source for the algorithm. |
| `_metric_column` (function) | Implementation helper. Open its source for the algorithm. |
| `accepted_commitments` (function) | Scan the pinned period log once; keep only small daily, role, era totals. |
| `distinct_identities` (function) | Count nodes, addresses, and distinct observed node-address links by interval. |
| `_source_cutoffs` (function) | Implementation helper. Open its source for the algorithm. |
| `_era_intervals` (function) | Implementation helper. Open its source for the algorithm. |
| `_report_digest` (function) | Implementation helper. Open its source for the algorithm. |
| `_report_utc` (function) | Implementation helper. Open its source for the algorithm. |
| `_report_iso` (function) | Implementation helper. Open its source for the algorithm. |
| `_canonical_inputs` (function) | Verify explicit pin bytes and receipts before opening any analytical relation. |
| `_canonical_windows` (function) | Implementation helper. Open its source for the algorithm. |
| `_canonical_relations` (function) | Implementation helper. Open its source for the algorithm. |
| `_canonical_statistics` (function) | Exact row medians and cumulative-stake medians. Never median of daily medians. |
| `_canonical_stock_oracle` (function) | Reconstruct complete-day principal/effective stocks independently from pinned half-open intervals. |
| `era_stocks` (function) | Complete UTC days whose 23:59:59 stock observation lies in [start,end). |
| `_canonical_identity` (function) | Dated address groups on original principal, reconciled with the admitted ledger stock basis. |
| `canonical_era_table` (function) | Return a pure, pinned long table of 29 measure families for both roles and All plus nine eras. |
| `_calendar_starts` (function) | Implementation helper. Open its source for the algorithm. |
| `cohort_table` (function) | One row per covered interval and role, including intervals with no accepted commitments. |
| `rates_per` (function) | Change only the display rate unit; the accepted cohort and its totals stay fixed. |
| `for_population` (function) | Show only the address count that applies to the selected population. |
| `selected_columns` (function) | Keep context, then group selected quantities by denominator. |
| `display_column` (function) | Translate an internal heading without changing its meaning or units. |
| `display_columns` (function) | Use readable headings without changing measure keys or units. |
| `quantity_colors` (function) | Resolve plotted columns from quantity definitions, independent of draw order. |
| `_upgrade_axis` (function) | Label upgrade starts above the calendar axis, as in the staking canvas. |
| `_legend_interaction` (function) | Implementation helper. Open its source for the algorithm. |
| `_hover_number` (function) | Implementation helper. Open its source for the algorithm. |
| `_cohort_data` (function) | Build the checked cohort tables once per pinned run in this kernel. |
| `_window_table` (function) | Recompute exact acceptance cohorts for inclusive UTC calendar dates. |
| `_CohortCommGuard` (class) | Ignore returned notebook patches instead of echoing stale widget values. |
| `_CohortChartPane` (class) | Give each live notebook document its own persistent figure. |
| `_CohortChart` (class) | Keep the notebook's model graph stable; selection changes only visibility. |
| `StakingCohorts` (class) | Fast notebook view of one checked staking-period release. |

## staking_durations.py

Commitment-weighted and stake-weighted durations of weekly acceptance cohorts.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/staking_durations.py)

| Component | Purpose from source |
| --- | --- |
| `mean_commitment_durations` (function) | Derive two means from additive cohort totals without averaging daily means. |
| `StakingDurations` (class) | Compare duration means using an existing cohort object's shared selections. |

## staking_renewal.py

Same-node renewal of ended validator commitments, with explicit follow-up.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/staking_renewal.py)

| Component | Purpose from source |
| --- | --- |
| `renewal_events` (function) | Pair successive commitments on each node before selecting an end cohort. |
| `renewal_summary` (function) | Unweighted renewal share for endings in [start, end), with full follow-up. |

## staking_state.py

Active staking stocks and supply on a checked common daily support.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/staking_state.py)

| Component | Purpose from source |
| --- | --- |
| `daily_state` (function) | Keep missing days as gaps and use identical support for all stocks/ratios. |
| `summarize_state` (function) | Reduce snapshots or daily ratios, never sum snapshots as an active stock. |
| `_state_data` (function) | Implementation helper. Open its source for the algorithm. |
| `StakingState` (class) | A snapshot explorer, separate from acceptance-cohort clocks and controls. |

## subnets.py

Moved to ``avalanche_research.datasets.derived.subnets``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/subnets.py)

Imported components: `alias`.

## treasury.py

Moved to ``avalanche_research.sources.treasury``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/treasury.py)

Imported components: `alias`.

## uptime_hourly.py

Moved to ``avalanche_research.datasets.derived.uptime_hourly``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/uptime_hourly.py)

Imported components: `alias`.

## validators_api.py

Moved to ``avalanche_research.sources.validators_api``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/validators_api.py)

Imported components: `alias`.

## views/__init__.py

Views: notebook and site projections of stored results and mechanism objects.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/views/__init__.py)

## views/diagrams/__init__.py

Structure diagrams as Graphviz `dot`, generated in Python and never written by hand.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/views/diagrams/__init__.py)

| Component | Purpose from source |
| --- | --- |
| `Node` (class) | Implementation helper. Open its source for the algorithm. |
| `Diagram` (class) | Implementation helper. Open its source for the algorithm. |
| `_quote` (function) | Implementation helper. Open its source for the algorithm. |
| `_attributes` (function) | Implementation helper. Open its source for the algorithm. |
| `_style` (function) | Implementation helper. Open its source for the algorithm. |
| `to_dot` (function) | Sorted DOT text: nodes by rank then id, edges by endpoints, the legend from the roles used. |
| `dot_version` (function) | Implementation helper. Open its source for the algorithm. |
| `save` (function) | Write NAME.dot, .svg, .png and .json. Refuses a diagram for which Graphviz prints a warning. |

## views/diagrams/lineage.py

The data path from the chain to the two tables the model reads, built from the run receipts.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/views/diagrams/lineage.py)

| Component | Purpose from source |
| --- | --- |
| `_role` (function) | Implementation helper. Open its source for the algorithm. |
| `_inputs` (function) | Implementation helper. Open its source for the algorithm. |
| `walk` (function) | Every run the two tables depend on, with its receipts and the runs it reads. |
| `_rows` (function) | Implementation helper. Open its source for the algorithm. |
| `_seam_line` (function) | Implementation helper. Open its source for the algorithm. |
| `build` (function) | Implementation helper. Open its source for the algorithm. |
| `manifest` (function) | Implementation helper. Open its source for the algorithm. |
| `_escape` (function) | Implementation helper. Open its source for the algorithm. |
| `_table` (function) | An HTML-like Graphviz label: a bold title, an optional note, and one row per dataset. |
| `build_memo` (function) | The same lineage at memo width: one box per provider with its captures, one for our walk, one for the seamed tables, the burn branch as one box, the two tables the model reads, and the model. An edge joins two boxes when a receipt in one names a run in the other. |

## views/mechanism_explorer.py

Notebook views of the mechanisms: rate curves, issuance on a cohort, admission, and a slider explorer.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/views/mechanism_explorer.py)

| Component | Purpose from source |
| --- | --- |
| `repriced` (function) | The cohort as if every stake started at ``start``. |
| `issuance_table` (function) | AVAX each mechanism would mint for the cohort, and its change against the chain. |
| `curves_plot` (function) | Implementation helper. Open its source for the algorithm. |
| `admission_table` (function) | Share of real validator periods each rule admits, by count and by AVAX. One row per period. |
| `admission_plot` (function) | Implementation helper. Open its source for the algorithm. |
| `explorer` (function) | Sliders for one mechanism's settings beside its curve against the chain and its issuance on the cohort. |
| `admission_explorer` (function) | Sliders for an admission rule beside its curve against the chain and the share of real stakes it admits. |

## views/model_results.py

Model v0.7 results as HoloViews figures: mechanism curves and issuance, the response sweep, the scorecard, and the version roadmap.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/views/model_results.py)

| Component | Purpose from source |
| --- | --- |
| `reference_mechanisms` (function) | The five reward designs of v0.7, labelled as in ``MECHANISM_COLORS``. |
| `mechanism_table` (function) | Annual reward rate by committed duration, 2 to 52 weeks, for each mechanism. |
| `mechanism_plot` (function) | Left: annual reward rate by committed duration. Right: AVAX each design mints for the reference cohort. |
| `response_sweep` (function) | Validators after ``timesteps`` days and AVAX issued, by mechanism and response strength, from ``origin``. |
| `sweep_plot` (function) | Validators after 180 days against AVAX issued, one panel per response strength, 10 to 90 percent bars. |
| `lifecycle_scores` (function) | The lifecycle model scored at 30 and 90 days after each origin against holding the origin value. |
| `score_plot` (function) | Absolute error as a percent of the actual value: the model's mean of 20 runs against holding the origin value. |
| `development_score_plot` (function) | Mean scaled error by horizon for each model and each simple forecast, from ``model_development_scores.py``. |
| `roadmap_plot` (function) | Each model version on the date of the call that shows it, with the events that frame the plan. |
| `reference_issuance` (function) | AVAX each mechanism mints for the reference cohort, as ``issuance_table``. |

## views/model_structure.py

The structure of a cadCAD model, traced from its code and drawn with Graphviz.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/views/model_structure.py)

| Component | Purpose from source |
| --- | --- |
| `_Recorder` (class) | Implementation helper. Open its source for the algorithm. |
| `Trace` (class) | Implementation helper. Open its source for the algorithm. |
| `trace` (function) | Which keys each policy and update of ``model`` reads and writes, from one recorded call of each. |
| `tiny_lifecycle` (function) | A lifecycle model on a small synthetic state, enough to trace its structure. |
| `_node` (function) | Implementation helper. Open its source for the algorithm. |
| `_edge` (function) | Implementation helper. Open its source for the algorithm. |
| `_small` (function) | Implementation helper. Open its source for the algorithm. |
| `lifecycle_dot` (function) | Graphviz source for the lifecycle model's structure, from ``trace``. |
| `render` (function) | Write ``.dot``, ``.svg`` and ``.png`` beside ``out_stem`` with the system ``dot`` command. Each suffix is appended to the stem's whole name, so a stem with a dot in it, such as ``v0.8-structure``, keeps it. |
| `_AttributeRecorder` (class) | A read-only view of ``target`` that records each attribute read, in order. |
| `StageTrace` (class) | What one stage of the daily step read and returned, from one recorded call. |
| `trace_stages` (function) | Each stage of ``model.stages``, in run order, called once inside the model's own daily policy with the state, the day, its blocks and settings, the earlier stages' outputs, and the model itself (for a stage that is one of its methods) wrapped so every read is recorded. A block, setting or model attribute read as None is left out. |
| `tiny_stake_lifecycle` (function) | The released variant's model class on a small synthetic state, with its stake hurdle and logit return hazard, enough to trace its structure. Every stage has something to act on: commitments that end on the first day, a node out of the set, arrivals and a scheduled commitment. |
| `_wrapped` (function) | Implementation helper. Open its source for the algorithm. |
| `_stage_table` (function) | The daily step as one HTML-like table, a row per stage in run order, each row a port named by its stage. |
| `fitted_lifecycle_dot` (function) | Graphviz source for the released v0.8.0 model's structure. The stage order, what each stage reads (state, blocks, settings), which stage's output each state variable is updated from, the daily outputs, the KPIs and the other reward mechanisms are read from the code; only the labels' plain words are typed here. |

## weeks.py

Moved to ``avalanche_research.datasets.derived.weeks``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/weeks.py)

Imported components: `alias`.

## yields.py

Moved to ``avalanche_research.sources.yields``. This older name is the same module, kept so earlier code still imports.

[Source](https://github.com/AVL-Foundation/ext-bcrg-validator-research/blob/milestone-2/src/avalanche_research/yields.py)

Imported components: `alias`.
