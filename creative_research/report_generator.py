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
        return text[:50_000]


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
    has_enriched_videos: bool = False,
) -> str:
    """
    Generate the full Creative Research Report in Markdown.

    Args:
        product_link: URL of the product (e.g. Amazon, brand site).
        product_page_content: Optional pre-fetched text from the product page.
        scraped_data: Optional ScrapedData from run_all_scrapes (Apify, YouTube, Reddit).
        model: OpenAI model to use.
        openai_api_key: Optional API key; otherwise uses OPENAI_API_KEY env.

    Returns:
        Full report as a single Markdown string.
    """
    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key

    cache_key = (product_link or "").strip() or "_"
    cache_suffix = "_enriched" if has_enriched_videos else ""
    cached, hit = load_cached("openai_report", product_link=cache_key + cache_suffix, model=model)
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
        "2) **1A. Hashtag & Search Strategy**: List 10–20 product-related hashtags. "
        "Then list search queries to use on YouTube, TikTok, and Instagram. "
        "Add a suggested time range (e.g. last 3–6 months).\n\n"
        "3) **1C. Competitors**: List 5–15 competitors (name, product type, positioning one-liner). "
        "Include ad library links: Meta Ad Library, TikTok Creative Center, Google Ads Transparency. "
        "Use the **Competitor analysis (Tavily search)** data when present.\n\n"
        + product_context
    )
    part1 = _call_llm(client, system1, user1, model=model)

    user2 = (
        "Continue the same Creative Research Report. "
        "4) **1B. Video Scrapes**: For YouTube, YouTube Shorts, TikTok, Instagram Reels: "
        "what to scrape, key metrics, curated list of 5–8 example videos with metrics and why they work. "
        "5) **1D. Organic Concepts**: 5–10 standout organic video ideas.\n\n"
        + product_context
    )
    part2 = _call_llm(client, system1, user2, model=model)

    user3 = (
        "Continue the report. "
        "6) **2A. Comment Scrapes**: Platforms, what to extract, verbatim comment banks by theme "
        "(desire, objection, question, comparison, surprise). "
        "7) **2B. Thematic Clusters**: Desires, Objections, Questions, Comparisons, Surprise.\n\n"
        + product_context
    )
    part3 = _call_llm(client, system1, user3, model=model)

    user4 = (
        "Finish the report. "
        "8) **3A. Avatars (10 Different Avatars to Target)**: Name, Demographics, Psychographics, "
        "Where they are, Relationship to product, Objections, Message that resonates. "
        "9) **3B. Messaging Pillars**: Top 10 Key Selling Points, 10 Core Desires, 10 Pain Points. "
        "10) **3C. Client Details**: Brand voice, do's and don'ts, gaps vs. research.\n\n"
        + product_context
    )
    part4 = _call_llm(client, system1, user4, model=model)

    report_date = datetime.utcnow().strftime("%Y-%m-%d")
    cover = (
        f"# Creative Agency Research Report\n\n"
        f"**Generated:** {report_date}  \n"
        f"**Product link:** {product_link}\n\n"
        "---\n\n"
    )
    report = cover + part1 + "\n\n---\n\n" + part2 + "\n\n---\n\n" + part3 + "\n\n---\n\n" + part4
    save_cached("openai_report", report, product_link=cache_key + cache_suffix, model=model)
    return report
