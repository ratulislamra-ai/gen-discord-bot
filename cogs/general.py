import discord
from discord.ext import commands
from discord import app_commands

class GeneralCog(commands.Cog):
    """General utility commands for the GEN Esports Discord Bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="ping", description="Check the bot's latency and connection health.")
    async def ping(self, interaction: discord.Interaction):
        """Slash command to verify the bot is online and measure round-trip latency."""
        # Calculate WebSocket latency in milliseconds
        latency_ms = round(self.bot.latency * 1000)

        # Create a visually appealing Embed for GEN Esports branding
        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"GEN Esports Bot is active and responding.\n\n**Latency:** `{latency_ms} ms`",
            color=discord.Color.blue()
        )
        embed.set_footer(text="GEN Esports Tournament System • Step 1 Base Setup")

        # Send response to the user
        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    """Asynchronous setup function to register GeneralCog with the bot."""
    await bot.add_cog(GeneralCog(bot))
