# GEN Esports - Discord Tournament Registration Bot

Welcome to the **GEN Esports Discord Bot** project! This bot is built using **Python 3.10+**, **discord.py 2.x**, **SQLite**, and **python-dotenv**.

---

## 📁 Project Structure

```text
gen-discord-bot/
├── cogs/
│   ├── __init__.py
│   └── general.py          # Cog for general commands (includes /ping)
├── config/
│   ├── __init__.py
│   └── settings.py         # Loads and validates environment variables (.env)
├── database/
│   └── __init__.py         # Reserved for SQLite database models (future steps)
├── utils/
│   └── __init__.py         # Reserved for reusable utility functions (future steps)
├── .env.example            # Template for environment configuration
├── .gitignore              # Files ignored by Git (protects secrets & database)
├── main.py                 # Primary entry point & bot launcher
├── requirements.txt        # Python package dependencies
└── README.md               # Setup and execution guide
```

---

## 🚀 Beginner Setup & Execution Guide

Follow these steps to configure, install dependencies, and run your Discord bot.

### Step 1: Create a Discord Bot on the Developer Portal

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications).
2. Click **New Application** at the top right and name it **GEN Esports Bot**.
3. In the left menu, click **Bot**.
4. Click **Reset Token** (or **Copy Token**) to generate your Bot Token.
   > ⚠️ **IMPORTANT:** Keep this token private! Never share it or commit it to GitHub.
5. In the **Privileged Gateway Intents** section, turn ON:
   - **Message Content Intent** (Required for processing commands and text).
6. Save your changes.

---

### Step 2: Invite the Bot to Your Server

1. In the Developer Portal, click **OAuth2** -> **URL Generator** in the left menu.
2. Under **Scopes**, select:
   - `bot`
   - `applications.commands` (Required for slash commands like `/ping`).
3. Under **Bot Permissions**, select:
   - `Send Messages`
   - `Embed Links`
   - `Read Message History`
4. Copy the generated URL at the bottom, paste it into your browser, and invite the bot to your Discord server.

---

### Step 3: Set Up Python & Virtual Environment

Open your terminal (PowerShell or Command Prompt) inside this project directory (`C:\Users\Genelion\.gemini\antigravity-ide\scratch\gen-discord-bot`):

1. **Create a virtual environment** (isolates dependencies):
   ```powershell
   python -m venv venv
   ```

2. **Activate the virtual environment**:
   - On Windows (PowerShell):
     ```powershell
     .\venv\Scripts\Activate.ps1
     ```
   - On Windows (Command Prompt):
     ```cmd
     venv\Scripts\activate.bat
     ```
   - On macOS/Linux:
     ```bash
     source venv/bin/activate
     ```

   *(You will see `(venv)` at the beginning of your terminal prompt when activated).*

---

### Step 4: Install Dependencies

With the virtual environment active, run:

```bash
pip install -r requirements.txt
```

---

### Step 5: Configure Environment Secrets (`.env`)

1. Make a copy of `.env.example` named `.env`:
   - On Windows PowerShell:
     ```powershell
     Copy-Item .env.example .env
     ```
2. Open `.env` in your text editor.
3. Paste your Discord bot token:
   ```env
   DISCORD_TOKEN=paste_your_actual_bot_token_here
   ```
4. *(Optional for Instant Slash Commands)*: Paste your Server's **Guild ID**:
   - Enable Developer Mode in Discord (*User Settings -> Advanced -> Developer Mode*).
   - Right-click your server icon in Discord and click **Copy Server ID**.
   - Paste it into `.env`:
     ```env
     GUILD_ID=123456789012345678
     ```
   *(Providing `GUILD_ID` registers slash commands instantly in your server instead of waiting up to an hour for global sync).*

---

### Step 6: Run the Bot!

Run the main script:

```bash
python main.py
```

You should see output similar to this:
```text
2026-08-11 22:18:00 [INFO] GENEsportsBot: Loading bot extensions (cogs)...
2026-08-11 22:18:00 [INFO] GENEsportsBot: Successfully loaded 'cogs.general'.
2026-08-11 22:18:00 [INFO] GENEsportsBot: Syncing slash commands with Discord...
2026-08-11 22:18:01 [INFO] GENEsportsBot: Synced 1 command(s) instantly to target Guild ID: ...
2026-08-11 22:18:02 [INFO] GENEsportsBot: ==================================================
2026-08-11 22:18:02 [INFO] GENEsportsBot: Bot connected successfully!
2026-08-11 22:18:02 [INFO] GENEsportsBot: Username: GEN Esports Bot#1234 (ID: ...)
2026-08-11 22:18:02 [INFO] GENEsportsBot: Active Guilds: 1
2026-08-11 22:18:02 [INFO] GENEsportsBot: WebSocket Latency: 42 ms
2026-08-11 22:18:02 [INFO] GENEsportsBot: GEN Esports Tournament Bot is Online & Ready!
2026-08-11 22:18:02 [INFO] GENEsportsBot: ==================================================
```

---

### Step 7: Test the Bot in Discord

Go to your Discord server and type:

```text
/ping
```

The bot will reply with an embed displaying:
> **🏓 Pong!**
> GEN Esports Bot is active and responding.
> **Latency:** `42 ms`

---

## 🛠️ Next Steps
In future steps, we will add:
1. SQLite database setup for tournament registrations.
2. Team & Player registration forms (`/register`, `/team`).
3. Admin management & match bracket slash commands.
