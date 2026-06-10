"""Step 1: drop rows that are missing coordinates."""

import pandas as pd


def filter_missing_cords(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Filter out rows that miss either Latitude or Longitude."""
    has_coords = data_frame["Latitude"].notna() & data_frame["Longitude"].notna()
    filtered_rows: pd.DataFrame = data_frame[has_coords]
    dropped = len(data_frame) - len(filtered_rows)
    print(
        f"[1] coords: kept {len(filtered_rows):,} of {len(data_frame):,} "
        f"({has_coords.mean() * 100:.1f}%), dropped {dropped:,}"
    )
    return filtered_rows
