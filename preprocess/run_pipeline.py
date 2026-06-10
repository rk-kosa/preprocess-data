"""Unified NTSB Aviation Accident preprocessing pipeline — orchestration.

The raw CSV is read ONCE (as latin-1, lossless byte preservation), every step
(defined in the `pipeline` package) is applied to one data frame in memory, and one
clean UTF-8 CSV is generated in the end.

Steps in order:
    0. validate_input_columns  fail fast if the raw CSV schema is unexpected
    1. filter_missing_cords    keep only rows with both Latitude & Longitude
    2. validate_coordinates    fix mis-geocoded coords; abort on foreign-land mismatch
    3. fix_dates               convert Event/Publication dates to ISO 'YYYY-MM-DD'
    4. fix_casing              normalize Make/Model/Location/... capitalization
    5. normalize_nulls         transform 'UNKNOWN'/'NA'/'-'/... to nulls
    6. split_severity          derive Severity.Category + Fatality.Count
    7. fill_injuries           set blank injury counts to 0 (except all-blank rows)
    8. drop_sparse             drop Air.Carrier & Schedule (too sparse/dirty)
    9. convert_types          Int64 casts, amateur_built to bool, 'Mixed' engine, geom
   10. fix_encoding            repair mojibake in foreign place/airport names
   11. rename_columns          transform Dot.Names to postgres snake_case (final step)
"""

import json
import sys
from collections.abc import Callable
from functools import partial
from pathlib import Path

import click
import pandas as pd

from preprocess.common import (
    DATA_DIR,
    INPUT_DATA_ENCODING,
    INPUT_FILE,
    REFERENCES_DIR,
    load_country_bounds,
)
from preprocess.pipeline.casing import fix_casing
from preprocess.pipeline.columns import drop_sparse, rename_columns
from preprocess.pipeline.coordinates import (
    CoordCorrections,
    CountryBounds,
    validate_coordinates,
)
from preprocess.pipeline.dates import fix_dates
from preprocess.pipeline.encoding import fix_encoding
from preprocess.pipeline.injuries import fill_injuries
from preprocess.pipeline.nulls import normalize_nulls
from preprocess.pipeline.rows import filter_missing_cords
from preprocess.pipeline.severity import split_severity
from preprocess.pipeline.types import convert_types
from preprocess.pipeline.validation import InvalidColumnError, validate_input_columns

OUTPUT_FILE = "aviation_accidents.csv"

CORRECTIONS_FILE = f"{REFERENCES_DIR}/encoding_corrections.json"
INPUT_COLUMNS_FILE = f"{REFERENCES_DIR}/input_columns.json"
COORD_CORRECTIONS_FILE = f"{REFERENCES_DIR}/coord_corrections.json"
COORD_EXCEPTIONS_FILE = f"{REFERENCES_DIR}/coord_exceptions.json"


def _load_encoding_corrections(path: Path) -> dict[tuple[str, str], str]:
    """Load the hand-verified mojibake corrections."""
    by_column: dict[str, dict[str, str]] = json.loads(path.read_text(encoding="utf-8"))
    return {
        (accident_number, column): value
        for column, entries in by_column.items()
        for accident_number, value in entries.items()
    }


def _build_pipeline(
    corrections: dict[tuple[str, str], str],
    bounds: CountryBounds,
    coord_corrections: CoordCorrections,
    coord_exceptions: dict[str, str],
) -> tuple[Callable[[pd.DataFrame], pd.DataFrame], ...]:
    return (
        filter_missing_cords,
        partial(
            validate_coordinates,
            bounds=bounds,
            corrections=coord_corrections,
            exceptions=coord_exceptions,
        ),
        fix_dates,
        fix_casing,
        normalize_nulls,
        split_severity,
        fill_injuries,
        drop_sparse,
        convert_types,
        partial(fix_encoding, corrections=corrections),
        rename_columns,
    )


def _validate_input(data_frame: pd.DataFrame, expected: list[str]) -> None:
    try:
        validate_input_columns(data_frame, expected)
    except InvalidColumnError as error:
        print(f"Invalid column(s) found: {error}")
        raise SystemExit(1) from error


@click.command()
@click.option("--src", type=str, default=INPUT_FILE, help="Path to raw input CSV file")
@click.option(
    "--output",
    type=str,
    default=f"{DATA_DIR}/{OUTPUT_FILE}",
    help="Path to cleaned output CSV file",
)
def main(src: str, output: str) -> None:
    """Run the full data transformer pipeline and generate the cleaned CSV in UTF-8."""
    corrections = _load_encoding_corrections(Path(CORRECTIONS_FILE))
    expected_columns: list[str] = json.loads(
        Path(INPUT_COLUMNS_FILE).read_text(encoding="utf-8")
    )
    bounds = load_country_bounds()
    coord_corrections: CoordCorrections = json.loads(
        Path(COORD_CORRECTIONS_FILE).read_text(encoding="utf-8")
    )
    coord_exceptions: dict[str, str] = json.loads(
        Path(COORD_EXCEPTIONS_FILE).read_text(encoding="utf-8")
    )
    data_transformer = _build_pipeline(
        corrections, bounds, coord_corrections, coord_exceptions
    )

    print(f"Reading {src}")
    data_frame = pd.read_csv(src, encoding=INPUT_DATA_ENCODING, low_memory=False)
    _validate_input(data_frame, expected_columns)

    for step in data_transformer:
        try:
            data_frame = step(data_frame)
        except ValueError as error:
            print(f"Preprocessing failed: {error}", file=sys.stderr)
            raise SystemExit(1) from error

    data_frame.to_csv(output, index=False, encoding="utf-8", na_rep="")
    print(
        f"\nDone: {data_frame.shape[1]} columns x {len(data_frame):,} rows -> {output}"
    )


if __name__ == "__main__":
    main()
