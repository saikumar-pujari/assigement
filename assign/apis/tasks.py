import logging
from io import StringIO
from decimal import Decimal
from datetime import date

import pandas as pd
from celery import shared_task
from django.utils import timezone

from .models import Job, Transaction, JobSummary
from .pipeline.cleaner import clean
from .pipeline.anomaly import detect_anomalies
from .pipeline.llm import classify_categories, generate_narrative

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=0)
def process_csv(self, job_id: str, csv_content: str, filename: str):
    """
    Full pipeline task. Passed csv_content as a string to avoid
    shared filesystem dependency between api and worker containers.

    State transitions: pending → processing → completed | failed
    """
    try:
        job = Job.objects.get(id=job_id)
        job.status = 'processing'
        job.save(update_fields=['status'])

        # Data Cleaning initially to get row counts and ensure we have valid data to work with 
        df = pd.read_csv(StringIO(csv_content), dtype=str, keep_default_na=False)
        df, raw_count = clean(df)
        job.row_count_raw = raw_count
        job.row_count_clean = len(df)
        job.save(update_fields=['row_count_raw', 'row_count_clean'])

        if df.empty:
            raise ValueError("No valid rows remain after cleaning.")

        # Anomaly Detection before LLM classification to ensure we have anomalies flagged even if LLM fails or is not needed 
        df = detect_anomalies(df)

        # LLM Category Classification 
        uncategorised_mask = df['category'] == 'Uncategorised'
        if uncategorised_mask.any():
            rows_for_llm = df[uncategorised_mask][
                ['txn_id', 'merchant', 'amount', 'currency']
            ].to_dict('records')

            classified = classify_categories(rows_for_llm)
            cat_map = {r['txn_id']: r for r in classified}

            for idx in df[uncategorised_mask].index:
                tid = df.at[idx, 'txn_id']
                mapped = cat_map.get(tid, {})
                df.at[idx, 'category'] = mapped.get('category', 'Other')
                df.at[idx, 'llm_category'] = mapped.get('llm_category', False)
                df.at[idx, 'llm_raw_response'] = mapped.get('llm_raw_response', '')
                df.at[idx, 'llm_failed'] = mapped.get('llm_failed', False)

        # Ensure LLM columns exist for rows that didn't go through LLM classification (e.g. already had category or were dropped during cleaning)
        for col, default in [('llm_category', False), ('llm_raw_response', ''), ('llm_failed', False)]:
            if col not in df.columns:
                df[col] = default

        # Persist Transactions 
        transactions = []
        for _, row in df.iterrows():
            transactions.append(Transaction(
                job=job,
                txn_id=str(row['txn_id']),
                date=date.fromisoformat(str(row['date'])),
                merchant=str(row['merchant']),
                amount=Decimal(str(row['amount'])),
                currency=str(row['currency']),
                status=str(row['status']),
                category=str(row['category']),
                account_id=str(row.get('account_id', '')),
                is_anomaly=bool(row.get('is_anomaly', False)),
                anomaly_reason=str(row.get('anomaly_reason', '')),
                llm_category=bool(row.get('llm_category', False)),
                llm_raw_response=str(row.get('llm_raw_response', '')),
                llm_failed=bool(row.get('llm_failed', False)),
            ))

        Transaction.objects.bulk_create(transactions, batch_size=200)
        logger.info(f"Job {job_id}: persisted {len(transactions)} transactions.")

        # Compute Summary Statistics  
        df['amount_float'] = df['amount'].astype(float)

        inr_total = float(df[df['currency'] == 'INR']['amount_float'].sum())
        usd_total = float(df[df['currency'] == 'USD']['amount_float'].sum())

        top_merchants = (
            df.groupby('merchant')['amount_float']
            .sum()
            .nlargest(3)
            .reset_index()
            .rename(columns={'amount_float': 'total_amount'})
            .to_dict('records')
        )
        # Round for cleaner JSON
        for m in top_merchants:
            m['total_amount'] = round(m['total_amount'], 2)

        anomaly_count = int(df['is_anomaly'].sum())

        # Compute LLM Narrative Summary
        narrative_input = {
            'total_spend_inr': round(inr_total, 2),
            'total_spend_usd': round(usd_total, 2),
            'top_merchants': top_merchants,
            'anomaly_count': anomaly_count,
            'transactions_count': len(df),
        }
        narrative_result = generate_narrative(narrative_input)

        JobSummary.objects.create(
            job=job,
            total_spend_inr=Decimal(str(round(inr_total, 2))),
            total_spend_usd=Decimal(str(round(usd_total, 2))),
            top_merchants=top_merchants,
            anomaly_count=anomaly_count,
            narrative=narrative_result.get('narrative', ''),
            risk_level=narrative_result.get('risk_level', 'low'),
        )

        # Finalize  
        job.status = 'completed'
        job.completed_at = timezone.now()
        job.save(update_fields=['status', 'completed_at'])
        logger.info(f"Job {job_id} completed: {len(df)} clean rows, {anomaly_count} anomalies.")

    except Exception as e:
        logger.exception(f"Job {job_id} failed: {e}")
        try:
            job = Job.objects.get(id=job_id)
            job.status = 'failed'
            job.error_message = str(e)
            job.completed_at = timezone.now()
            job.save(update_fields=['status', 'error_message', 'completed_at'])
        except Exception:
            pass
