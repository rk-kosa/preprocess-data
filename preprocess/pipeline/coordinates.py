"""Step 2: fix wrong coordinates and validate against country bounds.

A row is an error candidate when its reported country's point sits on the LAND of
ANOTHER country (per ``country_bounds.json``). Points over water (inside no
country's box) are left untouched by design — an aircraft incident can legitimately
happen over the sea and still be logged to a country.

This step also sets an ``offshore`` flag: ``"true"`` for points that fall in no
country's box (over open water), ``"false"`` otherwise. Map country-centering
relies on it to frame each country by its on-land accidents, excluding the
over-water outliers that would distort the bounding box.
"""

import pandas as pd

from preprocess.common import (
    ACCIDENT_NUMBER,
    COUNTRY,
    LATITUDE,
    LONGITUDE,
    is_inside_bounds,
)

CountryBounds = dict[str, list[list[float]]]
CoordCorrections = dict[str, dict[str, float | str]]


def _foreign_land(lat: float, lon: float, bounds: CountryBounds, own: str) -> list[str]:
    """Get countries other than ``own`` whose box contains the (lat, lon) point."""
    return [
        country
        for country, boxes in bounds.items()
        if country != own and is_inside_bounds(lat, lon, boxes)
    ]


def _mark_offshore(
    data_frame: pd.DataFrame,
    latitudes: pd.Series,
    longitudes: pd.Series,
    bounds: CountryBounds,
) -> pd.Series:
    """Flag rows whose point falls in NO country's box (i.e. over open water)."""
    flags = []
    for lat, lon in zip(latitudes, longitudes, strict=True):
        offshore = (
            not pd.isna(lat)
            and not pd.isna(lon)
            and not any(is_inside_bounds(lat, lon, boxes) for boxes in bounds.values())
        )
        flags.append("true" if offshore else "false")
    return pd.Series(flags, index=data_frame.index, dtype="string")


def _apply_corrections(data_frame: pd.DataFrame, corrections: CoordCorrections) -> int:
    acc_numbers: pd.Series[str] = data_frame[ACCIDENT_NUMBER]
    applied = 0
    for accident_number, fix in corrections.items():
        match = acc_numbers == accident_number
        if match.any():
            data_frame.loc[match, LATITUDE] = fix["latitude"]
            data_frame.loc[match, LONGITUDE] = fix["longitude"]
            applied += 1
    return applied


def validate_coordinates(
    data_frame: pd.DataFrame,
    bounds: CountryBounds,
    corrections: CoordCorrections,
    exceptions: dict[str, str],
) -> pd.DataFrame:
    """Apply coordinate corrections, then abort on any unacknowledged land mismatch."""
    applied = _apply_corrections(data_frame, corrections)

    latitudes: pd.Series[pd.Float64Dtype] = pd.to_numeric(
        data_frame[LATITUDE], errors="coerce"
    )
    longitudes: pd.Series[pd.Float64Dtype] = pd.to_numeric(
        data_frame[LONGITUDE], errors="coerce"
    )
    unresolved: list[tuple[str, str, list[str]]] = []

    for idx in data_frame.index:
        country = data_frame.at[idx, COUNTRY]
        lat, lon = latitudes.at[idx], longitudes.at[idx]
        if pd.isna(country) or pd.isna(lat) or pd.isna(lon) or country not in bounds:
            continue
        if is_inside_bounds(lat, lon, bounds[country]):
            continue  # in own country -> fine
        if not (foreign := _foreign_land(lat, lon, bounds, country)):
            continue  # over water / no country's land -> leave alone
        if (accident_number := data_frame.at[idx, ACCIDENT_NUMBER]) in exceptions:
            continue  # acknowledged, reported separately
        unresolved.append((accident_number, country, foreign))

    if unresolved:
        for accident_number, country, foreign in unresolved:
            print(
                f"Coordinate mismatch: {accident_number} country={country}"
                f" sits in {foreign}"
            )
        raise ValueError(
            f"{len(unresolved)} coordinate mismatch(es) neither corrected nor "
            f"acknowledged - aborting"
        )

    data_frame["offshore"] = _mark_offshore(data_frame, latitudes, longitudes, bounds)

    offshore_count = int((data_frame["offshore"] == "true").sum())
    print(
        f"[coords] applied {applied} corrections, "
        f"{len(exceptions)} acknowledged exceptions, "
        f"{offshore_count} over-water points flagged"
    )
    return data_frame
