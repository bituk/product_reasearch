"""
Pipeline v2: Research doc → Video scrape → Download (yt-dlp) → Analysis (Gemini) → Competitor research → LLM generation → Scripts.

Full orchestration with:
- Video scraped links
- Download via yt-dlp + transcript extraction
- Gemini multimodal video analysis
- Reference video stats (views, likes, comments, shares, CTA)
- LLM-generated scripts from research + analysis
"""

from pathlib import Path
from typing import Any

from creative_research.report_generator import fetch_product_page, generate_report
from creative_research.keyword_generator import generate_keywords
from creative_research.scrapers.runner import run_all_scrapes
from creative_research.scraped_data import ScrapedData, VideoItem
from creative_research.video_downloader import download_and_transcript_batch
from creative_research.gemini_analyzer import analyze_videos_batch
from creative_research.script_generator import generate_video_scripts
from creative_research.storage.sheets_storage import (
    has_sheets_credentials,
    save_scraped_data_to_sheets,
    save_analysis_to_sheets,
    sheets_skip_reason,
)


def run_pipeline_v2(
    product_link: str,
    *,
    model: str = "gpt-4o",
    gemini_model: str = "gemini-1.5-flash",
    save_to_sheets: bool = True,
    spreadsheet_id: str | None = None,
    search_queries_override: list[str] | None = None,
    subreddits_override: list[str] | None = None,
    download_videos: bool = True,
    max_videos_to_download: int = 5,
    max_videos_to_analyze: int = 5,
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    """
    Run the full v2 pipeline:
    1. Research doc (product fetch + keywords)
    2. Video scrape (YouTube, TikTok, Instagram, Reddit, Apify)
    3. Download videos via yt-dlp + extract transcripts
    4. Analyze videos with Gemini
    5. Competitor research (Tavily)
    6. LLM report generation
    7. Script generation from research + analysis

    Args:
        product_link: Product URL.
        model: OpenAI model for keywords, report, scripts.
        gemini_model: Gemini model for video analysis.
        save_to_sheets: Whether to persist to Google Sheets.
        spreadsheet_id: Optional Sheet ID.
        search_queries_override: Override search queries.
        subreddits_override: Override subreddits.
        download_videos: If True, download top videos with yt-dlp.
        max_videos_to_download: Max videos to download (default 5).
        max_videos_to_analyze: Max videos to send to Gemini (default 5).
        output_dir: Directory for downloaded videos/transcripts.

    Returns:
        Full result dict including report, scripts, video_analyses, download_results.
    """
    product_link = product_link.strip()
    result: dict[str, Any] = {
        "product_link": product_link,
        "keywords": {"search_queries": [], "subreddits": []},
        "scraped_data": None,
        "download_results": [],
        "video_analyses": [],
        "report": "",
        "scripts": "",
        "sheets_scraped": None,
        "sheets_analysis": None,
    }

    # 1) Fetch product page
    product_page_text = ""
    try:
        product_page_text = fetch_product_page(product_link)
    except Exception:
        pass

    # 2) Keywords
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

    # 3) Video scrape
    scraped = run_all_scrapes(
        product_link,
        search_queries=search_queries,
        subreddits=subreddits,
        product_page_text=product_page_text,
    )
    result["scraped_data"] = scraped

    # Collect video URLs (YouTube first, then TikTok, Instagram)
    video_urls: list[str] = []
    for v in scraped.youtube_videos + scraped.youtube_shorts:
        if v.url and v.url not in video_urls:
            video_urls.append(v.url)
    for v in scraped.tiktok_videos + scraped.instagram_videos:
        if v.url and v.url not in video_urls:
            video_urls.append(v.url)
    video_urls = video_urls[:max_videos_to_download]

    # 4) Download via yt-dlp + transcript
    if download_videos and video_urls:
        out_dir = Path(output_dir or Path.cwd() / "downloads" / "videos")
        try:
            dl_results = download_and_transcript_batch(video_urls, out_dir)
            result["download_results"] = dl_results
            # Enrich VideoItems with transcripts
            for r in dl_results:
                url = r.get("url", "")
                transcript = r.get("transcript", "")
                if url and transcript:
                    for v in scraped.youtube_videos + scraped.youtube_shorts + scraped.tiktok_videos + scraped.instagram_videos:
                        if v.url == url:
                            v.transcript = transcript
                            break
        except Exception as e:
            result["download_results"] = [{"error": str(e)}]

    # 5) Gemini video analysis (use URLs directly - no download needed for Gemini)
    urls_to_analyze = video_urls[:max_videos_to_analyze]
    if urls_to_analyze:
        try:
            analyses = analyze_videos_batch(
                urls_to_analyze,
                product_context=product_page_text[:500] or product_link,
                model=gemini_model,
            )
            result["video_analyses"] = analyses
            # Enrich VideoItems with gemini_analysis and cta_summary
            for a in analyses:
                inp = a.get("input", "").strip()
                analysis = a.get("analysis", "") or ""
                if not inp or not analysis:
                    continue
                for v in scraped.youtube_videos + scraped.youtube_shorts + scraped.tiktok_videos + scraped.instagram_videos:
                    v_url = (v.url or "").strip()
                    if v_url and (v_url == inp or inp in v_url or v_url in inp):
                        v.gemini_analysis = analysis
                        # Extract CTA from Gemini analysis (look for CTA / Call-to-Action section)
                        cta_candidates = []
                        for line in analysis.split("\n"):
                            line = line.strip().strip("-*: ")
                            if not line:
                                continue
                            if "CTA" in line or "call-to-action" in line.lower() or "call to action" in line.lower():
                                cta_candidates.append(line[:200])
                            elif "**CTA**" in line or "**Call-to-Action**" in line:
                                cta_candidates.append(line[:200])
                        v.cta_summary = cta_candidates[0] if cta_candidates else ""
                        break
        except Exception as e:
            result["video_analyses"] = [{"error": str(e)}]

    # 6) LLM report generation
    report = generate_report(
        product_link,
        product_page_content=scraped.product_page_text or None,
        scraped_data=scraped,
        model=model,
        has_enriched_videos=any(
            v.transcript or v.gemini_analysis
            for v in scraped.youtube_videos + scraped.youtube_shorts
            + scraped.tiktok_videos + scraped.instagram_videos
        ),
    )
    result["report"] = report

    # 6b) Inject Reference Video Details (scraped links, stats, transcripts, CTA, Gemini analysis)
    ref_section = scraped.build_reference_video_section(limit=10)
    if ref_section:
        # Insert after "## 4) 1B. Video Scrapes" or "## 1B. Video Scrapes", before "## 5) 1D"
        marker = "## 5) 1D"
        if marker in report:
            idx = report.find(marker)
            result["report"] = report[:idx] + ref_section + "\n---\n\n" + report[idx:]
        else:
            result["report"] = report + "\n\n---\n\n" + ref_section

    # 7) Script generation
    try:
        scripts = generate_video_scripts(
            report,
            scraped_data=scraped,
            video_analyses=result.get("video_analyses", []),
            product_summary=product_page_text[:300] if product_page_text else "",
            model=model,
        )
        result["scripts"] = scripts
    except Exception as e:
        result["scripts"] = f"Error generating scripts: {e}"

    # Sheets persistence
    if save_to_sheets and has_sheets_credentials(spreadsheet_id):
        try:
            result["sheets_scraped"] = save_scraped_data_to_sheets(
                product_link, scraped, spreadsheet_id=spreadsheet_id
            )
        except Exception as e:
            result["sheets_scraped"] = f"Error: {e}"
        try:
            combined = report + "\n\n---\n\n## Generated Scripts\n\n" + result.get("scripts", "")
            result["sheets_analysis"] = save_analysis_to_sheets(
                product_link, combined, spreadsheet_id=spreadsheet_id
            )
        except Exception as e:
            result["sheets_analysis"] = f"Error: {e}"
    elif save_to_sheets:
        reason = sheets_skip_reason(spreadsheet_id) or "no credentials"
        result["sheets_scraped"] = f"Skipped — {reason}"
        result["sheets_analysis"] = f"Skipped — {reason}"

    return result
