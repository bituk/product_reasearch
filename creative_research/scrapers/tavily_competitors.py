"""
Tavily search for competitor research: competitors, ad library links, ad intel.
"""

import os
from creative_research.cache import load_cached, save_cached


def fetch_competitor_research(
    category_hint: str,
    *,
    product_link: str | None = None,
) -> str:
    """Search Tavily for competitors and ad library info. Returns markdown text."""
    cache_key = (product_link or "").strip() or "_"
    cached, hit = load_cached("tavily", category_hint=category_hint[:200], product_link=cache_key)
    if hit and isinstance(cached, str) and cached.strip():
        return cached

    api_key = os.environ.get("TAVILY_API_KEY")
    if not api_key:
        return ""

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=api_key)
        results = client.search(
            query=f"{category_hint} competitors ad library Meta TikTok Google ads",
            max_results=5,
            search_depth="basic",
        )
        parts = []
        for r in results.get("results", [])[:5]:
            parts.append(f"- **{r.get('title', '')}**: {r.get('content', '')[:500]}...")
        text = "\n".join(parts) if parts else ""
        if text:
            save_cached("tavily", text, category_hint=category_hint[:200], product_link=cache_key)
        return text
    except Exception:
        return ""
