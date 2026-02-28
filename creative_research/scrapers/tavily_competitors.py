"""
Tavily search for competitor research: competitors, ad library links, ad intel.
Focuses on direct-response / DTC brands in mens grooming & style culture.
"""

from creative_research.constants import TAVILY_API_KEY


def fetch_competitor_research(
    category_hint: str,
    *,
    product_link: str | None = None,
) -> str:
    """
    Search Tavily for competitors and ad library info.
    Uses multiple queries to find direct-response/DTC mens style brands (e.g. Beardbrand, Dollar Shave Club).
    Returns markdown text.
    """
    if not TAVILY_API_KEY:
        return ""

    try:
        from tavily import TavilyClient
        client = TavilyClient(api_key=TAVILY_API_KEY)
        seen_titles: set[str] = set()
        parts: list[str] = []

        # Multiple queries to surface direct-response mens grooming/style brands
        queries = [
            f"{category_hint} direct response DTC brands mens grooming",
            f"{category_hint} competitors Meta Ad Library TikTok Creative Center",
            "mens grooming DTC brands beard hair subscription",
            f"{category_hint} brands like Beardbrand Dollar Shave Club",
        ]

        for q in queries:
            results = client.search(
                query=q,
                max_results=5,
                search_depth="basic",
            )
            for r in results.get("results", [])[:3]:
                title = (r.get("title", "") or "").strip()
                if not title or title.lower() in seen_titles:
                    continue
                seen_titles.add(title.lower())
                content = (r.get("content", "") or "")[:600]
                parts.append(f"- **{title}**: {content}...")

        return "\n".join(parts[:15]) if parts else ""
    except Exception:
        return ""
