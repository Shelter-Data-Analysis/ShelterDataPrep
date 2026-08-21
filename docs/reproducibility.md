# Reproducibility and publishing

*For anyone who has to defend a number: what the run log records, why, and what
travels with a prepared file into a paper.*

[← ShelterDataPrep](../README.md)

A run is deterministic: the same settings over the same source file give the
same output, and paths resolve against the settings file, so the working
directory makes no difference. The run log is enough to reproduce a result.

```
ShelterDataPrep run log

shelterprep   0.2.2
run at        2026-08-20T17:26:10
settings      configs/orange_county2.yaml
source        /Users/you/projects/_shelter_raw/OC_raw.csv.gz
source sha256 fbc5fa49...  (of the uncompressed contents)
sheet         (csv)
date_format   ISO8601
keep_time     False
window        2018-06-01 to 2025-10-02
destination   /Users/you/projects/ShelterDataPrep/results/OC2_data.csv
output sha256 aed363f4...
output rows   34718
final span    intake 2018-01-22 to 2025-10-02, last outcome 2025-10-03, 205 still in care

python        3.9.6 on macOS-26.6.2-arm64-arm-64bit
pandas        2.3.1
numpy         2.0.2
PyYAML        6.0.3
openpyxl      3.1.5
```

The digests here are shortened to fit; the log carries them in full. The two
paths are absolute, since `source_dir` and `dest_dir` resolve against the
settings file rather than the working directory.

`sheet`, `date_format`, `keep_time`, and `window` echo the settings that decide
how the source is read and what the derived columns say. The statistics table
then follows in the same file, rendered as text — the same content held by
`<name>_stats.csv` for easy conversion to a spreadsheet or pandas frame.

The two digests bracket the run. **`source sha256`** identifies the extract —
taken over the *uncompressed* contents, so it does not move if the file is
recompressed by a different tool or at a different level, and still matches the
original the archive was made from. **`output sha256`** identifies the prepared
file, so a copy that has been opened and re-saved by a spreadsheet announces
itself instead of passing as the original.

Library versions are recorded because pandas has changed the behavior of date
parsing, of `groupby`, and of nullable integers across minor versions. "It ran
under pandas 2" is not a version.

## For a paper

Four things reviewers care about:

1. **The prepared file, its statistics table, and its run log travel
   together.** The prepared file alone cannot say where it came from; the run
   log is the provenance and the statistics table is the exclusion history.
2. **Name a version, not a branch.** A GitHub URL is not archival — the
   repository can be rewritten or deleted, so a bare link fails a data
   availability statement. Cite the version the run log records, and the DOI
   alongside it once ShelterDataPrep has one.
3. **Deposit the raw extract separately**, with its own DOI. Raw extracts are
   public records; they belong in a repository with a persistent identifier,
   not in git history. That is why `source_dir` points outside this repo.
4. **The statistics table is the flow diagram.** It is shaped after CONSORT and
   goes into a supplement more or less as is; the by-value breakdown underneath
   it turns "147,385 rows were excluded" into a defensible sentence.

## Citation

`CITATION.cff` carries the citation metadata, so GitHub shows a "Cite this
repository" button and Zenodo picks it up when minting a DOI. Cite the version
number the run log reports, not "the GitHub repository": those are different
claims, and only the first one is checkable. ShelterDataPrep has no DOI yet, so
the version number is the whole citation for now.

---

**See also:** [the statistics table](statistics-table.md) ·
[the prepared file](outputs.md) · [the settings file](settings.md)
