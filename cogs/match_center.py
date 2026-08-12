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
    get_user_team_membership,
    add_player_to_team_roster,
    remove_player_from_team_roster,
    lock_team_roster,
    get_user_all_registrations,
    get_user_notifications,
    _get_connection,
    log_admin_action
)

logger = logging.getLogger("GENEsportsBot")

class CreateTeamModal(discord.ui.Modal, title="Create New Esports Team"):
    team_name = discord.ui.TextInput(label="Team Name", placeholder="e.g. GEN Titans", required=True, min_length=2, max_length=50)
    game = discord.ui.TextInput(label="Primary Game", placeholder="VALORANT or PUBG MOBILE", default="VALORANT", required=True)
    region = discord.ui.TextInput(label="Region", placeholder="South Asia", default="South Asia", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            t_name = self.team_name.value.strip()
            g_name = self.game.value.strip()
            r_name = self.region.value.strip()

            # Ensure player record exists
            player_data = await get_or_create_player(
                discord_user_id=str(interaction.user.id),
                username=interaction.user.name,
                display_name=interaction.user.display_name,
                avatar_url=str(interaction.user.display_avatar.url) if interaction.user.display_avatar else ""
            )

            # Create team in database
            team_res = await get_or_create_team(
                name=t_name,
                captain_player_id=player_data["player_id"],
                game=g_name
            )

            if not team_res:
                await interaction.followup.send("❌ Failed to create team. A team with that name may already exist.", ephemeral=True)
                return

            embed = discord.Embed(
                title=f"🏆 Team **{t_name}** Created Successfully!",
                description=f"**Public Team ID:** `{team_res.get('public_id')}`\n**Captain:** {interaction.user.mention}\n**Game:** `{g_name}` | **Region:** `{r_name}`",
                color=discord.Color.green()
            )
            embed.set_footer(text="Use the 'MY TEAM' panel to add players and manage your roster.")
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error creating team: {e}")
            await interaction.followup.send(f"❌ Error creating team: {str(e)}", ephemeral=True)

class ConfirmAddPlayerView(discord.ui.View):
    def __init__(self, team_id: int, team_name: str, target_user: discord.User):
        super().__init__(timeout=120)
        self.team_id = team_id
        self.team_name = team_name
        self.target_user = target_user

    @discord.ui.button(label="Confirm Add", style=discord.ButtonStyle.success, emoji="✅")
    async def confirm_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            res = await add_player_to_team_roster(
                team_id=self.team_id,
                target_discord_id=str(self.target_user.id),
                username=self.target_user.name,
                display_name=self.target_user.display_name,
                role="PLAYER"
            )
            embed = discord.Embed(
                title="✅ Player Added to Roster",
                description=f"**{self.target_user.mention}** has been added to team **{self.team_name}** as a active player.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except ValueError as ve:
            await interaction.followup.send(f"❌ {str(ve)}", ephemeral=True)
        except Exception as e:
            logger.error(f"Error adding player to roster: {e}")
            await interaction.followup.send(f"❌ Error adding player: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel_add(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cancelled player addition.", ephemeral=True)

class AddPlayerUserSelectView(discord.ui.View):
    def __init__(self, team_id: int, team_name: str):
        super().__init__(timeout=180)
        self.team_id = team_id
        self.team_name = team_name

    @discord.ui.select(
        cls=discord.ui.UserSelect,
        placeholder="Select Discord User to Add to Roster...",
        min_values=1,
        max_values=1
    )
    async def select_user_callback(self, interaction: discord.Interaction, select: discord.ui.UserSelect):
        target_user = select.values[0]
        embed = discord.Embed(
            title="❓ Confirm Roster Addition",
            description=f"Add **{target_user.display_name}** ({target_user.mention}) to team **{self.team_name}**?",
            color=discord.Color.gold()
        )
        view = ConfirmAddPlayerView(self.team_id, self.team_name, target_user)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class RemovePlayerSelectView(discord.ui.View):
    def __init__(self, team_id: int, team_name: str, roster_players: list[dict]):
        super().__init__(timeout=180)
        self.team_id = team_id
        self.team_name = team_name
        self.roster_players = roster_players

        options = []
        for p in roster_players:
            if p.get("role") != "CAPTAIN":
                options.append(discord.SelectOption(
                    label=p.get("display_name", p.get("username", "Player")),
                    value=str(p["player_id"]),
                    description=f"Public ID: {p.get('public_id')} ({p.get('role')})"
                ))
        
        if not options:
            options.append(discord.SelectOption(label="No non-captain players to remove", value="none"))

        self.select_menu = discord.ui.Select(
            placeholder="Select player to remove from roster...",
            options=options
        )
        self.select_menu.callback = self.select_callback
        self.add_item(self.select_menu)

    async def select_callback(self, interaction: discord.Interaction):
        val = self.select_menu.values[0]
        if val == "none":
            await interaction.response.send_message("❌ No non-captain players available to remove.", ephemeral=True)
            return

        p_id = int(val)
        await interaction.response.defer(ephemeral=True)
        try:
            ok = await remove_player_from_team_roster(self.team_id, p_id)
            if ok:
                await interaction.followup.send(f"✅ Player removed from team **{self.team_name}** roster.", ephemeral=True)
            else:
                await interaction.followup.send("❌ Could not remove player.", ephemeral=True)
        except ValueError as ve:
            await interaction.followup.send(f"❌ {str(ve)}", ephemeral=True)

class LockRosterConfirmView(discord.ui.View):
    def __init__(self, team_id: int, team_name: str):
        super().__init__(timeout=120)
        self.team_id = team_id
        self.team_name = team_name

    @discord.ui.button(label="Lock Roster Now", style=discord.ButtonStyle.danger, emoji="🔒")
    async def confirm_lock(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            ok = await lock_team_roster(self.team_id)
            if ok:
                embed = discord.Embed(
                    title="🔒 Roster Locked Successfully",
                    description=f"Roster for team **{self.team_name}** has been locked for competitive integrity. Normal additions/removals are now prohibited without admin authorization.",
                    color=discord.Color.red()
                )
                await interaction.followup.send(embed=embed, ephemeral=True)
            else:
                await interaction.followup.send("❌ Failed to lock roster.", ephemeral=True)
        except Exception as e:
            await interaction.followup.send(f"❌ Error: {str(e)}", ephemeral=True)

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="❌")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("Cancelled roster lock.", ephemeral=True)

class MyTeamView(discord.ui.View):
    def __init__(self, user_id: str, membership: dict | None):
        super().__init__(timeout=300)
        self.user_id = user_id
        self.membership = membership

        if not membership:
            # No Team
            btn_create = discord.ui.Button(label="Create Team", style=discord.ButtonStyle.success, emoji="➕")
            btn_create.callback = self.create_team_cb
            self.add_item(btn_create)

            btn_tournaments = discord.ui.Button(label="View Tournaments", style=discord.ButtonStyle.primary, emoji="🔍")
            btn_tournaments.callback = self.view_tournaments_cb
            self.add_item(btn_tournaments)
        else:
            is_captain = membership.get("role") == "CAPTAIN"
            if is_captain:
                btn_add = discord.ui.Button(label="Add Player", style=discord.ButtonStyle.success, emoji="➕")
                btn_add.callback = self.add_player_cb
                self.add_item(btn_add)

                btn_remove = discord.ui.Button(label="Remove Player", style=discord.ButtonStyle.danger, emoji="➖")
                btn_remove.callback = self.remove_player_cb
                self.add_item(btn_remove)

                btn_lock = discord.ui.Button(label="Lock Roster", style=discord.ButtonStyle.secondary, emoji="🔒")
                btn_lock.callback = self.lock_roster_cb
                self.add_item(btn_lock)

            btn_roster = discord.ui.Button(label="View Roster", style=discord.ButtonStyle.primary, emoji="👥")
            btn_roster.callback = self.view_roster_cb
            self.add_item(btn_roster)

    async def create_team_cb(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateTeamModal())

    async def view_tournaments_cb(self, interaction: discord.Interaction):
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tournament_id, title, game_type, status, prize_pool FROM tournaments ORDER BY tournament_id DESC LIMIT 5;")
            tournaments = [dict(r) for r in cursor.fetchall()]

        embed = discord.Embed(title="📋 Available Tournaments", color=discord.Color.blue())
        if tournaments:
            for t in tournaments:
                embed.add_field(
                    name=f"🏆 {t['title']}",
                    value=f"**Game:** `{t['game_type']}` | **Status:** `{t['status']}` | **Prize:** `{t.get('prize_pool', 'N/A')}`",
                    inline=False
                )
        else:
            embed.description = "No active tournaments available at this time."

        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def add_player_cb(self, interaction: discord.Interaction):
        if not self.membership:
            return
        t_id = self.membership["team_id"]
        t_name = self.membership["team_name"]
        if self.membership.get("roster_locked"):
            await interaction.response.send_message("🔒 Roster is currently locked. Contact an admin to request changes.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"➕ Add Player to {t_name}",
            description="Select a Discord user from the dropdown menu below to add them to your active roster.",
            color=discord.Color.green()
        )
        view = AddPlayerUserSelectView(t_id, t_name)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def remove_player_cb(self, interaction: discord.Interaction):
        if not self.membership:
            return
        t_id = self.membership["team_id"]
        t_name = self.membership["team_name"]
        if self.membership.get("roster_locked"):
            await interaction.response.send_message("🔒 Roster is currently locked. Contact an admin to request changes.", ephemeral=True)
            return

        team_prof = await get_team_full_profile(str(t_id))
        roster = team_prof.get("roster", []) if team_prof else []

        embed = discord.Embed(
            title=f"➖ Remove Player from {t_name}",
            description="Select a player from your current roster below to deactivate their membership.",
            color=discord.Color.red()
        )
        view = RemovePlayerSelectView(t_id, t_name, roster)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def lock_roster_cb(self, interaction: discord.Interaction):
        if not self.membership:
            return
        t_id = self.membership["team_id"]
        t_name = self.membership["team_name"]

        embed = discord.Embed(
            title=f"🔒 Lock Roster for {t_name}?",
            description="Locking your roster ensures competitive integrity for active tournaments. Once locked, normal additions and removals will be disabled.",
            color=discord.Color.gold()
        )
        view = LockRosterConfirmView(t_id, t_name)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    async def view_roster_cb(self, interaction: discord.Interaction):
        if not self.membership:
            return
        t_id = self.membership["team_id"]
        team_prof = await get_team_full_profile(str(t_id))
        if not team_prof:
            await interaction.response.send_message("❌ Team profile not found.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"👥 {team_prof['name']} — Roster Profile",
            description=f"**Public ID:** `{team_prof.get('public_id')}`\n**Verification:** `{team_prof.get('verification_status')}`",
            color=discord.Color.blue()
        )
        roster = team_prof.get("roster", [])
        if roster:
            r_text = "\n".join([f"• **{p['display_name']}** (`{p['public_id']}`) - *{p['role']}*" for p in roster])
            embed.add_field(name="Active Members", value=r_text, inline=False)
        else:
            embed.add_field(name="Active Members", value="No roster members assigned.", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

class MatchCenterMainView(discord.ui.View):
    """Persistent Main Control View for persistent Discord Match Center panel."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="MY TEAM", style=discord.ButtonStyle.primary, emoji="👥", custom_id="match_center_my_team")
    async def my_team_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        membership = await get_user_team_membership(str(interaction.user.id))

        if not membership:
            embed = discord.Embed(
                title="🛡️ GEN Esports Team Portal",
                description="**You are not currently assigned to an active team.**\n\nCreate a new team or apply to join an existing team using the options below.",
                color=discord.Color.orange()
            )
        else:
            is_cap = membership.get("role") == "CAPTAIN"
            role_badge = "👑 Team Captain" if is_cap else "🛡️ Team Member"
            locked_badge = "🔒 Locked" if membership.get("roster_locked") else "🟢 Open"

            embed = discord.Embed(
                title=f"🛡️ TEAM: {membership['team_name']}",
                description=f"**Public ID:** `{membership['team_public_id']}`\n**Role:** `{role_badge}`\n**Roster Status:** `{locked_badge}`\n**Verification:** `{membership['verification_status']}`",
                color=discord.Color.green()
            )
            if membership.get("logo_url"):
                embed.set_thumbnail(url=membership["logo_url"])

        view = MyTeamView(str(interaction.user.id), membership)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @discord.ui.button(label="MY MATCHES", style=discord.ButtonStyle.success, emoji="🎮", custom_id="match_center_my_matches")
    async def my_matches_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        membership = await get_user_team_membership(str(interaction.user.id))
        if not membership:
            await interaction.followup.send("❌ You must belong to an active team to view your scheduled matches.", ephemeral=True)
            return

        t_name = membership["team_name"]
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, t1.name as team1_name, t2.name as team2_name, tr.title as tournament_name
                FROM matches m
                LEFT JOIN teams t1 ON m.team1_id = t1.team_id
                LEFT JOIN teams t2 ON m.team2_id = t2.team_id
                LEFT JOIN tournaments tr ON m.tournament_id = tr.tournament_id
                WHERE (LOWER(t1.name) = LOWER(?) OR LOWER(t2.name) = LOWER(?))
                ORDER BY m.match_id DESC LIMIT 10;
            """, (t_name, t_name))
            matches = [dict(r) for r in cursor.fetchall()]

        if not matches:
            await interaction.followup.send("🎮 Your team currently has no scheduled or active matches.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🎮 Active Matches for {t_name}",
            description="Select or open a match below to access confidential lobby info, map veto, check-in, and score submission.",
            color=discord.Color.blue()
        )

        class OpenMatchView(discord.ui.View):
            def __init__(self, match_list: list[dict]):
                super().__init__(timeout=180)
                options = []
                for m in match_list[:10]:
                    m_id_str = m.get('public_match_id') or str(m['match_id'])
                    t1 = m.get('team1_name') or 'TBD'
                    t2 = m.get('team2_name') or 'TBD'
                    options.append(discord.SelectOption(
                        label=f"Match #{m_id_str}: {t1} vs {t2}",
                        value=str(m['match_id']),
                        description=f"Status: {m.get('status')} | Stage: {m.get('stage_name', 'Match')}"
                    ))
                
                select = discord.ui.Select(placeholder="Select match to open...", options=options)
                select.callback = self.select_match_cb
                self.add_item(select)

            async def select_match_cb(self, sel_interaction: discord.Interaction):
                chosen_id = int(self.children[0].values[0])
                with _get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("SELECT discord_channel_id, public_match_id, status FROM matches WHERE match_id = ?;", (chosen_id,))
                    m_row = cursor.fetchone()

                if m_row and m_row["discord_channel_id"]:
                    ch_mention = f"<#{m_row['discord_channel_id']}>"
                    await sel_interaction.response.send_message(f"🎮 Access your match room: {ch_mention}", ephemeral=True)
                else:
                    await sel_interaction.response.send_message(f"🎮 Match #{chosen_id} room is currently initializing.", ephemeral=True)

        for m in matches[:5]:
            m_id_str = m.get('public_match_id') or str(m['match_id'])
            t1 = m.get('team1_name') or 'TBD'
            t2 = m.get('team2_name') or 'TBD'
            embed.add_field(
                name=f"🏆 Match #{m_id_str} — {m.get('tournament_name', 'Tournament')}",
                value=f"**VS:** `{t1}` vs `{t2}`\n**Status:** `{m.get('status')}` | **Stage:** `{m.get('stage_name')}`",
                inline=False
            )

        await interaction.followup.send(embed=embed, view=OpenMatchView(matches), ephemeral=True)

    @discord.ui.button(label="MY TOURNAMENTS", style=discord.ButtonStyle.primary, emoji="📋", custom_id="match_center_my_tournaments")
    async def my_tournaments_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        regs = await get_user_all_registrations(str(interaction.user.id))
        embed = discord.Embed(title="📋 My Tournament Registrations", color=discord.Color.purple())

        if regs:
            for r in regs:
                embed.add_field(
                    name=f"🏆 {r['tournament_name']}",
                    value=f"**Team:** `{r['team_name']}` | **Status:** `{r['status']}`",
                    inline=False
                )
        else:
            embed.description = "You have no active tournament registrations."

        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="NOTIFICATIONS", style=discord.ButtonStyle.secondary, emoji="🔔", custom_id="match_center_notifications")
    async def notifications_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        notifs = await get_user_notifications(str(interaction.user.id))
        embed = discord.Embed(title="🔔 User Notifications", color=discord.Color.gold())

        if notifs:
            for n in notifs[:5]:
                embed.add_field(
                    name=f"📌 {n['title']}",
                    value=f"{n['message']}",
                    inline=False
                )
        else:
            embed.description = "No recent notifications."

        await interaction.followup.send(embed=embed, ephemeral=True)

    @discord.ui.button(label="SUPPORT", style=discord.ButtonStyle.danger, emoji="🆘", custom_id="match_center_support")
    async def support_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🆘 GEN Esports Support Center",
            description="Need help with registrations, match disputes, or payment issues?\n\nUse the `/ticket` slash command or visit the support channel to open a support case.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

class MatchCenterCog(commands.Cog):
    """Cog for persistent Discord Match Center panel management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup-match-center", description="[Admin] Post persistent GEN Esports Match Center panel into channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_match_center_cmd(self, interaction: discord.Interaction):
        """Admin command to post persistent Match Center panel embed."""
        embed = discord.Embed(
            title="━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n       GEN ESPORTS MATCH CENTER\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            description="Welcome to **GEN Esports**. Manage your competitive team, roster, scheduled matches, and tournament registrations using the persistent control panel below.",
            color=discord.Color.from_rgb(0, 255, 163)
        )
        embed.add_field(name="👥 MY TEAM", value="Create team, add/remove roster players, lock roster.", inline=True)
        embed.add_field(name="🎮 MY MATCHES", value="Access active match rooms, check-in & map veto.", inline=True)
        embed.add_field(name="📋 MY TOURNAMENTS", value="View registrations & status.", inline=True)
        embed.set_footer(text="GEN Esports Competitive Management Engine • Persistent Panel")

        view = MatchCenterMainView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Persistent Match Center panel posted successfully!", ephemeral=True)

async def setup(bot: commands.Bot):
    """Register MatchCenterCog."""
    await bot.add_cog(MatchCenterCog(bot))
