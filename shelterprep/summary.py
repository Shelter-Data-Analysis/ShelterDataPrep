"""Descriptive statistics of the finished set.

The ledger says what the pipeline removed.  This says what is left: how the
surviving stays are distributed across intake type, outcome type, and whatever
other categorical column the run exports, plus how long those stays were.

One long table rather than a stack of rectangular ones.  A contingency table
written as a rectangle needs a header row *and* a header column, which no
single CSV can carry for several tables at once and which neither pandas nor R
reads back without instructions.  One row per cell, with the dimensions in
named columns, reads directly into all three of a spreadsheet, `read_csv` and
`read.csv`, and pivots back into a rectangle in one call:

    frame.pivot_table(index="intake_type", columns="outcome_type", values="rows")
    xtabs(rows ~ intake_type + outcome_type, data=frame)

Partial sums are in the same table, marked by ``_ALL_`` in the dimension they
collapse and counted by the ``margin`` column: ``margin == 0`` selects the
cells alone, which is the filter a reader needs before summing anything.
"""

from __future__ import annotations

import pandas as pd

from .settings import DATE_COLUMNS

#: A dimension collapsed by a partial sum.  An ordinary value in the house
#: style of UNKNOWN, so that sorting, filtering and pivoting need no special
#: case for it.
ALL = "_ALL_"

#: The `field` of the intake x outcome table, which crosses no third column.
#: Spelled out rather than left blank because `read_csv` and `read.csv` both
#: turn a blank cell into a missing value, and `field == ""` then selects
#: nothing -- the one table most likely to be asked for by name.
NONE = "_NONE_"

#: The two axes every table is crossed against.  Both are required columns, so
#: they are always there to cross against.
AXES = ("intake_type", "outcome_type")

#: A column with more distinct values than this is an identifier or free text,
#: not a category, and crossing it against the axes would produce a table
#: longer than the data.  It is skipped, and `skipped` says so.
MAX_LEVELS = 50

#: The shortest and longest stay in a cell.  Whole nights, so they stay
#: integers; a journal table wants them rather than a rounded float.
EXTREMES = ("nights_min", "nights_max")

#: The rest of the distribution.  p90 because mLOS leans on it; the quartiles
#: because a length of stay is skewed enough that the extremes alone mislead.
QUANTILES = ("nights_mean", "nights_p25", "nights_median", "nights_p75",
             "nights_p90")


def fields(frame, settings):
    """The exported categorical columns, beyond the two axes themselves.

    Dates are not categories, numbers are not categories, and an identifier is
    not a category however it is typed -- so `unique_report` is excluded too:
    animal_id crossed against outcome type is one row per animal.
    """
    kept = []
    for column in settings.output_columns:
        if column in AXES or column in DATE_COLUMNS:
            continue
        if column in settings.unique_report:
            continue
        if pd.api.types.is_numeric_dtype(frame[column]):
            continue
        kept.append(column)
    return kept


def skipped(frame, settings):
    """Categorical columns left out for having too many levels."""
    return [column for column in fields(frame, settings)
            if frame[column].nunique(dropna=False) > MAX_LEVELS]


def summarize(frame, settings):
    """The long-form summary of *frame*, one row per cell and partial sum."""
    unique_report = list(settings.unique_report)
    over_wide = set(skipped(frame, settings))

    tables = [_table(frame, None, unique_report)]
    for field in fields(frame, settings):
        if field not in over_wide:
            tables.append(_table(frame, field, unique_report))

    summary = pd.concat(tables, ignore_index=True)
    counts = ["rows", "nights_known"] + [name + "_distinct" for name in unique_report]
    summary[counts] = summary[counts].astype("Int64")
    order = (["field", "value", "intake_type", "outcome_type", "margin", "rows"]
             + [name + "_distinct" for name in unique_report]
             + ["nights_known", "nights_mean", "nights_min", "nights_p25",
                "nights_median", "nights_p75", "nights_p90", "nights_max"])
    return summary[order]


# --- one table -------------------------------------------------------------

def _table(frame, field, unique_report):
    """The cells and partial sums of one table, as long rows.

    *field* None gives the intake x outcome table -- the degenerate case, with
    nothing to cross the axes against but each other.  Otherwise the field is a
    third dimension, and it is deliberately never collapsed: the sums over it
    are exactly the intake x outcome table, which is already its own table
    here, and repeating them once per field would be the only place in the file
    where the same number appears twice.
    """
    work = _working_frame(frame, field, unique_report)
    levels = {column: sorted(work[column].unique())
              for column in work.columns if column in ("value",) + AXES}
    keys = ["value"] if field else []

    pieces = []
    for collapse in ((), ("outcome_type",), ("intake_type",), AXES):
        piece = _aggregate(work, keys + [a for a in AXES if a not in collapse],
                           levels, unique_report)
        for axis in collapse:
            piece[axis] = ALL
        piece["margin"] = len(collapse)
        pieces.append(piece)

    table = pd.concat(pieces, ignore_index=True)
    table["field"] = field or NONE
    if not field:
        table["value"] = NONE
    return table


def _working_frame(frame, field, unique_report):
    """Just the columns the tabulation reads, with the field renamed `value`.

    Built rather than sliced so that a field literally named `value`, or one
    sharing a name with a measure column, cannot collide with anything.
    """
    work = pd.DataFrame(index=frame.index)
    if field:
        work["value"] = frame[field].astype(str)
    for axis in AXES:
        work[axis] = frame[axis].astype(str)
    # Int64 to float: the aggregates want NaN, and a stay still in care has no
    # night count rather than a count of zero.
    work["nights"] = frame["nights"].astype(float)
    for name in unique_report:
        work[name] = frame[name]
    return work


def _aggregate(work, keys, levels, unique_report):
    """Group by *keys* and measure, with every combination present.

    Reindexing onto the full product is what makes a combination that never
    occurs show up as a zero rather than as a missing row: the same reason the
    by-value breakdown in the ledger reports its zeros, and what keeps every
    pivot of this table rectangular.
    """
    specification = {
        "rows": ("nights", "size"),
        "nights_known": ("nights", "count"),
        "nights_mean": ("nights", "mean"),
        "nights_min": ("nights", "min"),
        "nights_p25": ("nights", _quantile(0.25)),
        "nights_median": ("nights", "median"),
        "nights_p75": ("nights", _quantile(0.75)),
        "nights_p90": ("nights", _quantile(0.90)),
        "nights_max": ("nights", "max"),
    }
    for name in unique_report:
        specification[name + "_distinct"] = (name, "nunique")

    if keys:
        grouped = work.groupby(keys, dropna=False).agg(**specification)
        grouped = grouped.reindex(pd.MultiIndex.from_product(
            [levels[key] for key in keys], names=keys)
            if len(keys) > 1 else pd.Index(levels[keys[0]], name=keys[0]))
    else:
        # The grand total: one group holding everything.
        grouped = work.assign(**{ALL: 1}).groupby(ALL).agg(**specification)

    for column in ["rows", "nights_known"] + [n + "_distinct" for n in unique_report]:
        grouped[column] = grouped[column].fillna(0)
    for column in QUANTILES:
        grouped[column] = grouped[column].round(2)
    # Not filled: a cell where nothing has finished has no shortest or longest
    # stay, and a blank says that where a zero would claim a same-day stay.
    for column in EXTREMES:
        grouped[column] = grouped[column].astype("Int64")
    return grouped.reset_index(drop=not keys)


def _quantile(fraction):
    """A named aggregation for one quantile of the night counts."""
    return lambda values: values.quantile(fraction)
