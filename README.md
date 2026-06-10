# NTSB Aviation Accident Preprocessing

A single, in-memory pipeline that reads the raw NTSB Aviation Accident CSV once, applies every transform to one DataFrame and writes a cleaned UTF-8 CSV ready for the Postgres / PostGIS load. Needs Python3.13 to execute.


## Setup

Create a virtual environment and activate it:

```bash
python3.13 -m venv venv
source venv/bin/activate
```

Then install the dependencies into the active environment:

```bash
pip install -r requirements.txt
```

## Run

From **project root**, with the venv activated (see Setup), run:

```bash
python -m preprocess.run_pipeline
```

Input and output paths default to `data/AviationData_SSC_case_Ranbir.csv` and `data/aviation_accidents.csv`, and the repo already has this cleaned file. To override, note that the input needs to located in the data folder and run:

```bash
python -m preprocess.run_pipeline --src data/<sample_input.csv> --output data/<sample_input_cleaned.csv>
```

## Coordinate corrections

Step 2 (`validate_coordinates`) *applies* a predefined set of fixes and *aborts* on anything new. The fixes themselves are produced offline by `preprocess/fix_coords.py`, a separate tool which needs to be ran when the source changes. It reads the **raw** CSV and generates coordinate corrections and exceptions files into `preprocess/references/` (`coord_corrections.json`, `coord_exceptions.json`) and a report to `coord_fix_report.md`.

Regenerate with:

```bash
venv/bin/python -m preprocess.fix_coords
```

## Transformation steps

| # | Module                    | Function                 | Effect |
|---|---------------------------|--------------------------|--------|
| 0 | `pipeline/validation.py`  | `validate_input_columns` | fail fast if the raw CSV schema is unexpected |
| 1 | `pipeline/rows.py`        | `filter_missing_cords`   | keep only rows with both Latitude & Longitude |
| 2 | `pipeline/coordinates.py` | `validate_coordinates`   | fix mis-geocoded coords; abort on foreign-land mismatch |
| 3 | `pipeline/dates.py`       | `fix_dates`              | Event/Publication dates -> ISO `YYYY-MM-DD` |
| 4 | `pipeline/casing.py`      | `fix_casing`             | normalise Make/Model/Location/... casing |
| 5 | `pipeline/nulls.py`       | `normalize_nulls`        | `UNKNOWN`/`NA`/`-`/... -> true nulls |
| 6 | `pipeline/severity.py`    | `split_severity`         | `Injury.Severity` -> `severity_category` + `fatality_count` |
| 7 | `pipeline/injuries.py`    | `fill_injuries`          | blank injury counts -> 0 (except all-blank rows) |
| 8 | `pipeline/columns.py`     | `drop_sparse`            | drop `Air.Carrier` & `Schedule` |
| 9 | `pipeline/types.py`       | `convert_types`          | Int64 casts, bool `amateur_built`, engine `Mixed`, `geom` EWKT |
| 10| `pipeline/encoding.py`    | `fix_encoding`           | repair mojibake in foreign place/airport names |
| 11| `pipeline/columns.py`     | `rename_columns`         | Dot.Names -> snake_case (final step) |



### Coordinate errors
A row is a candidate only when its reported country's point sits on **another country's land** (based on `country_bounds.json`). Points over water are left alone by design because an incident can legitimately happen at sea and still be logged to a country.

### How bad coordinates are fixed
A candidate is fixed only when a single *exact-inverse* transform (a sign flip and/or a lat/lon swap) puts the point back inside its own country. Rows that no transform recovers (dropped digits, over-water sign flips that are never flagged) are fixed by hand in `coord_corrections_manual.json` and they are also updated. Anything still unresolvable is written **unchanged** to `coord_exceptions.json` with their corresponding reason. These files are also present now in the repo, the pipeline uses them.


## Output

32 columns x 30,146 rows (currently, with the specified input), written as UTF-8 with `LF` line endings.