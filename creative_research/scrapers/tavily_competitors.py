"""
Tavily search for competitor research: competitors, ad library links, ad intel.
"""

from creative_research.constants import TAVILY_API_KEY


def fetch_competitor_research(
    category_hint: str,
    *,
    product_link: str | None = None,
) -> str:
    """Search Tavily for competitors and ad library info. Returns markdown text."""
    if not TAVILY_API_KEY:
        return ""

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        results = client.search(
            query=f"{category_hint} competitors ad library Meta TikTok Google ads",
            max_results=5,
            search_depth="basic",
        )
        parts = []
        for r in results.get("results", [])[:5]:
            parts.append(f"- **{r.get('title', '')}**: {r.get('content', '')[:500]}...")
        return "\n".join(parts) if parts else ""
    except Exception:
        return ""
