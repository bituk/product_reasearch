"""
LLM-based video script generation from research + video analysis.
Generates creative scripts inspired by reference videos and research insights.
"""

from typing import Any

from creative_research.constants import OPENAI_API_KEY
from creative_research.scraped_data import VideoItem, ScrapedData


def _get_openai_client():
    from openai import OpenAI
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY required for script generation. Set in .env")
    return OpenAI(api_key=OPENAI_API_KEY)


def _build_script_context(
    research_report: str,
    scraped_data: ScrapedData | None,
    video_analyses: list[dict[str, Any]],
    product_summary: str = "",
) -> str:
    """Build context string for script generation."""
    parts = []
    if product_summary:
        parts.append(f"## Product\n{product_summary[:1000]}")
    if research_report:
        parts.append(f"## Research Report (excerpt)\n{research_report[:12000]}")
    if scraped_data:
        parts.append("\n## Reference Videos & Stats\n" + scraped_data.to_llm_context(max_chars=8000))
    if video_analyses:
        parts.append("\n## Gemini Video Analyses\n")
        for i, va in enumerate(video_analyses[:10], 1):
            inp = va.get("input", "")
            analysis = va.get("analysis", "")
            if analysis:
                parts.append(f"### Video {i}: {inp}\n{analysis[:1500]}\n")
    return "\n".join(parts)


SCRIPT_GENERATION_PROMPT = """You are a creative director writing video scripts for ads and organic content.

Using the research report, reference video stats (views, likes, comments, CTA), and Gemini video analyses below, generate 3 distinct video scripts.

For each script provide:
1. **Platform** (YouTube Shorts, TikTok, Instagram Reels, etc.)
2. **Format** (e.g. UGC unboxing, talking head review, before/after)
3. **Hook** (first 3-5 seconds - exact words/visual direction)
4. **Full script** (dialogue + visual cues, 30-90 seconds)
5. **CTA** (call-to-action at end)
6. **Why it will work** (1-2 sentences tying to research)

Scripts should feel native to each platform, use language from the comment banks where relevant, and incorporate hooks/angles that worked in the reference videos. Be specific and actionable."""


def generate_video_scripts(
    research_report: str,
    *,
    scraped_data: ScrapedData | None = None,
    video_analyses: list[dict[str, Any]] | None = None,
    product_summary: str = "",
    model: str = "gpt-4o",
) -> str:
    """
    Generate video scripts from research + video analysis using LLM.

    Args:
        research_report: Full or excerpt of the Creative Research Report.
        scraped_data: Optional ScrapedData with videos/comments.
        video_analyses: Optional list of {input, analysis} from Gemini.
        product_summary: Optional one-line product summary.
        model: OpenAI model (default gpt-4o).

    Returns:
        Markdown with 3 generated scripts.
    """
    client = _get_openai_client()
    context = _build_script_context(
        research_report,
        scraped_data,
        video_analyses or [],
        product_summary,
    )
    user_msg = f"{SCRIPT_GENERATION_PROMPT}\n\n---\n\n{context}"
    resp = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are an expert creative director. Output only valid Markdown."},
            {"role": "user", "content": user_msg},
        ],
        temperature=0.7,
    )
    return (resp.choices[0].message.content or "").strip()
