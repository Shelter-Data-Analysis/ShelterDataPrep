# Stacking extracts

`tools/stack_extracts.py` joins several extracts of one shelter, such as one
file per year, into one file that a settings file can name as its source. It
is not part of the installed package, and the run log of a main run does not
mention it, so the stacking log belongs in the deposit beside the stacked
file.

```bash
python3 tools/stack_extracts.py stacked.xlsx 2014.xls 2015.xls 2016.xls --key "Impound Number"
```

List the inputs oldest first. Each may be CSV or Excel; reading .xls needs
the `xlrd` package, and .xlsx needs `openpyxl`. The output is .xlsx or .csv,
chosen by its suffix. A log, `stacked_stack_log.txt` in this example, is
written beside it and printed.

## What the tool checks

- **Header rows.** A file whose first row holds the key column's name has a
  header row. A file without one takes the column names of the first file
  that has one, if it has the same number of columns, and the log names each
  such file. If no file has a header row, or a file without one has a
  different number of columns, nothing is written.
- **Fields.** The log lists, for each file, the columns it lacks or adds
  relative to the first file, and a change in column order. Columns are
  stacked by name, and a file that lacks a column contributes blanks to it.
- **Repeated records.** The key column identifies a record, usually one stay.
  A key found more than once, in one file or across files, is kept once.
  Copies that agree in every column collapse. Copies that disagree are
  listed in the log with the columns that differ, and the copy from the file
  listed last is kept. Rows with a blank key are all kept and counted.

A last column, `Source Files`, names every input in which a kept row was
found. `--no-source` leaves it out.

## What the tool does not check

The tool does not know which records each extract was meant to hold, so it
cannot see a record that is missing from every file. A year-by-year extract
whose report selects stays by intake year alone, for example, loses an
outcome entered after the extract was pulled, and stacking does not recover
it. Comparing each file's intake and outcome dates against its year, before
stacking, shows which rule the extracts followed.
