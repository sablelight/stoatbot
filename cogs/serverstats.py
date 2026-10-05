import stoat
from stoat.ext import commands
from utils.helpers import info_embed, is_staff
import logging

log = logging.getLogger("serverstats")


class ServerStats(commands.Gear):
    """Server statistics."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @is_staff()
    async def stats(self, ctx):
        """Show server statistics."""
        guild = ctx.server
        members = guild.members or []
        bots = sum(1 for m in members if getattr(m, "bot", False))
        humans = len(members) - bots
        online = sum(1 for m in members if getattr(m, "status", "offline") != "offline")
        channels = len(guild.channels) if hasattr(guild, "channels") else 0
        roles = len(guild.roles) if hasattr(guild, "roles") else 0

        embed = info_embed(
            f"📊 {guild.name}",
            f"**Members:** {len(members)} ({humans} humans, {bots} bots)\n"
            f"**Online:** {online}\n"
            f"**Channels:** {channels}\n"
            f"**Roles:** {roles}\n"
            f"**Owner:** <@{guild.owner_id}>\n"
            f"**ID:** {guild.id}"
        )
        await ctx.send(embeds=[embed])


async def setup(bot):
    await bot.add_gear(ServerStats(bot))
