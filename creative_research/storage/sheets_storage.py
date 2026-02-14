"""
Google Sheets storage for scraped data and analysis.
Requires GOOGLE_APPLICATION_CREDENTIALS and RESEARCH_SHEET_ID.
"""

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from creative_research.scraped_data import ScrapedData


def has_sheets_credentials(spreadsheet_id: str | None = None) -> bool:
    """Check if Google Sheets credentials are configured."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    sheet_id = spreadsheet_id or os.environ.get("RESEARCH_SHEET_ID")
    return bool(creds_path and os.path.exists(creds_path) and sheet_id)


def sheets_skip_reason(spreadsheet_id: str | None = None) -> str | None:
    """Return reason why Sheets would be skipped."""
    creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    sheet_id = spreadsheet_id or os.environ.get("RESEARCH_SHEET_ID")
    if not creds_path:
        return "GOOGLE_APPLICATION_CREDENTIALS not set"
    if not os.path.exists(creds_path):
        return f"Credentials file not found: {creds_path}"
    if not sheet_id:
        return "RESEARCH_SHEET_ID not set"
    return None


def save_scraped_data_to_sheets(
    product_link: str,
    scraped_data: "ScrapedData",
    *,
    spreadsheet_id: str | None = None,
) -> str:
    """Save scraped data to Google Sheets. Returns status message."""
    if not has_sheets_credentials(spreadsheet_id):
        return "Skipped — no credentials"
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        sheet_id = spreadsheet_id or os.environ.get("RESEARCH_SHEET_ID")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        # Use first sheet or create "Scraped" tab
        try:
            ws = sh.worksheet("Scraped")
        except Exception:
            ws = sh.sheet1
        # Append summary
        rows = [[product_link[:80], "Scraped", str(len(scraped_data.youtube_videos) + len(scraped_data.tiktok_videos))]]
        ws.append_rows(rows, value_input_option="RAW")
        return f"Saved to {sh.title}"
    except Exception as e:
        return f"Error: {e}"


def save_analysis_to_sheets(
    product_link: str,
    report: str,
    *,
    spreadsheet_id: str | None = None,
) -> str:
    """Save report/analysis to Google Sheets. Returns status message."""
    if not has_sheets_credentials(spreadsheet_id):
        return "Skipped — no credentials"
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        creds_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        sheet_id = spreadsheet_id or os.environ.get("RESEARCH_SHEET_ID")
        scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_file(creds_path, scopes=scopes)
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        try:
            ws = sh.worksheet("Analysis")
        except Exception:
            ws = sh.sheet1
        ws.update_acell("A1", product_link[:80])
        ws.update_acell("A2", report[:50000])
        return f"Saved to {sh.title}"
    except Exception as e:
        return f"Error: {e}"
