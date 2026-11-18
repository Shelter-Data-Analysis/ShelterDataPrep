"""Stack several extracts of one shelter, such as one file per year, into one.

    python3 tools/stack_extracts.py OUTPUT.xlsx INPUT [INPUT ...] --key COLUMN

Inputs are read in the order given, so name them oldest first.  Each may be
CSV or Excel (.xls needs the `xlrd` package, .xlsx needs `openpyxl`).  The
output is .xlsx or .csv, chosen by its suffix, and a log of what was flagged
is written beside it as `<output>_stack_log.txt`.

Headers.  A file whose first row holds the key column's name has a header
row.  A file without one takes the header of the first file that has one,
provided it has the same number of columns, and the log says so.  If no file
has a header row, or a headerless file has a different number of columns,
nothing is written.

Fields.  The log lists, for each file, the columns it lacks or adds relative
to the first file, and any change in column order.  Columns are stacked by
name; a file lacking a column gets blanks in it.

Duplicates.  A record is identified by the key column (one row per stay, such
as an impound number).  A key that appears more than once, in one file or
across files, is kept once.  Copies that agree in every column collapse
silently; copies that disagree are flagged in the log with the columns that
differ, and the copy from the file listed last is kept.  Rows with a blank
key are all kept and counted in the log.

A last column, `Source Files`, names every input a kept row was found in,
unless `--no-source` is given.
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

SOURCE = "Source Files"
EXCEL = (".xls", ".xlsx", ".xlsm")


class StackError(ValueError):
    """The inputs cannot be stacked as they stand."""


def read_raw(path):
    """Every row of the file, the first included, as objects."""
    path = Path(path)
    if path.suffix.lower() in EXCEL:
        return pd.read_excel(path, header=None, dtype=object)
    return pd.read_csv(path, header=None, dtype=str, keep_default_na=False)


def blank(value):
    return value is None or (isinstance(value, float) and pd.isna(value)) \
        or (isinstance(value, str) and value.strip() == "")


def text(value):
    """A cell as text, for comparing copies: blanks agree with blanks."""
    if blank(value):
        return ""
    if isinstance(value, (datetime, pd.Timestamp)):
        return pd.Timestamp(value).isoformat()
    return str(value).strip()


def has_header(raw, key):
    return len(raw) > 0 and key in [text(v) for v in raw.iloc[0]]


def read_all(paths, key):
    """Each input as a frame with its own header, and the header notes."""
    raws = [read_raw(p) for p in paths]
    notes = []
    header = next((tuple(text(v) for v in raw.iloc[0])
                   for raw in raws if has_header(raw, key)), None)
    if header is None:
        raise StackError(f"no input has a header row naming {key!r}")
    donor = next(Path(p).name for p, raw in zip(paths, raws)
                 if has_header(raw, key))
    frames = []
    for path, raw in zip(paths, raws):
        name = Path(path).name
        if has_header(raw, key):
            frame = raw.iloc[1:].copy()
            frame.columns = [text(v) for v in raw.iloc[0]]
        elif raw.shape[1] == len(header):
            frame = raw.copy()
            frame.columns = list(header)
            notes.append(f"{name}: no header row; took the {len(header)} "
                         f"column names of {donor}")
        else:
            raise StackError(
                f"{name} has no header row and {raw.shape[1]} columns, "
                f"but {donor} has {len(header)}")
        frame = frame.reset_index(drop=True)
        frame[SOURCE] = name
        frames.append((name, frame))
    return frames, notes


def compare_fields(frames):
    """Log lines for each file whose columns differ from the first file's."""
    first_name, first = frames[0]
    ref = [c for c in first.columns if c != SOURCE]
    lines = []
    for name, frame in frames[1:]:
        cols = [c for c in frame.columns if c != SOURCE]
        lacks = [c for c in ref if c not in cols]
        adds = [c for c in cols if c not in ref]
        if lacks:
            lines.append(f"{name}: lacks {lacks} (present in {first_name})")
        if adds:
            lines.append(f"{name}: adds {adds} (absent from {first_name})")
        shared = [c for c in cols if c in ref]
        if not lacks and not adds and shared != [c for c in ref if c in cols]:
            lines.append(f"{name}: same columns as {first_name}, "
                         f"in a different order")
    return lines


def stack(frames, key):
    """The stacked frame, one row per key, and the duplicate log lines."""
    columns = []
    for _, frame in frames:
        columns += [c for c in frame.columns if c not in columns]
    columns = [c for c in columns if c != SOURCE] + [SOURCE]
    allrows = pd.concat([f for _, f in frames], ignore_index=True)
    allrows = allrows.reindex(columns=columns)
    data = [c for c in columns if c != SOURCE]
    keys = allrows[key].map(text)

    lines = []
    blank_key = keys == ""
    if blank_key.any():
        lines.append(f"{int(blank_key.sum())} rows with a blank {key!r}; "
                     f"all kept")

    named = allrows[~blank_key]
    dup = keys[~blank_key].duplicated(keep=False)
    agree, within, conflicts = 0, 0, []
    drop, sources = [], {}
    for k, group in named[dup].groupby(keys[~blank_key][dup], sort=False):
        names = list(dict.fromkeys(group[SOURCE]))
        within += group[SOURCE].duplicated().any()
        drop += list(group.index[:-1])
        sources[group.index[-1]] = "; ".join(names)
        as_text = group[data].apply(lambda col: col.map(text))
        differ = [c for c in data if as_text[c].nunique() > 1]
        if differ:
            conflicts.append(f"{k} in {', '.join(group[SOURCE])}: "
                             f"{', '.join(differ)} differ; kept the copy "
                             f"from {group[SOURCE].iloc[-1]}")
        else:
            agree += 1
    out = allrows.drop(index=drop)
    for i, names in sources.items():
        out.at[i, SOURCE] = names

    lines.append(f"{len(allrows)} rows read; {len(out)} kept; "
                 f"{len(drop)} duplicate copies dropped")
    lines.append(f"{agree} keys repeated with identical copies")
    if within:
        lines.append(f"{within} keys repeated within a single file")
    lines.append(f"{len(conflicts)} keys whose copies disagree")
    lines += ["  " + c for c in conflicts]
    return out.reset_index(drop=True), lines


def dates_to_days(frame):
    """Datetime columns that carry no time of day, as dates, for Excel."""
    for col in frame.columns:
        values = [v for v in frame[col] if isinstance(v, (datetime,
                                                         pd.Timestamp))]
        if values and all(pd.Timestamp(v).time().isoformat() == "00:00:00"
                          for v in values):
            frame[col] = [pd.Timestamp(v).date()
                          if isinstance(v, (datetime, pd.Timestamp)) else v
                          for v in frame[col]]
    return frame


def write(frame, path):
    path = Path(path)
    if path.suffix.lower() == ".csv":
        frame.to_csv(path, index=False)
    elif path.suffix.lower() == ".xlsx":
        dates_to_days(frame).to_excel(path, index=False)
    else:
        raise StackError(f"output must end in .xlsx or .csv, not {path.name}")


def log_path(output):
    output = Path(output)
    return output.with_name(output.stem + "_stack_log.txt")


def run(output, inputs, key, source=True):
    """Stack the inputs into output; return the log lines."""
    frames, notes = read_all(inputs, key)
    fields = compare_fields(frames)
    out, dupes = stack(frames, key)
    if not source:
        out = out.drop(columns=SOURCE)
    write(out, output)
    lines = ([f"Stacked {len(inputs)} files into {Path(output).name} "
              f"on key {key!r}, {datetime.now():%Y-%m-%d %H:%M}"]
             + [f"  {Path(p).name}: {len(f)} rows"
                for p, (_, f) in zip(inputs, frames)]
             + ["", "Headers:"] + (["  " + n for n in notes] or ["  all present"])
             + ["", "Fields:"] + (["  " + n for n in fields]
                                  or ["  same in every file"])
             + ["", "Duplicates:"] + ["  " + n for n in dupes])
    log_path(output).write_text("\n".join(lines) + "\n")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Stack several extracts of one shelter into one file.")
    parser.add_argument("output", help="the stacked file, .xlsx or .csv")
    parser.add_argument("inputs", nargs="+", help="extracts, oldest first")
    parser.add_argument("--key", required=True,
                        help="the column that identifies a record")
    parser.add_argument("--no-source", action="store_true",
                        help=f"leave out the {SOURCE!r} column")
    args = parser.parse_args(argv)
    try:
        lines = run(args.output, args.inputs, args.key, not args.no_source)
    except StackError as err:
        print(f"stack_extracts: {err}; nothing written", file=sys.stderr)
        return 1
    print("\n".join(lines))
    print(f"\nLog: {log_path(args.output)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
