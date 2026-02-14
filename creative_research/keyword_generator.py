"""
Keyword Generator (GPT): from product link + page content, generate search queries
and subreddits for Reddit / YouTube / Amazon scrapers.
OpenAI response is cached by product_link + model (same product = cache hit).
"""

import json
import os
import re
from typing import Any

from openai import OpenAI

from creative_research.cache import load_cached, save_cached


def get_client() -> OpenAI:
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is required for keyword generator. Set in .env")
    return OpenAI(api_key=api_key)


def generate_keywords(
    product_link: str,
    product_page_content: str = "",
    *,
    model: str = "gpt-4o",
    openai_api_key: str | None = None,
) -> dict[str, list[str]]:
    """
    Use GPT to generate search_queries and subreddits from the product context.
    Returns {"search_queries": ["q1", "q2", ...], "subreddits": ["Subreddit1", ...]}.
    """
    if openai_api_key:
        os.environ["OPENAI_API_KEY"] = openai_api_key

    cache_key = (product_link or "").strip() or "_"
    cached, hit = load_cached("openai_keywords", product_link=cache_key, model=model)
    if hit and isinstance(cached, dict) and "search_queries" in cached:
        return {
            "search_queries": cached.get("search_queries", ["product review", "best"])[:15],
            "subreddits": cached.get("subreddits", ["all"])[:8],
        }

    client = get_client()
    excerpt = (product_page_content or "")[:12_000]
    user_content = f"""Product URL: {product_link}

Product page excerpt (if any):
{excerpt}

From this product, output a JSON object with exactly two keys:
1) "search_queries": a list of 8-15 search keywords/phrases to use for Reddit, YouTube, and Amazon (e.g. product category, use cases, problems, competitor terms). Use short phrases like "best vitamin C serum", "dry skin moisturizer", "skincare routine".
2) "subreddits": a list of 3-8 relevant subreddit names (without r/) where this product's audience might discuss (e.g. SkincareAddiction, 30PlusSkinCare). Use real, active subreddits.

Output only valid JSON, no markdown or explanation."""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {
                "role": "system",
                "content": "You are a research assistant. You output only valid JSON with keys search_queries and subreddits, both arrays of strings.",
            },
            {"role": "user", "content": user_content},
        ],
        temperature=0.3,
    )
    text = (response.choices[0].message.content or "").strip()
    # Remove markdown code block if present
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"search_queries": ["product review", "best"], "subreddits": ["all"]}

    search_queries = data.get("search_queries")
    subreddits = data.get("subreddits")
    if not isinstance(search_queries, list):
        search_queries = ["product review", "best"]
    if not isinstance(subreddits, list):
        subreddits = ["all"]
    result = {
        "search_queries": [str(q).strip() for q in search_queries if str(q).strip()][:15],
        "subreddits": [str(s).strip().replace("r/", "") for s in subreddits if str(s).strip()][:8],
    }
    save_cached("openai_keywords", result, product_link=cache_key, model=model)
    return result
