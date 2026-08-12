import asyncio
import logging
import discord
from discord.ext import commands
from config.settings import DISCORD_TOKEN, GUILD_ID, API_HOST, API_PORT, validate_config
from database.db import init_db
from cogs.registration import (
    RegistrationPanel, 
    TournamentSelectionView, 
    ContinueToTeamView, 
    ContinueToRosterView,
    EnterRosterView,
    RosterPart2View,
    RosterPart3View,
    RosterSummaryView,
    RegistrationReviewView,
    UploadLogoView,
    AdminReviewView,
    CloseTicketView
)
from api.server import run_api_server_async

# Configure logging for terminal output
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("GENEsportsBot")

class GENBot(commands.Bot):
    """Custom Bot class for GEN Esports Tournament Registration System."""

    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True

        super().__init__(
            command_prefix="!",
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        """Asynchronously load database, persistent views, cogs, and initialize command tree."""
        # 1. Initialize SQLite database schema & migrations
        logger.info("Initializing SQLite database...")
        await init_db()
        logger.info("SQLite database initialized successfully.")

        # 2. Register Persistent UI Views
        self.add_view(RegistrationPanel())
        self.add_view(TournamentSelectionView())
        self.add_view(ContinueToTeamView())
        self.add_view(ContinueToRosterView())
        self.add_view(EnterRosterView())
        self.add_view(RosterPart2View())
        self.add_view(RosterPart3View())
        self.add_view(RosterSummaryView())
        self.add_view(RegistrationReviewView())
        self.add_view(UploadLogoView())
        self.add_view(AdminReviewView())
        self.add_view(CloseTicketView())
        logger.info("Registered persistent UI views (RegistrationPanel, TournamentSelectionView, ContinueToTeamView, ContinueToRosterView, EnterRosterView, RosterPart2View, RosterPart3View, RosterSummaryView, RegistrationReviewView, UploadLogoView, AdminReviewView, CloseTicketView).")

        # 3. Load extension cogs
        logger.info("Loading bot extensions (cogs)...")
        cogs = ["cogs.general", "cogs.registration"]
        for cog in cogs:
            try:
                await self.load_extension(cog)
                logger.info(f"Loaded extension cog: {cog}")
            except Exception as e:
                logger.error(f"Failed to load extension cog {cog}: {e}")

        # 4. Verify command tree registration
        tree_commands = [cmd.name for cmd in self.tree.get_commands()]
        logger.info(f"Command tree initialized with {len(tree_commands)} command(s): {tree_commands}")

    async def on_ready(self):
        """Event triggered when the bot completes gateway connection."""
        logger.info("==================================================")
        logger.info(f"Bot logged in successfully as: {self.user} (ID: {self.user.id})")
        logger.info(f"Connected to {len(self.guilds)} guild(s)")

        logger.info("[SLASH SYNC] Starting command sync...")

        target_guilds = []
        if GUILD_ID:
            target_guilds = [discord.Object(id=GUILD_ID)]
        else:
            target_guilds = [discord.Object(id=g.id) for g in self.guilds]

        for guild_obj in target_guilds:
            guild_id_val = getattr(guild_obj, "id", GUILD_ID)
            logger.info(f"[SLASH SYNC] Guild ID: {guild_id_val}")
            try:
                self.tree.copy_global_to(guild=guild_obj)
                synced = await self.tree.sync(guild=guild_obj)
                synced_names = [c.name for c in synced]
                logger.info(f"[SLASH SYNC] Commands synced to Guild {guild_id_val}: {synced_names}")
                logger.info(f"[SLASH SYNC] setup_registration_panel FOUND: {'setup_registration_panel' in synced_names}")
                logger.info(f"[SLASH SYNC] setup_admin FOUND: {'setup_admin' in synced_names}")
            except Exception as e:
                logger.error(f"[SLASH SYNC ERROR] Failed to sync commands to Guild {guild_id_val}: {e}", exc_info=e)

        # Global command sync fallback
        try:
            synced_global = await self.tree.sync()
            global_names = [c.name for c in synced_global]
            logger.info(f"[SLASH SYNC GLOBAL] Global sync complete ({len(synced_global)} command(s)): {global_names}")
        except Exception as e:
            logger.error(f"[SLASH SYNC GLOBAL ERROR] Failed global sync: {e}", exc_info=e)

        logger.info(f"WebSocket Latency: {round(self.latency * 1000)} ms")
        logger.info("GEN Esports Tournament Bot is Online & Ready!")
        logger.info("==================================================")

async def main():
    validate_config()
    bot = GENBot()

    # Launch REST API server alongside Discord bot in the same asyncio event loop
    api_task = asyncio.create_task(run_api_server_async(host=API_HOST, port=API_PORT))

    try:
        await bot.start(DISCORD_TOKEN)
    finally:
        api_task.cancel()

if __name__ == "__main__":
    asyncio.run(main())
