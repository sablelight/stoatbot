import stoat
from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, utcnow, is_staff
import logging

log = logging.getLogger("logging_cog")


class Logging(commands.Gear):
    """Audit log: message edits, deletes, member join/leave, role changes."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    async def _get_log_channel(self, guild_id: str):
        cfg = await self.db.get_guild_config(guild_id)
        ch_id = cfg.get("log_channel")
        if not ch_id:
            return None
        try:
            return await self.bot.fetch_channel(ch_id)
        except Exception:
            return None

    # ── Message events ─────────────────────────────────────────────────────

    @commands.Gear.listener(to=stoat.MessageUpdateEvent)
    async def on_message_update(self, event: stoat.MessageUpdateEvent):
        try:
            before = event.before
            after = event.message
            if not before or not after:
                return
            if before.content == after.content:
                return
            if after.author and after.author.bot:
                return

            guild_id = after.server.id if after.server else (after.channel.server_id if hasattr(after.channel, 'server_id') else None)
            if not guild_id:
                return

            ch = await self._get_log_channel(guild_id)
            if not ch:
                return

            await ch.send(embeds=[stoat.SendableEmbed(
                title="✏️ Message Edited",
                description=(
                    f"**Author:** <@{after.author.id}>\n"
                    f"**Channel:** <#{after.channel.id}>\n"
                    f"**Before:** {before.content[:500] or '*(empty)*'}\n"
                    f"**After:** {after.content[:500] or '*(empty)*'}"
                ),
                color="#FEE75C",
            )])
        except Exception as e:
            log.debug(f"Message update log error: {e}")

    @commands.Gear.listener(to=stoat.MessageDeleteEvent)
    async def on_message_delete(self, event: stoat.MessageDeleteEvent):
        try:
            msg = event.message
            if not msg:
                return
            if msg.author and msg.author.bot:
                return

            guild_id = msg.server.id if msg.server else (msg.channel.server_id if hasattr(msg.channel, 'server_id') else None)
            if not guild_id:
                return

            ch = await self._get_log_channel(guild_id)
            if not ch:
                return

            await ch.send(embeds=[stoat.SendableEmbed(
                title="🗑️ Message Deleted",
                description=(
                    f"**Author:** <@{msg.author.id}>\n"
                    f"**Channel:** <#{msg.channel.id}>\n"
                    f"**Content:** {msg.content[:1000] or '*(empty or attachment)*'}"
                ),
                color="#ED4245",
            )])
        except Exception as e:
            log.debug(f"Message delete log error: {e}")

    # ── Member events ──────────────────────────────────────────────────────

    @commands.Gear.listener(to=stoat.ServerMemberJoinEvent)
    async def on_member_join(self, event: stoat.ServerMemberJoinEvent):
        try:
            member = event.member
            ch = await self._get_log_channel(member.server_id)
            if not ch:
                return
            created_at = getattr(member, "created_at", None)
            age_text = f"<t:{int(created_at.timestamp())}:R>" if created_at else "Unknown"
            await ch.send(embeds=[stoat.SendableEmbed(
                title="📥 Member Joined",
                description=(
                    f"**User:** {member.mention} (`{member.id}`)\n"
                    f"**Account created:** {age_text}"
                ),
                color="#57F287",
            )])
        except Exception as e:
            log.debug(f"Member join log error: {e}")

    @commands.Gear.listener(to=stoat.ServerMemberRemoveEvent)
    async def on_member_leave(self, event: stoat.ServerMemberRemoveEvent):
        try:
            server_id = event.server_id
            user_id = event.user_id
            member = event.member  # may be None if not cached
            ch = await self._get_log_channel(server_id)
            if not ch:
                return
            display = member.mention if member else f"<@{user_id}>"
            display_id = member.id if member else user_id
            await ch.send(embeds=[stoat.SendableEmbed(
                title="📤 Member Left",
                description=f"**User:** {display} (`{display_id}`)",
                color="#ED4245",
            )])
        except Exception as e:
            log.debug(f"Member leave log error: {e}")

    # ── Config ─────────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @is_staff()
    async def logs(self, ctx):
        """Logging configuration."""
        cfg = await self.db.get_guild_config(ctx.server.id)
        ch = cfg.get("log_channel")
        await ctx.send(embeds=[info_embed("Logging Config",
            f"**Log channel:** {f'<#{ch}>' if ch else 'Not set'}\n\n"
            "`logs setchannel <channel_id>` — set the log channel\n"
            "`logs disable` — disable logging"
        )])

    @logs.command()
    @is_staff()
    async def setchannel(self, ctx, channel_id: str):
        """Set the logging channel."""
        await self.db.set_guild_config(ctx.server.id, log_channel=channel_id)
        await ctx.send(embeds=[success_embed("Log Channel Set", f"Logs will go to <#{channel_id}>")])

    @logs.command()
    @is_staff()
    async def disable(self, ctx):
        """Disable logging."""
        await self.db.set_guild_config(ctx.server.id, log_channel=None)
        await ctx.send(embeds=[success_embed("Logging Disabled", "Audit logs have been turned off.")])


async def setup(bot):
    await bot.add_gear(Logging(bot))
