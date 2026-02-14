"""
File-based cache for successful scraper/API and OpenAI responses.
Use for testing to avoid repeated Apify, YouTube, Reddit, Tavily, and OpenAI calls.
Disable with CREATIVE_RESEARCH_NO_CACHE=1 or --no-cache.
"""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

# Names of sources that had a cache hit this process (for logging)
_cache_hits: list[str] = []


def _cache_dir() -> Path | None:
    if os.environ.get("CREATIVE_RESEARCH_NO_CACHE"):
        return None
    path = os.environ.get("CREATIVE_RESEARCH_CACHE_DIR")
    if path:
        return Path(path)
    # Project root: parent of creative_research package
    pkg = Path(__file__).resolve().parent
    root = pkg.parent
    return root / ".creative_research_cache"


def _make_key(name: str, **params: Any) -> str:
    """Stable hash for cache key."""
    normalized = json.dumps(params, sort_keys=True, default=str)
    return hashlib.sha256(f"{name}:{normalized}".encode()).hexdigest()[:24]


def _cache_path(cache_dir: Path, name: str, key: str) -> Path:
    sub = cache_dir / name
    sub.mkdir(parents=True, exist_ok=True)
    return sub / f"{key}.json"


def load_cached(name: str, **params: Any) -> tuple[Any, bool]:
    """
    Load cached response if present. Returns (data, True) on hit, (None, False) on miss.
    """
    cache_dir = _cache_dir()
    if not cache_dir:
        return None, False
    key = _make_key(name, **params)
    path = _cache_path(cache_dir, name, key)
    if not path.exists():
        return None, False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("success") is True and "data" in data:
            _cache_hits.append(name)
            return data["data"], True
    except Exception:
        pass
    return None, False


def save_cached(name: str, data: Any, **params: Any) -> None:
    """Save successful response to cache. data must be JSON-serializable."""
    cache_dir = _cache_dir()
    if not cache_dir:
        return
    key = _make_key(name, **params)
    path = _cache_path(cache_dir, name, key)
    try:
        path.write_text(
            json.dumps({"success": True, "data": data}, default=str, ensure_ascii=False),
            encoding="utf-8",
        )
    except Exception:
        pass


def get_and_clear_cache_hits() -> list[str]:
    """Return list of cache source names that had a hit this run, then clear the list."""
    global _cache_hits
    out = list(_cache_hits)
    _cache_hits = []
    return out


def is_cache_enabled() -> bool:
    """Return True if cache is on (not disabled by env)."""
    return _cache_dir() is not None
