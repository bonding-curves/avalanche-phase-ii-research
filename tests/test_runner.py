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
    made = receipt.build_sweep(out, model.specification(), designs.design_hash(rows, model.specification_hash()), len(rows), stats,
                               pin_file, [0], "start", "end", code={"commit": "abc", "dirty": False})
    assert made["sweep"]["complete"] and len(made["sweep"]["files"]) == 2 and made["output"]["rows"] > 0
    assert made["model"]["specifications"][0]["hash"] == model.specification_hash()
    assert receipt.check(made) == []
    partial = receipt.build_sweep(out, model.specification(), "d", 5, stats, pin_file, [0], "s", "e", code={"commit": "abc", "dirty": False})
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


def final_counts(table):
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
    calls = []
    totals = runner.run_design(rows, 4, lambda o, m: calls.append(o) or builder(o, m), tmp_path, workers=2)
    record = __import__("json").loads((tmp_path / "design.json").read_text())
    assert totals["written"] == 4 and totals["groups"] == 2 and len(calls) == 2 and totals["seconds"] > 0
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
    monkeypatch.setattr(sweep, "builder", lambda periods, run, runs, timesteps: builder)
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
