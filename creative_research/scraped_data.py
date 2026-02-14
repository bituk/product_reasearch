"""
Structured scraped data passed to the report generator.
All fields are optional; LLM can still generate report with partial or no scraped data.
"""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class VideoItem:
    """Single video/post from any platform. Reference stats for creative research."""
    platform: str
    title: str
    url: str = ""
    description: str = ""
    views: int = 0
    likes: int = 0
    comments_count: int = 0
    shares: int = 0  # shares/saves where available
    published_at: str = ""
    author: str = ""
    # Enriched: transcript/script, Gemini analysis, CTA
    transcript: str = ""
    gemini_analysis: str = ""
    cta_summary: str = ""  # CTA extracted from analysis
    # Ad-specific (when available from ad libraries): spend, clicks, CTR
    spend: float = 0.0
    clicks: int = 0
    ctr: float = 0.0
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommentItem:
    """Single comment from any source."""
    source: str  # youtube, reddit, amazon, tiktok, instagram
    text: str
    author: str = ""
    likes: int = 0
    created_at: str = ""
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ScrapedData:
    """Aggregated scraped data for report generation."""
    product_url: str = ""
    product_page_text: str = ""
    # Video scrapes
    youtube_videos: list[VideoItem] = field(default_factory=list)
    youtube_shorts: list[VideoItem] = field(default_factory=list)
    youtube_comments: list[CommentItem] = field(default_factory=list)
    tiktok_videos: list[VideoItem] = field(default_factory=list)
    instagram_videos: list[VideoItem] = field(default_factory=list)
    # Comment scrapes
    reddit_posts_and_comments: list[CommentItem] = field(default_factory=list)
    amazon_reviews_text: str = ""  # concatenated or structured
    # Optional raw Apify/API outputs for LLM context
    apify_amazon: list[dict] = field(default_factory=list)
    apify_tiktok: list[dict] = field(default_factory=list)
    apify_instagram: list[dict] = field(default_factory=list)
    # Tavily competitor analysis (search results for competitors, ad libraries, etc.)
    competitor_research: str = ""

    def to_llm_context(self, max_chars: int = 40_000) -> str:
        """Serialize to a string for LLM context, truncating if needed."""
        parts = []
        if self.product_page_text:
            parts.append("## Product page (excerpt)\n" + self.product_page_text[:15_000])
        if self.youtube_videos:
            parts.append("## YouTube videos\n" + self._videos_to_text(self.youtube_videos, 20))
        if self.youtube_shorts:
            parts.append("## YouTube Shorts\n" + self._videos_to_text(self.youtube_shorts, 15))
        if self.youtube_comments:
            parts.append("## YouTube comments\n" + self._comments_to_text(self.youtube_comments, 30))
        if self.tiktok_videos:
            parts.append("## TikTok videos\n" + self._videos_to_text(self.tiktok_videos, 15))
        if self.instagram_videos:
            parts.append("## Instagram videos\n" + self._videos_to_text(self.instagram_videos, 15))
        if self.reddit_posts_and_comments:
            parts.append("## Reddit posts/comments\n" + self._comments_to_text(self.reddit_posts_and_comments, 40))
        if self.amazon_reviews_text:
            parts.append("## Amazon reviews (excerpt)\n" + self.amazon_reviews_text[:8_000])
        if self.apify_amazon:
            import json
            parts.append("## Amazon scrape (raw)\n" + json.dumps(self.apify_amazon[:50], default=str)[:6_000])
        if self.competitor_research:
            parts.append("## Competitor analysis (Tavily search)\n" + self.competitor_research[:15_000])
        text = "\n\n".join(parts)
        return text[:max_chars] if len(text) > max_chars else text

    @staticmethod
    def _videos_to_text(videos: list[VideoItem], limit: int) -> str:
        lines = []
        for v in videos[:limit]:
            lines.append(f"- [{v.platform}] {v.title}")
            if v.url:
                lines.append(f"  URL: {v.url}")
            stats = []
            if v.views:
                stats.append(f"Views: {v.views}")
            if v.likes:
                stats.append(f"Likes: {v.likes}")
            if v.comments_count:
                stats.append(f"Comments: {v.comments_count}")
            if v.shares:
                stats.append(f"Shares: {v.shares}")
            if v.spend:
                stats.append(f"Spend: {v.spend}")
            if v.clicks:
                stats.append(f"Clicks: {v.clicks}")
            if v.ctr:
                stats.append(f"CTR: {v.ctr}%")
            if stats:
                lines.append(f"  {' | '.join(stats)}")
            if v.cta_summary:
                lines.append(f"  CTA: {v.cta_summary[:150]}...")
            if v.description:
                lines.append(f"  Desc: {v.description[:200]}...")
            if v.transcript:
                lines.append(f"  Transcript: {v.transcript[:300]}...")
            if v.gemini_analysis:
                lines.append(f"  Analysis: {v.gemini_analysis[:400]}...")
        return "\n".join(lines)

    @staticmethod
    def _comments_to_text(comments: list[CommentItem], limit: int) -> str:
        return "\n".join(
            f"- [{c.source}] {c.text[:300]}" for c in comments[:limit]
        )
