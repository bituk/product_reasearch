"""
Save report summary to Airtable (free tier).
Requires AIRTABLE_API_KEY and AIRTABLE_BASE_ID in env. Table name: "Research Reports" or AIRTABLE_TABLE_ID.
"""

import os
from datetime import datetime


def save_report_to_airtable(
    product_link: str,
    report_markdown: str,
    *,
    base_id: str | None = None,
    table_name: str = "Research Reports",
) -> str:
    """
    Append one row to Airtable with product link, date, and report summary (first ~30k chars).
    Returns success message or error string.
    """
    api_key = os.environ.get("AIRTABLE_API_KEY")
    base_id = base_id or os.environ.get("AIRTABLE_BASE_ID")
    if not api_key or not base_id:
        return "Error: AIRTABLE_API_KEY and AIRTABLE_BASE_ID required. Set in .env"
    try:
        from pyairtable import Api
        api = Api(api_key)
        table = api.table(base_id, table_name)
        summary = report_markdown[:30_000] if len(report_markdown) > 30_000 else report_markdown
        table.create({
            "Product URL": product_link,
            "Report Date": datetime.utcnow().strftime("%Y-%m-%d"),
            "Report": summary,
            "Generated At": datetime.utcnow().isoformat() + "Z",
        })
        return f"Saved to Airtable base {base_id}, table '{table_name}'."
    except Exception as e:
        return f"Error saving to Airtable: {e}"
