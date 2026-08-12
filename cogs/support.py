import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional, List, Dict, Any

from database.db import (
    generate_next_case_id,
    create_support_ticket,
    get_support_ticket_by_case_id,
    get_support_ticket_by_channel,
    update_support_ticket_assignment,
    update_support_ticket_priority,
    add_support_ticket_note,
    close_support_ticket,
    save_support_transcript,
    get_user_active_support_tickets,
    get_user_all_registrations,
    get_user_all_cases,
    get_open_tournaments,
    log_admin_action
)
import config.settings as settings

logger = logging.getLogger("GENEsportsBot")

# ==============================================================================
# HELPER FUNCTIONS & CATEGORIES
# ==============================================================================

CATEGORY_NAMES = {
    "REGISTRATION": "🎫 REGISTRATION TICKETS",
    "SUPPORT": "🆘 SUPPORT TICKETS",
    "REPORTS": "⚠️ REPORTS",
    "DISPUTES": "⚖️ DISPUTES"
}

async def get_or_create_category(guild: discord.Guild, cat_type: str) -> discord.CategoryChannel:
    """Find existing category or create a new one safely."""
    target_name = CATEGORY_NAMES.get(cat_type, "🆘 SUPPORT TICKETS")
    for category in guild.categories:
        if category.name.lower() == target_name.lower():
            return category
    
    # Create category if not found
    try:
        category = await guild.create_category(name=target_name)
        logger.info(f"[SUPPORT] Created missing Discord category: '{target_name}'")
        return category
    except Exception as e:
        logger.error(f"[SUPPORT] Error creating category '{target_name}': {e}")
        return None

# ==============================================================================
# MODALS FOR STRUCTURED TICKET INPUT
# ==============================================================================

class GeneralSupportModal(discord.ui.Modal, title="General Support Request"):
    subject = discord.ui.TextInput(label="Subject", placeholder="What do you need help with?", max_length=100, required=True)
    description = discord.ui.TextInput(label="Description", style=discord.TextStyle.paragraph, placeholder="Provide full details...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await create_support_channel(
            interaction=interaction,
            ticket_type="GENERAL_SUPPORT",
            category_key="SUPPORT",
            subject=self.subject.value,
            details=self.description.value
        )

class TournamentHelpModal(discord.ui.Modal, title="Tournament Help Request"):
    tournament_name = discord.ui.TextInput(label="Tournament Name", placeholder="e.g. GEN Valorant Championship", max_length=100, required=True)
    registration_code = discord.ui.TextInput(label="Registration ID / Ticket ID (Optional)", placeholder="e.g. GEN-REG-000123", max_length=50, required=False)
    issue_description = discord.ui.TextInput(label="Describe Issue", style=discord.TextStyle.paragraph, placeholder="Explain what help you need...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await create_support_channel(
            interaction=interaction,
            ticket_type="TOURNAMENT_HELP",
            category_key="SUPPORT",
            subject=f"Help: {self.tournament_name.value}",
            details=f"Tournament: {self.tournament_name.value}\nReg Code: {self.registration_code.value or 'N/A'}\nIssue: {self.issue_description.value}"
        )

class PaymentSupportModal(discord.ui.Modal, title="Payment / Prize Support"):
    tournament_name = discord.ui.TextInput(label="Tournament / Event", placeholder="e.g. GEN Valorant Championship", max_length=100, required=True)
    payment_ref = discord.ui.TextInput(label="Transaction / Reference ID", placeholder="e.g. TXN-998822", max_length=100, required=True)
    details = discord.ui.TextInput(label="Issue / Details", style=discord.TextStyle.paragraph, placeholder="Describe payment/prize issue...", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        await create_support_channel(
            interaction=interaction,
            ticket_type="PAYMENT_SUPPORT",
            category_key="SUPPORT",
            subject=f"Payment Ref: {self.payment_ref.value}",
            details=f"Tournament: {self.tournament_name.value}\nRef ID: {self.payment_ref.value}\nDetails: {self.details.value}"
        )

class PlayerReportModal(discord.ui.Modal, title="Report Player"):
    reported_user = discord.ui.TextInput(label="Reported Player IGN / Discord ID", placeholder="IGN or Discord username", max_length=100, required=True)
    tournament_name = discord.ui.TextInput(label="Tournament", placeholder="e.g. GEN Valorant Championship", max_length=100, required=True)
    reason = discord.ui.TextInput(label="Reason for Report", style=discord.TextStyle.paragraph, placeholder="Cheating, toxicity, improper roster, etc.", required=True)
    evidence_url = discord.ui.TextInput(label="Evidence Link / Screenshots", placeholder="Imgur/YouTube/Drive link...", max_length=250, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await create_support_channel(
            interaction=interaction,
            ticket_type="PLAYER_REPORT",
            category_key="REPORTS",
            subject=f"Report: {self.reported_user.value}",
            details=f"Reported Player: {self.reported_user.value}\nTournament: {self.tournament_name.value}\nReason: {self.reason.value}\nEvidence: {self.evidence_url.value or 'Attached in channel'}"
        )

class TeamReportModal(discord.ui.Modal, title="Report Team"):
    reported_team = discord.ui.TextInput(label="Reported Team Name", placeholder="Full team name", max_length=100, required=True)
    tournament_name = discord.ui.TextInput(label="Tournament", placeholder="e.g. GEN PUBG Mobile Championship", max_length=100, required=True)
    reason = discord.ui.TextInput(label="Reason for Report", style=discord.TextStyle.paragraph, placeholder="Roster violations, ringers, etc.", required=True)
    evidence_url = discord.ui.TextInput(label="Evidence Link", placeholder="Link to screenshots/video...", max_length=250, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await create_support_channel(
            interaction=interaction,
            ticket_type="TEAM_REPORT",
            category_key="REPORTS",
            subject=f"Report Team: {self.reported_team.value}",
            details=f"Reported Team: {self.reported_team.value}\nTournament: {self.tournament_name.value}\nReason: {self.reason.value}\nEvidence: {self.evidence_url.value or 'Attached in channel'}"
        )

class DisputeModal(discord.ui.Modal, title="Match Dispute Request"):
    tournament_name = discord.ui.TextInput(label="Tournament", placeholder="e.g. GEN Valorant Championship", max_length=100, required=True)
    match_id = discord.ui.TextInput(label="Match ID / Stage", placeholder="e.g. Match #14 or Quarterfinals", max_length=50, required=True)
    dispute_details = discord.ui.TextInput(label="Dispute Explanation", style=discord.TextStyle.paragraph, placeholder="Explain match score/rule dispute...", required=True)
    evidence_url = discord.ui.TextInput(label="Evidence Screenshots / Video", placeholder="Link to match end screenshots...", max_length=250, required=False)

    async def on_submit(self, interaction: discord.Interaction):
        await create_support_channel(
            interaction=interaction,
            ticket_type="DISPUTE",
            category_key="DISPUTES",
            subject=f"Dispute: Match {self.match_id.value}",
            details=f"Tournament: {self.tournament_name.value}\nMatch: {self.match_id.value}\nDetails: {self.dispute_details.value}\nEvidence: {self.evidence_url.value or 'Attached in channel'}"
        )

# ==============================================================================
# CHANNEL CREATION LOGIC
# ==============================================================================

async def create_support_channel(interaction: discord.Interaction, ticket_type: str, category_key: str, subject: str, details: str):
    """Core function to safely create a private support channel with Case ID."""
    guild = interaction.guild
    user = interaction.user
    
    # 1. Rate Limit Check: max 3 active support tickets per user
    active_tickets = await get_user_active_support_tickets(str(user.id))
    if len(active_tickets) >= 3:
        await interaction.response.send_message(
            "⚠️ **Active Ticket Limit Reached**: You already have 3 open support tickets. Please resolve your existing tickets before creating a new one.",
            ephemeral=True
        )
        return

    await interaction.response.defer(ephemeral=True)

    # 2. Generate unique Case ID
    case_id = await generate_next_case_id()

    # 3. Locate category
    category = await get_or_create_category(guild, category_key)
    
    # 4. Set channel permissions (User + Staff + Bot + Deny Everyone)
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }

    # Add Staff Role permissions if defined
    if settings.STAFF_ROLE_ID:
        staff_role = guild.get_role(settings.STAFF_ROLE_ID)
        if staff_role:
            overwrites[staff_role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)

    # Clean channel name format: ticket-type-case_id (lowercase)
    channel_name = f"{ticket_type.lower().replace('_', '-')}-{case_id.lower()}"
    
    try:
        channel = await guild.create_text_channel(
            name=channel_name,
            category=category,
            overwrites=overwrites,
            topic=f"GEN Esports Support Case: {case_id} | User: {user} | Type: {ticket_type}"
        )
    except Exception as e:
        logger.error(f"[SUPPORT] Failed to create support text channel: {e}")
        await interaction.followup.send("❌ Error creating support ticket channel. Please notify an administrator.", ephemeral=True)
        return

    # 5. Record ticket in database
    await create_support_ticket(
        case_id=case_id,
        ticket_type=ticket_type,
        user_id=str(user.id),
        guild_id=str(guild.id),
        channel_id=str(channel.id),
        priority="NORMAL"
    )

    # 6. Build Initial Support Embed
    embed = discord.Embed(
        title=f"🎧 GEN ESPORTS SUPPORT • {case_id}",
        description=f"Welcome {user.mention}! A GEN Esports staff member will assist you shortly.\n\n**Subject:** `{subject}`",
        color=discord.Color.blue()
    )
    embed.add_field(name="📋 Case ID", value=f"`{case_id}`", inline=True)
    embed.add_field(name="📂 Category", value=f"`{ticket_type.replace('_', ' ')}`", inline=True)
    embed.add_field(name="🟢 Status", value="`OPEN`", inline=True)
    embed.add_field(name="⚡ Priority", value="`NORMAL`", inline=True)
    embed.add_field(name="👤 Assigned Staff", value="`Unassigned`", inline=True)
    embed.add_field(name="📝 Details", value=f"```\n{details[:900]}\n```", inline=False)
    embed.set_footer(text="Upload any relevant screenshots or video evidence directly in this channel.")

    # 7. Post Control View in channel
    control_view = SupportTicketControlView(case_id=case_id)
    msg = await channel.send(content=f"{user.mention} | Staff Role: <@&{settings.STAFF_ROLE_ID}>" if settings.STAFF_ROLE_ID else f"{user.mention}", embed=embed, view=control_view)

    # Notify user in ephemeral followup
    await interaction.followup.send(f"✅ **Support Ticket Created**: {channel.mention} (Case ID: `{case_id}`)", ephemeral=True)

# ==============================================================================
# PERSISTENT TICKET CONTROL VIEW (STAFF CONTROLS)
# ==============================================================================

class SupportTicketControlView(discord.ui.View):
    """Staff control panel view for claiming, transferring, changing priority, notes, and closing tickets."""

    def __init__(self, case_id: str = ""):
        super().__init__(timeout=None)
        self.case_id = case_id

    @discord.ui.button(label="Claim Ticket", style=discord.ButtonStyle.primary, emoji="👤", custom_id="gen_support:claim")
    async def claim_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Server-side staff check
        is_staff = interaction.user.guild_permissions.administrator or any(r.id == settings.STAFF_ROLE_ID for r in interaction.user.roles if settings.STAFF_ROLE_ID)
        if not is_staff and interaction.user.id != settings.BOT_OWNER_ID:
            await interaction.response.send_message("❌ **Staff Only**: Only authorized GEN Esports staff can claim tickets.", ephemeral=True)
            return

        ticket = await get_support_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message("❌ Ticket record not found.", ephemeral=True)
            return

        case_id = ticket["case_id"]
        await update_support_ticket_assignment(case_id, str(interaction.user.id))

        await interaction.response.send_message(f"✅ Ticket `{case_id}` has been claimed by {interaction.user.mention}.", ephemeral=False)

        # Notify user via DM safely
        try:
            user = interaction.guild.get_member(int(ticket["user_id"]))
            if user:
                await user.send(f"🏆 **GEN Esports Support Notification**: Your case `{case_id}` has been assigned to **{interaction.user.display_name}**.")
        except Exception:
            pass

    @discord.ui.button(label="Transfer", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="gen_support:transfer")
    async def transfer_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = interaction.user.guild_permissions.administrator or any(r.id == settings.STAFF_ROLE_ID for r in interaction.user.roles if settings.STAFF_ROLE_ID)
        if not is_staff and interaction.user.id != settings.BOT_OWNER_ID:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        class TransferModal(discord.ui.Modal, title="Transfer Ticket"):
            new_staff = discord.ui.TextInput(label="New Staff Member User ID / IGN", placeholder="Enter Discord User ID...", required=True)
            async def on_submit(self, modal_interaction: discord.Interaction):
                ticket = await get_support_ticket_by_channel(str(modal_interaction.channel.id))
                if ticket:
                    await update_support_ticket_assignment(ticket["case_id"], self.new_staff.value)
                    await modal_interaction.response.send_message(f"🔄 Ticket transferred to staff ID `{self.new_staff.value}`.")

        await interaction.response.send_modal(TransferModal())

    @discord.ui.button(label="Set Priority", style=discord.ButtonStyle.secondary, emoji="⏫", custom_id="gen_support:priority")
    async def set_priority(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = interaction.user.guild_permissions.administrator or any(r.id == settings.STAFF_ROLE_ID for r in interaction.user.roles if settings.STAFF_ROLE_ID)
        if not is_staff and interaction.user.id != settings.BOT_OWNER_ID:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        ticket = await get_support_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message("❌ Ticket record not found.", ephemeral=True)
            return

        class PrioritySelectView(discord.ui.View):
            def __init__(self, case_id: str):
                super().__init__(timeout=60)
                self.case_id = case_id

            @discord.ui.select(placeholder="Select Priority Level...", options=[
                discord.SelectOption(label="LOW", emoji="🟢"),
                discord.SelectOption(label="NORMAL", emoji="🔵"),
                discord.SelectOption(label="HIGH", emoji="🟠"),
                discord.SelectOption(label="URGENT", emoji="🚨")
            ])
            async def select_callback(self, sel_interaction: discord.Interaction, select: discord.ui.Select):
                val = select.values[0]
                await update_support_ticket_priority(self.case_id, val, str(sel_interaction.user.id))
                await sel_interaction.response.send_message(f"⚡ Priority for `{self.case_id}` set to **{val}**.", ephemeral=False)

        await interaction.response.send_message("Select new ticket priority level:", view=PrioritySelectView(ticket["case_id"]), ephemeral=True)

    @discord.ui.button(label="Add Note", style=discord.ButtonStyle.secondary, emoji="📝", custom_id="gen_support:note")
    async def add_note(self, interaction: discord.Interaction, button: discord.ui.Button):
        is_staff = interaction.user.guild_permissions.administrator or any(r.id == settings.STAFF_ROLE_ID for r in interaction.user.roles if settings.STAFF_ROLE_ID)
        if not is_staff and interaction.user.id != settings.BOT_OWNER_ID:
            await interaction.response.send_message("❌ Staff only.", ephemeral=True)
            return

        ticket = await get_support_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message("❌ Ticket record not found.", ephemeral=True)
            return

        class NoteModal(discord.ui.Modal, title="Add Internal Staff Note"):
            note = discord.ui.TextInput(label="Internal Note", style=discord.TextStyle.paragraph, placeholder="Private note visible to staff...", required=True)
            async def on_submit(self, modal_interaction: discord.Interaction):
                await add_support_ticket_note(ticket["case_id"], str(modal_interaction.user.id), self.note.value)
                await modal_interaction.response.send_message("📝 Internal staff note added successfully.", ephemeral=True)

        await interaction.response.send_modal(NoteModal())

    @discord.ui.button(label="Close Ticket", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="gen_support:close")
    async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
        ticket = await get_support_ticket_by_channel(str(interaction.channel.id))
        if not ticket:
            await interaction.response.send_message("❌ Ticket record not found.", ephemeral=True)
            return

        class CloseReasonModal(discord.ui.Modal, title="Close Support Case"):
            resolution = discord.ui.Select(placeholder="Resolution Status...", options=[
                discord.SelectOption(label="RESOLVED", emoji="✅"),
                discord.SelectOption(label="DUPLICATE", emoji="📑"),
                discord.SelectOption(label="USER_REQUESTED", emoji="👤"),
                discord.SelectOption(label="NO_RESPONSE", emoji="⏳"),
                discord.SelectOption(label="OTHER", emoji="❓")
            ])
            reason = discord.ui.TextInput(label="Resolution Summary", style=discord.TextStyle.paragraph, placeholder="Explain resolution...", required=True)

            async def on_submit(self, modal_interaction: discord.Interaction):
                await modal_interaction.response.defer()
                
                # Fetch recent channel messages for transcript
                transcript_text = f"GEN ESPORTS SUPPORT TRANSCRIPT • {ticket['case_id']}\n"
                transcript_text += f"Type: {ticket['ticket_type']} | User: {ticket['user_id']}\n"
                transcript_text += "==================================================\n\n"
                
                try:
                    async for msg in modal_interaction.channel.history(limit=200, oldest_first=True):
                        transcript_text += f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author.display_name}: {msg.content}\n"
                except Exception as e:
                    logger.warn(f"Transcript gathering warning: {e}")

                await save_support_transcript(ticket["case_id"], transcript_text)
                await close_support_ticket(ticket["case_id"], str(modal_interaction.user.id), "RESOLVED", self.reason.value)

                await modal_interaction.followup.send("🔒 Case resolved and closed. Channel archiving in 5 seconds...")

                # Notify user via DM safely
                try:
                    user = modal_interaction.guild.get_member(int(ticket["user_id"]))
                    if user:
                        await user.send(f"🏆 **GEN Esports Support Notification**: Your case `{ticket['case_id']}` has been resolved and closed. Resolution: {self.reason.value}")
                except Exception:
                    pass

                import asyncio
                await asyncio.sleep(5)
                try:
                    await modal_interaction.channel.delete(reason=f"Closed support ticket {ticket['case_id']}")
                except Exception as e:
                    logger.error(f"Error deleting support channel: {e}")

        class CloseChoiceView(discord.ui.View):
            def __init__(self, case_id: str):
                super().__init__(timeout=60)
                self.case_id = case_id

            @discord.ui.select(placeholder="Choose Resolution Category...", options=[
                discord.SelectOption(label="RESOLVED", description="Issue fully resolved", emoji="✅"),
                discord.SelectOption(label="DUPLICATE", description="Duplicate request", emoji="📑"),
                discord.SelectOption(label="USER_REQUESTED", description="Closed by user request", emoji="👤"),
                discord.SelectOption(label="NO_RESPONSE", description="No response from user", emoji="⏳"),
                discord.SelectOption(label="OTHER", description="Other reason", emoji="❓")
            ])
            async def select_close(self, sel_int: discord.Interaction, sel: discord.ui.Select):
                res_val = sel.values[0]
                await sel_int.response.defer()

                # Transcript
                transcript_text = f"GEN ESPORTS TRANSCRIPT • {self.case_id}\n"
                try:
                    async for msg in sel_int.channel.history(limit=200, oldest_first=True):
                        transcript_text += f"[{msg.created_at.strftime('%Y-%m-%d %H:%M:%S')}] {msg.author.display_name}: {msg.content}\n"
                except Exception:
                    pass

                await save_support_transcript(self.case_id, transcript_text)
                await close_support_ticket(self.case_id, str(sel_int.user.id), res_val, "Closed by staff request")
                await sel_int.followup.send(f"🔒 Case `{self.case_id}` marked as **{res_val}**. Archiving channel...")

                import asyncio
                await asyncio.sleep(3)
                try:
                    await sel_int.channel.delete()
                except Exception as e:
                    logger.error(f"Error deleting channel: {e}")

        await interaction.response.send_message("Select close resolution category:", view=CloseChoiceView(ticket["case_id"]), ephemeral=True)

# ==============================================================================
# PERSISTENT SUPPORT PANEL
# ==============================================================================

class SupportPanel(discord.ui.View):
    """Persistent support panel view containing category selection dropdown."""

    def __init__(self):
        super().__init__(timeout=None)

# ==============================================================================
# PERSISTENT DISCORD SUPPORT PANEL
# ==============================================================================

class SupportPanel(discord.ui.View):
    """Persistent support panel view with button to open ticket menu."""

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="OPEN SUPPORT TICKET", style=discord.ButtonStyle.primary, emoji="🎫", custom_id="support_open_ticket")
    async def open_ticket_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="🎫 What do you need help with?",
            description="Select the category below that best describes your inquiry or issue.",
            color=discord.Color.from_rgb(0, 255, 163)
        )
        view = SupportCategorySelectView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# ==============================================================================
# DISCORD EXTENSION COG & COMMANDS
# ==============================================================================

class SupportCog(commands.Cog):
    """Cog for GEN Esports Operations & Support System."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="setup-support-panel", description="[Admin] Post persistent GEN Esports Support Panel into channel.")
    @app_commands.checks.has_permissions(administrator=True)
    async def setup_support_panel_cmd(self, interaction: discord.Interaction):
        """Admin command to deploy persistent support panel embed."""
        embed = discord.Embed(
            title="━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🛡️ GEN ESPORTS SUPPORT\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            description="Welcome to **GEN Esports Support**. Need help with registrations, match schedules, map vetoes, score disputes, payment/prizes, or player reports?\n\nClick the button below to contact GEN Esports Support.",
            color=discord.Color.from_rgb(0, 255, 163)
        )
        embed.set_footer(text="GEN Esports Support Engine • Persistent Panel")
        view = SupportPanel()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Support Panel deployed successfully.", ephemeral=True)

    @app_commands.command(name="support", description="Post the persistent GEN Esports Support Panel (Staff Only).")
    async def post_support_panel(self, interaction: discord.Interaction):
        """Slash command to deploy the support center panel."""
        if not interaction.user.guild_permissions.administrator and interaction.user.id != settings.BOT_OWNER_ID:
            await interaction.response.send_message("❌ **Admin Only**: Only administrators can post the main support panel.", ephemeral=True)
            return

        embed = discord.Embed(
            title="━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n🛡️ GEN ESPORTS SUPPORT\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
            description="Welcome to **GEN Esports Support**. Need help with registrations, match schedules, map vetoes, score disputes, payment/prizes, or player reports?\n\nClick the button below to contact GEN Esports Support.",
            color=discord.Color.from_rgb(0, 255, 163)
        )
        embed.set_footer(text="GEN Esports Support Engine • Persistent Panel")
        view = SupportPanel()
        await interaction.channel.send(embed=embed, view=view)
        await interaction.response.send_message("✅ Support Panel deployed successfully.", ephemeral=True)

    @app_commands.command(name="my-registration", description="View your active team registrations and approval status.")
    async def my_registration(self, interaction: discord.Interaction):
        """Display user's registered teams and status."""
        regs = await get_user_all_registrations(str(interaction.user.id))
        if not regs:
            await interaction.response.send_message("📋 You have no registered teams found.", ephemeral=True)
            return

        embed = discord.Embed(
            title="📋 My Active Registrations",
            description=f"Showing registered teams for {interaction.user.mention}:",
            color=discord.Color.blue()
        )
        for r in regs[:10]:
            st = r.get("status", "PENDING")
            st_emoji = "🟢" if st == "APPROVED" else ("🔴" if st == "REJECTED" else "🟡")
            embed.add_field(
                name=f"{st_emoji} {r.get('team_name')} ({r.get('registration_code') or r.get('ticket_id')})",
                value=f"**Tournament:** {r.get('tournament_name')}\n**Captain:** {r.get('captain_name')}\n**Status:** `{st}`\n**Created:** {r.get('created_at')}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="my-tickets", description="View your open and closed support cases.")
    async def my_tickets(self, interaction: discord.Interaction):
        """Display user's support cases."""
        cases = await get_user_all_cases(str(interaction.user.id))
        if not cases:
            await interaction.response.send_message("🎧 You have no support cases on record.", ephemeral=True)
            return

        embed = discord.Embed(
            title="🎧 My Support Cases",
            description=f"Showing support cases for {interaction.user.mention}:",
            color=discord.Color.blue()
        )
        for c in cases[:10]:
            st = c.get("status", "OPEN")
            st_emoji = "🔴" if st == "CLOSED" else "🟢"
            embed.add_field(
                name=f"{st_emoji} Case ID: {c.get('case_id')}",
                value=f"**Category:** `{c.get('ticket_type')}`\n**Status:** `{st}`\n**Priority:** `{c.get('priority')}`\n**Created:** {c.get('created_at')}",
                inline=False
            )
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="case", description="Look up details for a specific Case ID.")
    async def lookup_case(self, interaction: discord.Interaction, case_id: str):
        """Look up support case by Case ID."""
        ticket = await get_support_ticket_by_case_id(case_id)
        if not ticket:
            await interaction.response.send_message(f"❌ Case ID `{case_id}` was not found.", ephemeral=True)
            return

        # Check permission: creator or staff
        is_staff = interaction.user.guild_permissions.administrator or any(r.id == settings.STAFF_ROLE_ID for r in interaction.user.roles if settings.STAFF_ROLE_ID)
        if str(interaction.user.id) != ticket["user_id"] and not is_staff:
            await interaction.response.send_message("❌ You are not authorized to view this private support case.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🔎 Case Lookup: {ticket['case_id']}",
            color=discord.Color.blue()
        )
        embed.add_field(name="Category", value=f"`{ticket['ticket_type']}`", inline=True)
        embed.add_field(name="Status", value=f"`{ticket['status']}`", inline=True)
        embed.add_field(name="Priority", value=f"`{ticket['priority']}`", inline=True)
        embed.add_field(name="User ID", value=f"`{ticket['user_id']}`", inline=True)
        embed.add_field(name="Assigned Staff", value=f"`{ticket['assigned_staff_id'] or 'Unassigned'}`", inline=True)
        embed.add_field(name="Created", value=f"{ticket['created_at']}", inline=True)
        if ticket.get("resolution"):
            embed.add_field(name="Resolution", value=f"```\n{ticket['resolution']}\n```", inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    """Asynchronously register SupportCog with the bot."""
    await bot.add_cog(SupportCog(bot))
