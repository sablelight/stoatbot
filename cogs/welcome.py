import stoat
from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, is_staff
import logging

log = logging.getLogger("welcome")

DEFAULT_WELCOME = "Welcome to **{server}**, {user}! 🎉 You are member #{count}."


class Welcome(commands.Gear):
    """Configurable welcome messages and auto-role assignment."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @commands.Gear.listener(to=stoat.ServerMemberJoinEvent)
    async def on_member_join(self, event: stoat.ServerMemberJoinEvent):
        member = event.member
        guild = self.bot.get_server(member.server_id)
        if not guild:
            return

        cfg = await self.db.get_guild_config(member.server_id)

        # Auto-roles
        auto_roles = await self.db.get_auto_roles(member.server_id)
        for row in auto_roles:
            try:
                current_roles = [r.id for r in member.roles]
                if row["role_id"] not in current_roles:
                    await member.edit(roles=current_roles + [row["role_id"]])
            except Exception as e:
                log.warning(f"Failed to assign auto role {row['role_id']}: {e}")

        # Welcome message
        welcome_ch = cfg.get("welcome_channel")
        if not welcome_ch:
            return

        message_template = cfg.get("welcome_message") or DEFAULT_WELCOME
        try:
            member_count = len(guild.members) if hasattr(guild, "members") else "?"
            message = message_template.replace("{user}", member.mention)
            message = message.replace("{username}", member.name)
            message = message.replace("{server}", guild.name)
            message = message.replace("{count}", str(member_count))
            message = message.replace("{id}", member.id)
        except Exception:
            message = f"Welcome {member.mention}!"

        try:
            ch = await self.bot.fetch_channel(welcome_ch)
            embed = stoat.SendableEmbed(
                title="👋 Welcome!",
                description=message,
                color="#57F287",
            )
            await ch.send(embeds=[embed])
        except Exception as e:
            log.error(f"Failed to send welcome message: {e}")

    # ── Config ─────────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @is_staff()
    async def welcome(self, ctx):
        """Welcome system configuration."""
        cfg = await self.db.get_guild_config(ctx.server.id)
        ch = cfg.get("welcome_channel")
        msg = cfg.get("welcome_message") or DEFAULT_WELCOME
        await ctx.send(embeds=[info_embed("Welcome Config",
            f"**Channel:** {f'<#{ch}>' if ch else 'Not set'}\n"
            f"**Message:** {msg}\n\n"
            "**Placeholders:** `{{user}}` `{{username}}` `{{server}}` `{{count}}` `{{id}}`"
        )])

    @welcome.command()
    @is_staff()
    async def setchannel(self, ctx, channel_id: str):
        """Set the welcome channel."""
        await self.db.set_guild_config(ctx.server.id, welcome_channel=channel_id)
        await ctx.send(embeds=[success_embed("Welcome Channel Set", f"Welcome messages will go to <#{channel_id}>")])

    @welcome.command()
    @is_staff()
    async def setmessage(self, ctx, *, message: str):
        """
        Set the welcome message.
        Placeholders: {user} {username} {server} {count} {id}
        """
        await self.db.set_guild_config(ctx.server.id, welcome_message=message)
        await ctx.send(embeds=[success_embed("Welcome Message Set", f"New message:\n{message}")])

    @welcome.command()
    @is_staff()
    async def test(self, ctx):
        """Preview the welcome message in the current channel."""
        cfg = await self.db.get_guild_config(ctx.server.id)
        message_template = cfg.get("welcome_message") or DEFAULT_WELCOME
        message = message_template.replace("{user}", ctx.author.mention)
        message = message.replace("{username}", ctx.author.name)
        message = message.replace("{server}", ctx.server.name)
        message = message.replace("{count}", "???")
        message = message.replace("{id}", ctx.author.id)
        embed = stoat.SendableEmbed(title="👋 Welcome! (Preview)", description=message, color="#57F287")
        await ctx.send(embeds=[embed])

    # ── Auto roles ─────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @is_staff()
    async def autorole(self, ctx):
        """Manage auto-assigned roles on member join."""
        roles = await self.db.get_auto_roles(ctx.server.id)
        if not roles:
            return await ctx.send(embeds=[info_embed("Auto Roles", "No auto roles configured.")])
        role_list = "\n".join(f"• <@&{r['role_id']}>" for r in roles)
        await ctx.send(embeds=[info_embed("Auto Roles", role_list)])

    @autorole.command(name="add")
    @is_staff()
    async def autorole_add(self, ctx, role_id: str):
        """Add a role to be assigned on member join."""
        await self.db.add_auto_role(ctx.server.id, role_id)
        await ctx.send(embeds=[success_embed("Auto Role Added", f"<@&{role_id}> will be assigned on join.")])

    @autorole.command(name="remove")
    @is_staff()
    async def autorole_remove(self, ctx, role_id: str):
        """Remove an auto role."""
        await self.db.remove_auto_role(ctx.server.id, role_id)
        await ctx.send(embeds=[success_embed("Auto Role Removed", f"<@&{role_id}> removed.")])


async def setup(bot):
    await bot.add_gear(Welcome(bot))
