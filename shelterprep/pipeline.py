"""The pipeline: read, derive, apply the step sequence, write.

`Prep` carries the three things a run consists of -- the settings, the frame
being processed, and the statistics of the processing -- and exposes the four
stages as methods so any of them can be inspected in isolation from a REPL.
`Prep.run` calls them in order.
"""

from __future__ import annotations

import csv
import gzip
import hashlib
import io
import platform
import posixpath
import re
import zipfile
from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from xml.etree import ElementTree

import numpy as np
import pandas as pd
import yaml

from . import dates, steps, summary
from .version import __version__
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
        self.source = None

    def run(self, verbose=True):
        self.read()
        self.derive()
        self.apply_steps()
        self.write()
        if verbose:
            print(self.statistics.render())
            print("\nwrote {0}".format(self.settings.dest_path))
            print("      {0}".format(self.settings.stats_path))
            print("      {0}".format(self.settings.summary_path))
            print("      {0}".format(self.settings.run_path))
        return self

    # -- stage 1: read ------------------------------------------------------

    def read(self):
        """Load only the columns this run needs, under canonical names."""
        settings = self.settings
        path = settings.source_path
        if not path.exists():
            raise SourceError("source file not found: {0}".format(path))
        if path.suffix.lower() not in EXCEL_SUFFIXES and settings.sheet is not None:
            raise SourceError(
                "sheet {0!r} was given but {1} is not an Excel "
                "file".format(settings.sheet, path.name))

        if path.suffix.lower() in EXCEL_SUFFIXES:
            # A workbook is parsed whole whatever is asked for, so every column
            # is read, and the empty rows and merged headings found in it.
            whole, empty, self.source = _load_workbook(path, settings.sheet)
            header = list(whole.columns)
            by_file_name = self._resolve(settings.wanted_columns(available=set(header)), header)
            frame = whole[list(by_file_name)]
        else:
            # A CSV is read for the named columns only, and a second pass over
            # all of them, a chunk at a time, finds the empty rows without
            # holding the whole file.
            header_row = _header_row(path)
            header = list(_read_csv(path, header_row, nrows=0).columns)
            self.source = Source(None, None, header_row, 0, 0, ())
            by_file_name = self._resolve(settings.wanted_columns(available=set(header)), header)
            frame = _read_csv(path, header_row, usecols=list(by_file_name))
            chunks = _read_csv(path, header_row, chunksize=100000)
            empty = np.concatenate([_empty_rows(chunk) for chunk in chunks] or [np.zeros(0, bool)])
        self.sheet = self.source.sheet
        header_row = self.source.header_row

        frame = frame.rename(columns=by_file_name)
        frame.index = pd.RangeIndex(len(frame))
        empty = pd.Series(np.asarray(empty, dtype=bool), index=frame.index)

        date_columns = [name for name in DATE_COLUMNS if name in frame.columns]
        for column in frame.columns:
            if column not in date_columns:
                frame[column] = _clean_text(frame[column])

        self.statistics.record(
            step=0, action="read", before=frame, after=frame,
            column=str(path.name),
            detail="{0} column(s){1}{2}".format(
                len(frame.columns),
                "" if self.sheet is None else ", sheet " + self.sheet,
                "" if header_row == 0 else
                ", column names in row {0}".format(header_row + 1)))
        if empty.any():
            kept = frame.loc[~empty]
            self.statistics.record(
                step=0, action="drop_empty", before=frame, after=kept,
                affected=empty, column=str(path.name),
                detail="rows with no value in any column of the file")
            frame = kept.reset_index(drop=True)

        self.frame = frame
        self._parse_dates(date_columns)
        return self

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

    def _parse_dates(self, date_columns):
        settings = self.settings
        for column in date_columns:
            raw = self.frame[column]
            supplied = raw.notna() & (raw.astype(str).str.strip() != "")
            date_format = settings.date_format_for(column)
            parsed = dates.to_datetime(raw, date_format, settings.keep_time)
            unparsed = supplied & parsed.isna()
            self.frame[column] = parsed
            self.statistics.record(
                step=0, action="parse_dates", before=self.frame, after=self.frame,
                affected=unparsed, column=column,
                detail="{0} of {1} supplied value(s) unparseable as {2}".format(
                    int(unparsed.sum()), int(supplied.sum()), date_format))

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
                frame, settings.window_start_date, settings.window_stop_date)
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
            self._check_complete(before, step)
            chosen = steps.selection(before, step)
            after = steps.apply(before, step, chosen)
            self.statistics.record(
                step=step.index, action=step.action, before=before, after=after,
                affected=chosen, column=step.column, detail=step.detail,
                breakdown=steps.breakdown(before, step, chosen))
            self.frame = after
        return self

    def _check_complete(self, frame, step):
        """Stop on values a ``complete: true`` map has no entry for."""
        missing = steps.unmapped(frame, step)
        if missing.empty:
            return
        listed = "\n".join("  {0!r}: {1} row(s)".format(value, int(count))
                           for value, count in missing.items())
        raise SourceError(
            "step {0} maps {1} with 'complete: true', but has no entry for "
            "{2} value(s):\n{3}\nadd each to the map, mapping a value to "
            "itself to keep it".format(step.index, step.column, len(missing), listed))

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
        summary.summarize(self.frame, settings).to_csv(
            settings.summary_path, index=False)
        settings.run_path.write_text(self._run_log(), encoding="utf-8")
        return self

    def _span(self):
        """The dates the surviving rows actually cover, and how many have no end.

        The one descriptive fact the summary table cannot carry: it counts
        stays, and this is about when they happened.  Worth a line because the
        span of the kept rows is not the study window -- the steps move it.

        The count is of rows with no outcome date, not of animals still in
        care: a row whose outcome is real but whose date failed to parse has
        none either, and only the config's own vocabulary (``_NODATE_`` in the
        shipped ones) tells the two apart.
        """
        frame = self.frame
        if frame.empty:
            return "(no rows)"
        undated = int(frame["outcome_date"].isna().sum())
        return "intake {0} to {1}, last outcome {2}, {3} with no outcome date".format(
            frame["intake_date"].min().date(), frame["intake_date"].max().date(),
            frame["outcome_date"].max().date(), undated)

    def _run_log(self):
        """Everything needed to say where this output came from.

        Written last, so the digest of the output file is of the file that was
        actually just written.  Between the two digests a reader can verify
        both ends of the run: that the extract is the one named, and that the
        prepared file has not been edited since.
        """
        settings = self.settings
        lines = [
            "ShelterDataPrep run log",
            "",
            "shelterprep   {0}".format(__version__),
            "run at        {0}".format(datetime.now().isoformat(timespec="seconds")),
            "settings      {0}".format(settings.path),
            "source        {0}".format(settings.source_path),
            "source sha256 {0}  (of the uncompressed contents)".format(
                _sha256(settings.source_path)),
            "sheet         {0}".format(self.sheet or "(csv)"),
        ] + _source_notes(self.source) + [
            "date_format   {0}".format(settings.date_format),
        ] + [
            "  {0:<12}{1}  (date_format_override)".format(column, date_format)
            for column, date_format in settings.date_format_override.items()
        ] + [
            "keep_time     {0}".format(settings.keep_time),
            "window        {0}".format(
                "{0} to {1} (stop date excluded)".format(
                    settings.window_start_date.date(),
                    settings.window_stop_date.date())
                if settings.has_window else "(none)"),
            "destination   {0}".format(settings.dest_path),
            "output sha256 {0}".format(_sha256(settings.dest_path)),
            "output rows   {0}".format(len(self.frame)),
            "final span    {0}".format(self._span()),
            "",
        ] + _environment() + [
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


def _window_presence(frame, start, stop):
    """BEFORE, IN or AFTER, relative to the study window [start, stop).

    IN is the default and the two exclusions are the special cases, which is
    what makes the still-in-care animal come out right without a branch of its
    own: its outcome_date is NaT, ``NaT < start`` is False, so it is never
    BEFORE.  That is correct -- it has not left.

    The window is a span of whole days.  Both dates are normalized first, so
    under ``keep_time`` the time of day never moves a stay across an edge.
    """
    presence = pd.Series("IN", index=frame.index, dtype=object)
    presence[frame["outcome_date"].dt.normalize() < start] = "BEFORE"
    presence[frame["intake_date"].dt.normalize() >= stop] = "AFTER"
    presence[frame["intake_date"].isna()] = UNKNOWN
    return presence


#: One day, in the fractional years `age` is measured in.  See `_age_group`.
_ONE_DAY = 1.0 / 365.25


def _age_group(age, age_groups):
    """Bin ages, with the cutoff falling in the *lower* group.

    ``pd.cut(..., right=True)`` closes each interval on the right, which is
    exactly that rule: with a JUVENILE cutoff of 1, an age of exactly 1 is
    JUVENILE.  Three sentinels sit outside the bins, kept separate because
    each is a different sentence in a methods section.

    Each cutoff admits one further day, which is what a leap year adds to a
    round-year guess.  Shelter staff routinely record an age as a whole number
    of years, so `dob` lands exactly N years before intake; `age` divides days
    by 365.25, so the same guess reads 0.99932 when the interval held no leap
    day and 1.00205 when it held one.  Without the extra day those two fall in
    different groups.  Cutoffs at a multiple of four are unaffected either way,
    since four years is 1461 days and 4 * 365.25 is 1461 exactly.
    """
    names = list(age_groups)
    edges = [-np.inf] + [float(cutoff) + _ONE_DAY for cutoff in age_groups.values()]
    group = pd.cut(age, bins=edges, labels=names, right=True).astype(object)
    group[age > edges[-1]] = OVER
    group[age < 0] = NEGATIVE       # date of birth after intake: a data error
    group[age.isna()] = UNKNOWN     # no date of birth
    return group


def _mask(condition):
    """A nullable-boolean condition, made safe to index with."""
    return condition.fillna(False).astype(bool)


def _environment():
    """The interpreter and libraries this run actually used.

    Recorded because a result is only reproducible against a stated
    environment: pandas has changed the behavior of date parsing, of groupby
    and of nullable integers across minor versions, and "it ran under pandas 2"
    is not a version.  Optional libraries are listed as absent rather than
    omitted, so the line means the same thing whether or not they were needed.
    """
    lines = [
        "python        {0} on {1}".format(
            platform.python_version(), platform.platform()),
        "pandas        {0}".format(pd.__version__),
        "numpy         {0}".format(np.__version__),
        "PyYAML        {0}".format(yaml.__version__),
    ]
    try:
        import openpyxl
        lines.append("openpyxl      {0}".format(openpyxl.__version__))
    except ImportError:
        lines.append("openpyxl      (not installed; Excel sources unavailable)")
    return lines


# -- reading a source --------------------------------------------------------
#
# The column names come from the first row with a value in any column, so a
# title or spacer row above them is passed over, and a row below them with no
# value in any column is dropped as no stay. Both rules look at every column
# of the file, not only those a run reads, so a row that holds a note in a
# column nobody reads is still read as a row.
#
# Two repairs apply to a workbook alone. Excel writes font families above 14,
# which openpyxl refuses as a broken style table; a font's family changes only
# how text is drawn, so those entries are dropped from a copy read in its
# place. And a heading merged across columns keeps its text in the leftmost
# one, which may be empty while the values sit in another column of the span;
# where exactly one unnamed column of the span holds values, it takes the
# heading's name. The run log records both.

@dataclass(frozen=True)
class Source:
    """A source file as a run reads it.

    *frame* is every column as text, with the empty rows dropped (None for a
    CSV inside a run, which reads only the columns it needs); *sheet* is the
    sheet read, None for a CSV; *header_row* is the 0-based row of the column
    names; *empty_rows* counts the rows dropped below them; *fonts_dropped*
    counts the font-family entries left out of the copy read; *headings_moved*
    pairs each heading moved with the name pandas gave its column of values.
    """
    frame: object
    sheet: object
    header_row: int
    empty_rows: int
    fonts_dropped: int
    headings_moved: tuple


def read_source(path, sheet=None):
    """A source file's every column as text, as a run reads it.

    For a program that shows the file to someone before a settings file exists
    for it, such as mLOS Web. Returns a `Source`.
    """
    path = Path(path)
    if path.suffix.lower() in EXCEL_SUFFIXES:
        whole, empty, source = _load_workbook(path, sheet)
        return replace(source, frame=whole.loc[~empty].reset_index(drop=True))
    header_row = _header_row(path)
    frame = _read_csv(path, header_row)
    empty = _empty_rows(frame)
    return Source(frame.loc[~empty].reset_index(drop=True), None, header_row,
                  int(empty.sum()), 0, ())


def open_workbook(path):
    """A workbook as pandas reads it, and the font entries dropped to read it.

    Returns a `pandas.ExcelFile` and a count, 0 when openpyxl reads the
    workbook as saved.
    """
    book, dropped = _workbook(Path(path))
    return pd.ExcelFile(book()), dropped


_FONT_FAMILY = re.compile(rb'<family val="(1[5-9]|[2-9][0-9]|[0-9]{3,})"\s*/>')


def _workbook(path):
    """A function giving something pandas can read the workbook from, and the
    font-family entries dropped from the copy it reads, 0 for the file itself."""
    try:
        pd.ExcelFile(path)
        return (lambda: path), 0
    except ValueError as error:
        if "stylesheet" not in str(error):
            raise
        parts, dropped = [], 0
        with zipfile.ZipFile(path) as source:
            for item in source.infolist():
                data = source.read(item.filename)
                if item.filename == "xl/styles.xml":
                    data, dropped = _FONT_FAMILY.subn(b"", data)
                parts.append((item, data))
        if not dropped:
            raise
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as copy:
            for item, data in parts:
                copy.writestr(item, data)
        data = buffer.getvalue()
        return (lambda: io.BytesIO(data)), dropped


def _load_workbook(path, sheet):
    """The sheet's every column with its empty rows, the mask of those rows,
    and a `Source` without its frame."""
    book, dropped = _workbook(path)
    names = pd.ExcelFile(book()).sheet_names
    if sheet is None:
        if len(names) != 1:
            raise SourceError(
                "{0} has {1} sheets ({2}), so 'sheet:' is required".format(
                    path.name, len(names), ", ".join(names)))
        sheet = names[0]
    elif sheet not in names:
        raise SourceError(
            "{0} has no sheet {1!r}; it has: {2}".format(
                path.name, sheet, ", ".join(names)))

    count = 50
    while True:
        top = pd.read_excel(book(), sheet_name=sheet, header=None, nrows=count, dtype=str)
        filled = np.flatnonzero(~_empty_rows(top))
        if len(filled) or len(top) < count:
            break
        count *= 4
    if not len(filled):
        raise SourceError("{0}, sheet {1} has no column names: every row is "
                          "empty".format(path.name, sheet))
    header_row = int(filled[0])

    frame = pd.read_excel(book(), sheet_name=sheet, header=header_row, dtype=str)
    names = list(frame.columns)
    filled = [bool(frame[column].notna().any() and frame[column].astype(str).str.strip().ne("").any())
              for column in frame.columns] if len(frame.columns) else []
    moved = []
    for first, last in _merged_headings(book, sheet, header_row + 1):
        if first >= len(names) or _unnamed(names[first]) or filled[first]:
            continue
        under = [j for j in range(first + 1, min(last, len(names) - 1) + 1) if filled[j]]
        if len(under) != 1 or not _unnamed(names[under[0]]):
            continue
        moved.append((str(names[first]), str(names[under[0]])))
        names[under[0]], names[first] = names[first], "Unnamed: {0}".format(first)
    frame.columns = names
    empty = _empty_rows(frame)
    return frame, empty, Source(None, sheet, header_row, int(empty.sum()), dropped, tuple(moved))


def _unnamed(name):
    """Whether pandas gave a column no name of the file's own."""
    return not str(name).strip() or re.fullmatch(r"Unnamed: \d+", str(name)) is not None


def _merged_headings(book, sheet, row):
    """The 0-based first and last columns of each range merged across columns
    that starts in *row*, the 1-based row of the column names."""
    main = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    rel = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
    with zipfile.ZipFile(book()) as source:
        rid = next(item.get(rel + "id") for item in
                   ElementTree.fromstring(source.read("xl/workbook.xml")).iter(main + "sheet")
                   if item.get("name") == sheet)
        target = next(item.get("Target") for item in
                      ElementTree.fromstring(source.read("xl/_rels/workbook.xml.rels"))
                      if item.get("Id") == rid)
        part = target.lstrip("/") if target.startswith("/") else \
            posixpath.normpath(posixpath.join("xl", target))
        xml = source.read(part).decode("utf-8", "replace")
    index = lambda letters: sum((ord(c) - 64) * 26 ** k
                                for k, c in enumerate(reversed(letters))) - 1
    return [(index(a), index(b)) for a, r, b in
            re.findall(r'<mergeCell ref="([A-Z]+)([0-9]+):([A-Z]+)[0-9]+"', xml)
            if int(r) == row and a != b]


def _source_notes(source):
    """The run log's lines on what the reader repaired, if anything."""
    if source is None:
        return []
    lines = []
    if source.fonts_dropped:
        lines.append("repaired      {0} font family setting(s) above 14 left out of a "
                     "copy read in place of the source, whose digest is above".format(
                         source.fonts_dropped))
    for heading, column in source.headings_moved:
        lines.append("heading       {0} names the column under its merged heading "
                     "({1})".format(heading, column))
    return lines


def _header_row(path):
    """The 0-based row a CSV's column names are in: the first that is not empty."""
    opener = gzip.open if path.suffix.lower() == ".gz" else open
    with opener(path, "rt", encoding="utf-8-sig", newline="") as handle:
        for number, fields in enumerate(csv.reader(handle)):
            if any(field.strip() for field in fields):
                return number
    raise SourceError("{0} has no column names: every row is empty".format(path.name))


def _read_csv(path, header_row, **options):
    # utf-8-sig, not utf-8: the Orange County and Long Beach exports carry a
    # byte-order mark, which otherwise becomes part of the first column name
    # and makes every lookup on it fail. Blank lines are kept as rows, so that
    # the header row counts lines as _header_row does and an empty line is
    # dropped and counted like any other empty row.
    return pd.read_csv(path, dtype=str, encoding="utf-8-sig", header=header_row,
                       skip_blank_lines=False, **options)


def _empty_rows(frame):
    """True for each row with no value, or only spaces, in any column."""
    if frame.shape[1] == 0:
        return np.ones(len(frame), dtype=bool)
    text = frame.astype(object).where(frame.notna(), "")
    return ~text.apply(lambda column: column.astype(str).str.strip() != "").any(axis=1).to_numpy()


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
