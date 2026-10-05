import stoat
from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, warn_embed, is_staff, _delete_after
from utils.db import Database
import asyncio
import logging
from datetime import datetime, timezone

log = logging.getLogger("tickets")


AUTO_REPLY = (
    "Please just say what you need or would like to buy. "
    "If you are buying, please say what payment method. "
    "Feel free to @ me, we will be with you when we can. "
    "*This is an auto-reply to a ticket opening.*"
)


class Tickets(commands.Gear):
    """Ticket system with categories and transcripts."""

    def __init__(self, bot):
        self.bot = bot
        self._panel_messages = set()
        self._ticket_welcome_messages = set()

    @property
    def db(self) -> Database:
        return self.bot.db

    async def _send_ticket_welcome(self, channel, member, ticket, category_name):
        """Send welcome embed + auto-reply + 🔒 close reaction in the ticket channel."""
        embed = stoat.SendableEmbed(
            title=f"🎫 Ticket #{ticket['id']} — {category_name.title()}",
            description=(
                f"Welcome {member.mention}! Staff will be with you shortly.\n\n"
                f"**Category:** {category_name}\n"
                f"**Opened:** <t:{int(datetime.now(timezone.utc).timestamp())}:R>\n\n"
                "React with 🔒 to close this ticket, or use `!close`"
            ),
            color="#5865F2",
        )
        welcome_msg = await channel.send(embeds=[embed])
        self._ticket_welcome_messages.add(welcome_msg.id)
        try:
            await welcome_msg.react("🔒")
        except Exception as e:
            log.warning(f"Failed to react with 🔒: {e}")

        await channel.send(content=AUTO_REPLY)

    async def _setup_ticket_permissions(self, guild, channel, opener_id):
        """Restrict ticket channel visibility to opener + staff roles only."""
        try:
            await channel.set_default_permissions(
                stoat.PermissionOverride(deny=stoat.Permissions.FLAGS["view_channel"])
            )
            log.info(f"Set default permissions (deny view) on channel {channel.id}")
        except Exception as e:
            log.warning(f"set_default_permissions failed (bot may lack ManagePermissions): {e}")

        cfg = await self.db.get_guild_config(guild.id)
        seen = set()
        for role_key in ("staff_role", "mod_role"):
            role_id = cfg.get(role_key)
            if not role_id or role_id in seen:
                continue
            seen.add(role_id)
            try:
                role = await guild.fetch_role(role_id)
                if role:
                    await channel.set_role_permissions(
                        role,
                        allow=(
                            stoat.Permissions.FLAGS["view_channel"]
                            | stoat.Permissions.FLAGS["send_messages"]
                            | stoat.Permissions.FLAGS["read_message_history"]
                            | stoat.Permissions.FLAGS["manage_messages"]
                        ),
                    )
                    log.info(f"Granted staff role {role.name} ({role_id}) access to {channel.id}")
            except Exception as e:
                log.warning(f"set_role_permissions for role {role_id}: {e}")

        try:
            await channel.set_role_permissions(
                opener_id,
                allow=(
                    stoat.Permissions.FLAGS["view_channel"]
                    | stoat.Permissions.FLAGS["send_messages"]
                    | stoat.Permissions.FLAGS["read_message_history"]
                ),
            )
            log.info(f"Granted opener {opener_id} access to {channel.id}")
        except Exception as e:
            log.warning(f"set_role_permissions for opener {opener_id} failed (user-level overrides may not be supported): {e}")

    # ── Setup ──────────────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @is_staff()
    async def ticket(self, ctx):
        """Ticket management commands."""
        await ctx.send(embeds=[info_embed("Ticket Commands",
            "`ticket setup` — configure the ticket system\n"
            "`ticket addcategory` — add a ticket category\n"
            "`ticket panel` — post a reaction-based ticket panel\n"
            "`ticket close` — close the current ticket\n"
            "`ticket transcript` — get ticket transcript\n"
            "`ticket list` — list open tickets"
        )])

    @ticket.command()
    @is_staff()
    async def setup(self, ctx, log_channel: str = None):
        """Set up the ticket system. Optionally provide a log channel ID."""
        await self.db.set_guild_config(
            ctx.server.id,
            ticket_log_channel=log_channel or ctx.channel.id
        )
        await ctx.send(embeds=[success_embed("Ticket System Configured",
            f"Log channel set to <#{log_channel or ctx.channel.id}>")])

    @ticket.command()
    @is_staff()
    async def addcategory(self, ctx, name: str, emoji: str = "🎫", *, description: str = ""):
        """Add a ticket category."""
        await self.db.add_ticket_category(ctx.server.id, name, description, emoji)
        await ctx.send(embeds=[success_embed("Category Added", f"{emoji} **{name}** — {description}")])

    @ticket.command()
    @is_staff()
    async def panel(self, ctx):
        """Post a reaction-based ticket panel for users to click and open tickets."""
        try:
            await ctx.message.delete()
        except Exception:
            pass
        categories = await self.db.get_ticket_categories(ctx.server.id)
        if not categories:
            return await ctx.send(embeds=[error_embed("No Categories",
                "Add categories first with `!ticket addcategory <name> <emoji>`.")])

        lines = [
            f"{cat['emoji']} — **{cat['name']}**" + (f" — {cat['description']}" if cat.get('description') else "")
            for cat in categories
        ]
        desc = "\n".join(lines)
        desc += "\n\nReact with the emoji for the category you want to open a ticket!"

        embed = stoat.SendableEmbed(
            title="🎫 Open a Ticket",
            description=desc,
            color="#5865F2",
        )
        msg = await ctx.send(embeds=[embed])
        await self.db.add_ticket_panel(ctx.server.id, msg.id)
        self._panel_messages.add(msg.id)
        for cat in categories:
            try:
                await msg.react(cat["emoji"])
            except Exception as e:
                log.warning(f"Failed to react with {cat['emoji']}: {e}")

    # ── Open ───────────────────────────────────────────────────────────────

    @commands.command()
    async def new(self, ctx, *, category: str = "general"):
        """Open a new support ticket."""
        try:
            await ctx.message.delete()
        except Exception:
            pass

        open_tickets = await self.db.get_user_open_tickets(ctx.server.id, ctx.author.id)
        if len(open_tickets) >= 3:
            _m = await ctx.send(embeds=[error_embed("Too Many Tickets",
                "You already have 3 open tickets. Please close one first.")])
            asyncio.create_task(_delete_after(_m, 10))
            return

        cfg = await self.db.get_guild_config(ctx.server.id)

        channel_name = f"ticket-{ctx.author.name.lower().replace(' ', '-')}"
        try:
            channel = await ctx.server.create_text_channel(
                name=channel_name,
                description=f"Support ticket for {ctx.author.name} | Category: {category}"
            )
        except Exception as e:
            log.error(f"Failed to create ticket channel: {e}")
            _m = await ctx.send(embeds=[error_embed("Error", "Could not create ticket channel. Check bot permissions.")])
            asyncio.create_task(_delete_after(_m, 10))
            return

        await self._setup_ticket_permissions(ctx.server, channel, ctx.author.id)

        ticket = await self.db.create_ticket(
            ctx.server.id, channel.id, ctx.author.id, category
        )

        await self._send_ticket_welcome(channel, ctx.author, ticket, category)

        _m = await ctx.send(embeds=[success_embed("Ticket Created", f"Ticket opened in {channel.mention}")])
        asyncio.create_task(_delete_after(_m, 10))

        # Log to ticket log channel
        log_ch_id = cfg.get("ticket_log_channel")
        if log_ch_id:
            try:
                log_ch = await self.bot.fetch_channel(log_ch_id)
                await log_ch.send(embeds=[stoat.SendableEmbed(
                    title="🎫 Ticket Opened",
                    description=(
                        f"**User:** {ctx.author.mention} (`{ctx.author.id}`)\n"
                        f"**Category:** {category}\n"
                        f"**Channel:** {channel.mention}\n"
                        f"**Ticket ID:** #{ticket['id']}"
                    ),
                    color="#57F287",
                )])
            except Exception:
                pass

    # ── Close ──────────────────────────────────────────────────────────────

    async def _execute_close(self, ticket, channel, closer, guild, reason="No reason provided"):
        """Shared close logic: transcript, DB save, log channel, delete."""
        import io

        transcript_lines = []
        try:
            messages = await channel.history(limit=500)
            for msg in reversed(messages):
                ts = msg.created_at.strftime("%Y-%m-%d %H:%M:%S UTC") if msg.created_at else "?"
                transcript_lines.append(f"[{ts}] {msg.author.name}: {msg.content}")
        except Exception:
            transcript_lines.append("(Could not fetch messages)")

        transcript = "\n".join(transcript_lines)
        await self.db.close_ticket(channel.id, transcript)

        cfg = await self.db.get_guild_config(guild.id)
        log_ch_id = cfg.get("ticket_log_channel")
        if log_ch_id:
            try:
                log_ch = await self.bot.fetch_channel(log_ch_id)
                file_data = transcript.encode("utf-8")
                await log_ch.send(
                    embed=stoat.SendableEmbed(
                        title="🎫 Ticket Closed",
                        description=(
                            f"**Ticket ID:** #{ticket['id']}\n"
                            f"**User:** <@{ticket['user_id']}>\n"
                            f"**Category:** {ticket['category']}\n"
                            f"**Closed by:** {closer.mention}\n"
                            f"**Reason:** {reason}"
                        ),
                        color="#ED4245",
                    ),
                    attachments=[stoat.File(
                        io.BytesIO(file_data),
                        filename=f"transcript-{ticket['id']}.txt",
                        spoiler=False
                    )]
                )
            except Exception as e:
                log.error(f"Failed to send transcript: {e}")

        try:
            _msg = await channel.send(embeds=[success_embed("Ticket Closed",
                f"Closed by {closer.mention}. Deleting in 5 seconds...")])
        except Exception:
            pass
        await asyncio.sleep(5)
        try:
            await channel.delete()
        except Exception:
            pass

    @commands.command()
    async def close(self, ctx, *, reason: str = "No reason provided"):
        """Close the current ticket channel."""
        ticket = await self.db.get_ticket(ctx.channel.id)
        if not ticket:
            return await ctx.send(embeds=[error_embed("Not a Ticket", "This command can only be used inside a ticket channel.")])

        if ticket["status"] == "closed":
            return await ctx.send(embeds=[error_embed("Already Closed", "This ticket is already closed.")])

        await self._execute_close(ticket, ctx.channel, ctx.author, ctx.server, reason)

    @ticket.command()
    @is_staff()
    async def closebyid(self, ctx, ticket_id: int, *, reason: str = "Closed by ID"):
        """Close a ticket by its # ID number."""
        ticket = await self.db.get_ticket_by_id(ticket_id)
        if not ticket:
            return await ctx.send(embeds=[error_embed("Not Found", f"No ticket with ID #{ticket_id}.")])
        if ticket["status"] == "closed":
            return await ctx.send(embeds=[error_embed("Already Closed", f"Ticket #{ticket_id} is already closed.")])
        try:
            ch = await self.bot.fetch_channel(ticket["channel_id"])
        except Exception:
            return await ctx.send(embeds=[error_embed("Error", "Could not find the ticket channel. It may have already been deleted.")])
        await self._execute_close(ticket, ch, ctx.author, ctx.server, reason)

    @ticket.command()
    @is_staff()
    async def closeall(self, ctx):
        """Close all open tickets in this server."""
        tickets = await self.db.get_all_tickets(ctx.server.id, "open")
        if not tickets:
            return await ctx.send(embeds=[info_embed("No Tickets", "No open tickets to close.")])
        closed = 0
        for ticket in tickets:
            try:
                ch = await self.bot.fetch_channel(ticket["channel_id"])
                await self._execute_close(ticket, ch, ctx.author, ctx.server, "Mass close")
                closed += 1
            except Exception:
                pass
        await ctx.send(embeds=[success_embed("Mass Close", f"Closed **{closed}** of **{len(tickets)}** open tickets.")])

    # ── Transcript ─────────────────────────────────────────────────────────

    @ticket.command()
    @is_staff()
    async def transcript(self, ctx):
        """Get the transcript of the current ticket."""
        ticket = await self.db.get_ticket(ctx.channel.id)
        if not ticket:
            return await ctx.send(embeds=[error_embed("Not a Ticket", "Run this inside a ticket channel.")])

        if ticket["transcript"]:
            import io
            file_data = ticket["transcript"].encode("utf-8")
            await ctx.send(
                embed=info_embed("Transcript", f"Transcript for ticket #{ticket['id']}"),
                attachments=[stoat.File(
                    io.BytesIO(file_data),
                    filename=f"transcript-{ticket['id']}.txt"
                )]
            )
        else:
            await ctx.send(embeds=[warn_embed("No Transcript", "No saved transcript yet (ticket still open).")])

    @ticket.command(name="list")
    @is_staff()
    async def list_tickets(self, ctx):
        """List all open tickets in this server."""
        tickets = await self.db.get_all_tickets(ctx.server.id, "open")
        if not tickets:
            return await ctx.send(embeds=[info_embed("Open Tickets", "No open tickets.")])
        lines = [f"#{t['id']} — <@{t['user_id']}> | {t['category']} | <#{t['channel_id']}>" for t in tickets]
        await ctx.send(embeds=[info_embed(f"Open Tickets ({len(tickets)})", "\n".join(lines))])


    # ── Reaction listener for ticket panel ────────────────────────────────

    @commands.Gear.listener(to=stoat.MessageReactEvent)
    async def on_reaction_add(self, event: stoat.MessageReactEvent):
        log.info(f"Reaction event: msg={event.message_id} user={event.user_id} emoji={event.emoji!r}")

        if not hasattr(event, "message_id") or not hasattr(event, "user_id"):
            return

        # Check if this is a panel message (in-memory cache + DB fallback)
        is_panel = event.message_id in self._panel_messages
        if not is_panel:
            guild_id = await self.db.get_ticket_panel_guild(event.message_id)
            if guild_id:
                self._panel_messages.add(event.message_id)
                is_panel = True
        if not is_panel:
            return
        log.info(f"Panel reaction detected: msg={event.message_id}")

        emoji = getattr(event, "emoji", None) or getattr(event, "emoji_id", None)
        if not emoji:
            log.warning("No emoji in event")
            return
        log.info(f"Emoji: {emoji!r}")

        user_id = event.user_id

        # Find guild from panel record
        guild_id = await self.db.get_ticket_panel_guild(event.message_id)
        if not guild_id:
            return
        guild = self.bot.get_server(guild_id)
        if not guild:
            log.warning(f"Guild {guild_id} not found")
            return

        try:
            panel_channel = await self.bot.fetch_channel(event.channel_id)
        except Exception as e:
            log.warning(f"fetch_channel {event.channel_id}: {e}")
            return

        try:
            member = await guild.fetch_member(user_id)
        except Exception:
            log.info(f"fetch_member {user_id} failed")
            return
        if not member or member.bot:
            return

        # Find which category this emoji matches
        categories = await self.db.get_ticket_categories(guild.id)
        category_name = None
        for cat in categories:
            if cat["emoji"] == emoji:
                category_name = cat["name"]
                break
        if not category_name:
            log.info(f"No category matches emoji {emoji!r}")
            return
        log.info(f"Category: {category_name}")

        # Check open ticket limit
        open_tickets = await self.db.get_user_open_tickets(guild.id, user_id)
        if len(open_tickets) >= 3:
            try:
                _msg = await panel_channel.send(f"<@{user_id}> You already have 3 open tickets. Close one first.")
                asyncio.create_task(_delete_after(_msg, 10))
            except Exception:
                pass
            return

        cfg = await self.db.get_guild_config(guild.id)

        channel_name = f"ticket-{member.name.lower().replace(' ', '-')}"
        try:
            channel = await guild.create_text_channel(
                name=channel_name,
                description=f"Support ticket for {member.name} | Category: {category_name}"
            )
            log.info(f"Created ticket channel {channel.id} for {member.name} ({category_name})")
        except Exception as e:
            log.error(f"create_text_channel failed: {e}")
            return

        await self._setup_ticket_permissions(guild, channel, user_id)

        ticket = await self.db.create_ticket(guild.id, channel.id, user_id, category_name)

        await self._send_ticket_welcome(channel, member, ticket, category_name)

        try:
            _msg = await panel_channel.send(f"{member.mention} Your ticket has been opened in {channel.mention}")
            asyncio.create_task(_delete_after(_msg, 10))
        except Exception:
            pass

        log_ch_id = cfg.get("ticket_log_channel")
        if log_ch_id:
            try:
                log_ch = await self.bot.fetch_channel(log_ch_id)
                await log_ch.send(embeds=[stoat.SendableEmbed(
                    title="🎫 Ticket Opened",
                    description=(
                        f"**User:** {member.mention} (`{user_id}`)\n"
                        f"**Category:** {category_name}\n"
                        f"**Channel:** {channel.mention}\n"
                        f"**Ticket ID:** #{ticket['id']}"
                    ),
                    color="#57F287",
                )])
            except Exception:
                pass


    # ── Close-ticket reaction listener 🔒 ─────────────────────────────────

    @commands.Gear.listener(to=stoat.MessageReactEvent)
    async def on_close_reaction(self, event: stoat.MessageReactEvent):
        if not hasattr(event, "message_id") or not hasattr(event, "user_id"):
            return
        if event.message_id not in self._ticket_welcome_messages:
            return

        emoji = getattr(event, "emoji", None) or getattr(event, "emoji_id", None)
        if emoji != "🔒":
            return

        ticket = await self.db.get_ticket(event.channel_id)
        if not ticket or ticket["status"] == "closed":
            return

        # Only the ticket opener or staff can close via reaction
        guild = self.bot.get_server(ticket["guild_id"])
        if not guild:
            return

        try:
            member = await guild.fetch_member(event.user_id)
        except Exception:
            return
        if not member or member.bot:
            return

        is_opener = event.user_id == ticket["user_id"]
        is_staff_member = False
        if not is_opener:
            cfg = await self.db.get_guild_config(guild.id)
            member_role_ids = [r.id for r in member.roles]
            for key in ("staff_role", "mod_role"):
                rid = cfg.get(key)
                if rid and rid in member_role_ids:
                    is_staff_member = True
                    break

        if not is_opener and not is_staff_member:
            return

        try:
            ch = await self.bot.fetch_channel(event.channel_id)
        except Exception:
            return

        await self._execute_close(ticket, ch, member, guild, "Closed via 🔒 reaction")


async def setup(bot):
    await bot.add_gear(Tickets(bot))
