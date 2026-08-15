import logging
import discord
from discord.ext import commands
from discord import app_commands

from database.db import (
    get_eligible_cleanup_channels,
    update_channel_cleanup_status,
    get_bot_setting
)

logger = logging.getLogger("GENEsportsBot")

class CleanupPromptView(discord.ui.View):
    """Interactive Admin Prompt View for deleting or retaining temporary Discord channels."""

    def __init__(self, channel_id: str, channel_type: str = "MATCH_ROOM"):
        super().__init__(timeout=None)
        self.channel_id = str(channel_id)
        self.channel_type = channel_type

    @discord.ui.button(label="DELETE", style=discord.ButtonStyle.danger, emoji="🗑️", custom_id="cleanup:delete_btn")
    async def delete_channel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Only Administrators can perform channel cleanup.", ephemeral=True)
            return

        guild = interaction.guild
        target_ch = guild.get_channel(int(self.channel_id)) if guild and self.channel_id.isdigit() else None

        if target_ch:
            try:
                # Delete channel from Discord
                await target_ch.delete(reason=f"GEN Esports Channel Cleanup approved by {interaction.user.name}")
                await update_channel_cleanup_status(self.channel_id, "DELETED")
            except Exception as e:
                logger.error(f"Failed to delete channel {self.channel_id}: {e}")
                await interaction.followup.send(f"⚠️ Failed to delete channel: {str(e)}", ephemeral=True)
                return
        else:
            # Channel already deleted or missing
            await update_channel_cleanup_status(self.channel_id, "DELETED")

        for child in self.children:
            child.disabled = True

        try:
            embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else discord.Embed(title="Cleanup Complete")
            embed.color = discord.Color.red()
            embed.title = "🗑️ CHANNEL CLEANED UP"
            embed.set_footer(text=f"Deleted by {interaction.user.display_name}")
            await interaction.message.edit(embed=embed, view=self)
        except Exception:
            pass

        await interaction.followup.send(f"🗑️ Temporary channel `(ID: {self.channel_id})` has been deleted cleanly.", ephemeral=True)

    @discord.ui.button(label="KEEP", style=discord.ButtonStyle.secondary, emoji="⏳", custom_id="cleanup:keep_btn")
    async def keep_channel_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Only Administrators can perform channel cleanup.", ephemeral=True)
            return

        await update_channel_cleanup_status(self.channel_id, "KEPT")

        for child in self.children:
            child.disabled = True

        try:
            embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else discord.Embed(title="Channel Retained")
            embed.color = discord.Color.blue()
            embed.title = "⏳ CHANNEL RETAINED"
            embed.set_footer(text=f"Retained by {interaction.user.display_name}")
            await interaction.message.edit(embed=embed, view=self)
        except Exception:
            pass

        await interaction.followup.send(f"⏳ Channel `(ID: {self.channel_id})` retained.", ephemeral=True)


class CleanupCog(commands.Cog):
    """Cog for temporary Discord channel cleanup and retention lifecycle management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="cleanup-audit", description="[Admin] Audit temporary channels ready for cleanup and prompt Admin.")
    @app_commands.checks.has_permissions(administrator=True)
    async def cleanup_audit_cmd(self, interaction: discord.Interaction):
        """Admin command to list and prompt for temporary channel cleanup."""
        await interaction.response.defer(ephemeral=True)
        try:
            eligible_channels = await get_eligible_cleanup_channels()
            if not eligible_channels:
                await interaction.followup.send("🟢 No temporary channels are currently pending cleanup.", ephemeral=True)
                return

            guild = interaction.guild
            prompted_count = 0

            for record in eligible_channels:
                ch_id = record["channel_id"]
                ch_type = record.get("channel_type", "TEMPORARY")
                match_id = record.get("related_match_id")
                ticket_id = record.get("related_ticket_id")

                embed = discord.Embed(
                    title=f"🧹 {ch_type.replace('_', ' ')} CLEANUP",
                    description=(
                        f"This temporary channel is ready for cleanup.\n\n"
                        f"📌 **Channel ID:** `{ch_id}`\n"
                        f"🏷️ **Type:** `{ch_type}`\n"
                        f"⚔️ **Related Match:** `{f'#{match_id}' if match_id else 'N/A'}`\n"
                        f"🎫 **Related Ticket:** `{f'#{ticket_id}' if ticket_id else 'N/A'}`\n"
                        f"🕒 **Eligible At:** `{record.get('cleanup_eligible_at', 'Now')}`"
                    ),
                    color=discord.Color.orange()
                )
                embed.set_footer(text="GEN Esports Cleanup Lifecycle Engine")

                view = CleanupPromptView(ch_id, ch_type)
                await interaction.channel.send(embed=embed, view=view)
                prompted_count += 1

            await interaction.followup.send(f"✅ Generated {prompted_count} channel cleanup prompt(s) in this channel.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in cleanup-audit command: {e}")
            await interaction.followup.send(f"❌ Error performing cleanup audit: {str(e)}", ephemeral=True)


async def setup(bot: commands.Bot):
    """Register CleanupCog with the bot."""
    await bot.add_cog(CleanupCog(bot))
