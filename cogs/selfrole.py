import stoat
from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, is_staff
import logging

log = logging.getLogger("selfrole")


class SelfRole(commands.Gear):
    """Self-assignable roles — let members opt into roles."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @commands.group(invoke_without_command=True, name="role")
    async def role_group(self, ctx, *, role_name: str = None):
        """Toggle a self-assignable role on yourself, or list available roles."""
        if role_name is None:
            roles = await self.db.get_self_roles(ctx.server.id)
            if not roles:
                return await ctx.send(embeds=[info_embed("Self Roles", "No self-assignable roles configured.")])
            lines = [f"<@&{r['role_id']}> — {r['name']}" for r in roles]
            await ctx.send(embeds=[info_embed("Available Roles", "\n".join(lines))])
            return

        roles = await self.db.get_self_roles(ctx.server.id)
        match = None
        for r in roles:
            if r["name"].lower() == role_name.lower() or r["role_id"] == role_name:
                match = r
                break
        if not match:
            return await ctx.send(embeds=[error_embed("Not Found", f"No self-assignable role named '{role_name}'.")])

        member = ctx.author
        current_roles = [r.id for r in member.roles]
        if match["role_id"] in current_roles:
            new_roles = [r for r in current_roles if r != match["role_id"]]
            await member.edit(roles=new_roles)
            await ctx.send(embeds=[success_embed("Role Removed", f"Removed <@&{match['role_id']}> from yourself.")])
        else:
            await member.edit(roles=current_roles + [match["role_id"]])
            await ctx.send(embeds=[success_embed("Role Added", f"Added <@&{match['role_id']}> to yourself.")])

    @commands.group(invoke_without_command=True)
    @is_staff()
    async def selfrole(self, ctx):
        """Manage self-assignable roles."""
        await ctx.send(embeds=[info_embed("Self Role Management",
            "`selfrole add <role_id> <name> [description]` — add a self-assignable role\n"
            "`selfrole remove <role_id>` — remove a self-assignable role\n"
            "`selfrole list` — list all self-assignable roles")])

    @selfrole.command(name="add")
    @is_staff()
    async def selfrole_add(self, ctx, role_id: str, name: str, *, description: str = ""):
        """Add a role as self-assignable."""
        await self.db.add_self_role(ctx.server.id, role_id, name, description)
        await ctx.send(embeds=[success_embed("Self Role Added", f"<@&{role_id}> is now available as '{name}'.")])

    @selfrole.command(name="remove")
    @is_staff()
    async def selfrole_remove(self, ctx, role_id: str):
        """Remove a role from self-assignable."""
        await self.db.remove_self_role(ctx.server.id, role_id)
        await ctx.send(embeds=[success_embed("Self Role Removed", f"<@&{role_id}> is no longer self-assignable.")])

    @selfrole.command(name="list")
    @is_staff()
    async def selfrole_list(self, ctx):
        """List all self-assignable roles."""
        roles = await self.db.get_self_roles(ctx.server.id)
        if not roles:
            return await ctx.send(embeds=[info_embed("Self Roles", "No self-assignable roles configured.")])
        lines = [f"<@&{r['role_id']}> — {r['name']}" + (f" — {r['description']}" if r.get("description") else "") for r in roles]
        await ctx.send(embeds=[info_embed(f"Self Roles ({len(roles)})", "\n".join(lines))])


async def setup(bot):
    await bot.add_gear(SelfRole(bot))
