"""Step 5: convert placeholder/sentinel strings to true nulls."""

import numpy as np
import pandas as pd

NULL_SENTINELS = {
    "unknown",
    "unk",
    "unavailable",
    "n/a",
    "na",
    "none",
    "nan",
    "",
    "-",
    "?",
}


def normalize_nulls(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Replace placeholder strings ('UNKNOWN', 'NA', '-', ...) with true nulls."""
    total_normalized = 0
    for column in data_frame.select_dtypes(include=["object", "string"]).columns:
        normalized = data_frame[column].astype("string").str.strip().str.lower()
        sentinel = normalized.isin(NULL_SENTINELS) & data_frame[column].notna()
        sentinel_count = int(sentinel.sum())
        if sentinel_count:
            data_frame.loc[sentinel, column] = np.nan
            total_normalized += sentinel_count
    print(f"[5] sentinels: nulled {total_normalized:,} values")
    return data_frame
