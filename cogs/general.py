import logging
import discord
from discord.ext import commands
from discord import app_commands
import config.settings as settings
from database.db import (
    get_bot_setting, set_bot_setting,
    create_role_request, get_role_request, update_role_request_status
)

logger = logging.getLogger("GENEsportsBot")

class RoleSelectionSelect(discord.ui.Select):
    """Discord Native Select Menu for choosing self-assignable roles."""
    def __init__(self):
        options = [
            discord.SelectOption(label="Player", value="player", description="Compete in official matches & rosters", emoji="🎮"),
            discord.SelectOption(label="Team Captain", value="captain", description="Register & manage team rosters", emoji="👑"),
            discord.SelectOption(label="Spectator", value="spectator", description="Follow live matches & leaderboards", emoji="👀"),
            discord.SelectOption(label="Content Creator", value="creator", description="Streamers & community casters", emoji="🎬"),
        ]
        super().__init__(
            placeholder="Choose your GEN Esports role...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="gen_role_select_dropdown"
        )

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        guild = interaction.guild
        if not guild:
            await interaction.followup.send("❌ Error resolving server.", ephemeral=True)
            return

        selected_val = self.values[0]
        role_map = {
            "player": ("Player", settings.PLAYER_ROLE_ID),
            "captain": ("Team Captain", settings.TEAM_CAPTAIN_ROLE_ID),
            "spectator": ("Spectator", settings.SPECTATOR_ROLE_ID),
            "creator": ("Content Creator", getattr(settings, 'CREATOR_ROLE_ID', ''))
        }

        role_name, role_id_str = role_map.get(selected_val, ("Player", ""))
        
        # Store role request in database
        success, req_id, msg = await create_role_request(
            guild_id=str(guild.id),
            user_id=str(interaction.user.id),
            requested_role_id=role_id_str or role_name,
            requested_role_name=role_name
        )

        if not success:
            await interaction.followup.send(msg, ephemeral=True)
            return

        # Notify Admin Review Channel
        admin_ch = None
        review_ch_id = await get_bot_setting("role_review_channel_id")
        if review_ch_id and review_ch_id.isdigit():
            admin_ch = guild.get_channel(int(review_ch_id))

        if not admin_ch:
            admin_ch = (
                discord.utils.get(guild.text_channels, name="admin-review") or
                discord.utils.get(guild.text_channels, name="staff-logs") or
                discord.utils.get(guild.text_channels, name="admin")
            )

        if admin_ch:
            embed = discord.Embed(
                title="📥 NEW ROLE REQUEST",
                description=(
                    f"A new role request requires admin review.\n\n"
                    f"👤 **User:** {interaction.user.mention} `({interaction.user.name})`\n"
                    f"🆔 **User ID:** `{interaction.user.id}`\n"
                    f"🎭 **Requested Role:** {role_name}\n"
                    f"📌 **Request ID:** `#{req_id}`"
                ),
                color=discord.Color.gold()
            )
            embed.set_footer(text="GEN Esports Role Approval System")
            await admin_ch.send(embed=embed, view=AdminRoleReviewView(req_id, role_name, str(interaction.user.id)))

        await interaction.followup.send(
            f"⏳ Your role request for **{role_name}** `(Request #{req_id})` has been submitted for Admin approval.\n"
            f"You will receive a notification once an admin reviews your request.",
            ephemeral=True
        )

class RoleSelectionSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=180)
        self.add_item(RoleSelectionSelect())

class RoleSelectionPanel(discord.ui.View):
    """Persistent panel displayed in the dedicated role selection channel."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="TAKE YOUR ROLE", style=discord.ButtonStyle.primary, emoji="🎮", custom_id="gen_take_your_role_btn")
    async def take_your_role(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleSelectionSelectView()
        embed = discord.Embed(
            title="🎮 GEN ESPORTS • ROLE SELECTION",
            description="Select the role that best describes your participation in GEN Esports from the menu below.",
            color=discord.Color.from_rgb(0, 240, 255)
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class AdminRoleReviewView(discord.ui.View):
    """Persistent Admin review panel with Approve/Reject buttons."""
    def __init__(self, request_id: int = 0, role_name: str = "", target_user_id: str = ""):
        super().__init__(timeout=None)
        self.request_id = request_id
        self.role_name = role_name
        self.target_user_id = target_user_id

    @discord.ui.button(label="APPROVE", style=discord.ButtonStyle.success, emoji="✅", custom_id="role_req:approve_btn")
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Only Administrators can review role requests.", ephemeral=True)
            return

        guild = interaction.guild
        req = await get_role_request(self.request_id) if self.request_id else None
        
        target_uid = self.target_user_id or (str(req["user_id"]) if req else "")
        r_name = self.role_name or (req["requested_role_name"] if req else "Player")
        r_id = req["requested_role_id"] if req else ""

        if self.request_id:
            await update_role_request_status(self.request_id, "APPROVED", str(interaction.user.id))

        member = guild.get_member(int(target_uid)) if guild and target_uid.isdigit() else None
        if member:
            role = None
            if r_id and r_id.isdigit():
                role = guild.get_role(int(r_id))
            if not role:
                role = discord.utils.get(guild.roles, name=r_name)
            if not role:
                try:
                    role = await guild.create_role(name=r_name, reason="GEN Esports Role Request Approved")
                except Exception:
                    pass
            if role:
                try:
                    await member.add_roles(role)
                except Exception as e:
                    logger.error(f"Error granting role {r_name} to {member.id}: {e}")

            try:
                dm_embed = discord.Embed(
                    title="✅ ROLE APPROVED",
                    description=f"Your GEN Esports role request has been approved.\n\n**Role:** {r_name}",
                    color=discord.Color.green()
                )
                dm_embed.set_footer(text="GEN Esports Community Platform")
                await member.send(embed=dm_embed)
            except Exception:
                pass

        for child in self.children:
            child.disabled = True

        try:
            embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else discord.Embed(title="Role Request Approved")
            embed.color = discord.Color.green()
            embed.title = "✅ ROLE REQUEST APPROVED"
            embed.set_footer(text=f"Approved by {interaction.user.display_name}")
            await interaction.message.edit(embed=embed, view=self)
        except Exception as e:
            logger.warning(f"Could not edit approval message: {e}")

        await interaction.followup.send(f"✅ Role request for user <@{target_uid}> approved.", ephemeral=True)

    @discord.ui.button(label="REJECT", style=discord.ButtonStyle.danger, emoji="❌", custom_id="role_req:reject_btn")
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        if not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("❌ Only Administrators can review role requests.", ephemeral=True)
            return

        guild = interaction.guild
        req = await get_role_request(self.request_id) if self.request_id else None

        target_uid = self.target_user_id or (str(req["user_id"]) if req else "")
        r_name = self.role_name or (req["requested_role_name"] if req else "Player")

        if self.request_id:
            await update_role_request_status(self.request_id, "REJECTED", str(interaction.user.id))

        member = guild.get_member(int(target_uid)) if guild and target_uid.isdigit() else None
        if member:
            try:
                dm_embed = discord.Embed(
                    title="❌ ROLE REQUEST REJECTED",
                    description=f"Your request for:\n**{r_name}**\n\nwas not approved by administration.",
                    color=discord.Color.red()
                )
                dm_embed.set_footer(text="GEN Esports Community Platform")
                await member.send(embed=dm_embed)
            except Exception:
                pass

        for child in self.children:
            child.disabled = True

        try:
            embed = interaction.message.embeds[0] if interaction.message and interaction.message.embeds else discord.Embed(title="Role Request Rejected")
            embed.color = discord.Color.red()
            embed.title = "❌ ROLE REQUEST REJECTED"
            embed.set_footer(text=f"Rejected by {interaction.user.display_name}")
            await interaction.message.edit(embed=embed, view=self)
        except Exception as e:
            logger.warning(f"Could not edit rejection message: {e}")

        await interaction.followup.send(f"❌ Role request for user <@{target_uid}> rejected.", ephemeral=True)

class CommunityWelcomeView(discord.ui.View):
    """Persistent View for Interactive Welcome Channel."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="TAKE YOUR ROLE", style=discord.ButtonStyle.primary, emoji="🎮", custom_id="gen_welcome_take_role_btn")
    async def take_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = RoleSelectionSelectView()
        embed = discord.Embed(
            title="🎮 GEN ESPORTS • ROLE SELECTION",
            description="Select the role that best describes your participation in GEN Esports from the menu below.",
            color=discord.Color.from_rgb(0, 240, 255)
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class GeneralCog(commands.Cog):
    """General utility commands, Welcome integration & Role Request system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send professional welcome embed to the configured Welcome channel when a new member joins."""
        try:
            guild = member.guild

            enabled_setting = await get_bot_setting("welcome_enabled")
            if enabled_setting and enabled_setting.lower() == "false":
                logger.info(f"Welcome listener skipped for {member.display_name}: welcome system disabled.")
                return

            target_ch = None
            db_channel_id = await get_bot_setting("welcome_channel_id")
            if db_channel_id and db_channel_id.isdigit():
                target_ch = guild.get_channel(int(db_channel_id))

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
                    title="🏆 GEN ESPORTS",
                    description=(
                        f"👋 **Welcome, {member.mention}!**\n\n"
                        "Welcome to the **GEN Esports** community.\n\n"
                        "Use the button below to get started and request your role."
                    ),
                    color=discord.Color.from_rgb(0, 240, 255)
                )
                embed.set_thumbnail(url=member.display_avatar.url if member.display_avatar else None)
                embed.set_footer(text=f"GEN Esports • Server Invite: {settings.DISCORD_INVITE_URL}")

                view = CommunityWelcomeView()
                await target_ch.send(content=f"Welcome {member.mention}!", embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error in on_member_join welcome listener: {e}", exc_info=True)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Send leave notification embed to configured Welcome/Log channel when a member leaves."""
        try:
            guild = member.guild

            target_ch = None
            db_channel_id = await get_bot_setting("welcome_channel_id")
            if db_channel_id and db_channel_id.isdigit():
                target_ch = guild.get_channel(int(db_channel_id))

            if not target_ch and settings.WELCOME_CHANNEL_ID and settings.WELCOME_CHANNEL_ID.isdigit():
                target_ch = guild.get_channel(int(settings.WELCOME_CHANNEL_ID))

            if not target_ch:
                target_ch = (
                    discord.utils.get(guild.text_channels, name="welcome") or 
                    discord.utils.get(guild.text_channels, name="welcome-and-rules") or 
                    guild.system_channel
                )

            if target_ch and isinstance(target_ch, (discord.TextChannel, discord.NewsChannel)):
                member_count = len(guild.members)
                embed = discord.Embed(
                    title="👋 MEMBER LEFT",
                    description=(
                        f"**{member.name}** (`@{member.name}`) has left GEN Esports.\n\n"
                        f"👥 **Member count:** `{member_count}`"
                    ),
                    color=discord.Color.dark_grey()
                )
                if member.display_avatar:
                    embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text="GEN Esports Community Log")
                await target_ch.send(embed=embed)
        except Exception as e:
            logger.error(f"Error in on_member_remove leave listener: {e}", exc_info=True)

    @app_commands.command(name="setup-role-panel", description="[Admin] Deploy persistent Role Selection panel to dedicated role selection channel.")
    @app_commands.describe(channel="Select dedicated role selection channel")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_role_panel_cmd(self, interaction: discord.Interaction, channel: discord.TextChannel):
        """Admin command to deploy persistent role selection panel."""
        await interaction.response.defer(ephemeral=True)
        try:
            embed = discord.Embed(
                title="🎮 GEN ESPORTS",
                description=(
                    "**CHOOSE YOUR ROLE**\n\n"
                    "Select the role that best describes you in the GEN Esports community."
                ),
                color=discord.Color.from_rgb(0, 240, 255)
            )
            embed.set_footer(text="GEN Esports Role System")
            view = RoleSelectionPanel()
            await channel.send(embed=embed, view=view)
            await interaction.followup.send(f"✅ Persistent Role Selection panel deployed to {channel.mention}.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error executing setup-role-panel command: {e}")
            await interaction.followup.send(f"❌ Error deploying panel: {str(e)}", ephemeral=True)

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

            await set_bot_setting("welcome_channel_id", str(channel.id))
            await set_bot_setting("welcome_enabled", "true" if enabled else "false")
            settings.WELCOME_CHANNEL_ID = str(channel.id)

            embed = discord.Embed(
                title="✅ Welcome Channel Connected Successfully",
                description=(
                    f"The GEN Esports welcome system has been connected to your existing channel.\n\n"
                    f"📌 **Configured Welcome Channel:** {channel.mention} `(ID: {channel.id})`\n"
                    f"⚙️ **Status:** `{'🟢 ENABLED' if enabled else '🔴 DISABLED'}`\n\n"
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

