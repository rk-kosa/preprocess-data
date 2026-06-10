"""Step 4: normalize text capitalization across name/code columns."""

import pandas as pd

COMMA = ","
MAX_SPLIT_LOCATION = 1
STATE_CODE_LEN = 2  # length of a US-style 2-letter state/region suffix
TITLE_COLS = ["Make", "Airport.Name"]
TO_UPPER_COLS = ["Model", "Airport.Code", "Registration.Number"]


def _fix_location(location: object) -> object:
    """Title-case the city, keep a trailing 2-letter state/region code upper."""
    if not isinstance(location, str):
        return location

    location = location.strip()
    if COMMA in location:
        city, region = location.rsplit(COMMA, MAX_SPLIT_LOCATION)
        region = (
            stripped.upper()
            if len(stripped := region.strip()) == STATE_CODE_LEN and stripped.isalpha()
            else stripped.title()
        )
        return f"{city.strip().title()}, {region}"
    return location.title()


def fix_casing(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Normalize capitalization: title names, upper codes, 'City, ST' location."""
    for column in TITLE_COLS:
        if column in data_frame.columns:
            data_frame[column] = data_frame[column].str.strip().str.title()

    for column in TO_UPPER_COLS:
        if column in data_frame.columns:
            data_frame[column] = data_frame[column].str.strip().str.upper()

    if "Location" in data_frame.columns:
        data_frame["Location"] = data_frame["Location"].map(_fix_location)

    print(f"[4] casing: title={TITLE_COLS}, upper={TO_UPPER_COLS}, Location normalized")
    return data_frame
