#!/usr/bin/env bash
set -o errexit

# Install dependencies
pip install -r requirements.txt

# Collect static files (run from api/ where manage.py lives)
cd api && python manage.py collectstatic --no-input --clear

# Run migrations
python manage.py migrate --no-input
