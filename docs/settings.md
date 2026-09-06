# The settings file

*For anyone writing or editing a config: every top-level key, what it means,
and how dates are handled. If you are starting from nothing, read [preparing
your own shelter data](getting-started.md) first — it puts these keys in the
order you will need them.*

[← ShelterDataPrep](../README.md)

A run is one YAML settings file. These are the top-level keys:

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

An unknown top-level key is an error, not a warning. A misspelled setting can
quietly skip an exclusion, and that failure survives into a published table.

`steps:` has a grammar of its own, in [steps and derived
columns](steps.md).

## Paths

`source_dir` and `dest_dir` are relative, and resolve against the settings file
rather than the working directory, so a run means the same thing from anywhere.

The shipped configs keep to relative paths, so a clone of this repo next to a
`_shelter_raw/` directory runs as written. They read `../../_shelter_raw` — a
sibling of the repo, which keeps the extracts outside git — and write to
`../results`.

## The source file

CSV or Excel, decided by the file extension.

**Gzipped CSVs need no setting.** pandas reads `.csv.gz` transparently, so
`source_file: "OC_raw.csv.gz"` works like the uncompressed name, and the
shipped configs use that form. A real extract is large enough to be worth
compressing. The run log's `source sha256` is a digest that fingerprints the
file; it is taken over the *uncompressed* contents, so compressing a file does
not change its recorded identity.

**Reading Excel needs `openpyxl`**, which is an optional dependency. Install
with `python3 -m pip install ".[excel]"` rather than a plain
`python3 -m pip install .`.

`sheet:` names the **Excel worksheet**. If it is omitted, the workbook must
contain exactly one sheet; otherwise the run stops and tells you how many it
found.

**CSVs are read as `utf-8-sig`.** The Orange County and Long Beach exports
carry a byte-order mark, which otherwise becomes part of the first column name
and makes every lookup on it fail.

Only the columns a run actually needs are read, which costs little: a wide
extract, which is the common case, is still read from disk, but only the needed
columns are built into the frame. When obtaining data, ask for as many columns
as are available, so that a later run can serve a new need without re-acquiring
the raw data.

## Columns

Five canonical fields must resolve to a column in the file: `animal_id`,
`intake_date`, `outcome_date`, `intake_type`, `outcome_type`. `dob` (date of
birth) is used when present and ignored when absent. Anything else a step or
`output_columns` names is assumed to exist in the file under that exact name;
if it does not, the run stops and the error lists what the file does contain.

`columns:` maps each canonical name to the one column in your file that carries
it, and the rename happens on the way in. Renaming outward as well would leave
two spellings of the same field in the frame at once, with different functions
reaching for different ones. The output keeps the canonical names.

## The study window

`window_start_date` and `window_end_date` are an optional pair — both or
neither. They do not filter anything by themselves. They build the
`window_presence` column, and an ordinary `cut:` step removes what you want
removed. The count lands in the statistics table like every other exclusion.

The rule is overlap, not intake date: a stay is `BEFORE` when it ended before
the window opened and `AFTER` when it began after the window closed. See
[derived columns](steps.md#derived-columns).

## age_groups and unique_report

`age_groups` maps a name to the upper cutoff of that band, in years at intake,
and builds `age_group`. Write the cutoffs as whole years: each one admits a
further day, so a round-year age falls in the same band whether or not its year
held a leap day. See [derived columns](steps.md#derived-columns).

`unique_report` names the identifier columns the statistics table counts
distinctly. Usually just `animal_id`, which gives every stage an animal count
alongside its row count.

## Dates

The package follows a simple rule on datetimes:

> Every date-valued thing here is a naive `datetime64`, from parse to write.

The stale pipeline mixed `datetime.date` with `datetime64`, and pandas 2
refuses to compare the two. The resolution is pandas's to choose — pandas 2
gives `[ns]`, pandas 3 infers `[us]` from strings — and nothing here depends
on which.

`keep_time: false` (the default) normalizes to midnight, effectively dropping
the time without changing the data type. `keep_time: true` preserves time
information. `nights` is computed from normalized values either way, so the
switch leaves a night count unchanged. Dates become `YYYY-MM-DD` strings at the
moment they are written.

**You state the datetime format.** Left to infer, pandas locks onto one format
from the first non-null value and silently coerces everything else to `NaT`:

```python
>>> s = pd.Series(["2018-01-01 14:30:00", "2018-03-02"])
>>> list(pd.to_datetime(s, errors="coerce"))
[Timestamp('2018-01-01 14:30:00'), NaT]
```

The second value is a perfectly ordinary date, and inference turns it into
`NaT`: pandas locked onto the first value's format, which carried a time. In a
real extract, it is a stay whose date has quietly gone blank, with nothing
printed to say so. Stating `ISO8601` accepts both spellings instead; `mixed`
also accepts US-style `m/d/Y`, at the cost of guessing on ambiguous days.
Whatever still fails to parse is **counted**, on its own `parse_dates` row in
the statistics table.

**A date that fails to parse becomes `NaT`**, which downstream is
indistinguishable from a **date absent altogether** — for `outcome_date` that
reads as "still in care". The `parse_dates` row of the statistics table catches
it. **Look at it before trusting a run.** A row in that state shows in the
frame as `outcome_type` set to something real while `night_sign` is
`_UNKNOWN_`; the stale pipeline repaired it by assuming the animal left the day
it arrived (`stale/_PhysicsSubs.py:28-30`). That repair was only a guess and
has no equivalent here, because a cut or a map cannot rewrite a date. Adding it
would take a new feature rather than a settings change.

What a settings file can do is mark the row, since a real outcome code with no
date is visible as `night_sign: _UNKNOWN_`. The shipped configs carry the step,
which relabels the outcome rather than letting it read as still in care:

```yaml
  - map: {outcome_type: {LCOM: _NODATE_, TRAN: _NODATE_, NONL: _NODATE_}}
    where: {night_sign: _UNKNOWN_}
```

It runs after the map to canonical codes, so the codes exist to match. What
happens to those rows then belongs to the analysis; mLOS discards them.

---

**See also:** [steps and derived columns](steps.md) ·
[preparing your own shelter data](getting-started.md) ·
[the prepared file](outputs.md) · [the statistics table](statistics-table.md)
