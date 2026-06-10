"""Step 0: validate that the raw CSV matches the expected input schema."""

import pandas as pd


class InvalidColumnError(Exception):
    """An error raised when an invalid column was found."""

    def __init__(self, missing: list[str], unexpected: list[str]) -> None:
        """Initialize the exception."""
        super().__init__(
            f"Input columns do not match the expected schema "
            f"(missing={missing}, unexpected={unexpected})"
        )
        self.missing = missing
        self.unexpected = unexpected


def validate_input_columns(
    data_frame: pd.DataFrame, expected_columns: list[str]
) -> None:
    """Raise if the raw CSV columns don't match the expected input schema."""
    actual = set(data_frame.columns)
    expected = set(expected_columns)
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if missing or unexpected:
        raise InvalidColumnError(missing, unexpected)
    print(f"[0] validated {len(expected_columns)} input columns")
