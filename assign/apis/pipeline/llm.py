import json
import time
import logging

from google import genai
from django.conf import settings

logger = logging.getLogger(__name__)

VALID_CATEGORIES = {
    'Food', 'Shopping', 'Travel', 'Transport',
    'Utilities', 'Cash Withdrawal', 'Entertainment', 'Other',
}
MAX_RETRIES = 3


def _get_client():
    return genai.Client(api_key=settings.GEMINI_API_KEY)


def _call_with_retry(client, prompt: str) -> str:
    """
    Calls Gemini with exponential backoff on failure.
    Waits 2^attempt seconds before each retry (1s, 2s, 4s).
    Raises on final failure.
    """
    last_err = None
    for attempt in range(MAX_RETRIES):
        try:
            response = client.models.generate_content(
                model='gemini-1.5-flash',
                contents=prompt,
            )
            return response.text
        except Exception as e:
            last_err = e
            if attempt < MAX_RETRIES - 1:
                wait = 2 ** attempt
                logger.warning(f"LLM call failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}. Retrying in {wait}s")
                time.sleep(wait)
    raise last_err


def _strip_fences(text: str) -> str:
    """Remove markdown code fences that Gemini sometimes adds."""
    text = text.strip()
    if text.startswith('```'):
        lines = text.split('\n')
        text = '\n'.join(lines[1:-1]) if lines[-1].strip() == '```' else '\n'.join(lines[1:])
    return text.strip()


def classify_categories(rows: list[dict]) -> list[dict]:
    """
    Batch-classifies transactions with missing categories via Gemini.

    Input:  list of dicts with keys txn_id, merchant, amount, currency
    Output: same list with 'category', 'llm_category', 'llm_raw_response', 'llm_failed' added

    On LLM failure: category='Other', llm_failed=True for all rows in the batch.
    """
    if not rows:
        return rows

    client = _get_client()
    batch_json = json.dumps(
        [{'txn_id': r['txn_id'], 'merchant': r['merchant'],
          'amount': r['amount'], 'currency': r['currency']} for r in rows],
        indent=2
    )

    prompt = f"""You are a financial transaction classifier.
Classify each transaction into exactly one category from this list:
Food, Shopping, Travel, Transport, Utilities, Cash Withdrawal, Entertainment, Other

Rules:
- Swiggy, Zomato → Food
- Amazon, Flipkart → Shopping
- MakeMyTrip, IRCTC → Travel
- Ola → Transport
- Jio Recharge → Utilities
- HDFC ATM → Cash Withdrawal
- BookMyShow → Entertainment
- Unknown merchants → Other

Return ONLY a valid JSON array with no extra text, markdown, or explanation:
[{{"txn_id": "...", "category": "..."}}]

Transactions:
{batch_json}"""

    try:
        raw = _call_with_retry(client, prompt)
        clean_raw = _strip_fences(raw)
        classifications = json.loads(clean_raw)
        cat_map = {item['txn_id']: item.get('category', 'Other') for item in classifications}

        for row in rows:
            cat = cat_map.get(row['txn_id'], 'Other')
            row['category'] = cat if cat in VALID_CATEGORIES else 'Other'
            row['llm_category'] = True
            row['llm_raw_response'] = raw[:2000]
            row['llm_failed'] = False

    except Exception as e:
        logger.error(f"LLM batch classification failed after {MAX_RETRIES} retries: {e}")
        for row in rows:
            row['category'] = 'Other'
            row['llm_category'] = True
            row['llm_raw_response'] = ''
            row['llm_failed'] = True

    return rows


def generate_narrative(summary_data: dict) -> dict:
    """
    Single Gemini call to generate a spending narrative and risk level.

    Input: dict with total_spend_inr, total_spend_usd, top_merchants,
                        anomaly_count, transactions_count
    Output: dict with 'narrative' (str) and 'risk_level' ('low'|'medium'|'high')
    On failure: returns {'narrative': '', 'risk_level': 'low'}.
    """
    client = _get_client()

    prompt = f"""You are a senior financial analyst reviewing a batch of processed transactions.
Based on the summary data below, write a concise 2-3 sentence spending narrative and assign a risk level.

Summary data:
{json.dumps(summary_data, indent=2, default=str)}

Risk level guidelines:
- high: anomaly_count > 5 OR any single transaction exceeds 100,000 INR
- medium: anomaly_count between 2 and 5 OR suspicious USD charges for domestic merchants present
- low: otherwise

Return ONLY valid JSON with no extra text or markdown:
{{
  "narrative": "2-3 sentence analysis here",
  "risk_level": "low"
}}"""

    try:
        raw = _call_with_retry(client, prompt)
        clean_raw = _strip_fences(raw)
        result = json.loads(clean_raw)
        if result.get('risk_level') not in ('low', 'medium', 'high'):
            result['risk_level'] = 'low'
        return result
    except Exception as e:
        logger.error(f"LLM narrative generation failed: {e}")
        return {'narrative': '', 'risk_level': 'low'}
