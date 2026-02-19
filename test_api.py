#!/usr/bin/env python3
"""
Test both API endpoints: start pipeline and get status.
Uses PRODUCT_URL from .env.

Usage:
  # Terminal 1: start server (with SQLite if no PostgreSQL)
  USE_SQLITE=1 cd api && python manage.py migrate && python manage.py runserver

  # Terminal 2: run test
  python test_api.py
"""
import sys
import time
from pathlib import Path

# Load .env via constants
_root = Path(__file__).resolve().parent
sys.path.insert(0, str(_root))
from creative_research.constants import API_BASE_URL, PRODUCT_URL
if not PRODUCT_URL:
    print("Error: PRODUCT_URL not set in .env", file=sys.stderr)
    sys.exit(1)

BASE_URL = API_BASE_URL


def test_start_pipeline(product_url=None, skip_apify=False):
    """POST /api/pipeline/start/ - product_url from env if not provided, skip_apify flag"""
    import urllib.request
    import json

    url = f"{BASE_URL}/api/pipeline/start/"
    payload = {"skip_apify": skip_apify}
    if product_url:
        payload["product_url"] = product_url
    # When product_url omitted, API uses PRODUCT_URL from env
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            print("=== POST /api/pipeline/start/ ===")
            print(json.dumps(body, indent=2))
            return body.get("id")
    except urllib.error.HTTPError as e:
        print(f"Error: {e.code} {e.reason}", file=sys.stderr)
        print(e.read().decode(), file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"Error: {e.reason}", file=sys.stderr)
        return None


def test_job_status(job_id):
    """GET /api/pipeline/status/<job_id>/"""
    import urllib.request
    import json

    url = f"{BASE_URL}/api/pipeline/status/{job_id}/"
    req = urllib.request.Request(url, method="GET")

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode())
            print("\n=== GET /api/pipeline/status/<job_id>/ ===")
            # Truncate report/scripts for display
            out = {k: v for k, v in body.items() if k not in ("report", "scripts")}
            if body.get("report"):
                out["report"] = f"<{len(body['report'])} chars>"
            if body.get("scripts"):
                out["scripts"] = f"<{len(body['scripts'])} chars>"
            print(json.dumps(out, indent=2, default=str))
            return body
    except urllib.error.HTTPError as e:
        print(f"Error: {e.code} {e.reason}", file=sys.stderr)
        print(e.read().decode(), file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"Error: {e.reason}", file=sys.stderr)
        return None


def main():
    print(f"Product URL: {PRODUCT_URL[:60]}...")
    print(f"Base URL: {BASE_URL}")

    # Test with product_url from env and skip_apify=False
    job_id = test_start_pipeline(product_url=PRODUCT_URL, skip_apify=False)
    if not job_id:
        sys.exit(1)

    # Poll status until completed or failed
    for i in range(60):
        time.sleep(2)
        result = test_job_status(job_id)
        if not result:
            sys.exit(1)
        status = result.get("status")
        print(f"  Status: {status} | Stage: {result.get('current_stage', 'N/A')}")
        if status in ("completed", "failed"):
            break

    if result.get("status") == "completed":
        print("\n✓ Pipeline completed successfully")
    else:
        print(f"\n✗ Pipeline ended with status: {result.get('status')}")
        if result.get("error_message"):
            print(f"  Error: {result['error_message']}")


if __name__ == "__main__":
    main()
