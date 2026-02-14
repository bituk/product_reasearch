"""
MCP server exposing the Creative Research Report as tools.
Orchestration: Research doc → Video scrape → Download → Analysis → Competitor research → LLM generation → Scripts.

Run with: uv run --with mcp creative_research/mcp_server.py
Or: python -m creative_research.mcp_server
"""

import json
import os
from pathlib import Path

from mcp.server.fastmcp import FastMCP

from creative_research.report_generator import generate_report

mcp = FastMCP(
    "Creative Research Report",
    json_response=True,
)


@mcp.tool()
def generate_creative_research_report(
    product_link: str,
    output_path: str | None = None,
    model: str = "gpt-4o",
) -> str:
    """Generate a full Creative Agency Research Report from a product URL.

    Fetches the product page, then uses an LLM to produce a structured report including:
    - Report cover and product summary
    - Step 1: Videos analysis (hashtags, video scrape strategy, competitors, ad library links, organic concepts)
    - Step 2: Comments analysis (scrape strategy, thematic clusters, verbatim comment banks)
    - Step 3: Avatar angles (10 avatars, top 10 selling points, 10 core desires, 10 pain problems)

    Args:
        product_link: Full URL of the product (e.g. Amazon, brand site, Shopify).
        output_path: Optional path to save the report Markdown file. If not set, report is returned as text.
        model: OpenAI model to use (default: gpt-4o).

    Returns:
        The full report in Markdown, or a message that the report was saved to output_path.
    """
    if not product_link or not product_link.strip():
        return "Error: product_link is required and cannot be empty."

    try:
        report = generate_report(
            product_link.strip(),
            product_page_content=None,
            model=model,
        )
    except ValueError as e:
        return f"Error: {e}"
    except Exception as e:
        return f"Error generating report: {e}"

    if output_path and output_path.strip():
        path = Path(output_path.strip())
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(report, encoding="utf-8")
        return f"Report saved to {path.absolute()} ({len(report)} characters)."

    return report


@mcp.tool()
def run_full_research_pipeline(
    product_link: str = "",
    output_path: str | None = None,
    download_videos: bool = True,
    max_videos_to_download: int = 5,
    max_videos_to_analyze: int = 5,
    model: str = "gpt-4o",
) -> str:
    """Run the full pipeline: Research doc → Video scrape → Download (yt-dlp) → Analysis (Gemini) → Competitor research → LLM generation → Scripts.

    Orchestrates:
    1. Video scrape (YouTube, TikTok, Instagram, Reddit, Apify)
    2. Download videos via yt-dlp + extract transcripts
    3. Analyze videos with Gemini (hooks, CTAs, format, engagement)
    4. Competitor research (Tavily)
    5. LLM report generation with reference video stats (views, likes, comments, shares, CTA)
    6. LLM script generation from research + video analysis

    Args:
        product_link: Full URL of the product.
        output_path: Optional path to save report + scripts Markdown.
        download_videos: If True, download top videos with yt-dlp.
        max_videos_to_download: Max videos to download (default 5).
        max_videos_to_analyze: Max videos to analyze with Gemini (default 5).
        model: OpenAI model for report and scripts.

    Returns:
        JSON summary with report, scripts, video_analyses, download_results.
    """
    product_link = (product_link or os.environ.get("PRODUCT_URL") or "").strip()
    if not product_link:
        return json.dumps({"error": "product_link or PRODUCT_URL in .env is required"})

    try:
        from creative_research.pipeline_v2 import run_pipeline_v2
        result = run_pipeline_v2(
            product_link.strip(),
            model=model,
            download_videos=download_videos,
            max_videos_to_download=max_videos_to_download,
            max_videos_to_analyze=max_videos_to_analyze,
            save_to_sheets=False,
        )
        # Serialize for JSON (remove non-serializable)
        out = {
            "product_link": result["product_link"],
            "report": result["report"],
            "scripts": result["scripts"],
            "video_analyses": [
                {"input": a.get("input"), "analysis": a.get("analysis"), "error": a.get("error")}
                for a in result.get("video_analyses", [])
            ],
            "download_results": [
                {"url": d.get("url"), "success": d.get("success"), "transcript": (d.get("transcript") or "")[:50] + "..." if d.get("transcript") else None}
                for d in result.get("download_results", [])
            ],
        }
        if output_path and output_path.strip():
            path = Path(output_path.strip())
            path.parent.mkdir(parents=True, exist_ok=True)
            content = f"# Creative Research Report\n\n{result['report']}\n\n---\n\n# Generated Scripts\n\n{result['scripts']}"
            path.write_text(content, encoding="utf-8")
            out["saved_to"] = str(path.absolute())
        return json.dumps(out, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def download_videos_and_extract_transcripts(
    video_urls: list[str],
    output_dir: str | None = None,
) -> str:
    """Download videos via yt-dlp and extract transcripts/scripts.

    Args:
        video_urls: List of video URLs (YouTube, TikTok, etc.).
        output_dir: Directory for downloaded files. Default: ./downloads/videos

    Returns:
        JSON with list of {url, success, video_path, transcript, error}.
    """
    try:
        from creative_research.video_downloader import download_and_transcript_batch
        out = Path(output_dir or "./downloads/videos")
        results = download_and_transcript_batch(video_urls, out)
        return json.dumps([
            {"url": r.get("url"), "success": r.get("success"), "video_path": r.get("video_path"), "transcript": r.get("transcript"), "error": r.get("error")}
            for r in results
        ], indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def analyze_videos_with_gemini(
    video_urls: list[str],
    product_context: str = "",
    model: str = "gemini-1.5-flash",
) -> str:
    """Analyze videos with Gemini for creative insights (hooks, CTAs, format, engagement).

    Args:
        video_urls: List of YouTube URLs (Gemini supports YouTube URLs directly).
        product_context: Optional product/category context.
        model: Gemini model (gemini-1.5-flash, gemini-1.5-pro).

    Returns:
        JSON with list of {input, analysis, error}.
    """
    try:
        from creative_research.gemini_analyzer import analyze_videos_batch
        results = analyze_videos_batch(
            video_urls,
            product_context=product_context,
            model=model,
        )
        return json.dumps(results, indent=2)
    except Exception as e:
        return json.dumps({"error": str(e)})


@mcp.tool()
def generate_video_scripts_from_research(
    research_report: str,
    video_analyses_json: str = "[]",
    product_summary: str = "",
    model: str = "gpt-4o",
) -> str:
    """Generate video scripts from research report + Gemini video analyses.

    Args:
        research_report: Full or excerpt of the Creative Research Report.
        video_analyses_json: JSON array of {input, analysis} from analyze_videos_with_gemini.
        product_summary: Optional one-line product summary.
        model: OpenAI model.

    Returns:
        Markdown with 3 generated scripts (platform, format, hook, full script, CTA).
    """
    try:
        from creative_research.script_generator import generate_video_scripts
        analyses = json.loads(video_analyses_json) if video_analyses_json else []
        return generate_video_scripts(
            research_report,
            video_analyses=analyses,
            product_summary=product_summary,
            model=model,
        )
    except Exception as e:
        return f"Error: {e}"


@mcp.resource("creative-research://outline")
def get_outline() -> str:
    """Return the Creative Research Report outline (structure and section descriptions)."""
    outline_path = Path(__file__).resolve().parent.parent / "CREATIVE_RESEARCH_REPORT_OUTLINE.md"
    if outline_path.exists():
        return outline_path.read_text(encoding="utf-8")
    return "Outline file not found."


@mcp.prompt()
def research_report_prompt(product_link: str) -> str:
    """Prompt template to generate a Creative Research Report for a product.

    Use this with an LLM or the generate_creative_research_report tool.
    """
    return (
        f"Generate a full Creative Agency Research Report for this product: {product_link}\n\n"
        "Use the tool generate_creative_research_report with this product_link to get "
        "the complete report (videos analysis, comments analysis, avatars, selling points, "
        "desires, pain points). Alternatively, follow the outline in the creative-research://outline resource."
    )


@mcp.prompt()
def full_pipeline_prompt(product_link: str) -> str:
    """Prompt template to run the full research pipeline: Research doc → Video scrape → Download → Analysis → Competitor research → LLM generation → Scripts.

    Use run_full_research_pipeline for end-to-end orchestration, or call individual tools:
    - generate_creative_research_report (or pipeline with scrapers)
    - download_videos_and_extract_transcripts
    - analyze_videos_with_gemini
    - generate_video_scripts_from_research
    """
    return (
        f"Run the full Creative Research pipeline for: {product_link}\n\n"
        "Use run_full_research_pipeline to get: report, video scripts, Gemini analyses, "
        "reference video stats (views, likes, comments, CTA), and generated scripts."
    )


if __name__ == "__main__":
    # Default: stdio for Cursor/Claude Desktop; use CREATIVE_RESEARCH_MCP_HTTP=1 for HTTP
    if os.environ.get("CREATIVE_RESEARCH_MCP_HTTP"):
        mcp.run(transport="streamable-http")
    else:
        mcp.run(transport="stdio")
