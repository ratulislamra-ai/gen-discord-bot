import os
import asyncio
import logging
import uuid
import discord
from discord import app_commands
from discord.ext import commands
from database.db import (
    create_ticket, 
    get_active_ticket, 
    close_ticket, 
    update_ticket_tournament, 
    update_ticket_team_info,
    get_ticket_by_channel,
    save_roster_players,
    get_roster_players,
    submit_ticket_registration,
    update_ticket_logo,
    set_bot_setting,
    get_bot_setting,
    get_ticket_by_id,
    update_ticket_review_message,
    approve_ticket_registration,
    reject_ticket_registration,
    get_ticket_by_review_message,
    get_open_tournaments,
    get_tournament_roster_rules,
    _get_open_tournaments_sync
)
from utils.logo_storage import save_team_logo, validate_logo_file
import config.settings as settings

logger = logging.getLogger("GENEsportsBot")

def can_user_review_registration(user_id: int, creator_id: int, is_admin: bool) -> tuple[bool, str]:
    """
    Evaluate if a Discord user is authorized to approve/reject a registration.
    - If user_id == BOT_OWNER_ID: ALWAYS ALLOWED (Bot Owner override for testing).
    - For everyone else:
      - Must have Administrator permission / Staff role.
      - Must NOT be the registration creator (user_id != creator_id).
    """
    # 1. Bot Owner Override
    if settings.BOT_OWNER_ID is not None and user_id == settings.BOT_OWNER_ID:
        return True, ""

    # 2. Administrator Permission Check
    if not is_admin:
        return False, "❌ Only authorized tournament administrators can review registrations."

    # 3. Creator Self-Review Block for Non-Owner Admins & Staff
    if int(user_id) == int(creator_id):
        return False, "❌ Registration creators cannot approve or reject their own registration."

    return True, ""

class InvitationView(discord.ui.View):
    """Persistent View attached to DMs or server panel for Accepting/Declining team invites."""
    def __init__(self, invitation_id: int):
        super().__init__(timeout=None)
        self.invitation_id = invitation_id

    @discord.ui.button(label="ACCEPT INVITE", style=discord.ButtonStyle.success, emoji="✅", custom_id="gen_inv:accept")
    async def accept_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from database.db import accept_team_invitation, get_invitation_by_id
        inv = await get_invitation_by_id(self.invitation_id)
        if not inv:
            await interaction.followup.send("❌ Invitation not found.", ephemeral=True)
            return

        ok, msg = await accept_team_invitation(self.invitation_id, str(interaction.user.id), interaction.user.display_name)
        if ok:
            embed = discord.Embed(
                title="🎉 Team Invitation Accepted!",
                description=f"You are now an official member of **{inv['team_name']}** for **{inv.get('tournament_name', 'Tournament')}**!",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)

            try:
                captain_member = interaction.guild.get_member(int(inv["invited_by_user_id"])) if interaction.guild else None
                if captain_member:
                    await captain_member.send(f"✅ **{interaction.user.display_name}** accepted your invitation to join **{inv['team_name']}**!")
            except Exception:
                pass
        else:
            await interaction.followup.send(msg, ephemeral=True)

    @discord.ui.button(label="DECLINE", style=discord.ButtonStyle.danger, emoji="❌", custom_id="gen_inv:decline")
    async def decline_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(ephemeral=True)
        from database.db import decline_team_invitation, get_invitation_by_id
        inv = await get_invitation_by_id(self.invitation_id)
        ok, msg = await decline_team_invitation(self.invitation_id, str(interaction.user.id))
        if ok:
            await interaction.followup.send("❌ You have declined the team invitation.", ephemeral=True)
            if inv:
                try:
                    captain_member = interaction.guild.get_member(int(inv["invited_by_user_id"])) if interaction.guild else None
                    if captain_member:
                        await captain_member.send(f"ℹ️ **{interaction.user.display_name}** declined your invitation to join **{inv['team_name']}**.")
                except Exception:
                    pass
        else:
            await interaction.followup.send(msg, ephemeral=True)

class AddTeamMemberSelect(discord.ui.UserSelect):
    """Native Discord UserSelect component for Team Captains to pick a teammate."""
    def __init__(self, team_id: int, tournament_id: int):
        super().__init__(
            placeholder="👤 Select a Discord member to invite...",
            min_values=1,
            max_values=1,
            custom_id="gen_team:select_member"
        )
        self.team_id = team_id
        self.tournament_id = tournament_id

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        selected_user = self.values[0]

        if selected_user.bot:
            await interaction.followup.send("❌ Bots cannot be invited to tournament teams.", ephemeral=True)
            return

        if selected_user.id == interaction.user.id:
            await interaction.followup.send("❌ You cannot invite yourself.", ephemeral=True)
            return

        from database.db import validate_player_invite_eligibility, create_team_invitation
        eligible, err_msg = await validate_player_invite_eligibility(self.tournament_id, self.team_id, str(selected_user.id))
        if not eligible:
            await interaction.followup.send(err_msg, ephemeral=True)
            return

        inv = await create_team_invitation(self.team_id, self.tournament_id, str(selected_user.id), str(interaction.user.id))
        inv_id = inv["id"] if "id" in inv else inv.get("rowid", 1)

        dm_sent = False
        try:
            embed = discord.Embed(
                title="🏆 GEN ESPORTS TEAM INVITATION",
                description=f"You have been invited by **{interaction.user.display_name}** to join roster for team **ID #{self.team_id}**!\n\nClick **ACCEPT INVITE** below to confirm.",
                color=discord.Color.gold()
            )
            embed.set_footer(text="GEN Esports Tournament Platform")
            view = InvitationView(inv_id)
            await selected_user.send(embed=embed, view=view)
            dm_sent = True
        except Exception as e:
            logger.warning(f"Could not send DM to invited player {selected_user.id}: {e}")

        if dm_sent:
            await interaction.followup.send(f"✅ Player **{selected_user.mention}** invited successfully! A DM has been sent to them.", ephemeral=True)
        else:
            await interaction.followup.send(
                f"⚠️ Invitation created for **{selected_user.mention}**, but they could not receive a Direct Message due to privacy settings.\n"
                f"They can accept the invite by running `/my-invitations` in the server.",
                ephemeral=True
            )

class ManageTeamView(discord.ui.View):
    """View containing Team Roster Management controls."""
    def __init__(self, team_id: int, tournament_id: int):
        super().__init__(timeout=None)
        self.team_id = team_id
        self.tournament_id = tournament_id
        self.add_item(AddTeamMemberSelect(team_id, tournament_id))

class CloseTicketView(discord.ui.View):
    """Persistent View attached to registration ticket channels for closing."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="gen_tournament:close_ticket"
    )
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for closing and deleting a registration ticket channel."""
        logger.info(f"[BUTTON CLICKED] 'Close Ticket' clicked by {interaction.user} (ID: {interaction.user.id}) in channel '{interaction.channel.name}' (ID: {interaction.channel.id})")
        
        await interaction.response.defer()

        # Update SQLite database
        await close_ticket(interaction.channel.id)

        embed = discord.Embed(
            title="🔒 Closing Registration Ticket",
            description=f"Ticket closed by {interaction.user.mention}.\nThis channel will be deleted in **5 seconds**...",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Registration ticket closed by {interaction.user}")
            logger.info(f"Successfully deleted ticket channel {interaction.channel.id}")
        except discord.NotFound:
            pass
        except Exception as e:
            logger.error(f"Error deleting ticket channel {interaction.channel.id}: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in CloseTicketView ({item.custom_id}): {error}", exc_info=error)

class EnterRosterView(discord.ui.View):
    """Persistent View containing [👥 Enter Roster] button."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Enter Roster",
        style=discord.ButtonStyle.success,
        emoji="👥",
        custom_id="gen_tournament:enter_roster"
    )
    async def enter_roster_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for opening RosterModalPart1."""
        logger.info(f"[BUTTON CLICKED] 'Enter Roster' clicked by {interaction.user} in channel '{interaction.channel.name}'")
        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            logger.warning(f"[PERMISSION DENIED] User {interaction.user} (ID: {interaction.user.id}) tried to click 'Enter Roster' for ticket owned by ID {ticket['user_id']}")
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        await interaction.response.send_modal(RosterModalPart1(default_p1_discord_id=str(interaction.user.id)))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in EnterRosterView ({getattr(item, 'custom_id', 'unknown')}): {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred while opening the roster form.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An error occurred while opening the roster form.", ephemeral=True)

class RosterPart2View(discord.ui.View):
    """Persistent View containing [➡️ Continue] button after Part 1."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.primary,
        emoji="➡️",
        custom_id="gen_tournament:roster_part2"
    )
    async def roster_part2_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for opening RosterModalPart2."""
        logger.info(f"[BUTTON CLICKED] 'Continue' clicked by {interaction.user} in channel '{interaction.channel.name}'")
        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        await interaction.response.send_modal(RosterModalPart2())

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in RosterPart2View ({getattr(item, 'custom_id', 'unknown')}): {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred while opening Part 2 of the roster form.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An error occurred while opening Part 2 of the roster form.", ephemeral=True)

class RosterPart3View(discord.ui.View):
    """Persistent View containing [➡️ Continue] button after Part 2."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.primary,
        emoji="➡️",
        custom_id="gen_tournament:roster_part3"
    )
    async def roster_part3_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for opening RosterModalPart3."""
        logger.info(f"[BUTTON CLICKED] 'Continue' clicked by {interaction.user} in channel '{interaction.channel.name}'")
        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        await interaction.response.send_modal(RosterModalPart3())

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in RosterPart3View ({getattr(item, 'custom_id', 'unknown')}): {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred while opening Part 3 of the roster form.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An error occurred while opening Part 3 of the roster form.", ephemeral=True)

class RosterSummaryView(discord.ui.View):
    """Persistent View containing [✏️ Edit Roster] and [➡️ Continue to Confirmation] buttons."""
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Edit Roster",
        style=discord.ButtonStyle.secondary,
        emoji="✏️",
        custom_id="gen_tournament:edit_roster",
        row=0
    )
    async def edit_roster_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for editing the roster from Part 1."""
        logger.info(f"[BUTTON CLICKED] 'Edit Roster' clicked by {interaction.user} in channel '{interaction.channel.name}'")
        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        await interaction.response.send_modal(RosterModalPart1(default_p1_discord_id=str(interaction.user.id)))

    @discord.ui.button(
        label="Continue to Confirmation",
        style=discord.ButtonStyle.primary,
        emoji="➡️",
        custom_id="gen_tournament:continue_confirmation",
        row=0
    )
    async def continue_confirmation_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for continuing to final registration review."""
        logger.info(f"[BUTTON CLICKED] 'Continue to Confirmation' clicked by {interaction.user} in channel '{interaction.channel.name}'")
        
        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        # Validate completeness before proceeding to review
        if not ticket["tournament_name"]:
            await interaction.response.send_message("⚠️ Please select a tournament before proceeding to confirmation.", ephemeral=True)
            return

        if not ticket["team_name"] or not ticket["captain_name"] or not ticket["captain_discord_id"] or not ticket["captain_phone"]:
            await interaction.response.send_message("⚠️ Please complete your Team Information before proceeding to confirmation.", ephemeral=True)
            return

        roster = await get_roster_players(ticket["ticket_id"])
        if len(roster) < 6:
            await interaction.response.send_message("⚠️ Please complete your Team Roster (5 starters + 1 substitute) before proceeding to confirmation.", ephemeral=True)
            return

        await interaction.response.defer()

        review_embed, logo_file = build_registration_review_embed(ticket, roster)
        if logo_file:
            await interaction.followup.send(embed=review_embed, file=logo_file, view=RegistrationReviewView())
        else:
            await interaction.followup.send(embed=review_embed, view=RegistrationReviewView())

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in RosterSummaryView ({getattr(item, 'custom_id', 'unknown')}): {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred while processing your request.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An error occurred while processing your request.", ephemeral=True)

def build_registration_review_embed(ticket: dict, roster: list) -> tuple[discord.Embed, discord.File | None]:
    """Build the clean, professional Registration Review embed and logo file if present."""
    roster_map = {p["player_role"]: p for p in roster}
    role_labels = [
        ("Player 1", "Player 1"),
        ("Player 2", "Player 2"),
        ("Player 3", "Player 3"),
        ("Player 4", "Player 4"),
        ("Player 5", "Player 5"),
        ("Substitute 1", "Substitute")
    ]

    roster_lines = []
    for role_key, label in role_labels:
        p_data = roster_map.get(role_key, {"ign": "N/A", "discord_id": "N/A"})
        roster_lines.append(f"**{label}:**\nIGN: {p_data['ign']}\nDiscord: {p_data['discord_id']}\n")

    roster_formatted = "\n".join(roster_lines)
    tournament_name = ticket["tournament_name"] if ticket["tournament_name"] else "N/A"
    team_name = ticket["team_name"] if ticket["team_name"] else "N/A"
    captain_name = ticket["captain_name"] if ticket["captain_name"] else "N/A"
    captain_discord_id = ticket["captain_discord_id"] if ticket["captain_discord_id"] else "N/A"
    captain_phone = ticket["captain_phone"] if ticket["captain_phone"] else "N/A"
    team_logo_status = "Uploaded ✅" if ticket.get("team_logo_url") else "Not Uploaded (Optional) ❌"

    review_text = (
        f"**Tournament:**\n{tournament_name}\n\n"
        "**TEAM INFORMATION**\n"
        f"Team Name: {team_name}\n"
        f"Captain Name: {captain_name}\n"
        f"Captain Discord ID: {captain_discord_id}\n"
        f"Captain Phone: {captain_phone}\n"
        f"Team Logo: {team_logo_status}\n\n"
        "**ROSTER**\n"
        f"{roster_formatted}\n"
        "**STATUS:**\n"
        "🟡 Ready for Submission"
    )

    embed = discord.Embed(
        title="🏆 TOURNAMENT REGISTRATION REVIEW",
        description=review_text,
        color=discord.Color.from_rgb(0, 255, 163)
    )
    embed.set_footer(text="GEN Esports Tournament System • Stage 6 Final Review")

    logo_file = None
    logo_path = ticket.get("team_logo_url")
    if logo_path:
        if logo_path.startswith("http://") or logo_path.startswith("https://"):
            embed.set_thumbnail(url=logo_path)
        elif os.path.exists(logo_path):
            logo_file = discord.File(logo_path, filename="team_logo.png")
            embed.set_thumbnail(url="attachment://team_logo.png")

    return embed, logo_file

def build_admin_review_embed(ticket: dict, roster: list, status_text: str = "🟡 PENDING", reason: str = "") -> tuple[discord.Embed, discord.File | None]:
    """Build the clean, professional Admin Registration Review embed."""
    roster_map = {p["player_role"]: p for p in roster}
    role_labels = [
        ("Player 1", "Player 1"),
        ("Player 2", "Player 2"),
        ("Player 3", "Player 3"),
        ("Player 4", "Player 4"),
        ("Player 5", "Player 5"),
        ("Substitute 1", "Substitute")
    ]

    roster_lines = []
    for role_key, label in role_labels:
        p_data = roster_map.get(role_key, {"ign": "N/A", "discord_id": "N/A"})
        roster_lines.append(f"• **{label}:** IGN: `{p_data['ign']}` | Discord: <@{p_data['discord_id']}> (`{p_data['discord_id']}`)")

    roster_formatted = "\n".join(roster_lines)
    tournament_name = ticket["tournament_name"] if ticket["tournament_name"] else "N/A"
    team_name = ticket["team_name"] if ticket["team_name"] else "N/A"
    captain_name = ticket["captain_name"] if ticket["captain_name"] else "N/A"
    captain_discord_id = ticket["captain_discord_id"] if ticket["captain_discord_id"] else "N/A"
    captain_phone = ticket["captain_phone"] if ticket["captain_phone"] else "N/A"
    reg_code = ticket["registration_code"] if ticket.get("registration_code") else f"GEN-{ticket['ticket_id']:06d}"

    review_description = (
        f"🏆 **Registration ID:** `{reg_code}`\n"
        f"🎮 **Tournament:** {tournament_name}\n\n"
        "👥 **TEAM INFORMATION**\n"
        f"🛡️ **Team Name:** {team_name}\n"
        f"👑 **Captain Name:** {captain_name}\n"
        f"🆔 **Captain Discord ID:** <@{captain_discord_id}> (`{captain_discord_id}`)\n"
        f"📞 **Captain Phone:** `{captain_phone}`\n\n"
        "📋 **ROSTER**\n"
        f"{roster_formatted}\n\n"
        f"📌 **Status:**\n{status_text}"
    )

    if reason:
        review_description += f"\n\n❌ **Rejection Reason:**\n{reason}"

    embed = discord.Embed(
        title="🏆 TOURNAMENT REGISTRATION REVIEW",
        description=review_description,
        color=discord.Color.from_rgb(0, 255, 163) if "APPROVED" in status_text else (discord.Color.red() if "REJECTED" in status_text else discord.Color.gold())
    )
    embed.set_footer(text="GEN Esports Admin System • Registration Review")

    logo_file = None
    logo_path = ticket.get("team_logo_url")
    if logo_path:
        if logo_path.startswith("http://") or logo_path.startswith("https://"):
            embed.set_thumbnail(url=logo_path)
        elif os.path.exists(logo_path):
            logo_file = discord.File(logo_path, filename="team_logo.png")
            embed.set_thumbnail(url="attachment://team_logo.png")

    return embed, logo_file

class RejectReasonModal(discord.ui.Modal, title="Reject Registration"):
    """Modal for capturing rejection reason from admin."""
    reason = discord.ui.TextInput(
        label="Rejection Reason",
        style=discord.TextStyle.paragraph,
        placeholder="Explain why this registration is being rejected...",
        required=True,
        min_length=3,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        reason_val = self.reason.value.strip()
        if not reason_val:
            await interaction.response.send_message("❌ Rejection reason cannot be empty.", ephemeral=True)
            return

        ticket = await get_ticket_by_review_message(interaction.message.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate the registration record for this review message.", ephemeral=True)
            return

        if ticket["status"] != "PENDING":
            await interaction.response.send_message("⚠️ This registration has already been processed.", ephemeral=True)
            return

        is_admin = interaction.user.guild_permissions.administrator if hasattr(interaction.user, "guild_permissions") else False
        can_review, err_msg = can_user_review_registration(interaction.user.id, ticket["user_id"], is_admin)
        if not can_review:
            await interaction.response.send_message(err_msg, ephemeral=True)
            return

        await interaction.response.defer()

        success = await reject_ticket_registration(ticket["ticket_id"], str(interaction.user.id), reason_val)
        if not success:
            await interaction.followup.send("❌ Failed to update registration status in database.", ephemeral=True)
            return

        logger.info(f"[REGISTRATION REJECTED] Ticket #{ticket['ticket_id']} rejected by admin {interaction.user} (ID: {interaction.user.id}). Reason: {reason_val}")

        view = AdminReviewView()
        for child in view.children:
            child.disabled = True

        roster = await get_roster_players(ticket["ticket_id"])
        updated_embed, logo_file = build_admin_review_embed(ticket, roster, status_text=f"🔴 REJECTED (Rejected by {interaction.user.mention})", reason=reason_val)

        try:
            if logo_file:
                await interaction.message.edit(embed=updated_embed, attachments=[logo_file], view=view)
            else:
                await interaction.message.edit(embed=updated_embed, view=view)
        except Exception as e:
            logger.error(f"Error editing review message on rejection: {e}")

        # Notify user in ticket channel
        ticket_channel = interaction.guild.get_channel(ticket["channel_id"])
        if ticket_channel:
            try:
                reject_embed = discord.Embed(
                    title="❌ REGISTRATION REJECTED",
                    description=(
                        f"Your tournament registration (ID: `{ticket['registration_code']}`) has been **REJECTED**.\n\n"
                        f"**Rejection Reason:**\n{reason_val}\n\n"
                        "If you have questions, please contact tournament staff in this channel."
                    ),
                    color=discord.Color.red()
                )
                await ticket_channel.send(embed=reject_embed)
            except Exception as e:
                logger.error(f"Error notifying ticket channel of rejection: {e}")

        # DM user if possible
        try:
            captain_user = await interaction.client.fetch_user(ticket["user_id"])
            if captain_user:
                dm_embed = discord.Embed(
                    title="❌ Tournament Registration Rejected",
                    description=(
                        f"Your registration for **{ticket['tournament_name']}** (Registration ID: `{ticket['registration_code']}`) has been **REJECTED**.\n\n"
                        f"**Reason:**\n{reason_val}"
                    ),
                    color=discord.Color.red()
                )
                await captain_user.send(embed=dm_embed)
        except Exception as e:
            logger.warning(f"Could not send rejection DM to user {ticket['user_id']}: {e}")

        await interaction.followup.send("✅ Registration rejected and notifications sent.", ephemeral=True)

class AdminReviewView(discord.ui.View):
    """Persistent View attached to Admin Review messages in registration-review channel."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="APPROVE",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="gen_tournament:admin_approve",
        row=0
    )
    async def approve_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for approving registration."""
        logger.info(f"[BUTTON CLICKED] 'APPROVE' clicked by {interaction.user} in channel '{interaction.channel.name}'")

        ticket = await get_ticket_by_review_message(interaction.message.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate registration record for this review message.", ephemeral=True)
            return

        if ticket["status"] != "PENDING":
            await interaction.response.send_message("⚠️ This registration has already been processed.", ephemeral=True)
            return

        is_admin = interaction.user.guild_permissions.administrator if hasattr(interaction.user, "guild_permissions") else False
        can_review, err_msg = can_user_review_registration(interaction.user.id, ticket["user_id"], is_admin)
        if not can_review:
            await interaction.response.send_message(err_msg, ephemeral=True)
            return

        await interaction.response.defer()

        success = await approve_ticket_registration(ticket["ticket_id"], str(interaction.user.id))
        if not success:
            await interaction.followup.send("❌ Failed to update registration status in database.", ephemeral=True)
            return

        logger.info(f"[REGISTRATION APPROVED] Ticket #{ticket['ticket_id']} approved by admin {interaction.user} (ID: {interaction.user.id})")

        for child in self.children:
            child.disabled = True

        roster = await get_roster_players(ticket["ticket_id"])
        updated_embed, logo_file = build_admin_review_embed(ticket, roster, status_text=f"🟢 APPROVED (Approved by {interaction.user.mention})")

        try:
            if logo_file:
                await interaction.message.edit(embed=updated_embed, attachments=[logo_file], view=self)
            else:
                await interaction.message.edit(embed=updated_embed, view=self)
        except Exception as e:
            logger.error(f"Error editing review message on approval: {e}")

        # Notify in ticket channel
        ticket_channel = interaction.guild.get_channel(ticket["channel_id"])
        if ticket_channel:
            try:
                approve_embed = discord.Embed(
                    title="🎉 REGISTRATION APPROVED!",
                    description=(
                        f"🎉 **Congratulations! Your registration has been approved!**\n\n"
                        f"**Registration ID:** `{ticket['registration_code']}`\n"
                        f"**Tournament:** {ticket['tournament_name']}\n"
                        f"**Team Name:** {ticket['team_name']}\n\n"
                        "Your team is officially registered for the tournament!"
                    ),
                    color=discord.Color.from_rgb(0, 255, 163)
                )
                await ticket_channel.send(embed=approve_embed)
            except Exception as e:
                logger.error(f"Error notifying ticket channel of approval: {e}")

        # DM Captain if possible
        try:
            captain_user = await interaction.client.fetch_user(ticket["user_id"])
            if captain_user:
                dm_embed = discord.Embed(
                    title="✅ REGISTRATION CONFIRMED",
                    description=(
                        f"Your registration for:\n\n"
                        f"🏆 **{ticket['tournament_name']}**\n\n"
                        f"has been confirmed.\n\n"
                        f"**Team:** {ticket['team_name']}\n"
                        f"**Registration Code:** `{ticket['registration_code']}`\n\n"
                        f"You can check your registration status here:\n"
                        f"🌐 https://genesports.online/"
                    ),
                    color=discord.Color.from_rgb(0, 255, 163)
                )
                dm_embed.set_footer(text="GEN Esports Official Platform")
                await captain_user.send(embed=dm_embed)
        except Exception as e:
            logger.warning(f"Could not send approval DM to user {ticket['user_id']}: {e}")

        await interaction.followup.send("✅ Registration approved successfully!", ephemeral=True)

    @discord.ui.button(
        label="REJECT",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="gen_tournament:admin_reject",
        row=0
    )
    async def reject_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for rejecting registration."""
        logger.info(f"[BUTTON CLICKED] 'REJECT' clicked by {interaction.user} in channel '{interaction.channel.name}'")

        ticket = await get_ticket_by_review_message(interaction.message.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate registration record for this review message.", ephemeral=True)
            return

        if ticket["status"] != "PENDING":
            await interaction.response.send_message("⚠️ This registration has already been processed.", ephemeral=True)
            return

        is_admin = interaction.user.guild_permissions.administrator if hasattr(interaction.user, "guild_permissions") else False
        can_review, err_msg = can_user_review_registration(interaction.user.id, ticket["user_id"], is_admin)
        if not can_review:
            await interaction.response.send_message(err_msg, ephemeral=True)
            return

        await interaction.response.send_modal(RejectReasonModal())

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in AdminReviewView ({getattr(item, 'custom_id', 'unknown')}): {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred while processing admin review.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An error occurred while processing admin review.", ephemeral=True)

class RegistrationReviewView(discord.ui.View):
    """Persistent View for final registration review and submission."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Edit Team Info",
        style=discord.ButtonStyle.secondary,
        emoji="✏️",
        custom_id="gen_tournament:edit_team",
        row=0
    )
    async def edit_team_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for editing team details from review screen."""
        logger.info(f"[BUTTON CLICKED] 'Edit Team Info' clicked by {interaction.user} in channel '{interaction.channel.name}'")
        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        default_id = ticket["captain_discord_id"] if ticket["captain_discord_id"] else str(interaction.user.id)
        await interaction.response.send_modal(TeamInfoModal(default_discord_id=default_id))

    @discord.ui.button(
        label="Edit Roster",
        style=discord.ButtonStyle.secondary,
        emoji="✏️",
        custom_id="gen_tournament:edit_roster",
        row=0
    )
    async def edit_roster_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for editing roster details from review screen."""
        logger.info(f"[BUTTON CLICKED] 'Edit Roster' clicked by {interaction.user} in channel '{interaction.channel.name}'")
        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        await interaction.response.send_modal(RosterModalPart1(default_p1_discord_id=str(interaction.user.id)))

    @discord.ui.button(
        label="Submit Registration",
        style=discord.ButtonStyle.success,
        emoji="✅",
        custom_id="gen_tournament:submit_registration",
        row=1
    )
    async def submit_registration_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for submitting final tournament registration."""
        logger.info(f"[BUTTON CLICKED] 'Submit Registration' clicked by {interaction.user} in channel '{interaction.channel.name}'")

        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            logger.warning(f"[PERMISSION DENIED] User {interaction.user} (ID: {interaction.user.id}) tried to submit registration owned by ID {ticket['user_id']}")
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        if ticket["status"] != "OPEN":
            await interaction.response.send_message("⚠️ This registration has already been submitted or closed.", ephemeral=True)
            return

        # Validate completeness before submitting
        if not ticket["tournament_name"]:
            await interaction.response.send_message("⚠️ Tournament selection is incomplete. Please select a tournament.", ephemeral=True)
            return

        if not ticket["team_name"] or not ticket["captain_name"] or not ticket["captain_discord_id"] or not ticket["captain_phone"]:
            await interaction.response.send_message("⚠️ Team Information is incomplete. Please complete your Team Information.", ephemeral=True)
            return

        roster = await get_roster_players(ticket["ticket_id"])
        if len(roster) < 6:
            await interaction.response.send_message("⚠️ Team Roster is incomplete. Please ensure all 5 starting players and 1 substitute are entered.", ephemeral=True)
            return

        await interaction.response.defer()

        # Generate unique registration ID (e.g. GEN-XXXXXX)
        code_suffix = uuid.uuid4().hex[:6].upper()
        reg_code = f"GEN-{code_suffix}"

        # Submit in SQLite
        success = await submit_ticket_registration(interaction.channel.id, reg_code)
        if not success:
            logger.error(f"[SUBMIT FAILED] Failed to update ticket status for channel {interaction.channel.id}")
            await interaction.followup.send("❌ Failed to record your registration. Please try again.", ephemeral=True)
            return

        logger.info(f"[REGISTRATION SUBMITTED] Ticket #{ticket['ticket_id']} submitted successfully with Registration ID '{reg_code}'")

        # Disable all buttons on the review message
        for child in self.children:
            child.disabled = True

        try:
            await interaction.message.edit(view=self)
        except Exception as e:
            logger.error(f"Failed to edit review message buttons: {e}")

        # Post clean final submission embed as requested
        submission_embed = discord.Embed(
            title="✅ REGISTRATION SUBMITTED",
            description=(
                f"**Registration ID:** `{reg_code}`\n"
                "**Status:** 🟡 Pending Approval\n\n"
                "Your registration has been submitted successfully.\n"
                "Tournament staff will review your registration."
            ),
            color=discord.Color.from_rgb(0, 255, 163)
        )
        submission_embed.set_footer(text="GEN Esports Tournament System • Registration Submitted")

        logo_path = ticket.get("team_logo_url")
        logo_file = None
        if logo_path:
            if logo_path.startswith("http://") or logo_path.startswith("https://"):
                submission_embed.set_thumbnail(url=logo_path)
            elif os.path.exists(logo_path):
                logo_file = discord.File(logo_path, filename="team_logo.png")
                submission_embed.set_thumbnail(url="attachment://team_logo.png")

        if logo_file:
            await interaction.followup.send(embed=submission_embed, file=logo_file)
        else:
            await interaction.followup.send(embed=submission_embed)

        # Step 7: Automatically post to configured admin review channel
        logger.info(f"[ADMIN REVIEW] Final submission received for Ticket #{ticket['ticket_id']} (Code: {reg_code}) by {interaction.user} (ID: {interaction.user.id})")

        admin_channel_id_str = await get_bot_setting("admin_channel_id")
        if not admin_channel_id_str:
            admin_channel_id_str = await get_bot_setting("review_channel_id")

        if not admin_channel_id_str or not admin_channel_id_str.isdigit():
            logger.error(f"[ADMIN REVIEW ERROR] ❌ Admin review channel has not been configured. An administrator must run /setup_admin in the desired admin channel.")
            await interaction.followup.send(
                "⚠️ **Admin review channel has not been configured.**\n"
                "An administrator must run `/setup_admin` in the desired admin channel to receive registration review messages.",
                ephemeral=True
            )
            return

        admin_channel_id = int(admin_channel_id_str)
        review_channel = interaction.guild.get_channel(admin_channel_id) if interaction.guild else None
        if not review_channel and interaction.client:
            try:
                review_channel = await interaction.client.fetch_channel(admin_channel_id)
            except Exception as fe:
                logger.warning(f"[ADMIN REVIEW WARNING] Configured admin channel ID {admin_channel_id} could not be fetched: {fe}")

        if not review_channel:
            logger.error(f"[ADMIN REVIEW ERROR] ❌ Configured admin channel (ID: {admin_channel_id}) was not found in guild '{interaction.guild.name if interaction.guild else 'Unknown'}'. Run /setup_admin in your admin channel.")
            await interaction.followup.send(
                f"⚠️ **Configured admin review channel (ID: `{admin_channel_id}`) was not found.**\n"
                "Please ask an administrator to run `/setup_admin` in the desired admin channel.",
                ephemeral=True
            )
            return

        logger.info(f"[ADMIN REVIEW] Sending registration to configured admin channel...")
        logger.info(f"[ADMIN REVIEW] Channel: #{review_channel.name} (ID: {review_channel.id})")

        # Check Bot Permissions
        bot_member = interaction.guild.me if interaction.guild else None
        perms = review_channel.permissions_for(bot_member) if bot_member else None
        missing_perms = []
        if perms:
            if not perms.view_channel: missing_perms.append("View Channel")
            if not perms.send_messages: missing_perms.append("Send Messages")
            if not perms.embed_links: missing_perms.append("Embed Links")
            if not perms.attach_files: missing_perms.append("Attach Files")

        if missing_perms:
            logger.error(f"[ADMIN REVIEW PERMISSION ERROR] ❌ Bot lacks required permissions in #{review_channel.name} (ID: {review_channel.id}): {', '.join(missing_perms)}")
            await interaction.followup.send(
                f"⚠️ **Bot lacks permissions ({', '.join(missing_perms)}) in {review_channel.mention}.** Please grant permissions to the bot.",
                ephemeral=True
            )
            return

        admin_ticket = await get_ticket_by_channel(interaction.channel.id)
        admin_embed, admin_logo_file = build_admin_review_embed(admin_ticket, roster, status_text="🟡 PENDING")
        try:
            if admin_logo_file:
                review_msg = await review_channel.send(embed=admin_embed, file=admin_logo_file, view=AdminReviewView())
            else:
                review_msg = await review_channel.send(embed=admin_embed, view=AdminReviewView())

            await update_ticket_review_message(admin_ticket["ticket_id"], review_channel.id, review_msg.id)
            logger.info(f"[ADMIN REVIEW] Review message sent: {review_msg.id}")
        except discord.Forbidden as e:
            logger.error(f"[ADMIN REVIEW ERROR] ❌ discord.Forbidden error posting to #{review_channel.name}: {e}", exc_info=e)
        except discord.NotFound as e:
            logger.error(f"[ADMIN REVIEW ERROR] ❌ discord.NotFound error posting to #{review_channel.name}: {e}", exc_info=e)
        except discord.HTTPException as e:
            logger.error(f"[ADMIN REVIEW ERROR] ❌ discord.HTTPException posting to #{review_channel.name}: {e}", exc_info=e)
        except Exception as e:
            logger.error(f"[ADMIN REVIEW ERROR] ❌ Unexpected error posting admin review embed: {e}", exc_info=e)

    @discord.ui.button(
        label="Cancel",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="gen_tournament:close_ticket",
        row=1
    )
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for cancelling registration ticket."""
        logger.info(f"[BUTTON CLICKED] 'Cancel' clicked by {interaction.user} in channel '{interaction.channel.name}'")
        await interaction.response.defer()
        await close_ticket(interaction.channel.id)

        embed = discord.Embed(
            title="🔒 Closing Registration Ticket",
            description=f"Ticket cancelled and closed by {interaction.user.mention}.\nThis channel will be deleted in **5 seconds**...",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)

        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Registration ticket cancelled by {interaction.user}")
        except Exception as e:
            logger.error(f"Error deleting ticket channel: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in RegistrationReviewView ({getattr(item, 'custom_id', 'unknown')}): {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred while processing your request.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An error occurred while processing your request.", ephemeral=True)

class RosterModalPart1(discord.ui.Modal, title="Roster Entry - Part 1 (Players 1 & 2)"):
    """Discord Modal for collecting Player 1 and Player 2 details."""
    p1_ign = discord.ui.TextInput(label="Player 1 IGN", placeholder="Enter Player 1 In-Game Name", required=True, min_length=1, max_length=100)
    p1_discord_id = discord.ui.TextInput(label="Player 1 Discord ID", placeholder="Enter Player 1 Discord ID", required=True, min_length=1, max_length=50)
    p2_ign = discord.ui.TextInput(label="Player 2 IGN", placeholder="Enter Player 2 In-Game Name", required=True, min_length=1, max_length=100)
    p2_discord_id = discord.ui.TextInput(label="Player 2 Discord ID", placeholder="Enter Player 2 Discord ID", required=True, min_length=1, max_length=50)

    def __init__(self, default_p1_discord_id: str = ""):
        super().__init__(title="Roster Entry - Part 1 (Players 1 & 2)")
        if default_p1_discord_id:
            self.p1_discord_id.default = str(default_p1_discord_id)

    async def on_submit(self, interaction: discord.Interaction):
        logger.info(f"[MODAL SUBMIT] RosterModalPart1 by {interaction.user} in channel {interaction.channel.id}")

        p1_ign_v = self.p1_ign.value.strip()
        p1_discord_v = self.p1_discord_id.value.strip()
        p2_ign_v = self.p2_ign.value.strip()
        p2_discord_v = self.p2_discord_id.value.strip()

        if not p1_ign_v or not p1_discord_v or not p2_ign_v or not p2_discord_v:
            await interaction.response.send_message("❌ All fields in Part 1 are required. Please provide valid non-empty values.", ephemeral=True)
            return

        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Registration ticket record not found for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can submit roster details.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        players = [
            {"player_role": "Player 1", "ign": p1_ign_v, "discord_id": p1_discord_v},
            {"player_role": "Player 2", "ign": p2_ign_v, "discord_id": p2_discord_v}
        ]

        await save_roster_players(ticket["ticket_id"], players)

        # Ephemeral intermediate response with Continue button
        await interaction.followup.send(
            "✅ Players 1–2 saved.\n\nClick **➡️ Continue** to enter Players 3 & 4.",
            view=RosterPart2View(),
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"[MODAL ERROR] Exception in RosterModalPart1: {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An unexpected error occurred while saving Roster Part 1.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An unexpected error occurred while saving Roster Part 1.", ephemeral=True)

class RosterModalPart2(discord.ui.Modal, title="Roster Entry - Part 2 (Players 3 & 4)"):
    """Discord Modal for collecting Player 3 and Player 4 details."""
    p3_ign = discord.ui.TextInput(label="Player 3 IGN", placeholder="Enter Player 3 In-Game Name", required=True, min_length=1, max_length=100)
    p3_discord_id = discord.ui.TextInput(label="Player 3 Discord ID", placeholder="Enter Player 3 Discord ID", required=True, min_length=1, max_length=50)
    p4_ign = discord.ui.TextInput(label="Player 4 IGN", placeholder="Enter Player 4 In-Game Name", required=True, min_length=1, max_length=100)
    p4_discord_id = discord.ui.TextInput(label="Player 4 Discord ID", placeholder="Enter Player 4 Discord ID", required=True, min_length=1, max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        logger.info(f"[MODAL SUBMIT] RosterModalPart2 by {interaction.user} in channel {interaction.channel.id}")

        p3_ign_v = self.p3_ign.value.strip()
        p3_discord_v = self.p3_discord_id.value.strip()
        p4_ign_v = self.p4_ign.value.strip()
        p4_discord_v = self.p4_discord_id.value.strip()

        if not p3_ign_v or not p3_discord_v or not p4_ign_v or not p4_discord_v:
            await interaction.response.send_message("❌ All fields in Part 2 are required. Please provide valid non-empty values.", ephemeral=True)
            return

        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Registration ticket record not found for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can submit roster details.", ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True)

        players = [
            {"player_role": "Player 3", "ign": p3_ign_v, "discord_id": p3_discord_v},
            {"player_role": "Player 4", "ign": p4_ign_v, "discord_id": p4_discord_v}
        ]

        await save_roster_players(ticket["ticket_id"], players)

        # Ephemeral intermediate response with Continue button
        await interaction.followup.send(
            "✅ Players 3–4 saved.\n\nClick **➡️ Continue** to enter Player 5 & Substitute.",
            view=RosterPart3View(),
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"[MODAL ERROR] Exception in RosterModalPart2: {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An unexpected error occurred while saving Roster Part 2.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An unexpected error occurred while saving Roster Part 2.", ephemeral=True)

class RosterModalPart3(discord.ui.Modal, title="Roster Entry - Part 3 (Player 5 & Sub)"):
    """Discord Modal for collecting Player 5 and Substitute details."""
    p5_ign = discord.ui.TextInput(label="Player 5 IGN", placeholder="Enter Player 5 In-Game Name", required=True, min_length=1, max_length=100)
    p5_discord_id = discord.ui.TextInput(label="Player 5 Discord ID", placeholder="Enter Player 5 Discord ID", required=True, min_length=1, max_length=50)
    sub1_ign = discord.ui.TextInput(label="Substitute 1 IGN", placeholder="Enter Substitute 1 In-Game Name", required=True, min_length=1, max_length=100)
    sub1_discord_id = discord.ui.TextInput(label="Substitute 1 Discord ID", placeholder="Enter Substitute 1 Discord ID", required=True, min_length=1, max_length=50)

    async def on_submit(self, interaction: discord.Interaction):
        logger.info(f"[MODAL SUBMIT] RosterModalPart3 by {interaction.user} in channel {interaction.channel.id}")

        p5_ign_v = self.p5_ign.value.strip()
        p5_discord_v = self.p5_discord_id.value.strip()
        sub1_ign_v = self.sub1_ign.value.strip()
        sub1_discord_v = self.sub1_discord_id.value.strip()

        if not p5_ign_v or not p5_discord_v or not sub1_ign_v or not sub1_discord_v:
            await interaction.response.send_message("❌ All fields in Part 3 are required. Please provide valid non-empty values.", ephemeral=True)
            return

        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Registration ticket record not found for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can submit roster details.", ephemeral=True)
            return

        await interaction.response.defer()

        players = [
            {"player_role": "Player 5", "ign": p5_ign_v, "discord_id": p5_discord_v},
            {"player_role": "Substitute 1", "ign": sub1_ign_v, "discord_id": sub1_discord_v}
        ]

        await save_roster_players(ticket["ticket_id"], players)

        # Fetch complete roster from SQLite
        all_players = await get_roster_players(ticket["ticket_id"])
        roster_map = {p["player_role"]: p for p in all_players}

        role_labels = [
            ("Player 1", "Player 1"),
            ("Player 2", "Player 2"),
            ("Player 3", "Player 3"),
            ("Player 4", "Player 4"),
            ("Player 5", "Player 5"),
            ("Substitute 1", "Substitute")
        ]

        summary_lines = []
        for role_key, label in role_labels:
            p_data = roster_map.get(role_key, {"ign": "N/A", "discord_id": "N/A"})
            summary_lines.append(f"**{label}**\nIGN: {p_data['ign']}\nDiscord: {p_data['discord_id']}\n")

        roster_text = "\n".join(summary_lines)

        summary_embed = discord.Embed(
            title="👥 TEAM ROSTER",
            description=roster_text,
            color=discord.Color.from_rgb(0, 255, 163)
        )
        summary_embed.set_footer(text="GEN Esports Tournament System • Stage 5 Complete")

        await interaction.followup.send(embed=summary_embed, view=RosterSummaryView())

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"[MODAL ERROR] Exception in RosterModalPart3: {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An unexpected error occurred while saving Roster Part 3.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An unexpected error occurred while saving Roster Part 3.", ephemeral=True)

class ContinueToRosterView(discord.ui.View):
    """Persistent View for transitioning to roster after team information submission."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Continue to Roster",
        style=discord.ButtonStyle.primary,
        emoji="➡️",
        custom_id="gen_tournament:continue_roster"
    )
    async def continue_roster_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for continuing to roster submission."""
        logger.info(f"[BUTTON CLICKED] 'Continue to Roster' clicked by {interaction.user} in channel '{interaction.channel.name}'")
        await interaction.response.defer(ephemeral=True)

        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.followup.send("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            logger.warning(f"[PERMISSION DENIED] User {interaction.user} (ID: {interaction.user.id}) tried to click 'Continue to Roster' for ticket owned by ID {ticket['user_id']}")
            await interaction.followup.send(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        embed = discord.Embed(
            title="👥 TEAM ROSTER",
            description=(
                "Required roster:\n"
                "• Player 1\n"
                "• Player 2\n"
                "• Player 3\n"
                "• Player 4\n"
                "• Player 5\n"
                "• Substitute"
            ),
            color=discord.Color.from_rgb(0, 255, 163)
        )
        embed.set_footer(text="GEN Esports Tournament System • Stage 5 Roster Setup")

        await interaction.channel.send(embed=embed, view=EnterRosterView())
        await interaction.followup.send("✅ Roster registration opened below.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in ContinueToRosterView ({getattr(item, 'custom_id', 'unknown')}): {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred while processing your request.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An error occurred while processing your request.", ephemeral=True)

class TeamInfoModal(discord.ui.Modal, title="Team Information"):
    """Discord Modal for collecting team name, captain name, captain discord ID, and phone number."""

    team_name = discord.ui.TextInput(
        label="Team Name",
        placeholder="Enter your official team name",
        required=True,
        min_length=1,
        max_length=100
    )
    captain_name = discord.ui.TextInput(
        label="Team Captain Name",
        placeholder="Enter captain's full name",
        required=True,
        min_length=1,
        max_length=100
    )
    captain_discord_id = discord.ui.TextInput(
        label="Team Captain Discord ID",
        placeholder="Enter captain's Discord User ID",
        required=True,
        min_length=1,
        max_length=50
    )
    captain_phone = discord.ui.TextInput(
        label="Captain Phone Number",
        placeholder="Enter captain's contact phone number",
        required=True,
        min_length=1,
        max_length=30
    )

    def __init__(self, default_discord_id: str = ""):
        super().__init__(title="Team Information")
        if default_discord_id:
            self.captain_discord_id.default = str(default_discord_id)

    async def on_submit(self, interaction: discord.Interaction):
        """Handler called when user submits the team information modal."""
        logger.info(f"[MODAL SUBMIT] TeamInfoModal submitted by {interaction.user} (ID: {interaction.user.id}) in channel {interaction.channel.id}")

        # Non-empty validation after stripping whitespace
        team_name_val = self.team_name.value.strip()
        captain_name_val = self.captain_name.value.strip()
        captain_discord_id_val = self.captain_discord_id.value.strip()
        captain_phone_val = self.captain_phone.value.strip()

        if not team_name_val or not captain_name_val or not captain_discord_id_val or not captain_phone_val:
            logger.warning(f"[VALIDATION FAILED] Empty or whitespace-only field submitted by {interaction.user}")
            await interaction.response.send_message(
                "❌ All fields are required. Please provide valid non-empty values for Team Name, Captain Name, Captain Discord ID, and Phone Number.",
                ephemeral=True
            )
            return

        # Fetch active ticket record
        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            logger.error(f"[MODAL ERROR] No active ticket found for channel {interaction.channel.id}")
            await interaction.response.send_message("❌ Registration ticket record not found for this channel.", ephemeral=True)
            return

        # Authorization check: only ticket creator can submit
        if ticket["user_id"] != interaction.user.id:
            logger.warning(f"[PERMISSION DENIED] User {interaction.user} (ID: {interaction.user.id}) attempted to submit TeamInfoModal for ticket owned by ID {ticket['user_id']}")
            await interaction.response.send_message(
                f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can submit team information.",
                ephemeral=True
            )
            return

        # Defer response before DB operations to prevent interaction timeout
        await interaction.response.defer()

        # Update SQLite database record
        success = await update_ticket_team_info(
            channel_id=interaction.channel.id,
            team_name=team_name_val,
            captain_name=captain_name_val,
            captain_discord_id=captain_discord_id_val,
            captain_phone=captain_phone_val
        )

        if not success:
            logger.error(f"[DB UPDATE FAILED] Could not update team info for ticket channel {interaction.channel.id}")
            await interaction.followup.send("❌ Failed to save team information to the database. Please try again.", ephemeral=True)
            return

        logger.info(f"[TEAM INFO SAVED] Ticket #{ticket['ticket_id']} updated with Team: '{team_name_val}', Captain: '{captain_name_val}', Discord ID: '{captain_discord_id_val}', Phone: '{captain_phone_val}'")

        tournament_name = ticket["tournament_name"] if ticket["tournament_name"] else "N/A"
        logo_status = "Uploaded ✅" if ticket.get("team_logo_url") else "Not uploaded (Optional) ❌"

        # Confirmation Embed
        confirm_embed = discord.Embed(
            title="📋 Team Information Saved",
            description=(
                f"Thank you, {interaction.user.mention}! Your team details have been recorded.\n\n"
                f"🏆 **Tournament:** {tournament_name}\n"
                f"🛡️ **Team Name:** {team_name_val}\n"
                f"👑 **Captain Name:** {captain_name_val}\n"
                f"🆔 **Captain Discord ID:** {captain_discord_id_val}\n"
                f"📞 **Phone Number:** {captain_phone_val}\n"
                f"🖼️ **Team Logo:** {logo_status}\n\n"
                "**Next Steps:**\n"
                "• Click **[🖼️ Upload Team Logo]** to upload/change your logo (PNG, JPG, WEBP, max 5 MB).\n"
                "• Click **[➡️ Continue to Roster]** when ready to enter your team roster."
            ),
            color=discord.Color.from_rgb(0, 255, 163)
        )
        confirm_embed.set_footer(text="GEN Esports Tournament System • Stage 4 Complete")

        # Send confirmation message with UploadLogoView via followup
        await interaction.followup.send(embed=confirm_embed, view=UploadLogoView())

    async def on_error(self, interaction: discord.Interaction, error: Exception):
        logger.error(f"[MODAL ERROR] Exception in TeamInfoModal: {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An unexpected error occurred while processing your team information.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An unexpected error occurred while processing your team information.", ephemeral=True)

class UploadLogoView(discord.ui.View):
    """Persistent View for uploading team logo image and continuing to roster."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Upload Team Logo",
        style=discord.ButtonStyle.primary,
        emoji="🖼️",
        custom_id="gen_tournament:upload_logo",
        row=0
    )
    async def upload_logo_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for uploading team logo image."""
        logger.info(f"[BUTTON CLICKED] 'Upload Team Logo' clicked by {interaction.user} in channel '{interaction.channel.name}'")

        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        await interaction.response.send_message(
            "📥 **Please upload your team logo image as an attachment in this channel within 60 seconds.**\n\n"
            "📌 **Requirements:**\n"
            "• Accepted formats: **PNG, JPG, WEBP**\n"
            "• Maximum file size: **5 MB**",
            ephemeral=True
        )

        def check(m: discord.Message):
            return m.channel.id == interaction.channel.id and m.author.id == interaction.user.id and len(m.attachments) > 0

        try:
            msg: discord.Message = await interaction.client.wait_for("message", check=check, timeout=60.0)
        except asyncio.TimeoutError:
            await interaction.followup.send("⏳ Logo upload timed out. Click **[🖼️ Upload Team Logo]** to try again.", ephemeral=True)
            return

        attachment = msg.attachments[0]

        # Validate file size and format using modular storage validator
        is_valid, err_msg = validate_logo_file(attachment.filename, attachment.size, attachment.content_type or "")
        if not is_valid:
            await interaction.followup.send(f"❌ {err_msg}", ephemeral=True)
            return

        try:
            file_bytes = await attachment.read()
            local_path, relative_url = save_team_logo(file_bytes, attachment.filename, ticket["ticket_id"])
            await update_ticket_logo(interaction.channel.id, local_path)
            logger.info(f"[LOGO SAVED] Logo saved for ticket #{ticket['ticket_id']} at '{local_path}'")
        except Exception as e:
            logger.error(f"Error saving logo for ticket #{ticket['ticket_id']}: {e}", exc_info=e)
            await interaction.followup.send("❌ An error occurred while saving the logo file.", ephemeral=True)
            return

        # Prepare confirmation embed with logo thumbnail
        confirm_embed = discord.Embed(
            title="🖼️ Team Logo Uploaded",
            description=(
                f"Your team logo has been saved successfully, {interaction.user.mention}!\n\n"
                "Click **[🖼️ Upload Team Logo]** if you wish to replace it, or **[➡️ Continue to Roster]** to proceed."
            ),
            color=discord.Color.from_rgb(0, 255, 163)
        )
        confirm_embed.set_footer(text="GEN Esports Tournament System • Logo Saved")

        logo_file = discord.File(local_path, filename="team_logo.png")
        confirm_embed.set_thumbnail(url="attachment://team_logo.png")

        await interaction.channel.send(embed=confirm_embed, file=logo_file, view=UploadLogoView())
        await interaction.followup.send("✅ Team logo uploaded successfully!", ephemeral=True)

    @discord.ui.button(
        label="Continue to Roster",
        style=discord.ButtonStyle.success,
        emoji="➡️",
        custom_id="gen_tournament:continue_roster",
        row=0
    )
    async def continue_roster_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for continuing to roster submission."""
        logger.info(f"[BUTTON CLICKED] 'Continue to Roster' clicked by {interaction.user} in channel '{interaction.channel.name}'")
        await interaction.response.defer(ephemeral=True)

        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.followup.send("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            await interaction.followup.send(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        embed = discord.Embed(
            title="👥 TEAM ROSTER",
            description=(
                "Required roster:\n"
                "• Player 1\n"
                "• Player 2\n"
                "• Player 3\n"
                "• Player 4\n"
                "• Player 5\n"
                "• Substitute"
            ),
            color=discord.Color.from_rgb(0, 255, 163)
        )
        embed.set_footer(text="GEN Esports Tournament System • Stage 5 Roster Setup")

        await interaction.channel.send(embed=embed, view=EnterRosterView())
        await interaction.followup.send("✅ Roster registration opened below.", ephemeral=True)

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in UploadLogoView ({getattr(item, 'custom_id', 'unknown')}): {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred while processing your request.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An error occurred while processing your request.", ephemeral=True)

class ContinueToTeamView(discord.ui.View):
    """Persistent View for transitioning after tournament selection."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="Continue",
        style=discord.ButtonStyle.primary,
        emoji="➡️",
        custom_id="gen_tournament:continue_team"
    )
    async def continue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for continuing after tournament selection."""
        logger.info(f"[BUTTON CLICKED] 'Continue' clicked by {interaction.user} in channel '{interaction.channel.name}'")

        ticket = await get_ticket_by_channel(interaction.channel.id)
        if not ticket:
            await interaction.response.send_message("❌ Could not locate an active registration ticket for this channel.", ephemeral=True)
            return

        if ticket["user_id"] != interaction.user.id:
            logger.warning(f"[PERMISSION DENIED] User {interaction.user} (ID: {interaction.user.id}) tried to click 'Continue' for ticket owned by ID {ticket['user_id']}")
            await interaction.response.send_message(f"❌ Only the user who created this registration ticket (<@{ticket['user_id']}>) can perform this action.", ephemeral=True)
            return

        if not ticket["tournament_name"]:
            await interaction.response.send_message("⚠️ Please select a tournament from the dropdown menu first!", ephemeral=True)
            return

        # Open Team Information Modal (must be direct response without deferring)
        await interaction.response.send_modal(TeamInfoModal(default_discord_id=str(interaction.user.id)))

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in ContinueToTeamView ({getattr(item, 'custom_id', 'unknown')}): {error}", exc_info=error)
        if not interaction.response.is_done():
            await interaction.response.send_message("❌ An error occurred while opening the team information form.", ephemeral=True)
        else:
            await interaction.followup.send("❌ An error occurred while opening the team information form.", ephemeral=True)

class TournamentSelect(discord.ui.Select):
    """Select menu for choosing a GEN Esports tournament, dynamically populated from database."""

    def __init__(self, open_tournaments: list[dict] = None):
        if open_tournaments is None:
            try:
                open_tournaments = _get_open_tournaments_sync()
            except Exception as e:
                logger.error(f"Error fetching open tournaments for Select menu: {e}")
                open_tournaments = []

        options = []
        if open_tournaments:
            for t in open_tournaments:
                title = t.get("title", "GEN Tournament")
                game = t.get("game_type") or t.get("game") or "Esports"
                prize = t.get("prize_info", "")
                is_full = t.get("is_full", False) or t.get("registration_status") == "FULL"
                
                # Exclude full tournaments from active Discord registration dropdown
                if is_full:
                    continue

                desc = f"{game} • Prize: {prize}" if prize else f"{game} Series"
                options.append(
                    discord.SelectOption(
                        label=title[:100],
                        value=title[:100],
                        description=desc[:100],
                        emoji="🏆"
                    )
                )

        if not options:
            options = [
                discord.SelectOption(
                    label="GEN Valorant Championship",
                    value="GEN Valorant Championship",
                    description="5v5 Tactical Shooter Championship",
                    emoji="🏆"
                ),
                discord.SelectOption(
                    label="GEN PUBG Mobile Championship",
                    value="GEN PUBG Mobile Championship",
                    description="PUBG Mobile Championship",
                    emoji="🏆"
                )
            ]

        super().__init__(
            placeholder="Choose an open tournament to register for...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="gen_tournament:select_menu"
        )

    async def callback(self, interaction: discord.Interaction):
        """Handler when user selects a tournament option."""
        selected_tournament = self.values[0]
        logger.info(f"[TOURNAMENT SELECT] User {interaction.user} (ID: {interaction.user.id}) selected '{selected_tournament}' in channel {interaction.channel.id}")

        await interaction.response.defer()

        # Check if tournament was already selected for this registration ticket
        ticket = await get_ticket_by_channel(interaction.channel.id)
        if ticket and ticket["tournament_name"]:
            await interaction.followup.send(
                f"⚠️ You have already selected **{ticket['tournament_name']}** for this ticket registration!",
                ephemeral=True
            )
            return

        # Update SQLite database with chosen tournament
        await update_ticket_tournament(interaction.channel.id, selected_tournament)

        # Confirmation Embed
        confirm_embed = discord.Embed(
            title=f"✅ Tournament Selected: {selected_tournament}",
            description=(
                f"Great choice, {interaction.user.mention}!\n"
                f"You have registered for **{selected_tournament}**.\n\n"
                "**Ready to enter your team information?**\n"
                "Click the **➡️ Continue** button below to proceed."
            ),
            color=discord.Color.from_rgb(0, 255, 163)
        )
        confirm_embed.set_footer(text="GEN Esports Tournament System • Stage 2 Complete")

        # Send confirmation message with Continue button via followup
        await interaction.followup.send(embed=confirm_embed, view=ContinueToTeamView())

class TournamentSelectionView(discord.ui.View):
    """Persistent View containing TournamentSelect dropdown and CloseTicket button."""

    def __init__(self, open_tournaments: list[dict] = None):
        super().__init__(timeout=None)
        self.add_item(TournamentSelect(open_tournaments=open_tournaments))

    @discord.ui.button(
        label="Close Ticket",
        style=discord.ButtonStyle.danger,
        emoji="❌",
        custom_id="gen_tournament:close_ticket",
        row=1
    )
    async def close_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Close ticket button inside selection view."""
        logger.info(f"[BUTTON CLICKED] 'Close Ticket' clicked by {interaction.user} in channel {interaction.channel.id}")
        await interaction.response.defer()
        await close_ticket(interaction.channel.id)

        embed = discord.Embed(
            title="🔒 Closing Registration Ticket",
            description=f"Ticket closed by {interaction.user.mention}.\nThis channel will be deleted in **5 seconds**...",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)
        await asyncio.sleep(5)
        try:
            await interaction.channel.delete(reason=f"Registration ticket closed by {interaction.user}")
        except Exception as e:
            logger.error(f"Error deleting ticket channel: {e}")

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in TournamentSelectionView ({getattr(item, 'custom_id', 'unknown')}): {error}", exc_info=error)

class RegistrationPanel(discord.ui.View):
    """Persistent View for the main Tournament Registration panel button."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(
        label="REGISTER NOW",
        style=discord.ButtonStyle.success,
        emoji="🎫",
        custom_id="gen_tournament:register"
    )
    async def register_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Handler for creating a private registration ticket channel."""
        logger.info(f"[BUTTON CLICKED] 'Register for Tournament' clicked by {interaction.user} (ID: {interaction.user.id}) in guild '{interaction.guild}'")

        # 1. Acknowledge interaction IMMEDIATELY
        await interaction.response.defer(ephemeral=True)

        guild = interaction.guild
        user = interaction.user

        if not guild:
            await interaction.followup.send("❌ This command can only be used in a server.", ephemeral=True)
            return

        # 2. Check SQLite database for an existing active ticket
        active_ticket = await get_active_ticket(user.id, guild.id)
        if active_ticket:
            existing_channel = guild.get_channel(active_ticket["channel_id"])
            if existing_channel:
                logger.info(f"[TICKET DUPLICATE] User {user} already has active ticket channel {existing_channel.id}")
                await interaction.followup.send(
                    f"❌ You already have an active registration ticket: {existing_channel.mention}",
                    ephemeral=True
                )
                return
            else:
                await close_ticket(active_ticket["channel_id"])

        # 3. Check bot channel permissions
        bot_member = guild.me
        if not bot_member.guild_permissions.manage_channels:
            logger.error(f"[PERMISSION DENIED] Bot lacks 'manage_channels' permission in guild '{guild.name}' ({guild.id})")
            await interaction.followup.send(
                "❌ Bot lacks **Manage Channels** permission. Please ask a server admin to grant the bot Manage Channels permission.",
                ephemeral=True
            )
            return

        # 4. Find or create Category for tickets
        category_name = "🏆 REGISTRATION TICKETS"
        category = discord.utils.get(guild.categories, name=category_name)
        if not category:
            try:
                category = await guild.create_category(category_name)
                logger.info(f"Created new category '{category_name}' in guild '{guild.name}'")
            except discord.Forbidden:
                category = None

        # 5. Define channel permission overrides
        overrides = {
            guild.default_role: discord.PermissionOverwrite(view_channel=False),
            user: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                read_message_history=True,
                attach_files=True
            ),
            bot_member: discord.PermissionOverwrite(
                view_channel=True,
                send_messages=True,
                manage_channels=True,
                manage_permissions=True
            )
        }

        # Grant access to staff/admin roles
        for role in guild.roles:
            if role.permissions.administrator or "staff" in role.name.lower() or "admin" in role.name.lower():
                overrides[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True)

        # 6. Create the private text channel
        channel_name = f"ticket-{user.name}".lower().replace(" ", "-")
        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                category=category,
                overwrites=overrides,
                topic=f"Registration Ticket for {user} (ID: {user.id})"
            )
            logger.info(f"Created private ticket channel '{channel_name}' (ID: {channel.id}) for user {user}")
        except discord.Forbidden as e:
            logger.error(f"[CREATE CHANNEL FORBIDDEN] Failed to create channel in guild '{guild.name}': {e}")
            await interaction.followup.send(
                "❌ Bot lacks permission to create channels in this category.",
                ephemeral=True
            )
            return

        # 7. Store ticket in SQLite
        ticket_id = await create_ticket(user.id, guild.id, channel.id)
        logger.info(f"Registered ticket #{ticket_id} in SQLite for user {user} (Channel: {channel.id})")

        # 8. Send Welcome & Tournament Selection Embed inside the ticket channel
        welcome_embed = discord.Embed(
            title="🏆 Welcome to GEN Esports Registration",
            description=(
                f"Welcome, {user.mention}!\n\n"
                "**Which tournament would you like to register for?**\n"
                "Please select your tournament from the dropdown menu below to begin."
            ),
            color=discord.Color.from_rgb(0, 255, 163)
        )
        welcome_embed.set_footer(text="GEN Esports Tournament Registration • Step 3")

        await channel.send(
            content=f"Welcome {user.mention}! Please select your tournament below:",
            embed=welcome_embed,
            view=TournamentSelectionView()
        )

        # 9. Send ephemeral confirmation to user
        await interaction.followup.send(
            f"✅ Your registration ticket has been created: {channel.mention}",
            ephemeral=True
        )

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item):
        logger.error(f"[VIEW ERROR] Exception in RegistrationPanel ({item.custom_id}): {error}", exc_info=error)

class RegistrationCog(commands.Cog):
    """Cog handling tournament registration panel setup and ticket management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup_registration_panel", description="Deploy permanent tournament registration panel in this channel.")
    @app_commands.describe(channel="Optional text channel for deploying the registration panel.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_registration_panel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Admin command to deploy or update the permanent registration panel."""
        target_channel = channel or interaction.channel
        await set_bot_setting("registration_channel_id", str(target_channel.id))
        logger.info(f"[/setup_registration_panel] Setting registration channel #{target_channel.name} (ID: {target_channel.id}) by {interaction.user}")

        # Duplicate Prevention Check
        existing_msg_id_str = await get_bot_setting("registration_panel_message_id")
        existing_msg = None
        if existing_msg_id_str and existing_msg_id_str.isdigit():
            try:
                existing_msg = await target_channel.fetch_message(int(existing_msg_id_str))
            except Exception:
                existing_msg = None

        panel_embed = discord.Embed(
            title="🏆 GEN ESPORTS TOURNAMENT REGISTRATION",
            description=(
                "Ready to compete?\n"
                "Click the button below to register your team for an upcoming GEN Esports tournament."
            ),
            color=discord.Color.from_rgb(0, 255, 163)
        )
        panel_embed.set_thumbnail(url=interaction.guild.icon.url if interaction.guild and interaction.guild.icon else None)
        panel_embed.set_footer(text="GEN Esports Tournament System • Permanent Panel")

        if existing_msg:
            try:
                await existing_msg.edit(embed=panel_embed, view=RegistrationPanel())
                logger.info(f"[/setup_registration_panel] Updated existing panel message (ID: {existing_msg.id}) in #{target_channel.name}")
                await interaction.response.send_message(
                    f"✅ Registration panel updated in {target_channel.mention}.",
                    ephemeral=True
                )
                return
            except Exception as e:
                logger.warning(f"[/setup_registration_panel] Could not edit existing message: {e}")

        # Post new panel message
        panel_msg = await target_channel.send(embed=panel_embed, view=RegistrationPanel())
        await set_bot_setting("registration_panel_message_id", str(panel_msg.id))
        logger.info(f"[/setup_registration_panel] Created new registration panel message (ID: {panel_msg.id}) in #{target_channel.name}")

        await interaction.response.send_message(
            f"✅ Registration panel configured successfully in {target_channel.mention}.",
            ephemeral=True
        )

    @setup_registration_panel.error
    async def setup_registration_panel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You need Administrator permissions to configure the registration panel.", ephemeral=True)
        else:
            logger.error(f"Error executing /setup_registration_panel: {error}")
            await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)

    @app_commands.command(name="setup_admin", description="Configure current channel as admin review destination for registrations.")
    @app_commands.describe(channel="Optional text channel for receiving registration review messages.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_admin(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Admin command to set the admin review channel."""
        target_channel = channel or interaction.channel
        await set_bot_setting("admin_channel_id", str(target_channel.id))
        await set_bot_setting("review_channel_id", str(target_channel.id))
        logger.info(f"[ADMIN SETUP] Admin channel configured: #{target_channel.name} (ID: {target_channel.id}) by {interaction.user}")

        embed = discord.Embed(
            title="⚙️ Admin Review Channel Configured",
            description=(
                f"✅ Admin review channel configured successfully in {target_channel.mention}.\n\n"
                "All submitted team registrations will automatically post here with **[✅ APPROVE]** and **[❌ REJECT]** buttons for admin review."
            ),
            color=discord.Color.from_rgb(0, 255, 163)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @setup_admin.error
    async def setup_admin_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You need Administrator permissions to configure the admin review channel.", ephemeral=True)
        else:
            logger.error(f"Error executing /setup_admin: {error}")
            await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)

    @app_commands.command(name="setup_review_channel", description="Configure review channel for admin approval notifications.")
    @app_commands.describe(channel="Optional text channel for receiving registration review messages.")
    @app_commands.default_permissions(administrator=True)
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_review_channel(self, interaction: discord.Interaction, channel: discord.TextChannel = None):
        """Admin command to set the registration review channel."""
        target_channel = channel or interaction.channel
        await set_bot_setting("admin_channel_id", str(target_channel.id))
        await set_bot_setting("review_channel_id", str(target_channel.id))
        logger.info(f"[ADMIN SETUP] Admin channel configured: #{target_channel.name} (ID: {target_channel.id}) by {interaction.user}")

        embed = discord.Embed(
            title="⚙️ Admin Review Channel Configured",
            description=(
                f"✅ Admin review channel configured successfully in {target_channel.mention}.\n\n"
                "All submitted team registrations will automatically post here with **[✅ APPROVE]** and **[❌ REJECT]** buttons for admin review."
            ),
            color=discord.Color.from_rgb(0, 255, 163)
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @setup_review_channel.error
    async def setup_review_channel_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, app_commands.MissingPermissions):
            await interaction.response.send_message("❌ You need Administrator permissions to configure the review channel.", ephemeral=True)
        else:
            logger.error(f"Error executing /setup_review_channel: {error}")
            await interaction.response.send_message("❌ An unexpected error occurred.", ephemeral=True)

    @app_commands.command(name="manage-team", description="[Captain/Staff] Manage team roster, invite players, or view members.")
    async def manage_team_cmd(self, interaction: discord.Interaction):
        """Open team roster management interface for captains and staff."""
        await interaction.response.defer(ephemeral=True)
        from database.db import _get_connection, get_team_roster_discord_ids
        
        user_id = str(interaction.user.id)
        is_admin = interaction.user.guild_permissions.administrator
        
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT tm.*, t.ticket_id, t.tournament_name
                FROM teams tm
                LEFT JOIN tickets t ON tm.name = t.team_name
                WHERE tm.captain_discord_id = ? OR t.captain_discord_id = ?
                ORDER BY tm.team_id DESC LIMIT 1;
            """, (user_id, user_id))
            team_row = cursor.fetchone()

        if not team_row and not is_admin:
            await interaction.followup.send("❌ Only team captains or staff can manage team rosters.", ephemeral=True)
            return

        if not team_row:
            with _get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM teams ORDER BY team_id DESC LIMIT 1;")
                team_row = cursor.fetchone()
            if not team_row:
                await interaction.followup.send("❌ No registered teams found.", ephemeral=True)
                return

        team = dict(team_row)
        team_id = team["team_id"]
        
        tourn_id = 0
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT tournament_id FROM tournaments ORDER BY tournament_id DESC LIMIT 1;")
            tr = cursor.fetchone()
            if tr:
                tourn_id = tr["tournament_id"]

        roster_ids = await get_team_roster_discord_ids(team_id)
        roster_mentions = []
        for r_id in roster_ids:
            mb = interaction.guild.get_member(int(r_id)) if interaction.guild else None
            if mb:
                roster_mentions.append(f"• {mb.mention} ({mb.display_name})")
            else:
                roster_mentions.append(f"• Discord ID `{r_id}`")

        roster_str = "\n".join(roster_mentions) if roster_mentions else "No active members."

        embed = discord.Embed(
            title=f"👥 Team Roster Management — {team['name']}",
            description=(
                f"**Team ID:** `{team_id}`\n"
                f"**Captain:** <@{team.get('captain_discord_id', user_id)}>\n\n"
                f"**Current Roster ({len(roster_ids)} players):**\n{roster_str}\n\n"
                "Use the **User Select** dropdown below to invite a Discord server member to join your team!"
            ),
            color=discord.Color.blue()
        )
        view = ManageTeamView(team_id, tourn_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="my-invitations", description="View and accept/decline your pending team invitations.")
    async def my_invitations_cmd(self, interaction: discord.Interaction):
        """View pending team invitations for the user."""
        await interaction.response.defer(ephemeral=True)
        from database.db import get_pending_invitations_for_user
        
        invites = await get_pending_invitations_for_user(str(interaction.user.id))
        if not invites:
            await interaction.followup.send("ℹ️ You have no pending team invitations.", ephemeral=True)
            return

        inv = invites[0]
        inv_id = inv["id"] if "id" in inv else inv.get("rowid", 1)
        embed = discord.Embed(
            title="📩 Pending Team Invitation",
            description=f"You have been invited to join **{inv['team_name']}** for **{inv.get('tournament_name', 'Tournament')}**!\n\nClick **ACCEPT INVITE** or **DECLINE** below.",
            color=discord.Color.gold()
        )
        view = InvitationView(inv_id)
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)

async def setup(bot: commands.Bot):
    """Register RegistrationCog."""
    await bot.add_cog(RegistrationCog(bot))


