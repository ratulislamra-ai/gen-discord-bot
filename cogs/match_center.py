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
    get_player_current_match,
    get_player_upcoming_matches,
    get_match_by_channel_id,
    get_uncompleted_matches,
    save_match_discord_channel,
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

from datetime import datetime
import pytz

def format_dhaka_time(timestamp_str: str | None) -> str:
    """Format UTC/ISO timestamp string into Asia/Dhaka local time."""
    if not timestamp_str:
        return "TBD / Not Scheduled"
    try:
        clean_str = str(timestamp_str).replace("Z", "+00:00")
        dt = datetime.fromisoformat(clean_str)
        dhaka_tz = pytz.timezone("Asia/Dhaka")
        if dt.tzinfo is None:
            dt = pytz.utc.localize(dt)
        local_dt = dt.astimezone(dhaka_tz)
        return local_dt.strftime("%b %d, %Y at %I:%M %p (BST)")
    except Exception:
        return str(timestamp_str)

class MatchRoomSelect(discord.ui.Select):
    """Dropdown menu to select a database match to bind to current channel."""
    def __init__(self, matches: list[dict]):
        options = []
        for m in matches[:25]:
            pm_id = m.get("public_match_id") or f"GEN-M-{m['match_id']:06d}"
            t1 = m.get("team1_name") or "TBD"
            t2 = m.get("team2_name") or "TBD"
            tr_title = m.get("tournament_name") or "Tournament"
            options.append(discord.SelectOption(
                label=f"{pm_id} — {t1} vs {t2}",
                value=str(m["match_id"]),
                description=f"{tr_title} | Status: {m.get('status', 'SCHEDULED')}"
            ))
        super().__init__(placeholder="Select the database match to bind to this channel...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        chosen_match_id = int(self.values[0])
        ch_id = str(interaction.channel.id)
        guild_id = str(interaction.guild.id) if interaction.guild else None

        # Fetch match details from DB
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, 
                       t1.name as team1_name, t2.name as team2_name, tr.title as tournament_name
                FROM matches m
                LEFT JOIN teams t1 ON m.team1_id = t1.team_id
                LEFT JOIN teams t2 ON m.team2_id = t2.team_id
                LEFT JOIN tournaments tr ON m.tournament_id = tr.tournament_id
                WHERE m.match_id = ?;
            """, (chosen_match_id,))
            m = cursor.fetchone()
            if not m:
                await interaction.followup.send("❌ Match not found in database.", ephemeral=True)
                return
            m = dict(m)

        existing_ch = m.get("discord_channel_id")
        if existing_ch and str(existing_ch) != ch_id:
            # Match is already connected to another channel
            warn_embed = discord.Embed(
                title="⚠️ Match Room Already Exists",
                description=f"This match is already connected to <#{existing_ch}>.\n\nDo you want to rebind it to **#{interaction.channel.name}**?",
                color=discord.Color.gold()
            )

            class RebindConfirmView(discord.ui.View):
                def __init__(self, m_id: int, new_ch: str, g_id: str | None, match_dict: dict):
                    super().__init__(timeout=120)
                    self.m_id = m_id
                    self.new_ch = new_ch
                    self.g_id = g_id
                    self.match_dict = match_dict

                @discord.ui.button(label="REBIND TO THIS CHANNEL", style=discord.ButtonStyle.danger, emoji="⚠️")
                async def confirm_rebind(self, rebind_int: discord.Interaction, btn: discord.ui.Button):
                    await rebind_int.response.defer(ephemeral=True)
                    await save_match_discord_channel(self.m_id, self.new_ch, self.g_id)
                    await post_match_room_center_panel(rebind_int.channel, self.match_dict)
                    await rebind_int.followup.send(f"✅ Rebound Match **#{self.match_dict.get('public_match_id') or self.m_id}** to <#{self.new_ch}>!", ephemeral=True)

                @discord.ui.button(label="USE EXISTING ROOM", style=discord.ButtonStyle.secondary, emoji="🔗")
                async def use_existing(self, exist_int: discord.Interaction, btn: discord.ui.Button):
                    await exist_int.response.send_message(f"ℹ️ Kept existing match room: <#{existing_ch}>", ephemeral=True)

            await interaction.followup.send(embed=warn_embed, view=RebindConfirmView(chosen_match_id, ch_id, guild_id, m), ephemeral=True)
            return

        # Save channel ID and guild ID in database
        await save_match_discord_channel(chosen_match_id, ch_id, guild_id)

        # Post persistent Match Center panel in current channel
        await post_match_room_center_panel(interaction.channel, m)
        await interaction.followup.send(f"✅ Successfully bound Match **#{m.get('public_match_id') or chosen_match_id}** to **#{interaction.channel.name}** and posted the Match Center panel!", ephemeral=True)

class MatchRoomSelectView(discord.ui.View):
    """Container view for MatchRoomSelect dropdown."""
    def __init__(self, matches: list[dict]):
        super().__init__(timeout=180)
        self.add_item(MatchRoomSelect(matches))

async def post_match_room_center_panel(channel: discord.TextChannel | discord.abc.GuildChannel, m: dict):
    """Post the formatted persistent Match Room panel embed into the given channel."""
    pm_id = m.get("public_match_id") or f"GEN-M-{m['match_id']:06d}"
    t1 = m.get("team1_name") or "TBD"
    t2 = m.get("team2_name") or "TBD"
    tr_name = m.get("tournament_name") or "GEN Esports Championship"
    s_time = format_dhaka_time(m.get("scheduled_time"))
    status_val = m.get("status", "SCHEDULED")
    status_icon = "🟢" if status_val == "SCHEDULED" else "🟡" if status_val == "CHECK_IN" else "🔵" if status_val == "LIVE" else "🏆" if status_val == "COMPLETED" else "🔴"

    embed = discord.Embed(
        title="🏆 GEN ESPORTS — MATCH ROOM",
        description="━━━━━━━━━━━━━━━━━━━━",
        color=discord.Color.from_rgb(0, 240, 255)
    )
    embed.add_field(name="🎮 Tournament", value=f"`{tr_name}`", inline=False)
    embed.add_field(name="⚔️ Match", value=f"`{t1}` vs `{t2}`", inline=False)
    embed.add_field(name="🆔 Match ID", value=f"`{pm_id}`", inline=True)
    embed.add_field(name="🕐 Scheduled", value=f"`{s_time}`", inline=True)
    embed.add_field(name="📊 Status", value=f"{status_icon} `{status_val}`", inline=True)
    embed.set_footer(text="GEN Esports Match Control Engine • Persistent Control Panel")

    view = MatchCenterMainView()
    await channel.send(embed=embed, view=view)

class MatchCenterMainView(discord.ui.View):
    """Persistent Control Panel for GEN Esports Match Center."""
    def __init__(self):
        super().__init__(timeout=None)

    async def _get_active_match(self, interaction: discord.Interaction) -> dict | None:
        """Fetch match associated with current channel first, or fallback to user's assigned match."""
        if interaction.channel:
            ch_match = await get_match_by_channel_id(str(interaction.channel.id))
            if ch_match:
                return ch_match
        return await get_player_current_match(str(interaction.user.id))

    @discord.ui.button(label="MY MATCH", style=discord.ButtonStyle.primary, emoji="📋", custom_id="gen_match_center:my_match", row=0)
    async def my_match_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            m = await self._get_active_match(interaction)
            if not m:
                await interaction.followup.send("❌ You currently have no active or upcoming matches assigned to your team.", ephemeral=True)
                return

            pm_id = m.get("public_match_id") or f"{m['match_id']:06d}"
            ch_id = m.get("discord_channel_id")
            ch_link = f"<#{ch_id}>" if ch_id else "Not created yet"

            t1_check = "✅ Checked In" if m.get("team_a_checked_in") else "❌ Pending"
            t2_check = "✅ Checked In" if m.get("team_b_checked_in") else "❌ Pending"

            embed = discord.Embed(
                title=f"🏆 GEN ESPORTS — MY MATCH #{pm_id}",
                description=f"**Tournament:** `{m.get('tournament_name', 'Championship')}`\n**Stage / Round:** `{m.get('stage_name', 'Round 1')}`",
                color=discord.Color.from_rgb(0, 240, 255)
            )
            embed.add_field(name="Your Team", value=f"`{m.get('my_team_name', m.get('team1_name', 'Team A'))}`", inline=True)
            embed.add_field(name="Opponent", value=f"`{m.get('opponent_team_name', m.get('team2_name', 'Team B'))}`", inline=True)
            embed.add_field(name="Scheduled Time (Asia/Dhaka)", value=f"`{format_dhaka_time(m.get('scheduled_time'))}`", inline=False)
            embed.add_field(name="Match Status", value=f"`{m.get('status', 'PENDING')}`", inline=True)
            embed.add_field(name="Match Room", value=ch_link, inline=True)
            embed.add_field(name="Check-in Status", value=f"`{m.get('team1_name', 'Team A')}`: {t1_check}\n`{m.get('team2_name', 'Team B')}`: {t2_check}", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in my_match_button: {e}")
            await interaction.followup.send("❌ Unable to load match information right now. Please try again.", ephemeral=True)

    @discord.ui.button(label="SCHEDULE", style=discord.ButtonStyle.secondary, emoji="🕐", custom_id="gen_match_center:schedule", row=0)
    async def schedule_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            m = await self._get_active_match(interaction)
            matches = await get_player_upcoming_matches(str(interaction.user.id))
            if not matches and not m:
                await interaction.followup.send("🎮 You currently have no upcoming scheduled matches.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🕐 MATCH SCHEDULE",
                description="All times displayed in **Asia/Dhaka (BST)** timezone.",
                color=discord.Color.blue()
            )
            if m and m.get("scheduled_time"):
                pm_id = m.get("public_match_id") or f"{m['match_id']:06d}"
                embed.add_field(
                    name=f"⏰ Current Match #{pm_id} — {format_dhaka_time(m.get('scheduled_time'))}",
                    value=f"**🎮 Tournament:** `{m.get('tournament_name', 'Tournament')}`\n**⚔️ Matchup:** `{m.get('team1_name', 'TBD')}` vs `{m.get('team2_name', 'TBD')}`\n**🏆 Stage:** `{m.get('stage_name', 'Round 1')}` | **📌 Status:** `{m.get('status')}`",
                    inline=False
                )

            for upcoming_m in (matches or [])[:5]:
                if m and upcoming_m["match_id"] == m["match_id"]:
                    continue
                pm_id = upcoming_m.get("public_match_id") or f"{upcoming_m['match_id']:06d}"
                t1 = upcoming_m.get("team1_name") or "TBD"
                t2 = upcoming_m.get("team2_name") or "TBD"
                s_time = format_dhaka_time(upcoming_m.get("scheduled_time"))
                embed.add_field(
                    name=f"⏰ {s_time} — Match #{pm_id}",
                    value=f"**🎮 Tournament:** `{upcoming_m.get('tournament_name', 'Tournament')}`\n**⚔️ Matchup:** `{t1}` vs `{t2}`\n**🏆 Stage:** `{upcoming_m.get('stage_name', 'Round 1')}` | **📌 Status:** `{upcoming_m.get('status')}`",
                    inline=False
                )
            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in schedule_button: {e}")
            await interaction.followup.send("❌ Unable to load match schedule right now. Please try again.", ephemeral=True)

    @discord.ui.button(label="OPPONENT", style=discord.ButtonStyle.secondary, emoji="⚔️", custom_id="gen_match_center:opponent", row=0)
    async def opponent_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            m = await self._get_active_match(interaction)
            if not m:
                await interaction.followup.send("⚔️ Opponent information is not available yet.", ephemeral=True)
                return

            op_name = m.get("opponent_team_name") or m.get("team2_name") or "TBD / Bye"
            op_slug = m.get("opponent_team_slug") or m.get("team2_slug")
            cap_name = m.get("opponent_captain_name") or m.get("t2_captain_name") or "Not assigned"
            cap_disc = m.get("opponent_captain_discord") or m.get("t2_captain_discord")
            cap_text = f"{cap_name} (<@{cap_disc}>)" if cap_disc else cap_name

            embed = discord.Embed(
                title=f"⚔️ OPPONENT DETAILS: {op_name}",
                description=f"**Match ID:** `{m.get('public_match_id') or m['match_id']}`\n**Scheduled Time:** `{format_dhaka_time(m.get('scheduled_time'))}`\n**Match Status:** `{m.get('status')}`",
                color=discord.Color.red()
            )
            embed.add_field(name="Team Captain", value=cap_text, inline=False)

            if op_slug:
                op_profile = await get_team_full_profile(op_slug)
                if op_profile and op_profile.get("roster"):
                    roster_lines = [f"• **{p['display_name']}** (`{p['role']}`)" for p in op_profile["roster"]]
                    embed.add_field(name="Active Roster", value="\n".join(roster_lines), inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in opponent_button: {e}")
            await interaction.followup.send("❌ Unable to load opponent information right now.", ephemeral=True)

    @discord.ui.button(label="MATCH ROOM", style=discord.ButtonStyle.success, emoji="🏠", custom_id="gen_match_center:match_room", row=0)
    async def match_room_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            m = await self._get_active_match(interaction)
            if not m:
                await interaction.followup.send("❌ No match is assigned to this channel or your team.", ephemeral=True)
                return

            ch_id = m.get("discord_channel_id")
            pm_id = m.get("public_match_id") or m["match_id"]

            if ch_id and str(interaction.channel.id) == str(ch_id):
                await interaction.followup.send(f"✅ You are currently inside the designated Match Room (<#{ch_id}>) for Match **#{pm_id}**!", ephemeral=True)
            elif ch_id:
                await interaction.followup.send(f"🏠 Match **#{pm_id}** room is located at <#{ch_id}>.", ephemeral=True)
            else:
                await interaction.followup.send(f"🏠 Match room for Match **#{pm_id}** has not been assigned yet. Run `/match-room` in the desired channel.", ephemeral=True)
        except Exception as e:
            logger.error(f"Error in match_room_button: {e}")
            await interaction.followup.send("❌ Unable to load match room details.", ephemeral=True)

    @discord.ui.button(label="LOBBY INFO", style=discord.ButtonStyle.secondary, emoji="🔐", custom_id="gen_match_center:lobby_info", row=1)
    async def lobby_info_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            m = await self._get_active_match(interaction)
            if not m:
                await interaction.followup.send("❌ You currently have no active match.", ephemeral=True)
                return

            lobby_name = m.get("lobby_name")
            lobby_pass = m.get("lobby_password")
            map_name = m.get("map") or "TBD"

            if not lobby_name and not lobby_pass:
                await interaction.followup.send("🔐 Lobby information has not been published yet.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🔐 CONFIDENTIAL LOBBY INFORMATION",
                description=f"**Match ID:** `{m.get('public_match_id') or m['match_id']}`\n\n*Strictly confidential — do not share credentials outside authorized participants.*",
                color=discord.Color.from_rgb(0, 240, 255)
            )
            embed.add_field(name="Scheduled Time", value=f"`{format_dhaka_time(m.get('scheduled_time'))}`", inline=False)
            embed.add_field(name="Map / Mode", value=f"`{map_name}`", inline=True)
            embed.add_field(name="Lobby Name / ID", value=f"`{lobby_name or 'TBD'}`", inline=True)
            embed.add_field(name="Lobby Password", value=f"`{lobby_pass or 'No Password'}`", inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in lobby_info_button: {e}")
            await interaction.followup.send("❌ Unable to load lobby information right now.", ephemeral=True)

    @discord.ui.button(label="MATCH STATUS", style=discord.ButtonStyle.secondary, emoji="📊", custom_id="gen_match_center:match_status", row=1)
    async def match_status_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            m = await self._get_active_match(interaction)
            if not m:
                await interaction.followup.send("❌ You currently have no active or upcoming matches.", ephemeral=True)
                return

            status_val = m.get("status", "PENDING")
            status_icon = "🟢" if status_val == "SCHEDULED" else "🟡" if status_val == "CHECK_IN" else "🔵" if status_val == "LIVE" else "🏆" if status_val == "COMPLETED" else "🔴" if status_val == "DISPUTED" else "⚪"

            score_text = f"{m.get('score_a', 0)} - {m.get('score_b', 0)}" if status_val in ("LIVE", "COMPLETED") else "Not played yet"

            embed = discord.Embed(
                title=f"📊 MATCH STATUS — #{m.get('public_match_id') or m['match_id']}",
                color=discord.Color.blue()
            )
            embed.add_field(name="Current Status", value=f"{status_icon} `{status_val}`", inline=True)
            embed.add_field(name="Scheduled Time", value=f"`{format_dhaka_time(m.get('scheduled_time'))}`", inline=True)
            embed.add_field(name="Team A", value=f"`{m.get('team1_name', 'TBD')}`", inline=True)
            embed.add_field(name="Team B", value=f"`{m.get('team2_name', 'TBD')}`", inline=True)
            embed.add_field(name="Current Score", value=f"`{score_text}`", inline=True)
            if m.get("winner_id"):
                embed.add_field(name="Winner Team ID", value=f"`{m['winner_id']}`", inline=True)

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in match_status_button: {e}")
            await interaction.followup.send("❌ Unable to load match status right now.", ephemeral=True)

    @discord.ui.button(label="SUBMIT SCORE", style=discord.ButtonStyle.primary, emoji="📝", custom_id="gen_match_center:submit_score", row=1)
    async def submit_score_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            m = await self._get_active_match(interaction)
            match_id_str = str(m.get("public_match_id") or m.get("match_id") or "") if m else ""

            from cogs.matches import ScoreSubmissionModal
            modal = ScoreSubmissionModal()
            if match_id_str:
                modal.match_id.default = match_id_str
            await interaction.response.send_modal(modal)
        except Exception as e:
            logger.error(f"Error in submit_score_button: {e}")
            await interaction.response.send_message("❌ Error opening score submission modal.", ephemeral=True)

    @discord.ui.button(label="REFRESH", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="gen_match_center:refresh", row=1)
    async def refresh_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        try:
            m = await self._get_active_match(interaction)
            if not m:
                await interaction.followup.send("🔄 Match Center refreshed! No active match currently assigned.", ephemeral=True)
                return

            pm_id = m.get("public_match_id") or f"{m['match_id']:06d}"
            embed = discord.Embed(
                title="🔄 MATCH CENTER REFRESHED",
                description=f"Latest match data reloaded cleanly from database for **Match #{pm_id}**.",
                color=discord.Color.green()
            )
            embed.add_field(name="Status", value=f"`{m.get('status')}`", inline=True)
            embed.add_field(name="Scheduled Time", value=f"`{format_dhaka_time(m.get('scheduled_time'))}`", inline=True)
            embed.add_field(name="Matchup", value=f"`{m.get('team1_name', 'TBD')}` vs `{m.get('team2_name', 'TBD')}`", inline=False)

            await interaction.followup.send(embed=embed, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in refresh_button: {e}")
            await interaction.followup.send("❌ Error refreshing match data.", ephemeral=True)

class MatchCenterCog(commands.Cog):
    """Cog for persistent Discord Match Center panel management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup-match-center", description="[Admin] Post persistent GEN Esports Match Center panel into channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_match_center_cmd(self, interaction: discord.Interaction):
        """Admin command to post persistent Match Center panel embed."""
        embed = discord.Embed(
            title="🏆 GEN ESPORTS — MATCH CENTER",
            description="Your complete tournament match control center. Use the interactive buttons below to manage your active matches, schedule, opponent roster, room access, lobby info, and submit scores.",
            color=discord.Color.from_rgb(0, 240, 255)
        )
        embed.add_field(name="📋 MY MATCH", value="View your currently assigned active match.", inline=True)
        embed.add_field(name="🕐 SCHEDULE", value="View upcoming match times (Asia/Dhaka).", inline=True)
        embed.add_field(name="⚔️ OPPONENT", value="Inspect opponent team & captain info.", inline=True)
        embed.add_field(name="🏠 MATCH ROOM", value="Access private team match channels.", inline=True)
        embed.add_field(name="🔐 LOBBY INFO", value="Confidential lobby ID & passcode.", inline=True)
        embed.add_field(name="📊 MATCH STATUS", value="Live match status & scores.", inline=True)
        embed.add_field(name="📝 SUBMIT SCORE", value="Submit match results & evidence.", inline=True)
        embed.add_field(name="🔄 REFRESH", value="Reload match state from database.", inline=True)
        embed.set_footer(text="GEN Esports Competitive Management Engine • Persistent Panel")

        view = MatchCenterMainView()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Persistent Match Center panel posted successfully!", ephemeral=True)

    @app_commands.command(name="match-room", description="[Admin] Bind current Discord channel as Match Room and post control panel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def match_room_cmd(self, interaction: discord.Interaction):
        """Admin command to bind current channel to a database match and post Match Center UI."""
        await interaction.response.defer(ephemeral=True)
        try:
            matches = await get_uncompleted_matches()
            if not matches:
                await interaction.followup.send("❌ No active or uncompleted matches found in database.", ephemeral=True)
                return

            embed = discord.Embed(
                title="🏆 Select Match Room",
                description=f"Select the database match to bind to **#{interaction.channel.name}**:\n\n*This channel (`ID: {interaction.channel.id}`) will be saved as the official Match Room.*",
                color=discord.Color.from_rgb(0, 240, 255)
            )
            view = MatchRoomSelectView(matches)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)
        except Exception as e:
            logger.error(f"Error in match_room_cmd: {e}")
            await interaction.followup.send("❌ Error opening match room selector.", ephemeral=True)

async def setup(bot: commands.Bot):
    """Register MatchCenterCog."""
    await bot.add_cog(MatchCenterCog(bot))
