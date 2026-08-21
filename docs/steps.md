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

Two restrictions are deliberate:

- A cut takes no `where:`. Add the column to the cut instead, which already
  requires every column to match.
- A map applies only to one column. To modify multiple columns, use a separate
  step for each one. The reason for this design choice is that the statistics
  describing two columns at once would be confusing.

A step whose count comes out zero is still worth keeping: it catches a
misspelled label, so retired values are often worth keeping in steps.

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
out again in the afternoon is physically possible. On the OC1 run that
intuition is borne out: of the 29 stays recorded twice, 19 of the 20 multi-day
pairs are identical (plain duplication), while 7 of the 9 same-day pairs
*disagree with each other* about the outcome. These could be improper
corrections or real multiple stays. It is a judgment call to make deliberately.
So the `where:` clause matters. Without it, this step would collapse pairs that
may be two genuine visits.

The bare form is tied to `output_columns`, so **widening the output has the
side effect of narrowing the step.** Each column added is one more that two
rows have to agree on before either is dropped. The explicit list decouples the
two: the `[animal_id, intake_date, outcome_date]` example above treats two
multi-day stays as one whenever the animal and both dates agree, regardless of
outcome type, animal size, or anything else. Either form costs little on the
shipped extracts: the wider one drops one further row on each of OC1, OC2, and
Long Beach, and none elsewhere. What the config does not handle falls to the
consumer of the prepared file.

**What the step leaves for the analysis.** Same-day repeats, overlapping stays,
and rows that agree on the animal and both dates while disagreeing in any other
output column all survive by design, because settling them means knowing what
the analysis counts. The disagreement can be the outcome type, the intake type,
the size, or anything else the config exports. An analysis that treats a stay
as a unit wants a screen of its own, which is where mLOS keeps its
duplicate-stay and overlapping-stay screens.

Which row in a matching set survives matters only when the compared columns are
a **subset**, which allows matching rows to still differ elsewhere. There the
**last** row is kept,
on the reading that a later record corrects an earlier one rather than the
reverse — which is also how mLOS breaks the same tie ("of two equal stays, the
one earlier in the file is dropped").

## Derived columns

Built after the dates are parsed and before any step runs, so they filter and
map like columns that came out of the file.

| column | meaning |
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

`window_presence` is `AFTER` if the animal arrived after the window closed and
`BEFORE` if it left before the window opened. An animal still in care has no
outcome date: it cannot pass the `BEFORE` test, and it is either `AFTER` or
`IN` depending solely on its intake date. A row with no parseable *intake* date
is `_UNKNOWN_`: it cannot be placed against the window at all, and every
shipped config cuts it there.

**Filtering is not hidden in code; it happens in the steps you write.**
Over-age animals, impossible date orders, and out-of-window stays are removed
by ordinary `cut:` steps in the settings file, so each lands in the statistics
table like every other exclusion.

`nights` is nights, not length of stay. mLOS defines `LOS = nights + 1` and
derives it from the two dates itself.

## Blanks

Every non-date value is text. Blank, whitespace-only, and missing all become
`_UNKNOWN_` — the same sentinel mLOS uses. Because it is an ordinary value, a
cut or a map can name it, and downstream code can treat it like any other
value.

---

**See also:** [the settings file](settings.md) ·
[preparing your own shelter data](getting-started.md) ·
[the statistics table](statistics-table.md) · [the prepared file](outputs.md)
