import logging
import discord
from discord.ext import commands
from discord import app_commands
import config.settings as settings
from database.db import get_bot_setting, set_bot_setting
from typing import Union

logger = logging.getLogger("GENEsportsBot")

class CommunityWelcomeView(discord.ui.View):
    """Persistent View for Interactive Self-Assignable Role Selection."""
    def __init__(self):
        super().__init__(timeout=None)

    async def _assign_role(self, interaction: discord.Interaction, role_name: str, role_id_str: str):
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            if not guild:
                await interaction.followup.send("❌ Error resolving server.", ephemeral=True)
                return

            role = None
            if role_id_str and role_id_str.isdigit():
                role = guild.get_role(int(role_id_str))

            if not role:
                role = discord.utils.get(guild.roles, name=role_name)

            if not role:
                # Create role if missing
                try:
                    role = await guild.create_role(name=role_name, reason="GEN Esports Self-Assign Role Auto-Create")
                except Exception:
                    await interaction.followup.send(f"⚠️ Role **{role_name}** is not configured yet on this server.", ephemeral=True)
                    return

            # Security check: Prevent self-assigning Staff, Admin, or Moderator roles
            forbidden_names = ["staff", "admin", "administrator", "organizer", "moderator", "manager", "referee"]
            if any(f in role.name.lower() for f in forbidden_names):
                if not interaction.user.guild_permissions.administrator:
                    await interaction.followup.send("❌ Self-assignment of administrative or staff roles is strictly forbidden.", ephemeral=True)
                    return

            member = interaction.user
            if isinstance(member, discord.Member):
                if role in member.roles:
                    await member.remove_roles(role)
                    await interaction.followup.send(f"➖ Role **{role.name}** removed successfully.", ephemeral=True)
                else:
                    await member.add_roles(role)
                    await interaction.followup.send(f"✅ Role **{role.name}** assigned successfully! Welcome to GEN Esports!", ephemeral=True)
            else:
                await interaction.followup.send("❌ Member profile not resolved.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error assigning role {role_name}: {e}")
            await interaction.followup.send("❌ Failed to assign role.", ephemeral=True)

    @discord.ui.button(label="PLAYER", style=discord.ButtonStyle.primary, emoji="🎮", custom_id="gen_roles:player", row=0)
    async def player_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_role(interaction, "Player", settings.PLAYER_ROLE_ID)

    @discord.ui.button(label="TEAM CAPTAIN", style=discord.ButtonStyle.secondary, emoji="👑", custom_id="gen_roles:captain", row=0)
    async def captain_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_role(interaction, "Team Captain", settings.TEAM_CAPTAIN_ROLE_ID)

    @discord.ui.button(label="SPECTATOR", style=discord.ButtonStyle.secondary, emoji="👀", custom_id="gen_roles:spectator", row=1)
    async def spectator_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_role(interaction, "Spectator", settings.SPECTATOR_ROLE_ID)

    @discord.ui.button(label="CONTENT CREATOR", style=discord.ButtonStyle.secondary, emoji="🎬", custom_id="gen_roles:creator", row=1)
    async def creator_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_role(interaction, "Content Creator", getattr(settings, 'CREATOR_ROLE_ID', ''))

    @discord.ui.button(label="COMMUNITY MEMBER", style=discord.ButtonStyle.success, emoji="🤝", custom_id="gen_roles:community", row=2)
    async def community_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_role(interaction, "Community Member", settings.COMMUNITY_ROLE_ID)

class GeneralCog(commands.Cog):
    """General utility commands & Welcome integration for the GEN Esports Discord Bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send welcome message and interactive role selection view to configured Welcome channel when a new member joins."""
        try:
            guild = member.guild

            # 1. Check if welcome system is enabled in database
            enabled_setting = await get_bot_setting("welcome_enabled")
            if enabled_setting and enabled_setting.lower() == "false":
                logger.info(f"Welcome listener skipped for {member.display_name}: welcome system disabled.")
                return

            # 2. Check for configured Welcome channel ID in database
            target_ch = None
            db_channel_id = await get_bot_setting("welcome_channel_id")
            if db_channel_id and db_channel_id.isdigit():
                target_ch = guild.get_channel(int(db_channel_id))

            # 3. Fallback to settings.WELCOME_CHANNEL_ID or existing #welcome text channel
            if not target_ch and settings.WELCOME_CHANNEL_ID and settings.WELCOME_CHANNEL_ID.isdigit():
                target_ch = guild.get_channel(int(settings.WELCOME_CHANNEL_ID))

            if not target_ch:
                target_ch = (
                    discord.utils.get(guild.text_channels, name="welcome") or 
                    discord.utils.get(guild.text_channels, name="welcome-and-rules") or 
                    guild.system_channel
                )

            if target_ch and isinstance(target_ch, (discord.TextChannel, discord.NewsChannel)):
                embed = discord.Embed(
                    title=f"👋 Welcome to GEN Esports, {member.display_name}!",
                    description=(
                        f"Welcome {member.mention} to the official **GEN Esports** community!\n\n"
                        "🎮 **GET STARTED & SELECT YOUR ROLES**\n"
                        "Select your role below to unlock channel access and join tournament matches.\n\n"
                        "• **Player**: Compete in official matches & rosters\n"
                        "• **Team Captain**: Register and manage team rosters\n"
                        "• **Spectator**: Follow live matches & leaderboards\n"
                        "• **Content Creator**: Streamers & community casters\n\n"
                        "━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=discord.Color.from_rgb(0, 240, 255)
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"GEN Esports • Join Link: {settings.DISCORD_INVITE_URL}")

                view = CommunityWelcomeView()
                await target_ch.send(content=f"Welcome {member.mention}!", embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error in on_member_join welcome listener: {e}")

    @app_commands.command(name="setup-welcome", description="[Admin] Connect existing Discord Welcome channel for new member welcome system.")
    @app_commands.describe(
        channel="Select your EXISTING Discord Welcome channel",
        enabled="Enable or disable welcome system notifications"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_welcome_cmd(
        self,
        interaction: discord.Interaction,
        channel: discord.TextChannel,
        enabled: bool = True
    ):
        """Admin command to configure existing Welcome channel and persist ID to SQLite database."""
        await interaction.response.defer(ephemeral=True)
        try:
            if channel.type not in (discord.ChannelType.text, discord.ChannelType.news):
                await interaction.followup.send("❌ Invalid channel type. Please select a text or announcement channel.", ephemeral=True)
                return
            # Save channel ID and enabled state to SQLite bot_settings table
            await set_bot_setting("welcome_channel_id", str(channel.id))
            await set_bot_setting("welcome_enabled", "true" if enabled else "false")

            # Update runtime setting
            settings.WELCOME_CHANNEL_ID = str(channel.id)

            embed = discord.Embed(
                title="✅ Welcome Channel Connected Successfully",
                description=(
                    f"The GEN Esports welcome system has been connected to your existing channel.\n\n"
                    f"📌 **Configured Welcome Channel:** {channel.mention} `(ID: {channel.id})`\n"
                    f"⚙️ **Status:** `{'🟢 ENABLED' if enabled else '🔴 DISABLED'}`\n"
                    f"🛡️ **Channel Creation:** Reused existing channel (0 channels created)\n\n"
                    "**Self-Assignable Roles Enabled:**\n"
                    "• 🎮 **Player**\n"
                    "• 👑 **Team Captain**\n"
                    "• 👀 **Spectator**\n"
                    "• 🎬 **Content Creator**"
                ),
                color=discord.Color.from_rgb(0, 240, 255)
            )
            embed.set_footer(text="GEN Esports Tournament Management System")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error executing setup-welcome command: {e}")
            await interaction.followup.send(f"❌ Error configuring welcome channel: {str(e)}", ephemeral=True)

    @app_commands.command(name="welcome-config", description="[Admin] Inspect current Welcome channel configuration and status.")
    @app_commands.checks.has_permissions(administrator=True)
    async def welcome_config_cmd(self, interaction: discord.Interaction):
        """Admin command to inspect configured Welcome channel and role security policy."""
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            db_channel_id = await get_bot_setting("welcome_channel_id")
            db_enabled = await get_bot_setting("welcome_enabled")

            is_enabled = db_enabled.lower() != "false" if db_enabled else True

            ch_str = "Not Configured"
            if db_channel_id and db_channel_id.isdigit():
                ch = guild.get_channel(int(db_channel_id)) if guild else None
                if ch:
                    ch_str = f"{ch.mention} `(ID: {ch.id})`"
                else:
                    ch_str = f"⚠️ Channel ID `{db_channel_id}` (Not found on server)"
            elif settings.WELCOME_CHANNEL_ID and settings.WELCOME_CHANNEL_ID.isdigit():
                ch = guild.get_channel(int(settings.WELCOME_CHANNEL_ID)) if guild else None
                if ch:
                    ch_str = f"{ch.mention} `(ID: {ch.id})`"

            embed = discord.Embed(
                title="⚙️ GEN Esports Welcome System Configuration",
                description=(
                    f"**Configured Welcome Channel:**\n{ch_str}\n\n"
                    f"**Integration Status:** `{'🟢 ENABLED' if is_enabled else '🔴 DISABLED'}`\n\n"
                    "**Self-Assignable Roles:**\n"
                    "• 🎮 **Player**\n"
                    "• 👑 **Team Captain**\n"
                    "• 👀 **Spectator**\n"
                    "• 🎬 **Content Creator**\n\n"
                    "🛡️ **Security Policy:** Administrative, Staff, Organizer, and Moderator roles cannot be self-assigned."
                ),
                color=discord.Color.from_rgb(0, 240, 255)
            )
            embed.set_footer(text="GEN Esports Admin Dashboard")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error fetching welcome config: {e}")
            await interaction.followup.send(f"❌ Error displaying welcome config: {str(e)}", ephemeral=True)

    @app_commands.command(name="ping", description="Check the bot's latency and connection health.")
    async def ping(self, interaction: discord.Interaction):
        """Slash command to verify the bot is online and measure round-trip latency."""
        latency_ms = round(self.bot.latency * 1000)

        embed = discord.Embed(
            title="🏓 Pong!",
            description=f"GEN Esports Bot is active and responding.\n\n**Latency:** `{latency_ms} ms`",
            color=discord.Color.blue()
        )
        embed.set_footer(text="GEN Esports Tournament Management System")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="broadcast-announcement", description="[Admin/Staff] Broadcast official announcement embed to community channels.")
    @app_commands.describe(
        title="Announcement Title",
        message="Announcement Content",
        target_channel="Optional target channel (defaults to configured announcement channel)",
        role_mention="Optional role to mention (e.g. @everyone or @Player)",
        image_url="Optional image URL attachment"
    )
    @app_commands.checks.has_permissions(administrator=True)
    async def broadcast_announcement_cmd(
        self,
        interaction: discord.Interaction,
        title: str,
        message: str,
        target_channel: discord.TextChannel | None = None,
        role_mention: str | None = None,
        image_url: str | None = None
    ):
        """Staff command to broadcast official tournament announcements."""
        await interaction.response.defer(ephemeral=True)
        try:
            guild = interaction.guild
            ch = target_channel
            if not ch and settings.ANNOUNCEMENT_CHANNEL_ID and settings.ANNOUNCEMENT_CHANNEL_ID.isdigit():
                ch = guild.get_channel(int(settings.ANNOUNCEMENT_CHANNEL_ID))

            if not ch:
                ch = interaction.channel

            embed = discord.Embed(
                title=f"📢 {title}",
                description=message,
                color=discord.Color.from_rgb(0, 240, 255)
            )
            embed.set_footer(text="GEN Esports Official Broadcast")
            if image_url:
                embed.set_image(url=image_url)

            content_text = role_mention if role_mention else ""
            await ch.send(content=content_text, embed=embed)
            await interaction.followup.send(f"✅ Announcement broadcasted to {ch.mention} successfully!", ephemeral=True)
        except Exception as e:
            logger.error(f"Error broadcasting announcement: {e}")
            await interaction.followup.send(f"❌ Broadcast error: {str(e)}", ephemeral=True)

async def setup(bot: commands.Bot):
    """Asynchronous setup function to register GeneralCog with the bot."""
    await bot.add_cog(GeneralCog(bot))
