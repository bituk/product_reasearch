# Deploy on Oracle Cloud Free Tier VM

## Prerequisites

- Oracle Cloud Free Tier account
- Ubuntu 20.04 or 22.04 VM (default on Oracle)
- VM public IP and open port 80 (and 22 for SSH)

## 1. Create VM & Open Firewall

1. Create a Compute Instance (VM.Standard.E2.1.Micro — free tier)
2. Use Ubuntu 22.04 image
3. In **Networking** → **Subnet** → **Security List**: add Ingress rules for port 22 (SSH), 80 (HTTP), and 8000 (if not using Nginx)
4. SSH: `ssh ubuntu@<your-vm-public-ip>`

## 2. One-Time Setup

```bash
# Update and install dependencies
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-pip python3-venv redis-server nginx build-essential libpq-dev git

# Clone your repo (replace with your repo URL)
sudo mkdir -p /opt
sudo git clone https://github.com/YOUR_USER/product_reasearch.git /opt/product_research
sudo chown -R ubuntu:ubuntu /opt/product_research
```

## 3. Configure Environment

```bash
cd /opt/product_research
cp .env.example .env
nano .env   # Edit: SUPABASE_DB_URL, API keys, etc.
```

**Required in .env:**
- `SUPABASE_DB_URL` or `DATABASE_URL` — PostgreSQL connection string
- `DJANGO_SECRET_KEY` — generate: `python3 -c "import secrets; print(secrets.token_urlsafe(50))"`
- `DJANGO_DEBUG=0`
- `DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1,YOUR_VM_PUBLIC_IP` (add your VM IP!)
- `CELERY_BROKER_URL=redis://localhost:6379/0`
- `CELERY_RESULT_BACKEND=redis://localhost:6379/0`
- API keys: `OPENAI_API_KEY`, `GEMINI_API_KEY`, `APIFY_API_TOKEN`, etc.

## 4. Deploy

```bash
cd /opt/product_research
chmod +x deploy/oracle/deploy.sh
./deploy/oracle/deploy.sh
```

## 5. Optional: Nginx Reverse Proxy

```bash
sudo cp /opt/product_research/deploy/oracle/nginx.conf /etc/nginx/sites-available/product_research
sudo ln -sf /etc/nginx/sites-available/product_research /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default   # or keep for default site
# Update server_name in nginx.conf if using a domain
sudo nginx -t && sudo systemctl reload nginx
```

Then access via `http://YOUR_VM_IP` (port 80). Without nginx, use `http://YOUR_VM_IP:8000`.

## 6. Create Admin User

```bash
cd /opt/product_research/api
source ../venv/bin/activate
python manage.py createsuperuser
```

## 7. Update After Code Changes

```bash
cd /opt/product_research
git pull
./deploy/oracle/deploy.sh
```

## Troubleshooting

| Issue | Fix |
|-------|-----|
| 502 Bad Gateway | Check `sudo systemctl status gunicorn` |
| Celery not processing | Check `sudo systemctl status celery` and Redis: `redis-cli ping` |
| CORS errors | Add frontend URL to `CORS_ALLOWED_ORIGINS` in .env |
| DisallowedHost | Add your VM IP to `DJANGO_ALLOWED_HOSTS` in .env |
