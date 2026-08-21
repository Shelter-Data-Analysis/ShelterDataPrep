# The statistics table

*For anyone reading a `<name>_stats.csv`, and for anyone writing one. This is
the format ShelterDataPrep shares with mLOS, so it is a contract between the
two.*

[← ShelterDataPrep](../README.md)

One row per stage, in execution order — the shape of a CONSORT flow diagram, so
it can go into a supplement more or less as is. Reading, date parsing, and
column derivation also get rows, so the chain of counts is continuous and a
gap is visible. On the OC2 run:

```
 step     action        column  rows_in  rows_affected  rows_out  animal_id_in  animal_id_out
    0       read           ...   192149              0    192149        160819         160819
    1        cut   animal_type   192149         147385     44764        160819          37305
    2        cut  ...
```

For each field in `unique_report` there is an `_in` / `_affected` / `_out`
triple. `animal_id_in` minus `animal_id_out` is the number of animals that left
the study *entirely* at that stage.

Every step computes its mask, records the statistics, and only then applies the
change, so the numbers describe the frame the step actually saw.

## The by-value breakdown

Underneath the stage table, in the same file, sits a second one at a finer
grain: **one row per value the settings name**, counted within the rows that
step actually cut or mapped. A `section` column selects between them, and each
section leaves the other's columns blank, so the file is still one CSV that
`pd.read_csv` opens. Again on OC2:

```
 step action       column     role      value        scope  rows_affected  animal_id_affected
    1    cut  animal_type      cut       BIRD     rows cut          16493               16421
    1    cut  animal_type      cut        CAT     rows cut          87403               64096
    1    cut  animal_type      cut  LIVESTOCK     rows cut            113                 110
    1    cut  animal_type      cut      OTHER     rows cut          43376               42887
    3    cut  intake_type      cut  DISPO REQ     rows cut           1815                1814
    3    cut  intake_type      cut      FOUND     rows cut              0                   0
```

This exists mostly for the zeros. Settings files may deliberately keep values
that no longer occur, so that a label reappearing in a future extract is caught
rather than passed through, and such carryovers appear here with zero hits.
`FOUND` above is one: named in the cut, matching nothing, its effect (or lack
of one) visible.

Two things to read carefully:

- **`role`** says which part of the step the value came from: `cut`, `map from`
  (a key of the map table), `where`, or `where_not`.
- **`scope`** says what the count is over, and names the step that produced
  it: `rows cut`, `rows mapped`, `rows dropped` for a dedup, or `rows excluded
  by where_not`. That last one is counted differently: a `where_not` value
  cannot appear in a row the step touched — the guard kept it out — so those
  are counted over the rows the guard **held back**, the number that says
  whether it fired.

A conjunction is broken down one part at a time, not by combination. For
`cut: {animal_type: [CAT, DOG], intake_type: DISPO REQ}` you get counts for
`animal_type` and counts for `intake_type` over the same set of cut rows. Since
a row holds one value per column, the counts within a column add up to the
scope they are counted over.

`dedup` breaks down only its `where` / `where_not` guards. Its own argument
names columns, not values, so there is no set to split.

## Other tools writing this table

The format is shared. mLOS, the length-of-stay analysis tool downstream,
records its own screening in the same column form, so the two files stack,
giving you a single flow from the raw extract to the rows the models ran on.
The chain joins at the handoff, because
the `write` row here and mLOS's `read` row are the same frame counted twice.

Two things to expect from a file this project did not write.

- **The vocabularies are open.** `action` and `role` are documented above as
  what *this* tool emits, not as the closed set. A conforming tool may add
  verbs for stages that do not arise in preparation. mLOS adds `split`, for
  breaking a stay into the periods it is observed in, and `pass`, for a
  keep-only filter, whose named values are counted over the rows it kept rather
  than the rows it cut.
- **`rows_out` may exceed `rows_in`.** Preparation removes rows, so a stage
  here narrows or holds, and it is tempting to take that as a property of the
  format. An analysis stage can multiply rows, which is what mLOS does with
  `split`.

The columns are the contract; what a writer puts in them is its own business.
An extra column would break the concatenation. That is why mLOS keeps its
internal stage names out of the file and identifies a stage the way this one
does, by `action`, `column`, and `detail`.

---

**See also:** [the prepared file and the summary table](outputs.md) ·
[the settings file](settings.md) · [steps](steps.md) ·
[reproducibility](reproducibility.md)
