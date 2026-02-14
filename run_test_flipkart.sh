#!/usr/bin/env bash
# Test pipeline for Flipkart Redmi A5. Run from project root.
# Usage: ./run_test_flipkart.sh   or   bash run_test_flipkart.sh
# Python loads .env automatically; ensure OPENAI_API_KEY is set in .env.

set -e
cd "$(dirname "$0")"

URL="https://www.flipkart.com/redmi-a5-jaisalmer-gold-64-gb/p/itm2b4357effaa74?pid=MOBHB2HGH5DCFNWZ&lid=LSTMOBHB2HGH5DCFNWZHAP4LG&marketplace=FLIPKART"

echo "Running pipeline for Flipkart Redmi A5..."
python3 cron/generate_report_job.py "$URL" -o report_flipkart_redmi.md

echo "Done. Report saved to report_flipkart_redmi.md"
