"""Step 9: final type fixes before the Postgres / PostGIS load."""

import pandas as pd

from preprocess.common import move_columns_after

INJURY_SEVERITY_COL = "Injury.Severity"
INTEGER_COLS = [
    "Fatality.Count",
    "Number.of.Engines",
    "Total.Fatal.Injuries",
    "Total.Serious.Injuries",
    "Total.Minor.Injuries",
    "Total.Uninjured",
]
ENGINE_TYPE_COMBOS = [
    "REC, TJ, TJ",
    "REC, ELEC",
    "REC, TJ, REC, TJ",
    "TJ, REC, REC, TJ",
]


def _drop_severity(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Drop the original Injury.Severity column (now redundant)."""
    if INJURY_SEVERITY_COL in data_frame.columns:
        data_frame = data_frame.drop(columns=[INJURY_SEVERITY_COL])
    return data_frame


def _cast_integer_columns(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Re-assert nullable Int64 on the count columns (null stays empty)."""
    for column in INTEGER_COLS:
        data_frame[column] = pd.to_numeric(data_frame[column], errors="coerce").astype(
            "Int64"
        )
    return data_frame


def _cast_amateur_built_to_bool(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Map Amateur.Built 'Yes'/'No' to 'true'/'false' literals (null stays empty)."""
    boolean_map = {"Yes": "true", "No": "false"}
    unmapped = data_frame["Amateur.Built"].notna() & ~data_frame["Amateur.Built"].isin(
        boolean_map
    )
    if unmapped.any():
        raise ValueError(
            f"Unexpected values in 'Amateur.Built': "
            f"{sorted(data_frame.loc[unmapped, 'Amateur.Built'].unique())}"
        )
    data_frame["Amateur.Built"] = data_frame["Amateur.Built"].map(boolean_map)
    return data_frame


def _engine_combos_to_mixed(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Update per-engine combo lists from mixed-powerplant aircraft to 'Mixed'."""
    is_combo = data_frame["Engine.Type"].isin(ENGINE_TYPE_COMBOS)
    data_frame.loc[is_combo, "Engine.Type"] = "Mixed"
    return data_frame


def _add_geom(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Add an EWKT 'SRID=4326;POINT(lon lat)' geom column right after Longitude."""
    latitude = pd.to_numeric(data_frame["Latitude"], errors="coerce")
    longitude = pd.to_numeric(data_frame["Longitude"], errors="coerce")
    both = latitude.notna() & longitude.notna()
    geom = pd.Series(pd.NA, index=data_frame.index, dtype="string")
    geom[both] = (
        "SRID=4326;POINT("
        + longitude[both].astype(str)
        + " "
        + latitude[both].astype(str)
        + ")"
    )
    data_frame["geom"] = geom
    return move_columns_after(data_frame, "Longitude", ["geom"])


def _place_offshore(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Move the offshore flag (from the coordinates step) to sit right after geom."""
    if "offshore" in data_frame.columns:
        data_frame = move_columns_after(data_frame, "geom", ["offshore"])
    return data_frame


def convert_types(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Apply final type fixes: drop raw severity, Int64 casts, bool, engine, geom."""
    data_frame = (
        data_frame.pipe(_drop_severity)
        .pipe(_cast_integer_columns)
        .pipe(_cast_amateur_built_to_bool)
        .pipe(_engine_combos_to_mixed)
        .pipe(_add_geom)
        .pipe(_place_offshore)
    )

    populated = int(data_frame["geom"].notna().sum())
    print(
        f"[9] types: dropped raw severity, Int64 casts, amateur_built bool, "
        f"geom added (populated={populated:,})"
    )
    return data_frame
