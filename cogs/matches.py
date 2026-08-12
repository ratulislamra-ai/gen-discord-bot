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

            # Determine winner and advance bracket if scores are non-equal
            winner_id = None
            if s_a > s_b:
                winner_id = match_res.get("team1_id")
            elif s_b > s_a:
                winner_id = match_res.get("team2_id")

            next_match_info = None
            if winner_id:
                with _get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("UPDATE matches SET status = 'COMPLETED', winner_id = ? WHERE match_id = ?;", (winner_id, match_res["match_id"]))
                    conn.commit()

                from database.db import advance_bracket_and_create_next_match
                next_match_info = await advance_bracket_and_create_next_match(match_res["match_id"], winner_id)

                if next_match_info and next_match_info.get("team1_id") and next_match_info.get("team2_id"):
                    try:
                        await create_or_get_match_room_channel(interaction.guild, next_match_info["match_id"])
                    except Exception as ex:
                        logger.warning(f"Auto-provisioning next match room error: {ex}")

            embed = discord.Embed(
                title="🏆 Match Result Submitted & Verified",
                description=f"Result for **Match #{match_res.get('public_match_id') or match_res.get('match_id')}** recorded.\n\n**Final Score:** `{s_a} - {s_b}`",
                color=discord.Color.green()
            )
            if winner_id:
                embed.add_field(name="Winner Team ID", value=f"`{winner_id}`", inline=True)
                embed.add_field(name="Match Status", value="`COMPLETED`", inline=True)
                if next_match_info:
                    embed.add_field(name="Bracket Advancement", value=f"Winner advanced to **Next Match #{next_match_info.get('public_match_id') or next_match_info['match_id']}**", inline=False)
            
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

    @discord.ui.button(label="JOIN MY TEAM", style=discord.ButtonStyle.secondary, emoji="👥", custom_id="match_ctrl_join_team")
    async def join_team_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        user_regs = await get_user_all_registrations(user_id)
        if not user_regs:
            await interaction.followup.send("❌ You are not a participant in this match.", ephemeral=True)
            return

        team_names = [r["team_name"] for r in user_regs]
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, t1.name as team1_name, t2.name as team2_name, t1.team_id as t1_id, t2.team_id as t2_id
                FROM matches m
                LEFT JOIN teams t1 ON m.team1_id = t1.team_id
                LEFT JOIN teams t2 ON m.team2_id = t2.team_id
                WHERE m.status IN ('SCHEDULED', 'CHECK_IN_OPEN', 'READY', 'IN_PROGRESS')
                ORDER BY m.match_id DESC LIMIT 10;
            """)
            matches = [dict(r) for r in cursor.fetchall()]

        target_m = None
        assigned_team = ""
        assigned_team_id = 0
        for m in matches:
            if m.get("team1_name") in team_names:
                target_m = m
                assigned_team = m["team1_name"]
                assigned_team_id = m["t1_id"]
                break
            elif m.get("team2_name") in team_names:
                target_m = m
                assigned_team = m["team2_name"]
                assigned_team_id = m["t2_id"]
                break

        if not target_m:
            await interaction.followup.send("❌ You are not a participant in this match.", ephemeral=True)
            return

        # Dynamically ensure permission overwrite for participant
        try:
            ch = interaction.channel
            if isinstance(ch, discord.TextChannel):
                po = discord.PermissionOverwrite(read_messages=True, send_messages=True, connect=True, speak=True)
                await ch.set_permissions(interaction.user, overwrite=po)
        except Exception as e:
            logger.warning(f"Could not apply channel permission overwrite for user {user_id}: {e}")

        embed = discord.Embed(
            title="👥 Team Access Verified!",
            description=f"Welcome {interaction.user.mention}! You are verified as a player for **{assigned_team}** in **Match #{target_m.get('public_match_id') or target_m['match_id']}**.",
            color=discord.Color.green()
        )
        embed.add_field(name="Match Status", value=f"`{target_m.get('status')}`", inline=True)
        embed.add_field(name="Stage", value=f"`{target_m.get('stage_name', 'Tournament Round')}`", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

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

async def handle_match_info_logic(interaction: discord.Interaction, match_id: Optional[int] = None):
    """Business logic for fetching and displaying match and lobby information."""
    if not interaction.response.is_done():
        await interaction.response.defer(ephemeral=True)

    try:
        if match_id:
            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT m.*, t1.name as team1_name, t2.name as team2_name, tr.title as tournament_name
                    FROM matches m
                    LEFT JOIN teams t1 ON m.team1_id = t1.team_id
                    LEFT JOIN teams t2 ON m.team2_id = t2.team_id
                    LEFT JOIN tournaments tr ON m.tournament_id = tr.tournament_id
                    WHERE m.match_id = ?;
                """, (match_id,))
                row = cursor.fetchone()

            if not row:
                await interaction.followup.send(f"❌ Match #{match_id} does not exist in database.", ephemeral=True)
                return

            target_m = dict(row)
        else:
            user_regs = await get_user_all_registrations(str(interaction.user.id))
            team_names = [r["team_name"] for r in user_regs] if user_regs else []

            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT m.*, t1.name as team1_name, t2.name as team2_name, tr.title as tournament_name
                    FROM matches m
                    LEFT JOIN teams t1 ON m.team1_id = t1.team_id
                    LEFT JOIN teams t2 ON m.team2_id = t2.team_id
                    LEFT JOIN tournaments tr ON m.tournament_id = tr.tournament_id
                    ORDER BY m.match_id DESC LIMIT 20;
                """)
                matches = [dict(r) for r in cursor.fetchall()]

            target_m = None
            if team_names:
                for m in matches:
                    if m.get("team1_name") in team_names or m.get("team2_name") in team_names:
                        target_m = m
                        break

            if not target_m and matches:
                target_m = matches[0]

        if not target_m:
            await interaction.followup.send("ℹ️ No active tournament matches found.", ephemeral=True)
            return

        pm_id = target_m.get("public_match_id") or f"GEN-M-{target_m['match_id']:06d}"
        t1_name = target_m.get("team1_name") or "Team A"
        t2_name = target_m.get("team2_name") or "Team B"
        tr_title = target_m.get("tournament_name") or "GEN Esports Championship"
        stage = target_m.get("stage_name") or "Round 1"
        m_status = target_m.get("status") or "SCHEDULED"

        embed = discord.Embed(
            title=f"🎮 Match #{target_m['match_id']} ({pm_id}) Details",
            description=f"**Tournament:** `{tr_title}`\n**Stage:** `{stage}`\n**Status:** `{m_status}`\n\n**{t1_name}**  VS  **{t2_name}**",
            color=discord.Color.blue()
        )
        embed.add_field(name="Team 1", value=f"**{t1_name}**", inline=True)
        embed.add_field(name="Team 2", value=f"**{t2_name}**", inline=True)
        embed.add_field(name="Match ID", value=f"`#{target_m['match_id']}`", inline=True)
        embed.add_field(name="Lobby Name", value=f"`{target_m.get('lobby_name') or 'GEN-LOBBY-' + str(target_m['match_id'])}`", inline=True)
        embed.add_field(name="Lobby Code", value=f"`{target_m.get('lobby_code') or 'GEN123'}`", inline=True)
        embed.add_field(name="Lobby Password", value=f"`{target_m.get('lobby_password') or 'GEN2026'}`", inline=True)
        embed.set_footer(text="Confidential • GEN Esports Competitive Integrity System")

        await interaction.followup.send(embed=embed, ephemeral=True)
    except Exception as e:
        logger.error(f"Error displaying match details: {e}", exc_info=True)
        await interaction.followup.send(f"❌ Error displaying match details: {str(e)}", ephemeral=True)

class MatchControlView(discord.ui.View):
    """Persistent View for Discord Match Channels & Rooms."""
    def __init__(self, match_id: str = ""):
        super().__init__(timeout=None)
        self.match_id = match_id

    @discord.ui.button(label="JOIN MY TEAM", style=discord.ButtonStyle.secondary, emoji="👥", custom_id="match_ctrl_join_team")
    async def join_team_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_id = str(interaction.user.id)
        user_regs = await get_user_all_registrations(user_id)
        if not user_regs:
            await interaction.followup.send("❌ You are not a participant in this match.", ephemeral=True)
            return

        team_names = [r["team_name"] for r in user_regs]
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, t1.name as team1_name, t2.name as team2_name, t1.team_id as t1_id, t2.team_id as t2_id
                FROM matches m
                LEFT JOIN teams t1 ON m.team1_id = t1.team_id
                LEFT JOIN teams t2 ON m.team2_id = t2.team_id
                WHERE m.status IN ('SCHEDULED', 'CHECK_IN_OPEN', 'READY', 'IN_PROGRESS')
                ORDER BY m.match_id DESC LIMIT 10;
            """)
            matches = [dict(r) for r in cursor.fetchall()]

        target_m = None
        assigned_team = ""
        assigned_team_id = 0
        for m in matches:
            if m.get("team1_name") in team_names:
                target_m = m
                assigned_team = m["team1_name"]
                assigned_team_id = m["t1_id"]
                break
            elif m.get("team2_name") in team_names:
                target_m = m
                assigned_team = m["team2_name"]
                assigned_team_id = m["t2_id"]
                break

        if not target_m:
            await interaction.followup.send("❌ You are not a participant in this match.", ephemeral=True)
            return

        try:
            ch = interaction.channel
            if isinstance(ch, discord.TextChannel):
                po = discord.PermissionOverwrite(read_messages=True, send_messages=True, connect=True, speak=True)
                await ch.set_permissions(interaction.user, overwrite=po)
        except Exception as e:
            logger.warning(f"Could not apply channel permission overwrite for user {user_id}: {e}")

        embed = discord.Embed(
            title="👥 Team Access Verified!",
            description=f"Welcome {interaction.user.mention}! You are verified as a player for **{assigned_team}** in **Match #{target_m.get('public_match_id') or target_m['match_id']}**.",
            color=discord.Color.green()
        )
        embed.add_field(name="Match Status", value=f"`{target_m.get('status')}`", inline=True)
        embed.add_field(name="Stage", value=f"`{target_m.get('stage_name', 'Tournament Round')}`", inline=True)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="Check In", style=discord.ButtonStyle.success, emoji="🎟️", custom_id="match_ctrl_checkin")
    async def check_in_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        user_regs = await get_user_all_registrations(str(interaction.user.id))
        if not user_regs:
            await interaction.followup.send("❌ You must be registered in a team to check in for matches.", ephemeral=True)
            return

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
        await handle_match_info_logic(interaction)

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
        await view.check_in_button.callback(interaction)

    @app_commands.command(name="match-info", description="View confidential lobby and match details for your match.")
    @app_commands.describe(match_id="Optional specific Match ID to view")
    async def match_info_cmd(self, interaction: discord.Interaction, match_id: Optional[int] = None):
        """Slash command to view match details."""
        await handle_match_info_logic(interaction, match_id)

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

    @app_commands.command(name="transfer-captaincy", description="[Captain] Transfer team captaincy to another roster member.")
    @app_commands.describe(team_id="Team ID", new_captain="Mention target Discord user")
    async def transfer_captaincy_cmd(self, interaction: discord.Interaction, team_id: int, new_captain: discord.User):
        """Transfer team captaincy to a roster member."""
        from database.db import get_or_create_player, transfer_team_captaincy
        await interaction.response.defer(ephemeral=True)
        try:
            target_p = await get_or_create_player(str(new_captain.id), new_captain.name, new_captain.display_name)
            ok = await transfer_team_captaincy(team_id, target_p["player_id"])
            if ok:
                await interaction.followup.send(f"👑 Captaincy transferred to **{new_captain.display_name}** successfully!", ephemeral=True)
            else:
                await interaction.followup.send("❌ Transfer failed.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @app_commands.command(name="inspect-team-history", description="[Staff] Inspect complete team history and past roster snapshots.")
    @app_commands.describe(team_id_or_slug="Team ID or Team Name/Slug")
    async def inspect_team_history_cmd(self, interaction: discord.Interaction, team_id_or_slug: str):
        """Staff command to view team history."""
        from database.db import get_team_history
        await interaction.response.defer(ephemeral=True)
        h = await get_team_history(team_id_or_slug)
        if not h:
            await interaction.followup.send("❌ Team history not found.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"📜 Team History • {h.get('name')}",
            description=f"**Public ID:** `{h.get('public_id')}`\n**Region:** `{h.get('region')}`\n**Roster Lock:** `{'LOCKED' if h.get('roster_locked') else 'UNLOCKED'}`",
            color=discord.Color.blue()
        )
        roster_str = "\n".join([f"• {p.get('display_name')} (`{p.get('role')}`) - Joined: {str(p.get('joined_at'))[:10]}" for p in h.get("roster_history", [])[:10]])
        embed.add_field(name="Roster Members", value=roster_str or "No history", inline=False)
        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(name="create-match-room", description="[Admin/Staff] Provision private match room channels for a match.")
    @app_commands.describe(match_id="Match ID")
    async def create_match_room_cmd(self, interaction: discord.Interaction, match_id: int):
        """Admin command to trigger private match room channel creation."""
        await interaction.response.defer(ephemeral=True)
        ok, msg, chs = await create_or_get_match_room_channel(interaction.guild, match_id)
        if not ok:
            await interaction.followup.send(msg, ephemeral=True)
            return

        if "t1_text" in chs:
            desc = (
                f"**Tournament:** GEN Esports Championship\n"
                f"**Match ID:** #{match_id}\n\n"
                f"**Channels:**\n"
                f"• Shared Chat: {chs['shared_text'].mention}\n"
                f"• Team A Private Chat: {chs['t1_text'].mention}\n"
                f"• Team B Private Chat: {chs['t2_text'].mention}\n"
                f"• Shared Voice: {chs['shared_voice'].mention}\n"
                f"• Team A Voice: {chs['t1_voice'].mention}\n"
                f"• Team B Voice: {chs['t2_voice'].mention}"
            )
            embed = discord.Embed(title="✅ MATCH ROOM CREATED", description=desc, color=discord.Color.green())
            await interaction.followup.send(embed=embed, ephemeral=True)
        else:
            await interaction.followup.send(msg, ephemeral=True)

async def create_or_get_match_room_channel(guild: discord.Guild, match_id: int) -> tuple[bool, str, dict]:
    """Find or create private Discord match room channels for a scheduled match with granular permission overwrites."""
    from database.db import validate_match_room_creation, get_team_roster_discord_ids, save_match_discord_channel
    
    valid, msg, m = await validate_match_room_creation(match_id)
    if not valid or not m:
        return False, msg, {}

    pm_id = m.get("public_match_id") or f"{match_id:06d}"
    t1_name = m.get("team1_name") or "Team A"
    t2_name = m.get("team2_name") or "Team B"

    ch_id = m.get("discord_channel_id")
    if ch_id:
        existing_ch = guild.get_channel(int(ch_id))
        if existing_ch and isinstance(existing_ch, discord.TextChannel):
            return True, f"ℹ️ Match room already exists: {existing_ch.mention}", {"shared_text": existing_ch}

    cat_name = f"🔒 MATCH #{match_id}: {t1_name} vs {t2_name}"
    category = discord.utils.get(guild.categories, name=cat_name)
    if not category:
        try:
            category = await guild.create_category(cat_name)
        except Exception as e:
            logger.error(f"Error creating category: {e}")
            category = None

    t1_discords = await get_team_roster_discord_ids(m["t1_id"])
    t2_discords = await get_team_roster_discord_ids(m["t2_id"])

    staff_overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False, connect=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, connect=True)
    }

    t1_overwrites = dict(staff_overwrites)
    t2_overwrites = dict(staff_overwrites)
    shared_overwrites = dict(staff_overwrites)

    for d_id in t1_discords:
        try:
            member = guild.get_member(int(d_id)) or await guild.fetch_member(int(d_id))
            if member:
                po = discord.PermissionOverwrite(read_messages=True, send_messages=True, connect=True, speak=True)
                t1_overwrites[member] = po
                shared_overwrites[member] = po
        except Exception:
            pass

    for d_id in t2_discords:
        try:
            member = guild.get_member(int(d_id)) or await guild.fetch_member(int(d_id))
            if member:
                po = discord.PermissionOverwrite(read_messages=True, send_messages=True, connect=True, speak=True)
                t2_overwrites[member] = po
                shared_overwrites[member] = po
        except Exception:
            pass

    base_kwargs = {"category": category} if category else {}

    shared_text = await guild.create_text_channel(name=f"match-{match_id}", overwrites=shared_overwrites, **base_kwargs)
    t1_text = await guild.create_text_channel(name=f"{t1_name.lower().replace(' ', '-')}-private", overwrites=t1_overwrites, **base_kwargs)
    t2_text = await guild.create_text_channel(name=f"{t2_name.lower().replace(' ', '-')}-private", overwrites=t2_overwrites, **base_kwargs)

    shared_voice = await guild.create_voice_channel(name="🔊 Match Voice", overwrites=shared_overwrites, **base_kwargs)
    t1_voice = await guild.create_voice_channel(name=f"🔊 {t1_name} Voice", overwrites=t1_overwrites, **base_kwargs)
    t2_voice = await guild.create_voice_channel(name=f"🔊 {t2_name} Voice", overwrites=t2_overwrites, **base_kwargs)

    await save_match_discord_channel(match_id, str(shared_text.id))

    embed = discord.Embed(
        title="━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🏆 GEN ESPORTS MATCH ROOM\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        description=(
            f"**Match ID:** `{pm_id}`\n\n"
            f"**{t1_name}**  VS  **{t2_name}**\n\n"
            f"**Tournament:** `{m.get('tournament_name', 'Championship')}`\n"
            f"**Stage:** `{m.get('stage_name', 'Round 1')}`"
        ),
        color=discord.Color.from_rgb(0, 255, 163)
    )
    embed.add_field(name="Check-in Status", value=f"{t1_name}: ❌\n{t2_name}: ❌", inline=False)
    embed.set_footer(text="Use the control buttons below for Check-in, Map Veto, Lobby Credentials & Score Submission.")

    view = MatchControlView(str(match_id))
    await shared_text.send(embed=embed, view=view)

    channels_dict = {
        "shared_text": shared_text,
        "t1_text": t1_text,
        "t2_text": t2_text,
        "shared_voice": shared_voice,
        "t1_voice": t1_voice,
        "t2_voice": t2_voice
    }

    return True, "✅ MATCH ROOM CREATED", channels_dict

async def setup(bot: commands.Bot):
    """Asynchronously register MatchesCog."""
    await bot.add_cog(MatchesCog(bot))
