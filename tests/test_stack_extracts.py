"""Tests for tools/stack_extracts.py, the rules docs/stacking.md states."""

from __future__ import annotations

import importlib.util
from datetime import date
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location(
    "stack_extracts", ROOT / "tools" / "stack_extracts.py")
tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(tool)

HEADER = ["Impound", "Intake Date", "Outcome Date", "Outcome Type"]


def write_csv(path, rows, header=True):
    lines = ([",".join(HEADER)] if header else []) + [",".join(r) for r in rows]
    path.write_text("\n".join(lines) + "\n")
    return path


def two_years(tmp_path, second_header=False, later_row=None):
    """A 2014 file with a header and a 2015 file that repeats one stay."""
    a = write_csv(tmp_path / "2014.csv", [
        ["K1", "2014-03-01", "2014-04-01", "ADOPTION"],
        ["K2", "2014-12-20", "2015-01-10", "RTO"]])
    b = write_csv(tmp_path / "2015.csv", [
        later_row or ["K2", "2014-12-20", "2015-01-10", "RTO"],
        ["K3", "2015-06-01", "", ""]], header=second_header)
    return [a, b]


def stacked(tmp_path, inputs, **kw):
    out = tmp_path / "out.csv"
    lines = tool.run(out, inputs, "Impound", **kw)
    return pd.read_csv(out, dtype=str, keep_default_na=False), lines


def test_identical_copies_collapse_and_name_both_sources(tmp_path):
    frame, lines = stacked(tmp_path, two_years(tmp_path))
    assert list(frame["Impound"]) == ["K1", "K2", "K3"]
    assert frame.set_index("Impound").at["K2", tool.SOURCE] == \
        "2014.csv; 2015.csv"
    assert "1 keys repeated with identical copies" in "\n".join(lines)
    assert "0 keys whose copies disagree" in "\n".join(lines)


def test_disagreeing_copies_are_flagged_and_the_last_file_wins(tmp_path):
    inputs = two_years(tmp_path,
                       later_row=["K2", "2014-12-20", "2015-01-12", "RTO"])
    frame, lines = stacked(tmp_path, inputs)
    text = "\n".join(lines)
    assert "1 keys whose copies disagree" in text
    assert "K2 in 2014.csv, 2015.csv: Outcome Date differ" in text
    assert frame.set_index("Impound").at["K2", "Outcome Date"] == "2015-01-12"


def test_headerless_file_takes_the_header_and_is_logged(tmp_path):
    _, lines = stacked(tmp_path, two_years(tmp_path))
    assert any("2015.csv: no header row" in line for line in lines)


def test_headerless_file_with_other_width_stops_the_run(tmp_path):
    a = write_csv(tmp_path / "2014.csv", [["K1", "2014-03-01", "", ""]])
    b = tmp_path / "2015.csv"
    b.write_text("K2,2015-01-01,\n")
    with pytest.raises(tool.StackError):
        tool.run(tmp_path / "out.csv", [a, b], "Impound")
    assert not (tmp_path / "out.csv").exists()


def test_no_header_anywhere_stops_the_run(tmp_path):
    a = write_csv(tmp_path / "2014.csv", [["K1", "x", "y", "z"]], header=False)
    with pytest.raises(tool.StackError):
        tool.run(tmp_path / "out.csv", [a], "Impound")


def test_missing_and_extra_columns_are_flagged(tmp_path):
    a = write_csv(tmp_path / "2014.csv", [["K1", "2014-03-01", "", ""]])
    b = tmp_path / "2015.csv"
    b.write_text("Impound,Intake Date,Outcome Type,Sex\nK2,2015-01-01,,F\n")
    frame, lines = stacked(tmp_path, [a, b])
    text = "\n".join(lines)
    assert "2015.csv: lacks ['Outcome Date']" in text
    assert "2015.csv: adds ['Sex']" in text
    assert list(frame.columns) == HEADER + ["Sex", tool.SOURCE]


def test_same_fields_reported_when_they_match(tmp_path):
    _, lines = stacked(tmp_path, two_years(tmp_path, second_header=True))
    assert "  same in every file" in lines


def test_blank_keys_are_all_kept(tmp_path):
    a = write_csv(tmp_path / "2014.csv", [["", "2014-01-01", "", ""],
                                          ["", "2014-01-02", "", ""]])
    frame, lines = stacked(tmp_path, [a])
    assert len(frame) == 2
    assert "2 rows with a blank 'Impound'; all kept" in "\n".join(lines)


def test_no_source_drops_the_column(tmp_path):
    frame, _ = stacked(tmp_path, two_years(tmp_path), source=False)
    assert tool.SOURCE not in frame.columns


def test_xlsx_output_writes_dates_without_a_time(tmp_path):
    pytest.importorskip("openpyxl")
    src = tmp_path / "2014.xlsx"
    pd.DataFrame({"Impound": ["K1"],
                  "Intake Date": [pd.Timestamp("2014-03-01")]}).to_excel(
        src, index=False)
    out = tmp_path / "out.xlsx"
    tool.run(out, [src], "Impound")
    import openpyxl
    cell = openpyxl.load_workbook(out).active["B2"]
    assert cell.value.date() == date(2014, 3, 1)
    assert cell.number_format.lower() == "yyyy-mm-dd"
