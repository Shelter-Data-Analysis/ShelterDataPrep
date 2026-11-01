# Known problems in source files

Problems found in real extracts that ShelterDataPrep does not yet handle, each
with what it does to a run, the workaround, and the fix it needs. An entry
leaves this page when a release handles the problem; the changelog then says
so.

A problem found in a new extract is added here, with the file it was found in.

## Excel 97-2003 workbooks (`.xls`)

**Not yet found in an extract.** `.xls` is among the extensions read as Excel,
but pandas reads that format with `xlrd`, which the `excel` extra does not
install.

**Effect.** The run stops with pandas' message that `xlrd` is missing.

**Workaround.** Save the workbook as `.xlsx` or as CSV, or install `xlrd`.

**Fix needed.** Either add `xlrd` to the `excel` extra, or drop `.xls` from
the Excel extensions and say in the error that the file should be saved as
`.xlsx`.
