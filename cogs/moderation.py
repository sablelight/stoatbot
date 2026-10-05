import stoat
from stoat.ext import commands
from utils.helpers import (
    _delete_after,
    success_embed, error_embed, info_embed, warn_embed,
    parse_duration, format_duration, utcnow, is_staff
)
import asyncio
import logging
from datetime import timedelta

log = logging.getLogger("moderation")


class Moderation(commands.Gear):
    """Full moderation suite: kick, ban, mute, warn, purge, case history."""

    def __init__(self, bot):
        self.bot = bot
        self._mute_task = None

    def cog_load(self):
        self._mute_task = asyncio.create_task(self._unmute_loop())

    def cog_unload(self):
        if self._mute_task:
            self._mute_task.cancel()

    @property
    def db(self):
        return self.bot.db

    async def _send_log(self, guild_id, embed):
        cfg = await self.db.get_guild_config(guild_id)
        log_ch = cfg.get("log_channel")
        if log_ch:
            try:
                ch = await self.bot.fetch_channel(log_ch)
                await ch.send(embeds=[embed])
            except Exception:
                pass

    async def _unmute_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                expired = await self.db.get_expired_mutes()
                for record in expired:
                    guild = self.bot.get_server(record["guild_id"])
                    if not guild:
                        continue
                    cfg = await self.db.get_guild_config(record["guild_id"])
                    mute_role_id = cfg.get("mute_role")
                    if not mute_role_id:
                        continue
                    try:
                        member = await guild.fetch_member(record["user_id"])
                        if member:
                            current_roles = [r.id for r in member.roles]
                            new_roles = [r for r in current_roles if r != mute_role_id]
                            await member.edit(roles=new_roles)
                    except Exception:
                        pass
                    await self.db.remove_timed_mute(record["guild_id"], record["user_id"])
            except Exception as e:
                log.error(f"Unmute loop error: {e}")
            await asyncio.sleep(30)

    # ── Kick ───────────────────────────────────────────────────────────────

    @commands.command()
    @is_staff()
    async def kick(self, ctx, member: stoat.Member, *, reason: str = "No reason provided"):
        """Kick a member from the server."""
        if member.id == ctx.author.id:
            return await ctx.send(embeds=[error_embed("Error", "You can't kick yourself.")])
        try:
            await member.kick()
            await self.db.log_mod_action(ctx.server.id, member.id, ctx.author.id, "kick", reason)
            embed = success_embed("Member Kicked",
                f"**User:** {member.mention} (`{member.id}`)\n"
                f"**Reason:** {reason}\n"
                f"**Moderator:** {ctx.author.mention}"
            )
            await ctx.send(embeds=[embed])
            await self._send_log(ctx.server.id, embed)
        except Exception as e:
            await ctx.send(embeds=[error_embed("Failed", f"Could not kick member: {e}")])

    # ── Ban ────────────────────────────────────────────────────────────────

    @commands.command()
    @is_staff()
    async def ban(self, ctx, member: stoat.Member, *, reason: str = "No reason provided"):
        """Ban a member from the server."""
        if member.id == ctx.author.id:
            return await ctx.send(embeds=[error_embed("Error", "You can't ban yourself.")])
        try:
            await member.ban()
            await self.db.log_mod_action(ctx.server.id, member.id, ctx.author.id, "ban", reason)
            embed = success_embed("Member Banned",
                f"**User:** {member.mention} (`{member.id}`)\n"
                f"**Reason:** {reason}\n"
                f"**Moderator:** {ctx.author.mention}"
            )
            await ctx.send(embeds=[embed])
            await self._send_log(ctx.server.id, embed)
        except Exception as e:
            await ctx.send(embeds=[error_embed("Failed", f"Could not ban member: {e}")])

    @commands.command()
    @is_staff()
    async def unban(self, ctx, user_id: str, *, reason: str = "No reason provided"):
        """Unban a user by ID."""
        try:
            await ctx.server.unban(user_id)
            await self.db.log_mod_action(ctx.server.id, user_id, ctx.author.id, "unban", reason)
            await ctx.send(embeds=[success_embed("User Unbanned", f"User `{user_id}` has been unbanned.")])
        except Exception as e:
            await ctx.send(embeds=[error_embed("Failed", f"Could not unban: {e}")])

    # ── Mute ───────────────────────────────────────────────────────────────

    @commands.command()
    @is_staff()
    async def mute(self, ctx, member: stoat.Member, duration: str = None, *, reason: str = "No reason provided"):
        """
        Mute a member. Optionally specify a duration (e.g. 30m, 1h, 1d).
        Usage: !mute @user 1h Spamming
        """
        cfg = await self.db.get_guild_config(ctx.server.id)
        mute_role_id = cfg.get("mute_role")
        if not mute_role_id:
            return await ctx.send(embeds=[error_embed("Not Configured",
                "No mute role set. Use `!setmuterole <role_id>` first.")])

        duration_secs = None
        if duration:
            try:
                duration_secs = parse_duration(duration)
            except ValueError:
                # Treat as part of reason
                reason = f"{duration} {reason}".strip()

        try:
            current_roles = [r.id for r in member.roles]
            if mute_role_id not in current_roles:
                await member.edit(roles=current_roles + [mute_role_id])
            desc = (
                f"**User:** {member.mention} (`{member.id}`)\n"
                f"**Duration:** {format_duration(duration_secs) if duration_secs else 'Permanent'}\n"
                f"**Reason:** {reason}\n"
                f"**Moderator:** {ctx.author.mention}"
            )
            await self.db.log_mod_action(ctx.server.id, member.id, ctx.author.id, "mute", reason, duration_secs)

            if duration_secs:
                unmute_at = utcnow() + timedelta(seconds=duration_secs)
                await self.db.add_timed_mute(ctx.server.id, member.id, unmute_at)

            embed = success_embed("Member Muted", desc)
            await ctx.send(embeds=[embed])
            await self._send_log(ctx.server.id, embed)
        except Exception as e:
            await ctx.send(embeds=[error_embed("Failed", f"Could not mute member: {e}")])

    @commands.command()
    @is_staff()
    async def unmute(self, ctx, member: stoat.Member, *, reason: str = "No reason provided"):
        """Unmute a member."""
        cfg = await self.db.get_guild_config(ctx.server.id)
        mute_role_id = cfg.get("mute_role")
        if not mute_role_id:
            return await ctx.send(embeds=[error_embed("Not Configured", "No mute role set.")])
        try:
            current_roles = [r.id for r in member.roles]
            new_roles = [r for r in current_roles if r != mute_role_id]
            await member.edit(roles=new_roles)
            await self.db.remove_timed_mute(ctx.server.id, member.id)
            await self.db.log_mod_action(ctx.server.id, member.id, ctx.author.id, "unmute", reason)
            embed = success_embed("Member Unmuted",
                f"**User:** {member.mention}\n**Reason:** {reason}\n**Moderator:** {ctx.author.mention}")
            await ctx.send(embeds=[embed])
            await self._send_log(ctx.server.id, embed)
        except Exception as e:
            await ctx.send(embeds=[error_embed("Failed", f"Could not unmute: {e}")])

    # ── Warn ───────────────────────────────────────────────────────────────

    @commands.command()
    @is_staff()
    async def warn(self, ctx, member: stoat.Member, *, reason: str):
        """Issue a warning to a member."""
        record = await self.db.add_warning(ctx.server.id, member.id, ctx.author.id, reason)
        warnings = await self.db.get_warnings(ctx.server.id, member.id)
        embed = warn_embed(f"Warning Issued (#{record['id']})",
            f"**User:** {member.mention}\n"
            f"**Reason:** {reason}\n"
            f"**Moderator:** {ctx.author.mention}\n"
            f"**Total warnings:** {len(warnings)}"
        )
        await ctx.send(embeds=[embed])
        await self._send_log(ctx.server.id, embed)

    @commands.command()
    @is_staff()
    async def warnings(self, ctx, member: stoat.Member):
        """View all warnings for a member."""
        warns = await self.db.get_warnings(ctx.server.id, member.id)
        if not warns:
            return await ctx.send(embeds=[info_embed("No Warnings", f"{member.mention} has no warnings.")])
        lines = [f"**#{w['id']}** — {w['reason']} (by <@{w['moderator_id']}>, <t:{int(w['created_at'].timestamp())}:R>)" for w in warns]
        await ctx.send(embeds=[info_embed(f"Warnings for {member.name} ({len(warns)})", "\n".join(lines))])

    @commands.command()
    @is_staff()
    async def delwarn(self, ctx, warning_id: int):
        """Delete a warning by ID."""
        await self.db.remove_warning(warning_id)
        await ctx.send(embeds=[success_embed("Warning Removed", f"Warning #{warning_id} deleted.")])

    # ── Purge ──────────────────────────────────────────────────────────────

    @commands.command()
    @is_staff()
    async def purge(self, ctx, count: int):
        """Delete up to 100 messages from anyone."""
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if count < 1 or count > 100:
            return await ctx.send(embeds=[error_embed("Invalid Count", "Count must be between 1 and 100.")])
        try:
            messages = await ctx.channel.history(limit=count)
            deleted = 0
            for msg in messages:
                try:
                    await msg.delete()
                    deleted += 1
                except Exception:
                    pass
            _msg = await ctx.send(embeds=[success_embed("Purged", f"Deleted **{deleted}** messages.")])
            asyncio.create_task(_delete_after(_msg, 5))
        except Exception as e:
            await ctx.send(embeds=[error_embed("Failed", str(e))])

    @commands.command()
    @is_staff()
    async def purgefrom(self, ctx, member: stoat.Member, count: int = 100):
        """Delete up to 100 messages from a specific member."""
        try:
            await ctx.message.delete()
        except Exception:
            pass
        if count < 1 or count > 100:
            return await ctx.send(embeds=[error_embed("Invalid Count", "Count must be between 1 and 100.")])
        try:
            messages = await ctx.channel.history(limit=100)
            deleted = 0
            for msg in messages:
                if msg.author.id == member.id:
                    try:
                        await msg.delete()
                        deleted += 1
                    except Exception:
                        pass
                    if deleted >= count:
                        break
            _msg = await ctx.send(embeds=[success_embed("Purged", f"Deleted **{deleted}** messages from {member.mention}.")])
            asyncio.create_task(_delete_after(_msg, 5))
        except Exception as e:
            await ctx.send(embeds=[error_embed("Failed", str(e))])

    @commands.command()
    @is_staff()
    async def purgeall(self, ctx):
        """Delete all messages in the channel."""
        try:
            await ctx.message.delete()
        except Exception:
            pass
        deleted = 0
        before = None
        while True:
            try:
                kwargs = {"limit": 100}
                if before is not None:
                    kwargs["before"] = before.id if hasattr(before, "id") else before
                messages = await ctx.channel.history(**kwargs)
                if not messages:
                    break
                for msg in messages:
                    try:
                        await msg.delete()
                        deleted += 1
                    except Exception:
                        pass
                if len(messages) < 100:
                    break
                before = messages[-1]
            except Exception:
                break
        _msg = await ctx.send(embeds=[success_embed("Purge All", f"Deleted **{deleted}** messages.")])
        asyncio.create_task(_delete_after(_msg, 5))

    # ── Mod history ────────────────────────────────────────────────────────

    @commands.command()
    @is_staff()
    async def modlogs(self, ctx, member: stoat.Member):
        """View moderation history for a member."""
        async with self.db.pool.acquire() as conn:
            records = await conn.fetch(
                "SELECT * FROM mod_actions WHERE guild_id=$1 AND target_id=$2 ORDER BY created_at DESC LIMIT 10",
                ctx.server.id, member.id
            )
        if not records:
            return await ctx.send(embeds=[info_embed("No Logs", f"No mod history for {member.mention}.")])
        lines = [
            f"**{r['action'].upper()}** by <@{r['moderator_id']}> — {r['reason'] or 'No reason'} (<t:{int(r['created_at'].timestamp())}:R>)"
            for r in records
        ]
        await ctx.send(embeds=[info_embed(f"Mod Logs — {member.name}", "\n".join(lines))])

    # ── Config ─────────────────────────────────────────────────────────────

    @commands.command()
    @is_staff()
    async def setmuterole(self, ctx, role_id: str):
        """Set the mute role for this server."""
        await self.db.set_guild_config(ctx.server.id, mute_role=role_id)
        await ctx.send(embeds=[success_embed("Mute Role Set", f"Mute role set to <@&{role_id}>")])

    @commands.command()
    @is_staff()
    async def setstaffrole(self, ctx, role_id: str):
        """Set the staff/mod role for this server."""
        await self.db.set_guild_config(ctx.server.id, staff_role=role_id)
        await ctx.send(embeds=[success_embed("Staff Role Set", f"Staff role set to <@&{role_id}>")])

    @commands.command()
    @is_staff()
    async def setlogchannel(self, ctx, channel_id: str):
        """Set the moderation log channel."""
        await self.db.set_guild_config(ctx.server.id, log_channel=channel_id)
        await ctx.send(embeds=[success_embed("Log Channel Set", f"Mod logs will go to <#{channel_id}>")])


async def setup(bot):
    await bot.add_gear(Moderation(bot))
