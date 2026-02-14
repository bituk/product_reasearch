"""
Save research data to Google Sheets (free tier).
Writes to 5 tabs: Reddit Comments | YouTube Videos | Amazon Reviews | GPT Insights | Avatars.
Requires: GOOGLE_APPLICATION_CREDENTIALS (service account JSON), RESEARCH_SHEET_ID.
"""

import os
import re
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from creative_research.scraped_data import ScrapedData

# Your 5 sheet (tab) names
SHEET_REDDIT = "Reddit Comments"
SHEET_YOUTUBE = "YouTube Videos"
SHEET_AMAZON = "Amazon Reviews"
SHEET_GPT = "GPT Insights"
SHEET_AVATARS = "Avatars"

ALL_SHEET_NAMES = [SHEET_REDDIT, SHEET_YOUTUBE, SHEET_AMAZON, SHEET_GPT, SHEET_AVATARS]


def has_sheets_credentials(spreadsheet_id: str | None = None) -> bool:
    """Return True if Google Sheets can be used (for minimal-credentials testing, skip when False)."""
    return sheets_skip_reason(spreadsheet_id) is None


def sheets_skip_reason(spreadsheet_id: str | None = None) -> str | None:
    """Return None if Sheets can be used; else a short reason (e.g. for logging)."""
    sid = spreadsheet_id or os.environ.get("RESEARCH_SHEET_ID")
    if not sid or not sid.strip():
        return "RESEARCH_SHEET_ID not set"
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not creds_path.strip():
        return "GOOGLE_APPLICATION_CREDENTIALS not set (set to path of service account JSON)"
    path = Path(creds_path.strip())
    if not path.is_absolute():
        path = Path(os.getcwd()) / path
    if not path.is_file():
        return "GOOGLE_APPLICATION_CREDENTIALS file not found (share Sheet with service account email)"
    return None


def _get_spreadsheet(spreadsheet_id: str | None = None):
    spreadsheet_id = spreadsheet_id or os.environ.get("RESEARCH_SHEET_ID")
    if not spreadsheet_id:
        raise ValueError("RESEARCH_SHEET_ID required. Set in .env (Google Sheet ID from URL)")
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not creds_path or not os.path.isfile(creds_path):
        raise ValueError("GOOGLE_APPLICATION_CREDENTIALS must point to service account JSON file.")
    import gspread
    from google.oauth2.service_account import Credentials
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
    gc = gspread.authorize(creds)
    return gc.open_by_key(spreadsheet_id)


def _get_or_create_worksheet(sh, title: str, headers: list[str]):
    """Get worksheet by title; create and add headers if missing."""
    try:
        ws = sh.worksheet(title)
    except Exception:
        ws = sh.add_worksheet(title=title, rows=200, cols=max(len(headers), 10))
        ws.append_row(headers, value_input_option="USER_ENTERED")
        return ws
    # Ensure headers exist (check row 1)
    try:
        row1 = ws.row_values(1)
        if not row1 and headers:
            ws.append_row(headers, value_input_option="USER_ENTERED")
    except Exception:
        if headers:
            ws.append_row(headers, value_input_option="USER_ENTERED")
    return ws


def save_scraped_data_to_sheets(
    product_link: str,
    scraped_data: "ScrapedData",
    *,
    spreadsheet_id: str | None = None,
) -> str:
    """
    Write scraped data to Google Sheets (database layer).
    Only Reddit Comments | YouTube Videos | Amazon Reviews.
    """
    sh = _get_spreadsheet(spreadsheet_id)
    report_date = datetime.utcnow().strftime("%Y-%m-%d")
    generated_at = datetime.utcnow().isoformat() + "Z"
    written = []

    ws_reddit = _get_or_create_worksheet(
        sh, SHEET_REDDIT,
        ["Product URL", "Report Date", "Author", "Text", "Likes", "Created At"],
    )
    for c in (scraped_data.reddit_posts_and_comments or [])[:500]:
        ws_reddit.append_row([
            product_link, report_date,
            (c.author or "")[:200], (c.text or "")[:50000], c.likes, c.created_at or "",
        ], value_input_option="USER_ENTERED")
    if scraped_data.reddit_posts_and_comments:
        written.append(SHEET_REDDIT)

    ws_yt = _get_or_create_worksheet(
        sh, SHEET_YOUTUBE,
        ["Product URL", "Report Date", "Platform", "Title", "URL", "Views", "Likes", "Comments", "Author", "Published At"],
    )
    all_yt = list(scraped_data.youtube_videos or []) + list(scraped_data.youtube_shorts or [])
    for v in all_yt[:300]:
        ws_yt.append_row([
            product_link, report_date, v.platform, (v.title or "")[:500], (v.url or "")[:2000],
            v.views, v.likes, v.comments_count, (v.author or "")[:200], v.published_at or "",
        ], value_input_option="USER_ENTERED")
    if all_yt:
        written.append(SHEET_YOUTUBE)

    ws_amazon = _get_or_create_worksheet(
        sh, SHEET_AMAZON,
        ["Product URL", "Report Date", "Content", "Generated At"],
    )
    if scraped_data.amazon_reviews_text:
        ws_amazon.append_row([product_link, report_date, scraped_data.amazon_reviews_text[:50000], generated_at], value_input_option="USER_ENTERED")
        written.append(SHEET_AMAZON)
    elif scraped_data.apify_amazon:
        import json as _json
        for item in (scraped_data.apify_amazon or [])[:100]:
            ws_amazon.append_row([product_link, report_date, _json.dumps(item, default=str)[:50000], generated_at], value_input_option="USER_ENTERED")
        written.append(SHEET_AMAZON)

    return f"Saved scraped data to Sheet '{sh.title}': {', '.join(written) or 'no data'}."


def save_analysis_to_sheets(
    product_link: str,
    report_markdown: str,
    *,
    spreadsheet_id: str | None = None,
) -> str:
    """
    Write GPT analysis output to Google Sheets.
    Only GPT Insights | Avatars (Insights + Avatars + Angles).
    """
    sh = _get_spreadsheet(spreadsheet_id)
    report_date = datetime.utcnow().strftime("%Y-%m-%d")
    generated_at = datetime.utcnow().isoformat() + "Z"

    ws_gpt = _get_or_create_worksheet(
        sh, SHEET_GPT,
        ["Product URL", "Report Date", "Report", "Generated At"],
    )
    report_truncated = report_markdown[:50000] if len(report_markdown) > 50000 else report_markdown
    ws_gpt.append_row([product_link, report_date, report_truncated, generated_at], value_input_option="USER_ENTERED")

    ws_avatars = _get_or_create_worksheet(
        sh, SHEET_AVATARS,
        ["Product URL", "Report Date", "Avatars Section", "Generated At"],
    )
    avatars_text = _extract_avatars_section(report_markdown)
    ws_avatars.append_row([product_link, report_date, avatars_text, generated_at], value_input_option="USER_ENTERED")

    return f"Saved analysis to Sheet '{sh.title}': {SHEET_GPT}, {SHEET_AVATARS}."


def _extract_avatars_section(report_markdown: str) -> str:
    """Extract the Avatars (3A) section from the report for the Avatars sheet."""
    # Match from "3A. Avatars" or "Avatars (10" until next ## or end
    m = re.search(
        r"(?:##\s*)?(?:3A\.\s*)?Avatars[^\n]*(?:\n(?!##)[\s\S]*?)(?=\n##|\Z)",
        report_markdown,
        re.IGNORECASE,
    )
    if m:
        return m.group(0).strip()[:50000]
    # Fallback: look for "10 Different Avatars" or "Avatar"
    m2 = re.search(r"(.{0,100}Avatars?[^\n]*\n[\s\S]{500,30000}?)(?=\n##\s*3B|\n##\s*Overview|\Z)", report_markdown, re.IGNORECASE | re.DOTALL)
    if m2:
        return m2.group(1).strip()[:50000]
    return report_markdown[:20000]  # Last resort: first 20k chars


def save_research_to_sheets(
    product_link: str,
    report_markdown: str,
    scraped_data: "ScrapedData | None" = None,
    *,
    spreadsheet_id: str | None = None,
) -> str:
    """
    Write to all 5 sheets: Reddit Comments | YouTube Videos | Amazon Reviews | GPT Insights | Avatars.
    Uses scraped_data for Reddit, YouTube, Amazon; report for GPT Insights and Avatars.
    """
    sh = _get_spreadsheet(spreadsheet_id)
    report_date = datetime.utcnow().strftime("%Y-%m-%d")
    generated_at = datetime.utcnow().isoformat() + "Z"
    written = []

    # --- Reddit Comments ---
    ws_reddit = _get_or_create_worksheet(
        sh, SHEET_REDDIT,
        ["Product URL", "Report Date", "Author", "Text", "Likes", "Created At"],
    )
    if scraped_data and scraped_data.reddit_posts_and_comments:
        for c in scraped_data.reddit_posts_and_comments[:500]:
            ws_reddit.append_row([
                product_link,
                report_date,
                (c.author or "")[:200],
                (c.text or "")[:50000],
                c.likes,
                c.created_at or "",
            ], value_input_option="USER_ENTERED")
        written.append(SHEET_REDDIT)

    # --- YouTube Videos ---
    ws_yt = _get_or_create_worksheet(
        sh, SHEET_YOUTUBE,
        ["Product URL", "Report Date", "Platform", "Title", "URL", "Views", "Likes", "Comments", "Author", "Published At"],
    )
    all_yt = []
    if scraped_data:
        all_yt = list(scraped_data.youtube_videos) + list(scraped_data.youtube_shorts)
    for v in all_yt[:300]:
        ws_yt.append_row([
            product_link,
            report_date,
            v.platform,
            (v.title or "")[:500],
            (v.url or "")[:2000],
            v.views,
            v.likes,
            v.comments_count,
            (v.author or "")[:200],
            v.published_at or "",
        ], value_input_option="USER_ENTERED")
    if all_yt:
        written.append(SHEET_YOUTUBE)

    # --- Amazon Reviews ---
    ws_amazon = _get_or_create_worksheet(
        sh, SHEET_AMAZON,
        ["Product URL", "Report Date", "Content", "Generated At"],
    )
    if scraped_data:
        if scraped_data.amazon_reviews_text:
            content = scraped_data.amazon_reviews_text[:50000]
            ws_amazon.append_row([product_link, report_date, content, generated_at], value_input_option="USER_ENTERED")
            written.append(SHEET_AMAZON)
        elif scraped_data.apify_amazon:
            for item in scraped_data.apify_amazon[:100]:
                import json
                content = json.dumps(item, default=str)[:50000]
                ws_amazon.append_row([product_link, report_date, content, generated_at], value_input_option="USER_ENTERED")
            written.append(SHEET_AMAZON)

    # --- GPT Insights (full report) ---
    ws_gpt = _get_or_create_worksheet(
        sh, SHEET_GPT,
        ["Product URL", "Report Date", "Report", "Generated At"],
    )
    report_truncated = report_markdown[:50000] if len(report_markdown) > 50000 else report_markdown
    ws_gpt.append_row([product_link, report_date, report_truncated, generated_at], value_input_option="USER_ENTERED")
    written.append(SHEET_GPT)

    # --- Avatars (extracted section from report) ---
    ws_avatars = _get_or_create_worksheet(
        sh, SHEET_AVATARS,
        ["Product URL", "Report Date", "Avatars Section", "Generated At"],
    )
    avatars_text = _extract_avatars_section(report_markdown)
    ws_avatars.append_row([product_link, report_date, avatars_text, generated_at], value_input_option="USER_ENTERED")
    written.append(SHEET_AVATARS)

    return f"Saved to Google Sheet '{sh.title}': {', '.join(written)}."


def save_report_to_sheets(
    product_link: str,
    report_markdown: str,
    scraped_data: "ScrapedData | None" = None,
    *,
    spreadsheet_id: str | None = None,
    sheet_name: str | None = None,
) -> str:
    """
    Save research to the 5-sheet layout (Reddit Comments | YouTube Videos | Amazon Reviews | GPT Insights | Avatars).
    If you pass scraped_data, Reddit/YouTube/Amazon sheets are filled; otherwise only GPT Insights and Avatars get the report.
    Legacy: if sheet_name is set (e.g. "Reports"), appends one row to that single sheet instead.
    """
    if sheet_name and sheet_name not in ALL_SHEET_NAMES:
        # Legacy single-sheet append
        spreadsheet_id = spreadsheet_id or os.environ.get("RESEARCH_SHEET_ID")
        if not spreadsheet_id:
            return "Error: RESEARCH_SHEET_ID required. Set in .env"
        try:
            import gspread
            from google.oauth2.service_account import Credentials
            scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
            creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
            if not creds_path or not os.path.isfile(creds_path):
                return "Error: GOOGLE_APPLICATION_CREDENTIALS must point to service account JSON file."
            creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
            gc = gspread.authorize(creds)
            sh = gc.open_by_key(spreadsheet_id)
            ws = sh.worksheet(sheet_name)
            report_date = datetime.utcnow().strftime("%Y-%m-%d")
            summary = report_markdown[:30_000] if len(report_markdown) > 30_000 else report_markdown
            ws.append_row([product_link, report_date, summary, datetime.utcnow().isoformat() + "Z"], value_input_option="USER_ENTERED")
            return f"Saved to Google Sheet '{sh.title}', tab '{sheet_name}'."
        except Exception as e:
            return f"Error saving to Google Sheets: {e}"
    return save_research_to_sheets(product_link, report_markdown, scraped_data, spreadsheet_id=spreadsheet_id)
