"""
Unified LLM client: OpenAI primary, Gemini fallback.
Used for report generation, keywords, and script generation.
"""

import os

from creative_research.constants import (
    GEMINI_API_KEY,
    GEMINI_MODEL,
    OPENAI_API_KEY,
)


def call_llm(
    system: str,
    user: str,
    *,
    openai_model: str = "gpt-4o",
    gemini_model: str | None = None,
    temperature: float = 0.4,
) -> str:
    """
    Call LLM for text generation. Tries OpenAI first, falls back to Gemini on failure.

    Args:
        system: System prompt / instructions.
        user: User message / main prompt.
        openai_model: OpenAI model (default gpt-4o).
        gemini_model: Gemini model for fallback (default from GEMINI_MODEL env).
        temperature: Sampling temperature (default 0.4).

    Returns:
        Generated text.
    """
    # 1) Try OpenAI
    openai_key = os.environ.get("OPENAI_API_KEY") or OPENAI_API_KEY
    if openai_key:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=openai_key)
            resp = client.chat.completions.create(
                model=openai_model,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                temperature=temperature,
            )
            text = (resp.choices[0].message.content or "").strip()
            if text:
                return text
        except Exception:
            pass  # Fall through to Gemini

    # 2) Fallback to Gemini
    if not GEMINI_API_KEY:
        raise ValueError(
            "No LLM available. Set OPENAI_API_KEY or GEMINI_API_KEY (or GOOGLE_API_KEY) in .env"
        )
    try:
        import warnings
        with warnings.catch_warnings(action="ignore", category=FutureWarning):
            import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        model_name = gemini_model or GEMINI_MODEL
        model = genai.GenerativeModel(model_name, system_instruction=system)
        response = model.generate_content(
            user,
            generation_config=genai.GenerationConfig(temperature=temperature),
        )
        return (response.text or "").strip()
    except Exception as e:
        raise RuntimeError(
            f"OpenAI failed and Gemini fallback failed: {e}. "
            "Check OPENAI_API_KEY and GEMINI_API_KEY."
        ) from e


def call_llm_json(
    prompt: str,
    *,
    openai_model: str = "gpt-4o",
    gemini_model: str | None = None,
    temperature: float = 0.3,
) -> str:
    """
    Call LLM for JSON-style output (e.g. keywords). Tries OpenAI first, Gemini fallback.
    Returns raw text; caller parses JSON.
    """
    system = "Output valid JSON only. No markdown code blocks, no preamble."
    return call_llm(
        system, prompt,
        openai_model=openai_model,
        gemini_model=gemini_model,
        temperature=temperature,
    )
