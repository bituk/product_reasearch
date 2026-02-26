#!/usr/bin/env bash
# One-time setup for Oracle Cloud Free Tier VM (Ubuntu 20.04/22.04)
# Run as: sudo bash setup.sh

set -e

export DEBIAN_FRONTEND=noninteractive

echo "==> Updating system..."
apt-get update && apt-get upgrade -y

echo "==> Installing Python, Redis, Nginx..."
apt-get install -y python3 python3-pip python3-venv redis-server nginx

echo "==> Installing build dependencies for Python packages..."
apt-get install -y build-essential libpq-dev

echo "==> Creating app user (optional, for security)..."
id -u appuser &>/dev/null || useradd -m -s /bin/bash appuser || true

echo "==> Setting up app directory..."
APP_DIR="${APP_DIR:-/opt/product_research}"
mkdir -p "$APP_DIR"
chown -R "$(whoami):$(whoami)" "$APP_DIR" 2>/dev/null || true

echo "==> Enabling Redis..."
systemctl enable redis-server
systemctl start redis-server

echo "==> Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Clone your repo to $APP_DIR"
echo "  2. Copy .env to $APP_DIR and configure"
echo "  3. Run: ./deploy/oracle/deploy.sh (as app user, not root)"
