"""
Reddit public JSON API — no credentials required.
Successful responses cached (CREATIVE_RESEARCH_NO_CACHE=1 to disable).
"""

import dataclasses
import httpx
from creative_research.scraped_data import CommentItem
from creative_research.cache import load_cached, save_cached

REDDIT_BASE = "https://www.reddit.com"
USER_AGENT = "creative-research-bot/1.0"


def _get_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=15.0,
        follow_redirects=True,
    )


def _listing(client: httpx.Client, path: str, params: dict | None = None) -> list[dict]:
    """Fetch a Reddit listing (hot, search, etc.) and return list of post data dicts."""
    url = f"{REDDIT_BASE}{path}"
    try:
        r = client.get(url, params=params or {})
        r.raise_for_status()
        data = r.json()
        children = (data.get("data") or {}).get("children") or []
        return [c.get("data") for c in children if c.get("data")]
    except Exception:
        return []


def _comments_for_post(client: httpx.Client, subreddit: str, post_id: str) -> list[dict]:
    """Fetch comments for a post. Returns list of comment data dicts (flattened)."""
    url = f"{REDDIT_BASE}/r/{subreddit}/comments/{post_id}.json"
    try:
        r = client.get(url)
        r.raise_for_status()
        listing = r.json()
        # listing[0] = post, listing[1] = comment tree
        if len(listing) < 2:
            return []
        comment_tree = listing[1].get("data", {}).get("children") or []
        out = []

        def extract(children):
            for c in children:
                d = c.get("data") or {}
                kind = d.get("kind")
                if kind == "t1" and d.get("body"):
                    out.append({"body": d.get("body"), "author": d.get("author"), "score": d.get("score", 0)})
                replies = d.get("replies")
                if isinstance(replies, dict) and "data" in replies:
                    extract(replies["data"].get("children") or [])

        extract(comment_tree)
        return out
    except Exception:
        return []


def fetch_reddit_posts_and_comments(
    subreddits: list[str],
    search_queries: list[str],
    *,
    limit_posts: int = 25,
    limit_comments_per_post: int = 10,
    product_link: str | None = None,
) -> list[CommentItem]:
    """
    Fetch hot (or search) posts and their comments via Reddit public JSON API.
    Returns flat list of CommentItem. Uses cache on hit (keyed by product_link so same product reuses cache).
    """
    cache_key = (product_link or "").strip() or "_"
    cached, hit = load_cached("reddit", product_link=cache_key)
    if hit and isinstance(cached, list):
        return [CommentItem(**d) for d in cached]

    items: list[CommentItem] = []
    seen_ids: set[str] = set()

    with _get_client() as client:
        for sub_name in subreddits[:5]:
            sub_name = sub_name.strip().replace("r/", "").strip()
            if not sub_name:
                continue

            posts_data: list[dict] = []
            if search_queries:
                for q in search_queries[:3]:
                    posts_data.extend(
                        _listing(
                            client,
                            f"/r/{sub_name}/search.json",
                            {"q": q, "limit": min(limit_posts, 25), "restrict_sr": "on", "sort": "relevance"},
                        )
                    )
            else:
                posts_data = _listing(
                    client,
                    f"/r/{sub_name}/hot.json",
                    {"limit": min(limit_posts, 100)},
                )

            for post in posts_data:
                post_id = post.get("id")
                if not post_id or post_id in seen_ids:
                    continue
                seen_ids.add(post_id)
                title = post.get("title") or ""
                selftext = post.get("selftext") or ""
                text = f"[POST] {title}\n{selftext}"[:2000]
                items.append(
                    CommentItem(
                        source="reddit",
                        text=text,
                        author=post.get("author") or "",
                        likes=post.get("score") or 0,
                        created_at=str(post.get("created_utc", "")),
                        raw={"id": post_id, "url": post.get("url", ""), "permalink": post.get("permalink", "")},
                    )
                )
                # Fetch comments for this post
                comments = _comments_for_post(client, sub_name, post_id)
                for c in comments[:limit_comments_per_post]:
                    items.append(
                        CommentItem(
                            source="reddit",
                            text=(c.get("body") or "")[:1000],
                            author=c.get("author") or "",
                            likes=c.get("score") or 0,
                            raw={},
                        )
                    )

    result = items[:200]
    if result:
        save_cached("reddit", [dataclasses.asdict(c) for c in result], product_link=cache_key)
    return result
