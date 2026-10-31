# Known problems in source files

Problems found in real extracts that ShelterDataPrep does not yet handle, each
with what it does to a run, the workaround, and the fix it needs. An entry
leaves this page when a release handles the problem; the changelog then says
so.

A problem found in a new extract is added here, with the file it was found in.
Numbers quoted are for that file, read by ShelterDataPrep 0.5.0 at commit
`9daa223` with the dog configuration mLOS Web writes for it (study window
2010-03-01 to 2025-10-01).

## A heading merged across columns names an empty column

**Found in** `Irvine 20251008 Attachment A.xlsx`, the Irvine Animal Care Center
extract of 2025-10-08.

In row 1, `intake_time` is a cell merged across columns AB to AD, and
`outcome_date` one merged across AL and AM. Excel keeps a merged cell's text in
its leftmost column, but the values sit in another column of the span: AC for
`intake_time`, AM for `outcome_date`. pandas, reading the header, gives the
heading to the empty column and names the column of values by its position,
`Unnamed: 28` and `Unnamed: 38`.

**Effect.** A run that maps `outcome_date` to the file's `outcome_date` column
reads an empty column without an error. In this file every outcome date is
blank, so `night_sign` is `_UNKNOWN_` for every row and every outcome becomes
`_NODATE_`: none of the 7,271 dog stays prepared has an outcome date.

**Workaround.** Either map the heading to the column of values,

```yaml
columns:
  outcome_date: "Unnamed: 38"
```

which breaks as soon as a later extract adds or drops a column before it, or
unmerge the headings in Excel and type each over its column of values. Saving
the workbook as CSV does not help: the CSV carries the heading over the empty
column, as pandas reads it.

**Fix needed.** The Excel reader reads the merged ranges of row 1 from the
worksheet. Where a heading's own column is empty and exactly one unnamed column
of its span holds values, that column takes the heading's name, and the run
log records the move. mLOS Web applies this rule today, writing the
`Unnamed: 38` mapping into the configuration it produces; it would then write
none.

## A font family above 14 stops the run

**Found in** `Irvine 20251008 Attachment A.xlsx`.

The workbook's style table gives two fonts `<family val="16"/>`. Excel writes
and reads it; openpyxl 3.1.5 accepts 0 to 14 only, and refuses the whole
workbook.

**Effect.** The run stops before reading any row, with openpyxl's message
"Unable to read workbook: could not read stylesheet", which names neither the
font nor a remedy.

**Workaround.** Save the sheet as CSV, which carries no style table. For this
file, the CSV then has the merged-heading problem above.

**Fix needed.** A font's family affects only how text is drawn. When openpyxl
refuses the style table, the reader drops the out-of-range `<family>` entries
from a copy of the workbook, reads the copy, and says so in the run log; the
source digest stays that of the original. mLOS Web does this today.

## A blank spacer row is counted as a stay

**Found in** `Irvine 20251008 Attachment A.xlsx`, whose row 2 is a thin empty
row between the headings and the data.

**Effect.** The row is read as a stay with no values. It is among the 21,071
rows read, although the sheet holds 21,070 stays, and the study-window cut,
step 1 of the configuration, removes it as one of its 15 rows: the one counted
under `_UNKNOWN_`, the other 14 being `AFTER`. No prepared row comes from it,
but the statistics table reports it as a stay whose window presence is
unknown rather than as a blank row.

**Workaround.** None needed for the prepared file. Delete the row in Excel for
a statistics table that counts stays only.

**Fix needed.** The reader drops rows in which every column it reads is blank,
and the statistics table counts them on a row of their own at step 0.

## Column names below row 1

**Not yet found in an extract.** The reader takes the column names from row 1
of a CSV or a sheet, and no setting names another row.

**Effect.** A sheet with a title or a blank row above the headings is read
with names such as `Unnamed: 0`, and the run stops because the columns the
configuration names are missing.

**Workaround.** Delete the rows above the headings.

**Fix needed**, if an extract needs it: a `header_row:` setting, or a reader
that finds the first non-blank row.

## Excel 97-2003 workbooks (`.xls`)

**Not yet found in an extract.** `.xls` is among the extensions read as Excel,
but pandas reads that format with `xlrd`, which the `excel` extra does not
install.

**Effect.** The run stops with pandas' message that `xlrd` is missing.

**Workaround.** Save the workbook as `.xlsx` or as CSV, or install `xlrd`.

**Fix needed.** Either add `xlrd` to the `excel` extra, or drop `.xls` from
the Excel extensions and say in the error that the file should be saved as
`.xlsx`.
