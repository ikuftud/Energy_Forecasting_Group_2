# Scripts README

## `building_merge.py`

This script merges an NMI-level wide CSV into building-level columns.

Default command:

```bash
python3 scripts/building_merge.py Data/LMS_2013-01-01_2026-03-24_HALF_HOUR_au.csv
```

Command with an explicit output path:

```bash
python3 scripts/building_merge.py Data/LMS_2013-01-01_2026-03-24_HALF_HOUR_au.csv --output output/building_level.csv
```

Command with an explicit mapping file:

```bash
python3 scripts/building_merge.py Data/LMS_2013-01-01_2026-03-24_HALF_HOUR_au.csv --mapping-json scripts/building_nmi_mapping.json --output output/building_level.csv
```

Mapping source:

- By default this script reads [`scripts/building_nmi_mapping.json`].
- The current mapping JSON contains `9` unmapped NMIs.
- Those unmapped NMIs are kept as raw NMI column names in the merged output.

## `date_merge.py`

This script aggregates a wide CSV from half-hour data to `1h` or `1d`.

Command for 1-hour aggregation:

```bash
python3 scripts/date_merge.py output/building_level.csv 1h
```

Command for 1-day aggregation:

```bash
python3 scripts/date_merge.py output/building_level.csv 1d
```

Command with an explicit output path:

```bash
python3 scripts/date_merge.py output/building_level.csv 1d --output output/building_level_1d.csv
```

Notes:

- The input file must contain a `date` column.
- The `period` argument only accepts `1h` or `1d`.
- If `--output` is not passed, the output file is written to the same folder as the input file.
