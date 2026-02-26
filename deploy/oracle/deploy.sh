#!/usr/bin/env bash
# Deploy/update Product Research API on Oracle VM
# Run from project root: ./deploy/oracle/deploy.sh

set -e

# Detect project root (parent of deploy/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
VENV="$APP_DIR/venv"
API_DIR="$APP_DIR/api"

# Ensure we're in the right place
if [ ! -f "$API_DIR/manage.py" ]; then
  echo "Error: Expected $API_DIR/manage.py. Run from project root."
  exit 1
fi

echo "==> Deploying from $APP_DIR"

echo "==> Creating virtualenv..."
python3 -m venv "$VENV" 2>/dev/null || true
source "$VENV/bin/activate"

echo "==> Installing dependencies..."
pip install -q --upgrade pip
pip install -q -r "$API_DIR/requirements.txt"

echo "==> Collecting static files..."
cd "$API_DIR" && python manage.py collectstatic --no-input --clear 2>/dev/null || true

echo "==> Running migrations..."
python manage.py migrate --no-input

echo "==> Installing systemd services..."
sudo cp "$APP_DIR/deploy/oracle/gunicorn.service" /etc/systemd/system/
sudo cp "$APP_DIR/deploy/oracle/celery.service" /etc/systemd/system/

# Update paths in service files if APP_DIR differs
sudo sed -i "s|/opt/product_research|$APP_DIR|g" /etc/systemd/system/gunicorn.service
sudo sed -i "s|/opt/product_research|$APP_DIR|g" /etc/systemd/system/celery.service

# Update user (Oracle default is often ubuntu)
CURRENT_USER=$(whoami)
sudo sed -i "s|User=ubuntu|User=$CURRENT_USER|g" /etc/systemd/system/gunicorn.service
sudo sed -i "s|Group=ubuntu|Group=$CURRENT_USER|g" /etc/systemd/system/gunicorn.service
sudo sed -i "s|User=ubuntu|User=$CURRENT_USER|g" /etc/systemd/system/celery.service
sudo sed -i "s|Group=ubuntu|Group=$CURRENT_USER|g" /etc/systemd/system/celery.service

echo "==> Reloading and starting services..."
sudo systemctl daemon-reload
sudo systemctl enable gunicorn celery
sudo systemctl restart gunicorn celery

echo ""
echo "==> Deploy complete!"
echo "  API: http://localhost:8000 (or your VM public IP)"
echo "  Check: sudo systemctl status gunicorn celery"
