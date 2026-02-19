# Pipeline v2 — Manager Requirements

Implements the full orchestration requested:

> **Research doc → Video scrape → Download (yt-dlp) → Analysis (Gemini) → Competitor research → LLM generation → Scripts**

## Features

### 1. Video Scraped Links + Download via yt-dlp
- Scrapes video links from YouTube, TikTok, Instagram (via Apify + YouTube Data API)
- Downloads videos via **yt-dlp** to local storage
- Extracts **transcripts/scripts** from subtitles (VTT) or youtube-transcript-api fallback

### 2. Gemini Video Analysis
- Analyzes videos (YouTube URL or local file) with **Gemini** multimodal
- Extracts: **Hook**, **CTA**, **Format**, **Engagement drivers**, **Script structure**
- Product context passed for relevance

### 3. Reference Video Stats
- **Views**, **Likes**, **Comments**, **Shares** (where available)
- **CTA summary** from Gemini analysis
- **Spend**, **Clicks**, **CTR** fields (for ad library data when available)

### 4. Video Scripts Generation
- LLM generates **3 distinct video scripts** from research + video analysis
- Each script: Platform, Format, Hook, Full script, CTA, Why it works

### 5. Orchestration via LLM + MCPs
- **MCP tools** for full pipeline or step-by-step:
  - `run_full_research_pipeline` — end-to-end
  - `download_videos_and_extract_transcripts`
  - `analyze_videos_with_gemini`
  - `generate_video_scripts_from_research`
- Cursor/Claude can orchestrate via MCP

## Troubleshooting

### TikTok videos not downloading via POST/API
- **Restart the Celery worker** after code changes: `Ctrl+C` then `celery -A api worker -l info`
- The worker caches code at startup; it won't pick up changes until restarted
- Ensure `APIFY_API_TOKEN` is set (required for TikTok download via Apify storage)

## Usage

### Full pipeline (Python)
```python
from creative_research.pipeline_v2 import run_pipeline_v2

result = run_pipeline_v2(
    "https://www.flipkart.com/redmi-a5-...",
    download_videos=True,
    max_videos_to_download=5,
    max_videos_to_analyze=5,
)
print(result["report"])
print(result["scripts"])
```

### MCP (Cursor/Claude)
Add to MCP config:
```json
{
  "mcpServers": {
    "creative-research-report": {
      "command": "python",
      "args": ["-m", "creative_research.mcp_server"],
      "cwd": "/path/to/product_reasearch",
      "env": {
        "OPENAI_API_KEY": "...",
        "GEMINI_API_KEY": "..."
      }
    }
  }
}
```

Then use `run_full_research_pipeline` tool with your product URL.

### CLI (run script)
```bash
pip install -r requirements.txt

# Run full pipeline
python -c "
from creative_research.pipeline_v2 import run_pipeline_v2
r = run_pipeline_v2('YOUR_PRODUCT_URL', download_videos=True)
print(r['scripts'])
"
```

## Env Variables

See `.env.example` for the full list. Key variables:

| Variable | Purpose |
|----------|---------|
| `OPENAI_API_KEY` | Keywords, report, scripts |
| `GEMINI_API_KEY` or `GOOGLE_API_KEY` | Video analysis |
| `YOUTUBE_API_KEY` | Video search |
| `APIFY_API_TOKEN` | TikTok, Instagram |
| `TAVILY_API_KEY` | Competitor research |

## New Files

- `creative_research/video_downloader.py` — yt-dlp download + transcript
- `creative_research/gemini_analyzer.py` — Gemini video analysis
- `creative_research/script_generator.py` — LLM script generation
- `creative_research/pipeline_v2.py` — Full orchestration
