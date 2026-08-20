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
| `OC2_data.csv` | the prepared file |
| `OC2_data_stats.csv` | the statistics table: one row per stage, then one row per value each step names |
| `OC2_data_summary.csv` | descriptive statistics of the finished set: joint frequencies and length of stay |
| `OC2_data_run.txt` | provenance: source path, SHA-256, versions, timestamp |

`results/` is gitignored. To hand a prepared file to the downstream analysis,
copy it over. Then re-running the prep generates a new result here without
affecting the downstream copy.

`-q` suppresses the console table; the files are written either way. Installing
the package also puts a `shelterprep` command on your path, so
`shelterprep configs/orange_county2.yaml` does the same thing from anywhere.

## Installing

Python 3.9 or newer.

```bash
python3 -m pip install -r requirements.txt
python3 -m shelterprep configs/example_tiny.yaml
```

`python3 -m pip` installs into the interpreter you just named, whichever of
`pip` and `pip3` your system happens to provide. It is refused on a system
Python marked externally managed, such as Debian, Ubuntu, and Homebrew 3.12
and later, where the answer is a virtual environment.

Run from the repository root, where `configs/` and `shelterprep/` live. Or
install it properly, so `shelterprep` works from anywhere:

```bash
python3 -m pip install .
```

Add the `excel` extra if your extract is a workbook — a plain
`python3 -m pip install .` leaves out `openpyxl`, and an Excel source will
fail without it:

```bash
python3 -m pip install ".[excel]"
```

Everything else is pandas and PyYAML, with `pytest` needed to run the tests.
The run log records the version of each, along with the Python version,
because reproducing a result means stating the environment it ran in.

## Documentation

| document | content |
|---|---|
| [Preparing your own shelter data](docs/getting-started.md) | how to prepare a config for a shelter not listed below |
| [The settings file](docs/settings.md) | the settings file: all top-level keys, the path rules, and how dates are handled |
| [Steps and derived columns](docs/steps.md) | the step grammar (`cut` / `map` / `dedup`) for filters and transformations, plus the columns the tool derives for you |
| [The prepared file and the summary table](docs/outputs.md) | the prepared CSV and the summary table: what each column means |
| [The statistics table](docs/statistics-table.md) | the statistics table format, meant for downstream consumers; already shared with mLOS, the length-of-stay analysis tool |
| [Reproducibility and publishing](docs/reproducibility.md) | reproducibility and publishing: the run log, the digests, and what travels with a file into a paper |

[CONTRIBUTING.md](CONTRIBUTING.md) covers what to do with data you have
prepared. In a nutshell, deposit the extract, the settings, and the result
together, and cite the version you actually ran. [CHANGELOG.md](CHANGELOG.md)
records what changed between versions, and flags anything that could move a
number (that is, anything affecting the data and statistics this tool
generates).

## The shipped configs

| config | shelter | rows out | notes |
|---|---|---|---|
| `example_tiny.yaml` | none — the test fixture | 11 | runs on a clean clone; the starting point to copy |
| `orange_county2.yaml` | Orange County, dogs | 34,718 | the mLOS default; new outcome codes, `age_group` exported |
| `orange_county1.yaml` | Orange County, dogs | 36,564 | superseded by the above; frozen, so earlier results can be rebuilt and differences traced |
| `irvine_dogs.yaml` | Irvine, dogs | 11,022 | no dob, no size — no `animal_group` |
| `irvine_all_species.yaml` | Irvine, all species | 20,690 | US `m/d/yy` dates; `animal_type` is the stratifier |
| `long_beach.yaml` | Long Beach, dogs | 12,183 | no size; `age_group` is the stratifier |
| `mission_viejo.yaml` | Mission Viejo, dogs | 4,661 | its own column names throughout |
| `la_county_dogs.yaml` | LA County, dogs | 97,990 | offset-stamped dates; large blank-outcome share |
| `la_county_cats.yaml` | LA County, cats | 76,402 | same file and maps as the dogs config |

`orange_county1.yaml` was manually derived and checked against a previous
result. `orange_county2.yaml` is a deliberate revision of it, reviewed against
its own statistics table and the analysis it feeds. **The rest are
best-approximation ports of the stale pipeline's modules and have not been
validated against anything** — go through their statistics tables before
trusting a run. Places where a judgment was made, or where this tool deviates
from the stale pipeline because that pipeline appears to have had a bug, are
commented in the config itself.

Every config except `example_tiny.yaml` reads an extract that stays outside
the repository, so running one means [supplying the file
yourself](docs/getting-started.md#2-put-your-extract-where-a-config-can-see-it).

## The statistics table

One row per stage, in execution order — the shape of a CONSORT flow diagram, so
it can go into a supplement with minimal editing. Underneath it, in the same
file, one row per value the settings name, including the values that matched
nothing: that is how a misspelled label or a retired code gets caught. The
format is meant for downstream consumers, and is already shared with mLOS, the
length-of-stay analysis tool, so this file and a consumer's own statistics
stack into a single flow from the raw extract to the final sample.

**[Full specification →](docs/statistics-table.md)**

## From Python

If you want to poke at an intermediate stage:

```python
from shelterprep import load, Prep

prep = Prep(load("configs/orange_county2.yaml"))
prep.read().derive()          # frame now has nights, age_group, window_presence
prep.apply_steps().write()
prep.statistics.frame()       # the stage table as a DataFrame
prep.statistics.details()     # the by-value breakdown, on its own
prep.statistics.report()      # both, stacked -- what gets written to the CSV

from shelterprep import summary
summary.summarize(prep.frame, prep.settings)   # the descriptive tables
```

The command line calls `Prep(load(path)).run()`, which is the whole thing.

## Scope

Preparation only: read, derive, filter, map, and write. The `dedup:` step
collapses only stays identical in every column written, so screening
near-duplicates in an analysis-specific way belongs
[downstream](docs/steps.md#deduplication-is-deliberately-narrow). `stale/` also
holds weekly-cumulative "physics" code (`getCumulative`, `AnimDays`, the
17-week differencing), unported and kept for reference; it does not run under
pandas 2.

## Tests

```bash
python3 -m pytest tests/ -q
```

83 tests, 96% line coverage of `shelterprep/`. Most of them pin down a decision
documented in `docs/`, so a test name reads as the rule it protects. For
example, the age cutoff falling in the lower group, a map being simultaneous
rather than sequential, a still-in-care animal staying `IN` however old its
intake. The non-covered portion is defensive branches and the console
printing.

The tests do **not** establish that a config is *correct* for its shelter. A
config is a set of claims about the data. Check its statistics table for clues
about whether it did the intended transformation.

## License and citation

MIT — see [LICENSE](LICENSE). Use it, change it, redistribute it, keep the
notice, no warranty.

`CITATION.cff` carries the citation metadata, so GitHub shows a "Cite this
repository" button and Zenodo picks it up when minting a DOI. Cite the version
number the run log reports, not "the GitHub repository": those are different
claims, and only the first one is checkable. [More on publishing
→](docs/reproducibility.md)
