"""Generate coordinate corrections and the unresolved tail report for `coordinates`.

A row is an error candidate when its reported country's point sits on ANOTHER
country's land (per country_bounds.json). Over-water points are left
alone by design because an incident can legitimately happen over the sea and be logged
to a country.

A candidate is auto-corrected only when a single exact-inverse transform (a sign
flip and/or a lat/lon swap, operations that recover the original magnitude
exactly) lands the point back inside its own country. Everything else is written
to the exceptions file UNCHANGED.
"""

import json
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import pandas as pd

from preprocess.common import (
    ACCIDENT_NUMBER,
    COUNTRY,
    INPUT_DATA_ENCODING,
    INPUT_FILE,
    LATITUDE,
    LONGITUDE,
    REFERENCES_DIR,
    is_inside_bounds,
    load_country_bounds,
)
from preprocess.pipeline.coordinates import CoordCorrections, CountryBounds

# A single coordinate correction entry, as stored in CoordCorrections.
Correction = dict[str, float | str]
# An exact-inverse transform mapping (lat, lon) to a candidate (lat, lon).
Transform = Callable[[float, float], tuple[float, float]]

MANUAL_FIXES_FILE = f"{REFERENCES_DIR}/coord_corrections_manual.json"

CORRECTIONS_OUT_FILE = f"{REFERENCES_DIR}/coord_corrections.json"
EXCEPTIONS_OUT_FILE = f"{REFERENCES_DIR}/coord_exceptions.json"
JSON_INDENT = 2

REPORT_FILE = f"{REFERENCES_DIR}/coord_fix_report.md"


# Exact-inverse transforms, in priority order. Each recovers the original
# coordinate magnitude exactly (no invented digits), so a hit is high-confidence.
# Priority resolves the two rows where two transforms both land in-country
# (Rigolet NL -> lon_flip, Pretoria ZA -> lat_flip; verified against the city).
TRANSFORMS: list[tuple[str, Transform]] = [
    ("lon_flip", lambda lat, lon: (lat, -lon)),
    ("lat_flip", lambda lat, lon: (-lat, lon)),
    ("both_flip", lambda lat, lon: (-lat, -lon)),
    ("swap", lambda lat, lon: (lon, lat)),
    ("swap_lonneg", lambda lat, lon: (lon, -lat)),
    ("swap_latneg", lambda lat, lon: (-lon, lat)),
    ("swap_bothneg", lambda lat, lon: (-lon, -lat)),
]

# Decimal places at which two transform results count as the same point.
DEDUP_PRECISION = 5

# Decimal places for the corrected coordinates written to the corrections file.
COORD_PRECISION = 6

# Decimal places for coordinates shown in human-readable notes and reasons.
NOTE_PRECISION = 4


def get_containing_countries(
    lat: float, lon: float, bounds: CountryBounds
) -> list[str]:
    """Return every country whose box contains the point."""
    return [
        country
        for country, boxes in bounds.items()
        if is_inside_bounds(lat, lon, boxes)
    ]


def find_transform(
    latitude: float, longitude: float, own: list[list[float]]
) -> tuple[str, tuple[float, float]] | None:
    """Return the single exact-inverse transform landing in the own country.

    Result is ``(transform_name, (lat, lon))``, or None when no transform or more
    than one distinct result lands inside ``own``.
    """
    hits = [
        (name, transform(latitude, longitude))
        for name, transform in TRANSFORMS
        if is_inside_bounds(*transform(latitude, longitude), own)
    ]
    distinct = {
        (round(lat, DEDUP_PRECISION), round(lon, DEDUP_PRECISION))
        for _, (lat, lon) in hits
    }
    if not hits or len(distinct) > 1:
        return None
    return hits[0]


def apply_manual(
    corrections: CoordCorrections,
    exceptions: dict[str, str],
    manual: CoordCorrections,
    countries: dict[str, str],
    bounds: CountryBounds,
) -> None:
    """Apply manual overrides on corrections."""
    for accident_number, fix in manual.items():
        country = countries.get(accident_number)
        if country is None:
            raise SystemExit(
                f"Manual override {accident_number} not present in the input data"
            )
        coord_in_own_country = country in bounds and is_inside_bounds(
            float(fix["latitude"]), float(fix["longitude"]), bounds[country]
        )
        if country in bounds and not coord_in_own_country:
            raise SystemExit(
                f"Manual override {accident_number} does not land in {country}"
            )
        corrections[accident_number] = fix
        exceptions.pop(accident_number, None)


def get_coords_data() -> pd.DataFrame:
    """Read the input CSV and return rows with numeric coordinates."""
    data_frame = pd.read_csv(INPUT_FILE, encoding=INPUT_DATA_ENCODING, low_memory=False)
    latitudes = pd.to_numeric(data_frame[LATITUDE], errors="coerce")
    longitudes = pd.to_numeric(data_frame[LONGITUDE], errors="coerce")
    return data_frame[latitudes.notna() & longitudes.notna()]


def is_misplaced(
    lat: float,
    lon: float,
    country: str,
    bounds: CountryBounds,
) -> bool:
    """Determine if a country points sits outside of the country."""
    return country in bounds and not is_inside_bounds(lat, lon, bounds[country])


def check_unique_coords(
    accident_number: str,
    lat: float,
    lon: float,
    coords_seen: dict[str, tuple[float, float]],
) -> None:
    """Record the row's coords, aborting if it already appeared with different ones."""
    if accident_number in coords_seen and coords_seen[accident_number] != (lat, lon):
        raise SystemExit(
            f"Duplicate accident_number {accident_number} with differing coords"
        )
    coords_seen[accident_number] = (lat, lon)


def build_correction(
    name: str,
    lat: float,
    lon: float,
    lat_corrected: float,
    lon_corrected: float,
) -> Correction:
    """Build a correction entry from new coords and the transform applied."""
    was = f"{round(lat, NOTE_PRECISION)},{round(lon, NOTE_PRECISION)}"
    return {
        "latitude": round(lat_corrected, COORD_PRECISION),
        "longitude": round(lon_corrected, COORD_PRECISION),
        "note": f"{name} (was {was})",
    }


def build_exception(
    location: str,
    country: str,
    lat: float,
    lon: float,
    containing_countries: list[str],
) -> str:
    """Build report for an entry where no exact-inverse fix exists."""
    return (
        f"{location!r} country={country} at {round(lat, NOTE_PRECISION)},"
        f"{round(lon, NOTE_PRECISION)} sits in {containing_countries}; "
        "no exact-inverse fix - left as-is"
    )


def find_correction(
    lat: float,
    lon: float,
    country: str,
    bounds: CountryBounds,
) -> Correction | None:
    """Get a correction for the row, or None when no exact-inverse fix exists."""
    transform = find_transform(lat, lon, bounds[country])
    if transform is None:
        return None
    name, (corrected_latitude, corrected_longitude) = transform
    return build_correction(name, lat, lon, corrected_latitude, corrected_longitude)


def evaluate_coordinates(
    data_frame: pd.DataFrame,
    bounds: CountryBounds,
    manual: CoordCorrections,
) -> tuple[CoordCorrections, dict[str, str]]:
    """Scan rows and split flagged errors into corrections and exceptions."""
    corrections: CoordCorrections = {}
    exceptions: dict[str, str] = {}
    coords_seen: dict[str, tuple[float, float]] = {}

    for _, row in data_frame.iterrows():
        accident_number: pd.Series[str] = row[ACCIDENT_NUMBER]
        if accident_number in manual:
            continue

        country: pd.Series[str] = row[COUNTRY]
        lat = float(row[LATITUDE])
        lon = float(row[LONGITUDE])
        if not is_misplaced(lat, lon, country, bounds):
            continue

        containing_countries = get_containing_countries(lat, lon, bounds)
        if not containing_countries:
            continue

        check_unique_coords(accident_number, lat, lon, coords_seen)
        correction = find_correction(lat, lon, country, bounds)
        if correction is not None:
            corrections[accident_number] = correction
        else:
            exceptions[accident_number] = build_exception(
                row["Location"], country, lat, lon, containing_countries
            )

    return corrections, exceptions


def generate_outputs(corrections: CoordCorrections, exceptions: dict[str, str]) -> None:
    """Generate the corrections and exceptions JSON files."""
    Path(CORRECTIONS_OUT_FILE).write_text(
        json.dumps(corrections, indent=JSON_INDENT, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    Path(EXCEPTIONS_OUT_FILE).write_text(
        json.dumps(exceptions, indent=JSON_INDENT, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def get_counts_per_transform(corrections: CoordCorrections) -> dict[str, int]:
    """Get correction counts grouped by transform type."""
    return Counter(
        str(correction["note"]).split(" ")[0] for correction in corrections.values()
    )


def generate_report(
    corrections: CoordCorrections,
    exceptions: dict[str, str],
    counts_per_transform: dict[str, int],
) -> None:
    """Generate a human-readable summary of corrections and exceptions."""
    report = [
        "# Coordinate validation report",
        "",
        f"Generated by `preprocess/fix_coords.py` against `{INPUT_FILE}`.",
        "",
        f"- **{len(corrections)} auto-corrected** (exact-inverse transform):",
        *[
            f"    - {name}: {count}"
            for name, count in sorted(counts_per_transform.items())
        ],
        f"- **{len(exceptions)} left unchanged** (no exact fix; listed below):",
        "",
        "## Unchanged rows",
        "",
        "| accident_number | detail |",
        "| --- | --- |",
        *[
            f"| {accident_number} | {reason} |"
            for accident_number, reason in sorted(exceptions.items())
        ],
        "",
    ]
    Path(REPORT_FILE).write_text("\n".join(report), encoding="utf-8")


def main() -> None:
    """Generate the corrections, exceptions and report."""
    bounds = load_country_bounds()
    manual: CoordCorrections = json.loads(
        Path(MANUAL_FIXES_FILE).read_text(encoding="utf-8")
    )
    data_frame = get_coords_data()
    corrections, exceptions = evaluate_coordinates(data_frame, bounds, manual)

    country_by_accident_number = dict(
        zip(data_frame[ACCIDENT_NUMBER], data_frame[COUNTRY], strict=False)
    )
    apply_manual(corrections, exceptions, manual, country_by_accident_number, bounds)

    generate_outputs(corrections, exceptions)
    counts = get_counts_per_transform(corrections)
    generate_report(corrections, exceptions, counts)

    print(f"corrections: {len(corrections)}  {counts}")
    print(f"exceptions:  {len(exceptions)} -> {EXCEPTIONS_OUT_FILE}")
    print(f"report:      {REPORT_FILE}")


if __name__ == "__main__":
    main()
