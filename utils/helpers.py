import stoat
from stoat.ext import commands
from datetime import datetime, timezone
import re


def parse_duration(duration_str: str) -> int:
    """Parse a duration string like '1h30m' into seconds."""
    pattern = re.compile(r"(?:(\d+)d)?(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?")
    match = pattern.fullmatch(duration_str.strip())
    if not match or not any(match.groups()):
        raise ValueError(f"Invalid duration: {duration_str}")
    days, hours, minutes, seconds = (int(x or 0) for x in match.groups())
    return days * 86400 + hours * 3600 + minutes * 60 + seconds


def format_duration(seconds: int) -> str:
    """Format seconds into a human-readable string."""
    parts = []
    for unit, div in [("d", 86400), ("h", 3600), ("m", 60), ("s", 1)]:
        val, seconds = divmod(seconds, div)
        if val:
            parts.append(f"{val}{unit}")
    return " ".join(parts) if parts else "0s"


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def success_embed(title: str, description: str = None) -> stoat.SendableEmbed:
    return stoat.SendableEmbed(
        title=f"✅ {title}",
        description=description,
        color="#57F287",
    )


def error_embed(title: str, description: str = None) -> stoat.SendableEmbed:
    return stoat.SendableEmbed(
        title=f"❌ {title}",
        description=description,
        color="#ED4245",
    )


def info_embed(title: str, description: str = None) -> stoat.SendableEmbed:
    return stoat.SendableEmbed(
        title=f"ℹ️ {title}",
        description=description,
        color="#5865F2",
    )


def warn_embed(title: str, description: str = None) -> stoat.SendableEmbed:
    return stoat.SendableEmbed(
        title=f"⚠️ {title}",
        description=description,
        color="#FEE75C",
    )


def is_staff():
    """Check if the user has the staff role or server manage permissions."""
    async def predicate(ctx: commands.Context):
        if ctx.author.id == ctx.server.owner_id:
            return True
        cfg = await ctx.bot.db.get_guild_config(ctx.server.id)
        staff_role = cfg.get("staff_role")
        mod_role = cfg.get("mod_role")
        author_roles = [r.id for r in ctx.author.roles]
        if staff_role and staff_role in author_roles:
            return True
        if mod_role and mod_role in author_roles:
            return True
        # Check server manage permission
        perms = ctx.author.server_permissions
        return bool(perms.manage_server)
    return commands.check(predicate)


async def _delete_after(message, delay: float = 5.0):
    """Delete a message after a delay (stoat has no native delete_after)."""
    import asyncio
    await asyncio.sleep(delay)
    try:
        await message.delete()
    except Exception:
        pass
