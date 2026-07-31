"""Settings: the YAML file, parsed and validated into frozen dataclasses.

Everything the pipeline does is decided here, before a single row is read.  A
settings file that is going to fail should fail on the settings, not eighty
seconds into a 70 MB extract, and certainly not silently.

Unknown keys are therefore an error rather than a warning.  A misspelled
setting that quietly skips an exclusion is exactly the failure mode that
survives all the way into a published table.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, FrozenSet, List, Optional, Tuple

import yaml

from . import dates

# --- vocabulary ------------------------------------------------------------

#: Canonical fields that must resolve to a column in the source file.
REQUIRED_COLUMNS = ("animal_id", "intake_date", "outcome_date",
                    "intake_type", "outcome_type")

#: Canonical fields used when present, ignored when absent.
OPTIONAL_COLUMNS = ("dob",)

#: Canonical fields parsed as dates rather than as text.
DATE_COLUMNS = ("intake_date", "outcome_date", "dob")

#: Columns the pipeline computes.  They may be filtered and mapped like any
#: other column, but they are never read from the file.
DERIVED_COLUMNS = ("nights", "night_sign", "window_presence", "age", "age_group")

#: Blank, missing, or whitespace-only text.  Matches the convention mLOS uses,
#: so a value stays greppable end to end.  Because it is an ordinary value, a
#: filter or a map can name it without any special-casing for NaN.
UNKNOWN = "_UNKNOWN_"

#: age_group for an animal older than the last cutoff.
OVER = "_OVER_"

#: age_group where the date of birth falls after the intake date.  A data
#: error, kept distinct from "no date of birth" because they warrant different
#: sentences in a methods section.
NEGATIVE = "_NEGATIVE_"

_TOP_LEVEL_KEYS = frozenset({
    "source_dir", "source_file", "sheet", "date_format", "keep_time",
    "window_start_date", "window_end_date",
    "dest_dir", "dest_file", "output_columns",
    "columns", "age_groups", "unique_report", "steps",
})

_STEP_KEYS = frozenset({"cut", "map", "dedup", "where", "where_not"})

_ACTIONS = ("cut", "map", "dedup")


class SettingsError(ValueError):
    """A settings file that cannot be honoured as written."""


# --- helpers ---------------------------------------------------------------

def as_value_set(value):
    """A scalar is accepted anywhere a set is meant; ``DEAD`` == ``[DEAD]``.

    Everything is compared as text, so ``night_sign: -1`` in YAML (which
    arrives as the integer -1) matches the string ``"-1"`` in the frame.
    """
    if value is None:
        return frozenset()
    if isinstance(value, (list, tuple, set, frozenset)):
        return frozenset(str(item) for item in value)
    return frozenset([str(value)])


def _conditions(raw, where):
    """Parse a ``{column: values}`` mapping into ``{column: frozenset}``."""
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise SettingsError(
            "{0} must be a mapping of column to value(s), got {1!r}".format(where, raw))
    return {str(column): as_value_set(values) for column, values in raw.items()}


def _describe(conditions):
    return " and ".join(
        "{0} in ({1})".format(column, ", ".join(sorted(values)))
        for column, values in conditions.items())


# --- steps -----------------------------------------------------------------

@dataclass(frozen=True)
class Cut:
    """Drop every row matching all of ``conditions``.

    A cut is always a cut, never a pass, and multiple columns are always ANDed
    together.  Both restrictions are deliberate: they make the statistics row
    for a cut unambiguous without anyone having to reason about precedence.
    """

    index: int
    conditions: Dict[str, FrozenSet[str]]

    action = "cut"

    @property
    def columns(self):
        return tuple(self.conditions)

    @property
    def column(self):
        return ", ".join(self.conditions)

    @property
    def detail(self):
        return "drop where " + _describe(self.conditions)


@dataclass(frozen=True)
class Map:
    """Rewrite values in exactly one column, optionally gated by other columns.

    One column per step, because a step produces one statistics row and a row
    describing two columns at once cannot be read unambiguously.  Two rewrites
    are two steps.
    """

    index: int
    column: str
    table: Dict[str, str]
    where: Dict[str, FrozenSet[str]] = field(default_factory=dict)
    where_not: Dict[str, FrozenSet[str]] = field(default_factory=dict)

    action = "map"

    @property
    def columns(self):
        return (self.column,) + tuple(self.where) + tuple(self.where_not)

    @property
    def detail(self):
        pairs = ", ".join("{0} -> {1}".format(source, target)
                          for source, target in sorted(self.table.items()))
        if self.where:
            pairs += " where " + _describe(self.where)
        if self.where_not:
            pairs += " where not " + _describe(self.where_not)
        return pairs


@dataclass(frozen=True)
class Dedup:
    """Keep the last of each group of rows matching across ``on``, cut the rest.

    The last rather than the first: where ``on`` is a subset of the columns,
    two matching rows can still differ elsewhere, and a later record is much
    more likely to be a correction of an earlier one than the reverse.  It is
    also how mLOS breaks the same tie.


    Deliberately the narrowest useful form of deduplication.  Two rows
    identical in every output column and covering a stay of at least one night
    cannot both be real: an animal cannot be admitted twice on the same day for
    the same multi-day stay.  A *same-day* repeat, by contrast, is physically
    possible -- in and out in the morning, in and out again in the afternoon --
    so restricting this step with ``where: {night_sign: "1"}`` keeps it to the
    unambiguous cases and leaves the rest to the downstream analysis, which has
    its own duplicate-stay and overlapping-stay screens.

    ``on`` empty means "every output column", resolved when the step runs.
    """

    index: int
    on: Tuple[str, ...] = ()
    where: Dict[str, FrozenSet[str]] = field(default_factory=dict)
    where_not: Dict[str, FrozenSet[str]] = field(default_factory=dict)

    action = "dedup"

    @property
    def columns(self):
        return tuple(self.on) + tuple(self.where) + tuple(self.where_not)

    @property
    def column(self):
        return ", ".join(self.on) if self.on else "(output columns)"

    @property
    def detail(self):
        text = "drop repeats of " + (
            ", ".join(self.on) if self.on else "every output column")
        if self.where:
            text += " where " + _describe(self.where)
        if self.where_not:
            text += " where not " + _describe(self.where_not)
        return text


def _parse_step(index, raw):
    if not isinstance(raw, dict):
        raise SettingsError("step {0} must be a mapping, got {1!r}".format(index, raw))

    unknown = sorted(set(raw) - _STEP_KEYS)
    if unknown:
        raise SettingsError(
            "step {0} has unknown key(s) {1}; allowed: {2}".format(
                index, ", ".join(unknown), ", ".join(sorted(_STEP_KEYS))))

    present = [name for name in _ACTIONS if name in raw]
    if len(present) != 1:
        raise SettingsError(
            "step {0} needs exactly one of {1}".format(
                index, ", ".join("'{0}:'".format(name) for name in _ACTIONS)))
    action = present[0]

    if action == "cut":
        if "where" in raw or "where_not" in raw:
            raise SettingsError(
                "step {0}: a cut already ANDs its columns together, so it takes "
                "no 'where:'. Add the extra column to the cut itself.".format(index))
        conditions = _conditions(raw["cut"], "step {0} cut".format(index))
        if not conditions:
            raise SettingsError("step {0}: cut is empty".format(index))
        return Cut(index=index, conditions=conditions)

    if action == "dedup":
        on = raw["dedup"]
        if on is not None and not isinstance(on, (list, tuple)):
            raise SettingsError(
                "step {0}: dedup takes a list of columns, or nothing at all "
                "for every output column".format(index))
        return Dedup(
            index=index,
            on=tuple(str(column) for column in (on or ())),
            where=_conditions(raw.get("where"), "step {0} where".format(index)),
            where_not=_conditions(raw.get("where_not"),
                                  "step {0} where_not".format(index)),
        )

    table_by_column = raw["map"]
    if not isinstance(table_by_column, dict) or len(table_by_column) != 1:
        raise SettingsError(
            "step {0}: map takes exactly one column, as "
            "'map: {{column: {{from: to}}}}'. Split multiple columns into "
            "separate steps.".format(index))

    column, table = next(iter(table_by_column.items()))
    if not isinstance(table, dict) or not table:
        raise SettingsError(
            "step {0}: map for {1!r} must be a non-empty "
            "{{from: to}} mapping".format(index, column))

    return Map(
        index=index,
        column=str(column),
        table={str(source): str(target) for source, target in table.items()},
        where=_conditions(raw.get("where"), "step {0} where".format(index)),
        where_not=_conditions(raw.get("where_not"), "step {0} where_not".format(index)),
    )


# --- settings --------------------------------------------------------------

@dataclass(frozen=True)
class Settings:
    """One run: where the data comes from, what happens to it, where it goes."""

    source_dir: Path
    source_file: str
    dest_dir: Path
    dest_file: str
    output_columns: Tuple[str, ...]
    columns: Dict[str, str]
    age_groups: Dict[str, float]
    unique_report: Tuple[str, ...]
    steps: Tuple[object, ...]
    sheet: Optional[str] = None
    date_format: str = dates.ISO8601
    keep_time: bool = False
    window_start_date: Optional[object] = None
    window_end_date: Optional[object] = None
    path: Optional[Path] = None

    # -- derived views ------------------------------------------------------

    @property
    def source_path(self):
        return self.source_dir / self.source_file

    @property
    def dest_path(self):
        return self.dest_dir / self.dest_file

    @property
    def stats_path(self):
        return self.dest_dir / (Path(self.dest_file).stem + "_stats.csv")

    @property
    def run_path(self):
        return self.dest_dir / (Path(self.dest_file).stem + "_run.txt")

    @property
    def has_window(self):
        return self.window_start_date is not None

    def file_name_for(self, canonical):
        """The column name in the source file for a canonical field."""
        return self.columns.get(canonical, canonical)

    def step_columns(self):
        """Every column named anywhere in the step sequence."""
        names = set()
        for step in self.steps:
            names.update(step.columns)
        return names

    def wanted_columns(self, available):
        """Canonical names to pull from the file, given its actual header.

        Reading only what is needed keeps a 70 MB extract cheap, and lets a
        missing *required* column fail loudly while a missing *optional* one
        passes quietly.
        """
        wanted = set(self.output_columns)
        wanted |= self.step_columns()
        wanted |= set(REQUIRED_COLUMNS)
        wanted |= set(self.unique_report)
        wanted -= set(DERIVED_COLUMNS)

        for canonical in OPTIONAL_COLUMNS:
            if self.file_name_for(canonical) in available:
                wanted.add(canonical)
            else:
                wanted.discard(canonical)
        return wanted


def load(path):
    """Read and validate a settings file."""
    path = Path(path).expanduser()
    with open(path, "r", encoding="utf-8") as handle:
        raw = yaml.safe_load(handle) or {}

    if not isinstance(raw, dict):
        raise SettingsError("{0}: top level must be a mapping".format(path))

    unknown = sorted(set(raw) - _TOP_LEVEL_KEYS)
    if unknown:
        raise SettingsError(
            "{0}: unknown setting(s) {1}. Known settings: {2}".format(
                path, ", ".join(unknown), ", ".join(sorted(_TOP_LEVEL_KEYS))))

    for required in ("source_dir", "source_file", "dest_dir", "dest_file",
                     "output_columns"):
        if raw.get(required) is None:
            raise SettingsError("{0}: {1} is required".format(path, required))

    date_format = str(raw.get("date_format") or dates.ISO8601)
    if date_format not in dates.DATE_FORMATS:
        raise SettingsError(
            "{0}: date_format must be one of {1}, got {2!r}".format(
                path, ", ".join(dates.DATE_FORMATS), date_format))

    start, end = raw.get("window_start_date"), raw.get("window_end_date")
    if (start is None) != (end is None):
        raise SettingsError(
            "{0}: window_start_date and window_end_date must be given "
            "together or not at all".format(path))
    if start is not None:
        start, end = dates.to_timestamp(start), dates.to_timestamp(end)
        if start > end:
            raise SettingsError(
                "{0}: window_start_date {1} is after window_end_date {2}".format(
                    path, start.date(), end.date()))

    age_groups = _parse_age_groups(raw.get("age_groups"), path)
    steps = tuple(_parse_step(number, step)
                  for number, step in enumerate(raw.get("steps") or [], start=1))

    unique_report = tuple(raw.get("unique_report") or ("animal_id",))
    output_columns = tuple(raw["output_columns"])
    if len(set(output_columns)) != len(output_columns):
        raise SettingsError("{0}: output_columns has duplicates".format(path))

    settings = Settings(
        source_dir=_resolve_dir(raw["source_dir"], path),
        source_file=str(raw["source_file"]),
        dest_dir=_resolve_dir(raw["dest_dir"], path),
        dest_file=str(raw["dest_file"]),
        output_columns=output_columns,
        columns={str(k): str(v) for k, v in (raw.get("columns") or {}).items()},
        age_groups=age_groups,
        unique_report=unique_report,
        steps=steps,
        sheet=None if raw.get("sheet") is None else str(raw["sheet"]),
        date_format=date_format,
        keep_time=bool(raw.get("keep_time", False)),
        window_start_date=start,
        window_end_date=end,
        path=path,
    )

    _check_window_usage(settings, path)
    _check_age_usage(settings, path)
    return settings


def _resolve_dir(value, settings_path):
    """Resolve a directory from the settings file.

    A relative path is taken relative to the settings file itself, not to the
    working directory, so a run means the same thing from anywhere.
    """
    directory = Path(str(value)).expanduser()
    if not directory.is_absolute():
        directory = settings_path.resolve().parent / directory
    return Path(os.path.normpath(str(directory)))


def _parse_age_groups(raw, path):
    if not raw:
        return {}
    if not isinstance(raw, dict):
        raise SettingsError("{0}: age_groups must be a mapping of "
                            "name to cutoff".format(path))
    groups = {str(name): float(cutoff) for name, cutoff in raw.items()}
    cutoffs = list(groups.values())
    if len(set(cutoffs)) != len(cutoffs):
        raise SettingsError(
            "{0}: age_groups cutoffs must be distinct, got {1}".format(
                path, cutoffs))
    # Ordered by cutoff rather than by how they happen to be written: the
    # cutoffs alone determine the bins, so an out-of-order settings file is
    # unambiguous and there is nothing to be gained by rejecting it.
    return dict(sorted(groups.items(), key=lambda item: item[1]))


def _check_window_usage(settings, path):
    if settings.has_window or "window_presence" not in settings.step_columns():
        return
    raise SettingsError(
        "{0}: a step filters on window_presence, but window_start_date and "
        "window_end_date are not set, so the column is never built".format(path))


def _check_age_usage(settings, path):
    names = settings.step_columns() | set(settings.output_columns)
    used = names & {"age", "age_group"}
    if not used or settings.age_groups:
        return
    raise SettingsError(
        "{0}: {1} is used but age_groups is not set".format(
            path, ", ".join(sorted(used))))
