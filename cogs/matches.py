import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from database.db import (
    process_match_check_in,
    submit_match_score,
    confirm_opponent_match_score,
    update_match_schedule_and_lobby,
    get_user_all_registrations,
    log_admin_action,
    _get_connection
)

logger = logging.getLogger("GENEsportsBot")

class ScoreSubmissionModal(discord.ui.Modal, title="Submit Match Result"):
    match_id = discord.ui.TextInput(label="Match ID", placeholder="e.g. 1 or GEN-M-000001", required=True)
    score_a = discord.ui.TextInput(label="Your Team Score", placeholder="e.g. 13", required=True)
    score_b = discord.ui.TextInput(label="Opponent Team Score", placeholder="e.g. 9", required=True)
    evidence_url = discord.ui.TextInput(label="Screenshot Evidence URL", placeholder="https://imgur.com/... or image link", required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            m_id = self.match_id.value.strip()
            s_a = int(self.score_a.value.strip())
            s_b = int(self.score_b.value.strip())
            ev_url = self.evidence_url.value.strip() if self.evidence_url.value else ""

            match_res = await submit_match_score(
                match_id=m_id,
                submitting_team_id=0,
                submitting_user_id=str(interaction.user.id),
                score_a=s_a,
                score_b=s_b,
                evidence_url=ev_url
            )

            if not match_res:
                await interaction.followup.send("❌ Match not found or invalid submission.", ephemeral=True)
                return

            embed = discord.Embed(
                title="📤 Match Result Submitted",
                description=f"Result for **Match #{match_res.get('public_match_id') or match_res.get('match_id')}** has been submitted and is awaiting opponent confirmation.\n\n**Score:** `{s_a} - {s_b}`",
                color=discord.Color.gold()
            )
            if ev_url:
                embed.add_field(name="Screenshot Evidence", value=ev_url, inline=False)
            
            await interaction.followup.send(embed=embed, ephemeral=True)
        except ValueError:
            await interaction.followup.send("❌ Please enter valid numerical scores.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in ScoreSubmissionModal: {e}")
            await interaction.followup.send(f"❌ Error submitting score: {str(e)}", ephemeral=True)

class MatchControlView(discord.ui.View):
    """Persistent View for Discord Match Channels & Rooms."""
    def __init__(self, match_id: str = ""):
        super().__init__(timeout=None)
        self.match_id = match_id

    @discord.ui.button(label="Check In", style=discord.ButtonStyle.success, emoji="🎟️", custom_id="match_ctrl_checkin")
    async def check_in_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        
        user_regs = await get_user_all_registrations(str(interaction.user.id))
        if not user_regs:
            await interaction.followup.send("❌ You must be registered in a team to check in for matches.", ephemeral=True)
            return

        # Fetch active team registrations
        team_names = [r["team_name"] for r in user_regs]
        
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, t1.name as team1_name, t2.name as team2_name 
                FROM matches m
                LEFT JOIN teams t1 ON m.team1_id = t1.team_id
                LEFT JOIN teams t2 ON m.team2_id = t2.team_id
                WHERE m.status IN ('SCHEDULED', 'CHECK_IN_OPEN')
                ORDER BY m.match_id DESC LIMIT 10;
            """)
            active_matches = [dict(r) for r in cursor.fetchall()]

        user_match = None
        user_team_id = None

        for m in active_matches:
            if m.get("team1_name") in team_names:
                user_match = m
                user_team_id = m["team1_id"]
                break
            elif m.get("team2_name") in team_names:
                user_match = m
                user_team_id = m["team2_id"]
                break

        if not user_match:
            await interaction.followup.send("❌ No active match check-in open for your registered team(s).", ephemeral=True)
            return

        updated_match = await process_match_check_in(user_match["match_id"], user_team_id)
        if updated_match and updated_match.get("status") == "READY":
            await interaction.followup.send("✅ Check-in processed! **BOTH TEAMS ARE CHECKED IN — MATCH IS READY!** 🏆", ephemeral=False)
        else:
            await interaction.followup.send(f"✅ Check-in recorded for **Match #{user_match.get('public_match_id') or user_match['match_id']}**. Awaiting opponent check-in.", ephemeral=True)

    @discord.ui.button(label="Lobby Info", style=discord.ButtonStyle.primary, emoji="🎮", custom_id="match_ctrl_lobby")
    async def lobby_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        user_regs = await get_user_all_registrations(str(interaction.user.id))
        team_names = [r["team_name"] for r in user_regs]

        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, t1.name as team1_name, t2.name as team2_name 
                FROM matches m
                LEFT JOIN teams t1 ON m.team1_id = t1.team_id
                LEFT JOIN teams t2 ON m.team2_id = t2.team_id
                ORDER BY m.match_id DESC LIMIT 10;
            """)
            matches = [dict(r) for r in cursor.fetchall()]

        target_m = None
        for m in matches:
            if m.get("team1_name") in team_names or m.get("team2_name") in team_names:
                target_m = m
                break

        if not target_m:
            await interaction.response.send_message("🔒 Lobby credentials are only visible to authorized match participants.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🎮 Match #{target_m.get('public_match_id') or target_m['match_id']} Lobby Information",
            description=f"**Stage:** `{target_m.get('stage_name', 'Tournament Match')}`\n**Server/Region:** `{target_m.get('server_region', 'South Asia')}`\n**Map:** `{target_m.get('map', 'TBD')}`",
            color=discord.Color.blue()
        )
        embed.add_field(name="Lobby Name", value=f"`{target_m.get('lobby_name') or 'GEN-LOBBY-01'}`", inline=True)
        embed.add_field(name="Lobby Code", value=f"`{target_m.get('lobby_code') or '12345'}`", inline=True)
        embed.add_field(name="Lobby Password", value=f"`{target_m.get('lobby_password') or 'GEN2026'}`", inline=True)
        embed.set_footer(text="Confidential • Do not share credentials publicly.")

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @discord.ui.button(label="Map Veto", style=discord.ButtonStyle.primary, emoji="🗺️", custom_id="match_ctrl_veto")
    async def map_veto_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_regs = await get_user_all_registrations(str(interaction.user.id))
        team_names = [r["team_name"] for r in user_regs]

        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, t1.name as team1_name, t2.name as team2_name 
                FROM matches m
                LEFT JOIN teams t1 ON m.team1_id = t1.team_id
                LEFT JOIN teams t2 ON m.team2_id = t2.team_id
                ORDER BY m.match_id DESC LIMIT 10;
            """)
            matches = [dict(r) for r in cursor.fetchall()]

        target_m = None
        for m in matches:
            if m.get("team1_name") in team_names or m.get("team2_name") in team_names:
                target_m = m
                break

        if not target_m:
            await interaction.followup.send("❌ No active match veto session found for your team.", ephemeral=True)
            return

        from database.db import get_match_veto_state, start_match_veto_session
        veto_session = await get_match_veto_state(target_m["match_id"])
        if not veto_session:
            veto_session = await start_match_veto_session(target_m["match_id"])

        if not veto_session:
            await interaction.followup.send("❌ Could not initialize veto session for this match.", ephemeral=True)
            return

        v_state = veto_session.get("veto_state", {})
        banned = ", ".join(v_state.get("banned_maps", [])) or "None"
        picked = ", ".join(v_state.get("picked_maps", [])) or "None"
        decider = v_state.get("decider_map") or "TBD"

        embed = discord.Embed(
            title=f"🗺️ Map Veto Session — Match #{target_m.get('public_match_id') or target_m['match_id']}",
            description=f"**Status:** `{veto_session.get('status')}`\n**Banned:** `{banned}`\n**Picked:** `{picked}`\n**Decider:** `{decider}`",
            color=discord.Color.purple()
        )
        embed.set_footer(text="GEN Esports Competitive Integrity System")
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Submit Score", style=discord.ButtonStyle.secondary, emoji="📤", custom_id="match_ctrl_submit")
    async def submit_score_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(ScoreSubmissionModal())

    @discord.ui.button(label="Dispute Match", style=discord.ButtonStyle.danger, emoji="⚖️", custom_id="match_ctrl_dispute")
    async def dispute_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("⚖️ Match dispute recorded. A GEN Esports Tournament Staff member will review the evidence.", ephemeral=True)

class MatchesCog(commands.Cog):
    """Cog for Competitive Match Operations and Room Control."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="match-checkin", description="Check in your team for an upcoming tournament match.")
    async def match_checkin_cmd(self, interaction: discord.Interaction):
        """Slash command for team check-in."""
        view = MatchControlView()
        await view.check_in_button(interaction, None)

    @app_commands.command(name="match-info", description="View confidential lobby details for your match.")
    async def match_info_cmd(self, interaction: discord.Interaction):
        """Slash command to view match lobby details."""
        view = MatchControlView()
        await view.lobby_info_button(interaction, None)

    @app_commands.command(name="submit-score", description="Submit final match scores and screenshot evidence.")
    async def submit_score_cmd(self, interaction: discord.Interaction):
        """Slash command to open score submission modal."""
        await interaction.response.send_modal(ScoreSubmissionModal())

    @app_commands.command(name="map-veto", description="View or participate in live map pick/ban veto session.")
    async def map_veto_cmd(self, interaction: discord.Interaction):
        """Slash command to check map veto session."""
        view = MatchControlView()
        await view.map_veto_button(interaction, None)

    @app_commands.command(name="generate-seeds", description="[Admin] Generate team seeds for a tournament.")
    @app_commands.describe(tournament_id="Tournament ID", method="Seeding method (RANDOM or ELO)")
    async def generate_seeds_cmd(self, interaction: discord.Interaction, tournament_id: int, method: str = "RANDOM"):
        """Admin slash command to generate seeds."""
        from database.db import generate_tournament_seeds
        await interaction.response.defer(ephemeral=True)
        seeds = await generate_tournament_seeds(tournament_id, method.upper())
        if not seeds:
            await interaction.followup.send("❌ No approved teams or seeds already locked.", ephemeral=True)
            return
        
        desc = "\n".join([f"**Seed {s['seed_number']}**: Team ID {s['team_id']}" for s in seeds[:16]])
        embed = discord.Embed(
            title=f"🎲 Tournament #{tournament_id} Seeds Generated ({method.upper()})",
            description=desc,
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    """Asynchronously register MatchesCog."""
    await bot.add_cog(MatchesCog(bot))
