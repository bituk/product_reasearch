"""
Run all scrapers (Apify, YouTube, Reddit) and product page fetch; return ScrapedData.
"""

from creative_research.constants import APIFY_API_TOKEN, get_skip_apify, TAVILY_API_KEY, YOUTUBE_OR_GOOGLE_API_KEY
from creative_research.scraped_data import ScrapedData, VideoItem, CommentItem
from creative_research.report_generator import fetch_product_page


def _has_apify() -> bool:
    return bool(APIFY_API_TOKEN) and not get_skip_apify()


def _has_youtube() -> bool:
    return bool(YOUTUBE_OR_GOOGLE_API_KEY)


def _has_tavily() -> bool:
    return bool(TAVILY_API_KEY)


def run_all_scrapes(
    product_link: str,
    search_queries: list[str] | None = None,
    subreddits: list[str] | None = None,
    *,
    product_page_text: str | None = None,
    max_youtube_videos: int = 20,
    max_apify_per_platform: int = 15,
    max_reddit_posts: int = 25,
) -> ScrapedData:
    """Run product page fetch + YouTube + Reddit + Apify (if tokens set)."""
    queries = search_queries or []
    subs = subreddits or []
    data = ScrapedData(product_url=product_link)

    if product_page_text is not None:
        data.product_page_text = product_page_text
    else:
        try:
            data.product_page_text = fetch_product_page(product_link)
        except Exception:
            data.product_page_text = ""

    if _has_youtube() and queries:
        try:
            from creative_research.scrapers.youtube_scraper import fetch_youtube_videos_and_comments
            long_form, shorts, yt_comments = fetch_youtube_videos_and_comments(
                queries, max_videos=max_youtube_videos, product_link=product_link
            )
            data.youtube_videos = long_form
            data.youtube_shorts = shorts
            data.youtube_comments = yt_comments
        except Exception:
            pass

    if queries or subs:
        try:
            from creative_research.scrapers.reddit_scraper import fetch_reddit_posts_and_comments
            if not subs:
                subs = ["all"]
            data.reddit_posts_and_comments = fetch_reddit_posts_and_comments(
                subs, queries, limit_posts=max_reddit_posts, product_link=product_link
            )
        except Exception:
            pass

    if _has_apify():
        try:
            from creative_research.scrapers.apify_scraper import run_apify_scrapes
            hashtags = [q.replace(" ", "") for q in queries[:5]] or ["product", "review"]
            tiktok, instagram, amazon_raw, _, _ = run_apify_scrapes(
                product_link,
                hashtags,
                max_videos_per_platform=max_apify_per_platform,
            )
            data.tiktok_videos = tiktok
            data.instagram_videos = instagram
            data.apify_amazon = amazon_raw
            if amazon_raw:
                import json
                data.amazon_reviews_text = json.dumps(amazon_raw[:30], default=str)[:15_000]
        except BaseException:
            pass  # Skip Apify on any error (e.g. client panic, network)

    if _has_tavily():
        try:
            from creative_research.scrapers.tavily_competitors import fetch_competitor_research
            category_hint = (queries[0] if queries else "") or "product"
            if data.product_page_text:
                category_hint = category_hint or data.product_page_text[:400].replace("\n", " ")
            data.competitor_research = fetch_competitor_research(
                category_hint, product_link=product_link
            )
        except Exception:
            pass

    return data
