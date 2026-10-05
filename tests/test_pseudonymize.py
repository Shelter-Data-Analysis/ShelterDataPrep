"""Tests for tools/pseudonymize_ids.py, the rules docs/pseudonymizing.md states."""

from __future__ import annotations

import hashlib
import importlib.util
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelterprep import Prep, load                                  # noqa: E402

from test_pipeline import write_settings                            # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "pseudonymize_ids", ROOT / "tools" / "pseudonymize_ids.py")
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)

RAW_IDS = {"A{0:03d}".format(n) for n in range(1, 15)}


def main_run(tmp_path, **overrides):
    """Settings path and prepared file of a finished main run."""
    path = write_settings(tmp_path, **overrides)
    prep = Prep(load(path)).run(verbose=False)
    return path, prep.settings.dest_path


def mapping_of(tmp_path):
    return pd.read_csv(tmp_path / "private_animal_id.csv", dtype=str)


def test_map_gives_each_raw_id_one_distinct_pseudonym(tmp_path):
    settings, _ = main_run(tmp_path)
    assert tool.main(["map", str(settings)]) == 0
    mapping = mapping_of(tmp_path)
    assert set(mapping["animal_id"]) == RAW_IDS
    assert mapping["pseudonym"].is_unique
    assert not set(mapping["pseudonym"]) & RAW_IDS
    assert mapping["pseudonym"].str.fullmatch(r"P[0-9A-F]{12}").all()


def test_map_keeps_existing_pseudonyms_and_adds_only_new_ids(tmp_path):
    settings, _ = main_run(tmp_path)
    path = tmp_path / "private_animal_id.csv"
    path.write_text("animal_id,pseudonym\nA001,PKEEP\nZ999,PGONE\n")
    tool.main(["map", str(settings)])
    mapping = mapping_of(tmp_path)
    assert list(mapping["animal_id"][:2]) == ["A001", "Z999"]
    assert list(mapping["pseudonym"][:2]) == ["PKEEP", "PGONE"]
    assert set(mapping["animal_id"]) == RAW_IDS | {"Z999"}


def test_map_twice_leaves_the_mapping_unchanged(tmp_path):
    settings, _ = main_run(tmp_path)
    tool.main(["map", str(settings)])
    first = (tmp_path / "private_animal_id.csv").read_bytes()
    tool.main(["map", str(settings)])
    assert (tmp_path / "private_animal_id.csv").read_bytes() == first


def test_apply_without_a_mapping_makes_one_first(tmp_path):
    settings, _ = main_run(tmp_path)
    assert tool.main(["apply", str(settings)]) == 0
    assert set(mapping_of(tmp_path)["animal_id"]) == RAW_IDS
    assert (tmp_path / "out_pseudonymized.csv").exists()


def test_apply_changes_nothing_but_the_ids(tmp_path):
    # Mapped back, the pseudonymized file is the prepared file byte for byte.
    settings, prepared = main_run(tmp_path)
    tool.main(["apply", str(settings)])
    output = tmp_path / "out_pseudonymized.csv"
    frame = pd.read_csv(output, dtype=str, keep_default_na=False)
    assert not set(frame["animal_id"]) & RAW_IDS
    back = {p: a for a, p in tool.read_mapping(
        tmp_path / "private_animal_id.csv").items()}
    frame["animal_id"] = frame["animal_id"].map(lambda v: back.get(v, v))
    restored = tmp_path / "restored.csv"
    frame.to_csv(restored, index=False)
    assert restored.read_bytes() == prepared.read_bytes()


def test_apply_stops_on_an_unmapped_id_and_writes_nothing(tmp_path, capsys):
    settings, _ = main_run(tmp_path)
    (tmp_path / "private_animal_id.csv").write_text(
        "animal_id,pseudonym\nA001,PONE\n")
    assert tool.main(["apply", str(settings)]) == 1
    error = capsys.readouterr().err
    assert "13 animal ID(s)" in error
    assert "A002  (2 row(s))" in error
    assert not (tmp_path / "out_pseudonymized.csv").exists()


def test_apply_warns_but_succeeds_when_the_file_has_no_animal_id(
        tmp_path, capsys):
    settings, _ = main_run(tmp_path, output_columns=[
        "intake_date", "outcome_date", "outcome_type"])
    assert tool.main(["apply", str(settings)]) == 0
    assert "has no animal_id column" in capsys.readouterr().err
    assert not (tmp_path / "out_pseudonymized.csv").exists()
    assert not (tmp_path / "private_animal_id.csv").exists()


def test_apply_writes_to_a_named_output_and_logs_both_digests(tmp_path):
    settings, prepared = main_run(tmp_path)
    output = tmp_path / "elsewhere" / "shared.csv"
    tool.main(["apply", str(settings), "--output", str(output)])
    log = (tmp_path / "elsewhere" / "shared_run.txt").read_text()
    for path in (prepared, output):
        assert hashlib.sha256(path.read_bytes()).hexdigest() in log


def test_apply_refuses_to_overwrite_the_prepared_file(tmp_path):
    settings, prepared = main_run(tmp_path)
    before = prepared.read_bytes()
    assert tool.main(["apply", str(settings), "--output", str(prepared)]) == 1
    assert prepared.read_bytes() == before


def test_a_mapping_that_repeats_a_pseudonym_is_refused(tmp_path, capsys):
    # Two animals under one pseudonym would merge their stays downstream.
    settings, _ = main_run(tmp_path)
    rows = ["{0},P{1}".format(a, a) for a in sorted(RAW_IDS)]
    rows[1] = "A002,PA001"
    (tmp_path / "private_animal_id.csv").write_text(
        "animal_id,pseudonym\n" + "\n".join(rows) + "\n")
    assert tool.main(["apply", str(settings)]) == 1
    assert "repeats pseudonym value(s): PA001" in capsys.readouterr().err
    assert not (tmp_path / "out_pseudonymized.csv").exists()


@pytest.mark.parametrize("mode", ["map", "apply"])
def test_a_named_mapping_file_is_used(tmp_path, mode):
    settings, _ = main_run(tmp_path)
    mapping = tmp_path / "keys" / "ids.csv"
    tool.main([mode, str(settings), "--mapping", str(mapping)])
    assert set(pd.read_csv(mapping, dtype=str)["animal_id"]) == RAW_IDS
    assert not (tmp_path / "private_animal_id.csv").exists()
