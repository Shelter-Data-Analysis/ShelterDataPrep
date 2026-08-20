# Changelog

Notable changes to ShelterDataPrep, newest first.

The version that matters for a result is the one its run log reports, so an
entry here is worth reading against the log of the run you are trying to
reproduce. Anything that could move a number — a new or altered step type, a
change to how a derived column is built, a change to what the table counts —
is called out as such.

This file starts at 0.2.0, the first version stamped in
`shelterprep/version.py`. There was no 0.1.x, and 0.2.0 was never tagged, so
0.2.1 is the first release with an artifact behind it.

## 0.2.1 (2026-08-10)

Documentation, and one new example config. **No code changed**: `shelterprep/`
is untouched apart from the version string, so a run of any config produces
byte-identical output to 0.2.0. The version moves anyway, because the
documentation is part of what a citation points at and it needs a number of its
own.

### Added

- `configs/example_tiny.yaml`, which reads the 15-row fixture in
  `tests/fixtures/` and therefore runs on a fresh clone.
  It is meant to be copied as the starting point for a real config.
- `docs/`, six audience-scoped documents split out of the README:
  `getting-started` (you have an extract from a shelter this repo has never
  seen), `settings`, `steps`, `outputs`, `statistics-table`, and
  `reproducibility`. `docs/getting-started.md` is new writing — nothing
  previously walked a reader from their own extract to a first run.
- `CONTRIBUTING.md` and this file.

### Changed

- The README is an orientation document: quickstart, install, the config
  inventory, and an index into `docs/`. It keeps a short "The statistics table"
  section so that existing links to `#the-statistics-table` still resolve.
- The statistics table format is documented as a format other tools may write,
  with its open vocabularies and the warning that `rows_out` may exceed
  `rows_in` in a stage this package did not produce.

### Fixed

Documentation defects, each of which could have cost someone a working run:

- `.csv.gz` sources are read transparently and every shipped config uses one,
  which the README never said.
- An Excel source needs `pip install ".[excel]"`. `openpyxl` is an optional
  dependency, so a plain `pip install .` left a workbook failing on import,
  with nothing in the README to explain it.
- The tests command gave `python -m pytest` while the rest of the README said
  `python3`.
- The by-value section referred to a `dedup` "`on:`" key. There is no such key
  — the columns are the argument of `dedup:` itself — so following it earned an
  unknown-key error. Both the list form and the bare form are now shown.
- Five configs pointed at `orange_county.yaml`, renamed in 0.2.0. They now
  point at `orange_county2.yaml`, where the reasoning they refer to lives.

## 0.2.0 (2026-08-01)

Never tagged, so there is no artifact to cite for it; this entry is
reconstructed from the commit history rather than written at the time. It
replaces the per-shelter scripts in `stale/`, which do not run under pandas 2
and are kept only for reference.

### The package

- A run is one YAML settings file, executed as
  `python3 -m shelterprep <config>` or through the installed `shelterprep`
  command. An unknown top-level key is an error rather than a warning.
- Sources are CSV, gzipped CSV, or Excel. CSVs are read as `utf-8-sig`, because
  two of the shipped extracts carry a byte-order mark. Only the columns a run
  needs are read.
- Every date-valued thing is `datetime64[ns]`, never `datetime.date` and never
  a mix, and you state the format — inferring it is how pandas silently
  coerces a whole column to `NaT`. Unparseable values are counted on
  their own `parse_dates` row rather than disappearing.
- Derived columns — `nights`, `night_sign`, `window_presence`, `age`,
  `age_group` — are built before any step runs, so they filter and map like
  columns that came out of the file. Filtering happens in the steps you write:
  out-of-window stays and impossible date orders are removed by ordinary `cut:`
  steps that land in the statistics table like every other exclusion.
- Steps are an ordered sequence of `cut`, `map`, and `dedup`, with `where:` /
  `where_not:` guards. `map` was made simultaneous rather than sequential, and
  `dedup` keeps the last of each group.
- Blank, whitespace-only, and missing text all become `_UNKNOWN_` before any
  step runs, so a filter can name a blank and nothing downstream special-cases
  NaN.

### Four output files

- The prepared CSV, with the columns and order `output_columns` asks for.
- The statistics table: one row per stage in execution order, shaped after a
  CONSORT flow diagram, plus a by-value breakdown underneath it counting every
  value the settings name — including the ones that matched nothing, which is
  what catches a misspelled label or a vocabulary that has drifted.
- A summary of the finished set: every exported categorical column crossed
  against intake and outcome type, long rather than rectangular, with
  frequencies and a length-of-stay distribution per cell including min, max, and
  p90.
- A run log: source path, SHA-256 of the source's uncompressed contents,
  SHA-256 of the output, row count, the span the surviving rows cover, and the
  version of Python, pandas, numpy, PyYAML, and openpyxl.

### Configs

Eight, one per shelter and species. `orange_county2.yaml` is the mLOS default;
`orange_county.yaml` was retired to `orange_county1.yaml` and frozen as a
baseline. Only `orange_county1.yaml` has been checked against a known-good
result — the ports of the `stale/` modules have not been validated against
anything, and say so in the config and in the README.

`SURG SCHED` and `SURG WAIT` map to `INC` rather than `LCOM`: both name an
animal waiting on surgery, which is a state inside the shelter, not a way of
leaving it. **This moves a number** for any extract in which those codes occur.
They are 0 in the Orange County extract, so no shipped result changes.

### Project

MIT license, `CITATION.cff` for GitHub's cite button and for Zenodo, and 83
tests at 96% line coverage of `shelterprep/`.
