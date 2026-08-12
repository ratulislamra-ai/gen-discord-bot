import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from database.db import (
    get_or_create_player,
    get_player_full_profile,
    get_or_create_team,
    get_team_full_profile,
    get_user_all_registrations,
    log_admin_action
)
import config.settings as settings

logger = logging.getLogger("GENEsportsBot")

class IdentityCog(commands.Cog):
    """Cog for GEN Esports Player & Team Identity Management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="profile", description="View a player's GEN Esports public profile and statistics.")
    async def view_player_profile(self, interaction: discord.Interaction, user: Optional[discord.User] = None):
        """Slash command to view a player's profile embed."""
        target_user = user or interaction.user
        
        # Ensure player record exists
        player_data = await get_or_create_player(
            discord_user_id=str(target_user.id),
            username=target_user.name,
            display_name=target_user.display_name,
            avatar_url=str(target_user.display_avatar.url) if target_user.display_avatar else ""
        )

        full_profile = await get_player_full_profile(str(target_user.id))
        if not full_profile:
            await interaction.response.send_message("❌ Player profile not found.", ephemeral=True)
            return

        is_verified = full_profile.get("verification_status") == "VERIFIED"
        verified_badge = " ✅ VERIFIED" if is_verified else ""

        embed = discord.Embed(
            title=f"👤 {full_profile.get('display_name')}{verified_badge}",
            description=f"**Public ID:** `{full_profile.get('public_id')}`\n**Primary Game:** `{full_profile.get('primary_game')}`",
            color=discord.Color.gold() if is_verified else discord.Color.blue()
        )

        if full_profile.get("avatar_url"):
            embed.set_thumbnail(url=full_profile["avatar_url"])

        # Stats
        stats = full_profile.get("stats", {})
        embed.add_field(name="⚔️ Matches Played", value=f"`{stats.get('matches_played', 0)}`", inline=True)
        embed.add_field(name="🏆 Wins / Losses", value=f"`{stats.get('wins', 0)} W / {stats.get('losses', 0)} L`", inline=True)
        embed.add_field(name="📈 Win Rate", value=f"`{stats.get('win_rate', 0.0)}%`", inline=True)

        # Teams
        teams = full_profile.get("teams", [])
        if teams:
            team_names = ", ".join([f"**{t['team_name']}** ({t['role']})" for t in teams])
            embed.add_field(name="🛡️ Active Teams", value=team_names, inline=False)
        else:
            embed.add_field(name="🛡️ Active Teams", value="*No active team memberships*", inline=False)

        # Achievements
        achievements = full_profile.get("achievements", [])
        if achievements:
            ach_text = "\n".join([f"{a['badge_icon']} **{a['title']}** - {a.get('description', '')}" for a in achievements])
            embed.add_field(name="🏅 Achievements", value=ach_text, inline=False)

        embed.set_footer(text="GEN Esports Player Identity System")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="my-team", description="View your current esports team profile and active roster.")
    async def my_team(self, interaction: discord.Interaction):
        """Display user's active team profile."""
        full_profile = await get_player_full_profile(str(interaction.user.id))
        if not full_profile or not full_profile.get("teams"):
            await interaction.response.send_message("🛡️ You are not currently a member of any active team.", ephemeral=True)
            return

        team_info = full_profile["teams"][0]
        team_profile = await get_team_full_profile(team_info["team_slug"])
        if not team_profile:
            await interaction.response.send_message("❌ Team details not found.", ephemeral=True)
            return

        is_verified = team_profile.get("verification_status") == "VERIFIED"
        verified_badge = " ✅ VERIFIED" if is_verified else ""

        embed = discord.Embed(
            title=f"🛡️ {team_profile.get('name')}{verified_badge}",
            description=f"**Team ID:** `{team_profile.get('public_id')}`\n**Game:** `{team_profile.get('game')}` | **Region:** `{team_profile.get('region')}`",
            color=discord.Color.green()
        )

        if team_profile.get("logo_url"):
            embed.set_thumbnail(url=team_profile["logo_url"])

        # Active Roster
        roster = team_profile.get("roster", [])
        if roster:
            roster_text = "\n".join([f"• **{p['display_name']}** (`{p['public_id']}`) - *{p['role']}*" for p in roster])
            embed.add_field(name="👥 Active Roster", value=roster_text, inline=False)

        # Tournament History
        history = team_profile.get("tournament_history", [])
        if history:
            hist_text = "\n".join([f"🏆 {h['tournament_name']} ({h['status']})" for h in history])
            embed.add_field(name="📜 Tournament History", value=hist_text, inline=False)

        embed.set_footer(text="GEN Esports Team Identity Engine")
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="invite-player", description="Invite a player to join your competitive team (Captain Only).")
    async def invite_player(self, interaction: discord.Interaction, player: discord.User):
        """Captain command to invite another player."""
        await interaction.response.defer(ephemeral=True)

        full_profile = await get_player_full_profile(str(interaction.user.id))
        if not full_profile or not full_profile.get("teams"):
            await interaction.followup.send("❌ You must be a team captain to invite players.", ephemeral=True)
            return

        # Verify captain role
        team_info = full_profile["teams"][0]
        if team_info.get("role") != "CAPTAIN":
            await interaction.followup.send("❌ Only the Team Captain can invite new members.", ephemeral=True)
            return

        # Ensure target player exists
        target_player = await get_or_create_player(
            discord_user_id=str(player.id),
            username=player.name,
            display_name=player.display_name
        )

        # Send DM invitation to player
        try:
            embed = discord.Embed(
                title="📩 GEN ESPORTS TEAM INVITATION",
                description=f"You have been invited by **{interaction.user.display_name}** to join team **{team_info['team_name']}**!",
                color=discord.Color.gold()
            )
            embed.add_field(name="Team Name", value=team_info['team_name'], inline=True)
            embed.add_field(name="Invited By", value=interaction.user.display_name, inline=True)
            embed.set_footer(text="Use the button below or visit your website dashboard to accept or reject.")

            class InvitationResponseView(discord.ui.View):
                def __init__(self, team_name: str, invitee_id: str):
                    super().__init__(timeout=86400)
                    self.team_name = team_name
                    self.invitee_id = invitee_id

                @discord.ui.button(label="Accept Invitation", style=discord.ButtonStyle.success, emoji="✅")
                async def accept(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                    await btn_interaction.response.send_message(f"✅ You have joined **{self.team_name}**!", ephemeral=True)

                @discord.ui.button(label="Decline", style=discord.ButtonStyle.danger, emoji="❌")
                async def decline(self, btn_interaction: discord.Interaction, button: discord.ui.Button):
                    await btn_interaction.response.send_message(f"❌ You declined the invitation to join **{self.team_name}**.", ephemeral=True)

            await player.send(embed=embed, view=InvitationResponseView(team_info['team_name'], str(player.id)))
            await interaction.followup.send(f"✅ Formal team invitation sent to {player.mention}.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error sending DM invitation: {e}")
            await interaction.followup.send(f"⚠️ Invitation created, but could not DM user {player.mention}. Please ask them to check their Website Dashboard.", ephemeral=True)

async def setup(bot: commands.Bot):
    """Asynchronously register IdentityCog with the bot."""
    await bot.add_cog(IdentityCog(bot))
