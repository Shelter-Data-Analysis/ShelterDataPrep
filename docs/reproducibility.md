# Reproducibility and publishing

*For anyone who has to defend a number: what the run log records, why, and what
travels with a prepared file into a paper.*

[← ShelterDataPrep](../README.md)

A run is deterministic: same settings, same source file, same output, with no
sampling, no randomness, and no dependence on the working directory or on the
order of anything. So the run log is enough to reproduce it.

```
shelterprep   0.2.0
run at        2026-08-01T18:23:27
settings      configs/orange_county2.yaml
source        ../../_shelter_raw/OC_raw.csv.gz
source sha256 fbc5fa49...  (of the uncompressed contents)
destination   results/OC2_data.csv
output sha256 e7b04f9a...
output rows   34718
final span    intake 2018-01-22 to 2025-10-02, last outcome 2025-10-03, 205 still in care

python        3.9.6 on macOS-26.5.2-arm64-arm-64bit
pandas        2.3.1
numpy         2.0.2
PyYAML        6.0.3
openpyxl      3.1.5
```

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

Four things, in the order a reviewer will want them:

1. **The prepared file, its stats file, and its run log travel together.** The
   data file alone cannot say where it came from; the run log is the provenance
   and the stats file is the exclusion history.
2. **Archive a tagged release, not a branch.** A GitHub URL is not archival —
   the repository can be rewritten or deleted, so a bare link fails a data
   availability statement. Tag a release and mint a DOI for it, then cite the
   DOI and the version number the run log records.

   Zenodo does this from a GitHub release, but **enable the repository in
   Zenodo before you tag**: the integration archives releases made after it is
   switched on and does not reach back for earlier ones. A release tagged first
   and remembered later has no DOI, which is the one thing this step exists to
   prevent.
3. **Deposit the raw extract separately**, with its own DOI. Raw extracts are
   public records; they belong in a repository with a persistent identifier,
   not in git history. That is why `source_dir` points outside this repo.
4. **The statistics table is the flow diagram.** It is shaped after CONSORT and
   goes into a supplement more or less as is; the by-value breakdown underneath
   it is what turns "147,385 rows were excluded" into a defensible sentence.

## Citation

`CITATION.cff` carries the citation metadata, so GitHub shows a "Cite this
repository" button and Zenodo picks it up when minting a DOI. Cite the version
number the run log reports, not "the GitHub repository": those are different
claims, and only the first one is checkable.

---

**See also:** [the statistics table](statistics-table.md) ·
[the prepared file](outputs.md) · [the settings file](settings.md)
