"""
Reddit public JSON API: fetch posts and comments from subreddits.
No credentials required (User-Agent: creative-research-bot/1.0).
"""

import dataclasses
import httpx
from creative_research.scraped_data import CommentItem
from creative_research.cache import load_cached, save_cached

USER_AGENT = "creative-research-bot/1.0"


def fetch_reddit_posts_and_comments(
    subreddits: list[str],
    queries: list[str],
    *,
    limit_posts: int = 25,
    product_link: str | None = None,
) -> list[CommentItem]:
    """Fetch hot posts from subreddits, optionally filtered by queries."""
    cache_key = (product_link or "").strip() or "_"
    cached, hit = load_cached("reddit", subreddits=str(subreddits), queries=str(queries[:3]), product_link=cache_key)
    if hit and isinstance(cached, list):
        valid = {f.name for f in dataclasses.fields(CommentItem)}
        return [CommentItem(**{k: v for k, v in d.items() if k in valid}) for d in cached]

    items: list[CommentItem] = []
    subs = subreddits if subreddits else ["all"]
    for sub in subs[:5]:
        try:
            url = f"https://www.reddit.com/r/{sub}/hot.json?limit={min(limit_posts, 25)}"
            with httpx.Client(timeout=15.0, headers={"User-Agent": USER_AGENT}) as client:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
            for child in data.get("data", {}).get("children", [])[:limit_posts]:
                post = child.get("data", {})
                title = post.get("title", "")
                selftext = post.get("selftext", "")
                if title or selftext:
                    text = f"{title}\n{selftext}".strip()[:500]
                    if queries:
                        q_lower = [q.lower() for q in queries[:3]]
                        if not any(q in text.lower() for q in q_lower):
                            continue
                    items.append(CommentItem(
                        source="reddit",
                        text=text,
                        author=post.get("author", ""),
                        likes=post.get("ups", 0),
                        created_at=post.get("created_utc", ""),
                        raw=post,
                    ))
        except Exception:
            continue

    if items:
        save_cached("reddit", [dataclasses.asdict(c) for c in items],
                   subreddits=str(subs), queries=str(queries[:3]), product_link=cache_key)
    return items
