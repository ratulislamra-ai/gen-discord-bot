# 🚀 GEN Esports Discord Bot - VPS Production Deployment Guide

This document provides a step-by-step guide for deploying and operating the **GEN Esports Discord Tournament Registration Bot** and FastAPI backend on a Linux VPS (Ubuntu 20.04 / 22.04 / 24.04 LTS recommended).

---

## 📋 Initial VPS Environment Checklist

Before deployment, run the following commands on your VPS terminal to inspect the environment:

1. **Check OS & Version:**
   ```bash
   lsb_release -a || cat /etc/os-release
   ```
2. **Check Python Version (Python 3.10+ required):**
   ```bash
   python3 --version
   ```
3. **Check Git Availability:**
   ```bash
   git --version
   ```
4. **Check Available Ports & Firewall:**
   Ensure outbound port `443` (Discord Gateway) is open, and port `8000` (FastAPI REST API server) is open if website integration is used.
   ```bash
   sudo ufw status
   ```

---

## 🛠️ Automated 1-Click Deployment (Recommended)

The repository contains an automated deployment script `deploy.sh` that sets up system dependencies, python virtual environments, `.env` file, SQLite backup cron jobs, and the `systemd` background service.

### Quick Run:

```bash
# 1. Clone repository to your VPS
git clone <YOUR_GIT_REPOSITORY_URL> gen-discord-bot
cd gen-discord-bot

# 2. Make deploy.sh executable
chmod +x deploy.sh

# 3. Run deployment script
./deploy.sh
```

---

## ⚙️ Manual Deployment Step-by-Step

If you prefer to set up your VPS manually, follow these steps:

### Step 1: Install System Dependencies
```bash
sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv git sqlite3 curl
```

### Step 2: Set Up Python Virtual Environment
```bash
cd /home/YOUR_SSH_USERNAME/gen-discord-bot
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

### Step 3: Configure Environment Variables (`.env`)
Create a production `.env` file from `.env.example`:
```bash
cp .env.example .env
nano .env
```
Ensure your secrets are configured securely:
```env
DISCORD_TOKEN=your_actual_discord_bot_token
BOT_OWNER_ID=1146803287841050674
GEN_API_KEY=your_secure_api_key_here
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
DISCORD_INVITE_URL=https://discord.gg/your_invite
API_HOST=0.0.0.0
API_PORT=8000
```
> [!SECURITY]
> **Important Security Rules:**
> - Never commit `.env` to Git repository.
> - `.env` is listed in `.gitignore` and must remain secret.

### Step 4: Database Safety & Initial Backup
To create a safe backup of your SQLite database before running the service:
```bash
python3 scripts/backup_db.py
```
Database backups will be saved with timestamps in the `./backups/` directory.

### Step 5: Install Systemd Service (`gen-esports-bot.service`)
Create the systemd service file:
```bash
sudo nano /etc/systemd/system/gen-esports-bot.service
```
Insert the following configuration (replace `ubuntu` and path with your actual SSH username and directory):
```ini
[Unit]
Description=GEN Esports Discord Tournament Registration Bot & API Service
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/gen-discord-bot
ExecStart=/home/ubuntu/gen-discord-bot/venv/bin/python main.py
Restart=always
RestartSec=10
EnvironmentFile=/home/ubuntu/gen-discord-bot/.env

StandardOutput=journal
StandardError=journal
SyslogIdentifier=gen-esports-bot

PrivateTmp=true

[Install]
WantedBy=multi-user.target
```

Reload systemd daemon, enable automatic start on boot, and launch the service:
```bash
sudo systemctl daemon-reload
sudo systemctl enable gen-esports-bot
sudo systemctl start gen-esports-bot
```

---

## 🌐 Nginx Reverse Proxy & Domain Setup (Optional / Recommended for Web Server)

To expose your website and REST API on Port `80` / `443` with custom domain and HTTPS SSL certificate:

### 1. Install Nginx & Certbot
```bash
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

### 2. Create Nginx Site Configuration
```bash
sudo nano /etc/nginx/sites-available/genesports.conf
```

Insert the following production configuration for `genesports.online`:

```nginx
# 1. HTTP -> HTTPS Redirect for main domain & www
server {
    listen 80;
    listen [::]:80;
    server_name genesports.online www.genesports.online;

    location / {
        return 301 https://genesports.online$request_uri;
    }
}

# 2. HTTPS Main Server Block
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name genesports.online;

    client_max_body_size 10M;

    # Proxy all traffic to FastAPI application (serves website & API)
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
    }
}

# 3. www -> non-www HTTPS Redirect
server {
    listen 443 ssl http2;
    listen [::]:443 ssl http2;
    server_name www.genesports.online;

    return 301 https://genesports.online$request_uri;
}
```

### 3. Enable Site & Reload Nginx
```bash
sudo ln -s /etc/nginx/sites-available/genesports.conf /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 4. Enable Free SSL Certificate (HTTPS via Certbot)
```bash
sudo certbot --nginx -d genesports.online -d www.genesports.online
```

---

## 🎮 VPS Service Management Commands

Use these standard commands to manage your Discord Bot service on the VPS:

| Action | Command |
| :--- | :--- |
| **Check Bot Status** | `sudo systemctl status gen-esports-bot` |
| **Start Bot** | `sudo systemctl start gen-esports-bot` |
| **Stop Bot** | `sudo systemctl stop gen-esports-bot` |
| **Restart Bot** | `sudo systemctl restart gen-esports-bot` |
| **View Live Logs** | `sudo journalctl -u gen-esports-bot -f` |
| **View Recent Errors** | `sudo journalctl -u gen-esports-bot -p err..emerg -n 50` |

---

## 🔄 Updating Bot After Code Changes

When you push new code changes or fixes to Git:

```bash
cd /home/YOUR_SSH_USERNAME/gen-discord-bot

# 1. Backup live database first
venv/bin/python scripts/backup_db.py

# 2. Pull latest code from repository
git pull

# 3. Update python dependencies if requirements changed
venv/bin/pip install -r requirements.txt

# 4. Restart bot service
sudo systemctl restart gen-esports-bot

# 5. Check live logs to confirm clean startup
sudo journalctl -u gen-esports-bot -f
```

---

## 🧪 Post-Deployment Verification Checklist

Verify all features on Discord after deployment or restarts:

- [ ] **Slash Command Sync:** Run `/setup_registration_panel` in an admin channel.
- [ ] **Registration Panel:** Click `🏆 Register for Tournament`. Verify a private ticket channel opens.
- [ ] **Tournament Selection:** Select a tournament from the dropdown menu (e.g. *GEN Valorant Championship* or *GEN PUBG Mobile Championship*).
- [ ] **Team Information:** Enter team details in the modal.
- [ ] **Roster & Logo Upload:** Add player roster and submit team logo URL or file.
- [ ] **Admin Review:** Run `/setup_admin` in your admin channel. Verify review card appears with `✅ Approve Registration` and `❌ Reject Registration` buttons.
- [ ] **Bot Restart Test:** Run `sudo systemctl restart gen-esports-bot`. Verify buttons and ticket channels continue working seamlessly (Discord persistent UI views).
- [ ] **Database Integrity:** Verify SQLite database (`tournament.db`) and user registration records remain completely intact after restarts.
