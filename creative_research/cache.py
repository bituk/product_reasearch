"""
Cache for API responses (Apify, YouTube, Tavily, etc.).
Stored in .creative_research_cache/{source}/{hash}.json
Disable with CREATIVE_RESEARCH_NO_CACHE=1
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any


def _cache_dir() -> Path:
    base = Path(__file__).resolve().parent.parent
    return base / ".creative_research_cache"


def _cache_key(source: str, **kwargs: Any) -> str:
    """Generate a deterministic hash from source + kwargs."""
    key_parts = [source] + [f"{k}={v!r}" for k, v in sorted(kwargs.items())]
    key_str = "|".join(key_parts)
    return hashlib.md5(key_str.encode()).hexdigest()


def load_cached(source: str, **kwargs: Any) -> tuple[Any, bool]:
    """
    Load cached data. Returns (data, hit).

    Args:
        source: Cache source (e.g. "apify", "youtube", "tavily").
        **kwargs: Key params (e.g. product_link, actor_id, run_input).

    Returns:
        (cached_data, True) on hit, (None, False) on miss.
    """
    if os.environ.get("CREATIVE_RESEARCH_NO_CACHE"):
        return None, False

    cache_path = _cache_dir() / source / f"{_cache_key(source, **kwargs)}.json"
    if not cache_path.exists():
        return None, False

    try:
        with open(cache_path, encoding="utf-8") as f:
            obj = json.load(f)
        if isinstance(obj, dict) and obj.get("success") and "data" in obj:
            return obj["data"], True
        return obj, True
    except Exception:
        return None, False


def save_cached(source: str, data: Any, **kwargs: Any) -> None:
    """
    Save data to cache.

    Args:
        source: Cache source.
        data: Data to cache.
        **kwargs: Key params (must match load_cached).
    """
    if os.environ.get("CREATIVE_RESEARCH_NO_CACHE"):
        return

    cache_path = _cache_dir() / source / f"{_cache_key(source, **kwargs)}.json"
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    out = {"success": True, "data": data}
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(out, f, default=str, ensure_ascii=False)
