"""Tests for the shelterprep pipeline.

Most of these pin down a specific decision documented in the README, so a test
name should read as the rule it protects.
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelterprep import Prep, SettingsError, SourceError, load       # noqa: E402
from shelterprep import dates, summary                              # noqa: E402
from shelterprep.pipeline import _age_group, _window_presence        # noqa: E402
from shelterprep.settings import NEGATIVE, OVER, UNKNOWN             # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"
AGE_GROUPS = {"JUVENILE": 1, "YOUNG": 4, "ADULT": 9, "SENIOR": 18}


def write_settings(tmp_path, **overrides):
    base = {
        "source_dir": str(FIXTURES),
        "source_file": "tiny.csv",
        "dest_dir": str(tmp_path),
        "dest_file": "out.csv",
        "output_columns": ["animal_id", "intake_date", "outcome_date",
                           "outcome_type", "animal_size"],
        "columns": {"animal_id": "Animal ID", "intake_date": "Intake Date",
                    "outcome_date": "Outcome Date", "dob": "DOB"},
        "age_groups": dict(AGE_GROUPS),
        "window_start_date": "2019-01-01",
        "window_end_date": "2021-12-31",
        "steps": [],
    }
    base.update(overrides)
    path = tmp_path / "settings.yaml"
    path.write_text(yaml.safe_dump(base, sort_keys=False), encoding="utf-8")
    return path


def prepared(tmp_path, **overrides):
    prep = Prep(load(write_settings(tmp_path, **overrides)))
    prep.read()
    prep.derive()
    prep.apply_steps()
    return prep


# --- age groups ------------------------------------------------------------

def test_age_cutoff_falls_in_the_lower_group():
    age = pd.Series([0.5, 1.0, 1.01, 4.0, 4.01, 9.0, 9.01, 18.0])
    groups = list(_age_group(age, AGE_GROUPS))
    assert groups == ["JUVENILE", "JUVENILE", "YOUNG", "YOUNG",
                      "ADULT", "ADULT", "SENIOR", "SENIOR"]


def test_age_sentinels_are_distinct():
    age = pd.Series([18.1, np.nan, -0.2])
    assert list(_age_group(age, AGE_GROUPS)) == [OVER, UNKNOWN, NEGATIVE]


# --- study window ----------------------------------------------------------

def _presence(intake, outcome):
    frame = pd.DataFrame({
        "intake_date": dates.to_datetime(pd.Series([intake])),
        "outcome_date": dates.to_datetime(pd.Series([outcome])),
    })
    return _window_presence(frame, pd.Timestamp("2020-01-01"),
                            pd.Timestamp("2020-12-31"))[0]


def test_a_stay_straddling_either_window_edge_is_in():
    assert _presence("2019-11-01", "2020-01-05") == "IN"   # straddles the open
    assert _presence("2020-12-20", "2021-02-01") == "IN"   # straddles the close


def test_window_edges_are_inclusive():
    assert _presence("2020-12-31", "2021-01-04") == "IN"
    assert _presence("2019-06-01", "2020-01-01") == "IN"
    assert _presence("2021-01-01", "2021-01-04") == "AFTER"
    assert _presence("2019-06-01", "2019-12-31") == "BEFORE"


def test_a_stay_still_in_care_is_in_however_old_its_intake():
    # No outcome date: the animal has not left, so it cannot be BEFORE.
    assert _presence("2015-01-01", None) == "IN"


def test_an_arrival_after_the_window_is_after_even_with_no_outcome():
    assert _presence("2021-06-01", None) == "AFTER"


def test_window_settings_must_be_given_together(tmp_path):
    path = write_settings(tmp_path, window_end_date=None)
    with pytest.raises(SettingsError, match="together"):
        load(path)


def test_window_start_must_precede_window_end(tmp_path):
    path = write_settings(tmp_path, window_start_date="2022-01-01",
                          window_end_date="2021-01-01")
    with pytest.raises(SettingsError, match="after"):
        load(path)


def test_filtering_on_window_presence_without_a_window_is_an_error(tmp_path):
    path = write_settings(tmp_path, window_start_date=None, window_end_date=None,
                          steps=[{"cut": {"window_presence": "BEFORE"}}])
    with pytest.raises(SettingsError, match="window_presence"):
        load(path)


# --- dates -----------------------------------------------------------------

def test_iso8601_keeps_rows_that_format_inference_would_destroy():
    # The regression this package exists for: pandas locks onto the first
    # value's format and coerces the rest to NaT.
    values = pd.Series(["2018-01-01 14:30:00", "2018-03-02"])
    assert pd.to_datetime(values, errors="coerce").isna().sum() == 1
    assert dates.to_datetime(values).notna().all()


def test_an_offset_stamped_source_still_parses_to_naive_datetime64():
    # The LA County extract writes local midnight as UTC. pandas returns
    # datetime64[ns, UTC] for that, which would break every later comparison.
    values = pd.Series(["2021/09/14 07:00:00+00", "2022/01/20 08:00:00+00", ""])
    parsed = dates.to_datetime(values, dates.MIXED)
    assert parsed.dtype == "datetime64[ns]"
    assert list(parsed.dt.strftime("%Y-%m-%d")[:2]) == ["2021-09-14", "2022-01-20"]


def test_mixed_parses_us_style_two_digit_years():
    values = pd.Series(["3/29/24", "4/10/15", "9/9/24"])
    parsed = dates.to_datetime(values, dates.MIXED)
    assert list(parsed.dt.strftime("%Y-%m-%d")) == ["2024-03-29", "2015-04-10",
                                                    "2024-09-09"]


def test_dates_are_datetime64_never_date_objects(tmp_path):
    frame = prepared(tmp_path).frame
    for column in ("intake_date", "outcome_date", "dob"):
        assert frame[column].dtype == "datetime64[ns]"
    # The comparison that raised TypeError in the old code.
    assert (frame["intake_date"] > pd.Timestamp("2019-01-01")).any()


def test_keep_time_does_not_shift_a_night_count(tmp_path):
    without = prepared(tmp_path).frame.set_index("animal_id")["nights"]
    with_time = prepared(tmp_path, keep_time=True).frame.set_index("animal_id")["nights"]
    assert without.equals(with_time)
    assert prepared(tmp_path).frame["intake_date"].dt.hour.eq(0).all()


def test_unparseable_dates_are_counted_not_silently_dropped(tmp_path):
    ledger = prepared(tmp_path).statistics.frame()
    row = ledger[(ledger.action == "parse_dates") & (ledger.column == "outcome_date")]
    assert int(row.rows_affected.iloc[0]) == 1   # the "not a date" row


def test_dates_are_written_as_iso_with_blanks_for_missing(tmp_path):
    prep = prepared(tmp_path)
    prep.write()
    written = pd.read_csv(prep.settings.dest_path, dtype=str)
    outcomes = written["outcome_date"].dropna()
    assert outcomes.str.match(r"^\d{4}-\d{2}-\d{2}$").all()
    assert written["outcome_date"].isna().any()   # still-in-care rows stay blank


# --- derived columns -------------------------------------------------------

def test_night_sign_marks_an_outcome_before_intake(tmp_path):
    frame = prepared(tmp_path).frame
    negative = frame[frame.night_sign == "-1"]
    assert list(negative.animal_id) == ["A005"]


def test_blank_text_becomes_the_unknown_sentinel(tmp_path):
    frame = prepared(tmp_path).frame
    assert frame.loc[frame.animal_id == "A014", "animal_size"].iloc[0] == UNKNOWN
    assert frame["animal_size"].notna().all()


# --- steps -----------------------------------------------------------------

def test_a_scalar_is_accepted_where_a_set_is_meant(tmp_path):
    scalar = prepared(tmp_path, steps=[{"cut": {"animal_type": "CAT"}}])
    listed = prepared(tmp_path, steps=[{"cut": {"animal_type": ["CAT"]}}])
    assert len(scalar.frame) == len(listed.frame) == 14


def test_a_cut_ands_its_columns(tmp_path):
    both = prepared(tmp_path, steps=[
        {"cut": {"animal_type": "DOG", "intake_type": "DISPO REQ"}}])
    assert "A007" not in set(both.frame.animal_id)
    assert len(both.frame) == 14   # only the row matching both is gone


def test_where_restricts_a_map(tmp_path):
    prep = prepared(tmp_path, steps=[
        {"map": {"outcome_type": {"ADOPTION": "TRANSFER"}},
         "where": {"outcome_subtype": "RESCUE"}}])
    frame = prep.frame.set_index("animal_id")
    assert frame.loc["A001", "outcome_type"] == "ADOPTION"   # no subtype
    assert (frame.loc["A002", "outcome_type"] == "TRANSFER").any()


def test_where_not_negates_the_whole_conjunction(tmp_path):
    prep = prepared(tmp_path, steps=[
        {"map": {"animal_size": {"PUPPY": "MED"}},
         "where_not": {"age_group": "JUVENILE"}}])
    frame = prep.frame.set_index("animal_id")
    # A004 is a PUPPY aged 1.002 years, so YOUNG, so not exempt.
    assert frame.loc["A004", "animal_size"] == "MED"


def test_an_empty_where_not_does_not_silence_the_step(tmp_path):
    prep = prepared(tmp_path, steps=[{"map": {"animal_size": {"PUPPY": "MED"}}}])
    assert "PUPPY" not in set(prep.frame.animal_size)


def test_a_map_leaves_unlisted_values_alone(tmp_path):
    prep = prepared(tmp_path, steps=[{"map": {"animal_size": {"LARGE": "LRG"}}}])
    sizes = set(prep.frame.animal_size)
    assert "LRG" in sizes and "SMALL" in sizes and "LARGE" not in sizes


# --- deduplication ---------------------------------------------------------

def _twice(tmp_path, intake, outcome, second_size="MED"):
    """A source file with one stay recorded twice."""
    frame = pd.read_csv(FIXTURES / "tiny.csv", dtype=str)
    rows = pd.DataFrame([
        {"Animal ID": "D001", "Intake Date": intake, "Outcome Date": outcome,
         "intake_type": "STRAY", "outcome_type": "ADOPTION", "outcome_subtype": "",
         "animal_type": "DOG", "DOB": "2019-01-01", "animal_size": size}
        for size in ("MED", second_size)])
    source = tmp_path / "dup.csv"
    pd.concat([frame, rows], ignore_index=True).to_csv(source, index=False)
    return dict(source_dir=str(tmp_path), source_file="dup.csv")


def test_dedup_drops_a_repeated_multi_night_stay(tmp_path):
    prep = prepared(tmp_path, steps=[{"dedup": None, "where": {"night_sign": "1"}}],
                    **_twice(tmp_path, "2020-03-01", "2020-03-08"))
    assert list(prep.frame.animal_id).count("D001") == 1


def test_dedup_leaves_a_repeated_same_day_stay_alone(tmp_path):
    # An animal really can come in and go out twice in one day, so this pair
    # is a judgement call for the downstream analysis, not for us.
    prep = prepared(tmp_path, steps=[{"dedup": None, "where": {"night_sign": "1"}}],
                    **_twice(tmp_path, "2020-03-01", "2020-03-01"))
    assert list(prep.frame.animal_id).count("D001") == 2


def test_dedup_keeps_rows_that_differ_in_any_output_column(tmp_path):
    prep = prepared(tmp_path, steps=[{"dedup": None, "where": {"night_sign": "1"}}],
                    **_twice(tmp_path, "2020-03-01", "2020-03-08", second_size="LARGE"))
    assert list(prep.frame.animal_id).count("D001") == 2


def test_dedup_compares_only_the_named_columns(tmp_path):
    prep = prepared(
        tmp_path,
        steps=[{"dedup": ["animal_id", "intake_date", "outcome_date"],
                "where": {"night_sign": "1"}}],
        **_twice(tmp_path, "2020-03-01", "2020-03-08", second_size="LARGE"))
    assert list(prep.frame.animal_id).count("D001") == 1


def test_dedup_keeps_the_last_row_of_each_group(tmp_path):
    # Rows matching on a subset can differ elsewhere; the later one is taken
    # to be the correction. Same tie-break as mLOS.
    prep = prepared(
        tmp_path,
        steps=[{"dedup": ["animal_id", "intake_date", "outcome_date"]}],
        **_twice(tmp_path, "2020-03-01", "2020-03-08", second_size="LARGE"))
    kept = prep.frame[prep.frame.animal_id == "D001"]
    assert list(kept.animal_size) == ["LARGE"]


def test_dedup_defaults_to_every_output_column(tmp_path):
    prep = prepared(tmp_path, steps=[{"dedup": None}],
                    **_twice(tmp_path, "2020-03-01", "2020-03-08"))
    row = prep.statistics.frame().query("action == 'dedup'").iloc[0]
    assert row.rows_in - row.rows_affected == row.rows_out
    assert "animal_size" in row.detail


def test_dedup_takes_a_list_of_columns_or_nothing(tmp_path):
    path = write_settings(tmp_path, steps=[{"dedup": {"on": "animal_id"}}])
    with pytest.raises(SettingsError, match="list of columns"):
        load(path)


# --- the statistics ledger -------------------------------------------------

def test_cut_row_counts_reconcile(tmp_path):
    prep = prepared(tmp_path, steps=[
        {"cut": {"animal_type": "CAT"}},
        {"cut": {"intake_type": "DISPO REQ"}}])
    ledger = prep.statistics.frame()
    cuts = ledger[ledger.action == "cut"]
    assert len(cuts) == 2
    assert (cuts.rows_in - cuts.rows_affected == cuts.rows_out).all()


def test_a_map_never_changes_the_row_count(tmp_path):
    prep = prepared(tmp_path, steps=[{"map": {"animal_size": {"LARGE": "LRG"}}}])
    maps = prep.statistics.frame().query("action == 'map'")
    assert (maps.rows_in == maps.rows_out).all()


def test_the_ledger_reports_animals_lost_entirely(tmp_path):
    prep = prepared(tmp_path, steps=[{"cut": {"animal_type": "CAT"}}])
    row = prep.statistics.frame().query("action == 'cut'").iloc[0]
    # A006 is the only cat, and its only row goes.
    assert row.animal_id_in - row.animal_id_out == 1


def test_the_ledger_chain_is_continuous(tmp_path):
    ledger = prepared(tmp_path, steps=[
        {"cut": {"animal_type": "CAT"}},
        {"map": {"animal_size": {"LARGE": "LRG"}}},
        {"cut": {"night_sign": "-1"}}]).statistics.frame()
    counts = ledger[ledger.action.isin(["cut", "map"])]
    assert list(counts.rows_in)[1:] == list(counts.rows_out)[:-1]


# --- the value-level breakdown ---------------------------------------------

def _values(details, **filters):
    """The {value: rows_affected} mapping of the matching detail rows."""
    for column, wanted in filters.items():
        details = details[details[column] == wanted]
    return dict(zip(details["value"], details["rows_affected"]))


def test_a_value_that_never_occurs_is_reported_as_zero(tmp_path):
    # The safeguard case: a label kept in the settings so a future extract
    # carrying it is caught. A summary of what occurred would omit it.
    details = prepared(tmp_path, steps=[
        {"cut": {"animal_type": ["CAT", "LIVESTOCK"]}}]).statistics.details()
    assert _values(details) == {"CAT": 1, "LIVESTOCK": 0}


def test_the_breakdown_of_a_column_adds_up_to_the_step(tmp_path):
    prep = prepared(tmp_path, steps=[
        {"cut": {"animal_type": ["CAT", "DOG"], "intake_type": "DISPO REQ"}}])
    row = prep.statistics.frame().query("action == 'cut'").iloc[0]
    details = prep.statistics.details()
    for column in ("animal_type", "intake_type"):
        assert sum(_values(details, column=column).values()) == row.rows_affected


def test_a_conjunction_is_broken_down_one_part_at_a_time(tmp_path):
    details = prepared(tmp_path, steps=[
        {"cut": {"animal_type": ["CAT", "DOG"], "intake_type": "DISPO REQ"}}
    ]).statistics.details()
    assert _values(details, column="animal_type") == {"CAT": 0, "DOG": 1}
    assert _values(details, column="intake_type") == {"DISPO REQ": 1}


def test_a_map_breaks_down_by_source_value(tmp_path):
    details = prepared(tmp_path, steps=[
        {"map": {"animal_size": {"LARGE": "LRG", "905-V": UNKNOWN}}}
    ]).statistics.details()
    counts = _values(details, role="map from")
    assert set(counts) == {"LARGE", "905-V"}
    assert counts["LARGE"] > 0


def test_a_where_is_counted_within_the_rows_mapped(tmp_path):
    prep = prepared(tmp_path, steps=[
        {"map": {"outcome_type": {"ADOPTION": "TRANSFER"}},
         "where": {"outcome_subtype": ["RESCUE", "NEVER USED"]}}])
    row = prep.statistics.frame().query("action == 'map'").iloc[0]
    counts = _values(prep.statistics.details(), role="where")
    assert counts == {"RESCUE": int(row.rows_affected), "NEVER USED": 0}


def test_a_where_not_is_counted_over_the_rows_it_held_back(tmp_path):
    # Counting where_not values among the *mapped* rows would report zero for
    # every one of them, since excluding them is exactly what the guard did.
    prep = prepared(tmp_path, steps=[
        {"map": {"animal_size": {"MED": "MEDIUM"}},
         "where_not": {"age_group": ["ADULT", "NEVER USED"]}}])
    row = prep.statistics.frame().query("action == 'map'").iloc[0]
    details = prep.statistics.details()
    # Six MED rows; A005 is the ADULT one, so five are mapped and one held back.
    assert int(row.rows_affected) == 5
    assert _values(details, role="map from") == {"MED": 5}
    assert _values(details, role="where_not") == {"ADULT": 1, "NEVER USED": 0}
    assert details.query("role == 'where_not'")["scope"].iloc[0].endswith("where_not")


def test_a_dedup_breaks_down_only_its_guards(tmp_path):
    prep = prepared(tmp_path, steps=[{"dedup": None, "where": {"night_sign": "1"}}],
                    **_twice(tmp_path, "2020-03-01", "2020-03-08"))
    details = prep.statistics.details()
    assert _values(details) == {"1": 1}
    assert set(details.column) == {"night_sign"}


def test_stages_without_a_value_set_get_no_detail_rows(tmp_path):
    details = prepared(tmp_path, steps=[]).statistics.details()
    assert details.empty
    assert "value" in details.columns   # shape holds even when there is nothing


def test_the_report_stacks_both_tables_in_one_readable_csv(tmp_path):
    prep = Prep(load(write_settings(tmp_path, steps=[
        {"cut": {"animal_type": ["CAT", "LIVESTOCK"]}}]))).run(verbose=False)

    written = pd.read_csv(prep.settings.stats_path)
    assert set(written.section) == {"stage", "detail"}
    # Stage rows come first, so the file reads top to bottom as before.
    assert written.section.tolist() == sorted(written.section.tolist(),
                                              key=lambda s: s != "stage")

    stages = written[written.section == "stage"]
    details = written[written.section == "detail"]
    assert stages.rows_in.notna().all() and details.rows_in.isna().all()
    # Nullable integers: a blank stays blank rather than making the column float.
    assert prep.statistics.report()["rows_in"].dtype == "Int64"
    assert dict(zip(details["value"], details["rows_affected"])) == {"CAT": 1,
                                                                     "LIVESTOCK": 0}


def test_the_run_log_carries_the_breakdown_too(tmp_path):
    prep = Prep(load(write_settings(tmp_path, steps=[
        {"cut": {"animal_type": ["CAT", "LIVESTOCK"]}}]))).run(verbose=False)
    log = prep.settings.run_path.read_text()
    assert "by value" in log and "LIVESTOCK" in log


# --- the summary of the finished set ---------------------------------------

def summarized(tmp_path, **overrides):
    prep = prepared(tmp_path, **overrides)
    return summary.summarize(prep.frame, prep.settings), prep


def test_the_summary_crosses_each_kept_category_against_both_types(tmp_path):
    table, _ = summarized(tmp_path)
    # animal_size is the only extra category: the rest of output_columns is an
    # identifier and two dates.
    assert set(table.field) == {summary.NONE, "animal_size"}


def test_intake_by_outcome_alone_is_the_degenerate_case(tmp_path):
    table, _ = summarized(tmp_path, output_columns=[
        "animal_id", "intake_date", "outcome_date", "outcome_type"])
    assert set(table.field) == {summary.NONE}
    assert set(table["value"]) == {summary.NONE}


def test_identifiers_dates_and_numbers_are_not_categories(tmp_path):
    prep = prepared(tmp_path, output_columns=[
        "animal_id", "intake_date", "outcome_date", "outcome_type",
        "animal_size", "nights", "age"])
    assert summary.fields(prep.frame, prep.settings) == ["animal_size"]


def test_the_cells_add_up_to_the_partial_sums_and_the_total(tmp_path):
    table, prep = summarized(tmp_path)
    for field in set(table.field):
        one = table[table.field == field]
        cells = one[one.margin == 0].rows.sum()
        assert one[one.margin == 1].rows.sum() == 2 * cells   # two ways to sum
        assert one[one.margin == 2].rows.sum() == cells
        assert cells == len(prep.frame)


def test_a_margin_column_keeps_the_partial_sums_from_double_counting(tmp_path):
    # The one hazard of putting the sums in the same table: margin == 0 is the
    # filter that makes summing safe, so it has to be there and be right.
    table, prep = summarized(tmp_path)
    cells = table[(table.field == summary.NONE) & (table.margin == 0)]
    assert cells.rows.sum() == len(prep.frame)
    assert not (cells.intake_type == summary.ALL).any()
    assert not (cells.outcome_type == summary.ALL).any()


def test_a_combination_that_never_occurs_is_a_zero_not_a_missing_row(tmp_path):
    table, _ = summarized(tmp_path)
    cells = table[(table.field == "animal_size") & (table.margin == 0)]
    levels = cells.groupby(["value", "intake_type", "outcome_type"]).size()
    # Full rectangle: every level of every dimension against every other.
    assert len(cells) == len(levels)
    assert (cells.rows == 0).any()


def test_a_stay_still_in_care_is_counted_but_has_no_night_count(tmp_path):
    table, prep = summarized(tmp_path)
    total = table[(table.field == summary.NONE) & (table.margin == 2)].iloc[0]
    assert total.rows == len(prep.frame) == 15
    # A002's second row and A014 have no outcome date; A013's is unparseable.
    assert total.nights_known == 12
    assert total.animal_id_distinct == 14


def test_the_summary_reads_back_with_its_sentinels_intact(tmp_path):
    prep = Prep(load(write_settings(tmp_path))).run(verbose=False)
    written = pd.read_csv(prep.settings.summary_path)
    # Blanks would have come back as NaN and made the tables unselectable.
    dimensions = ["field", "value", "intake_type", "outcome_type"]
    assert written[dimensions].notna().all(axis=None)
    assert (written[written.margin == 2].intake_type == summary.ALL).all()
    assert len(written[written.field == summary.NONE]) > 0

    # And it pivots back into the rectangle it came from.
    cells = written[(written.field == summary.NONE) & (written.margin == 0)]
    grid = cells.pivot_table(index="intake_type", columns="outcome_type",
                             values="rows", aggfunc="sum")
    assert grid.to_numpy().sum() == len(prep.frame)


def test_the_run_log_records_the_span_of_the_kept_rows(tmp_path):
    prep = Prep(load(write_settings(tmp_path))).run(verbose=False)
    line = [l for l in prep.settings.run_path.read_text().splitlines()
            if l.startswith("final span")][0]
    assert "2018-01-05" in line and "still in care" in line


# --- settings validation ---------------------------------------------------

def test_an_unknown_setting_is_an_error(tmp_path):
    path = tmp_path / "s.yaml"
    base = yaml.safe_load(write_settings(tmp_path).read_text())
    base["destination_dir"] = "typo"
    path.write_text(yaml.safe_dump(base), encoding="utf-8")
    with pytest.raises(SettingsError, match="unknown setting"):
        load(path)


def test_a_step_needs_exactly_one_of_cut_or_map(tmp_path):
    path = write_settings(tmp_path, steps=[{"cut": {"a": "b"}, "map": {"c": {"d": "e"}}}])
    with pytest.raises(SettingsError, match="exactly one"):
        load(path)


def test_a_map_takes_one_column(tmp_path):
    path = write_settings(tmp_path, steps=[
        {"map": {"animal_size": {"LARGE": "LRG"}, "outcome_type": {"RTO": "LiveC"}}}])
    with pytest.raises(SettingsError, match="exactly one column"):
        load(path)


def test_a_cut_takes_no_where(tmp_path):
    path = write_settings(tmp_path, steps=[
        {"cut": {"animal_type": "CAT"}, "where": {"intake_type": "STRAY"}}])
    with pytest.raises(SettingsError, match="no 'where:'"):
        load(path)


def test_age_groups_may_be_written_out_of_order(tmp_path):
    # The cutoffs determine the bins, so the order they are written in is not
    # information. YAML dumpers reorder mappings, so this must not matter.
    settings = load(write_settings(tmp_path, age_groups={"SENIOR": 18, "JUVENILE": 1,
                                                         "ADULT": 9, "YOUNG": 4}))
    assert list(settings.age_groups) == ["JUVENILE", "YOUNG", "ADULT", "SENIOR"]


def test_age_group_cutoffs_must_be_distinct(tmp_path):
    path = write_settings(tmp_path, age_groups={"A": 4, "B": 4})
    with pytest.raises(SettingsError, match="distinct"):
        load(path)


def test_relative_paths_resolve_against_the_settings_file(tmp_path):
    # Not against the working directory: a run must mean the same thing from
    # anywhere, including from cron or from another project's directory.
    nested = tmp_path / "configs"
    nested.mkdir()
    path = nested / "s.yaml"
    base = yaml.safe_load(write_settings(tmp_path).read_text())
    base["source_dir"] = "../fixtures"
    base["dest_dir"] = "../out"
    path.write_text(yaml.safe_dump(base, sort_keys=False), encoding="utf-8")

    settings = load(path)
    assert settings.source_dir == tmp_path / "fixtures"
    assert settings.dest_dir == tmp_path / "out"


def test_an_unknown_date_format_is_an_error(tmp_path):
    path = write_settings(tmp_path, date_format="dd/mm/yyyy")
    with pytest.raises(SettingsError, match="date_format"):
        load(path)


# --- source validation -----------------------------------------------------

def test_a_missing_required_column_names_what_the_file_has(tmp_path):
    path = write_settings(tmp_path, columns={"animal_id": "No Such Column"})
    with pytest.raises(SourceError) as caught:
        Prep(load(path)).read()
    message = str(caught.value)
    assert "No Such Column" in message and "animal_id" in message
    assert "the file has:" in message


def test_a_missing_step_column_is_an_error(tmp_path):
    path = write_settings(tmp_path, steps=[{"cut": {"nonexistent": "x"}}])
    with pytest.raises(SourceError, match="nonexistent"):
        Prep(load(path)).read()


def test_an_optional_column_may_simply_be_absent(tmp_path):
    # No dob in the file, and no step or output column needs age.
    source = tmp_path / "nodob.csv"
    frame = pd.read_csv(FIXTURES / "tiny.csv", dtype=str).drop(columns=["DOB"])
    frame.to_csv(source, index=False)
    path = write_settings(
        tmp_path, source_dir=str(tmp_path), source_file="nodob.csv",
        columns={"animal_id": "Animal ID", "intake_date": "Intake Date",
                 "outcome_date": "Outcome Date"})
    prep = Prep(load(path)).read().derive()
    assert "age_group" not in prep.frame.columns
    assert "nights" in prep.frame.columns


def test_a_multi_sheet_workbook_requires_a_sheet_name(tmp_path):
    book = tmp_path / "two.xlsx"
    frame = pd.read_csv(FIXTURES / "tiny.csv", dtype=str)
    with pd.ExcelWriter(book) as writer:
        frame.to_excel(writer, sheet_name="first", index=False)
        frame.to_excel(writer, sheet_name="second", index=False)

    path = write_settings(tmp_path, source_dir=str(tmp_path), source_file="two.xlsx")
    with pytest.raises(SourceError, match="2 sheets"):
        Prep(load(path)).read()

    named = write_settings(tmp_path, source_dir=str(tmp_path),
                           source_file="two.xlsx", sheet="second")
    assert len(Prep(load(named)).read().frame) == 15


def test_a_single_sheet_workbook_needs_no_sheet_name(tmp_path):
    book = tmp_path / "one.xlsx"
    pd.read_csv(FIXTURES / "tiny.csv", dtype=str).to_excel(
        book, sheet_name="only", index=False)
    path = write_settings(tmp_path, source_dir=str(tmp_path), source_file="one.xlsx")
    assert len(Prep(load(path)).read().frame) == 15


def test_a_gzipped_source_reads_and_hashes_as_its_uncompressed_self(tmp_path):
    import gzip as gziplib
    plain = (FIXTURES / "tiny.csv").read_bytes()
    (tmp_path / "z.csv.gz").write_bytes(gziplib.compress(plain))

    path = write_settings(tmp_path, source_dir=str(tmp_path), source_file="z.csv.gz")
    prep = Prep(load(path)).run(verbose=False)
    assert len(prep.frame) == 15
    # The digest identifies the data, not the archive, so it matches the
    # original file the archive was made from.
    assert hashlib.sha256(plain).hexdigest() in prep.settings.run_path.read_text()


def test_a_utf8_bom_does_not_corrupt_the_first_column_name(tmp_path):
    source = tmp_path / "bom.csv"
    source.write_bytes(b"\xef\xbb\xbf" + (FIXTURES / "tiny.csv").read_bytes())
    path = write_settings(tmp_path, source_dir=str(tmp_path), source_file="bom.csv")
    assert "animal_id" in Prep(load(path)).read().frame.columns


# --- end to end ------------------------------------------------------------

def test_a_full_run_writes_data_statistics_and_a_log(tmp_path):
    prep = Prep(load(write_settings(tmp_path, steps=[
        {"cut": {"animal_type": "CAT"}},
        {"cut": {"window_presence": ["BEFORE", "AFTER"]}},
        {"cut": {"night_sign": "-1"}},
        {"cut": {"age_group": OVER}},
        {"map": {"animal_size": {"LARGE": "LRG", "905-V": UNKNOWN}}},
    ]))).run(verbose=False)

    settings = prep.settings
    assert settings.dest_path.exists()
    assert settings.stats_path.exists()
    assert settings.run_path.exists()

    written = pd.read_csv(settings.dest_path, dtype=str)
    assert list(written.columns) == list(settings.output_columns)
    # A006 cat, A012 before the window, A005 negative nights, A008 over-age.
    gone = {"A006", "A012", "A005", "A008"}
    assert not (gone & set(written.animal_id))
    assert "LARGE" not in set(written.animal_size)

    log = settings.run_path.read_text()
    assert "source sha256" in log and "pandas" in log
