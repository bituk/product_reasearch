# Storage: Google Sheets, Airtable

from creative_research.storage.airtable_storage import save_report_to_airtable
from creative_research.storage.sheets_storage import (
    has_sheets_credentials,
    save_report_to_sheets,
    save_research_to_sheets,
    save_scraped_data_to_sheets,
    save_analysis_to_sheets,
)

__all__ = [
    "has_sheets_credentials",
    "save_report_to_airtable",
    "save_report_to_sheets",
    "save_research_to_sheets",
    "save_scraped_data_to_sheets",
    "save_analysis_to_sheets",
]
