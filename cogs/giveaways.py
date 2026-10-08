import stoat
from stoat.ext import commands
from utils.helpers import _delete_after, success_embed, error_embed, info_embed, warn_embed, parse_duration, utcnow, is_staff
import asyncio
import random
import logging
from datetime import datetime, timedelta

log = logging.getLogger("giveaways")

class Giveaways(commands.Gear):
    """Full-featured giveaway system with alt protection."""

    def __init__(self, bot):
        self.bot = bot
        self._task = None

    def cog_load(self):
        self._task = asyncio.create_task(self._giveaway_loop())

    def cog_unload(self):
        if self._task:
            self._task.cancel()

    @property
    def db(self):
        return self.bot.db

    async def _build_giveaway_embed(self, giveaway: dict, entry_ids: list[str] = None):
        if entry_ids is None:
            rows = await self.db.get_giveaway_entries(giveaway["id"])
            entry_ids = [r["user_id"] for r in rows]

        total = len(entry_ids)

        reqs = []
        if giveaway["required_role"]:
            reqs.append(f"• Must have role <@&{giveaway['required_role']}>")
        if giveaway["min_account_age_days"]:
            reqs.append(f"• Account must be at least **{giveaway['min_account_age_days']} days** old")
        if giveaway["min_messages"]:
            reqs.append(f"• Must have sent at least **{giveaway['min_messages']} messages** in this server")
        req_text = ("\n**Requirements:**\n" + "\n".join(reqs)) if reqs else ""

        entrants_line = ""
        if giveaway["ended"]:
            winners = giveaway["winners"] or []
            if winners:
                entrants_line = "\n\n**Winner(s):** " + " ".join(f"<@{w}>" for w in winners)
            else:
                entrants_line = "\n\n**Winner(s):** None"
        else:
            if total == 0:
                entrants_line = "\n\n🎉 **Entrants (0):** *None yet*"
            else:
                show = entry_ids[:20]
                mentions = " ".join(f"<@{uid}>" for uid in show)
                if total > 20:
                    mentions += f"\n*...and {total - 20} more*"
                entrants_line = f"\n\n🎉 **Entrants ({total}):** {mentions}"

        end_time = giveaway["ends_at"]
        timestamp = int(end_time.timestamp()) if hasattr(end_time, "timestamp") else int(
            datetime.fromisoformat(end_time).timestamp() if isinstance(end_time, str) else 0
        )

        desc = (
            f"**Prize:** {giveaway['prize']}\n"
            f"**Winners:** {giveaway['winner_count']}\n"
            f"**Hosted by:** <@{giveaway['host_id']}>\n"
            f"**Ends:** <t:{timestamp}:R> (<t:{timestamp}:f>)"
            f"{req_text}"
            f"{entrants_line}"
        )

        if not giveaway["ended"]:
            desc += "\n\nReact with 🎉 to enter!"

        return stoat.SendableEmbed(
            title="🎉 GIVEAWAY 🎉",
            description=desc,
            color="#FFD700",
        )

    async def _update_giveaway_message(self, giveaway: dict):
        if not giveaway.get("message_id"):
            return
        embed = await self._build_giveaway_embed(giveaway)
        try:
            channel = await self.bot.fetch_channel(giveaway["channel_id"])
            msg = await channel.fetch_message(giveaway["message_id"])
            await msg.edit(embeds=[embed])
        except Exception:
            pass

    # ── Background loop ────────────────────────────────────────────────────

    async def _giveaway_loop(self):
        await self.bot.wait_until_ready()
        while not self.bot.is_closed():
            try:
                active = await self.db.get_active_giveaways()
                for giveaway in active:
                    await self._end_giveaway(giveaway)
            except Exception as e:
                log.error(f"Giveaway loop error: {e}")
            await asyncio.sleep(15)

    async def _end_giveaway(self, giveaway: dict):
        entries = await self.db.get_giveaway_entries(giveaway["id"])
        entry_ids = [e["user_id"] for e in entries]

        guild = self.bot.get_server(giveaway["guild_id"])
        if not guild:
            return

        valid_entries = []
        for uid in entry_ids:
            try:
                member = await guild.fetch_member(uid)
                if member:
                    valid_entries.append(uid)
            except Exception:
                pass

        winner_count = min(giveaway["winner_count"], len(valid_entries))
        winners = random.sample(valid_entries, winner_count) if valid_entries else []
        await self.db.end_giveaway(giveaway["id"], winners)

        giveaway["ended"] = 1
        giveaway["winners"] = winners
        await self._update_giveaway_message(giveaway)

        try:
            channel = await self.bot.fetch_channel(giveaway["channel_id"])
            if winners:
                winner_mentions = " ".join(f"<@{w}>" for w in winners)
                embed = stoat.SendableEmbed(
                    title="🎉 Giveaway Ended!",
                    description=(
                        f"**Prize:** {giveaway['prize']}\n"
                        f"**Winner(s):** {winner_mentions}\n"
                        f"**Total entries:** {len(valid_entries)}"
                    ),
                    color="#FFD700",
                )
                await channel.send(
                    content=f"🎉 Congratulations {winner_mentions}! You won **{giveaway['prize']}**!",
                    embed=embed
                )
            else:
                await channel.send(embeds=[warn_embed("Giveaway Ended", f"No valid entries for **{giveaway['prize']}**.")])
        except Exception as e:
            log.error(f"Failed to send giveaway end message: {e}")

    # ── Prefix commands ────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @is_staff()
    async def giveaway(self, ctx):
        """Giveaway management."""
        await ctx.send(embeds=[info_embed("Giveaway Commands",
            "`giveaway start <duration> <winners> <prize>` — start a giveaway\n"
            "`giveaway end <message_id>` — end a giveaway early\n"
            "`giveaway reroll <message_id>` — reroll winners\n"
            "`giveaway info <message_id>` — show giveaway info\n"
            "`giveaway entrants <message_id>` — list all entrants\n\n"
            "**Options (append to start):**\n"
            "`--role <role_id>` — required role to enter\n"
            "`--age <days>` — minimum account age in days\n"
            "`--messages <count>` — minimum messages sent in this server"
        )])

    @giveaway.command()
    @is_staff()
    async def start(self, ctx, duration: str, winners: int, *, prize: str):
        """Start a giveaway. Usage: !giveaway start 1h 2 Nitro --role 123456 --age 30 --messages 50"""
        try:
            await ctx.message.delete()
        except Exception:
            pass

        required_role = None
        min_age = 0
        min_messages = 0

        parts = prize.split()
        clean_parts = []
        i = 0
        while i < len(parts):
            if parts[i] == "--role" and i + 1 < len(parts):
                required_role = parts[i + 1]; i += 2
            elif parts[i] == "--age" and i + 1 < len(parts):
                min_age = int(parts[i + 1]); i += 2
            elif parts[i] == "--messages" and i + 1 < len(parts):
                min_messages = int(parts[i + 1]); i += 2
            else:
                clean_parts.append(parts[i]); i += 1
        prize = " ".join(clean_parts)

        try:
            duration_secs = parse_duration(duration)
        except ValueError:
            return await ctx.send(embeds=[error_embed("Invalid Duration", "Use formats like `30m`, `2h`, `1d12h`.")])

        if winners < 1 or winners > 20:
            return await ctx.send(embeds=[error_embed("Invalid Winners", "Winner count must be between 1 and 20.")])

        ends_at = utcnow() + timedelta(seconds=duration_secs)

        giveaway = await self.db.create_giveaway(
            guild_id=ctx.server.id,
            channel_id=ctx.channel.id,
            host_id=ctx.author.id,
            prize=prize,
            winner_count=winners,
            ends_at=ends_at,
            required_role=required_role,
            min_account_age_days=min_age,
            min_messages=min_messages,
        )

        embed = await self._build_giveaway_embed(giveaway, [])
        msg = await ctx.channel.send(embeds=[embed])
        await self.db.set_giveaway_message(giveaway["id"], msg.id)

        try:
            await msg.react("🎉")
        except Exception as e:
            log.warning(f"Failed to add 🎉 reaction: {e}")

    @giveaway.command()
    @is_staff()
    async def end(self, ctx, message_id: str):
        """End a giveaway early."""
        try:
            await ctx.message.delete()
        except Exception:
            pass
        giveaway = await self.db.get_giveaway(message_id)
        if not giveaway:
            return await ctx.send(embeds=[error_embed("Not Found", "No giveaway found with that message ID.")])
        if giveaway["ended"]:
            return await ctx.send(embeds=[error_embed("Already Ended", "This giveaway has already ended.")])

        await self._end_giveaway(giveaway)
        await ctx.send(embeds=[success_embed("Giveaway Ended", f"Giveaway for **{giveaway['prize']}** ended.")])

    @giveaway.command()
    @is_staff()
    async def reroll(self, ctx, message_id: str, count: int = 1):
        """Reroll winner(s) for an ended giveaway."""
        try:
            await ctx.message.delete()
        except Exception:
            pass
        giveaway = await self.db.get_giveaway(message_id)
        if not giveaway:
            return await ctx.send(embeds=[error_embed("Not Found", "No giveaway found with that message ID.")])
        if not giveaway["ended"]:
            return await ctx.send(embeds=[error_embed("Still Active", "This giveaway hasn't ended yet.")])

        entries = await self.db.get_giveaway_entries(giveaway["id"])
        entry_ids = [e["user_id"] for e in entries]

        if not entry_ids:
            return await ctx.send(embeds=[warn_embed("No Entries", "No entries to reroll from.")])

        count = min(count, len(entry_ids))
        winners = random.sample(entry_ids, count)
        winner_mentions = " ".join(f"<@{w}>" for w in winners)

        await ctx.send(embeds=[stoat.SendableEmbed(
            title="🎲 Giveaway Rerolled!",
            description=f"New winner(s) for **{giveaway['prize']}**: {winner_mentions}",
            color="#FFD700",
        )])

    @giveaway.command()
    async def info(self, ctx, message_id: str):
        """Show info about a giveaway."""
        try:
            await ctx.message.delete()
        except Exception:
            pass
        giveaway = await self.db.get_giveaway(message_id)
        if not giveaway:
            return await ctx.send(embeds=[error_embed("Not Found", "No giveaway found with that message ID.")])

        entries = await self.db.get_giveaway_entries(giveaway["id"])
        status = "✅ Ended" if giveaway["ended"] else "🔄 Active"
        winners_text = ", ".join(f"<@{w}>" for w in (giveaway["winners"] or [])) or "None yet"

        embed = stoat.SendableEmbed(
            title=f"🎉 Giveaway — {giveaway['prize']}",
            description=(
                f"**Status:** {status}\n"
                f"**Entries:** {len(entries)}\n"
                f"**Winners:** {winners_text}\n"
                f"**Hosted by:** <@{giveaway['host_id']}>\n"
                f"**Ends/Ended:** <t:{int(giveaway['ends_at'].timestamp())}:f>"
            ),
            color="#FFD700",
        )
        await ctx.send(embeds=[embed])

    @giveaway.command()
    async def entrants(self, ctx, message_id: str):
        """List all entrants in a giveaway."""
        try:
            await ctx.message.delete()
        except Exception:
            pass
        giveaway = await self.db.get_giveaway(message_id)
        if not giveaway:
            return await ctx.send(embeds=[error_embed("Not Found", "No giveaway found with that message ID.")])

        rows = await self.db.get_giveaway_entries(giveaway["id"])
        entry_ids = [r["user_id"] for r in rows]

        if not entry_ids:
            return await ctx.send(embeds=[info_embed("No Entrants", f"No one has entered **{giveaway['prize']}** yet.")])

        mentions = " ".join(f"<@{uid}>" for uid in entry_ids)
        total = len(entry_ids)

        if len(mentions) <= 2000:
            await ctx.send(embeds=[stoat.SendableEmbed(
                title=f"🎉 Entrants — {giveaway['prize']} ({total})",
                description=mentions,
                color="#FFD700",
            )])
        else:
            parts = []
            current = []
            for uid in entry_ids:
                m = f"<@{uid}>"
                if len(" ".join(current + [m])) > 1800:
                    parts.append(current)
                    current = [m]
                else:
                    current.append(m)
            if current:
                parts.append(current)

            await ctx.send(embeds=[info_embed(f"🎉 Entrants — {giveaway['prize']} ({total})",
                f"There are **{total}** entrants. Showing them in chunks below:")])
            for chunk in parts:
                await ctx.send(" ".join(chunk))

    # ── Reaction handler for entering giveaways ────────────────────────────

    @commands.Gear.listener(to=stoat.MessageReactEvent)
    async def on_reaction_add(self, event: stoat.MessageReactEvent):
        """Handle 🎉 reaction to enter a giveaway."""
        if not hasattr(event, "message_id") or not hasattr(event, "user_id"):
            return
        emoji = getattr(event, "emoji", None) or getattr(event, "emoji_id", None)
        if emoji != "🎉":
            return

        giveaway = await self.db.get_giveaway(event.message_id)
        if not giveaway or giveaway["ended"]:
            return

        user_id = event.user_id
        guild = self.bot.get_server(giveaway["guild_id"])
        if not guild:
            return

        try:
            member = await guild.fetch_member(user_id)
        except Exception:
            return

        if not member or member.bot:
            return

        min_age = giveaway["min_account_age_days"]
        if min_age > 0 and member.joined_at:
            age_days = (utcnow() - member.joined_at).days
            if age_days < min_age:
                try:
                    ch = await self.bot.fetch_channel(giveaway["channel_id"])
                    _msg = await ch.send(f"<@{user_id}> Your account must be at least **{min_age} days** old to enter this giveaway.")
                    asyncio.create_task(_delete_after(_msg, 10))
                except Exception:
                    pass
                return

        min_msg = giveaway["min_messages"]
        if min_msg > 0:
            msg_count = await self.db.get_message_count(giveaway["guild_id"], user_id)
            if msg_count < min_msg:
                try:
                    ch = await self.bot.fetch_channel(giveaway["channel_id"])
                    _msg = await ch.send(f"<@{user_id}> You need at least **{min_msg} messages** in this server to enter.")
                    asyncio.create_task(_delete_after(_msg, 10))
                except Exception:
                    pass
                return

        req_role = giveaway["required_role"]
        if req_role:
            member_role_ids = [r.id for r in member.roles]
            if req_role not in member_role_ids:
                try:
                    ch = await self.bot.fetch_channel(giveaway["channel_id"])
                    _msg = await ch.send(f"<@{user_id}> You need the <@&{req_role}> role to enter this giveaway.")
                    asyncio.create_task(_delete_after(_msg, 10))
                except Exception:
                    pass
                return

        await self.db.enter_giveaway(giveaway["id"], user_id)
        await self._update_giveaway_message(giveaway)

    @commands.Gear.listener(to=stoat.MessageUnreactEvent)
    async def on_reaction_remove(self, event: stoat.MessageUnreactEvent):
        """Handle removing 🎉 to leave a giveaway."""
        if not hasattr(event, "message_id") or not hasattr(event, "user_id"):
            return
        emoji = getattr(event, "emoji", None) or getattr(event, "emoji_id", None)
        if emoji != "🎉":
            return

        giveaway = await self.db.get_giveaway(event.message_id)
        if not giveaway or giveaway["ended"]:
            return

        await self.db.leave_giveaway(giveaway["id"], event.user_id)
        await self._update_giveaway_message(giveaway)

async def setup(bot):
    await bot.add_gear(Giveaways(bot))
