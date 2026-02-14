"""
Competitor analysis via Tavily Search API.
Successful responses cached (CREATIVE_RESEARCH_NO_CACHE=1 to disable).
"""

import os
from typing import Any

from creative_research.cache import load_cached, save_cached


def _get_client():
    key = os.environ.get("TAVILY_API_KEY")
    if not key:
        raise ValueError("TAVILY_API_KEY is required for competitor analysis. Set in .env (get key at tavily.com)")
    try:
        from tavily import TavilyClient
        return TavilyClient(api_key=key)
    except ImportError:
        raise ImportError("Install tavily-python: pip install tavily-python")


def _search(client: Any, query: str, max_results: int = 8) -> list[dict]:
    """Run Tavily search and return results (title, url, content)."""
    try:
        response = client.search(
            query=query,
            max_results=max_results,
            search_depth="basic",
            include_answer=False,
        )
        if isinstance(response, dict):
            return response.get("results") or []
        return getattr(response, "results", []) or []
    except Exception:
        return []


def fetch_competitor_research(
    product_category_or_name: str,
    *,
    max_results_per_query: int = 8,
    product_link: str | None = None,
) -> str:
    """
    Run Tavily searches for competitor analysis. Returns a single text block for LLM context.
    Uses cache on hit (keyed by product_link so same product reuses cache).
    """
    category = product_category_or_name.strip() or "product"
    cache_key = (product_link or "").strip() or "_"
    cached, hit = load_cached("tavily", product_link=cache_key)
    if hit and isinstance(cached, str):
        return cached

    client = _get_client()
    out_lines: list[str] = []

    # 1) Main competitors / brands in category
    q1 = f"top competitors and brands in {category} market"
    for r in _search(client, q1, max_results=max_results_per_query):
        title = r.get("title") or ""
        url = r.get("url") or ""
        content = (r.get("content") or "")[:800]
        out_lines.append(f"[Competitors] {title}\nURL: {url}\n{content}\n")

    # 2) Meta Ad Library + category (how to find competitor ads)
    q2 = f"Meta Ad Library Facebook Instagram ads {category}"
    for r in _search(client, q2, max_results=5):
        title = r.get("title") or ""
        url = r.get("url") or ""
        content = (r.get("content") or "")[:500]
        out_lines.append(f"[Ad Library] {title}\nURL: {url}\n{content}\n")

    # 3) TikTok / Google ad transparency for category
    q3 = f"TikTok Creative Center Google Ads Transparency competitor ads {category}"
    for r in _search(client, q3, max_results=5):
        title = r.get("title") or ""
        url = r.get("url") or ""
        content = (r.get("content") or "")[:500]
        out_lines.append(f"[Ad intel] {title}\nURL: {url}\n{content}\n")

    result = "\n".join(out_lines)[:25_000]
    if result:
        save_cached("tavily", result, product_link=cache_key)
    return result
