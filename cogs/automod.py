import stoat
from stoat.ext import commands
from utils.helpers import success_embed, error_embed, info_embed, is_staff, _delete_after
from collections import defaultdict, deque
import asyncio
import time
import re
import logging

log = logging.getLogger("automod")

INVITE_PATTERN = re.compile(r"(discord\.gg|discord\.com/invite|stoat\.chat|rvlt\.gg)/\S+", re.IGNORECASE)


class Automod(commands.Gear):
    """Automatic moderation: spam, invites, caps, bad words, message tracking."""

    def __init__(self, bot):
        self.bot = bot
        # In-memory spam tracker: {guild_id: {user_id: deque of timestamps}}
        self._spam_tracker: dict[str, dict[str, deque]] = defaultdict(lambda: defaultdict(deque))

    @property
    def db(self):
        return self.bot.db

    # ── Message listener ───────────────────────────────────────────────────

    @commands.Gear.listener(to=stoat.MessageCreateEvent)
    async def on_message_create(self, event: stoat.MessageCreateEvent):
        message = event.message
        if not message.content or not message.server:
            return
        if message.author and message.author.bot:
            return

        guild_id = message.server.id
        user_id = message.author.id

        # Track message count for alt protection
        await self.db.increment_message_count(guild_id, user_id)

        cfg = await self.db.get_automod_config(guild_id)
        if not cfg:
            return

        content = message.content

        # ── Anti-spam ──────────────────────────────────────────────────────
        if cfg["anti_spam"]:
            threshold = cfg["spam_threshold"] or 5
            interval = cfg["spam_interval"] or 5
            now = time.time()
            user_msgs = self._spam_tracker[guild_id][user_id]
            user_msgs.append(now)
            # Remove old timestamps outside the interval
            while user_msgs and user_msgs[0] < now - interval:
                user_msgs.popleft()
            if len(user_msgs) >= threshold:
                user_msgs.clear()
                try:
                    await message.delete()
                    _msg = await message.channel.send(f"<@{user_id}> ⚠️ Please stop spamming.")
                    asyncio.create_task(_delete_after(_msg, 8))
                except Exception:
                    pass
                return

        # ── Anti-invite ────────────────────────────────────────────────────
        if cfg["anti_invite"] and INVITE_PATTERN.search(content):
            try:
                await message.delete()
                _msg = await message.channel.send(f"<@{user_id}> ⚠️ Invite links are not allowed here.")
                asyncio.create_task(_delete_after(_msg, 8))
            except Exception:
                pass
            return

        # ── Anti-caps ──────────────────────────────────────────────────────
        if cfg["anti_caps"] and len(content) > 10:
            caps = sum(1 for c in content if c.isupper())
            threshold = cfg["caps_threshold"] or 70
            if (caps / len(content)) * 100 >= threshold:
                try:
                    await message.delete()
                    _msg = await message.channel.send(f"<@{user_id}> ⚠️ Please don't use excessive caps.")
                    asyncio.create_task(_delete_after(_msg, 8))
                except Exception:
                    pass
                return

        # ── Bad words ──────────────────────────────────────────────────────
        bad_words = cfg["bad_words"] or []
        if bad_words:
            lower = content.lower()
            for word in bad_words:
                if word.lower() in lower:
                    try:
                        await message.delete()
                        _msg = await message.channel.send(f"<@{user_id}> ⚠️ Your message contained a prohibited word.")
                        asyncio.create_task(_delete_after(_msg, 8))
                    except Exception:
                        pass
                    return

    # ── Config commands ────────────────────────────────────────────────────

    @commands.group(invoke_without_command=True)
    @is_staff()
    async def automod(self, ctx):
        """Automod configuration."""
        cfg = await self.db.get_automod_config(ctx.server.id)
        if not cfg:
            return await ctx.send(embeds=[info_embed("Automod", "No automod configured yet. Use subcommands to set up.")])
        await ctx.send(embeds=[info_embed("Automod Config",
            f"**Anti-spam:** {'✅' if cfg['anti_spam'] else '❌'} (threshold: {cfg['spam_threshold']} msgs / {cfg['spam_interval']}s)\n"
            f"**Anti-invite:** {'✅' if cfg['anti_invite'] else '❌'}\n"
            f"**Anti-caps:** {'✅' if cfg['anti_caps'] else '❌'} (threshold: {cfg['caps_threshold']}%)\n"
            f"**Bad words:** {len(cfg['bad_words'] or [])} words blocked\n\n"
            "Use `automod spam`, `automod invite`, `automod caps`, `automod badwords` to configure."
        )])

    @automod.command()
    @is_staff()
    async def spam(self, ctx, enabled: bool = True, threshold: int = 5, interval: int = 5):
        """
        Configure anti-spam.
        Usage: !automod spam true 5 5  (5 messages in 5 seconds triggers it)
        """
        await self.db.set_automod_config(
            ctx.server.id,
            anti_spam=enabled,
            spam_threshold=threshold,
            spam_interval=interval
        )
        status = "enabled" if enabled else "disabled"
        await ctx.send(embeds=[success_embed("Anti-Spam Updated",
            f"Anti-spam {status}. Triggers after **{threshold}** messages in **{interval}s**.")])

    @automod.command()
    @is_staff()
    async def invite(self, ctx, enabled: bool = True):
        """Enable or disable anti-invite filter."""
        await self.db.set_automod_config(ctx.server.id, anti_invite=enabled)
        await ctx.send(embeds=[success_embed("Anti-Invite Updated",
            f"Anti-invite {'enabled' if enabled else 'disabled'}.")])

    @automod.command()
    @is_staff()
    async def caps(self, ctx, enabled: bool = True, threshold: int = 70):
        """Enable or disable caps filter. Threshold is % of caps (default 70)."""
        await self.db.set_automod_config(ctx.server.id, anti_caps=enabled, caps_threshold=threshold)
        await ctx.send(embeds=[success_embed("Anti-Caps Updated",
            f"Anti-caps {'enabled' if enabled else 'disabled'} (threshold: {threshold}%).")])

    @automod.group(invoke_without_command=True)
    @is_staff()
    async def badwords(self, ctx):
        """Manage the blocked words list."""
        cfg = await self.db.get_automod_config(ctx.server.id)
        words = cfg["bad_words"] if cfg else []
        await ctx.send(embeds=[info_embed("Blocked Words",
            ", ".join(f"`{w}`" for w in words) if words else "No words blocked.\n\n"
            "Use `automod badwords add <word>` and `automod badwords remove <word>`."
        )])

    @badwords.command(name="add")
    @is_staff()
    async def badwords_add(self, ctx, *, word: str):
        """Add a word to the blocked list."""
        cfg = await self.db.get_automod_config(ctx.server.id)
        words = list(cfg["bad_words"] or []) if cfg else []
        word = word.lower().strip()
        if word not in words:
            words.append(word)
        await self.db.set_automod_config(ctx.server.id, bad_words=words)
        await ctx.send(embeds=[success_embed("Word Added", f"`{word}` added to blocked words.")])

    @badwords.command(name="remove")
    @is_staff()
    async def badwords_remove(self, ctx, *, word: str):
        """Remove a word from the blocked list."""
        cfg = await self.db.get_automod_config(ctx.server.id)
        words = list(cfg["bad_words"] or []) if cfg else []
        word = word.lower().strip()
        if word in words:
            words.remove(word)
        await self.db.set_automod_config(ctx.server.id, bad_words=words)
        await ctx.send(embeds=[success_embed("Word Removed", f"`{word}` removed from blocked words.")])


async def setup(bot):
    await bot.add_gear(Automod(bot))
