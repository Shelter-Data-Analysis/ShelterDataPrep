# The settings file

*For anyone writing or editing a config: every top-level key, what it means,
and how dates are handled. If you are starting from nothing, read [preparing
your own shelter data](getting-started.md) first — it puts these keys in the
order you will need them.*

[← ShelterDataPrep](../README.md)

A run is one YAML settings file. These are all fourteen top-level keys:

```yaml
source_dir:   "../../_shelter_raw"
source_file:  "intakes and outcomes.csv"
sheet:                       # Excel only; omit and the file must have one sheet
date_format:  ISO8601        # or: mixed  (US-style m/d/Y extracts)
keep_time:    false

window_start_date: 2018-07-01   # optional pair, both or neither
window_end_date:   2024-10-19

dest_dir:   "../results"
dest_file:  "OC2_data.csv"
output_columns: [animal_id, intake_date, outcome_date, outcome_type, animal_size]

columns:                     # canonical_name: name_in_file
  intake_date: "Intake Date"

age_groups: {JUVENILE: 1, YOUNG: 4, ADULT: 9, SENIOR: 18}
unique_report: [animal_id]

steps:
  - cut: {window_presence: [BEFORE, AFTER]}
  - cut: {animal_type: [CAT, BIRD]}
  - map: {outcome_type: {ADOPTION: TRANSFER}}
    where: {outcome_subtype: [TRANSFER, RESCUE]}
```

An unknown top-level key is an error, not a warning. A misspelled setting that
quietly skips an exclusion is the failure mode that survives into a published
table.

`steps:` has a grammar of its own, in [steps and derived
columns](steps.md).

## Paths

`source_dir` and `dest_dir` are relative, and resolve against the settings file
rather than the working directory, so a run means the same thing from anywhere.
Nothing in `configs/` names a home directory or a machine, so a clone of this
repo next to a `_shelter_raw/` directory runs as written.

The shipped configs read `../../_shelter_raw` — a sibling of the repo, so the
extracts can never be committed — and write to `../results`.

## The source file

CSV or Excel, decided by the file extension.

**Gzipped CSVs need no setting.** pandas reads `.csv.gz` transparently, so
`source_file: "OC_raw.csv.gz"` works exactly like the uncompressed name, and
every shipped config uses that form — a real extract is large enough to be
worth it. The run log's `source sha256` is taken over the *uncompressed*
contents, so compressing a file does not change its recorded identity.

**Excel needs `openpyxl`**, which is an optional dependency: install with
`pip install ".[excel]"` rather than plain `pip install .`. `sheet:` names the
worksheet; omit it and the workbook must contain exactly one, or the run stops
and tells you how many it found.

**CSVs are read as `utf-8-sig`.** The Orange County and Long Beach exports
carry a byte-order mark, which otherwise becomes part of the first column name
and makes every lookup on it fail.

Only the columns a run actually needs are read, which keeps a 70 MB extract
cheap.

## Columns

Five canonical fields must resolve to a column in the file: `animal_id`,
`intake_date`, `outcome_date`, `intake_type`, `outcome_type`. `dob` is used
when present and ignored when absent. Anything else a step or `output_columns`
names is assumed to exist in the file under that exact name; if it does not,
the run stops and the error lists what the file does contain.

`columns:` renames file columns to canonical names — and only ever in that
direction. The previous pipeline renamed *outward* (`outcome_date` became
`outdate`, `outcome_type` became `outcome`) while leaving the originals in the
frame, so two spellings of the same field circulated at once and different
functions read different ones. Nothing here is renamed on the way out.

## The study window

`window_start_date` and `window_end_date` are an optional pair — both or
neither. They do not filter anything by themselves. They build the
`window_presence` column, and an ordinary `cut:` step removes what you want
removed, so the count lands in the statistics table like every other exclusion.

The rule is overlap, not intake date: a stay is `BEFORE` when it ended before
the window opened and `AFTER` when it began after the window closed. See
[derived columns](steps.md#derived-columns).

## age_groups and unique_report

`age_groups` maps a name to the upper cutoff of that band, in years at intake,
and is what builds `age_group`. `unique_report` names the identifier columns
the statistics table counts distinctly — normally just `animal_id`, which gives
every stage an animal count alongside its row count.

## Dates

One rule, and the reason this package exists:

> Every date-valued thing here is `datetime64[ns]`. Never `datetime.date`,
> never a mix.

`keep_time: false` (the default) normalises to midnight — the time is dropped,
the dtype is not. `keep_time: true` preserves it. `nights` is computed from
normalised values either way, so the switch can never shift a night count.
Dates become `YYYY-MM-DD` strings only at the moment they are written.

**Format is always explicit.** Left to infer, pandas locks onto one format from
the first non-null value and silently coerces everything else to `NaT`:

```python
>>> s = pd.Series(["2018-01-01 14:30:00", "2018-03-02"])
>>> list(pd.to_datetime(s, errors="coerce"))
[Timestamp('2018-01-01 14:30:00'), NaT]
```

That row would leave the study with no warning. `ISO8601` accepts both
spellings; `mixed` also accepts US-style `m/d/Y`, at the cost of guessing on
ambiguous days. Whatever still fails to parse is **counted**, on its own
`parse_dates` row in the statistics table.

**A date that fails to parse becomes `NaT`, which downstream is
indistinguishable from a date that was never recorded** — for `outcome_date`
that reads as "still in care". The `parse_dates` row of the statistics table
is what catches it, so it is worth looking at before trusting a run. A row in
that state is visible in the frame as `outcome_type` set to something real
while `night_sign` is `_UNKNOWN_`; the old pipeline repaired it by assuming
the animal left the day it arrived (`stale/_PhysicsSubs.py:28-30`). That
repair is **not** reproduced here, because a cut or a map cannot rewrite a
date. If you want it, it needs to be a new feature rather than a settings
change.

---

**See also:** [steps and derived columns](steps.md) ·
[preparing your own shelter data](getting-started.md) ·
[the prepared file](outputs.md) · [the statistics table](statistics-table.md)
