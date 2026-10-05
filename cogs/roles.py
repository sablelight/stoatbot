import stoat
from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, is_staff
import logging

log = logging.getLogger("roles")


class Roles(commands.Gear):
    """Reaction roles and role management commands."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    # ── Reaction roles ─────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @is_staff()
    async def reactionrole(self, ctx):
        """Reaction role management."""
        await ctx.send(embeds=[info_embed("Reaction Role Commands",
            "`reactionrole add <message_id> <emoji> <role_id> [mode]` — add a reaction role\n"
            "`reactionrole remove <message_id> <emoji>` — remove a reaction role\n"
            "`reactionrole list` — list all reaction roles\n\n"
            "**Modes:** `toggle` (default), `add` (only add), `remove` (only remove)"
        )])

    @reactionrole.command(name="add")
    @is_staff()
    async def rr_add(self, ctx, message_id: str, emoji: str, role_id: str, mode: str = "toggle"):
        """Add a reaction role to a message."""
        if mode not in ("toggle", "add", "remove"):
            return await ctx.send(embeds=[error_embed("Invalid Mode", "Mode must be `toggle`, `add`, or `remove`.")])
        await self.db.add_reaction_role(
            ctx.server.id, ctx.channel.id, message_id, emoji, role_id, mode
        )
        await ctx.send(embeds=[success_embed("Reaction Role Added",
            f"React with {emoji} on message `{message_id}` to get role <@&{role_id}> (mode: `{mode}`)")])

    @reactionrole.command(name="remove")
    @is_staff()
    async def rr_remove(self, ctx, message_id: str, emoji: str):
        """Remove a reaction role."""
        await self.db.remove_reaction_role(message_id, emoji)
        await ctx.send(embeds=[success_embed("Reaction Role Removed", f"Removed {emoji} from message `{message_id}`")])

    @reactionrole.command(name="list")
    @is_staff()
    async def rr_list(self, ctx):
        """List all reaction roles in this server."""
        rrs = await self.db.get_all_reaction_roles(ctx.server.id)
        if not rrs:
            return await ctx.send(embeds=[info_embed("Reaction Roles", "No reaction roles configured.")])
        lines = [
            f"{r['emoji']} on `{r['message_id']}` → <@&{r['role_id']}> (mode: `{r['mode']}`)"
            for r in rrs
        ]
        await ctx.send(embeds=[info_embed(f"Reaction Roles ({len(rrs)})", "\n".join(lines))])

    # ── Reaction listeners ─────────────────────────────────────────────────

    @commands.Gear.listener(to=stoat.MessageReactEvent)
    async def on_reaction_add(self, event: stoat.MessageReactEvent):
        if not hasattr(event, "message_id") or not hasattr(event, "user_id"):
            return

        emoji = getattr(event, "emoji", None) or getattr(event, "emoji_id", None)
        if not emoji:
            return

        rr = await self.db.get_reaction_role(event.message_id, str(emoji))
        if not rr:
            return

        if rr["mode"] == "remove":
            return  # This mode only removes on reaction remove

        guild = self.bot.get_server(rr["guild_id"])
        if not guild:
            return

        try:
            member = await guild.fetch_member(event.user_id)
            if member and not member.bot:
                current_roles = [r.id for r in member.roles]
                if rr["role_id"] not in current_roles:
                    await member.edit(roles=current_roles + [rr["role_id"]])
        except Exception as e:
            log.debug(f"Reaction role add failed: {e}")

    @commands.Gear.listener(to=stoat.MessageUnreactEvent)
    async def on_reaction_remove(self, event: stoat.MessageUnreactEvent):
        if not hasattr(event, "message_id") or not hasattr(event, "user_id"):
            return

        emoji = getattr(event, "emoji", None) or getattr(event, "emoji_id", None)
        if not emoji:
            return

        rr = await self.db.get_reaction_role(event.message_id, str(emoji))
        if not rr:
            return

        if rr["mode"] == "add":
            return  # This mode only adds

        guild = self.bot.get_server(rr["guild_id"])
        if not guild:
            return

        try:
            member = await guild.fetch_member(event.user_id)
            if member and not member.bot:
                current_roles = [r.id for r in member.roles]
                new_roles = [r for r in current_roles if r != rr["role_id"]]
                await member.edit(roles=new_roles)
        except Exception as e:
            log.debug(f"Reaction role remove failed: {e}")

    # ── Role management commands ───────────────────────────────────────────

    @commands.command()
    @is_staff()
    async def giverole(self, ctx, member: stoat.Member, role_id: str):
        """Give a role to a member."""
        try:
            current_roles = [r.id for r in member.roles]
            if role_id not in current_roles:
                await member.edit(roles=current_roles + [role_id])
            await ctx.send(embeds=[success_embed("Role Given", f"<@&{role_id}> given to {member.mention}")])
        except Exception as e:
            await ctx.send(embeds=[error_embed("Failed", str(e))])

    @commands.command()
    @is_staff()
    async def takerole(self, ctx, member: stoat.Member, role_id: str):
        """Remove a role from a member."""
        try:
            current_roles = [r.id for r in member.roles]
            new_roles = [r for r in current_roles if r != role_id]
            await member.edit(roles=new_roles)
            await ctx.send(embeds=[success_embed("Role Removed", f"<@&{role_id}> removed from {member.mention}")])
        except Exception as e:
            await ctx.send(embeds=[error_embed("Failed", str(e))])

    @commands.command()
    async def roles(self, ctx, member: stoat.Member = None):
        """List roles for yourself or another member."""
        target = member or ctx.author
        role_list = ", ".join(f"<@&{r.id}>" for r in target.roles) if target.roles else "None"
        await ctx.send(embeds=[info_embed(f"Roles for {target.name}", role_list)])


async def setup(bot):
    await bot.add_gear(Roles(bot))
