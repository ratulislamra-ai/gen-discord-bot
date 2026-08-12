#!/usr/bin/env bash
# ==============================================================================
# GEN Esports Discord Tournament Bot - Production Deployment Script
# Target: /root/gen-discord-bot on Production VPS (Ubuntu 24.04)
# ==============================================================================

set -e

PROJECT_DIR="/root/gen-discord-bot"
REPO_URL="https://github.com/ratulislamra-ai/gen-discord-bot.git"
SERVICE_NAME="gen-esports-bot"

echo "=================================================="
echo "🚀 Starting GEN Esports Production Deployment"
echo "=================================================="

# 1. Ensure directory exists
cd "$PROJECT_DIR" || exit 1

# 2. Initialize Git repo if missing
if [ ! -d ".git" ]; then
    echo "⚠️ .git repository missing. Initializing git repository..."
    git init
    git remote add origin "$REPO_URL" || git remote set-url origin "$REPO_URL"
fi

# 3. Perform automated database backup before changes
echo "💾 Performing automated pre-deployment database backup..."
mkdir -p backups
if [ -f "venv/bin/python" ] && [ -f "scripts/backup_db.py" ]; then
    venv/bin/python scripts/backup_db.py || echo "Warning: Backup script finished with alert"
elif command -v python3 &>/dev/null && [ -f "scripts/backup_db.py" ]; then
    python3 scripts/backup_db.py || echo "Warning: Backup script finished with alert"
fi

# 4. Fetch latest code from GitHub
echo "📥 Fetching latest code from origin/main..."
git fetch origin main

# 5. Safely reset code tree to origin/main preserving .env, tournament.db, backups, uploads
echo "🔄 Synchronizing code with origin/main..."
git reset --hard origin/main

# 6. Verify Python Virtual Environment & Install Dependencies
echo "📦 Verifying virtual environment dependencies..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi

venv/bin/pip install --upgrade pip setuptools wheel --quiet
venv/bin/pip install -r requirements.txt --quiet

# 7. Run Python syntax & import sanity checks
echo "🧪 Running syntax and cog loading checks..."
venv/bin/python -c "import asyncio, main; bot = main.GENBot(); asyncio.run(bot.setup_hook()); print('Sanity Check PASSED: Commands total =', len(bot.tree.get_commands()))"

# 8. Restart Systemd Service
echo "🔄 Restarting systemd service (${SERVICE_NAME}.service)..."
systemctl restart "$SERVICE_NAME"

# 9. Verify Systemd Service Status
echo "🏥 Checking service health status..."
sleep 3
if systemctl is-active --quiet "$SERVICE_NAME"; then
    echo "✅ Service ${SERVICE_NAME} is ACTIVE and RUNNING!"
else
    echo "❌ Service ${SERVICE_NAME} failed to start!"
    systemctl status "$SERVICE_NAME" --no-pager
    exit 1
fi

# 10. Check recent service logs for slash command tree verification
echo "📋 Inspecting recent service logs..."
journalctl -u "$SERVICE_NAME" -n 25 --no-pager

# 11. Verify Website & Public API Endpoints
echo "🌐 Verifying Website & Public API health..."
if command -v curl &>/dev/null; then
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://genesports.online || echo "000")
    echo "Production Website Status: HTTP $HTTP_CODE"
    API_CODE=$(curl -s -o /dev/null -w "%{http_code}" https://genesports.online/api/public/tournaments || echo "000")
    echo "Public API Status: HTTP $API_CODE"
fi

echo "=================================================="
echo "🎉 GEN Esports Production Deployment Complete!"
echo "=================================================="
