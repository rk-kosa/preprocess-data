"""Step 7: fill blank injury counts with 0 (except genuinely all-blank rows)."""

import pandas as pd

INJURY_COLS = [
    "Total.Fatal.Injuries",
    "Total.Serious.Injuries",
    "Total.Minor.Injuries",
    "Total.Uninjured",
]


def fill_injuries(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Fill blank injury counts with 0, leaving genuinely all-blank rows null."""
    all_null = data_frame[INJURY_COLS].isna().all(axis=1)
    fillable = ~all_null
    for column in INJURY_COLS:
        data_frame.loc[fillable, column] = data_frame.loc[fillable, column].fillna(0)
        data_frame[column] = data_frame[column].astype("Int64")
    print(
        f"[7] injuries: filled blanks with 0, "
        f"left {int(all_null.sum()):,} all-null rows"
    )
    return data_frame
