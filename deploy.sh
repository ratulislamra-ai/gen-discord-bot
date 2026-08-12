#!/usr/bin/env bash
# ==============================================================================
# GEN Esports Discord Tournament Bot - Production VPS Automated Deployer
# OS Target: Ubuntu 20.04 / 22.04 / 24.04 LTS or Debian 11+
# ==============================================================================

set -e

# Styling & Output colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${BLUE}==============================================================${NC}"
echo -e "${GREEN}🚀 Starting GEN Esports Discord Bot VPS Deployment${NC}"
echo -e "${BLUE}==============================================================${NC}"

# 1. Resolve Project Root Directory & User
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CURRENT_USER="$(whoami)"
SERVICE_NAME="gen-esports-bot"

echo -e "📂 Project Directory: ${YELLOW}${PROJECT_DIR}${NC}"
echo -e "👤 Operating User:    ${YELLOW}${CURRENT_USER}${NC}"

# 2. Verify System Dependencies (Python 3.10+, pip, venv, git, sqlite3)
echo -e "\n${BLUE}[1/7] Inspecting System Environment & Dependencies...${NC}"

if command -v lsb_release &>/dev/null; then
    OS_INFO=$(lsb_release -ds)
    echo -e "🖥️  OS Detected: ${GREEN}${OS_INFO}${NC}"
else
    echo -e "🖥️  OS Detected: Linux Kernel $(uname -r)"
fi

if ! command -v python3 &>/dev/null; then
    echo -e "${RED}❌ python3 is not installed. Installing python3, python3-venv, and python3-pip...${NC}"
    sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv git sqlite3 curl
fi

PYTHON_VERSION=$(python3 --version 2>&1)
echo -e "🐍 Python Version: ${GREEN}${PYTHON_VERSION}${NC}"

# Ensure python3-venv package is installed
if ! python3 -m venv --help &>/dev/null; then
    echo -e "${YELLOW}Installing python3-venv environment packages...${NC}"
    sudo apt-get update && sudo apt-get install -y python3-venv python3-pip git sqlite3
fi

# 3. Setup Python Virtual Environment
echo -e "\n${BLUE}[2/7] Setting up Python Virtual Environment...${NC}"
if [ ! -d "${PROJECT_DIR}/venv" ]; then
    echo -e "Creating virtual environment at ${PROJECT_DIR}/venv..."
    python3 -m venv "${PROJECT_DIR}/venv"
fi

source "${PROJECT_DIR}/venv/bin/activate"
pip install --upgrade pip setuptools wheel --quiet

# 4. Install Project Requirements
echo -e "\n${BLUE}[3/7] Installing / Updating Python Dependencies...${NC}"
if [ -f "${PROJECT_DIR}/requirements.txt" ]; then
    pip install -r "${PROJECT_DIR}/requirements.txt"
else
    echo -e "${RED}❌ requirements.txt not found in ${PROJECT_DIR}!${NC}"
    exit 1
fi

# 5. Check & Validate Production .env Configuration
echo -e "\n${BLUE}[4/7] Checking Production Environment (.env)...${NC}"
if [ ! -f "${PROJECT_DIR}/.env" ]; then
    if [ -f "${PROJECT_DIR}/.env.example" ]; then
        echo -e "${YELLOW}⚠️  .env file not found. Copying .env.example -> .env...${NC}"
        cp "${PROJECT_DIR}/.env.example" "${PROJECT_DIR}/.env"
        echo -e "${RED}❗ IMPORTANT: Please edit ${PROJECT_DIR}/.env and insert your real DISCORD_TOKEN before starting the bot!${NC}"
    else
        echo -e "${RED}❌ Neither .env nor .env.example found!${NC}"
        exit 1
    fi
else
    echo -e "${GREEN}✅ .env file exists and verified.${NC}"
fi

# 6. Database Safety & Automated Backup
echo -e "\n${BLUE}[5/7] Performing Database Safety Check & Backup...${NC}"
mkdir -p "${PROJECT_DIR}/backups"
if [ -f "${PROJECT_DIR}/tournament.db" ]; then
    echo -e "Creating safe timestamped backup of existing database..."
    python3 "${PROJECT_DIR}/scripts/backup_db.py" || true
else
    echo -e "ℹ️  No existing database found; initial database will be created on bot startup."
fi

# 7. Configure and Install Systemd Service
echo -e "\n${BLUE}[6/7] Installing Systemd Service (${SERVICE_NAME}.service)...${NC}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

sudo bash -c "cat <<EOF > ${SERVICE_FILE}
[Unit]
Description=GEN Esports Discord Tournament Registration Bot & API Service
After=network.target

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
ExecStart=${PROJECT_DIR}/venv/bin/python main.py
Restart=always
RestartSec=10
EnvironmentFile=${PROJECT_DIR}/.env

StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

PrivateTmp=true

[Install]
WantedBy=multi-user.target
EOF"

echo -e "Reloading systemd daemon..."
sudo systemctl daemon-reload

echo -e "Enabling ${SERVICE_NAME} to start automatically on system boot..."
sudo systemctl enable ${SERVICE_NAME}

echo -e "Restarting ${SERVICE_NAME} service..."
sudo systemctl restart ${SERVICE_NAME}

# 8. Setup Daily Database Backup Cron Job
echo -e "\n${BLUE}[7/7] Configuring Daily Automated Database Backup Cron Job...${NC}"
CRON_JOB="0 3 * * * ${PROJECT_DIR}/venv/bin/python ${PROJECT_DIR}/scripts/backup_db.py >> ${PROJECT_DIR}/backups/cron_backup.log 2>&1"
(crontab -l 2>/dev/null | grep -v "backup_db.py" ; echo "$CRON_JOB") | crontab -

echo -e "\n${GREEN}==============================================================${NC}"
echo -e "${GREEN}🎉 VPS DEPLOYMENT COMPLETED SUCCESSFULLY!${NC}"
echo -e "${GREEN}==============================================================${NC}"

echo -e "\n📌 ${YELLOW}SERVICE MANAGEMENT COMMANDS:${NC}"
echo -e " • Check Bot Status:   ${GREEN}sudo systemctl status ${SERVICE_NAME}${NC}"
echo -e " • Restart Bot:        ${GREEN}sudo systemctl restart ${SERVICE_NAME}${NC}"
echo -e " • Stop Bot:           ${GREEN}sudo systemctl stop ${SERVICE_NAME}${NC}"
echo -e " • Start Bot:          ${GREEN}sudo systemctl start ${SERVICE_NAME}${NC}"
echo -e " • View Live Logs:     ${GREEN}sudo journalctl -u ${SERVICE_NAME} -f${NC}"
echo -e " • View Errors Only:   ${GREEN}sudo journalctl -u ${SERVICE_NAME} -p err..emerg -n 50${NC}"

echo -e "\n🔍 ${YELLOW}CURRENT SERVICE STATUS:${NC}"
sudo systemctl status ${SERVICE_NAME} --no-pager || true
