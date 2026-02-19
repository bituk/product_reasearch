"""
Structured scraped data passed to the report generator.
All fields are optional; LLM can still generate report with partial or no scraped data.
"""

import re
from dataclasses import dataclass, field
from typing import Any


def _sanitize_description(desc: str) -> str:
    """Remove promotional boilerplate from video descriptions (subscribe prompts, social links, ASCII art)."""
    if not desc or not desc.strip():
        return ""
    lines = desc.split("\n")
    keep: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        # Skip ASCII art (box-drawing chars, mostly symbols)
        if re.match(r"^[\s╔═╦╗║╚╣╠╗╚╩╝─│├┤┬┴┼]*$", s) or len(set(s) - set(" \t\n\r")) < 3:
            continue
        # Skip subscribe/follow prompts
        if re.search(r"SUBSCRIBE\s+FOR|follow\s+pls|follow\s+me|subscribe\s+for", s, re.I):
            continue
        # Skip social link lines (TikTok, Instagram, Discord, etc.)
        if re.search(r"^\s*[•\-]\s*(TikTok|Instagram|Discord|Twitter|Facebook|YouTube)\s*[-–—]", s, re.I):
            continue
        if re.search(r"https?://(www\.)?(tiktok|instagram|discord|twitter|facebook)\.com", s, re.I):
            continue
        if re.search(r"Discord\s*[-–—]\s*To be announced", s, re.I):
            continue
        # Skip ambassador/affiliate lines
        if re.search(r"become\s+an?\s+ambassador|join\.collabs\.shopify|collaborations@", s, re.I):
            continue
        # Skip long separator lines (5+ dashes/equals)
        if re.match(r"^[\-\=]{5,}$", s):
            continue
        keep.append(line)
    result = "\n".join(keep).strip()
    return result


@dataclass
class VideoItem:
    """Single video/post from any platform. Reference stats for creative research."""
    platform: str
    title: str
    url: str = ""
    video_direct_url: str = ""  # Direct CDN URL for download (from Apify videoUrl)
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
                clean_desc = _sanitize_description(v.description)
                if clean_desc:
                    lines.append(f"  Desc: {clean_desc[:200]}...")
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

    def truncate_videos_to_max(
        self,
        max_total: int = 20,
        youtube_ratio: float = 0.75,
        min_tiktok: int = 2,
        min_instagram: int = 2,
    ) -> None:
        """
        Keep only the top max_total videos.
        Ensures at least min_tiktok (2) from TikTok and min_instagram (2) from Instagram when available.
        Remaining slots go to YouTube (videos + shorts).
        Updates youtube_videos, youtube_shorts, tiktok_videos, instagram_videos in place.
        """
        youtube_vids = self.youtube_videos + self.youtube_shorts
        all_vids = youtube_vids + self.tiktok_videos + self.instagram_videos

        if len(all_vids) <= max_total:
            return

        # Reserve slots for TikTok and Instagram (min 2 each when available)
        tiktok_reserved = min(min_tiktok, len(self.tiktok_videos)) if self.tiktok_videos else 0
        instagram_reserved = min(min_instagram, len(self.instagram_videos)) if self.instagram_videos else 0
        other_slots = tiktok_reserved + instagram_reserved
        youtube_slots = max(0, max_total - other_slots)

        youtube_sorted = sorted(youtube_vids, key=lambda v: v.views or 0, reverse=True)
        tiktok_sorted = sorted(self.tiktok_videos, key=lambda v: v.views or 0, reverse=True)
        instagram_sorted = sorted(self.instagram_videos, key=lambda v: v.views or 0, reverse=True)

        keep_youtube = youtube_sorted[:youtube_slots]
        keep_tiktok = tiktok_sorted[:tiktok_reserved]
        keep_instagram = instagram_sorted[:instagram_reserved]
        used = len(keep_youtube) + len(keep_tiktok) + len(keep_instagram)

        # Fill remaining slots from YouTube if we have room
        if used < max_total and len(youtube_sorted) > len(keep_youtube):
            remaining = max_total - used
            keep_youtube = youtube_sorted[: len(keep_youtube) + remaining]

        keep_set = {id(v) for v in keep_youtube + keep_tiktok + keep_instagram}

        self.youtube_videos = [v for v in self.youtube_videos if id(v) in keep_set]
        self.youtube_shorts = [v for v in self.youtube_shorts if id(v) in keep_set]
        self.tiktok_videos = [v for v in self.tiktok_videos if id(v) in keep_set]
        self.instagram_videos = [v for v in self.instagram_videos if id(v) in keep_set]

    def _select_videos_for_popular(
        self,
        limit: int = 12,
        min_per_source: int = 1,
        min_tiktok: int = 2,
        min_instagram: int = 2,
    ) -> list["VideoItem"]:
        """
        Select videos for reports: top by views + at least min_tiktok/min_instagram from TikTok/Instagram.
        Ensures both reports have at least 2 TikTok and 2 Instagram when available.
        """
        source_min = {
            "youtube": min_per_source,
            "youtube_shorts": min_per_source,
            "tiktok": min_tiktok,
            "instagram": min_instagram,
        }
        sources = [
            ("youtube", self.youtube_videos),
            ("youtube_shorts", self.youtube_shorts),
            ("tiktok", self.tiktok_videos),
            ("instagram", self.instagram_videos),
        ]
        all_videos = []
        for _, lst in sources:
            all_videos.extend(lst)
        videos_with_url = [v for v in all_videos if v.url]
        if not videos_with_url:
            return []

        by_views = sorted(videos_with_url, key=lambda v: v.views or 0, reverse=True)
        base_limit = max(6, limit - 4)
        selected: list[VideoItem] = list(by_views[:base_limit])
        seen_urls = {v.url for v in selected}

        # Ensure at least min_tiktok/min_instagram from TikTok/Instagram, min_per_source from others
        for src, lst in sources:
            min_needed = source_min[src]
            source_videos = [v for v in lst if v.url]
            source_videos.sort(
                key=lambda v: (1 if getattr(v, "video_direct_url", "") else 0, v.views or 0),
                reverse=True,
            )
            added = 0
            for v in source_videos:
                if v.url not in seen_urls and added < min_needed:
                    selected.append(v)
                    seen_urls.add(v.url)
                    added += 1

        selected.sort(key=lambda v: v.views or 0, reverse=True)
        return selected[:limit]

    def select_videos_for_analysis(
        self,
        limit: int = 5,
        min_per_source: int = 1,
    ) -> list["VideoItem"]:
        """
        Select videos for Gemini analysis with platform diversity.
        Ensures participation from YouTube, YouTube Shorts, TikTok, Instagram when available.
        """
        return self._select_videos_for_popular(limit=limit, min_per_source=min_per_source)

    def _platform_display(self, v: "VideoItem") -> str:
        """Display name for platform (YouTube Shorts vs YouTube)."""
        if v in self.youtube_shorts:
            return "YouTube Shorts"
        return v.platform

    def build_reference_video_section(
        self,
        limit: int | None = 10,
        sort_by_popularity: bool = True,
        section_title: str = "Reference Video Details",
        ensure_platform_diversity: bool = False,
        include_full_info: bool = False,
        show_full_analysis: bool = False,
        max_analysis_lines: int | None = 25,
    ) -> str:
        """
        Build markdown section for Reference Video Details (yt-dlp transcripts + Gemini analysis).
        Includes: URL, Views, Likes, Comments, Shares, CTA, Transcript, Gemini Analysis.
        Spend/Clicks: N/A for organic videos (ad library only).

        Args:
            limit: Max videos to include. None = all scraped videos.
            sort_by_popularity: If True, sort by views (desc) before applying limit.
            section_title: Optional section heading (e.g. "Most Popular" vs "All Scraped Videos").
            ensure_platform_diversity: If True, ensure at least 1 from each source (report_popular).
            include_full_info: If True, add description, author (report_all_videos).
            show_full_analysis: If True, show full Gemini analysis without truncation (report_all_videos).
        """
        all_videos = (
            self.youtube_videos + self.youtube_shorts
            + self.tiktok_videos + self.instagram_videos
        )
        videos_with_url = [v for v in all_videos if v.url]

        if ensure_platform_diversity and limit is not None:
            videos_with_url = self._select_videos_for_popular(
                limit=limit, min_per_source=1, min_tiktok=2, min_instagram=2
            )
        else:
            if sort_by_popularity:
                videos_with_url = sorted(videos_with_url, key=lambda v: v.views or 0, reverse=True)
            if limit is not None:
                videos_with_url = videos_with_url[:limit]
        if not videos_with_url:
            return ""

        has_transcript = any(v.transcript for v in videos_with_url)
        has_gemini = any(v.gemini_analysis for v in videos_with_url)
        subtitle = []
        if has_transcript:
            subtitle.append("transcripts via yt-dlp")
        if has_gemini:
            subtitle.append("analyzed with Gemini (YouTube, Instagram, TikTok, others)")
        subtitle_str = ", ".join(subtitle) if subtitle else "scraped links"

        # Video counts: reflect displayed videos (not total scraped) so counts match the table
        platform_counts: dict[str, int] = {}
        for v in videos_with_url:
            platform_display = self._platform_display(v)
            platform_counts[platform_display] = platform_counts.get(platform_display, 0) + 1
        # Fixed order: YouTube, YouTube Shorts, TikTok, Instagram (only include platforms present)
        order = ["YouTube", "YouTube Shorts", "TikTok", "Instagram"]
        counts = [f"{p}: {platform_counts[p]}" for p in order if platform_counts.get(p)]
        counts_str = " | ".join(counts) if counts else ""

        platform_note = "max 25; includes YouTube, Instagram, TikTok, and other platforms when available. "
        lines = [
            "",
            f"## 1B.1 {section_title}",
            "",
            f"Videos scraped ({platform_note}{subtitle_str}). Stats: Views, Likes, Comments, Shares, CTA.",
            "",
        ]
        if counts_str:
            lines.append(f"**Video counts:** {counts_str}")
            lines.append("")
        lines.extend([
            "| # | Platform | Title | URL | Views | Likes | Comments | Shares | CTA |",
            "|---|----------|-------|-----|-------|-------|----------|--------|-----|",
        ])
        for i, v in enumerate(videos_with_url, 1):
            title_esc = (v.title or "")[:40].replace("|", " ").replace("\n", " ")
            platform_display = self._platform_display(v)
            cta_short = (v.cta_summary or "—")[:30].replace("|", " ")
            lines.append(
                f"| {i} | {platform_display} | {title_esc} | [Link]({v.url}) | {v.views:,} | {v.likes:,} | {v.comments_count:,} | {v.shares:,} | {cta_short} |"
            )

        lines.extend([
            "",
            "> **Note:** Spend, Clicks, CTR are available for paid ads from ad libraries (Meta, TikTok). N/A for organic videos.",
            "",
        ])

        for i, v in enumerate(videos_with_url, 1):
            title_display = (v.title or "Untitled")[:60] + ("..." if len(v.title or "") > 60 else "")
            lines.append(f"### Video {i}: {title_display}")
            lines.append(f"- **URL:** {v.url}")
            lines.append(f"- **Stats:** Views {v.views:,} | Likes {v.likes:,} | Comments {v.comments_count:,} | Shares {v.shares:,}")
            if include_full_info and v.author:
                lines.append(f"- **Author:** {v.author}")
            if include_full_info and v.description:
                clean_desc = _sanitize_description(v.description)
                if clean_desc:
                    desc_limit = 2000 if show_full_analysis else 500
                    desc_text = clean_desc[:desc_limit] + "..." if len(clean_desc) > desc_limit else clean_desc
                    lines.append(f"- **Description:** {desc_text}")
            if v.cta_summary:
                lines.append(f"- **CTA:** {v.cta_summary}")
            if v.transcript:
                lines.append(f"- **Transcript (yt-dlp):**")
                lines.append(f"  ```")
                transcript_limit = None if show_full_analysis else 800
                transcript_text = v.transcript if transcript_limit is None else (v.transcript[:transcript_limit] + "..." if len(v.transcript) > transcript_limit else v.transcript)
                lines.append(f"  {transcript_text}")
                lines.append(f"  ```")
            if v.gemini_analysis:
                lines.append(f"- **Gemini Analysis:**")
                lines.append("")
                analysis_lines = v.gemini_analysis.split("\n")
                max_lines = None if show_full_analysis else (max_analysis_lines or 25)
                for ln in (analysis_lines[:max_lines] if max_lines else analysis_lines):
                    lines.append("  " + ln)
                if not show_full_analysis and max_lines and len(analysis_lines) > max_lines:
                    lines.append("  ...")
            lines.append("")

        return "\n".join(lines)
