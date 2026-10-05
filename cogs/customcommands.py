import stoat
from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, is_staff
import logging

log = logging.getLogger("customcommands")


class CustomCommands(commands.Gear):
    """Let admins create custom text commands."""

    def __init__(self, bot):
        self.bot = bot
        self._cache = {}

    @property
    def db(self):
        return self.bot.db

    async def gear_start(self):
        await self._rebuild_cache()

    async def _rebuild_cache(self):
        self._cache.clear()

    @commands.group(invoke_without_command=True, aliases=["cc"])
    @is_staff()
    async def customcommand(self, ctx):
        """Manage custom commands."""
        await ctx.send(embeds=[info_embed("Custom Commands",
            "`customcommand add <trigger> <response>` — add a custom command\n"
            "`customcommand remove <trigger>` — remove a custom command\n"
            "`customcommand list` — list all custom commands")])

    @customcommand.command(name="add")
    @is_staff()
    async def cc_add(self, ctx, trigger: str, *, response: str):
        """Add a custom command."""
        success = await self.db.add_custom_command(ctx.server.id, trigger, response)
        if not success:
            return await ctx.send(embeds=[error_embed("Exists", f"A command named `{trigger}` already exists.")])
        await self._rebuild_cache()
        await ctx.send(embeds=[success_embed("Command Added",
            f"`{trigger}` will respond with: {response}")])

    @customcommand.command(name="remove", aliases=["del", "rm"])
    @is_staff()
    async def cc_remove(self, ctx, trigger: str):
        """Remove a custom command."""
        await self.db.remove_custom_command(ctx.server.id, trigger)
        await self._rebuild_cache()
        await ctx.send(embeds=[success_embed("Command Removed", f"Removed `{trigger}`.")])

    @customcommand.command(name="list", aliases=["ls"])
    @is_staff()
    async def cc_list(self, ctx):
        """List all custom commands."""
        cmds = await self.db.get_custom_commands(ctx.server.id)
        if not cmds:
            return await ctx.send(embeds=[info_embed("Custom Commands", "No custom commands configured.")])
        lines = [f"`{c['trigger']}` → {c['response']}" for c in cmds]
        await ctx.send(embeds=[info_embed(f"Custom Commands ({len(cmds)})", "\n".join(lines))])

    @commands.Gear.listener(to=stoat.MessageCreateEvent)
    async def on_message(self, event: stoat.MessageCreateEvent):
        if not hasattr(event, "message") or event.message.author.bot:
            return
        guild_id = getattr(event.message, "guild", None) or getattr(event.message, "server", None)
        if not guild_id:
            return
        guild_id = guild_id.id
        content = event.message.content.strip()
        prefix = ""
        cfg = await self.db.get_guild_config(guild_id)
        prefix = cfg.get("prefix") or "!"

        if not content.startswith(prefix):
            return
        trigger = content[len(prefix):].strip()
        cmds = await self.db.get_custom_commands(guild_id)
        for cmd in cmds:
            if cmd["trigger"] == trigger:
                await event.message.channel.send(cmd["response"])
                return


async def setup(bot):
    await bot.add_gear(CustomCommands(bot))
