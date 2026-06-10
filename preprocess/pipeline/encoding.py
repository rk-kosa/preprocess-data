"""Step 10: repair corrupted foreign place/airport names."""

import pandas as pd

HIGH_BYTE = 0x80  # first non-ASCII byte, flags latin-1 mojibake
REPLACEMENT_MARKER = "?"


def _has_non_ascii_byte(text: object) -> bool:
    return isinstance(text, str) and any(ord(c) >= HIGH_BYTE for c in text)


def _contains_replacement(text: object) -> bool:
    """Return True if the value is a string carrying a lossy '?' replacement."""
    return isinstance(text, str) and REPLACEMENT_MARKER in text


def _is_corrupted(text: object) -> bool:
    """Return True for a cell corrupted by either mojibake or a lossy '?'."""
    return _has_non_ascii_byte(text) or _contains_replacement(text)


def _fix_corrupted(
    data_frame: pd.DataFrame, corrections: dict[tuple[str, str], str]
) -> tuple[int, list[tuple[str, str, object]]]:
    """Apply the correction map in place.

    Each unhandled cell is (accident_number, column, original_value) for a
    corrupted cell that has no entry in the correction map.

    return: a tuple of fixed count and unhandled cells
    """
    fixed_count = 0
    unhandled: list[tuple[str, str, object]] = []
    for column in data_frame.columns:
        corrupted = data_frame[column].map(_is_corrupted)
        for idx in data_frame.index[corrupted]:
            accident_number = (data_frame.at[idx, "Accident.Number"], column)
            if accident_number in corrections:
                data_frame.at[idx, column] = corrections[accident_number]
                fixed_count += 1
            else:
                unhandled.append(
                    (accident_number[0], column, data_frame.at[idx, column])
                )
    return fixed_count, unhandled


def fix_encoding(
    data_frame: pd.DataFrame, corrections: dict[tuple[str, str], str]
) -> pd.DataFrame:
    """Restore diacritics in corrupted foreign names using the correction map."""
    fixed_count, unhandled = _fix_corrupted(data_frame, corrections)
    if unhandled:
        for accident, column, name in unhandled:
            print(f"No correction found for: {accident} [{column}] {name!r}")
        raise ValueError(
            f"{len(unhandled)} corrupted cell(s) have NO correction - aborting"
        )
    print(f"[10] encoding: applied {fixed_count} corrections")
    return data_frame
