"""The Milestone 2 sweep design: its counts, noise keys, bounds, row format and repeatability."""

from __future__ import annotations

import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import m2_sweep_design as m2

from avalanche_research import mechanisms
from avalanche_research.model.designs import settings
from avalanche_research.model.fitted_lifecycle import FittedLifecycle
from avalanche_research.model.response import FittedMenu

FITTED = 4.144417670682732
VARIANT = "v0.8-a u"


@pytest.fixture(scope="module")
def design():
    rows, labels, keys = m2.build(VARIANT, FITTED)
    return rows, labels, keys


def key(row):
    return row["seed"], row["draw"]


def by_block(rows, labels):
    table = defaultdict(dict)
    for row, label in zip(rows, labels):
        table[label["family"], label["yield_pp"], label["block"]][label["i"], label["j"]] = (row, label)
    return table


def test_the_counts_are_exact(design):
    rows, labels, keys = design
    assert len(rows) == m2.TOTAL_ROWS == 74_176 + 58_624
    assert m2.counts(labels) == {"A": 8192, "B": 8192, "AB": 22528, "BA": 22528, "noise": 8192, "zero": 1024,
                                 "stress": 3072, "control": 448, "baseline": 58_624}
    assert sum(1 for label in labels if label["block"] in ("A", "B", "AB", "BA")) == m2.SALTELLI_ROWS == 61_440
    per = defaultdict(int)
    for label in labels:
        if label["block"] in ("A", "B", "AB", "BA"):
            per[label["family"], label["yield_pp"]] += 1
    assert per == {(f.code, y): 512 * (2 * f.k + 2) for f in m2.FAMILIES for y in m2.YIELDS}
    assert {f.code: f.k for f in m2.FAMILIES} == {"ramp": 3, "before": 2, "tenure": 3, "quadratic": 3}
    assert keys == m2.expected_keys() == 24_896


def test_hybrid_rows_inherit_their_matrix_key_and_take_one_column_from_the_other(design):
    rows, labels, _ = design
    table = by_block(rows, labels)
    for family in m2.FAMILIES:
        for y in m2.YIELDS:
            a, b = table[family.code, y, "A"], table[family.code, y, "B"]
            for i in range(m2.N):
                (row_a, label_a), (row_b, label_b) = a[i, None], b[i, None]
                assert key(row_a) != key(row_b)
                ua = [label_a[f"u{c + 1}"] for c in range(family.k)]
                ub = [label_b[f"u{c + 1}"] for c in range(family.k)]
                for j in range(1, family.k + 1):
                    row_ab, label_ab = table[family.code, y, "AB"][i, j]
                    row_ba, label_ba = table[family.code, y, "BA"][i, j]
                    assert key(row_ab) == key(row_a) and key(row_ba) == key(row_b)
                    assert [label_ab[f"u{c + 1}"] for c in range(family.k)] == [ub[c] if c == j - 1 else ua[c] for c in range(family.k)]
                    assert [label_ba[f"u{c + 1}"] for c in range(family.k)] == [ua[c] if c == j - 1 else ub[c] for c in range(family.k)]


def test_ordinary_keys_belong_to_one_family_and_yield(design):
    rows, labels, _ = design
    owners = defaultdict(set)
    for row, label in zip(rows, labels):
        if label["block"] in ("A", "B", "AB", "BA", "noise"):
            owners[key(row)].add((label["family"], label["yield_pp"], label["block"] if label["block"] == "noise" else "saltelli"))
    assert all(len(owner) == 1 for owner in owners.values())
    assert len(owners) == 2 * 512 * 16 + 64 * 8 * 16


def test_noise_replicates_are_the_first_64_points_of_a_each_on_8_new_keys(design):
    rows, labels, _ = design
    table = by_block(rows, labels)
    for family in m2.FAMILIES:
        for y in m2.YIELDS:
            noise = table[family.code, y, "noise"]
            assert len(noise) == 64 * 8
            for i in range(64):
                row_a, label_a = table[family.code, y, "A"][i, None]
                replicates = [noise[i, r] for r in range(8)]
                assert len({key(row) for row, _ in replicates} | {key(row_a)}) == 9
                for row, label in replicates:
                    assert {k: v for k, v in row.items() if k not in ("seed", "draw")} == {k: v for k, v in row_a.items() if k not in ("seed", "draw")}
                    assert [label[f"u{c}"] for c in (1, 2, 3)] == [label_a[f"u{c}"] for c in (1, 2, 3)]


def test_response_zero_stress_and_control_keys_are_free_of_family(design):
    rows, labels, _ = design
    shared = defaultdict(set)
    control = defaultdict(set)
    elsewhere = set()
    for row, label in zip(rows, labels):
        if label["block"] in ("zero", "stress"):
            shared[label["yield_pp"], label["i"]].add(key(row))
        elif label["block"] == "control":
            control[label["i"]].add(key(row))
        elif label["block"] != "baseline":
            elsewhere.add(key(row))
    assert len(shared) == 4 * 64 and all(len(keys) == 1 for keys in shared.values())
    assert len({next(iter(keys)) for keys in shared.values()}) == 4 * 64
    assert len(control) == 64 and all(len(keys) == 1 for keys in control.values())
    control_keys = {next(iter(keys)) for keys in control.values()}
    shared_keys = {next(iter(keys)) for keys in shared.values()}
    assert not control_keys & shared_keys and not (control_keys | shared_keys) & elsewhere
    per_key = defaultdict(list)
    for row, label in zip(rows, labels):
        if label["block"] in ("zero", "stress"):
            per_key[key(row)].append((label["family"], label["block"], label["j"]))
    assert all(len(group) == 4 + 3 * 4 and len(set(group)) == 16 for group in per_key.values())


def test_every_key_has_its_own_seed_and_its_own_draw(design):
    rows, _, keys = design
    pairs = {key(row) for row in rows}
    assert len(pairs) == keys
    assert len({seed for seed, _ in pairs}) == keys
    assert sorted(draw for _, draw in pairs) == list(range(keys))
    assert all(type(row["seed"]) is int and type(row["draw"]) is int and row["seed"] > 0 for row in rows)


def test_every_input_is_within_its_bounds_and_the_fixed_settings_are_exact(design):
    rows, labels, _ = design
    for row, label in zip(rows[:m2.DESIGN_ROWS], labels[:m2.DESIGN_ROWS]):
        family = m2.BY_CODE[label["family"]]
        mechanism = row["mechanism"]
        assert row["origin"] == "2025-11-18" and row["model"] == VARIANT and row["fitted_outside_yield_pp"] == FITTED
        if label["block"] in ("A", "B", "AB", "BA", "noise"):
            assert row["outside_yield_pp"] in m2.YIELDS
            assert 0 <= row["renewal_response"] <= 0.1 and 0 <= row["entry_response"] <= 0.1
            if family.input_name:
                low, high = family.bounds
                assert low <= mechanism[family.input_name] <= high
            for c in range(family.k):
                assert 0 <= label[f"u{c + 1}"] < 1
        elif label["block"] == "zero":
            assert (row["renewal_response"], row["entry_response"]) == (0.0, 0.0) and row["outside_yield_pp"] in m2.YIELDS
        elif label["block"] == "stress":
            expected = {1: (0.3, 0.0), 2: (0.0, 0.3), 3: (0.3, 0.3)}[label["j"]]
            assert (row["renewal_response"], row["entry_response"]) == expected
        if label["block"] in ("zero", "stress") and family.input_name:
            assert mechanism[family.input_name] == family.middle
        if label["family"] == "ramp":
            assert mechanism["activation"] == "2025-11-18T16:00:00+00:00" and mechanism["ramp_days"] == 90
        if label["family"] == "before":
            assert mechanism == {"name": "ACP285Ramp", "target_min_rate": 0.1}
    controls = defaultdict(set)
    for row, label in zip(rows, labels):
        if label["block"] == "control":
            controls[label["j"]].add((label["family"], tuple(sorted((k, v) for k, v in row["mechanism"].items() if k != "name")),
                                      row["renewal_response"], row["entry_response"], row["outside_yield_pp"]))
    assert {j: len(s) for j, s in controls.items()} == dict.fromkeys(range(1, 8), 1)
    flat = {j: next(iter(s)) for j, s in controls.items()}
    assert [flat[j][0] for j in range(1, 8)] == ["before"] * 3 + ["ramp"] * 2 + ["tenure"] * 2
    assert [flat[j][2:] for j in (1, 2, 3)] == [(0.0, 0.0, FITTED), (0.1, 0.0, FITTED), (0.0, 0.1, FITTED)]
    assert all(flat[j][2:] == (0.05, 0.05, 5.0) for j in (4, 5, 6, 7))
    assert dict(flat[4][1])["target_min_rate"] == 0.05 and dict(flat[5][1])["target_min_rate"] == 0.10
    assert dict(flat[6][1])["boost_max"] == 0.0 and dict(flat[7][1])["boost_max"] == 0.2


def test_rows_hold_only_the_runner_keys_and_every_setting_is_a_model_setting(design):
    rows, _, _ = design
    model_settings = set(FittedLifecycle.param.objects())
    for row in rows:
        assert tuple(row) == m2.ROW_KEYS
        assert set(settings(row)) - {"draw"} <= model_settings


def test_every_mechanism_is_built_by_its_class_once_its_dates_are_read(design):
    rows, _, _ = design
    seen = {}
    for row in rows:
        spec = row["mechanism"]
        seen[tuple(sorted((k, v) for k, v in spec.items() if k not in ("target_min_rate", "boost_max", "exponent")))] = spec
    for spec in seen.values():
        options = {k: (datetime.fromisoformat(v) if k == "activation" else v) for k, v in spec.items() if k != "name"}
        built = getattr(mechanisms, spec["name"])(**options)
        assert isinstance(built, mechanisms.RewardMechanism)


@pytest.mark.parametrize("start", [datetime(2025, 11, 19, 12, tzinfo=UTC), datetime(2026, 9, 23, 12, tzinfo=UTC),
                                   datetime(2026, 11, 18, 12, tzinfo=UTC)])
def test_the_before_family_holds_the_rule_before_acp285_at_every_start(start):
    before = mechanisms.ACP285Ramp(target_min_rate=m2.RULE_BEFORE_ACP285_MIN_RATE)
    menu = FittedMenu(fitted_at=datetime(2025, 11, 19, tzinfo=UTC))
    assert before.config(start) == menu.config(start)
    supply = 465_000_000 * 10**9
    assert before.annual_rate(30, supply, start) == menu.annual_rate(30, supply, start)


@pytest.mark.parametrize("start", [datetime(2025, 11, 19, 12, tzinfo=UTC), datetime(2026, 9, 23, 12, tzinfo=UTC),
                                   datetime(2026, 11, 18, 12, tzinfo=UTC)])
def test_the_tenure_and_quadratic_rows_price_every_stake_on_the_rule_before_acp285(design, start):
    rows, labels = design[0], design[1]
    menu = FittedMenu(fitted_at=datetime(2025, 11, 19, tzinfo=UTC))
    seen = set()
    for row, label in zip(rows, labels):
        if label["family"] in ("tenure", "quadratic") and label["family"] not in seen:
            seen.add(label["family"])
            assert row["mechanism"]["acp285"] is False
            built = getattr(mechanisms, row["mechanism"]["name"])(**{k: v for k, v in row["mechanism"].items() if k != "name"})
            assert built.config(start) == menu.config(start)
    assert seen == {"tenure", "quadratic"}


def test_the_design_repeats_byte_for_byte(design, tmp_path):
    rows, labels, keys = design
    again = m2.build(VARIANT, FITTED)
    assert m2.rows_bytes(again[0]) == m2.rows_bytes(rows) and m2.labels_bytes(again[1]) == m2.labels_bytes(labels) and again[2] == keys
    frame = pd.DataFrame({"renewal.intercept": [0.1, -0.2, 1 / 3], "renewal_shift": [0.0, 0.5, -0.25], "resample_seed": [1, 2, 3]})
    m2.write_parquet(frame, tmp_path / "one.parquet")
    m2.write_parquet(frame, tmp_path / "two.parquet")
    assert (tmp_path / "one.parquet").read_bytes() == (tmp_path / "two.parquet").read_bytes()
    assert m2.design_seed("ramp", 3.0) != m2.design_seed("ramp", 5.0) != m2.design_seed("before", 5.0)


def test_a_variant_without_draws_is_run_by_its_draw_reading_name():
    assert m2.model_variant("v0.8-a") == "v0.8-a u" and m2.model_variant("v0.8-a u") == "v0.8-a u"
    assert m2.model_variant("v0.8.0") == "v0.8.0"
    with pytest.raises(ValueError, match="reads parameter draws"):
        m2.model_variant("v0.7")


def test_the_design_names_its_files_relative_to_its_folder_so_it_is_the_same_anywhere(tmp_path):
    for name in ("one", "two"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "rows.json").write_bytes(b"[]")
        (tmp_path / name / "draws.parquet").write_bytes(b"draws")
    one, two = m2.file_fields(tmp_path / "one"), m2.file_fields(tmp_path / "two")
    assert one == two
    assert one["rows_file"] == "rows.json" and one["draws_file"] == "draws.parquet"


def test_every_design_row_pairs_with_the_chain_rule_run_on_its_own_key_responses_and_yields(design):
    rows, labels, _ = design
    design_rows, baselines = rows[:m2.DESIGN_ROWS], rows[m2.DESIGN_ROWS:]
    assert all(label["block"] == "baseline" and label["family"] == "chain" for label in labels[m2.DESIGN_ROWS:])
    assert all(row["mechanism"] == {"name": "ChainReward"} for row in baselines)
    users = defaultdict(int)
    for row, label in zip(design_rows, labels):
        partner = rows[label["baseline"]]
        assert {k: v for k, v in partner.items() if k != "mechanism"} == {k: v for k, v in row.items() if k != "mechanism"}
        users[label["baseline"]] += 1
    assert set(users) == set(range(m2.DESIGN_ROWS, m2.TOTAL_ROWS))
    assert len({tuple(row[name] for name in m2.PAIRED) for row in baselines}) == len(baselines)
    table = by_block(rows, labels)
    for family in m2.FAMILIES:
        a, ab = table[family.code, 5.0, "A"], table[family.code, 5.0, "AB"]
        if family.input_name:
            # A_i with its mechanism input from B_i is the same run under the chain's rule as A_i.
            assert all(ab[i, 1][1]["baseline"] == a[i, None][1]["baseline"] for i in range(512))
        assert all(ab[i, family.k][1]["baseline"] != a[i, None][1]["baseline"] for i in range(512))


@pytest.mark.parametrize("plant", ["negative entry response", "negative ramp target", "earlier origin", "wrong family label",
                                   "baseline on another key", "baseline under another rule", "wrong index",
                                   "wrong block", "ordinary response at the stress level"])
def test_check_refuses_a_row_whose_settings_or_label_are_wrong(design, plant):
    rows, labels, keys = (list(map(dict, design[0])), [dict(label) for label in design[1]], design[2])
    i = next(n for n, label in enumerate(labels) if label["family"] == "ramp" and label["block"] == "A")
    if plant == "negative entry response":
        rows[i]["entry_response"] = -0.01
    elif plant == "negative ramp target":
        rows[i]["mechanism"] = {**rows[i]["mechanism"], "target_min_rate": -0.05}
    elif plant == "earlier origin":
        rows[i]["origin"] = "2025-10-01"
    elif plant == "wrong index":
        labels[i]["index"] = 100
    elif plant == "wrong block":
        labels[i]["block"] = "control"
    elif plant == "ordinary response at the stress level":
        rows[i]["renewal_response"] = 0.3
    elif plant == "baseline on another key":
        labels[i]["baseline"] = labels[i + 1]["baseline"]
    elif plant == "baseline under another rule":
        rows[labels[i]["baseline"]]["mechanism"] = {"name": "ACP285Ramp", "target_min_rate": 0.1}
    else:
        labels[i]["family"] = "tenure"
    with pytest.raises(ValueError):
        m2.check(rows, labels, m2.SALTELLI_ROWS, keys)


def test_parquet_is_written_into_a_folder_whose_name_holds_a_quote(tmp_path):
    folder = tmp_path / "output's"
    folder.mkdir()
    m2.write_parquet(pd.DataFrame({"a": [1, 2]}), folder / "draws.parquet")
    assert (folder / "draws.parquet").stat().st_size > 0
