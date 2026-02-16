"""
Gemini multimodal video analysis.
Analyzes videos (via YouTube URL or local file) for creative insights:
hooks, CTAs, format, engagement patterns, script/structure.
Responses are cached (disable with CREATIVE_RESEARCH_NO_CACHE=1).

Rate limits: https://ai.google.dev/gemini-api/docs/rate-limits
- Adds delay between batch requests to respect RPM limits
- Retries with backoff on 429 (Too Many Requests)
"""

import time
from pathlib import Path
from typing import Any

from creative_research.cache import load_cached, save_cached
from creative_research.constants import (
    GEMINI_API_KEY,
    GEMINI_BATCH_DELAY,
    GEMINI_MODEL,
    SKIP_GEMINI_ANALYSIS,
)

DEFAULT_BATCH_DELAY = GEMINI_BATCH_DELAY

# Max total time spent retrying on 429/quota errors (seconds)
MAX_RETRY_SECONDS = 300  # 5 minutes

# Fallback models to try when primary fails with quota (different models may have separate quotas)
GEMINI_FALLBACK_MODELS = ["gemini-1.5-flash", "gemini-1.5-flash-8b", "gemini-2.0-flash-lite"]


def _parse_retry_seconds(err_str: str) -> float | None:
    """Parse 'Please retry in X.Ys' or 'retry in X seconds' from Gemini error."""
    import re
    m = re.search(r"retry\s+in\s+([\d.]+)\s*s", err_str, re.I)
    return float(m.group(1)) if m else None

# Gemini supports YouTube URLs directly - no download needed for analysis
GEMINI_VIDEO_ANALYSIS_PROMPT = """Analyze this video for creative/ad research purposes.

Extract and structure:
1. **Hook** (first 3-5 seconds): What grabs attention? Visual, text, sound?
2. **Main message/angle**: Core value prop or story.
3. **CTA (Call-to-Action)**: What does the creator ask viewers to do? (like, follow, link, buy, comment)
4. **Format**: Style (talking head, B-roll, UGC, unboxing, review, etc.)
5. **Engagement drivers**: What makes this engaging? (humor, curiosity, urgency, social proof)
6. **Script/structure summary**: Key beats and flow (opening, middle, close).
7. **Why it works**: 2-3 bullets on why this creative would perform well.

Output as structured markdown. Be specific and actionable."""


def _configure_gemini():
    """Configure Gemini API."""
    if not GEMINI_API_KEY:
        raise ValueError(
            "GEMINI_API_KEY or GOOGLE_API_KEY required for video analysis. Set in .env"
        )
    try:
        import warnings
        with warnings.catch_warnings(action="ignore", category=FutureWarning):
            import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        return genai
    except ImportError:
        raise ImportError(
            "Install google-generativeai: pip install google-generativeai"
        )


def analyze_video_with_gemini(
    video_input: str | Path,
    *,
    product_context: str = "",
    model: str | None = None,
) -> str:
    """
    Analyze a video using Gemini (multimodal).
    Caches responses by video URL + product_context.

    Args:
        video_input: YouTube URL (str) or path to local video file (Path).
        product_context: Optional product/category context for relevance.
        model: Gemini model (gemini-2.0-flash, gemini-1.5-flash, gemini-1.5-pro, etc.)

    Returns:
        Structured analysis text (markdown).
    """
    if SKIP_GEMINI_ANALYSIS:
        return "Video analysis skipped (SKIP_GEMINI_ANALYSIS=1). Enable billing or wait for quota reset."

    model = model or GEMINI_MODEL
    models_to_try = [model] + [m for m in GEMINI_FALLBACK_MODELS if m != model]
    inp_str = str(video_input)
    genai = _configure_gemini()
    prompt = GEMINI_VIDEO_ANALYSIS_PROMPT
    if product_context:
        prompt = f"Product/category context: {product_context[:500]}\n\n{prompt}"

    video_path = Path(video_input) if isinstance(video_input, (str, Path)) else None
    is_url = isinstance(video_input, str) and (
        "youtube.com" in video_input or "youtu.be" in video_input
    )

    last_error = None
    retry_start = time.monotonic()
    for try_model in models_to_try:
        cached, hit = load_cached(
            "gemini_analysis",
            video_input=inp_str,
            product_context=product_context[:500],
            model=try_model,
        )
        if hit and isinstance(cached, str) and cached.strip():
            return cached

        attempt = 0
        while True:
            try:
                model_obj = genai.GenerativeModel(try_model)
                if is_url:
                    response = model_obj.generate_content([video_input, prompt])
                elif video_path and video_path.exists():
                    video_file = genai.upload_file(path=str(video_path))
                    response = model_obj.generate_content([video_file, prompt])
                else:
                    return f"Error: Invalid video input. Expected YouTube URL or file path: {video_input}"

                analysis = (response.text or "No analysis generated.").strip()
                if analysis and not analysis.startswith("Error"):
                    save_cached(
                        "gemini_analysis",
                        analysis,
                        video_input=inp_str,
                        product_context=product_context[:500],
                        model=try_model,
                    )
                return analysis
            except Exception as e:
                last_error = e
                err_str = str(e)
                is_quota = "429" in err_str or "quota" in err_str.lower() or "Too Many Requests" in err_str or "ResourceExhausted" in err_str
                if is_quota:
                    elapsed = time.monotonic() - retry_start
                    if elapsed >= MAX_RETRY_SECONDS:
                        break  # Stop retrying (5 min exhausted)
                    wait = _parse_retry_seconds(err_str) or min((2 ** attempt) * 10, 120)
                    remaining = MAX_RETRY_SECONDS - elapsed
                    sleep_time = min(wait, remaining, 120)
                    if sleep_time > 0:
                        time.sleep(sleep_time)
                    attempt += 1
                    continue
                return f"Error analyzing video: {e}"
        # If we broke due to time exhaustion, don't try more models
        if time.monotonic() - retry_start >= MAX_RETRY_SECONDS:
            break
    return f"Error analyzing video: {last_error}"


def analyze_videos_batch(
    video_inputs: list[str | Path],
    *,
    product_context: str = "",
    model: str | None = None,
    batch_delay: float | None = None,
) -> list[dict[str, Any]]:
    """
    Analyze multiple videos. Returns list of {url/path, analysis, error}.
    Adds delay between requests to respect Gemini API rate limits (RPM).
    See: https://ai.google.dev/gemini-api/docs/rate-limits
    """
    if SKIP_GEMINI_ANALYSIS:
        return [{"input": str(inp), "analysis": None, "error": "Skipped (SKIP_GEMINI_ANALYSIS=1)"} for inp in video_inputs]

    delay = batch_delay if batch_delay is not None else DEFAULT_BATCH_DELAY
    results = []
    for i, inp in enumerate(video_inputs):
        if i > 0 and delay > 0:
            time.sleep(delay)
        r = {"input": str(inp), "analysis": None, "error": None}
        try:
            r["analysis"] = analyze_video_with_gemini(
                inp, product_context=product_context, model=model
            )
        except Exception as e:
            r["error"] = str(e)
        results.append(r)
    return results
