"""
slash_commands.py
-----------------
Slash-command + modal GUI layer for every staff command in Stoat Bot.

Categories:
  /mod        — kick, ban, unban, mute, unmute, warn, purge, modlogs
  /setup      — muterole, staffrole, logchannel
  /giveaway   — create, end, reroll, info
  /ticket     — setup, addcategory, list
  /welcome    — setchannel, setmessage, test
  /autorole   — add, remove
  /reactionrole — add, remove, list
  /role       — give, take
  /automod    — spam, invite, caps, badwords add/remove
  /logs       — setchannel, disable
"""

import stoat
from stoat.ext import commands
from utils.helpers import (
    success_embed, error_embed, info_embed, warn_embed,
    parse_duration, format_duration, utcnow, is_staff,
)
import asyncio
import random
import logging
from datetime import timedelta

log = logging.getLogger("slash_commands")

# ── helpers ────────────────────────────────────────────────────────────────

async def _wait_modal(bot, interaction, modal, timeout=300):
    """Send a modal and wait for its submission. Returns the modal interaction or None."""
    await interaction.response.send_modal(modal)
    try:
        return await bot.wait_for(
            "modal_submit",
            check=lambda i: i.custom_id == modal.custom_id and i.user.id == interaction.user.id,
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        return None


def _field(mi, key: str, default: str = "") -> str:
    return (mi.fields.get(key) or default).strip()


# ── Cog ───────────────────────────────────────────────────────────────────

class SlashCommands(commands.Gear):
    """Slash command + modal GUI layer covering all bot commands."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ════════════════════════════════════════════════════════════════════════
    # /mod — Moderation
    # ════════════════════════════════════════════════════════════════════════

    @stoat.slash_command(name="mod")
    @is_staff()
    async def mod(self, interaction):
        """Moderation commands."""
        pass

    # /mod kick ──────────────────────────────────────────────────────────────

    @mod.subcommand(name="kick", description="Kick a member from the server")
    @is_staff()
    async def mod_kick(self, interaction):
        modal = stoat.Modal(title="Kick Member")
        modal.add_item(stoat.TextInput(custom_id="user_id",  label="User ID",           placeholder="123456789012345678", required=True,  max_length=20))
        modal.add_item(stoat.TextInput(custom_id="reason",   label="Reason",             placeholder="Reason for kick",    required=False, max_length=500))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        user_id = _field(mi, "user_id")
        reason  = _field(mi, "reason") or "No reason provided"
        try:
            guild  = self.bot.get_server(interaction.server.id)
            member = await guild.fetch_member(user_id)
            await member.kick()
            await self.db.log_mod_action(interaction.server.id, user_id, interaction.user.id, "kick", reason)
            embed = success_embed("Member Kicked",
                f"**User:** <@{user_id}> (`{user_id}`)\n**Reason:** {reason}\n**Moderator:** {interaction.user.mention}")
            await mi.response.send_message(embed=embed)
        except Exception as e:
            await mi.response.send_message(embed=error_embed("Failed", str(e)), ephemeral=True)

    # /mod ban ───────────────────────────────────────────────────────────────

    @mod.subcommand(name="ban", description="Ban a member from the server")
    @is_staff()
    async def mod_ban(self, interaction):
        modal = stoat.Modal(title="Ban Member")
        modal.add_item(stoat.TextInput(custom_id="user_id", label="User ID",  placeholder="123456789012345678", required=True,  max_length=20))
        modal.add_item(stoat.TextInput(custom_id="reason",  label="Reason",   placeholder="Reason for ban",     required=False, max_length=500))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        user_id = _field(mi, "user_id")
        reason  = _field(mi, "reason") or "No reason provided"
        try:
            guild  = self.bot.get_server(interaction.server.id)
            member = await guild.fetch_member(user_id)
            await member.ban()
            await self.db.log_mod_action(interaction.server.id, user_id, interaction.user.id, "ban", reason)
            embed = success_embed("Member Banned",
                f"**User:** <@{user_id}> (`{user_id}`)\n**Reason:** {reason}\n**Moderator:** {interaction.user.mention}")
            await mi.response.send_message(embed=embed)
        except Exception as e:
            await mi.response.send_message(embed=error_embed("Failed", str(e)), ephemeral=True)

    # /mod unban ─────────────────────────────────────────────────────────────

    @mod.subcommand(name="unban", description="Unban a user by ID")
    @is_staff()
    async def mod_unban(self, interaction):
        modal = stoat.Modal(title="Unban User")
        modal.add_item(stoat.TextInput(custom_id="user_id", label="User ID", placeholder="123456789012345678", required=True, max_length=20))
        modal.add_item(stoat.TextInput(custom_id="reason",  label="Reason",  placeholder="Reason for unban",   required=False, max_length=500))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        user_id = _field(mi, "user_id")
        reason  = _field(mi, "reason") or "No reason provided"
        try:
            await interaction.server.unban(user_id)
            await self.db.log_mod_action(interaction.server.id, user_id, interaction.user.id, "unban", reason)
            await mi.response.send_message(embed=success_embed("User Unbanned", f"User `{user_id}` has been unbanned."))
        except Exception as e:
            await mi.response.send_message(embed=error_embed("Failed", str(e)), ephemeral=True)

    # /mod mute ──────────────────────────────────────────────────────────────

    @mod.subcommand(name="mute", description="Mute a member (optionally with a duration)")
    @is_staff()
    async def mod_mute(self, interaction):
        modal = stoat.Modal(title="Mute Member")
        modal.add_item(stoat.TextInput(custom_id="user_id",  label="User ID",           placeholder="123456789012345678",  required=True,  max_length=20))
        modal.add_item(stoat.TextInput(custom_id="duration", label="Duration (optional)", placeholder="e.g. 30m, 1h, 1d — leave blank for permanent", required=False, max_length=20))
        modal.add_item(stoat.TextInput(custom_id="reason",   label="Reason",             placeholder="Reason for mute",     required=False, max_length=500))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        user_id      = _field(mi, "user_id")
        duration_str = _field(mi, "duration")
        reason       = _field(mi, "reason") or "No reason provided"

        cfg = await self.db.get_guild_config(interaction.server.id)
        mute_role_id = cfg.get("mute_role")
        if not mute_role_id:
            return await mi.response.send_message(
                embed=error_embed("Not Configured", "No mute role set. Use `/setup muterole` first."), ephemeral=True)

        duration_secs = None
        if duration_str:
            try:
                duration_secs = parse_duration(duration_str)
            except ValueError:
                return await mi.response.send_message(
                    embed=error_embed("Invalid Duration", "Use formats like `30m`, `1h`, `1d`."), ephemeral=True)

        try:
            guild  = self.bot.get_server(interaction.server.id)
            member = await guild.fetch_member(user_id)
            await member.add_role(mute_role_id)
            await self.db.log_mod_action(interaction.server.id, user_id, interaction.user.id, "mute", reason, duration_secs)
            if duration_secs:
                await self.db.add_timed_mute(interaction.server.id, user_id, utcnow() + timedelta(seconds=duration_secs))
            embed = success_embed("Member Muted",
                f"**User:** <@{user_id}>\n"
                f"**Duration:** {format_duration(duration_secs) if duration_secs else 'Permanent'}\n"
                f"**Reason:** {reason}\n**Moderator:** {interaction.user.mention}")
            await mi.response.send_message(embed=embed)
        except Exception as e:
            await mi.response.send_message(embed=error_embed("Failed", str(e)), ephemeral=True)

    # /mod unmute ────────────────────────────────────────────────────────────

    @mod.subcommand(name="unmute", description="Unmute a member")
    @is_staff()
    async def mod_unmute(self, interaction):
        modal = stoat.Modal(title="Unmute Member")
        modal.add_item(stoat.TextInput(custom_id="user_id", label="User ID", placeholder="123456789012345678", required=True,  max_length=20))
        modal.add_item(stoat.TextInput(custom_id="reason",  label="Reason",  placeholder="Reason for unmute",  required=False, max_length=500))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        user_id = _field(mi, "user_id")
        reason  = _field(mi, "reason") or "No reason provided"

        cfg = await self.db.get_guild_config(interaction.server.id)
        mute_role_id = cfg.get("mute_role")
        if not mute_role_id:
            return await mi.response.send_message(embed=error_embed("Not Configured", "No mute role set."), ephemeral=True)

        try:
            guild  = self.bot.get_server(interaction.server.id)
            member = await guild.fetch_member(user_id)
            await member.remove_role(mute_role_id)
            await self.db.remove_timed_mute(interaction.server.id, user_id)
            await self.db.log_mod_action(interaction.server.id, user_id, interaction.user.id, "unmute", reason)
            await mi.response.send_message(embed=success_embed("Member Unmuted",
                f"**User:** <@{user_id}>\n**Reason:** {reason}\n**Moderator:** {interaction.user.mention}"))
        except Exception as e:
            await mi.response.send_message(embed=error_embed("Failed", str(e)), ephemeral=True)

    # /mod warn ──────────────────────────────────────────────────────────────

    @mod.subcommand(name="warn", description="Issue a warning to a member")
    @is_staff()
    async def mod_warn(self, interaction):
        modal = stoat.Modal(title="Warn Member")
        modal.add_item(stoat.TextInput(custom_id="user_id", label="User ID", placeholder="123456789012345678", required=True, max_length=20))
        modal.add_item(stoat.TextInput(custom_id="reason",  label="Reason",  placeholder="Reason for warning", required=True, max_length=500))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        user_id = _field(mi, "user_id")
        reason  = _field(mi, "reason")
        try:
            record   = await self.db.add_warning(interaction.server.id, user_id, interaction.user.id, reason)
            warnings = await self.db.get_warnings(interaction.server.id, user_id)
            await mi.response.send_message(embed=warn_embed(f"Warning Issued (#{record['id']})",
                f"**User:** <@{user_id}>\n**Reason:** {reason}\n"
                f"**Moderator:** {interaction.user.mention}\n**Total warnings:** {len(warnings)}"))
        except Exception as e:
            await mi.response.send_message(embed=error_embed("Failed", str(e)), ephemeral=True)

    # /mod purge ─────────────────────────────────────────────────────────────

    @mod.subcommand(name="purge", description="Delete messages in the current channel")
    @is_staff()
    async def mod_purge(self, interaction):
        modal = stoat.Modal(title="Purge Messages")
        modal.add_item(stoat.TextInput(custom_id="count",   label="Number of messages (1–100)", placeholder="10",                          required=True,  max_length=3))
        modal.add_item(stoat.TextInput(custom_id="user_id", label="Filter by User ID (optional)", placeholder="Leave blank for all messages", required=False, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        try:
            count = int(_field(mi, "count"))
            if not 1 <= count <= 100:
                raise ValueError
        except ValueError:
            return await mi.response.send_message(embed=error_embed("Invalid Count", "Count must be between 1 and 100."), ephemeral=True)

        filter_id = _field(mi, "user_id") or None
        try:
            messages  = await interaction.channel.history(limit=count)
            to_delete = [m.id for m in messages if not filter_id or m.author.id == filter_id]
            deleted   = 0
            for mid in to_delete:
                try:
                    msg = await interaction.channel.fetch_message(mid)
                    await msg.delete()
                    deleted += 1
                except Exception:
                    pass
            await mi.response.send_message(embed=success_embed("Purged", f"Deleted **{deleted}** messages."), ephemeral=True)
        except Exception as e:
            await mi.response.send_message(embed=error_embed("Failed", str(e)), ephemeral=True)

    # /mod modlogs ───────────────────────────────────────────────────────────

    @mod.subcommand(name="modlogs", description="View moderation history for a member")
    @is_staff()
    async def mod_modlogs(self, interaction):
        modal = stoat.Modal(title="View Mod Logs")
        modal.add_item(stoat.TextInput(custom_id="user_id", label="User ID", placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        user_id = _field(mi, "user_id")
        try:
            async with self.db.pool.acquire() as conn:
                records = await conn.fetch(
                    "SELECT * FROM mod_actions WHERE guild_id=$1 AND target_id=$2 ORDER BY created_at DESC LIMIT 10",
                    interaction.server.id, user_id
                )
            if not records:
                return await mi.response.send_message(embed=info_embed("No Logs", f"No mod history for <@{user_id}>."), ephemeral=True)
            lines = [
                f"**{r['action'].upper()}** by <@{r['moderator_id']}> — {r['reason'] or 'No reason'} (<t:{int(r['created_at'].timestamp())}:R>)"
                for r in records
            ]
            await mi.response.send_message(embed=info_embed(f"Mod Logs — <@{user_id}>", "\n".join(lines)), ephemeral=True)
        except Exception as e:
            await mi.response.send_message(embed=error_embed("Failed", str(e)), ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    # /setup — Server configuration
    # ════════════════════════════════════════════════════════════════════════

    @stoat.slash_command(name="setup")
    @is_staff()
    async def setup_cmd(self, interaction):
        """Server setup commands."""
        pass

    @setup_cmd.subcommand(name="muterole", description="Set the mute role for this server")
    @is_staff()
    async def setup_muterole(self, interaction):
        modal = stoat.Modal(title="Set Mute Role")
        modal.add_item(stoat.TextInput(custom_id="role_id", label="Role ID", placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        role_id = _field(mi, "role_id")
        await self.db.set_guild_config(interaction.server.id, mute_role=role_id)
        await mi.response.send_message(embed=success_embed("Mute Role Set", f"Mute role set to <@&{role_id}>"), ephemeral=True)

    @setup_cmd.subcommand(name="staffrole", description="Set the staff/mod role for this server")
    @is_staff()
    async def setup_staffrole(self, interaction):
        modal = stoat.Modal(title="Set Staff Role")
        modal.add_item(stoat.TextInput(custom_id="role_id", label="Role ID", placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        role_id = _field(mi, "role_id")
        await self.db.set_guild_config(interaction.server.id, staff_role=role_id)
        await mi.response.send_message(embed=success_embed("Staff Role Set", f"Staff role set to <@&{role_id}>"), ephemeral=True)

    @setup_cmd.subcommand(name="logchannel", description="Set the moderation log channel")
    @is_staff()
    async def setup_logchannel(self, interaction):
        modal = stoat.Modal(title="Set Log Channel")
        modal.add_item(stoat.TextInput(custom_id="channel_id", label="Channel ID", placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        channel_id = _field(mi, "channel_id")
        await self.db.set_guild_config(interaction.server.id, log_channel=channel_id)
        await mi.response.send_message(embed=success_embed("Log Channel Set", f"Mod logs will go to <#{channel_id}>"), ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    # /giveaway — Giveaways
    # ════════════════════════════════════════════════════════════════════════

    @stoat.slash_command(name="giveaway")
    @is_staff()
    async def giveaway_slash(self, interaction):
        """Giveaway commands."""
        pass

    @giveaway_slash.subcommand(name="create", description="Create a new giveaway via a form")
    @is_staff()
    async def giveaway_create(self, interaction):
        modal = stoat.Modal(title="Create Giveaway")
        modal.add_item(stoat.TextInput(custom_id="prize",       label="Prize Description",            placeholder="e.g. $100 Amazon Gift Card",     required=True,  max_length=100))
        modal.add_item(stoat.TextInput(custom_id="description", label="Giveaway Description (optional)", placeholder="What is this giveaway about?", required=False, style=stoat.TextInputStyle.paragraph, max_length=500))
        modal.add_item(stoat.TextInput(custom_id="duration",    label="Duration",                     placeholder="e.g. 1h, 30m, 2d",               required=True,  max_length=20))
        modal.add_item(stoat.TextInput(custom_id="winners",     label="Number of Winners",            placeholder="e.g. 1",                         required=True,  max_length=2))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        prize        = _field(mi, "prize")
        description  = _field(mi, "description")
        duration_str = _field(mi, "duration")
        winners_str  = _field(mi, "winners", "1")

        try:
            duration_secs = parse_duration(duration_str)
        except ValueError:
            return await mi.response.send_message(embed=error_embed("Invalid Duration", "Use formats like `30m`, `2h`, `1d12h`."), ephemeral=True)

        try:
            winners = int(winners_str)
            if not 1 <= winners <= 20:
                raise ValueError
        except ValueError:
            return await mi.response.send_message(embed=error_embed("Invalid Winners", "Winner count must be between 1 and 20."), ephemeral=True)

        ends_at  = utcnow() + timedelta(seconds=duration_secs)
        giveaway = await self.db.create_giveaway(
            guild_id=interaction.server.id, channel_id=interaction.channel.id,
            host_id=interaction.user.id, prize=prize, winner_count=winners, ends_at=ends_at,
        )

        desc_line = f"\n**About:** {description}" if description else ""
        embed = stoat.SendableEmbed(
            title="🎉 GIVEAWAY 🎉",
            description=(
                f"**Prize:** {prize}{desc_line}\n"
                f"**Winners:** {winners}\n"
                f"**Hosted by:** {interaction.user.mention}\n"
                f"**Ends:** <t:{int(ends_at.timestamp())}:R> (<t:{int(ends_at.timestamp())}:f>)\n\n"
                "React with 🎉 to enter!"
            ),
            color="#FFD700",
        )
        msg = await interaction.channel.send(embeds=[embed])
        await self.db.set_giveaway_message(giveaway["id"], msg.id)
        try:
            await msg.add_reaction("🎉")
        except Exception:
            pass
        await mi.response.send_message(embed=success_embed("Giveaway Created", f"Your giveaway for **{prize}** is now live!"), ephemeral=True)

    @giveaway_slash.subcommand(name="end", description="End a giveaway early by message ID")
    @is_staff()
    async def giveaway_end(self, interaction):
        modal = stoat.Modal(title="End Giveaway")
        modal.add_item(stoat.TextInput(custom_id="message_id", label="Giveaway Message ID", placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        message_id = _field(mi, "message_id")
        giveaway   = await self.db.get_giveaway(message_id)
        if not giveaway:
            return await mi.response.send_message(embed=error_embed("Not Found", "No giveaway found with that message ID."), ephemeral=True)
        if giveaway["ended"]:
            return await mi.response.send_message(embed=error_embed("Already Ended", "This giveaway has already ended."), ephemeral=True)

        # Delegate end logic to the Giveaways cog if loaded
        giveaways_cog = self.bot.get_cog("Giveaways")
        if giveaways_cog:
            await giveaways_cog._end_giveaway(giveaway)
        await mi.response.send_message(embed=success_embed("Giveaway Ended", f"Giveaway for **{giveaway['prize']}** ended."), ephemeral=True)

    @giveaway_slash.subcommand(name="reroll", description="Reroll winner(s) for an ended giveaway")
    @is_staff()
    async def giveaway_reroll(self, interaction):
        modal = stoat.Modal(title="Reroll Giveaway")
        modal.add_item(stoat.TextInput(custom_id="message_id", label="Giveaway Message ID", placeholder="123456789012345678", required=True, max_length=20))
        modal.add_item(stoat.TextInput(custom_id="count",      label="Number of winners to reroll", placeholder="1",          required=False, max_length=2))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        message_id = _field(mi, "message_id")
        count_str  = _field(mi, "count", "1")
        giveaway   = await self.db.get_giveaway(message_id)
        if not giveaway:
            return await mi.response.send_message(embed=error_embed("Not Found", "No giveaway found with that message ID."), ephemeral=True)
        if not giveaway["ended"]:
            return await mi.response.send_message(embed=error_embed("Still Active", "This giveaway hasn't ended yet."), ephemeral=True)

        entries   = await self.db.get_giveaway_entries(giveaway["id"])
        entry_ids = [e["user_id"] for e in entries]
        if not entry_ids:
            return await mi.response.send_message(embed=warn_embed("No Entries", "No entries to reroll from."), ephemeral=True)

        count   = min(int(count_str or 1), len(entry_ids))
        winners = random.sample(entry_ids, count)
        winner_mentions = " ".join(f"<@{w}>" for w in winners)
        await mi.response.send_message(embed=stoat.SendableEmbed(
            title="🎲 Giveaway Rerolled!",
            description=f"New winner(s) for **{giveaway['prize']}**: {winner_mentions}",
            color="#FFD700",
        ))

    @giveaway_slash.subcommand(name="info", description="Show info about a giveaway by message ID")
    async def giveaway_info(self, interaction):
        modal = stoat.Modal(title="Giveaway Info")
        modal.add_item(stoat.TextInput(custom_id="message_id", label="Giveaway Message ID", placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        message_id = _field(mi, "message_id")
        giveaway   = await self.db.get_giveaway(message_id)
        if not giveaway:
            return await mi.response.send_message(embed=error_embed("Not Found", "No giveaway found with that message ID."), ephemeral=True)

        entries      = await self.db.get_giveaway_entries(giveaway["id"])
        status       = "✅ Ended" if giveaway["ended"] else "🔄 Active"
        winners_text = ", ".join(f"<@{w}>" for w in (giveaway["winners"] or [])) or "None yet"
        await mi.response.send_message(embed=stoat.SendableEmbed(
            title=f"🎉 Giveaway — {giveaway['prize']}",
            description=(
                f"**Status:** {status}\n**Entries:** {len(entries)}\n"
                f"**Winners:** {winners_text}\n**Hosted by:** <@{giveaway['host_id']}>\n"
                f"**Ends/Ended:** <t:{int(giveaway['ends_at'].timestamp())}:f>"
            ),
            color="#FFD700",
        ), ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    # /ticket — Ticket system
    # ════════════════════════════════════════════════════════════════════════

    @stoat.slash_command(name="ticket")
    @is_staff()
    async def ticket_slash(self, interaction):
        """Ticket management commands."""
        pass

    @ticket_slash.subcommand(name="setup", description="Configure the ticket system")
    @is_staff()
    async def ticket_setup(self, interaction):
        modal = stoat.Modal(title="Ticket System Setup")
        modal.add_item(stoat.TextInput(custom_id="log_channel", label="Log Channel ID (optional)", placeholder="Leave blank to use current channel", required=False, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        log_channel = _field(mi, "log_channel") or interaction.channel.id
        await self.db.set_guild_config(interaction.server.id, ticket_log_channel=log_channel)
        await mi.response.send_message(embed=success_embed("Ticket System Configured", f"Log channel set to <#{log_channel}>"), ephemeral=True)

    @ticket_slash.subcommand(name="addcategory", description="Add a ticket category")
    @is_staff()
    async def ticket_addcategory(self, interaction):
        modal = stoat.Modal(title="Add Ticket Category")
        modal.add_item(stoat.TextInput(custom_id="name",        label="Category Name",        placeholder="e.g. Support",    required=True,  max_length=50))
        modal.add_item(stoat.TextInput(custom_id="emoji",       label="Emoji",                placeholder="e.g. 🎫",         required=False, max_length=10))
        modal.add_item(stoat.TextInput(custom_id="description", label="Description",          placeholder="What is it for?", required=False, max_length=200))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        name        = _field(mi, "name")
        emoji       = _field(mi, "emoji") or "🎫"
        description = _field(mi, "description")
        await self.db.add_ticket_category(interaction.server.id, name, description, emoji)
        await mi.response.send_message(embed=success_embed("Category Added", f"{emoji} **{name}** — {description}"), ephemeral=True)

    @ticket_slash.subcommand(name="list", description="List all open tickets")
    @is_staff()
    async def ticket_list(self, interaction):
        async with self.db.pool.acquire() as conn:
            tickets = await conn.fetch(
                "SELECT * FROM tickets WHERE guild_id=$1 AND status='open' ORDER BY opened_at DESC",
                interaction.server.id
            )
        if not tickets:
            return await interaction.response.send_message(embed=info_embed("Open Tickets", "No open tickets."), ephemeral=True)
        lines = [f"#{t['id']} — <@{t['user_id']}> | {t['category']} | <#{t['channel_id']}>" for t in tickets]
        await interaction.response.send_message(embed=info_embed(f"Open Tickets ({len(tickets)})", "\n".join(lines)), ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    # /welcome — Welcome system
    # ════════════════════════════════════════════════════════════════════════

    @stoat.slash_command(name="welcome")
    @is_staff()
    async def welcome_slash(self, interaction):
        """Welcome system commands."""
        pass

    @welcome_slash.subcommand(name="setchannel", description="Set the welcome channel")
    @is_staff()
    async def welcome_setchannel(self, interaction):
        modal = stoat.Modal(title="Set Welcome Channel")
        modal.add_item(stoat.TextInput(custom_id="channel_id", label="Channel ID", placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        channel_id = _field(mi, "channel_id")
        await self.db.set_guild_config(interaction.server.id, welcome_channel=channel_id)
        await mi.response.send_message(embed=success_embed("Welcome Channel Set", f"Welcome messages will go to <#{channel_id}>"), ephemeral=True)

    @welcome_slash.subcommand(name="setmessage", description="Set the welcome message")
    @is_staff()
    async def welcome_setmessage(self, interaction):
        modal = stoat.Modal(title="Set Welcome Message")
        modal.add_item(stoat.TextInput(
            custom_id="message", label="Welcome Message",
            placeholder="Welcome to **{server}**, {user}! You are member #{count}.",
            required=True, style=stoat.TextInputStyle.paragraph, max_length=1000,
        ))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        message = _field(mi, "message")
        await self.db.set_guild_config(interaction.server.id, welcome_message=message)
        await mi.response.send_message(embed=success_embed("Welcome Message Set",
            f"New message:\n{message}\n\n**Placeholders:** `{{user}}` `{{username}}` `{{server}}` `{{count}}` `{{id}}`"), ephemeral=True)

    @welcome_slash.subcommand(name="test", description="Preview the welcome message in the current channel")
    @is_staff()
    async def welcome_test(self, interaction):
        cfg = await self.db.get_guild_config(interaction.server.id)
        template = cfg.get("welcome_message") or "Welcome to **{server}**, {user}! 🎉 You are member #{count}."
        message = (template
            .replace("{user}", interaction.user.mention)
            .replace("{username}", interaction.user.name)
            .replace("{server}", interaction.server.name)
            .replace("{count}", "???")
            .replace("{id}", interaction.user.id))
        await interaction.response.send_message(
            embed=stoat.SendableEmbed(title="👋 Welcome! (Preview)", description=message, color="#57F287"))

    # ════════════════════════════════════════════════════════════════════════
    # /autorole — Auto roles
    # ════════════════════════════════════════════════════════════════════════

    @stoat.slash_command(name="autorole")
    @is_staff()
    async def autorole_slash(self, interaction):
        """Auto role commands."""
        pass

    @autorole_slash.subcommand(name="add", description="Add a role to be assigned on member join")
    @is_staff()
    async def autorole_add(self, interaction):
        modal = stoat.Modal(title="Add Auto Role")
        modal.add_item(stoat.TextInput(custom_id="role_id", label="Role ID", placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        role_id = _field(mi, "role_id")
        await self.db.add_auto_role(interaction.server.id, role_id)
        await mi.response.send_message(embed=success_embed("Auto Role Added", f"<@&{role_id}> will be assigned on join."), ephemeral=True)

    @autorole_slash.subcommand(name="remove", description="Remove an auto role")
    @is_staff()
    async def autorole_remove(self, interaction):
        modal = stoat.Modal(title="Remove Auto Role")
        modal.add_item(stoat.TextInput(custom_id="role_id", label="Role ID", placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        role_id = _field(mi, "role_id")
        await self.db.remove_auto_role(interaction.server.id, role_id)
        await mi.response.send_message(embed=success_embed("Auto Role Removed", f"<@&{role_id}> removed."), ephemeral=True)

    @autorole_slash.subcommand(name="list", description="List all auto roles")
    @is_staff()
    async def autorole_list(self, interaction):
        roles = await self.db.get_auto_roles(interaction.server.id)
        if not roles:
            return await interaction.response.send_message(embed=info_embed("Auto Roles", "No auto roles configured."), ephemeral=True)
        role_list = "\n".join(f"• <@&{r['role_id']}>" for r in roles)
        await interaction.response.send_message(embed=info_embed("Auto Roles", role_list), ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    # /reactionrole — Reaction roles
    # ════════════════════════════════════════════════════════════════════════

    @stoat.slash_command(name="reactionrole")
    @is_staff()
    async def reactionrole_slash(self, interaction):
        """Reaction role commands."""
        pass

    @reactionrole_slash.subcommand(name="add", description="Add a reaction role to a message")
    @is_staff()
    async def rr_add(self, interaction):
        modal = stoat.Modal(title="Add Reaction Role")
        modal.add_item(stoat.TextInput(custom_id="message_id", label="Message ID",  placeholder="123456789012345678",          required=True,  max_length=20))
        modal.add_item(stoat.TextInput(custom_id="emoji",      label="Emoji",       placeholder="e.g. ✅",                     required=True,  max_length=20))
        modal.add_item(stoat.TextInput(custom_id="role_id",    label="Role ID",     placeholder="123456789012345678",          required=True,  max_length=20))
        modal.add_item(stoat.TextInput(custom_id="mode",       label="Mode",        placeholder="toggle / add / remove  (default: toggle)", required=False, max_length=10))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        message_id = _field(mi, "message_id")
        emoji      = _field(mi, "emoji")
        role_id    = _field(mi, "role_id")
        mode       = _field(mi, "mode") or "toggle"

        if mode not in ("toggle", "add", "remove"):
            return await mi.response.send_message(embed=error_embed("Invalid Mode", "Mode must be `toggle`, `add`, or `remove`."), ephemeral=True)

        await self.db.add_reaction_role(interaction.server.id, interaction.channel.id, message_id, emoji, role_id, mode)
        await mi.response.send_message(embed=success_embed("Reaction Role Added",
            f"React with {emoji} on message `{message_id}` → <@&{role_id}> (mode: `{mode}`)"), ephemeral=True)

    @reactionrole_slash.subcommand(name="remove", description="Remove a reaction role")
    @is_staff()
    async def rr_remove(self, interaction):
        modal = stoat.Modal(title="Remove Reaction Role")
        modal.add_item(stoat.TextInput(custom_id="message_id", label="Message ID", placeholder="123456789012345678", required=True, max_length=20))
        modal.add_item(stoat.TextInput(custom_id="emoji",      label="Emoji",      placeholder="e.g. ✅",           required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        message_id = _field(mi, "message_id")
        emoji      = _field(mi, "emoji")
        await self.db.remove_reaction_role(message_id, emoji)
        await mi.response.send_message(embed=success_embed("Reaction Role Removed", f"Removed {emoji} from message `{message_id}`"), ephemeral=True)

    @reactionrole_slash.subcommand(name="list", description="List all reaction roles in this server")
    @is_staff()
    async def rr_list(self, interaction):
        rrs = await self.db.get_all_reaction_roles(interaction.server.id)
        if not rrs:
            return await interaction.response.send_message(embed=info_embed("Reaction Roles", "No reaction roles configured."), ephemeral=True)
        lines = [
            f"{r['emoji']} on `{r['message_id']}` → <@&{r['role_id']}> (mode: `{r['mode']}`)"
            for r in rrs
        ]
        await interaction.response.send_message(embed=info_embed(f"Reaction Roles ({len(rrs)})", "\n".join(lines)), ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    # /role — Role management
    # ════════════════════════════════════════════════════════════════════════

    @stoat.slash_command(name="role")
    @is_staff()
    async def role_slash(self, interaction):
        """Role management commands."""
        pass

    @role_slash.subcommand(name="give", description="Give a role to a member")
    @is_staff()
    async def role_give(self, interaction):
        modal = stoat.Modal(title="Give Role")
        modal.add_item(stoat.TextInput(custom_id="user_id", label="User ID",  placeholder="123456789012345678", required=True, max_length=20))
        modal.add_item(stoat.TextInput(custom_id="role_id", label="Role ID",  placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        user_id = _field(mi, "user_id")
        role_id = _field(mi, "role_id")
        try:
            guild  = self.bot.get_server(interaction.server.id)
            member = await guild.fetch_member(user_id)
            await member.add_role(role_id)
            await mi.response.send_message(embed=success_embed("Role Given", f"<@&{role_id}> given to <@{user_id}>"), ephemeral=True)
        except Exception as e:
            await mi.response.send_message(embed=error_embed("Failed", str(e)), ephemeral=True)

    @role_slash.subcommand(name="take", description="Remove a role from a member")
    @is_staff()
    async def role_take(self, interaction):
        modal = stoat.Modal(title="Take Role")
        modal.add_item(stoat.TextInput(custom_id="user_id", label="User ID",  placeholder="123456789012345678", required=True, max_length=20))
        modal.add_item(stoat.TextInput(custom_id="role_id", label="Role ID",  placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        user_id = _field(mi, "user_id")
        role_id = _field(mi, "role_id")
        try:
            guild  = self.bot.get_server(interaction.server.id)
            member = await guild.fetch_member(user_id)
            await member.remove_role(role_id)
            await mi.response.send_message(embed=success_embed("Role Removed", f"<@&{role_id}> removed from <@{user_id}>"), ephemeral=True)
        except Exception as e:
            await mi.response.send_message(embed=error_embed("Failed", str(e)), ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    # /automod — Auto moderation
    # ════════════════════════════════════════════════════════════════════════

    @stoat.slash_command(name="automod")
    @is_staff()
    async def automod_slash(self, interaction):
        """Automod configuration commands."""
        pass

    @automod_slash.subcommand(name="spam", description="Configure anti-spam settings")
    @is_staff()
    async def automod_spam(self, interaction):
        modal = stoat.Modal(title="Configure Anti-Spam")
        modal.add_item(stoat.TextInput(custom_id="enabled",   label="Enable anti-spam?",        placeholder="true / false",          required=True,  max_length=5))
        modal.add_item(stoat.TextInput(custom_id="threshold", label="Message threshold",         placeholder="5  (messages)",         required=False, max_length=3))
        modal.add_item(stoat.TextInput(custom_id="interval",  label="Interval (seconds)",        placeholder="5  (seconds)",          required=False, max_length=3))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return

        enabled   = _field(mi, "enabled").lower() in ("true", "yes", "1", "on")
        threshold = int(_field(mi, "threshold") or 5)
        interval  = int(_field(mi, "interval")  or 5)
        await self.db.set_automod_config(interaction.server.id, anti_spam=enabled, spam_threshold=threshold, spam_interval=interval)
        await mi.response.send_message(embed=success_embed("Anti-Spam Updated",
            f"Anti-spam {'enabled' if enabled else 'disabled'}. Triggers after **{threshold}** messages in **{interval}s**."), ephemeral=True)

    @automod_slash.subcommand(name="invite", description="Enable or disable the anti-invite filter")
    @is_staff()
    async def automod_invite(self, interaction):
        modal = stoat.Modal(title="Anti-Invite Filter")
        modal.add_item(stoat.TextInput(custom_id="enabled", label="Enable anti-invite?", placeholder="true / false", required=True, max_length=5))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        enabled = _field(mi, "enabled").lower() in ("true", "yes", "1", "on")
        await self.db.set_automod_config(interaction.server.id, anti_invite=enabled)
        await mi.response.send_message(embed=success_embed("Anti-Invite Updated", f"Anti-invite {'enabled' if enabled else 'disabled'}."), ephemeral=True)

    @automod_slash.subcommand(name="caps", description="Configure the caps filter")
    @is_staff()
    async def automod_caps(self, interaction):
        modal = stoat.Modal(title="Anti-Caps Filter")
        modal.add_item(stoat.TextInput(custom_id="enabled",   label="Enable anti-caps?",       placeholder="true / false",   required=True,  max_length=5))
        modal.add_item(stoat.TextInput(custom_id="threshold", label="Caps % threshold",         placeholder="70  (percent)",  required=False, max_length=3))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        enabled   = _field(mi, "enabled").lower() in ("true", "yes", "1", "on")
        threshold = int(_field(mi, "threshold") or 70)
        await self.db.set_automod_config(interaction.server.id, anti_caps=enabled, caps_threshold=threshold)
        await mi.response.send_message(embed=success_embed("Anti-Caps Updated",
            f"Anti-caps {'enabled' if enabled else 'disabled'} (threshold: {threshold}%)."), ephemeral=True)

    @automod_slash.subcommand(name="badword_add", description="Add a word to the blocked list")
    @is_staff()
    async def automod_badword_add(self, interaction):
        modal = stoat.Modal(title="Add Blocked Word")
        modal.add_item(stoat.TextInput(custom_id="word", label="Word to block", placeholder="e.g. badword", required=True, max_length=100))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        word = _field(mi, "word").lower()
        cfg  = await self.db.get_automod_config(interaction.server.id)
        words = list(cfg["bad_words"] or []) if cfg else []
        if word not in words:
            words.append(word)
        await self.db.set_automod_config(interaction.server.id, bad_words=words)
        await mi.response.send_message(embed=success_embed("Word Added", f"`{word}` added to blocked words."), ephemeral=True)

    @automod_slash.subcommand(name="badword_remove", description="Remove a word from the blocked list")
    @is_staff()
    async def automod_badword_remove(self, interaction):
        modal = stoat.Modal(title="Remove Blocked Word")
        modal.add_item(stoat.TextInput(custom_id="word", label="Word to remove", placeholder="e.g. badword", required=True, max_length=100))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        word  = _field(mi, "word").lower()
        cfg   = await self.db.get_automod_config(interaction.server.id)
        words = list(cfg["bad_words"] or []) if cfg else []
        if word in words:
            words.remove(word)
        await self.db.set_automod_config(interaction.server.id, bad_words=words)
        await mi.response.send_message(embed=success_embed("Word Removed", f"`{word}` removed from blocked words."), ephemeral=True)

    @automod_slash.subcommand(name="status", description="Show current automod configuration")
    @is_staff()
    async def automod_status(self, interaction):
        cfg = await self.db.get_automod_config(interaction.server.id)
        if not cfg:
            return await interaction.response.send_message(embed=info_embed("Automod", "No automod configured yet."), ephemeral=True)
        await interaction.response.send_message(embed=info_embed("Automod Config",
            f"**Anti-spam:** {'✅' if cfg['anti_spam'] else '❌'} ({cfg['spam_threshold']} msgs / {cfg['spam_interval']}s)\n"
            f"**Anti-invite:** {'✅' if cfg['anti_invite'] else '❌'}\n"
            f"**Anti-caps:** {'✅' if cfg['anti_caps'] else '❌'} ({cfg['caps_threshold']}%)\n"
            f"**Blocked words:** {len(cfg['bad_words'] or [])} words"
        ), ephemeral=True)

    # ════════════════════════════════════════════════════════════════════════
    # /logs — Audit logging
    # ════════════════════════════════════════════════════════════════════════

    @stoat.slash_command(name="logs")
    @is_staff()
    async def logs_slash(self, interaction):
        """Logging configuration commands."""
        pass

    @logs_slash.subcommand(name="setchannel", description="Set the audit log channel")
    @is_staff()
    async def logs_setchannel(self, interaction):
        modal = stoat.Modal(title="Set Log Channel")
        modal.add_item(stoat.TextInput(custom_id="channel_id", label="Channel ID", placeholder="123456789012345678", required=True, max_length=20))
        mi = await _wait_modal(self.bot, interaction, modal)
        if not mi:
            return
        channel_id = _field(mi, "channel_id")
        await self.db.set_guild_config(interaction.server.id, log_channel=channel_id)
        await mi.response.send_message(embed=success_embed("Log Channel Set", f"Logs will go to <#{channel_id}>"), ephemeral=True)

    @logs_slash.subcommand(name="disable", description="Disable audit logging")
    @is_staff()
    async def logs_disable(self, interaction):
        await self.db.set_guild_config(interaction.server.id, log_channel=None)
        await interaction.response.send_message(embed=success_embed("Logging Disabled", "Audit logs have been turned off."), ephemeral=True)

    @logs_slash.subcommand(name="status", description="Show current logging configuration")
    @is_staff()
    async def logs_status(self, interaction):
        cfg = await self.db.get_guild_config(interaction.server.id)
        ch  = cfg.get("log_channel")
        await interaction.response.send_message(embed=info_embed("Logging Config",
            f"**Log channel:** {f'<#{ch}>' if ch else 'Not set'}"
        ), ephemeral=True)


def setup(bot):
    bot.add_gear(SlashCommands(bot))
