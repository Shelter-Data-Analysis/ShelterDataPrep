# Preparing your own shelter data

*For anyone arriving with an extract from a shelter this repository has never
seen. It assumes nothing except a CSV or Excel file and a working Python.*

[← ShelterDataPrep](../README.md)

Six steps; the third and fourth take the real thought.

## 1. Check that the install works

```bash
python3 -m pip install -r requirements.txt
python3 -m shelterprep configs/example_tiny.yaml
```

`configs/example_tiny.yaml` reads a 15-row fixture inside the repository, so it
runs on a fresh clone with no data of your own. It prints a statistics table
and writes four files into `results/`. If that worked, everything below is
editing.

Look at what it printed before moving on: it is the same table you will be
reading about your own data in step 6, at a size you can check by hand against
[tests/fixtures/tiny.csv](../tests/fixtures/tiny.csv).

## 2. Put your extract where a config can see it

Raw extracts stay outside the repository. They are public records that belong
in a deposit with their own DOI, and keeping them out of git makes that
possible later. The shipped configs expect a sibling directory:

```
your-projects/
├── _shelter_raw/            <- extracts live here, outside every repo
│   └── MY_raw.csv.gz
└── ShelterDataPrep/
    ├── configs/             <- your settings file goes here
    ├── results/             <- gitignored; runs write here
    └── shelterprep/
```

Nothing forces this layout, since `source_dir` can point anywhere. But this is
the layout `../../_shelter_raw` assumes in the shipped configs. It keeps a
config machine-independent, so a colleague with the same two directories runs
your config unchanged.

Gzip your extract if it is large. `MY_raw.csv.gz` needs no setting: pandas
reads it transparently, and the run log hashes the uncompressed contents, so
the recorded identity does not change.

## 3. Start from the nearest shipped config

Copy the one whose shelter most resembles yours, and edit it down. Copying is
helpful, because a blank file would miss the comments that explain *why* each
step exists.

A good candidate is one whose extract comes from the same shelter database as
yours — Chameleon, Shelterluv, and others. The initial shelter set, added in
2026, all read Chameleon exports, which is an accident of geography rather than
an endorsement, so the guideposts below key on the content of the raw file
instead of on the database behind it. Each config names its own on a
`# Shelter database:` line in its header.

| if your extract… | start from |
|---|---|
| is reasonably complete: dates, size, date of birth | `orange_county2.yaml` |
| has no date of birth and no size | `irvine_dogs.yaml` |
| covers several species | `irvine_all_species.yaml` |
| uses US-style `m/d/yy` dates | `irvine_all_species.yaml` |
| carries an offset or timezone on its dates | `la_county_dogs.yaml` |
| uses its own column names throughout | `mission_viejo.yaml` |
| you just want the smallest thing that runs | `example_tiny.yaml` |

Next, set the four paths at the top — `source_dir`, `source_file`, `dest_dir`,
`dest_file` — name your own database on the `# Shelter database:` line, and
delete the comments that describe someone else's shelter. They are specific,
and a config that keeps them claims something untrue about your data.

## 4. Name your columns

Five canonical fields have to resolve: `animal_id`, `intake_date`,
`outcome_date`, `intake_type`, `outcome_type`. `dob` is used when present.
`columns:` maps the canonical name to whatever your file calls it:

```yaml
columns:
  animal_id:    "Animal ID"
  intake_date:  "Intake Date"
  outcome_date: "Outcome Date"
  dob:          "DOB"
```

The fastest way through this is to run the config and let it fail. The error
lists every column your file *does* contain, which is usually easier than
opening a 70 MB extract to look:

```
error: tiny.csv does not have the column(s) this run needs:
  intake_date
the file has: Animal ID, Intake Date, Outcome Date, intake_type, ...
```

Set `output_columns` to what you want written, in the order you want it. Any
name there that is neither canonical nor derived is assumed to be a column in
your file under exactly that spelling.

Then set `date_format`. `ISO8601` covers `YYYY-MM-DD` with or without a time;
`mixed` also accepts US-style `m/d/Y`. The tool asks you to state it, for
[reasons the settings reference explains](settings.md#dates).

## 5. Say what to exclude

Exclusions are ordinary `cut:` steps: you can see each one, each lands in the
statistics table, and each can be quoted in a research paper's methods.
Out-of-window stays, impossible date orders, and animals with no recorded
outcome are all removed by steps you write.

Work from the inherited steps and change the values to your shelter's
vocabulary. Three habits are worth adopting from the start:

- **Order sometimes affects the content of the prepared file.** Re-mapping
  `X-LRG` to `LARGE` and then cutting on `LARGE` gives one result. Swap the two
  and you get another. Treat the steps as a sequence.
- **Order almost always affects the counts in the statistics table.** Cutting
  species first and the window second means the window's count is about dogs.
  Reversed, it is about everything. Both are defensible; only one matches the
  description you give in a report.
- **Leave retired values in the list,** if they existed before at this shelter
  or exist at similar ones. A value that matches nothing costs one row of zeros
  in the by-value breakdown, and it catches the label resurfacing in another
  year's extract.

The full grammar — `cut`, `map`, `dedup`, and the `where:` guards — is in
[steps and derived columns](steps.md). Look at the `dedup:` part before you
inherit one: it collapses only what is unambiguous, so **near-duplicate stays
reach your analysis intact**. The wider the set of `output_columns`, the
narrower the scope of deduplication, unless you name the columns in the
`dedup:` step yourself.

## 6. Run it, then read the statistics table

```bash
python3 -m shelterprep configs/my_shelter.yaml
```

Four files land in `results/`, and the statistics table also prints to the
console (`-q` suppresses that; the file is written either way). A run that
succeeds is not finished. You need to go through `<name>_stats.csv` and
confirm that the config says what you meant, and did it. Four checks, in
order:

1. **The `parse_dates` rows.** Any non-zero count is dates your `date_format`
   could not parse. They became blanks, and a blank `outcome_date` reads
   downstream as "still in care".
2. **The by-value breakdown, for zeros.** A value at zero is either a retired
   label you kept on purpose or a value you misspelled. That is a question for
   you to answer.
3. **`rows_out` at the end.** Against your own expectation of roughly how many
   stays this shelter has. If a step removed three times what you expected, you
   need to investigate.
4. **The summary table.** Check the shape of what survived. You know the
   shelter and its data, and can judge whether the result makes sense.

## The two failures that pass silently

Both are why the statistics table exists.

- **A step that affects 0 rows.** Often correct — a retired label kept as a
  safeguard — but also exactly what a misspelled value looks like. The by-value
  breakdown names every value at zero.
- **An unparseable date.** It becomes `NaT`, and for `outcome_date` that reads
  downstream as "still in care". The `parse_dates` row distinguishes the two.

The second one is live in the example config, if you want to see it: row `A013`
of [tests/fixtures/tiny.csv](../tests/fixtures/tiny.csv) has an outcome date of
`not a date` and an outcome type of `ADOPTION`. In `results/EX_data.csv` it
comes out with a real outcome type and a blank outcome date — an animal the
file now says was adopted but never left. The `parse_dates` line of the
statistics table carries a row that says this.

## When it stops

Error reporting is deliberate and names what is wrong. The common ones:

| message | what to do |
|---|---|
| `unknown setting(s) ...` | a misspelled top-level key. Rejected rather than ignored, because a typo that quietly skips an exclusion survives into a published table |
| `... does not have the column(s) this run needs` | the error lists what the file *does* contain; add a `columns:` entry mapping the canonical name to the file's spelling |
| `step N names the column X, which does not exist` | a step column that is neither in the file nor derived. If it is a derived one, the message says what building it needs |
| `has N sheets, so 'sheet:' is required` | name the sheet |
| `No module named 'openpyxl'` | an Excel source with a plain install. `python3 -m pip install ".[excel]"` |
| `N of M supplied value(s) unparseable` — in the statistics table, not an error | wrong `date_format`. Try `mixed` for US-style `m/d/Y` extracts |

## What this does not tell you

That your config is *correct* for your shelter. Nothing here can. A config is a
set of claims about someone's data, things like: `DISPO REQ` is an
administrative row; a blank outcome means still in care. Check these against
your knowledge of shelter recordkeeping, using the statistics table. Of the
configs shipped here, only one has been checked against a previous result. The
rest are best-approximation ports, and declare themselves that way.

---

**See also:** [the settings file](settings.md) ·
[steps and derived columns](steps.md) · [the statistics table](statistics-table.md) ·
[the prepared file](outputs.md) · [reproducibility](reproducibility.md)
