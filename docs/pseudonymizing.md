# Pseudonymizing animal IDs

`tools/pseudonymize_ids.py` replaces each animal ID in a prepared file with a
random pseudonym, so the file can be shared without the shelter's own IDs. It
is meant for confidential data sets, such as the WAGS extract, whose raw
extract, settings file, and outputs sit outside this repository. The shelters
whose configs ship here publish their extracts, and anyone holding one can
match a prepared row back to it by dates and types alone, so pseudonymizing
their files protects nothing.

The tool runs after the main run, on the same settings file. It is not part
of the installed package, and the run log of the main run does not mention
it.

## The two modes

```bash
python3 tools/pseudonymize_ids.py map settings.yaml
```

`map` reads the raw extract named in the settings file, with the settings
file's `columns:` entries and the same cleaning as a main run. It adds a
pseudonym for each animal ID the mapping does not yet hold. An ID already in
the mapping keeps its pseudonym, so one mapping can serve several configs
and later extracts of the same shelter, and an animal keeps its pseudonym
across them. A blank ID (`_UNKNOWN_`) is not an ID and gets no pseudonym.

```bash
python3 tools/pseudonymize_ids.py apply settings.yaml
```

`apply` reads the prepared file and writes a copy with every animal ID
replaced. Every other byte of the file is unchanged: mapped back, the copy is
the prepared file. If there is no mapping file yet, `apply` runs `map` first.

`apply` stops, and writes nothing, in these cases:

- the prepared file holds an ID that the mapping lacks. The error lists each
  such ID with its row count. This happens when the mapping was built from an
  older extract; run `map` to add them.
- the mapping repeats an ID or a pseudonym. Two animals under one pseudonym
  would be merged downstream.
- the output would overwrite the prepared file or the mapping.

A prepared file without an `animal_id` column, because `output_columns` leaves
it out, has nothing to pseudonymize. `apply` prints a warning, writes
nothing, and exits successfully.

## Files

All paths default to the settings file's `dest_dir`.

| File | Written by | Holds |
|---|---|---|
| `private_animal_id.csv` | `map` | columns `animal_id`, `pseudonym`; one row per ID |
| `<name>_pseudonymized.csv` | `apply` | the prepared file `<name>.csv` with pseudonyms for IDs |
| `<name>_pseudonymized_run.txt` | `apply` | the log described below |

`--mapping PATH` names a different mapping file, in either mode. `--output
PATH` names a different output file for `apply`; the log is written beside
it, named after it.

`private_animal_id.csv` is the key. Anyone holding it and the pseudonymized
file has the original IDs. Keep it with the raw extract, not with what is
shared. The repository's `.gitignore` excludes both file patterns, as a
safeguard.

## The pseudonyms

A pseudonym is `P` followed by 12 hexadecimal digits, such as `P3FA9C01B2E4D`:
48 bits drawn from Python's `secrets` module. It is not derived from the ID,
so nothing about the ID can be recovered from it, and the mapping is the
single way back. A hash of the ID would not have that property. Animal IDs
come from a small, predictable range, so hashing every candidate ID and
matching the results reverses an unkeyed hash.

A pseudonym is drawn to differ from every other pseudonym and from every
animal ID in the mapping and the extract, so a pseudonymized file cannot hold
a value that is also a real ID.

## The log

```
ShelterDataPrep pseudonymization log

shelterprep   0.5.0  (tools/pseudonymize_ids.py)
run at        2026-10-05T14:02:11
settings      /Users/you/studies/WAGS/wags_dogs.yaml
input         /Users/you/studies/WAGS/results/WAGS_data.csv
input sha256  9b1c07e2...  (the output sha256 of its run log)
mapping       /Users/you/studies/WAGS/results/private_animal_id.csv
output        /Users/you/studies/WAGS/results/WAGS_data_pseudonymized.csv
output sha256 51d0a3f4...
output rows   18214
IDs replaced  15377 distinct
```

The values above are illustrative, not from a run. The input digest equals
the `output sha256` line of the main run's log, which ties the pseudonymized
file to the run that produced it. The log holds no IDs and no pseudonyms.

## What it does not protect

Pseudonymizing hides the ID and nothing else. The dates, intake type, outcome
type, and any other column written stay as they are, and together they can
identify a stay to anyone who holds the raw extract. The raw extract and the
mapping both stay confidential.
