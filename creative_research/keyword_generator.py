"""
Keyword generator: uses LLM to produce search_queries and subreddits from product link + page content.
Uses OpenAI with Gemini fallback.
"""

import json

from creative_research.constants import GEMINI_API_KEY, OPENAI_API_KEY
from creative_research.llm_client import call_llm_json


def generate_keywords(
    product_link: str,
    product_page_text: str = "",
    *,
    model: str = "gpt-4o",
) -> dict:
    """
    Generate search_queries and subreddits for scraping.
    Uses OpenAI with Gemini fallback.

    Returns:
        {"search_queries": [...], "subreddits": [...]}
    """
    if not OPENAI_API_KEY and not GEMINI_API_KEY:
        raise ValueError("OPENAI_API_KEY or GEMINI_API_KEY required. Set in .env")

    context = product_page_text[:8000] if product_page_text else "No product page content."
    prompt = f"""Product URL: {product_link}

Product page excerpt:
{context}

Generate JSON only (no markdown):
{{
  "search_queries": ["query1", "query2", ...],  // 8-12 clever, thought-out queries
  "subreddits": ["sub1", "sub2", ...],         // 5-10 relevant subreddits
  "hashtags": ["tag1", "tag2", ...]            // 8-12 hashtags: mix direct (product-specific) and indirect (broader: #hairgrowth #mensfashion #beard #grooming)
}}

Search query guidelines—be creative and specific, not generic:
- Use phrases real people type: "does [product type] actually work", "honest [product] review", "[product] before and after"
- Include pain-point angles: "patchy beard fix", "beard growth journey", "best beard oil for dry skin"
- Add format-specific: "unboxing [product]", "[product] vs [competitor]", "30 day [product] results"
- Vary specificity: some broad (#mensgrooming), some niche (exact product name)
- Avoid bland queries like "product review" or "best product"—craft queries that surface authentic UGC and third-party creators."""

    text = call_llm_json(prompt, openai_model=model)
    # Parse JSON from response (may be wrapped in ```json)
    if "```" in text:
        text = text.split("```")[1].replace("json", "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"search_queries": ["product review", "best"], "subreddits": ["all"], "hashtags": []}
    if not isinstance(data.get("search_queries"), list):
        data["search_queries"] = ["product review", "best"]
    if not isinstance(data.get("subreddits"), list):
        data["subreddits"] = ["all"]
    if not isinstance(data.get("hashtags"), list):
        data["hashtags"] = []
    return data
