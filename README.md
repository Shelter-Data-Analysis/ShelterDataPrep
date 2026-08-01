# ShelterDataPrep

Turns a raw animal shelter extract (CSV or Excel) into a tidy CSV, plus a
statistics table recording exactly what every step removed or changed.

A run is one YAML settings file:

```bash
python -m shelterprep configs/orange_county.yaml
```

Three files come out, next to each other in `results/`:

| file | contents |
|---|---|
| `OC_data.csv` | the prepared data |
| `OC_data_stats.csv` | the processing ledger: one row per stage, then one row per value each step names |
| `OC_data_run.txt` | provenance: source path, SHA-256, versions, timestamp |

`results/` is gitignored, and a run writes nowhere else. Handing a prepared
file to the downstream analysis is a copy you make deliberately, not something
that happens because you re-ran the prep.

Or from Python, if you want to poke at an intermediate stage:

```python
from shelterprep import load, Prep

prep = Prep(load("configs/orange_county.yaml"))
prep.read().derive()          # frame now has nights, age_group, window_presence
prep.apply_steps().write()
prep.statistics.frame()       # the stage ledger as a DataFrame
prep.statistics.details()     # the by-value breakdown, on its own
prep.statistics.report()      # both, stacked -- what gets written to the CSV
```

## Configs

| config | shelter | rows out | notes |
|---|---|---|---|
| `orange_county.yaml` | Orange County, dogs | 36,564 | validated against the previous `OC_data.csv` |
| `orange_county2.yaml` | Orange County, dogs | 34,718 | supersedes the above; new outcome codes, `age_group` exported |
| `irvine_dogs.yaml` | Irvine, dogs | 11,022 | no dob, no size — no `animal_group` |
| `irvine_all_species.yaml` | Irvine, all species | 20,690 | US `m/d/yy` dates; `animal_type` is the stratifier |
| `long_beach.yaml` | Long Beach, dogs | 12,183 | no size; `age_group` is the stratifier |
| `mission_viejo.yaml` | Mission Viejo, dogs | 4,661 | its own column names throughout |
| `la_county_dogs.yaml` | LA County, dogs | 97,990 | offset-stamped dates; large blank-outcome share |
| `la_county_cats.yaml` | LA County, cats | 76,402 | same file and maps as the dogs config |

Only the Orange County config has been checked against a known-good result.
**The other six are best-approximation ports of the modules in `stale/` and
have not been validated against anything** — read their statistics tables
before trusting a run. Places where a judgement was made, or where the old
code had a bug worth knowing about, are commented in the config itself.

## The settings file

```yaml
source_dir:   "../../_shelter_raw"
source_file:  "intakes and outcomes.csv"
sheet:                       # Excel only; omit and the file must have one sheet
date_format:  ISO8601        # or: mixed  (US-style m/d/Y extracts)
keep_time:    false

window_start_date: 2018-07-01   # optional pair, both or neither
window_end_date:   2024-10-19

dest_dir:   "../results"
dest_file:  "OC_data.csv"
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

### Paths

`source_dir` and `dest_dir` are relative, and resolve against the settings file
rather than the working directory, so a run means the same thing from anywhere.
Nothing in `configs/` names a home directory or a machine, so a clone of this
repo next to a `_shelter_raw/` directory runs as written.

The shipped configs read `../../_shelter_raw` — a sibling of the repo, so the
extracts can never be committed — and write to `../results`.

### Columns

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

Only the columns a run actually needs are read, which keeps a 70 MB extract
cheap.

### Steps

The sequence is ordered and each entry is a cut, a map or a dedup.

- **`cut:`** drops matching rows. Multiple columns are ANDed. Always a cut,
  never a pass.
- **`map:`** rewrites values in exactly one column. `where:` / `where_not:`
  restrict which rows it applies to; both are ANDs of columns, and `where_not`
  negates the whole conjunction.
- **`dedup:`** keeps the **last** of each group of rows matching across the
  listed columns — or across every output column if none are listed — and cuts
  the earlier ones. Takes `where:` / `where_not:` like a map.

A scalar is accepted anywhere a set is meant (`intake_cond: DEAD` is
`[DEAD]`). Values compare as text, so `night_sign: "-1"` matches.

Two restrictions are deliberate: a cut takes no `where:` (add the column to the
cut, which already ANDs), and a map takes one column (a statistics row
describing two columns at once cannot be read unambiguously — use two steps).

A step whose count comes out zero is not dead weight. It is how a misspelled
label gets caught, so retired values are worth leaving in place.

### Deduplication is deliberately narrow

```yaml
  - dedup:                      # compare every output column
    where: {night_sign: "1"}    # only stays of at least one night
```

Two rows identical in every output column covering a stay of **at least one
night** cannot both be real: an animal cannot be admitted twice on the same day
for the same multi-day stay. Those are safe to collapse.

A **same-day** repeat is a different matter — in and out in the morning, in and
out again in the afternoon is physically possible. In the Orange County extract
that intuition is borne out: of the 29 stays recorded twice, 19 of the 20
multi-day pairs are identical (plain duplication), while 7 of the 9 same-day
pairs *disagree with each other* about the outcome. Those are a judgement call,
and they belong to the downstream analysis, which has its own duplicate-stay
and overlapping-stay screens.

So the `where:` clause is not a detail. Without it this step would collapse
pairs that may be two genuine visits.

Which row survives matters only when the compared columns are a **subset**, so
two matching rows can still differ elsewhere. There the **last** row is kept,
on the reading that a later record corrects an earlier one rather than the
reverse — which is also how mLOS breaks the same tie ("of two equal stays, the
one earlier in the file is dropped").

### Derived columns

Built after the dates are parsed and before any step runs, so they filter and
map exactly like columns that came out of the file.

| column | |
|---|---|
| `nights` | `outcome_date - intake_date`, in whole nights |
| `night_sign` | `-1`, `0`, `1`, or `_UNKNOWN_` |
| `window_presence` | `BEFORE`, `IN`, `AFTER`, or `_UNKNOWN_` |
| `age` | years at intake, from `dob` |
| `age_group` | per `age_groups`, plus `_OVER_`, `_NEGATIVE_`, `_UNKNOWN_` |

Age cutoffs fall in the **lower** group: with `JUVENILE: 1`, an age of exactly
1 is JUVENILE. Above the last cutoff is `_OVER_`; a `dob` after the intake date
is `_NEGATIVE_` (a data error, kept distinct from a missing `dob`, which is
`_UNKNOWN_`).

`window_presence` is `AFTER` when the animal arrived after the window closed
and `BEFORE` when it left before the window opened. `IN` is the default, so an
animal still in care — no outcome date — is never `BEFORE`. It has not left.

**Nothing is filtered automatically.** Over-age animals, impossible date
orders and out-of-window stays are all removed by ordinary `cut:` steps you
can see in the settings file, so each lands in the statistics table like
everything else.

`nights` is nights, not length of stay. mLOS defines `LOS = nights + 1` and
derives it from the two dates itself.

### Blanks

Every non-date value is text, and blank, whitespace-only and missing all become
`_UNKNOWN_` — the same sentinel mLOS uses. Because it is an ordinary value, a
cut or a map can name it and nothing downstream has to special-case NaN.

## Dates

One rule, and the reason this package exists:

> Every date-valued thing here is `datetime64[ns]`. Never `datetime.date`,
> never a mix.

`keep_time: false` (the default) normalises to midnight — the time is dropped,
the dtype is not. `keep_time: true` preserves it. `nights` is computed from
normalised values either way, so the switch can never shift a night count.
Dates become `YYYY-MM-DD` strings only at the moment they are written.

Two things worth knowing about the parsing:

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

**CSVs are read as `utf-8-sig`.** The Orange County and Long Beach exports
carry a byte-order mark, which otherwise becomes part of the first column name
and makes every lookup on it fail.

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

## The statistics table

One row per stage, in execution order — the shape of a CONSORT flow diagram, so
it can go into a supplement more or less as is. Reading, date parsing and the
derived columns get rows too, so the chain of counts is continuous and a gap is
visible rather than inferred.

```
 step     action        column  rows_in  rows_affected  rows_out  animal_id_in  animal_id_out
    0       read           ...   192149              0    192149        105396         105396
    1        cut   animal_type   192149         147385     44764        105396          33402
    2        cut  ...
```

For each field in `unique_report` there is an `_in` / `_affected` / `_out`
triple. `_in` minus `_out` is the number of animals that left the study
*entirely* at that stage.

Every step computes its mask, records the statistics, and only then applies the
change, so the numbers describe the frame the step actually saw.

### The by-value breakdown

Underneath the stage table, in the same file, sits a second one at a finer
grain: **one row per value the settings name**, counted within the rows that
step actually cut or mapped. A `section` column selects between them, and each
section leaves the other's columns blank, so the file is still one CSV that
`pd.read_csv` opens.

```
 step action       column     role      value        scope  rows_affected  animal_id_affected
    1    cut  animal_type      cut       BIRD     rows cut          16493               16421
    1    cut  animal_type      cut        CAT     rows cut          87403               64096
    1    cut  animal_type      cut  LIVESTOCK     rows cut            113                 110
    1    cut  animal_type      cut      OTHER     rows cut          43376               42887
    3    cut  intake_type      cut  DISPO REQ     rows cut           1815                1814
    3    cut  intake_type      cut      FOUND     rows cut              0                   0
```

This exists mostly for the zeros. Settings files deliberately keep values that
no longer occur, so that a label reappearing in a future extract is caught
rather than passed through — and a summary of what *did* happen is exactly the
report that cannot show them. `FOUND` above is one: named in the cut, matching
nothing, and now visibly so.

Two things to read carefully:

- **`role`** says which part of the step the value came from: `cut`, `map from`
  (a key of the map table), `where` or `where_not`.
- **`scope`** says what the count is over. For everything except `where_not`
  that is the rows the step cut or mapped. A `where_not` value cannot appear in
  a row the step touched — keeping it out is what the guard did — so those are
  counted over the rows the guard **held back** instead, which is the number
  that says whether it fired.

A conjunction is broken down one part at a time, not by combination. For
`cut: {animal_type: [CAT, DOG], intake_type: DISPO REQ}` you get counts for
`animal_type` and counts for `intake_type` over the same set of cut rows. Since
a row holds one value per column, the counts within a column add up to the
stage's `rows_affected` — a column that does not add up is one whose value set
is missing something.

`dedup` breaks down only its `where` / `where_not` guards: `on:` names columns,
not values, so there is no set to split.

## Scope

Preparation only: read, derive, filter and map, write. The weekly-cumulative
"physics" (`getCumulative`, `AnimDays`, the 17-week differencing) stays in
`stale/`, unported. `stale/` is kept for reference and does not run under
pandas 2.

## Tests

```bash
python -m pytest tests/ -q
```
