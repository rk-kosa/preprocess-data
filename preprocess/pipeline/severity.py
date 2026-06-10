"""Step 6: split Injury.Severity into Severity.Category + Fatality.Count."""

import pandas as pd

from preprocess.common import move_columns_after


def _determine_severity(severity: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return boolean masks for fatal / non-fatal / incident rows."""
    fatal = severity.str.match(r"(?i)^Fatal").fillna(False)
    non_fatal = severity.str.fullmatch(r"(?i)non-fatal").fillna(False)
    incident = severity.str.fullmatch(r"(?i)incident").fillna(False)
    return fatal, non_fatal, incident


def _fatality_count(
    severity: pd.Series, non_fatal: pd.Series, incident: pd.Series
) -> pd.Series:
    """Extract N from 'Fatal(N)'; Non-Fatal/Incident -> 0; anything else -> null."""
    return (
        severity.str.extract(r"^Fatal\((\d+)\)$", expand=False)
        .astype("Float64")
        .mask(non_fatal | incident, 0)
        .astype("Int64")
    )


def _severity_category(
    fatal: pd.Series, non_fatal: pd.Series, incident: pd.Series
) -> pd.Series:
    """Collapse severity into 'Fatal' / 'Non-Fatal' / 'Incident' (null stays null)."""
    return (
        pd.Series(pd.NA, index=fatal.index, dtype="string")
        .mask(fatal, "Fatal")
        .mask(non_fatal, "Non-Fatal")
        .mask(incident, "Incident")
    )


def split_severity(data_frame: pd.DataFrame) -> pd.DataFrame:
    """Split Injury.Severity into Severity.Category and a numeric Fatality.Count."""
    severity = data_frame["Injury.Severity"].astype("string").str.strip()
    fatal, non_fatal, incident = _determine_severity(severity)

    data_frame["Fatality.Count"] = _fatality_count(severity, non_fatal, incident)
    data_frame["Severity.Category"] = _severity_category(fatal, non_fatal, incident)
    data_frame = move_columns_after(
        data_frame, "Injury.Severity", ["Severity.Category", "Fatality.Count"]
    )

    print(
        f"[6] severity: Fatal={int(fatal.sum()):,} "
        f"Non-Fatal={int(non_fatal.sum()):,} Incident={int(incident.sum()):,}"
    )
    return data_frame
