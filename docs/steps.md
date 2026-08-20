# Steps and derived columns

*For anyone expressing inclusion criteria as a config: the step grammar, the
columns the tool builds for you to filter on, and how blanks behave.*

[← ShelterDataPrep](../README.md)

## Steps

The sequence is ordered and each entry is a cut, a map, or a dedup.

- **`cut:`** drops matching rows, and multiple columns must all match.
- **`map:`** rewrites values in exactly one column. `where:` / `where_not:`
  restrict which rows it applies to; both take several columns at once, and
  `where_not` negates the whole conjunction.
- **`dedup:`** keeps the **last** of each group of rows matching across the
  listed columns — or across every output column if none are listed — and cuts
  the earlier ones. Takes `where:` / `where_not:` like a map.

A scalar is accepted anywhere a set is meant (`intake_cond: DEAD` is
`[DEAD]`). Values compare as text, so `night_sign: "-1"` matches.

Two restrictions are deliberate: a cut takes no `where:` (add the column to the
cut, which already requires every column to match), and a map takes one column
(a statistics row describing two columns at once is ambiguous — use two steps).

A step whose count comes out zero still earns its place: it catches a
misspelled label, so retired values are worth leaving in the list.

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
pairs *disagree with each other* about the outcome. Those are a judgment call,
and they belong to the downstream analysis, which has its own duplicate-stay
and overlapping-stay screens.

So the `where:` clause carries the weight: without it, this step would collapse
pairs that may be two genuine visits.

Which row survives matters only when the compared columns are a **subset**, so
two matching rows can still differ elsewhere. There the **last** row is kept,
on the reading that a later record corrects an earlier one rather than the
reverse — which is also how mLOS breaks the same tie ("of two equal stays, the
one earlier in the file is dropped").

## Derived columns

Built after the dates are parsed and before any step runs, so they filter and
map like columns that came out of the file.

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
animal still in care — no outcome date — stays `IN`. It has not left.

**Filtering happens in the steps you write.** Over-age animals, impossible date
orders, and out-of-window stays are removed by ordinary `cut:` steps in the
settings file, so each lands in the statistics table like every other
exclusion.

`nights` is nights, not length of stay. mLOS defines `LOS = nights + 1` and
derives it from the two dates itself.

## Blanks

Every non-date value is text, and blank, whitespace-only, and missing all become
`_UNKNOWN_` — the same sentinel mLOS uses. Because it is an ordinary value, a
cut or a map can name it, and downstream code can treat it like any other
value.

---

**See also:** [the settings file](settings.md) ·
[preparing your own shelter data](getting-started.md) ·
[the statistics table](statistics-table.md) · [the prepared file](outputs.md)
