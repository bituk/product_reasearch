"""
Pipeline: Product Link → Keyword Generator (GPT) → Scrapers → Google Sheets (DB) → GPT Analysis → Insights + Avatars + Angles → Final Report.

Architecture:
  1. Product Link (input)
  2. Keyword Generator (GPT) — generates search_queries + subreddits
  3. Scrapers (Reddit / YouTube / Amazon) — use generated keywords
  4. Google Sheets (Database) — persist scraped data (Reddit Comments | YouTube Videos | Amazon Reviews)
  5. GPT Analysis Engine — produces report from product + scraped data
  6. Insights + Avatars + Angles — extracted from report
  7. Final Report — markdown; analysis saved to Sheets (GPT Insights | Avatars)
"""

from typing import Any

from creative_research.report_generator import fetch_product_page
from creative_research.keyword_generator import generate_keywords
from creative_research.scrapers.runner import run_all_scrapes
from creative_research.report_generator import generate_report
from creative_research.storage.sheets_storage import (
    has_sheets_credentials,
    save_scraped_data_to_sheets,
    save_analysis_to_sheets,
    sheets_skip_reason,
)


def run_pipeline(
    product_link: str,
    *,
    model: str = "gpt-4o",
    save_to_sheets: bool = True,
    spreadsheet_id: str | None = None,
    search_queries_override: list[str] | None = None,
    subreddits_override: list[str] | None = None,
) -> dict[str, Any]:
    """
    Run the full pipeline in architecture order.

    Args:
        product_link: Product URL (input).
        model: OpenAI model for keyword generator and analysis.
        save_to_sheets: If True, write scraped data to Sheets (DB) then analysis (Insights + Avatars).
        spreadsheet_id: Optional Sheet ID; else RESEARCH_SHEET_ID from env.
        search_queries_override: If set, skip Keyword Generator and use these queries.
        subreddits_override: If set, skip Keyword Generator for subreddits and use these.

    Returns:
        {
          "product_link": str,
          "keywords": {"search_queries": [...], "subreddits": [...]},
          "scraped_data": ScrapedData,
          "report": str,  # Final Report
          "sheets_scraped": str | None,  # message from save_scraped_data_to_sheets
          "sheets_analysis": str | None,  # message from save_analysis_to_sheets
        }
    """
    product_link = product_link.strip()
    result = {
        "product_link": product_link,
        "keywords": {"search_queries": [], "subreddits": []},
        "scraped_data": None,
        "report": "",
        "sheets_scraped": None,
        "sheets_analysis": None,
    }

    # 1) Fetch product page (for keyword generator + analysis)
    product_page_text = ""
    try:
        product_page_text = fetch_product_page(product_link)
    except Exception:
        pass

    # 2) Keyword Generator (GPT) — use overrides where provided
    if search_queries_override is not None and subreddits_override is not None:
        keywords = {"search_queries": search_queries_override, "subreddits": subreddits_override}
    else:
        keywords = generate_keywords(product_link, product_page_text, model=model)
        if search_queries_override is not None:
            keywords["search_queries"] = search_queries_override
        if subreddits_override is not None:
            keywords["subreddits"] = subreddits_override
    result["keywords"] = keywords
    search_queries = keywords.get("search_queries") or ["product review", "best"]
    subreddits = keywords.get("subreddits") or ["all"]

    # 3) Scrapers (Reddit / YouTube / Amazon)
    scraped = run_all_scrapes(
        product_link,
        search_queries=search_queries,
        subreddits=subreddits,
        product_page_text=product_page_text,
    )
    result["scraped_data"] = scraped

    # 4) Google Sheets (Database) — persist scraped data only (skipped if no credentials)
    if save_to_sheets and has_sheets_credentials(spreadsheet_id):
        try:
            result["sheets_scraped"] = save_scraped_data_to_sheets(product_link, scraped, spreadsheet_id=spreadsheet_id)
        except Exception as e:
            result["sheets_scraped"] = f"Error: {e}"
    elif save_to_sheets:
        reason = sheets_skip_reason(spreadsheet_id) or "no credentials"
        result["sheets_scraped"] = f"Skipped — {reason}. Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON path and share the Sheet with that email."

    # 5) GPT Analysis Engine
    report = generate_report(
        product_link,
        product_page_content=scraped.product_page_text or None,
        scraped_data=scraped,
        model=model,
    )
    result["report"] = report

    # 6) Insights + Avatars + Angles — embedded in report; 7) Final Report
    # 7) Save analysis to Sheets (GPT Insights | Avatars) — skipped if no credentials
    if save_to_sheets and has_sheets_credentials(spreadsheet_id):
        try:
            result["sheets_analysis"] = save_analysis_to_sheets(product_link, report, spreadsheet_id=spreadsheet_id)
        except Exception as e:
            result["sheets_analysis"] = f"Error: {e}"
    elif save_to_sheets:
        reason = sheets_skip_reason(spreadsheet_id) or "no credentials"
        result["sheets_analysis"] = f"Skipped — {reason}. Set GOOGLE_APPLICATION_CREDENTIALS to your service account JSON path and share the Sheet with that email."

    return result
