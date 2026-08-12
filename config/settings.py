import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Fetch Discord Token
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")

# Optional Guild ID for quick slash command syncing during development
GUILD_ID_RAW = os.getenv("GUILD_ID")
GUILD_ID = int(GUILD_ID_RAW) if GUILD_ID_RAW and GUILD_ID_RAW.strip().isdigit() else None

# Configurable Bot Owner ID for admin self-approval testing overrides
BOT_OWNER_ID_RAW = os.getenv("BOT_OWNER_ID")
BOT_OWNER_ID = int(BOT_OWNER_ID_RAW) if BOT_OWNER_ID_RAW and BOT_OWNER_ID_RAW.strip().isdigit() else None

# Configurable Staff Role ID for support ticket permissions
STAFF_ROLE_ID_RAW = os.getenv("STAFF_ROLE_ID")
STAFF_ROLE_ID = int(STAFF_ROLE_ID_RAW) if STAFF_ROLE_ID_RAW and STAFF_ROLE_ID_RAW.strip().isdigit() else None

# Website Integration API Configuration
GEN_API_KEY = os.getenv("GEN_API_KEY", "")
CORS_ORIGINS_RAW = os.getenv("CORS_ORIGINS", "http://localhost:3000,http://localhost:8000")
CORS_ORIGINS = [origin.strip() for origin in CORS_ORIGINS_RAW.split(",") if origin.strip()]

# Discord Server Invite URL
DISCORD_INVITE_URL = os.getenv("DISCORD_INVITE_URL", "https://discord.gg/G568r5MFqB")

# SQLite Database Location
DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "..", "tournament.db"))

# API Server Host & Port
API_HOST = os.getenv("API_HOST", "127.0.0.1")
API_PORT = int(os.getenv("API_PORT", "8000"))

def validate_config():
    """Ensure essential configuration parameters are present."""
    logger = logging.getLogger("GENEsportsBot")
    if not DISCORD_TOKEN or DISCORD_TOKEN == "your_discord_bot_token_here":
        raise ValueError(
            "\n[ERROR] DISCORD_TOKEN is missing or not configured!\n"
            "Please create a '.env' file in the root folder, copy the template from '.env.example',\n"
            "and set your actual Discord bot token from the Discord Developer Portal."
        )

    if BOT_OWNER_ID is None:
        logger.warning("⚠️ [CONFIG WARNING] BOT_OWNER_ID is not configured in .env. Bot owner self-approval override will be disabled.")
    else:
        logger.info(f"👑 Configured BOT_OWNER_ID: {BOT_OWNER_ID}")

    if not GEN_API_KEY:
        logger.warning("⚠️ [CONFIG WARNING] GEN_API_KEY is not configured in .env. API authentication will fail.")
    else:
        logger.info("🔑 Configured GEN_API_KEY for Website Integration API.")
