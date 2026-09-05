# Changelog

Notable changes to ShelterDataPrep, newest first.

The version that matters for a result is the one its run log reports, so an
entry here is worth reading against the log of the run you are trying to
reproduce. Anything that could move a number — a new or altered step type, a
change to how a derived column is built, a change to what the table counts —
is called out as such.

This file starts at 0.2.0, the first version stamped in
`shelterprep/version.py`. There was no 0.1.x, and neither 0.2.0 nor 0.2.1 was
tagged, so 0.3.0 is the first release with an artifact behind it.

## Unreleased

### Fixed

- pandas is capped below 3. pandas 3.0 was released in January 2026 and
  installs on Python 3.11 and newer, so the floor-only `pandas>=2.0` had begun
  resolving to it. pandas 3 infers microsecond resolution when parsing date
  strings, where pandas 2 always gave nanoseconds, so a parsed column arrives
  as `datetime64[us]`. `shelterprep/dates.py` states `datetime64[ns]` as the
  one date rule in the package and two tests assert it by name, which made a
  fresh install on a recent Python a failing suite.

  **No numbers move** for an install that already resolved to pandas 2, which
  is every install on Python 3.10 or older and any environment holding pandas
  2 deliberately. Whether pandas 3 would move a number is untested, and
  answering that is part of the migration the cap defers: the module has to
  say whether it promises one resolution or only a naive `datetime64`.

## 0.3.1 (2026-08-22)

Documentation. **No code changed**: `shelterprep/` is untouched apart from the
version string, so a run of any config produces byte-identical output to
0.3.0. The version moves because what a citation points at has changed.

### Added

- ShelterDataPrep has a DOI:
  [10.5281/zenodo.22051338](https://doi.org/10.5281/zenodo.22051338), the
  concept DOI, which resolves to the newest release. `CITATION.cff` carries it
  in `doi:`, and the README, `CONTRIBUTING.md`, and `docs/reproducibility.md`
  name it in the three places that until now said the version number was the
  whole citation.
- What the shipped configs produce is deposited at
  [10.5281/zenodo.22051368](https://doi.org/10.5281/zenodo.22051368), CC BY
  4.0: each prepared file with its statistics table, its run log, and the
  settings file behind it. Those files were produced under 0.3.0, and this
  release does not move them — the deposit stays valid because 0.3.1 writes
  the same bytes.

## 0.3.0 (2026-08-21)

**Numbers move** — in the age cutoff, in outcomes carrying no date, and in two
configs that now take a size as a stand-in for a missing age — and each is
called out where it appears. The rest corrects documentation against the code.

### Fixed

Every document was reviewed against the code and against live runs. Four
claims were wrong, and a reader who relied on any of them was misinformed:

- **`window_presence` on a still-in-care animal.** `docs/steps.md` said such a
  row stays `IN`. It does not: the assignments run default `IN`, then `BEFORE`
  where `outcome_date < start`, then `AFTER` where `intake_date > end`, so an
  animal admitted after the window closed and not yet released comes out
  `AFTER`. Eight rows of the OC2 run are in that state. What holds, and what
  the code's own docstring claims, is that such a row cannot be `BEFORE`.
  `README.md` compressed the neighboring test the same way.
- **`age` is not rounded.** `docs/outputs.md` described `nights` and `age`
  together as whole numbers. `age` is `(intake_date - dob).dt.days / 365.25`
  and keeps its fraction: 12.106776 on the OC2 run, whole in fewer than 5% of
  rows.
- **`scope` has four values, not three.** `rows excluded by where_not` was
  missing from `docs/statistics-table.md`, which described that case at length
  without naming it. No shipped config uses `where_not`, so it appears in no
  output.
- **The sample run log had drifted from the artifact.** It showed an old
  version and an old output digest, relative paths the log does not print, and
  omitted `sheet`, `date_format`, `keep_time`, and `window` — four fields that
  are half the reason the run log is enough to reproduce a result.

### Changed

- An age cutoff admits one further day. Shelter staff record an age as a whole
  number of years, so `dob` lands exactly N years before intake, and `age`
  divides days by 365.25 — so the same guess reads 0.99932 when the year held
  no leap day and 1.00205 when it held one, and the two fell in different
  groups. **This moves a number**: 692 rows change `age_group` on OC2, 690 on
  OC1, and fewer elsewhere. It also moves three row counts, because a cutoff
  that no longer overshoots stops sending rows to `_OVER_`, which several
  configs cut: Long Beach 12,183 to 12,184, Mission Viejo 4,661 to 4,662, and
  `orange_county1.yaml` 36,564 to 36,567. Cutoffs at a multiple of four are
  unaffected, since four years is 1461 days and 4 x 365.25 is 1461 exactly.
- Every config marks an outcome that carries no date. A real outcome code with
  a blank `outcome_date` otherwise reads downstream as still in care, which it
  is not: the date failed to parse, or was never recorded. A `map:` guarded by
  `night_sign: _UNKNOWN_` relabels those rows `_NODATE_`, so the count lands in
  the statistics table and the analysis can decide; mLOS discards them. One row
  each on OC1, Mission Viejo, LA County dogs, LA County cats, and the fixture,
  and none on OC2.
- `orange_county2.yaml` and `mission_viejo.yaml` take a `PUPPY` size as the
  age when the date of birth cannot supply one. Where one field is missing or
  impossible and another can stand in for it, the config uses the stand-in, as
  an ordinary `map:` step that lands in the statistics table like every other
  decision. **This moves a number** for a run that strata on `age_group`: 133
  rows on OC2, 132 of them dates of birth falling after the intake date, and 2
  on Mission Viejo. No row count changes, and a run using
  `animal_group_columns: [animal_size]` is unaffected.
- `long_beach.yaml` and `mission_viejo.yaml` fold `age_group` `_NEGATIVE_`
  into `_UNKNOWN_`, as `orange_county2.yaml` already did, so the three configs
  that export the column ship the same vocabulary. A date of birth falling
  after the intake date says the record is wrong rather than that the animal
  is young. 12 rows on Long Beach and 4 on Mission Viejo, of which the PUPPY
  step recovers 1. Neither row count moves.
- Install commands read `python3 -m pip` rather than `pip`, which installs
  into the interpreter named on the same line whichever of `pip` and `pip3` a
  system provides. A machine can carry one, the other, or neither, and the two
  can belong to different interpreters.
- `docs/steps.md` and `docs/outputs.md` say what `dedup:` does and does not
  settle: the bare form compares every output column, so widening the output
  narrows the step; naming the columns deduplicates harder; and same-day
  repeats, overlapping stays, and rows disagreeing about the outcome survive
  by design, for a screen in the analysis downstream.
- `mission_viejo.yaml` exports `age_group`, so the repair above reaches a
  consumer of the prepared file rather than stopping at the statistics table.
  That export also puts an `age_group` table in the summary, and adds the
  column to the bare `dedup:` comparison, which drops no rows there either
  way. `orange_county1.yaml` builds `age_group` and does not export it, and
  stays that way: it is frozen as a baseline. The remaining configs have no
  date of birth, so they have no `age_group` to export.
- The raw extracts the shipped configs read are deposited at
  10.5281/zenodo.22051091, CC BY 4.0, so running one no longer depends on
  having been sent the file. The README, `docs/getting-started.md`,
  `docs/reproducibility.md`, and every config that reads an extract name the
  deposit. `CITATION.cff` carries the deposit as a `references` entry, and its
  `message` asks anyone using that data to cite it alongside the software.
  No output changes.

## 0.2.1 (2026-08-10)

Never tagged either, so like 0.2.0 it has no artifact to cite.

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
- An Excel source needs `python3 -m pip install ".[excel]"`. `openpyxl` is an
  optional dependency, so a plain `python3 -m pip install .` left a workbook
  failing on import, with nothing in the README to explain it.
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
baseline. Only `orange_county1.yaml` was manually derived and checked against
a previous result — the ports of the stale pipeline's modules have not been
validated against anything, and say so in the config and in the README.

`SURG SCHED` and `SURG WAIT` map to `INC` rather than `LCOM`: both name an
animal waiting on surgery, which is a state inside the shelter, not a way of
leaving it. **This moves a number** for any extract in which those codes occur.
They are 0 in the Orange County extract, so no shipped result changes.

### Project

MIT license, `CITATION.cff` for GitHub's cite button and for Zenodo, and 83
tests at 96% line coverage of `shelterprep/`.
