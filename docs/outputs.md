# The prepared file and the summary table

*For whoever receives a prepared CSV — which may well be someone who never runs
this tool. Everything here is about what the columns mean, not about how to
produce them.*

[← ShelterDataPrep](../README.md)

## The prepared file

`output_columns` decides which columns are written and in what order, so the
file is whatever a run asks for. What each of those columns *means* is fixed:

| column | type | values |
|---|---|---|
| `animal_id` | text | as in the source. Not unique — an animal with repeat stays has one row per stay |
| `intake_date` | `YYYY-MM-DD` | never blank; a row with no parseable intake date can still exist, and shows as blank |
| `outcome_date` | `YYYY-MM-DD` | **blank means the stay had not ended**, either still in care or never recorded |
| `intake_type` | text | the source vocabulary, as rewritten by the `map:` steps in the config |
| `outcome_type` | text | likewise. The shipped configs land on `LCOM` / `TRAN` / `NONL` / `INC` for mLOS |
| `animal_size`, `animal_type`, … | text | any other source column the config keeps, as rewritten |
| `nights`, `age` | number | whole nights, and years at intake. Blank where a date is missing |
| `night_sign` | text | `-1`, `0`, `1`, `_UNKNOWN_` |
| `window_presence` | text | `BEFORE`, `IN`, `AFTER`, `_UNKNOWN_` |
| `age_group` | text | the `age_groups` names, plus `_OVER_`, `_NEGATIVE_`, `_UNKNOWN_` |

Three conventions run through all of it:

- **`_UNKNOWN_` is the only missing-value marker in a text column.** Blank,
  whitespace, and absent all become it, before any step runs. A cut or a map can
  name it, and nothing downstream special-cases NaN.
- **A blank date is genuinely blank**, never `NaN` or `NaT` as text.
- **One row is one stay**, not one animal. `animal_id_distinct` in the summary
  is the animal count where you need it.

The observed levels of every categorical column, for a given run, are
enumerated in that run's summary file — so a reader can see the whole
vocabulary without opening the data.

How the derived columns are built is in [steps and derived
columns](steps.md#derived-columns); the date rules are in [the settings
file](settings.md#dates).

## The summary table

The ledger says what came out. `OC2_data_summary.csv` says what is left: every
exported categorical column crossed against intake type and outcome type, with
length of stay in each cell. It is a convenience for whoever gets the prepared
file, and nothing downstream depends on it.

```
      field     value intake_type outcome_type  margin   rows  animal_id_distinct  nights_known  nights_mean  nights_min  nights_p25  nights_median  nights_p75  nights_p90  nights_max
     _NONE_    _NONE_       STRAY         LCOM       0  19446               18586         19446        11.22           0         1.0            5.0         9.0        20.0         616
     _NONE_    _NONE_       STRAY         TRAN       0   4275                4272          4275        27.29           0         5.0           10.0        24.5        67.0         618
     _NONE_    _NONE_       STRAY        _ALL_       1  24832               23864         24696        14.19           0         1.0            5.0        11.0        28.0         618
     _NONE_    _NONE_       _ALL_        _ALL_       2  34718               28230         34513        15.40           0         1.0            5.0        12.0        33.0         730
animal_size     LARGE       STRAY         LCOM       0   6617                6144          6617        21.34           0         1.0            6.0        17.0        52.0         616
```

**Long, not rectangular.** A contingency table written as a grid needs a header
row *and* a header column, which one CSV cannot carry for several tables at
once and which neither pandas nor R reads back without being told how. One row
per cell, dimensions in named columns, goes straight into all three:

```python
cells = frame[(frame.field == "animal_size") & (frame.margin == 0)]
cells.pivot_table(index="value", columns="outcome_type", values="rows")
```

```r
cells <- subset(frame, field == "animal_size" & margin == 0)
xtabs(rows ~ value + outcome_type, data = cells)
```

and in a spreadsheet it is already a pivot table's source range.

**Which tables are there.** One per exported categorical column — a third
dimension crossed against the two type axes — plus the degenerate one that
crosses the axes against each other, marked `field = _NONE_`. Dates, numbers,
and the `unique_report` identifiers are not categories and are skipped, as is
any column with more than 50 distinct values. A run whose output columns are
just IDs, dates, and the two types gets the `_NONE_` table alone.

**Partial sums** are in the same table, marked `_ALL_` in the dimension they
collapse. `margin` counts how many of the two axes are collapsed, so:

- `margin == 0` — the cells. **Filter on this before summing anything.**
- `margin == 1` — one axis totaled: rows per intake type, or per outcome type.
- `margin == 2` — both, i.e. the total for that field level (or the grand total
  in the `_NONE_` table).

Sums over a field are not repeated per field, because they are exactly the
`_NONE_` table. So every number appears once, and the `margin == 2` rows of any
field table add up to the `margin == 2` row of `_NONE_`.

**The measures**, per cell, are the frequency and the one descriptive that
matters for a length-of-stay study:

| column | |
|---|---|
| `rows` | stays in the cell |
| `animal_id_distinct` | distinct animals — one per `unique_report` field; below `rows` where an animal has repeat stays |
| `nights_known` | stays with a night count; `rows` minus this is the stays still in care |
| `nights_min`, `nights_max` | shortest and longest stay, as whole nights |
| `nights_mean`, `nights_p25`, `nights_median`, `nights_p75`, `nights_p90` | the distribution over the known ones. `p90` because mLOS leans on it; the quartiles because a length of stay is skewed enough that the extremes alone mislead |

`nights` counts nights, not days — an animal in and out the same day scores 0,
and mLOS defines `LOS = nights + 1`. A cell with `rows` but no `nights_known`
is entirely still in care, and its night columns are blank rather than zero.

The run log carries the one fact this table cannot, since it counts stays
rather than dates: the span the surviving rows actually cover.

---

**See also:** [the statistics table](statistics-table.md) ·
[the settings file](settings.md) · [steps](steps.md) ·
[reproducibility](reproducibility.md)
