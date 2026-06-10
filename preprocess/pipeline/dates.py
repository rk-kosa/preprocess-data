"""Step 3: normalize the date columns to ISO 'YYYY-MM-DD'."""

import pandas as pd

DATE_FORMATS = {"Event.Date": "%Y-%m-%d", "Publication.Date": "%d/%m/%Y"}


def fix_dates(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Rewrite the two date columns as ISO 'YYYY-MM-DD' (bad values -> empty)."""
    for column, date_format in DATE_FORMATS.items():
        parsed = pd.to_datetime(data_frame[column], format=date_format, errors="coerce")
        data_frame[column] = parsed.dt.strftime("%Y-%m-%d")  # NaT -> empty on write
        print(f"[3] {column}: parsed {parsed.notna().sum():,} as {date_format} -> ISO")
    return data_frame
