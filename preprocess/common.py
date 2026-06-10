import json
from pathlib import Path

import pandas as pd

INPUT_DATA_ENCODING = "latin-1"

DATA_DIR = "data"
INPUT_FILE = f"{DATA_DIR}/AviationData_SSC_case_Ranbir.csv"

REFERENCES_DIR = "preprocess/references"
COUNTRY_BOUNDS_FILE = f"{REFERENCES_DIR}/country_bounds.json"

# Column names
ACCIDENT_NUMBER = "Accident.Number"
COUNTRY = "Country"
LATITUDE = "Latitude"
LONGITUDE = "Longitude"


def load_country_bounds() -> dict[str, list[list[float]]]:
    """Load countries bounding boxes, dropping `_comment`."""
    country_bounds = json.loads(Path(COUNTRY_BOUNDS_FILE).read_text(encoding="utf-8"))
    return {
        country: bounds
        for country, bounds in country_bounds.items()
        if not country.startswith("_")
    }


def is_inside_bounds(lat: float, lon: float, boxes: list[list[float]]) -> bool:
    """Return whether coordinates are inside the specified bounding boxes."""
    for lon_min, lat_min, lon_max, lat_max in boxes:
        lat_in_range = lat_min <= lat <= lat_max
        lon_in_range = (
            lon_min <= lon <= lon_max
            if lon_min <= lon_max
            else lon >= lon_min or lon <= lon_max
        )
        if lat_in_range and lon_in_range:
            return True
    return False


def move_columns_after(
    data_frame: pd.DataFrame, anchor: str, columns_to_move: list[str]
) -> pd.DataFrame:
    """Return data_frame with columns_to_move placed right after the anchor column."""
    columns = data_frame.columns.tolist()
    for column in columns_to_move:
        columns.remove(column)
    insert_at = columns.index(anchor) + 1
    columns[insert_at:insert_at] = columns_to_move
    return data_frame[columns]
