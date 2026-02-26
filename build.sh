#!/usr/bin/env bash
set -o errexit

# Install dependencies (requirements.txt at root includes api/requirements.txt)
pip install -r requirements.txt

# Collect static files and run migrations
cd api && python manage.py collectstatic --no-input --clear
python manage.py migrate --no-input
