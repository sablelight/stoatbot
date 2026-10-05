import stoat
from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, warn_embed, is_staff
from datetime import datetime, timezone
import logging

log = logging.getLogger("reputation")

REP_COOLDOWN = 3600


class Reputation(commands.Gear):
    """Reputation system — give/take rep, leaderboards, and logs."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @commands.group(invoke_without_command=True)
    @is_staff()
    async def rep(self, ctx, member: stoat.Member = None):
        """Show your or another member's reputation."""
        target = member or ctx.author
        data = await self.db.get_rep(ctx.server.id, target.id)
        await ctx.send(embeds=[info_embed(
            f"Reputation: {target.name}",
            f"**{data['rep']}** rep points"
        )])

    @rep.command(name="give")
    async def rep_give(self, ctx, member: stoat.Member, *, reason: str = None):
        """Give +rep to a member."""
        if member.id == ctx.author.id:
            return await ctx.send(embeds=[error_embed("Nope", "You can't give rep to yourself.")])
        if member.bot:
            return await ctx.send(embeds=[error_embed("Nope", "You can't give rep to bots.")])

        giver_data = await self.db.get_rep(ctx.server.id, ctx.author.id)
        last_given = giver_data.get("last_given")
        if last_given:
            try:
                last_dt = datetime.fromisoformat(last_given) if isinstance(last_given, str) else last_given
                elapsed = (datetime.now(timezone.utc) - last_dt).total_seconds()
                if elapsed < REP_COOLDOWN:
                    remaining = int(REP_COOLDOWN - elapsed)
                    return await ctx.send(embeds=[warn_embed("Cooldown",
                        f"You can give rep again in {remaining // 60}m {remaining % 60}s.")])
            except Exception:
                pass

        await self.db.update_rep(ctx.server.id, member.id, 1)
        await self.db.update_rep(ctx.server.id, ctx.author.id, 0)
        await self.db.log_rep(ctx.server.id, ctx.author.id, member.id, 1, reason)
        await ctx.send(embeds=[success_embed("+rep", f"Gave +1 rep to {member.mention}")])

    @rep.command(name="take", aliases=["-"])
    async def rep_take(self, ctx, member: stoat.Member, *, reason: str = None):
        """Give -rep to a member."""
        await self.db.update_rep(ctx.server.id, member.id, -1)
        await self.db.log_rep(ctx.server.id, ctx.author.id, member.id, -1, reason)
        await ctx.send(embeds=[success_embed("-rep", f"Gave -1 rep to {member.mention}")])

    @rep.command(name="leaderboard", aliases=["lb", "top"])
    async def rep_leaderboard(self, ctx):
        """Show the reputation leaderboard."""
        top = await self.db.get_rep_leaderboard(ctx.server.id, 10)
        if not top:
            return await ctx.send(embeds=[info_embed("Rep Leaderboard", "No rep data yet.")])
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(top):
            prefix = medals[i] if i < 3 else f"`#{i + 1:2}`"
            lines.append(f"{prefix} <@{row['user_id']}> — **{row['rep']}** rep")
        await ctx.send(embeds=[info_embed("Rep Leaderboard", "\n".join(lines))])

    @rep.command(name="log", aliases=["logs"])
    async def rep_log(self, ctx, member: stoat.Member = None):
        """Show the rep log for a member."""
        target = member or ctx.author
        entries = await self.db.get_rep_log(ctx.server.id, target.id, 10)
        if not entries:
            return await ctx.send(embeds=[info_embed(f"Rep Log: {target.name}", "No entries yet.")])
        lines = []
        for e in entries:
            sign = "+" if e["delta"] > 0 else ""
            reason = f": {e['reason']}" if e.get("reason") else ""
            lines.append(f"`{sign}{e['delta']}` by <@{e['giver_id']}>{reason}")
        await ctx.send(embeds=[info_embed(f"Rep Log: {target.name} (last 10)", "\n".join(lines))])

    @rep.command(name="set")
    @is_staff()
    async def rep_set(self, ctx, member: stoat.Member, value: int):
        """Set a member's rep to a specific value (staff only)."""
        await self.db.set_rep(ctx.server.id, member.id, value)
        await ctx.send(embeds=[success_embed("Rep Set", f"{member.mention} now has {value} rep.")])

    @rep.command(name="delete", aliases=["del"])
    @is_staff()
    async def rep_delete(self, ctx, member: stoat.Member):
        """Delete a member from the rep system entirely (staff only)."""
        await self.db.delete_rep(ctx.server.id, member.id)
        await ctx.send(embeds=[success_embed("Rep Deleted", f"Removed {member.mention} from the rep system.")])


async def setup(bot):
    await bot.add_gear(Reputation(bot))
