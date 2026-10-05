import stoat
from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, parse_duration, format_duration, utcnow, is_staff
from datetime import datetime, timedelta, timezone
import logging
import asyncio

log = logging.getLogger("reminders")


class Reminders(commands.Gear):
    """Set and manage reminders."""

    def __init__(self, bot):
        self.bot = bot
        self._task = None

    @property
    def db(self):
        return self.bot.db

    async def gear_start(self):
        self._task = asyncio.create_task(self._reminder_loop())

    async def gear_stop(self):
        if self._task:
            self._task.cancel()
            self._task = None

    async def _reminder_loop(self):
        await asyncio.sleep(10)
        while True:
            try:
                due = await self.db.get_due_reminders()
                for r in due:
                    try:
                        channel = self.bot.get_channel(r["channel_id"])
                        if channel:
                            await channel.send(
                                content=f"<@{r['user_id']}> ⏰ Reminder: {r['message']}"
                            )
                    except Exception as e:
                        log.debug(f"Failed to send reminder {r['id']}: {e}")
                    await self.db.delete_reminder(r["id"])
            except Exception as e:
                log.error(f"Reminder loop error: {e}")
            await asyncio.sleep(15)

    @commands.group(invoke_without_command=True)
    @is_staff()
    async def remindme(self, ctx, duration: str, *, message: str):
        """Set a reminder. Usage: remindme 1h30m your message here"""
        seconds = parse_duration(duration)
        if seconds < 30:
            return await ctx.send(embeds=[error_embed("Too Short", "Minimum duration is 30 seconds.")])
        if seconds > 86400 * 365:
            return await ctx.send(embeds=[error_embed("Too Long", "Maximum duration is 1 year.")])

        remind_at = utcnow() + timedelta(seconds=seconds)
        reminder = await self.db.create_reminder(
            ctx.server.id, ctx.channel.id, ctx.author.id, message,
            remind_at.isoformat()
        )
        await ctx.send(embeds=[success_embed("Reminder Set",
            f"I'll remind you in **{format_duration(seconds)}**: {message}")])

    @commands.command(aliases=["reminders"])
    @is_staff()
    async def listreminders(self, ctx):
        """List your active reminders."""
        reminders = await self.db.get_user_reminders(ctx.server.id, ctx.author.id)
        if not reminders:
            return await ctx.send(embeds=[info_embed("Reminders", "You have no active reminders.")])
        lines = []
        for r in reminders:
            try:
                dt = datetime.fromisoformat(r["remind_at"]) if isinstance(r["remind_at"], str) else r["remind_at"]
                remaining = (dt - utcnow()).total_seconds()
                time_str = format_duration(int(remaining)) if remaining > 0 else "any moment"
            except Exception:
                time_str = r["remind_at"]
            lines.append(f"`#{r['id']}` in **{time_str}** — {r['message']}")
        await ctx.send(embeds=[info_embed(f"Your Reminders ({len(reminders)})", "\n".join(lines))])

    @commands.command(aliases=["delreminder", "rmreminder"])
    @is_staff()
    async def deletereminder(self, ctx, reminder_id: int):
        """Delete a reminder by its ID."""
        await self.db.delete_reminder(reminder_id)
        await ctx.send(embeds=[success_embed("Reminder Deleted", f"Deleted reminder `#{reminder_id}`.")])


async def setup(bot):
    await bot.add_gear(Reminders(bot))
