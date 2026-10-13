"""Design rows and the streaming sweep runner, on the lifecycle model with synthetic inputs."""

import numpy as np
import pandas as pd
import pytest

pytest.importorskip("cadCAD")

from avalanche_research.model import designs, runner
from avalanche_research.model.lifecycle import ValidatorLifecycle

VARIABLES = ("active_validators", "active_validator_stake_navax")
BIG = 2**53 + 1


def base(**overrides):
    values = {"initial_stakes": np.array([BIG, 20, 30, 40]), "initial_days_left": np.array([1, 2, 3, 100]),
              "draw_durations": np.array([5, 9]), "draw_stakes": np.array([7, 11]), "entry_rate_per_day": 1.5,
              "renewal_probability": 0.5, "timesteps": 6, "runs": 3, "inputs_source": "synthetic"}
    return ValidatorLifecycle(**{**values, **overrides})


def comparable(frame):
    return frame.drop(columns="worker_peak_mib").sort_values(["row_id", "run", "timestep", "variable"]).reset_index(drop=True)


def test_a_sobol_design_extends_and_resumes_to_the_same_rows():
    bounds = {"renewal_probability": (0.5, 0.9), "entry_rate_per_day": (1.0, 9.0)}
    eight, sixteen = list(designs.sobol(bounds, 3, 7)), list(designs.sobol(bounds, 4, 7))
    assert [designs.settings(r) for r in eight] == [designs.settings(r) for r in sixteen[:8]]
    assert list(designs.sobol(bounds, 4, 7, start=8)) == sixteen[8:]
    assert list(designs.sobol(bounds, 3, 7, start=0)) == eight


def test_cardinality_and_row_ids_are_checked_before_launch():
    rows = list(designs.cartesian({"renewal_probability": [0.2, 0.8], "seed": [0, 1]}))
    designs.check_cardinality(rows, 4)
    with pytest.raises(ValueError, match="not 5"):
        designs.check_cardinality(rows, 5)
    with pytest.raises(ValueError, match="repeats"):
        designs.check_cardinality(rows + [{**rows[0], "index": 9}], 5)
    assert designs.row_id(rows[0], "aa") == designs.row_id(dict(rows[0]), "aa") != designs.row_id(rows[0], "bb")
    assert designs.design_hash(rows, "aa") != designs.design_hash(rows[::-1], "aa")


def test_an_interrupted_and_resumed_sweep_equals_a_clean_one(tmp_path):
    rows = list(designs.cartesian({"renewal_probability": [0.2, 0.8], "seed": [0, 1, 2]}))
    clean = runner.run_sweep(base(), rows, tmp_path / "clean", VARIABLES, workers=2)
    assert clean["written"] == 6 and not clean["stopped"]
    first = runner.run_sweep(base(), rows, tmp_path / "resumed", VARIABLES, workers=2, in_flight=1, stop_after=2)
    assert first["stopped"] and 2 <= first["written"] < 6
    (tmp_path / "resumed" / ".stale.parquet.tmp").write_bytes(b"partial")
    second = runner.run_sweep(base(), rows, tmp_path / "resumed", VARIABLES, workers=2)
    assert second["skipped"] == first["written"] and second["written"] == 6 - first["written"]
    assert not list((tmp_path / "resumed").glob(".*.tmp"))
    pd.testing.assert_frame_equal(comparable(runner.read_sweep(tmp_path / "clean")), comparable(runner.read_sweep(tmp_path / "resumed")))


def test_whole_navax_above_two_to_the_53_stay_exact(tmp_path):
    rows = list(designs.cartesian({"renewal_probability": [1.0]}))
    runner.run_sweep(base(entry_rate_per_day=0.0, initial_days_left=np.array([10, 10, 10, 10])), rows, tmp_path, VARIABLES, workers=1)
    paths = runner.read_sweep(tmp_path)
    stake = paths[(paths.variable == "active_validator_stake_navax") & (paths.timestep == 1)].value
    assert str(paths.value.dtype) == "int64" and set(stake.map(int)) == {BIG + 90}


def test_a_swept_setting_that_moves_nothing_is_named(tmp_path):
    # Under the chain's own reward rule the yield gap is zero, so the response multiplies nothing.
    rows = list(designs.cartesian({"renewal_response": [0.0, 0.3], "renewal_probability": [0.3, 0.7]}))
    runner.run_sweep(base(), rows, tmp_path, VARIABLES, workers=2)
    assert designs.no_effect(runner.read_sweep(tmp_path), ["renewal_response", "renewal_probability"]) == ["renewal_response"]


def test_a_sweep_receipt_names_every_row_file_and_finds_a_change(tmp_path):
    from avalanche_research.experiments import receipt

    pin_file = tmp_path / "pin.json"
    pin_file.write_text('{"schema_version": "avalanche-pins/v1", "name": "none", "runs": []}')
    model = base()
    rows = list(designs.cartesian({"renewal_probability": [0.2, 0.8]}))
    out = tmp_path / "sweep"
    stats = runner.run_sweep(model, rows, out, VARIABLES, workers=1)
    made = receipt.build_sweep(out, [model.specification()], designs.design_hash(rows, model.specification_hash()), len(rows), stats,
                               pin_file, [0], "start", "end", code={"commit": "abc", "dirty": False})
    assert made["sweep"]["complete"] and len(made["sweep"]["files"]) == 2 and made["output"]["rows"] > 0
    assert made["model"]["specifications"][0]["hash"] == model.specification_hash()
    assert receipt.check(made) == []
    partial = receipt.build_sweep(out, [model.specification()], "d", 5, stats, pin_file, [0], "s", "e", code={"commit": "abc", "dirty": False})
    assert any("of 5 rows" in finding for finding in receipt.check(partial))
    first = min(out.glob("*.parquet"))
    first.write_bytes(first.read_bytes() + b"\0")
    (out / "extra.parquet").write_bytes(b"x")
    assert sorted(receipt.check(made)) == sorted([f"row file {first.stem} changed", "row file extra is not in the receipt"])


def test_the_pool_is_sized_from_a_pilot_and_never_exceeds_memory_or_cpus():
    # RG1's measurement: 409 MiB at 5 runs and 2,100 MiB at 40.
    pilot = pd.DataFrame({"row_id": ["a", "b"], "worker_peak_mib": [409.0, 2100.0]})
    base_mib, per_run = runner.worker_memory(pilot, [5, 40])
    assert per_run == pytest.approx(48.31, abs=0.01) and base_mib == pytest.approx(167.4, abs=0.1)
    sized = runner.size_pool(16_000, base_mib, per_run, 20, cpus=16)
    assert sized["workers"] == 12 and sized["projected_mib"] <= 16_000
    assert runner.size_pool(16_000, base_mib, per_run, 20, cpus=4)["workers"] == 4
    with pytest.raises(ValueError, match="one worker needs"):
        runner.size_pool(2_500, base_mib, per_run, 40)
    with pytest.raises(ValueError, match="two run counts"):
        runner.worker_memory(pilot, [20, 20])


def final_counts(table, row):
    """A reducer: one row per run with the last day's validators, as a registry KPI reducer would."""
    last = table[(table.variable == "active_validators") & (table.timestep == table.timestep.max())]
    return pd.DataFrame({"run": last.run.to_numpy(), "final_validators": last.value.map(int).to_numpy()})


def builder(origin, model):
    from datetime import date
    return base(origin=date.fromisoformat(str(origin)))


def test_a_design_refuses_lockbox_origins_before_building_anything():
    rows = list(designs.cartesian({"origin": ["2025-04-08", "2025-11-19"]}))
    with pytest.raises(ValueError, match="lockbox"):
        designs.check_origins(rows)
    designs.check_origins(rows[:1])


def test_a_design_across_origins_is_hashed_and_written_before_its_rows(tmp_path):
    rows = list(designs.cartesian({"origin": ["2024-03-06", "2025-04-08"], "renewal_probability": [0.3, 0.7]}))
    calls = tmp_path.parent / "calls"

    def counted(origin, model):
        with calls.open("a") as handle:
            handle.write(f"{origin}\n")
        return builder(origin, model)

    totals = runner.run_design(rows, 4, counted, tmp_path, workers=2)
    record = __import__("json").loads((tmp_path / "design.json").read_text())
    assert totals["written"] == 4 and totals["groups"] == 2 and len(calls.read_text().split()) == 2 and totals["seconds"] > 0
    assert [spec["origin"] for spec in totals["base_specifications"]] == ["2024-03-06", "2025-04-08"]
    assert record["rows"] == 4 and len(record["row_ids"]) == 4 and record["design_hash"] == totals["design_hash"]
    written = [p.stat().st_mtime_ns for p in tmp_path.glob("*.parquet")]
    assert (tmp_path / "design.json").stat().st_mtime_ns <= min(written)
    assert set(runner.read_sweep(tmp_path).origin) == {"2024-03-06", "2025-04-08"}
    with pytest.raises(ValueError, match="not 5"):
        runner.run_design(rows, 5, builder, tmp_path / "other")


def test_with_both_responses_at_zero_designs_differ_only_in_issuance(tmp_path):
    # Contract check C1: two rows that differ only in mechanism give identical count and stake in every run.
    rows = list(designs.cartesian({"mechanism": ["ChainReward", {"name": "ACP285Ramp", "target_min_rate": 0.05}],
                                   "renewal_response": [0.0], "entry_response": [0.0]}))
    runner.run_sweep(base(), rows, tmp_path, workers=2)
    paths = runner.read_sweep(tmp_path)
    for variable in ("active_validators", "active_validator_stake_navax"):
        part = paths[paths.variable == variable].pivot_table(index=["run", "timestep"], columns="index", values="value")
        assert (part[0] == part[1]).all()
    with pytest.raises(ValueError, match="unknown reward mechanism"):
        runner.model_settings({"design": "x", "index": 0, "mechanism": "NoSuchRule"})


def test_a_reducer_keeps_one_row_per_run(tmp_path):
    rows = list(designs.cartesian({"renewal_probability": [0.3, 0.7]}))
    runner.run_sweep(base(), rows, tmp_path, workers=2, reducer=final_counts)
    kept = __import__("duckdb").execute(f"SELECT * FROM read_parquet('{tmp_path}/*.parquet')").df()
    assert len(kept) == 2 * 3 and set(kept.columns) >= {"row_id", "run", "final_validators", "specification"}


def test_available_memory_is_read_from_the_kernel(tmp_path):
    info = tmp_path / "meminfo"
    info.write_text("MemTotal:       65536000 kB\nMemAvailable:    8192000 kB\n")
    assert runner.available_mib(info) == pytest.approx(8000.0)
    info.write_text("MemTotal: 1 kB\n")
    with pytest.raises(OSError):
        runner.available_mib(info)


def test_the_sweep_command_runs_a_design_file_and_writes_its_receipt(tmp_path, monkeypatch):
    import json

    from click.testing import CliRunner

    from avalanche_research import cli
    from avalanche_research.experiments import receipt, sweep

    pin_file = tmp_path / "pin.json"
    pin_file.write_text('{"schema_version": "avalanche-pins/v1", "name": "p", "runs": [{"dataset_id": "derived.staking-periods", '
                        '"run": "synthetic", "sha256": "x", "parquet": "x.parquet", "bytes": 0, "check": "pass"}]}')
    monkeypatch.setattr(sweep, "builder", lambda periods, run, runs, timesteps, draws=None: builder)
    monkeypatch.setattr(sweep, "parquet_path", lambda dataset, run: "unused")
    monkeypatch.setattr(receipt, "code_commit", lambda directory=None: {"commit": "abc", "dirty": False, "package_version": "test"})
    monkeypatch.setattr(receipt.pins, "verify", lambda path, root=None: [])
    design = {"generator": "cartesian", "levels": {"renewal_probability": [0.3, 0.7]}, "seed": 0, "origins": ["2025-04-08"],
              "models": ["v0.7"], "rows": 2, "pin": str(pin_file), "runs": 3, "timesteps": 6, "workers": 2}
    (tmp_path / "design.json").write_text(json.dumps(design))
    result = CliRunner().invoke(cli.cli, ["model", "sweep", str(tmp_path / "design.json"), str(tmp_path / "out"), "--json"])
    assert result.exit_code == 0, result.output
    made = json.loads(result.output)["receipt"]
    assert made["sweep"]["complete"] and made["sweep"]["rows_written"] == 2 and (tmp_path / "out" / "receipt.json").is_file()
    assert receipt.check(made) == []
    again = CliRunner().invoke(cli.cli, ["model", "sweep", str(tmp_path / "design.json"), str(tmp_path / "again"), "--json"])
    assert again.exit_code == 0
    rerun = CliRunner().invoke(cli.cli, ["model", "sweep", str(tmp_path / "design.json"), str(tmp_path / "out")])
    assert rerun.exit_code != 0 and "receipt already exists" in str(rerun.exception)


def test_a_base_model_is_built_in_a_child_process_and_its_failure_is_raised(tmp_path):
    import os

    built = tmp_path / "pid"

    def build(origin, model):
        built.write_text(str(os.getpid()))
        return builder(origin, model)

    made = runner.build_apart(build, "2025-04-08", "test", tmp_path / "base.pickle")
    assert int(built.read_text()) != os.getpid()
    assert made["path"].is_file() and made["specification_hash"] == builder("2025-04-08", "test").specification_hash()

    def broken(origin, model):
        raise ValueError("no inputs")

    with pytest.raises(RuntimeError, match="failed in its child process"):
        runner.build_apart(broken, "2025-04-08", "test", tmp_path / "other.pickle")


def pinned_sweep(tmp_path, monkeypatch, findings=()):
    """The sweep module with a synthetic pin, a synthetic builder, and the pin's verification returning ``findings``."""
    from avalanche_research.experiments import receipt, sweep

    pin_file = tmp_path / "pin.json"
    pin_file.write_text('{"schema_version": "avalanche-pins/v1", "name": "p", "runs": [{"dataset_id": "derived.staking-periods", '
                        '"run": "synthetic", "sha256": "x", "parquet": "x.parquet", "bytes": 0, "check": "pass"}]}')
    monkeypatch.setattr(sweep, "builder", lambda periods, run, runs, timesteps, draws=None: builder)
    monkeypatch.setattr(sweep, "parquet_path", lambda dataset, run: "unused")
    monkeypatch.setattr(receipt, "code_commit", lambda directory=None: {"commit": "abc", "dirty": False, "package_version": "test"})
    monkeypatch.setattr(receipt.pins, "verify", lambda path, root=None: list(findings))
    return pin_file


def test_the_run_command_runs_one_scenario_from_a_pin_file(tmp_path, monkeypatch):
    import json

    from click.testing import CliRunner

    from avalanche_research import cli
    from avalanche_research.experiments import receipt

    pin_file = pinned_sweep(tmp_path, monkeypatch)
    args = ["model", "run", str(pin_file), str(tmp_path / "out"), "--origin", "2025-04-08", "--model", "v0.7", "--runs", "3",
            "--timesteps", "6", "--seed", "4", "--workers", "1", "--json"]
    result = CliRunner().invoke(cli.cli, args)
    assert result.exit_code == 0, result.output
    made = json.loads(result.output)["receipt"]
    assert made["sweep"]["rows_written"] == 1 and made["seeds"] == [4] and receipt.check(made) == []
    assert made["sweep"]["design_file"]["pin"] == str(pin_file)


def test_a_sweep_takes_the_pin_given_on_the_command_and_refuses_one_that_does_not_verify(tmp_path, monkeypatch):
    import json

    from avalanche_research.core.catalog import DataError
    from avalanche_research.experiments import sweep

    pin_file = pinned_sweep(tmp_path, monkeypatch)
    design = sweep.scenario(tmp_path / "missing.json", "2025-04-08", "v0.7", 3, 6, workers=1)
    made = sweep.run(design, tmp_path / "out", pin=pin_file)
    assert made["sweep"]["design_file"]["pin"] == str(pin_file) and json.loads((tmp_path / "out" / "receipt.json").read_text())
    pinned_sweep(tmp_path, monkeypatch, findings=["derived.staking-periods run synthetic differs from its pin"])
    with pytest.raises(DataError, match="does not verify"):
        sweep.run(sweep.scenario(pin_file, "2025-04-08", "v0.7", 3, 6, workers=1), tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


def test_a_kpi_reducer_refuses_an_unknown_kind_or_a_horizon_past_the_run():
    from pathlib import Path

    from avalanche_research.experiments import sweep

    design = {"timesteps": 90, "origins": ["2025-04-08"], "reducer": {"kind": "kpis", "horizons": [180], "competing_yield": 0.04,
                                                                       "operating_costs": {}}}
    with pytest.raises(ValueError, match="past the run"):
        sweep.kpi_reducer(design, Path("unused.json"), "unused")
    with pytest.raises(ValueError, match="unknown reducer"):
        sweep.kpi_reducer({**design, "reducer": {"kind": "paths"}}, Path("unused.json"), "unused")
    assert sweep.kpi_reducer({k: v for k, v in design.items() if k != "reducer"}, Path("unused.json"), "unused") is None


def test_the_kpi_reducer_keeps_one_row_per_run_measure_and_horizon_on_pinned_data(tmp_path):
    from pathlib import Path

    from avalanche_research.catalog import DataError
    from avalanche_research.experiments import sweep

    pin = Path("data/pins/p5-v0.7-report.json")
    design = {**sweep.scenario(pin, "2025-04-08", "v0.8", 2, 90, workers=1),
              "reducer": {"kind": "kpis", "horizons": [90, 30], "competing_yield": 0.04, "operating_costs": {"mid": 0.01}}}
    try:
        periods, run_name = sweep.pinned_periods(pin)
    except (DataError, FileNotFoundError, StopIteration):
        pytest.skip("the pinned runs are not built in this checkout")
    reducer = sweep.kpi_reducer(design, pin, periods)
    runner.run_design(sweep.rows(design), 1, sweep.builder(periods, run_name, 2, 90), tmp_path, workers=1, reducer=reducer)
    kept = __import__("duckdb").execute(f"SELECT * FROM read_parquet('{tmp_path}/*.parquet')").df()
    assert not kept.duplicated(["run", "measure", "horizon_days", "cost_level"]).any()
    assert set(kept["run"]) == {1, 2} and set(kept["horizon_days"]) == {30, 90}
    assert {"validator_stake_navax", "active_validators", "net_inflation"} <= set(kept["measure"])
    assert kept["value"].notna().all() and "timestep" not in kept.columns


def test_identical_reruns_give_identical_row_hashes(tmp_path):
    from avalanche_research.experiments import receipt

    rows = list(designs.cartesian({"renewal_probability": [0.2, 0.8]}))
    for name in ("first", "second"):
        runner.run_sweep(base(), rows, tmp_path / name, VARIABLES, workers=2)
    first, second = receipt._file_hashes(tmp_path / "first"), receipt._file_hashes(tmp_path / "second")
    assert first == second and len(first) == 2


def test_a_receipt_lists_every_base_and_refuses_a_row_whose_base_it_does_not_list(tmp_path):
    from avalanche_research.experiments import receipt

    pin_file = tmp_path / "pin.json"
    pin_file.write_text('{"schema_version": "avalanche-pins/v1", "name": "none", "runs": []}')
    rows = list(designs.cartesian({"origin": ["2024-03-06", "2025-04-08"], "renewal_probability": [0.3]}))
    out = tmp_path / "sweep"
    stats = runner.run_design(rows, 2, builder, out, workers=1)
    specifications = stats.pop("base_specifications")
    made = receipt.build_sweep(out, specifications, stats["design_hash"], 2, stats, pin_file, [0], "s", "e", code={"commit": "abc", "dirty": False})
    assert len(made["model"]["specifications"]) == 2 and receipt.check(made) == []
    one = receipt.build_sweep(out, specifications[:1], stats["design_hash"], 2, stats, pin_file, [0], "s", "e", code={"commit": "abc", "dirty": False})
    assert any("which the receipt does not list" in finding for finding in receipt.check(one))


def test_explicit_rows_are_taken_as_written_and_must_each_set_a_seed(tmp_path):
    import json

    from avalanche_research.experiments import receipt, sweep

    listed = [{"seed": 3, "renewal_probability": 0.3}, {"seed": 3, "renewal_probability": 0.7}, {"seed": 4, "renewal_probability": 0.3}]
    path = tmp_path / "rows.json"
    path.write_text(json.dumps(listed))
    design = {"generator": "explicit", "rows_file": str(path), "rows_sha256": receipt.sha256(path.read_bytes()), "origins": ["2025-04-08"],
              "models": ["v0.7"]}
    made = sweep.rows(design)
    assert [(row["seed"], row["renewal_probability"], row["index"]) for row in made] == [(3, 0.3, 0), (3, 0.7, 1), (4, 0.3, 2)]
    with pytest.raises(ValueError, match="rows_sha256"):
        sweep.rows({**design, "rows_sha256": "0" * 64})
    path.write_text(json.dumps([{"renewal_probability": 0.3}]))
    with pytest.raises(ValueError, match="must each set a seed"):
        sweep.rows({**design, "rows_sha256": receipt.sha256(path.read_bytes())})


def test_a_row_reads_the_competing_yield_from_its_own_outside_yield():
    from avalanche_research.experiments import sweep

    reducer = sweep.KpiReducer({}, [90], 0.04, {})
    assert reducer.competing_for({"outside_yield_pp": 7.0}) == pytest.approx(0.07) and reducer.competing_for({}) == 0.04


@pytest.mark.parametrize("row", [{"seed": True}, {"seed": -1}, {"seed": 1, "draw": 0.5}, {"seed": 1, "draw": True}])
def test_explicit_rows_refuse_ambiguous_noise_keys(tmp_path, row):
    import json
    from avalanche_research.experiments import sweep

    path = tmp_path / "rows.json"
    path.write_text(json.dumps([row]))
    from avalanche_research.experiments.receipt import sha256
    with pytest.raises(ValueError, match="nonnegative integer"):
        sweep.rows({"generator": "explicit", "rows_file": str(path), "rows_sha256": sha256(path.read_bytes()),
                    "origins": ["2025-04-08"], "models": ["v0.7"]})


def test_external_parquet_draws_use_the_installed_duckdb_reader(tmp_path):
    import duckdb
    from avalanche_research.experiments import receipt, sweep
    frame = pd.DataFrame({"renewal_shift": [0.0, 3.0]})
    path = tmp_path / "draws.parquet"
    with duckdb.connect() as con:
        con.register("draws", frame)
        con.execute("COPY draws TO ? (FORMAT PARQUET)", [str(path)])
    got = sweep.load_draws({"draws_file": str(path), "draws_sha256": receipt.sha256(path.read_bytes())})
    pd.testing.assert_frame_equal(got, frame)
    with pytest.raises(ValueError, match="draws_sha256"):
        sweep.load_draws({"draws_file": str(path), "draws_sha256": "0" * 64})


def test_explicit_sweep_records_external_file_hash_and_refuses_changed_input(tmp_path, monkeypatch):
    import json
    from avalanche_research.experiments import receipt, sweep

    pin = pinned_sweep(tmp_path, monkeypatch)
    path = tmp_path / "rows.json"
    path.write_text(json.dumps([{"seed": 4, "renewal_probability": 0.3}]))
    design = {**sweep.scenario(pin, "2025-04-08", "v0.7", 1, 6, workers=1),
              "generator": "explicit", "rows_file": str(path), "rows_sha256": receipt.sha256(path.read_bytes())}
    made = sweep.run(design, tmp_path / "out")
    frozen = made["sweep"]["design_file"]
    assert frozen["rows_sha256"] == receipt.sha256(path.read_bytes())
    assert receipt.check(made) == []
    path.write_text(json.dumps([{"seed": 5, "renewal_probability": 0.3}]))
    with pytest.raises(ValueError, match="rows_sha256"):
        sweep.run(frozen, tmp_path / "refused")
    assert not (tmp_path / "refused").exists()


def test_sweep_requires_external_hashes_and_one_draw_origin(tmp_path):
    from avalanche_research.experiments import sweep
    path = tmp_path / "rows.json"
    path.write_text('[{"seed": 1}]')
    with pytest.raises(ValueError, match="rows_file requires rows_sha256"):
        sweep.run({"rows_file": str(path)}, tmp_path / "out")
    from avalanche_research.experiments.receipt import sha256
    design = {"draws_file": str(path), "draws_sha256": sha256(path.read_bytes()), "runs": 1,
              "origins": ["2025-04-08", "2025-07-01"]}
    with pytest.raises(ValueError, match="one fitting origin"):
        sweep.run(design, tmp_path / "out")
    with pytest.raises(ValueError, match="one fitted model"):
        sweep.run({**design, "origins": ["2025-04-08"], "models": ["v0.8-a u", "v0.8-e u"]}, tmp_path / "out")


def test_external_rows_and_draws_parse_the_exact_hashed_snapshot(tmp_path, monkeypatch):
    import json
    from avalanche_research.experiments import receipt, sweep
    rows_path = tmp_path / "rows.json"
    draws_path = tmp_path / "draws.csv"
    rows_body = b'[{"seed": 1}]'
    draws_body = b'renewal_shift\n3.0\n'
    rows_path.write_bytes(rows_body)
    draws_path.write_bytes(draws_body)
    original = type(rows_path).read_bytes
    def read_then_replace(path):
        body = original(path)
        if path == rows_path:
            path.write_text('[{"seed": 9}]')
        elif path == draws_path:
            path.write_text('renewal_shift\n9.0\n')
        return body
    monkeypatch.setattr(type(rows_path), "read_bytes", read_then_replace)
    rows = sweep.rows({"generator": "explicit", "rows_file": str(rows_path), "rows_sha256": receipt.sha256(rows_body),
                       "origins": ["2025-04-08"], "models": ["v0.8-a u"]})
    draws = sweep.load_draws({"draws_file": str(draws_path), "draws_sha256": receipt.sha256(draws_body)})
    assert rows[0]["seed"] == 1 and draws.iloc[0]["renewal_shift"] == 3.0


def test_a_mechanism_iso_activation_date_reaches_its_typed_constructor():
    from datetime import date
    settings = runner.model_settings({"mechanism": {"name": "ACP285Ramp", "activation": "2025-11-18", "target_min_rate": 0.075}})
    assert settings["mechanism"].activation == date(2025, 11, 18)
    with pytest.raises(ValueError, match="ISO date"):
        runner.model_settings({"mechanism": {"name": "ACP285Ramp", "activation": "not-a-date"}})


@pytest.mark.parametrize("value", [True, float("nan"), float("inf")])
def test_reducer_refuses_nonfinite_or_boolean_outside_yield(value):
    from avalanche_research.experiments import sweep
    with pytest.raises(ValueError, match="finite"):
        sweep.KpiReducer({}, [90], 0.04, {}).competing_for({"outside_yield_pp": value})


def test_rows_sharing_a_seed_and_a_draw_share_their_noise_and_another_draw_differs(tmp_path):
    from pathlib import Path

    from avalanche_research.catalog import DataError
    from avalanche_research.experiments import sweep

    pin = Path("data/pins/p5-v0.7-report.json")
    try:
        periods, run_name = sweep.pinned_periods(pin)
    except (DataError, FileNotFoundError, StopIteration):
        pytest.skip("the pinned runs are not built in this checkout")
    draws = pd.DataFrame({"renewal_shift": [0.0, 3.0]})
    # With both responses at zero the renewal tenure changes nothing, so rows 0 and 1 differ only in a setting without effect.
    rows = [{"design": "noise", "index": i, "seed": 1, "draw": draw, "renewal_tenure": tenure, "origin": "2025-04-08", "model": "v0.8"}
            for i, (draw, tenure) in enumerate(((0, 4), (0, 5), (1, 4)))]
    runner.run_design(rows, 3, sweep.builder(periods, run_name, 1, 30, draws), tmp_path, workers=1)
    paths = runner.read_sweep(tmp_path)
    by_index = {i: frame.sort_values(["timestep", "variable"])["value"].to_numpy() for i, frame in paths.groupby("index")}
    assert (by_index[0] == by_index[1]).all() and not (by_index[0] == by_index[2]).all()
    with pytest.raises(ValueError, match="draw 5"):
        runner.run_design([{**rows[0], "draw": 5}], 1, sweep.builder(periods, run_name, 1, 30, draws), tmp_path / "bad", workers=1)


def test_design_provenance_binds_same_count_row_values_base_and_order(tmp_path, monkeypatch):
    # Exercise the actual design writer without a trajectory or fit.
    import json

    def skipped(*args, **kwargs):
        return {"skipped": 2, "written": 0, "seconds": 0, "parent_peak_mib": 0, "stopped": False}

    monkeypatch.setattr(runner, "_run_pickled", skipped)
    key = ("2024-03-06", "v0.8-a")
    rows = [{"origin": key[0], "model": key[1], "seed": 0, "draw": draw} for draw in (0, 1)]

    def written(name, values, base_hash):
        out = tmp_path / name
        bases = {key: {"path": out / "unused", "specification_hash": base_hash, "specification": {"origin": key[0]}}}
        totals = runner._run_groups({key: values}, bases, values, out, (), {})
        record = json.loads((out / "design.json").read_text())
        assert totals["design_hash"] == record["design_hash"]
        return record

    first = written("first", rows, "base-a")
    replay = written("replay", rows, "base-a")
    changed = written("changed", [{**row, "seed": 1} for row in rows], "base-a")
    rebased = written("rebased", rows, "base-b")
    reordered = written("reordered", rows[::-1], "base-a")
    assert first == replay
    assert len({record["design_hash"] for record in (first, changed, rebased, reordered)}) == 4
    assert first["row_ids"] == reordered["row_ids"][::-1]
