import pandas as pd


DOMESTIC_ONLY_MERCHANTS = {
    'Swiggy', 'Ola', 'IRCTC', 'Zomato',
    'Jio Recharge', 'HDFC ATM',
}


def detect_anomalies(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds is_anomaly (bool) and anomaly_reason (str) columns.

    Rule 1 — Statistical outlier: amount > 3 × per-account median.
    Rule 2 — Currency mismatch: USD charge for a domestic-only merchant.

    A row can trigger both rules; reasons are joined with '; '.
    """
    df = df.copy()
    df['is_anomaly'] = False
    df['anomaly_reason'] = ''

    # Rule 1: per-account_id median
    df['amount_float'] = df['amount'].astype(float)
    account_medians = df.groupby('account_id')['amount_float'].median()

    for idx, row in df.iterrows():
        median = account_medians.get(row['account_id'], row['amount_float'])
        if median > 0 and row['amount_float'] > 3 * median:
            df.at[idx, 'is_anomaly'] = True
            df.at[idx, 'anomaly_reason'] = (
                f"Amount {row['amount_float']:.2f} exceeds 3x account median ({median:.2f})"
            )

    # Rule 2: USD charge for domestic-only merchant
    usd_domestic_mask = df['currency'].eq('USD') & df['merchant'].isin(DOMESTIC_ONLY_MERCHANTS)
    for idx in df[usd_domestic_mask].index:
        merchant = df.at[idx, 'merchant']
        reason = f"USD charge for domestic-only merchant '{merchant}'"
        existing = df.at[idx, 'anomaly_reason']
        df.at[idx, 'is_anomaly'] = True
        df.at[idx, 'anomaly_reason'] = f"{existing}; {reason}" if existing else reason

    df = df.drop(columns=['amount_float'])
    return df
