"""
Gemini multimodal video analysis.
Analyzes videos (via YouTube URL or local file) for creative insights:
hooks, CTAs, format, engagement patterns, script/structure.
Responses are cached (disable with CREATIVE_RESEARCH_NO_CACHE=1).
"""

import os
from pathlib import Path
from typing import Any

from creative_research.cache import load_cached, save_cached

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
    api_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            "GEMINI_API_KEY or GOOGLE_API_KEY required for video analysis. Set in .env"
        )
    try:
        import warnings
        with warnings.catch_warnings(action="ignore", category=FutureWarning):
            import google.generativeai as genai
        genai.configure(api_key=api_key)
        return genai
    except ImportError:
        raise ImportError(
            "Install google-generativeai: pip install google-generativeai"
        )


def analyze_video_with_gemini(
    video_input: str | Path,
    *,
    product_context: str = "",
    model: str = "gemini-1.5-flash",
) -> str:
    """
    Analyze a video using Gemini (multimodal).
    Caches responses by video URL + product_context.

    Args:
        video_input: YouTube URL (str) or path to local video file (Path).
        product_context: Optional product/category context for relevance.
        model: Gemini model (gemini-1.5-flash, gemini-1.5-pro, etc.)

    Returns:
        Structured analysis text (markdown).
    """
    inp_str = str(video_input)
    cached, hit = load_cached(
        "gemini_analysis",
        video_input=inp_str,
        product_context=product_context[:500],
        model=model,
    )
    if hit and isinstance(cached, str) and cached.strip():
        return cached

    genai = _configure_gemini()
    prompt = GEMINI_VIDEO_ANALYSIS_PROMPT
    if product_context:
        prompt = f"Product/category context: {product_context[:500]}\n\n{prompt}"

    video_path = Path(video_input) if isinstance(video_input, (str, Path)) else None
    is_url = isinstance(video_input, str) and (
        "youtube.com" in video_input or "youtu.be" in video_input
    )

    try:
        model_obj = genai.GenerativeModel(model)
        if is_url:
            # Gemini can process YouTube URLs directly
            response = model_obj.generate_content([video_input, prompt])
        elif video_path and video_path.exists():
            # Upload file and analyze (google-generativeai)
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
                model=model,
            )
        return analysis
    except Exception as e:
        return f"Error analyzing video: {e}"


def analyze_videos_batch(
    video_inputs: list[str | Path],
    *,
    product_context: str = "",
    model: str = "gemini-1.5-flash",
) -> list[dict[str, Any]]:
    """
    Analyze multiple videos. Returns list of {url/path, analysis, error}.
    """
    results = []
    for inp in video_inputs:
        r = {"input": str(inp), "analysis": None, "error": None}
        try:
            r["analysis"] = analyze_video_with_gemini(
                inp, product_context=product_context, model=model
            )
        except Exception as e:
            r["error"] = str(e)
        results.append(r)
    return results
