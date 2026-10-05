import stoat
from stoat.ext import commands
import asyncio
import logging
import os
from dotenv import load_dotenv
from utils.db import Database

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("bot")

COGS = [
    "cogs.help",
    "cogs.tickets",
    "cogs.giveaways",
    "cogs.moderation",
    "cogs.welcome",
    "cogs.logging",
    "cogs.roles",
    "cogs.automod",
    "cogs.vouches",
    "cogs.reputation",
    "cogs.reminders",
    "cogs.serverstats",
    "cogs.trivia",
    "cogs.selfrole",
    "cogs.timezone",
    "cogs.invites",
    "cogs.events",
    "cogs.customcommands",
    # "cogs.slash_commands",  # DISABLED: this version of stoat.py has no slash_command API
]


class StoatBot(commands.Bot):
    def __init__(self, token: str):
        super().__init__(
            command_prefix=os.getenv("PREFIX") or "!",
            token=token,
        )
        self.db: Database = None

    async def on_ready(self, event: stoat.ReadyEvent):
        log.info(f"Logged in as {event.me.name} (ID: {event.me.id})")
        log.info(f"Connected to {len(event.servers)} server(s)")

    async def setup(self):
        self.db = Database()   # uses local stoat.db — no DATABASE_URL needed
        await self.db.connect()
        await self.db.init_tables()
        log.info("Database ready (stoat.db)")

        for cog in COGS:
            try:
                await self.load_extension(cog)
                log.info(f"Loaded cog: {cog}")
            except Exception as e:
                log.error(f"Failed to load cog {cog}: {e}")

    async def close(self):
        if self.db:
            await self.db.close()
        await super().close()


async def main():
    token = os.getenv("BOT_TOKEN")
    if not token:
        raise ValueError("BOT_TOKEN not set in .env")
    bot = StoatBot(token=token)
    await bot.setup()
    await bot.start()


if __name__ == "__main__":
    asyncio.run(main())
