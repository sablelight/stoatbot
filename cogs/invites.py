import stoat
from stoat.ext import commands
from utils.helpers import error_embed, info_embed, is_staff
import asyncio
import logging

log = logging.getLogger("invites")

class Invites(commands.Gear):
    """Invite tracking system."""

    def __init__(self, bot):
        self.bot = bot
        self._task = None
        # In-memory cache: {guild_id: {code: creator_id}}
        self._invite_cache: dict[str, dict[str, str]] = {}

    @property
    def db(self):
        return self.bot.db

    def cog_load(self):
        self._task = asyncio.create_task(self._invite_sync_loop())

    def cog_unload(self):
        if self._task:
            self._task.cancel()

    async def _sync_invites(self, guild):
        try:
            invites = await guild.fetch_invites()
        except Exception:
            return

        codes = []
        cache = {}
        for inv in invites:
            codes.append({
                "code": inv.code,
                "creator_id": inv.creator_id,
                "channel_id": inv.channel_id,
            })
            cache[inv.code] = inv.creator_id

        await self.db.sync_invite_codes(guild.id, codes)
        self._invite_cache[guild.id] = cache

    async def _invite_sync_loop(self):
        await self.bot.wait_until_ready()
        # Initial sync for all servers
        for guild in self.bot.servers:
            await self._sync_invites(guild)

        while not self.bot.is_closed():
            await asyncio.sleep(60)
            try:
                for guild in self.bot.servers:
                    await self._sync_invites(guild)
            except Exception as e:
                log.error(f"Invite sync error: {e}")

    # ── Member events ──────────────────────────────────────────────────────

    @commands.Gear.listener(to=stoat.ServerMemberJoinEvent)
    async def on_member_join(self, event: stoat.ServerMemberJoinEvent):
        member = event.member
        guild = self.bot.get_server(member.server_id)
        if not guild:
            return

        # Re-fetch invites to detect which was used
        try:
            current = await guild.fetch_invites()
        except Exception:
            await self.db.log_join(guild.id, member.id)
            return

        old_cache = self._invite_cache.get(guild.id, {})
        new_cache = {}

        inviter_id = None
        used_code = None

        for inv in current:
            new_cache[inv.code] = inv.creator_id
            # If this code wasn't in our cache before, it's likely the one used
            if inv.code not in old_cache:
                used_code = inv.code
                inviter_id = inv.creator_id

        self._invite_cache[guild.id] = new_cache

        if not inviter_id:
            db_invites = await self.db.get_invite_codes(guild.id)
            for row in db_invites:
                if row["code"] not in old_cache:
                    inviter_id = row["creator_id"]
                    used_code = row["code"]
                    break

        await self.db.log_join(guild.id, member.id, inviter_id, used_code)

    @commands.Gear.listener(to=stoat.ServerMemberRemoveEvent)
    async def on_member_leave(self, event: stoat.ServerMemberRemoveEvent):
        await self.db.log_leave(event.server_id, event.user_id)

    # ── Commands ───────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    async def invites(self, ctx):
        """Check your invite stats."""
        total = await self.db.get_total_invites(ctx.server.id, ctx.author.id)
        active = await self.db.get_invite_count(ctx.server.id, ctx.author.id)

        await ctx.send(embeds=[info_embed("Your Invites",
            f"**Total invites:** {total}\n"
            f"**Active members:** {active}\n\n"
            "`invites leaderboard` — top inviters\n"
            "`invites info [user]` — someone's invites\n"
            "`invites codes` — list server invites"
        )])

    @invites.command()
    async def leaderboard(self, ctx):
        """Show the invite leaderboard."""
        rows = await self.db.get_invite_leaderboard(ctx.server.id, 10)
        if not rows:
            return await ctx.send(embeds=[info_embed("Invite Leaderboard", "No invites tracked yet.")])

        lines = []
        for i, row in enumerate(rows, 1):
            lines.append(f"`#{i}` <@{row['inviter_id']}> — **{row['cnt']}** invites")

        await ctx.send(embeds=[info_embed("🏆 Invite Leaderboard", "\n".join(lines))])

    @invites.command()
    async def info(self, ctx, member: str = None):
        """Show invite stats for a member."""
        target_id = member if member else ctx.author.id
        name = f"<@{target_id}>"

        total = await self.db.get_total_invites(ctx.server.id, target_id)
        active = await self.db.get_invite_count(ctx.server.id, target_id)

        await ctx.send(embeds=[info_embed(f"Invites — {name}",
            f"**Total invites:** {total}\n"
            f"**Active members:** {active}"
        )])

    @invites.command()
    @is_staff()
    async def codes(self, ctx):
        """List all server invite codes and their creators."""
        try:
            invites = await ctx.server.fetch_invites()
        except Exception:
            return await ctx.send(embeds=[error_embed("Error", "Failed to fetch invites. Check permissions.")])

        if not invites:
            return await ctx.send(embeds=[info_embed("Invite Codes", "No invites found for this server.")])

        lines = []
        for inv in invites:
            lines.append(f"`{inv.code}` — <@{inv.creator_id}> (<#{inv.channel_id}>)")

        await ctx.send(embeds=[info_embed(f"Invite Codes ({len(lines)})", "\n".join(lines))])

    @commands.command()
    async def inviteinfo(self, ctx):
        """Alias for invites info showing your own stats."""
        total = await self.db.get_total_invites(ctx.server.id, ctx.author.id)
        active = await self.db.get_invite_count(ctx.server.id, ctx.author.id)
        await ctx.send(embeds=[info_embed("Your Invite Stats",
            f"**Total people invited:** {total}\n"
            f"**Still in server:** {active}"
        )])

async def setup(bot):
    await bot.add_gear(Invites(bot))
