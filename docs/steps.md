# Steps and derived columns

*For anyone expressing inclusion criteria as a config: the step grammar, the
columns the tool builds for you to filter on, and how blanks behave.*

[← ShelterDataPrep](../README.md)

## Steps

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

## Deduplication is deliberately narrow

`dedup:` takes a list of columns to compare, or nothing at all, which means
every output column:

```yaml
  - dedup: [animal_id, intake_date, outcome_date]
    where: {night_sign: "1"}
```

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

## Derived columns

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

## Blanks

Every non-date value is text, and blank, whitespace-only and missing all become
`_UNKNOWN_` — the same sentinel mLOS uses. Because it is an ordinary value, a
cut or a map can name it and nothing downstream has to special-case NaN.

---

**See also:** [the settings file](settings.md) ·
[preparing your own shelter data](getting-started.md) ·
[the statistics table](statistics-table.md) · [the prepared file](outputs.md)
