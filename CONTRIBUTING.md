# Contributing

Four things, in order of how much they help: report what you did with the
tool, report a bug, ask a question, change the code. The first three are
issues, and each has a template that asks for what an answer usually needs.

## If you have prepared a shelter's data

The most useful thing you can do with this tool is deposit what you prepared.
A config belongs with the data it prepared, in its author's deposit, rather
than in this repository. The deposit cites ShelterDataPrep, so a config turns
up when someone traces the citations.

Deposit four things together, in a data repository that mints a persistent
identifier — Figshare, Zenodo, Dryad, an institutional repository:

1. **The raw extract**, as you received it.
2. **The YAML settings file** that prepared it.
3. **The result** — the prepared CSV, and with it the statistics table and the
   run log, which are what make the CSV mean anything.
4. **A short usage report**, a few paragraphs, saying what you prepared and
   what for, what in the tool was most useful, what was less useful or needed
   a workaround, and what you would want added. Name the version you ran.

[docs/getting-started.md](docs/getting-started.md) sets out what a config needs
to be useful to others: every step commented with what it claims about that
shelter's vocabulary, and a statistics table you have gone through. Say plainly
whether it has been checked against a previous result. Checking is preferable
but not always practical. (Most of the shipped configs have not been checked,
and say so clearly.)

Then **cite ShelterDataPrep by its DOI, naming the version you actually
used**, not
by a link to the repository. A GitHub URL is not archival: the repository can
be rewritten or deleted, and "the GitHub repository" and "version 0.3.0" are
different claims, of which only the second is checkable. Your run log reports
the version to name, and
[10.5281/zenodo.22051338](https://doi.org/10.5281/zenodo.22051338) is the DOI
to name it with.

Those files plus the version are the whole reproduction. Someone with them can
rebuild your prepared file byte for byte and see every row you excluded and
why.

Post the usage report, or a link to the deposit holding it, as a GitHub issue
as well, so it reaches the people working on the tool rather than only the
people tracing citations. It is read as a report of experience, not a feature
request that anyone has undertaken to fill.

More on what travels with a file into a paper: [docs/reproducibility.md](docs/reproducibility.md).

## If you have found a bug

Open an issue with the settings file and the statistics table. Those two, with
the run log, usually locate it without the data — which is just as well, since
the data is generally not yours to send.

## If you have a question

Open an issue for that too. Questions about whether a config expresses what you
meant, or about what a statistics table is telling you, are as welcome as bug
reports and are often the same thing. Check `docs/` first, which the README
indexes by topic. This is a small academic project, so answers come when they
come.

## If you want to change the code

Open an issue describing the problem before writing a patch, so the approach
can be agreed on rather than reworked. Pull requests should keep
`python3 -m pytest tests/ -q` passing, add a test for anything they change, and
update the doc that states the rule. Anything that could move a number in a
prepared file needs an entry in [CHANGELOG.md](CHANGELOG.md) saying so.
