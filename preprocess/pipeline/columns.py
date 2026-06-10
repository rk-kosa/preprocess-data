"""Step 8 + 11: drop sparse columns, and rename everything to snake_case."""

import pandas as pd

SPARSE_COLS = ["Air.Carrier", "Schedule"]


def _to_snake_case(name: str) -> str:
    """Convert a dot-separated header like 'Event.Id' to snake_case ('event_id')."""
    return name.replace(".", "_").lower()


def drop_sparse(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Drop columns too sparse/dirty to keep (Air.Carrier, Schedule)."""
    sparse = [column for column in SPARSE_COLS if column in data_frame.columns]
    data_frame = data_frame.drop(columns=sparse)
    print(f"[8] dropped sparse columns: {sparse}")
    return data_frame


def rename_columns(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Rename every column to postgres-friendly snake_case (the final step)."""
    data_frame = data_frame.rename(columns=_to_snake_case)
    print(f"[11] renamed {len(data_frame.columns)} columns to snake_case")
    return data_frame
