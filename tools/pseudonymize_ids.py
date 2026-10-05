"""Replace animal IDs in a prepared file with random pseudonyms.

For confidential data sets, run after the main run on the same settings file:

    python3 tools/pseudonymize_ids.py map   settings.yaml
    python3 tools/pseudonymize_ids.py apply settings.yaml [--output PATH]

`map` reads the raw extract the settings file names and adds a pseudonym for
each of its animal IDs to `private_animal_id.csv`, in `dest_dir` unless
`--mapping` says otherwise.  An ID already in the mapping keeps its
pseudonym, so the mapping can grow across extracts and configs.

`apply` reads the prepared file and writes a copy with every animal ID
replaced, named `<prepared>_pseudonymized.csv` unless `--output` says
otherwise, plus a short log beside it.  With no mapping file it runs `map`
first.  An ID the mapping lacks stops the run, and nothing is written.  A
prepared file without an `animal_id` column draws a warning and nothing is
written, but the run does not fail.

A pseudonym is drawn from `secrets`, so it carries no information about the
ID it replaces: the mapping is the only way back.  See
docs/pseudonymizing.md.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import secrets
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shelterprep import Prep, SettingsError, SourceError, load      # noqa: E402
from shelterprep.settings import UNKNOWN                            # noqa: E402
from shelterprep.version import __version__                         # noqa: E402

COLUMN = "animal_id"
MAPPING_FILE = "private_animal_id.csv"
SUFFIX = "_pseudonymized"


class PseudonymError(ValueError):
    """The mapping or the prepared file cannot be used as they stand."""


# --- the mapping -------------------------------------------------------------

def mapping_path(settings, override=None):
    return Path(override) if override else settings.dest_dir / MAPPING_FILE


def read_mapping(path):
    """The mapping as a dict from animal ID to pseudonym, checked both ways."""
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    if list(frame.columns) != [COLUMN, "pseudonym"]:
        raise PseudonymError(
            "{0} should have the columns {1}, pseudonym; it has: {2}".format(
                path, COLUMN, ", ".join(frame.columns)))
    for column in frame.columns:
        repeated = sorted(frame[column][frame[column].duplicated()].unique())
        if repeated:
            raise PseudonymError("{0} repeats {1} value(s): {2}".format(
                path, column, ", ".join(repeated)))
    return dict(zip(frame[COLUMN], frame["pseudonym"]))


def new_pseudonym(taken):
    """A pseudonym not in *taken*: P and 12 hex digits, 48 random bits."""
    while True:
        candidate = "P" + secrets.token_hex(6).upper()
        if candidate not in taken:
            return candidate


def extend_mapping(path, ids):
    """Add a pseudonym for each of *ids* the mapping at *path* lacks.

    Existing rows are kept as they are, in their order, and new ones follow in
    sorted order, so an extended mapping starts with the bytes it had.
    Returns (number of IDs in the mapping, number added).
    """
    mapping = read_mapping(path) if path.exists() else {}
    ids = set(ids) - {UNKNOWN}
    new = sorted(ids - set(mapping))
    taken = set(mapping.values()) | set(mapping) | ids
    rows = list(mapping.items())
    for animal_id in new:
        pseudonym = new_pseudonym(taken)
        taken.add(pseudonym)
        rows.append((animal_id, pseudonym))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow([COLUMN, "pseudonym"])
        writer.writerows(rows)
    return len(rows), len(new)


def raw_ids(settings):
    """The animal IDs of the raw extract, read as the main run reads them."""
    return Prep(settings).read().frame[COLUMN]


# --- the two modes -----------------------------------------------------------

def run_map(settings, mapping):
    total, added = extend_mapping(mapping, raw_ids(settings))
    print("mapping  {0}: {1} ID(s), {2} new".format(mapping, total, added))


def output_path(settings, override=None):
    if override:
        return Path(override)
    stem = Path(settings.dest_file).stem
    return settings.dest_dir / (stem + SUFFIX + ".csv")


def run_apply(settings, mapping, output):
    source = settings.dest_path
    if not source.exists():
        raise PseudonymError(
            "prepared file not found: {0}; run shelterprep on {1} "
            "first".format(source, settings.path))
    if output.resolve() in (source.resolve(), mapping.resolve()):
        raise PseudonymError(
            "the output {0} would overwrite the {1}".format(
                output, "prepared file" if output.resolve() == source.resolve()
                else "mapping"))

    frame = pd.read_csv(source, dtype=str, keep_default_na=False)
    if COLUMN not in frame.columns:
        print("warning: {0} has no {1} column, so there is nothing to "
              "pseudonymize; nothing written".format(source, COLUMN),
              file=sys.stderr)
        return

    if not mapping.exists():
        print("no mapping at {0}; making one from the raw extract".format(
            mapping))
        run_map(settings, mapping)
    lookup = read_mapping(mapping)

    ids = frame[COLUMN]
    unmapped = ids[(ids != UNKNOWN) & ~ids.isin(list(lookup))]
    if len(unmapped):
        counts = unmapped.value_counts().sort_index()
        lines = ["{0} holds {1} animal ID(s) that {2} lacks; nothing "
                 "written. Run map to add them:".format(
                     source.name, len(counts), mapping)]
        lines += ["  {0}  ({1} row(s))".format(value, count)
                  for value, count in counts.items()]
        raise PseudonymError("\n".join(lines))

    frame[COLUMN] = ids.map(lambda value: lookup.get(value, value))
    output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output, index=False)

    log = output.with_name(output.stem + "_run.txt")
    log.write_text("\n".join([
        "ShelterDataPrep pseudonymization log",
        "",
        "shelterprep   {0}  (tools/pseudonymize_ids.py)".format(__version__),
        "run at        {0}".format(datetime.now().isoformat(timespec="seconds")),
        "settings      {0}".format(settings.path),
        "input         {0}".format(source),
        "input sha256  {0}  (the output sha256 of its run log)".format(
            _sha256(source)),
        "mapping       {0}".format(mapping),
        "output        {0}".format(output),
        "output sha256 {0}".format(_sha256(output)),
        "output rows   {0}".format(len(frame)),
        "IDs replaced  {0} distinct".format(ids[ids != UNKNOWN].nunique()),
        "",
    ]), encoding="utf-8")
    print("wrote {0}\n      {1}".format(output, log))


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="pseudonymize_ids",
        description="Replace animal IDs in a prepared file with pseudonyms.")
    parser.add_argument("mode", choices=("map", "apply"),
                        help="map: add the raw extract's IDs to the mapping; "
                             "apply: write the pseudonymized copy")
    parser.add_argument("settings", help="the settings file of the main run")
    parser.add_argument("--mapping",
                        help="mapping file (default: {0} in dest_dir)".format(
                            MAPPING_FILE))
    parser.add_argument("--output",
                        help="apply only: output file (default: the prepared "
                             "file's name plus {0})".format(SUFFIX))
    args = parser.parse_args(argv)
    if args.output and args.mode != "apply":
        parser.error("--output applies to apply only")

    try:
        settings = load(args.settings)
        mapping = mapping_path(settings, args.mapping)
        if args.mode == "map":
            run_map(settings, mapping)
        else:
            run_apply(settings, mapping, output_path(settings, args.output))
    except (SettingsError, SourceError, PseudonymError) as error:
        print("error: {0}".format(error), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
