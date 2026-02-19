"""
Keyword generator: uses LLM to produce search_queries and subreddits from product link + page content.
"""

from openai import OpenAI

from creative_research.constants import OPENAI_API_KEY


def get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required. Set in .env")
    return OpenAI(api_key=OPENAI_API_KEY)


def generate_keywords(
    product_link: str,
    product_page_text: str = "",
    *,
    model: str = "gpt-4o",
) -> dict:
    """
    Generate search_queries and subreddits for scraping.

    Returns:
        {"search_queries": [...], "subreddits": [...]}
    """
    client = get_client()
    context = product_page_text[:8000] if product_page_text else "No product page content."
    prompt = f"""Product URL: {product_link}

Product page excerpt:
{context}

Generate JSON only (no markdown):
{{
  "search_queries": ["query1", "query2", ...],  // 8-12 queries for YouTube/TikTok/Instagram search
  "subreddits": ["sub1", "sub2", ...]          // 5-10 relevant subreddits
}}

Use product name, category, and features. Queries should find reviews, unboxing, comparisons."""

    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
    )
    text = (resp.choices[0].message.content or "").strip()
    # Parse JSON from response (may be wrapped in ```json)
    import json
    if "```" in text:
        text = text.split("```")[1].replace("json", "").strip()
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = {"search_queries": ["product review", "best"], "subreddits": ["all"]}
    if not isinstance(data.get("search_queries"), list):
        data["search_queries"] = ["product review", "best"]
    if not isinstance(data.get("subreddits"), list):
        data["subreddits"] = ["all"]
    return data
