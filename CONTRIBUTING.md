# Contributing

*Placeholder. The most useful thing you can do with this tool is deposit what
you prepared, so that part comes first.*

## If you have prepared a shelter's data

Deposit three things together, in a data repository that mints a persistent
identifier — Figshare, Zenodo, Dryad, an institutional repository:

1. **The raw extract**, as you received it.
2. **The YAML settings file** that prepared it.
3. **The result** — the prepared CSV, and with it the statistics table and the
   run log, which are what make the CSV mean anything.

Then **cite ShelterDataPrep by the DOI of the version you actually used**, not
by a link to the repository. A GitHub URL is not archival: the repository can
be rewritten or deleted, and "the GitHub repository" and "version 0.2.1" are
different claims, of which only the second is checkable. Your run log reports
the version to name.

Those three files plus the version are the whole reproduction. Someone with
them can rebuild your prepared data byte for byte and see every row you
excluded and why.

More on what travels with a file into a paper: [docs/reproducibility.md](docs/reproducibility.md).

## If you have a config for a new shelter

That is the contribution this repository most wants, and there is no process
for it yet. [docs/getting-started.md](docs/getting-started.md) sets out what a
config needs to be worth shipping: every step commented with what it claims
about that shelter's vocabulary, and a statistics table you have gone
through. Say plainly whether it has been checked against a previous result —
most of the shipped configs have not, and say so.

## If you have found a bug

Open an issue with the settings file and the statistics table. Those two, with
the run log, usually locate it without the data — which is just as well, since
the data is generally not yours to send.
