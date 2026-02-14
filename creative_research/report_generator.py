"""
Creative Agency Research Report Generator.
Uses LLM to produce a full report from a product URL (and optional product page content).
Supports optional ScrapedData from Apify, YouTube Data API, and Reddit for richer reports.
OpenAI report response is cached by product_link + model (same product = cache hit).
"""

import os
import re
from datetime import datetime
from typing import TYPE_CHECKING, Optional

import httpx
from bs4 import BeautifulSoup
from openai import OpenAI

from creative_research.cache import load_cached, save_cached

if TYPE_CHECKING:
    from creative_research.scraped_data import ScrapedData

OUTLINE_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)),
    "CREATIVE_RESEARCH_REPORT_OUTLINE.md",
)

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_product_page(url: str, timeout: float = 15.0) -> str:
    """Fetch product URL and return cleaned text content (no HTML)."""
    with httpx.Client(
        follow_redirects=True,
        timeout=timeout,
        headers={"User-Agent": USER_AGENT},
    ) as client:
        resp = client.get(url)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text[:50_000]  # cap for context


def get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError(
            "OPENAI_API_KEY environment variable is required. "
            "Set it or pass product_page_content to avoid fetching."
        )
    return OpenAI(api_key=api_key)


def _call_llm(client: OpenAI, system: str, user: str, model: str = "gpt-4o") -> str:
    out = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.4,
    )
    return (out.choices[0].message.content or "").strip()


def generate_report(
    product_link: str,
    product_page_content: Optional[str] = None,
    scraped_data: Optional["ScrapedData"] = None,
    *,
    model: str = "gpt-4o",
    openai_api_key: Optional[str] = None,
) -> str:
    """
    Generate the full Creative Research Report in Markdown.

    Args:
        product_link: URL of the product (e.g. Amazon, brand site).
        product_page_content: Optional pre-fetched text from the product page.
            If None, product_link will be fetched (requires OPENAI_API_KEY).
        scraped_data: Optional ScrapedData from run_all_scrapes (Apify, YouTube, Reddit).
            When provided, real videos and comments are included in LLM context.
        model: OpenAI model to use.
        openai_api_key: Optional API key; otherwise uses OPENAI_API_KEY env.

    Returns:
        Full report as a single Markdown string.
    """
    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key

    cache_key = (product_link or "").strip() or "_"
    cached, hit = load_cached("openai_report", product_link=cache_key, model=model)
    if hit and isinstance(cached, str) and cached.strip():
        return cached

    client = get_client()

    if product_page_content is None and (not scraped_data or not scraped_data.product_page_text):
        try:
            product_page_content = fetch_product_page(product_link)
        except Exception as e:
            product_page_content = (
                f"[Could not fetch URL: {e}. Using product link only for context.]"
            )
    elif scraped_data and scraped_data.product_page_text:
        product_page_content = scraped_data.product_page_text
    elif product_page_content is None:
        product_page_content = ""

    product_context = f"""
Product link: {product_link}

Product page content (excerpt):
---
{product_page_content[:30_000]}
---
"""
    if scraped_data:
        product_context += "\n\n## Scraped data (videos & comments from YouTube, Reddit, Apify)\n\n"
        product_context += scraped_data.to_llm_context(max_chars=35_000)

    # --- Report Cover + Step 1A + 1C ---
    system1 = (
        "You are an expert creative strategist and researcher for a creative agency. "
        "You produce structured, actionable research reports in Markdown. "
        "Output only valid Markdown, no preamble."
    )
    use_scraped = " Use the scraped videos and comments data below when present to ground your analysis in real examples." if scraped_data else ""
    user1 = (
        "Using the product link and page content below, produce the following sections "
        "for a Creative Agency Research Report. Output each section with the exact headings."
        + use_scraped + "\n\n"
        "1) **Report Cover / Meta**: Product name, product link, report date (today), "
        "category/vertical, and a one-line product summary.\n\n"
        "2) **1A. Hashtag & Search Strategy**: List 10–20 product-related hashtags "
        "(core product terms, use-case/outcome terms, problem/pain terms). "
        "Then list search queries to use on YouTube, TikTok, and Instagram. "
        "Add a suggested time range (e.g. last 3–6 months).\n\n"
        "3) **1C. Competitors**: List 5–15 competitors (name, product type, positioning one-liner). "
        "Include the standard ad library links: Meta Ad Library, TikTok Creative Center, "
        "Google Ads Transparency, and Pinterest if relevant. "
        "Use the **Competitor analysis (Tavily search)** data when present to name real competitors and ad library / ad intel links. "
        "Add a short table or bullets for competitor ad themes (main angles, offers, creative styles).\n\n"
        + product_context
    )
    part1 = _call_llm(client, system1, user1, model=model)

    # --- Step 1B + 1D ---
    user2 = (
        "Continue the same Creative Research Report for this product. "
        "Using the product context and category, produce:\n\n"
        "4) **1B. Video Scrapes**: For YouTube (long-form), YouTube Shorts, TikTok, "
        "TikTok Shop, and Instagram Reels: for each platform give a short description of "
        "what to scrape, key metrics, and notes. Then provide a **curated list** of "
        "5–8 example high-engaging video concepts (title/description, key metrics, "
        "why they work in 2–3 bullets). End with **Common patterns** (recurring hooks, "
        "angles, formats, CTAs). Use realistic examples even if hypothetical.\n\n"
        "5) **1D. Organic Concepts — Crazy Organic Ideas of the Month**: "
        "List 5–10 standout organic video/content ideas (platform, one-line concept, "
        "why it’s notable, how it could translate to this product).\n\n"
        + product_context
    )
    part2 = _call_llm(client, system1, user2, model=model)

    # --- Step 2 ---
    user3 = (
        "Continue the same Creative Research Report. Produce:\n\n"
        "6) **2A. Comment Scrapes**: For Amazon, Reddit, YouTube, YouTube Shorts, "
        "TikTok, and Instagram: what to scrape and what to extract. "
        "Then provide **Deliverables**: verbatim comment banks by theme (desire, "
        "objection, question, comparison, surprise) with 3–5 example phrases per theme "
        "that sound like real customers in this category. Add a short **Sentiment summary** "
        "(what people love vs. doubt vs. ask).\n\n"
        "7) **2B. Thematic Clusters**: Desires, Objections, Questions, Comparisons, "
        "Surprise/delight — each with 3–5 bullet points and example phrases.\n\n"
        + product_context
    )
    part3 = _call_llm(client, system1, user3, model=model)

    # --- Step 3 ---
    user4 = (
        "Finish the Creative Research Report. Produce:\n\n"
        "8) **3A. Avatars (10 Different Avatars to Target)**: For each of 10 avatars, "
        "give: Name/label, Demographics, Psychographics, Where they are (platforms, "
        "content), Relationship to product, Objections, Message that resonates, "
        "Source (which research supports this). Use the product and category from the context.\n\n"
        "9) **3B. Overview — Messaging Pillars**: "
        "**Top 10 Key Selling Points** (one line each + short proof). "
        "**10 Core Desires** (outcome-focused, with verbatim-style language). "
        "**10 Pain Points / Problems** (frustrations, fears, current state).\n\n"
        "10) **3C. Client Details (Optional)**: Short note on brand voice, do’s and don’ts, "
        "current assets, and gaps vs. research.\n\n"
        + product_context
    )
    part4 = _call_llm(client, system1, user4, model=model)

    # Assemble
    report_date = datetime.utcnow().strftime("%Y-%m-%d")
    cover = (
        f"# Creative Agency Research Report\n\n"
        f"**Generated:** {report_date}  \n"
        f"**Product link:** {product_link}\n\n"
        "---\n\n"
    )
    report = cover + part1 + "\n\n---\n\n" + part2 + "\n\n---\n\n" + part3 + "\n\n---\n\n" + part4
    save_cached("openai_report", report, product_link=cache_key, model=model)
    return report
