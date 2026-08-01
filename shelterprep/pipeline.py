"""The pipeline: read, derive, apply the step sequence, write.

`Prep` carries the three things a run consists of -- the settings, the frame
being processed, and the statistics of the processing -- and exposes the four
stages as methods so any of them can be inspected in isolation from a REPL.
`Prep.run` calls them in order.
"""

from __future__ import annotations

import gzip
import hashlib
from dataclasses import replace
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

from . import dates, steps
from .settings import (DATE_COLUMNS, DERIVED_COLUMNS, NEGATIVE, OVER,
                       REQUIRED_COLUMNS, UNKNOWN, Dedup, SettingsError)
from .statistics import Statistics

EXCEL_SUFFIXES = (".xlsx", ".xlsm", ".xltx", ".xls")


class SourceError(ValueError):
    """The source file does not match what the settings expect of it."""


class Prep:
    """One run of the pipeline."""

    def __init__(self, settings):
        self.settings = settings
        self.frame = None
        self.statistics = Statistics(settings.unique_report)
        self.sheet = None

    def run(self, verbose=True):
        self.read()
        self.derive()
        self.apply_steps()
        self.write()
        if verbose:
            print(self.statistics.render())
            print("\nwrote {0}".format(self.settings.dest_path))
            print("      {0}".format(self.settings.stats_path))
            print("      {0}".format(self.settings.run_path))
        return self

    # -- stage 1: read ------------------------------------------------------

    def read(self):
        """Load only the columns this run needs, under canonical names."""
        settings = self.settings
        path = settings.source_path
        if not path.exists():
            raise SourceError("source file not found: {0}".format(path))

        header, self.sheet = self._probe(path)
        wanted = settings.wanted_columns(available=set(header))
        by_file_name = self._resolve(wanted, header)

        frame = self._read_columns(path, list(by_file_name))
        frame = frame.rename(columns=by_file_name)
        frame.index = pd.RangeIndex(len(frame))

        date_columns = [name for name in DATE_COLUMNS if name in frame.columns]
        for column in frame.columns:
            if column not in date_columns:
                frame[column] = _clean_text(frame[column])

        self.frame = frame
        self.statistics.record(
            step=0, action="read", before=frame, after=frame,
            column=str(path.name),
            detail="{0} column(s){1}".format(
                len(frame.columns),
                "" if self.sheet is None else ", sheet " + self.sheet))

        self._parse_dates(date_columns)
        return self

    def _probe(self, path):
        """Read the header only, and settle which sheet we are reading."""
        settings = self.settings
        if path.suffix.lower() not in EXCEL_SUFFIXES:
            header = pd.read_csv(path, nrows=0, encoding="utf-8-sig").columns
            if settings.sheet is not None:
                raise SourceError(
                    "sheet {0!r} was given but {1} is not an Excel "
                    "file".format(settings.sheet, path.name))
            return list(header), None

        book = pd.ExcelFile(path)
        sheet = settings.sheet
        if sheet is None:
            if len(book.sheet_names) != 1:
                raise SourceError(
                    "{0} has {1} sheets ({2}), so 'sheet:' is required".format(
                        path.name, len(book.sheet_names),
                        ", ".join(book.sheet_names)))
            sheet = book.sheet_names[0]
        elif sheet not in book.sheet_names:
            raise SourceError(
                "{0} has no sheet {1!r}; it has: {2}".format(
                    path.name, sheet, ", ".join(book.sheet_names)))
        header = pd.read_excel(book, sheet_name=sheet, nrows=0).columns
        return list(header), sheet

    def _resolve(self, wanted, header):
        """Map file column names to canonical names, failing loudly on gaps.

        pandas would raise on a missing `usecols` entry anyway, but its message
        names neither the canonical field nor what the file does contain.
        """
        available = set(header)
        by_file_name = {}
        missing = []
        for canonical in sorted(wanted):
            file_name = self.settings.file_name_for(canonical)
            if file_name not in available:
                missing.append((canonical, file_name))
                continue
            if file_name in by_file_name:
                raise SettingsError(
                    "both {0!r} and {1!r} map to the file column {2!r}".format(
                        by_file_name[file_name], canonical, file_name))
            by_file_name[file_name] = canonical

        if missing:
            lines = ["{0} does not have the column(s) this run needs:".format(
                self.settings.source_path.name)]
            for canonical, file_name in missing:
                if canonical == file_name:
                    lines.append("  {0}".format(file_name))
                else:
                    lines.append("  {0}  (for {1})".format(file_name, canonical))
            lines.append("the file has: " + ", ".join(header))
            raise SourceError("\n".join(lines))
        return by_file_name

    def _read_columns(self, path, file_names):
        settings = self.settings
        if path.suffix.lower() in EXCEL_SUFFIXES:
            return pd.read_excel(path, sheet_name=self.sheet,
                                 usecols=file_names, dtype=str)
        # utf-8-sig, not utf-8: the Orange County and Long Beach exports carry
        # a byte-order mark, which otherwise becomes part of the first column
        # name and makes every lookup on it fail.
        return pd.read_csv(path, usecols=file_names, dtype=str,
                           encoding="utf-8-sig")

    def _parse_dates(self, date_columns):
        settings = self.settings
        for column in date_columns:
            raw = self.frame[column]
            supplied = raw.notna() & (raw.astype(str).str.strip() != "")
            parsed = dates.to_datetime(raw, settings.date_format, settings.keep_time)
            unparsed = supplied & parsed.isna()
            self.frame[column] = parsed
            self.statistics.record(
                step=0, action="parse_dates", before=self.frame, after=self.frame,
                affected=unparsed, column=column,
                detail="{0} of {1} supplied value(s) unparseable as {2}".format(
                    int(unparsed.sum()), int(supplied.sum()), settings.date_format))

    # -- stage 2: derive ----------------------------------------------------

    def derive(self):
        """Add nights, night_sign, window_presence, age and age_group.

        Computed once, before any step runs, so a step can filter or map them
        exactly as it would a column that came out of the file.
        """
        settings = self.settings
        frame = self.frame
        before = frame.copy()
        built = []

        frame["nights"] = dates.nights_between(frame["intake_date"],
                                               frame["outcome_date"])
        frame["night_sign"] = _sign_of(frame["nights"])
        built.extend(["nights", "night_sign"])

        if settings.has_window:
            frame["window_presence"] = _window_presence(
                frame, settings.window_start_date, settings.window_end_date)
            built.append("window_presence")

        if "dob" in frame.columns and settings.age_groups:
            frame["age"] = (frame["intake_date"] - frame["dob"]).dt.days / 365.25
            frame["age_group"] = _age_group(frame["age"], settings.age_groups)
            built.extend(["age", "age_group"])

        self.statistics.record(
            step=0, action="derive", before=before, after=frame,
            column=", ".join(built), detail="computed " + ", ".join(built))
        self._check_columns_exist()
        return self

    def _check_columns_exist(self):
        """Every column a step or the output names must exist by now.

        Checked here rather than at write time so a typo costs nothing: the
        run stops before the step sequence, not after it.
        """
        available = set(self.frame.columns)
        missing = [c for c in self.settings.output_columns if c not in available]
        if missing:
            raise SettingsError(
                "output_columns names {0}, which the frame does not have. "
                "It has: {1}".format(", ".join(missing), ", ".join(sorted(available))))

        for step in self.settings.steps:
            for column in step.columns:
                if column in available:
                    continue
                hint = ""
                if column in DERIVED_COLUMNS:
                    hint = (" (a derived column: it needs dob in the source file "
                            "and age_groups in the settings)")
                raise SettingsError(
                    "step {0} names the column {1!r}, which does not "
                    "exist{2}".format(step.index, column, hint))

    # -- stage 3: the step sequence ----------------------------------------

    def apply_steps(self):
        """Run the filter and mapping steps in order.

        Each step measures first and changes second, so its statistics row
        describes the frame the step actually saw.
        """
        for step in self.settings.steps:
            step = self._with_defaults(step)
            before = self.frame
            chosen = steps.selection(before, step)
            after = steps.apply(before, step, chosen)
            self.statistics.record(
                step=step.index, action=step.action, before=before, after=after,
                affected=chosen, column=step.column, detail=step.detail,
                breakdown=steps.breakdown(before, step, chosen))
            self.frame = after
        return self

    def _with_defaults(self, step):
        """Fill in a dedup step's default column list: every output column."""
        if isinstance(step, Dedup) and not step.on:
            return replace(step, on=tuple(self.settings.output_columns))
        return step

    # -- stage 4: write -----------------------------------------------------

    def write(self):
        """Write the output CSV, the statistics table and the run log."""
        settings = self.settings
        missing = [c for c in settings.output_columns
                   if c not in self.frame.columns]
        if missing:
            raise SettingsError(
                "output_columns names {0}, which the frame does not have. "
                "It has: {1}".format(", ".join(missing),
                                     ", ".join(self.frame.columns)))

        output = self.frame[list(settings.output_columns)].copy()
        for column in output.columns:
            if column in DATE_COLUMNS:
                output[column] = dates.to_iso(output[column])

        self.statistics.record(
            step=len(settings.steps) + 1, action="write",
            before=self.frame, after=self.frame,
            column=", ".join(settings.output_columns),
            detail=str(settings.dest_path))

        settings.dest_dir.mkdir(parents=True, exist_ok=True)
        output.to_csv(settings.dest_path, index=False)
        self.statistics.report().to_csv(settings.stats_path, index=False)
        settings.run_path.write_text(self._run_log(), encoding="utf-8")
        return self

    def _run_log(self):
        settings = self.settings
        lines = [
            "ShelterDataPrep run log",
            "",
            "run at        {0}".format(datetime.now().isoformat(timespec="seconds")),
            "settings      {0}".format(settings.path),
            "source        {0}".format(settings.source_path),
            "source sha256 {0}  (of the uncompressed contents)".format(
                _sha256(settings.source_path)),
            "sheet         {0}".format(self.sheet or "(csv)"),
            "date_format   {0}".format(settings.date_format),
            "keep_time     {0}".format(settings.keep_time),
            "window        {0}".format(
                "{0} to {1}".format(settings.window_start_date.date(),
                                    settings.window_end_date.date())
                if settings.has_window else "(none)"),
            "destination   {0}".format(settings.dest_path),
            "pandas        {0}".format(pd.__version__),
            "numpy         {0}".format(np.__version__),
            "",
            self.statistics.render(),
            "",
        ]
        return "\n".join(lines)


# --- column construction ---------------------------------------------------

def _clean_text(values):
    """Strip whitespace; blank and missing both become the UNKNOWN sentinel.

    Turning absence into an ordinary value means no filter, map or comparison
    anywhere downstream has to special-case NaN.
    """
    text = values.fillna("").astype(str).str.strip()
    return text.where(text != "", UNKNOWN)


def _sign_of(nights):
    """-1, 0 or 1 as text, UNKNOWN where the number of nights is unknown."""
    sign = pd.Series(UNKNOWN, index=nights.index, dtype=object)
    sign[_mask(nights < 0)] = "-1"
    sign[_mask(nights == 0)] = "0"
    sign[_mask(nights > 0)] = "1"
    return sign


def _window_presence(frame, start, end):
    """BEFORE, IN or AFTER, relative to the study window.

    IN is the default and the two exclusions are the special cases, which is
    what makes the still-in-care animal come out right without a branch of its
    own: its outcome_date is NaT, ``NaT < start`` is False, so it is never
    BEFORE.  That is correct -- it has not left.
    """
    presence = pd.Series("IN", index=frame.index, dtype=object)
    presence[frame["outcome_date"] < start] = "BEFORE"
    presence[frame["intake_date"] > end] = "AFTER"
    presence[frame["intake_date"].isna()] = UNKNOWN
    return presence


def _age_group(age, age_groups):
    """Bin ages, with the cutoff falling in the *lower* group.

    ``pd.cut(..., right=True)`` closes each interval on the right, which is
    exactly that rule: with a JUVENILE cutoff of 1, an age of exactly 1 is
    JUVENILE.  Three sentinels sit outside the bins, kept separate because
    each is a different sentence in a methods section.
    """
    names = list(age_groups)
    edges = [-np.inf] + [float(cutoff) for cutoff in age_groups.values()]
    group = pd.cut(age, bins=edges, labels=names, right=True).astype(object)
    group[age > edges[-1]] = OVER
    group[age < 0] = NEGATIVE       # date of birth after intake: a data error
    group[age.isna()] = UNKNOWN     # no date of birth
    return group


def _mask(condition):
    """A nullable-boolean condition, made safe to index with."""
    return condition.fillna(False).astype(bool)


def _sha256(path):
    """SHA-256 of the file's contents, decompressing a ``.gz`` first.

    Hashing the uncompressed bytes makes the digest identify the *data* rather
    than the container: it stays equal to the digest of the original extract
    the archive was made from, and does not move if the file is recompressed
    by a different tool or at a different level.
    """
    digest = hashlib.sha256()
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    with opener(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
