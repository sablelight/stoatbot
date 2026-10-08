from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, warn_embed, is_staff, parse_duration, utcnow
from datetime import datetime, timedelta
import logging

log = logging.getLogger("events")

class Events(commands.Gear):
    """Create and manage events with RSVP."""

    def __init__(self, bot):
        self.bot = bot

    @property
    def db(self):
        return self.bot.db

    @commands.group(invoke_without_command=True, aliases=["event"])
    @is_staff()
    async def events(self, ctx):
        """Manage events. Use `events create`, `events list`, `events edit`, `events delete`."""
        await ctx.send(embeds=[info_embed("Events",
            "`events create <title>` — create a new event\n"
            "`events list` — list all events\n"
            "`events edit <id> [--title] [--time] [--max] [--desc]` — edit an event\n"
            "`events delete <id>` — delete an event\n"
            "`events rsvp <id>` — RSVP to an event\n"
            "`events unrsvp <id>` — cancel RSVP\n"
            "`events info <id>` — show event details")])

    @events.command(name="create", aliases=["new"])
    @is_staff()
    async def events_create(self, ctx, *, title: str):
        """Create a new event with a title."""
        event = await self.db.create_event(ctx.server.id, ctx.author.id, title,
                                           channel_id=ctx.channel.id)
        await ctx.send(embeds=[success_embed("Event Created",
            f"**{title}** (ID: `#{event['id']}`)\n"
            f"Use `events edit {event['id']} --time <duration>` to set when it starts.\n"
            f"Use `events edit {event['id']} --desc <text>` to add a description.")])

    @events.command(name="list", aliases=["ls"])
    @is_staff()
    async def events_list(self, ctx):
        """List all events in this server."""
        events = await self.db.get_guild_events(ctx.server.id)
        if not events:
            return await ctx.send(embeds=[info_embed("Events", "No events scheduled.")])
        lines = []
        for e in events:
            rsvps = await self.db.get_rsvps(e["id"])
            rsvp_count = len(rsvps)
            time_str = ""
            if e.get("event_time"):
                try:
                    dt = datetime.fromisoformat(e["event_time"]) if isinstance(e["event_time"], str) else e["event_time"]
                    time_str = f" — <t:{int(dt.timestamp())}:R>"
                except Exception:
                    time_str = f" — {e['event_time']}"
            max_str = f"/{e['max_participants']}" if e.get("max_participants") else ""
            lines.append(f"`#{e['id']}` **{e['title']}**{time_str} — {rsvp_count}{max_str} RSVPs")
        await ctx.send(embeds=[info_embed(f"Events ({len(events)})", "\n".join(lines))])

    @events.command(name="info")
    @is_staff()
    async def events_info(self, ctx, event_id: int):
        """Show event details."""
        event = await self.db.get_event(event_id)
        if not event or event["guild_id"] != ctx.server.id:
            return await ctx.send(embeds=[error_embed("Not Found", "No event with that ID.")])
        rsvps = await self.db.get_rsvps(event_id)
        rsvp_lines = "\n".join(f"<@{r['user_id']}>" for r in rsvps[:20]) if rsvps else "None yet"
        if len(rsvps) > 20:
            rsvp_lines += f"\n... and {len(rsvps) - 20} more"
        desc = event.get("description") or "No description"
        time_str = ""
        if event.get("event_time"):
            try:
                dt = datetime.fromisoformat(event["event_time"]) if isinstance(event["event_time"], str) else event["event_time"]
                time_str = f"\n**Time:** <t:{int(dt.timestamp())}:F>"
            except Exception:
                time_str = f"\n**Time:** {event['event_time']}"
        max_str = f" / {event['max_participants']}" if event.get("max_participants") else ""
        await ctx.send(embeds=[info_embed(
            f"📅 {event['title']}",
            f"**ID:** `#{event['id']}`\n"
            f"**By:** <@{event['creator_id']}>{time_str}\n"
            f"**Description:** {desc}\n"
            f"**RSVPs:** {len(rsvps)}{max_str}\n\n**Attendees:**\n{rsvp_lines}"
        )])

    @events.command(name="edit")
    @is_staff()
    async def events_edit(self, ctx, event_id: int, *, options: str):
        """Edit an event. Options: --title, --desc, --time <duration>, --max <count>."""
        event = await self.db.get_event(event_id)
        if not event or event["guild_id"] != ctx.server.id:
            return await ctx.send(embeds=[error_embed("Not Found", "No event with that ID.")])
        if event["creator_id"] != ctx.author.id and not ctx.author.server_permissions.manage_server:
            return await ctx.send(embeds=[error_embed("No Permission", "You don't own this event.")])

        updates = {}
        import shlex
        try:
            parts = shlex.split(options)
        except Exception:
            parts = options.split()
        i = 0
        while i < len(parts):
            if parts[i] == "--title" and i + 1 < len(parts):
                updates["title"] = parts[i + 1]
                i += 2
            elif parts[i] == "--desc" and i + 1 < len(parts):
                updates["description"] = parts[i + 1]
                i += 2
            elif parts[i] == "--time" and i + 1 < len(parts):
                seconds = parse_duration(parts[i + 1])
                dt = utcnow() + timedelta(seconds=seconds)
                updates["event_time"] = dt.isoformat()
                i += 2
            elif parts[i] == "--max" and i + 1 < len(parts):
                try:
                    updates["max_participants"] = int(parts[i + 1])
                except ValueError:
                    return await ctx.send(embeds=[error_embed("Invalid", "--max must be a number.")])
                i += 2
            else:
                i += 1

        if not updates:
            return await ctx.send(embeds=[error_embed("No Changes", "Provide --title, --desc, --time, or --max.")])

        await self.db.update_event(event_id, **updates)
        await ctx.send(embeds=[success_embed("Event Updated", f"Updated event `#{event_id}`.")])

    @events.command(name="delete", aliases=["del", "rm"])
    @is_staff()
    async def events_delete(self, ctx, event_id: int):
        """Delete an event."""
        event = await self.db.get_event(event_id)
        if not event or event["guild_id"] != ctx.server.id:
            return await ctx.send(embeds=[error_embed("Not Found", "No event with that ID.")])
        if event["creator_id"] != ctx.author.id and not ctx.author.server_permissions.manage_server:
            return await ctx.send(embeds=[error_embed("No Permission", "You don't own this event.")])
        await self.db.delete_event(event_id)
        await ctx.send(embeds=[success_embed("Event Deleted", f"Deleted event `#{event_id}`.")])

    @events.command(name="rsvp")
    @is_staff()
    async def events_rsvp(self, ctx, event_id: int):
        """RSVP to an event."""
        event = await self.db.get_event(event_id)
        if not event or event["guild_id"] != ctx.server.id:
            return await ctx.send(embeds=[error_embed("Not Found", "No event with that ID.")])
        if await self.db.is_rsvped(event_id, ctx.author.id):
            return await ctx.send(embeds=[warn_embed("Already RSVPed", "You're already on the list.")])
        if event.get("max_participants"):
            rsvps = await self.db.get_rsvps(event_id)
            if len(rsvps) >= event["max_participants"]:
                return await ctx.send(embeds=[error_embed("Full", "This event is full.")])
        await self.db.add_rsvp(event_id, ctx.author.id)
        await ctx.send(embeds=[success_embed("RSVPed", f"You're attending **{event['title']}**!")])

    @events.command(name="unrsvp")
    @is_staff()
    async def events_unrsvp(self, ctx, event_id: int):
        """Cancel your RSVP to an event."""
        event = await self.db.get_event(event_id)
        if not event or event["guild_id"] != ctx.server.id:
            return await ctx.send(embeds=[error_embed("Not Found", "No event with that ID.")])
        if not await self.db.is_rsvped(event_id, ctx.author.id):
            return await ctx.send(embeds=[warn_embed("Not RSVPed", "You're not on the list for this event.")])
        await self.db.remove_rsvp(event_id, ctx.author.id)
        await ctx.send(embeds=[success_embed("RSVP Cancelled", f"You're no longer attending **{event['title']}**.")])

async def setup(bot):
    await bot.add_gear(Events(bot))
