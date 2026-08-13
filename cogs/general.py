import logging
import discord
from discord.ext import commands
from discord import app_commands
import config.settings as settings

logger = logging.getLogger("GENEsportsBot")

class CommunityWelcomeView(discord.ui.View):
    """Persistent View for Interactive Role Selection."""
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

            # Security check: Prevent self-assigning Staff or Admin roles
            forbidden_names = ["staff", "admin", "administrator", "organizer", "moderator"]
            if any(f in role.name.lower() for f in forbidden_names) and role_name.lower() not in ["organizer"]:
                if not interaction.user.guild_permissions.administrator:
                    await interaction.followup.send("❌ You are not authorized to assign this role.", ephemeral=True)
                    return

            member = interaction.user
            if isinstance(member, discord.Member):
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

    @discord.ui.button(label="ORGANIZER", style=discord.ButtonStyle.secondary, emoji="🏆", custom_id="gen_roles:organizer", row=1)
    async def organizer_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_role(interaction, "Organizer", settings.ORGANIZER_ROLE_ID)

    @discord.ui.button(label="SPECTATOR", style=discord.ButtonStyle.secondary, emoji="👀", custom_id="gen_roles:spectator", row=1)
    async def spectator_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_role(interaction, "Spectator", settings.SPECTATOR_ROLE_ID)

    @discord.ui.button(label="COMMUNITY MEMBER", style=discord.ButtonStyle.success, emoji="🤝", custom_id="gen_roles:community", row=2)
    async def community_role_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._assign_role(interaction, "Community Member", settings.COMMUNITY_ROLE_ID)

class GeneralCog(commands.Cog):
    """General utility commands for the GEN Esports Discord Bot."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Send welcome message and interactive role selection view when a new user joins."""
        try:
            guild = member.guild
            target_ch = None
            if settings.WELCOME_CHANNEL_ID and settings.WELCOME_CHANNEL_ID.isdigit():
                target_ch = guild.get_channel(int(settings.WELCOME_CHANNEL_ID))

            if not target_ch:
                target_ch = discord.utils.get(guild.text_channels, name="welcome") or discord.utils.get(guild.text_channels, name="welcome-and-rules") or guild.system_channel

            if target_ch and isinstance(target_ch, discord.TextChannel):
                embed = discord.Embed(
                    title=f"👋 Welcome to GEN Esports, {member.display_name}!",
                    description=(
                        f"Welcome {member.mention} to the official **GEN Esports** community!\n\n"
                        "🎮 **WHAT ARE YOU HERE FOR?**\n"
                        "Select your role below to unlock access to channels and tournament matches.\n\n"
                        "━━━━━━━━━━━━━━━━━━━━"
                    ),
                    color=discord.Color.from_rgb(0, 240, 255)
                )
                embed.set_thumbnail(url=member.display_avatar.url)
                embed.set_footer(text=f"GEN Esports • Join Server Link: {settings.DISCORD_INVITE_URL}")

                view = CommunityWelcomeView()
                await target_ch.send(content=f"Welcome {member.mention}!", embed=embed, view=view)
        except Exception as e:
            logger.error(f"Error in on_member_join welcome listener: {e}")

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
