# ShelterDataPrep

Turns a raw animal shelter extract (CSV, gzipped CSV, or Excel) into a tidy CSV,
plus a statistics table recording what each step removed or changed.

A run is one YAML settings file:

```bash
python3 -m shelterprep configs/example_tiny.yaml
```

That one reads a 15-row fixture inside the repository, so it works on a fresh
clone with no data of your own. A real run names a real config:

```bash
python3 -m shelterprep configs/orange_county2.yaml
```

Four files come out, next to each other in `results/`:

| file | contents |
|---|---|
| `OC2_data.csv` | the prepared data |
| `OC2_data_stats.csv` | the processing ledger: one row per stage, then one row per value each step names |
| `OC2_data_summary.csv` | descriptive statistics of the finished set: joint frequencies and length of stay |
| `OC2_data_run.txt` | provenance: source path, SHA-256, versions, timestamp |

`results/` is gitignored. Handing a prepared file to the downstream analysis
is a copy you make deliberately, so re-running the prep leaves that copy as it
was.

`-q` suppresses the console table; the files are written either way. Installing
the package also puts a `shelterprep` command on your path, so
`shelterprep configs/orange_county2.yaml` does the same thing from anywhere.

## Installing

Python 3.9 or newer.

```bash
pip install -r requirements.txt
python3 -m shelterprep configs/example_tiny.yaml
```

Run from the repository root, where `configs/` and `shelterprep/` live. Or
install it properly, so `shelterprep` works from anywhere:

```bash
pip install .
```

Add the `excel` extra if your extract is a workbook — a plain `pip install .`
leaves out `openpyxl`, and an Excel source will fail without it:

```bash
pip install ".[excel]"
```

Everything else is pandas and PyYAML; `pytest` runs the tests. The run log
records the version of each, because reproducing a result means stating the
environment it ran in.

## Documentation

| document | read it when |
|---|---|
| [Preparing your own shelter data](docs/getting-started.md) | you have an extract from a shelter not listed below, and need a config for it |
| [The settings file](docs/settings.md) | every top-level key, the path rules, and how dates are handled |
| [Steps and derived columns](docs/steps.md) | the `cut` / `map` / `dedup` grammar, and the columns the tool builds for you to filter on |
| [The prepared file and the summary table](docs/outputs.md) | you have been handed a prepared CSV and need to know what its columns mean |
| [The statistics table](docs/statistics-table.md) | the ledger format — shared with mLOS, so the two files stack into one flow |
| [Reproducibility and publishing](docs/reproducibility.md) | the run log, the digests, and what travels with a file into a paper |

[CONTRIBUTING.md](CONTRIBUTING.md) covers what to do with data you have
prepared — deposit the extract, the settings, and the result together, and cite
the version you actually ran. [CHANGELOG.md](CHANGELOG.md) records what changed
between versions, and flags anything that could move a number.

## The shipped configs

| config | shelter | rows out | notes |
|---|---|---|---|
| `example_tiny.yaml` | none — the test fixture | 11 | runs on a clean clone; the starting point to copy |
| `orange_county2.yaml` | Orange County, dogs | 34,718 | the mLOS default; new outcome codes, `age_group` exported |
| `orange_county1.yaml` | Orange County, dogs | 36,564 | superseded by the above, frozen and kept as a baseline |
| `irvine_dogs.yaml` | Irvine, dogs | 11,022 | no dob, no size — no `animal_group` |
| `irvine_all_species.yaml` | Irvine, all species | 20,690 | US `m/d/yy` dates; `animal_type` is the stratifier |
| `long_beach.yaml` | Long Beach, dogs | 12,183 | no size; `age_group` is the stratifier |
| `mission_viejo.yaml` | Mission Viejo, dogs | 4,661 | its own column names throughout |
| `la_county_dogs.yaml` | LA County, dogs | 97,990 | offset-stamped dates; large blank-outcome share |
| `la_county_cats.yaml` | LA County, cats | 76,402 | same file and maps as the dogs config |

`orange_county1.yaml` has been checked against a known-good result.
`orange_county2.yaml` is a deliberate revision of it, reviewed against its own
statistics table and the analysis it feeds. **The rest are best-approximation
ports of the modules in `stale/` and have not been validated against
anything** — go through their statistics tables before trusting a run. Places
where a judgment was made, or where the old code had a bug worth knowing
about, are commented in the config itself.

Every config except `example_tiny.yaml` reads an extract we cannot
distribute, so running one means [supplying the file
yourself](docs/getting-started.md#2-put-your-extract-where-a-config-can-see-it).

## The statistics table

One row per stage, in execution order — the shape of a CONSORT flow diagram, so
it can go into a supplement more or less as is. Underneath it, in the same
file, one row per value the settings name, which makes a step that cut nothing
visible. The format is shared with mLOS, so the two files stack into a single
flow from the raw extract to the rows the models ran on.

**[Full specification →](docs/statistics-table.md)**

## From Python

If you want to poke at an intermediate stage:

```python
from shelterprep import load, Prep

prep = Prep(load("configs/orange_county2.yaml"))
prep.read().derive()          # frame now has nights, age_group, window_presence
prep.apply_steps().write()
prep.statistics.frame()       # the stage ledger as a DataFrame
prep.statistics.details()     # the by-value breakdown, on its own
prep.statistics.report()      # both, stacked -- what gets written to the CSV

from shelterprep import summary
summary.summarize(prep.frame, prep.settings)   # the descriptive tables
```

The command line calls `Prep(load(path)).run()`, which is the whole thing.

## Scope

Preparation only: read, derive, filter, map, and write. The weekly-cumulative
"physics" (`getCumulative`, `AnimDays`, the 17-week differencing) stays in
`stale/`, unported and kept for reference; it does not run under pandas 2.

## Tests

```bash
python3 -m pytest tests/ -q
```

83 tests, 96% line coverage of `shelterprep/`. Most of them pin down a decision
documented in `docs/`, so a test name states the rule it protects — the age
cutoff falling in the lower group, a map being simultaneous rather than
sequential, a still-in-care animal staying `IN` the window. The uncovered
remainder is defensive branches and the console printing.

The tests do **not** establish that a config is *correct* for its shelter. A
config is a set of claims about someone's data, and you check one by going
through its statistics table.

## License and citation

MIT — see [LICENSE](LICENSE). Use it, change it, redistribute it, keep the
notice, no warranty.

`CITATION.cff` carries the citation metadata, so GitHub shows a "Cite this
repository" button and Zenodo picks it up when minting a DOI. Cite the version
number the run log reports, not "the GitHub repository": those are different
claims, and only the first one is checkable. [More on publishing
→](docs/reproducibility.md)
