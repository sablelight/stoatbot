import stoat
from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, utcnow, is_staff
from datetime import datetime, timezone, timedelta
import logging

log = logging.getLogger("timezone")

COMMON_TZ = {
    "utc": "UTC", "gmt": "UTC",
    "est": "US/Eastern", "edt": "US/Eastern",
    "cst": "US/Central", "cdt": "US/Central",
    "mst": "US/Mountain", "mdt": "US/Mountain",
    "pst": "US/Pacific", "pdt": "US/Pacific",
    "cet": "Europe/Paris", "cest": "Europe/Paris",
    "bst": "Europe/London",
    "ist": "Asia/Kolkata",
    "jst": "Asia/Tokyo",
    "aest": "Australia/Sydney", "aedt": "Australia/Sydney",
    "nzst": "Pacific/Auckland", "nzdt": "Pacific/Auckland",
}


class Timezone(commands.Gear):
    """Set your timezone and convert times."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @commands.group(invoke_without_command=True, name="time")
    @is_staff()
    async def time_group(self, ctx, member: stoat.Member = None):
        """Show the current time for a member or yourself."""
        target = member or ctx.author
        tz_name = await self.db.get_user_timezone(target.id)
        if not tz_name:
            return await ctx.send(embeds=[info_embed("Timezone Not Set",
                f"{target.mention} hasn't set their timezone. Use `settimezone <tz>`.")])
        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(tz_name)
            now = datetime.now(tz)
            await ctx.send(embeds=[info_embed(
                f"🕐 {target.name}'s Time",
                f"**{now.strftime('%A, %B %d, %Y %I:%M %p')}** ({tz_name})"
            )])
        except Exception:
            await ctx.send(embeds=[error_embed("Invalid Timezone", f"`{tz_name}` is not a valid timezone.")])

    @commands.command(aliases=["setz", "tzset"])
    @is_staff()
    async def settimezone(self, ctx, *, timezone_name: str):
        """Set your timezone (e.g. US/Eastern, Europe/London, Asia/Tokyo)."""
        tz = COMMON_TZ.get(timezone_name.upper().strip(), timezone_name.strip())
        try:
            import zoneinfo
            zoneinfo.ZoneInfo(tz)
        except Exception:
            return await ctx.send(embeds=[error_embed("Invalid Timezone",
                f"`{tz}` is not a valid timezone. Use IANA names like `US/Eastern`, `Europe/London`, `Asia/Tokyo`.")])
        await self.db.set_user_timezone(ctx.author.id, tz)
        await ctx.send(embeds=[success_embed("Timezone Set", f"Your timezone is now **{tz}**.")])

    @commands.command()
    @is_staff()
    async def mytimezone(self, ctx):
        """Show your current timezone."""
        tz = await self.db.get_user_timezone(ctx.author.id)
        if not tz:
            return await ctx.send(embeds=[info_embed("Timezone", "You haven't set a timezone yet.")])
        await ctx.send(embeds=[info_embed("Your Timezone", f"**{tz}**")])

    @commands.command(aliases=["deltz"])
    @is_staff()
    async def deletetimezone(self, ctx):
        """Delete your timezone."""
        await self.db.delete_user_timezone(ctx.author.id)
        await ctx.send(embeds=[success_embed("Timezone Deleted", "Your timezone has been removed.")])


async def setup(bot):
    await bot.add_gear(Timezone(bot))
