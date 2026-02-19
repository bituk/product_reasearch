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
from typing import Any, Callable

from creative_research.constants import GEMINI_MODEL
from creative_research.report_generator import fetch_product_page, generate_report
from creative_research.keyword_generator import generate_keywords
from creative_research.scrapers.runner import run_all_scrapes
from creative_research.scraped_data import ScrapedData, VideoItem
from creative_research.video_downloader import download_and_transcript_batch
from creative_research.gemini_analyzer import analyze_videos_batch
from creative_research.script_generator import generate_video_scripts


def run_pipeline_v2(
    product_link: str,
    *,
    model: str = "gpt-4o",
    gemini_model: str | None = None,
    search_queries_override: list[str] | None = None,
    subreddits_override: list[str] | None = None,
    download_videos: bool = True,
    max_videos_total: int = 20,
    max_videos_to_download: int = 5,
    max_videos_to_analyze: int = 5,
    output_dir: Path | str | None = None,
    on_stage: Callable[[str], None] | None = None,
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
        gemini_model: Gemini model for video analysis. Defaults to GEMINI_MODEL from .env.
        search_queries_override: Override search queries.
        subreddits_override: Override subreddits.
        download_videos: If True, download top videos with yt-dlp.
        max_videos_total: Max videos to scrape across all platforms (default 20).
        max_videos_to_download: Max videos to download (default 5).
        max_videos_to_analyze: Max videos to send to Gemini (default 5).
        output_dir: Directory for downloaded videos/transcripts.

    Returns:
        Full result dict including report, scripts, video_analyses, download_results.
    """
    product_link = product_link.strip()
    _stage = on_stage or (lambda _: None)
    gemini_model = gemini_model or GEMINI_MODEL

    result: dict[str, Any] = {
        "product_link": product_link,
        "keywords": {"search_queries": [], "subreddits": []},
        "scraped_data": None,
        "download_results": [],
        "video_analyses": [],
        "report": "",
        "report_popular": "",
        "report_all_videos": "",
        "scripts": "",
    }

    # 1) Fetch product page
    _stage("fetch_product")
    product_page_text = ""
    try:
        product_page_text = fetch_product_page(product_link)
    except Exception:
        pass

    # 2) Keywords
    _stage("keywords")
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
    _stage("video_scrape")
    scraped = run_all_scrapes(
        product_link,
        search_queries=search_queries,
        subreddits=subreddits,
        product_page_text=product_page_text,
    )
    scraped.truncate_videos_to_max(max_total=max_videos_total)
    result["scraped_data"] = scraped

    # Collect video URLs with platform diversity (YouTube, Shorts, TikTok, Instagram)
    videos_for_download = scraped.select_videos_for_analysis(limit=max_videos_to_download)
    video_urls = list(dict.fromkeys(v.url for v in videos_for_download if v.url))

    # 4) Download via yt-dlp + transcript
    _stage("download")
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

    # 5) Gemini video analysis (YouTube URLs; TikTok/Instagram via downloaded files)
    # Ensure participation from all scrapers: YouTube, YouTube Shorts, TikTok, Instagram
    _stage("analysis")
    videos_for_analysis = scraped.select_videos_for_analysis(limit=max_videos_to_analyze)
    # Build path->url mapping from download results (for TikTok/Instagram)
    path_to_url: dict[str, str] = {}
    for r in result.get("download_results", []):
        url = r.get("url", "")
        vpath = r.get("video_path")
        if url and vpath and Path(vpath).exists():
            path_to_url[str(vpath)] = url

    inputs_to_analyze: list[tuple[str, str | Path]] = []  # (url, input_for_gemini)
    for v in videos_for_analysis:
        if not v.url:
            continue
        is_youtube = "youtube.com" in v.url or "youtu.be" in v.url
        if is_youtube:
            inputs_to_analyze.append((v.url, v.url))
        else:
            # TikTok/Instagram: use downloaded file if available
            matched_path = next((p for p, u in path_to_url.items() if u == v.url), None)
            if matched_path:
                inputs_to_analyze.append((v.url, Path(matched_path)))
            # else skip (Gemini doesn't support TikTok/Instagram URLs directly)

    if inputs_to_analyze:
        try:
            gemini_inputs = [inp for _, inp in inputs_to_analyze]
            url_by_input = {str(inp): url for url, inp in inputs_to_analyze}
            analyses = analyze_videos_batch(
                gemini_inputs,
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
                match_url = url_by_input.get(inp)
                if not match_url:
                    match_url = inp  # might be URL if passed as string
                for v in scraped.youtube_videos + scraped.youtube_shorts + scraped.tiktok_videos + scraped.instagram_videos:
                    v_url = (v.url or "").strip()
                    if v_url and (v_url == match_url or match_url == v_url or match_url in v_url or v_url in match_url):
                        v.gemini_analysis = analysis
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
    _stage("report")
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

    # 6b) Build two report variants with Reference Video Details
    def _inject_ref_section(base: str, ref_section: str) -> str:
        if not ref_section:
            return base
        marker = "## 5) 1D"
        if marker in base:
            idx = base.find(marker)
            return base[:idx] + ref_section + "\n---\n\n" + base[idx:]
        return base + "\n\n---\n\n" + ref_section

    # Report 1: Most popular (top 12 by views) + ensure 1-2 from TikTok/Instagram, shorter analysis
    ref_popular = scraped.build_reference_video_section(
        limit=12,
        sort_by_popularity=True,
        section_title="Reference Video Details (Most Popular)",
        ensure_platform_diversity=True,
        max_analysis_lines=12,  # Shorter Gemini analysis
    )
    result["report_popular"] = _inject_ref_section(report, ref_popular)

    # Report 2: All scraped videos (max 25) with full info and shorter analysis
    # ensure_platform_diversity=True so TikTok/Instagram are included when available
    ref_all = scraped.build_reference_video_section(
        limit=25,
        sort_by_popularity=True,
        section_title="Reference Video Details (All Scraped Videos)",
        ensure_platform_diversity=True,
        include_full_info=True,
        show_full_analysis=False,
        max_analysis_lines=12,  # Shorter Gemini analysis (hook, message, CTA, why it works)
    )
    result["report_all_videos"] = _inject_ref_section(report, ref_all)

    # Keep report as popular variant (backward compatible)
    result["report"] = result["report_popular"]

    # 7) Script generation
    _stage("scripts")
    try:
        scripts = generate_video_scripts(
            result["report"],
            scraped_data=scraped,
            video_analyses=result.get("video_analyses", []),
            product_summary=product_page_text[:300] if product_page_text else "",
            model=model,
        )
        result["scripts"] = scripts
    except Exception as e:
        result["scripts"] = f"Error generating scripts: {e}"

    # Append scripts to both report variants
    scripts_block = "\n\n---\n\n# Generated Scripts\n\n" + result["scripts"]
    result["report_popular"] = result["report_popular"] + scripts_block
    result["report_all_videos"] = result["report_all_videos"] + scripts_block
    result["report"] = result["report_popular"]

    return result
