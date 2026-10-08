import stoat
from stoat.ext import commands
from utils.helpers import success_embed, info_embed, warn_embed, is_staff
import logging
import random
import asyncio

log = logging.getLogger("trivia")

QUESTIONS = [
    {"q": "What is the capital of France?", "a": "paris"},
    {"q": "What planet is known as the Red Planet?", "a": "mars"},
    {"q": "What is the largest mammal?", "a": "blue whale"},
    {"q": "What year did World War II end?", "a": "1945"},
    {"q": "What element has the symbol 'O'?", "a": "oxygen"},
    {"q": "What is the fastest land animal?", "a": "cheetah"},
    {"q": "What language is the most spoken in the world?", "a": "mandarin"},
    {"q": "What is the square root of 144?", "a": "12"},
    {"q": "Who painted the Mona Lisa?", "a": "leonardo da vinci"},
    {"q": "What is the smallest country in the world?", "a": "vatican city"},
    {"q": "How many continents are there?", "a": "7"},
    {"q": "What gas do plants absorb from the atmosphere?", "a": "carbon dioxide"},
    {"q": "What is the hardest natural substance?", "a": "diamond"},
    {"q": "What ocean is the largest?", "a": "pacific"},
    {"q": "How many bones are in the human body?", "a": "206"},
    {"q": "What is the chemical symbol for gold?", "a": "au"},
    {"q": "Who wrote 'Romeo and Juliet'?", "a": "shakespeare"},
    {"q": "What is the tallest mountain in the world?", "a": "mount everest"},
    {"q": "What is the main ingredient in guacamole?", "a": "avocado"},
    {"q": "How many sides does a hexagon have?", "a": "6"},
    {"q": "What is the boiling point of water in Celsius?", "a": "100"},
    {"q": "Which country invented pizza?", "a": "italy"},
    {"q": "What is the largest organ in the human body?", "a": "skin"},
    {"q": "How many legs does a spider have?", "a": "8"},
    {"q": "What planet is closest to the sun?", "a": "mercury"},
    {"q": "What is the currency of Japan?", "a": "yen"},
    {"q": "In what year was the internet invented?", "a": "1983"},
    {"q": "What does USB stand for?", "a": "universal serial bus"},
    {"q": "How many teeth does an adult human have?", "a": "32"},
    {"q": "What is the largest desert in the world?", "a": "antarctic"},
    {"q": "Which animal is known as the 'King of the Jungle'?", "a": "lion"},
    {"q": "What is the circumference of the Earth in km?", "a": "40075"},
    {"q": "What gas makes up most of Earth's atmosphere?", "a": "nitrogen"},
    {"q": "How many Harry Potter books are there?", "a": "7"},
    {"q": "What is the deepest ocean trench?", "a": "mariana trench"},
    {"q": "What is the speed of light in km/s?", "a": "299792"},
]

class Trivia(commands.Gear):
    """Trivia game — answer questions and earn points."""

    def __init__(self, bot):
        self.bot = bot
        self._active_games = {}

    @property
    def db(self):
        return self.bot.db

    @commands.group(invoke_without_command=True)
    @is_staff()
    async def trivia(self, ctx):
        """Start a trivia session or view subcommands."""
        if ctx.channel.id in self._active_games:
            return await ctx.send(embeds=[warn_embed("Already Running", "A trivia session is already active in this channel.")])
        await self._start_game(ctx)

    @trivia.command(name="rank")
    @is_staff()
    async def trivia_rank(self, ctx, member: stoat.Member = None):
        """Show your or another member's trivia rank."""
        target = member or ctx.author
        data = await self.db.get_trivia_score(ctx.server.id, target.id)
        await ctx.send(embeds=[info_embed(
            f"Trivia Rank: {target.name}",
            f"**Score:** {data['score']}\n"
            f"**Streak:** {data['streak']} (best: {data['max_streak']})\n"
            f"**Correct:** {data['correct']}\n"
            f"**Incorrect:** {data['incorrect']}"
        )])

    @trivia.command(name="leaderboard", aliases=["lb", "top"])
    @is_staff()
    async def trivia_leaderboard(self, ctx, sort: str = "score"):
        """Show the trivia leaderboard. Sort by: score (default), streak, max_streak, correct."""
        top = await self.db.get_trivia_leaderboard(ctx.server.id, sort, 10)
        if not top:
            return await ctx.send(embeds=[info_embed("Trivia Leaderboard", "No trivia data yet.")])
        lines = []
        medals = ["🥇", "🥈", "🥉"]
        for i, row in enumerate(top):
            prefix = medals[i] if i < 3 else f"`#{i + 1:2}`"
            lines.append(f"{prefix} <@{row['user_id']}> — **{row['score']}** pts (streak: {row['streak']})")
        await ctx.send(embeds=[info_embed(f"Trivia Leaderboard (by {sort})", "\n".join(lines))])

    async def _start_game(self, ctx):
        game = {
            "channel": ctx.channel.id,
            "players": set(),
            "question": None,
            "answer": None,
            "active": True,
        }
        self._active_games[ctx.channel.id] = game
        await ctx.send(embeds=[info_embed("Trivia Started!",
            "Answer the questions in chat. Type `cancel` to stop. First correct answer wins a point!")])
        await asyncio.sleep(3)
        await self._next_question(ctx.channel, game)

    async def _next_question(self, channel, game):
        if not game["active"]:
            return
        q = random.choice(QUESTIONS)
        game["question"] = q["q"]
        game["answer"] = q["a"]
        game["players"].clear()
        await channel.send(embeds=[info_embed("❓ Trivia Question", q["q"])])
        self.bot.loop.call_later(30, lambda: asyncio.create_task(self._timeout_question(channel, game)))

    async def _timeout_question(self, channel, game):
        if not game["active"] or game["answer"] is None:
            return
        answer = game["answer"]
        game["answer"] = None
        await channel.send(embeds=[info_embed("⏰ Time's Up!", f"The answer was: **{answer}**")])
        await asyncio.sleep(3)
        await self._next_question(channel, game)

    @commands.Gear.listener(to=stoat.MessageCreateEvent)
    async def on_message(self, event: stoat.MessageCreateEvent):
        if not hasattr(event, "message") or not hasattr(event.message, "channel"):
            return
        channel_id = event.message.channel.id
        game = self._active_games.get(channel_id)
        if not game or not game["active"] or game["answer"] is None:
            return
        if event.message.author.bot:
            return
        content = event.message.content.strip().lower()
        if content == "cancel":
            game["active"] = False
            game["answer"] = None
            await event.message.channel.send(embeds=[info_embed("Trivia Ended", "Game cancelled.")])
            del self._active_games[channel_id]
            return
        correct = game["answer"].lower()
        if content == correct or content.startswith(correct):
            game["answer"] = None
            guild_id = getattr(event.message, "guild", None) or getattr(event.message, "server", None)
            if not guild_id:
                return
            guild_id = guild_id.id
            await self.db.update_trivia_score(guild_id, event.message.author.id, True)
            await event.message.channel.send(embeds=[success_embed("Correct!",
                f"<@{event.message.author.id}> got it right! The answer was **{correct}**.")])
            await asyncio.sleep(3)
            await self._next_question(event.message.channel, game)

async def setup(bot):
    await bot.add_gear(Trivia(bot))
