import re
import uuid
import pandas as pd
from dateutil import parser as dateparser


VALID_CURRENCIES = {'INR', 'USD'}
VALID_STATUSES = {'SUCCESS', 'FAILED', 'PENDING'}


def _parse_date(val) -> str | None:
    """
    Handles DD-MM-YYYY, YYYY/MM/DD, YYYY-MM-DD.
    DD-MM-YYYY: first segment is 2 chars → use dayfirst=True.
    Others: dayfirst=False to avoid MDY ambiguity.
    Returns ISO 8601 (YYYY-MM-DD) string or None.
    """
    if not val or pd.isna(val):
        return None
    val = str(val).strip()
    parts = re.split(r'[-/]', val)
    if len(parts) != 3:
        return None
    dayfirst = len(parts[0]) == 2
    try:
        return dateparser.parse(val, dayfirst=dayfirst).date().isoformat()
    except (ValueError, OverflowError):
        return None


def _clean_amount(val) -> float | None:
    """Strip leading $ and whitespace, cast to float."""
    s = str(val).strip().lstrip('$').strip()
    try:
        f = float(s)
        return f if f > 0 else None
    except ValueError:
        return None


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
    """
    Cleans the raw transaction DataFrame.
    Returns (cleaned_df, raw_row_count).
    """
    raw_count = len(df)

    # Strip whitespace from all string columns
    df = df.apply(lambda col: col.str.strip() if col.dtype == object else col)

    # txn_id: generate UUID for blank rows
    df['txn_id'] = df['txn_id'].apply(
        lambda x: str(x) if pd.notna(x) and str(x).strip() else str(uuid.uuid4())
    )

    # date: normalize to ISO 8601
    df['date'] = df['date'].apply(_parse_date)
    df = df.dropna(subset=['date'])

    # amount: strip $ and cast
    df['amount'] = df['amount'].apply(_clean_amount)
    df = df.dropna(subset=['amount'])

    # currency: uppercase, keep only INR/USD
    df['currency'] = df['currency'].str.upper()
    df = df[df['currency'].isin(VALID_CURRENCIES)]

    # status: uppercase, keep only valid values
    df['status'] = df['status'].str.upper()
    df = df[df['status'].isin(VALID_STATUSES)]

    # category: fill blank with 'Uncategorised'
    df['category'] = df['category'].fillna('').str.strip()
    df['category'] = df['category'].apply(lambda x: x if x else 'Uncategorised')

    # account_id: fill blank
    df['account_id'] = df['account_id'].fillna('').str.strip()

    # notes: fill blank (not stored in DB but used during processing)
    if 'notes' in df.columns:
        df['notes'] = df['notes'].fillna('')

    # Remove exact duplicate rows (all columns match)
    df = df.drop_duplicates()
    df = df.reset_index(drop=True)

    return df, raw_count
