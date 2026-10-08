from stoat.ext import commands
from utils.helpers import info_embed, is_staff

HELP_TEXT = """
**🎫 Tickets**
`!new <category>` — Open a ticket
`!close [reason]` — Close current ticket
`!ticket close <#id> [reason]` — Close ticket by number
`!ticket closeall` — Close all open tickets
`!ticket setup <log_channel>` — Configure ticket system
`!ticket addcategory <name> <emoji> [desc]` — Add category
`!ticket panel` — Post reaction ticket panel
`!ticket transcript` — View transcript
`!ticket list` — List open tickets

**🎉 Giveaways**
`!giveaway start <duration> <winners> <prize>` — Start giveaway
   Options: `--role <id>` (required role), `--age <days>` (min account age), `--messages <count>` (min messages)
`!giveaway end <message_id>` — End early
`!giveaway reroll <message_id> [count]` — Reroll winners
`!giveaway info <message_id>` — Show info
`!giveaway entrants <message_id>` — List entrants

**🛡️ Moderation**
`!kick <member> [reason]` — Kick member
`!ban <member> [reason]` — Ban member
`!unban <user_id> [reason]` — Unban user
`!mute <member> [duration] [reason]` — Mute member
`!unmute <member> [reason]` — Unmute member
`!warn <member> <reason>` — Warn member
`!warnings <member>` — View warnings
`!delwarn <id>` — Delete warning
`!purge <count>` — Delete messages (max 100)
`!purgefrom <member> [count]` — Delete member's messages
`!purgeall` — Delete all messages in channel
`!modlogs <member>` — View moderation history
`!setmuterole <role_id>` — Set mute role
`!setstaffrole <role_id>` — Set staff role
`!setlogchannel <channel_id>` — Set log channel

**👥 Roles**
`!reactionrole add <msg_id> <emoji> <role_id>` — Add reaction role
`!reactionrole remove <msg_id> <emoji>` — Remove reaction role
`!reactionrole list` — List reaction roles
`!giverole <member> <role_id>` — Give role
`!takerole <member> <role_id>` — Remove role
`!roles [member]` — Show roles
`!role [name]` — Toggle a self-assignable role

**🤖 Auto-mod**
`!automod spam <on/off> [threshold] [interval]` — Anti-spam
`!automod invite <on/off>` — Anti-invite
`!automod caps <on/off> [threshold]` — Anti-caps
`!automod badwords add <word>` — Block word
`!automod badwords remove <word>` — Unblock word

**👋 Welcome**
`!welcome setchannel <channel_id>` — Set welcome channel
`!welcome setmessage <text>` — Set welcome message
`!welcome test` — Preview welcome message
`!autorole add <role_id>` — Auto-assign role on join
`!autorole remove <role_id>` — Remove auto-role

**📜 Logging**
`!logs setchannel <channel_id>` — Set log channel
`!logs disable` — Disable logging

**⭐ Reputation**
`!rep [member]` — Show rep
`!rep give <member> [reason]` — Give +rep
`!rep take <member> [reason]` — Give -rep
`!rep leaderboard` — Top rep users
`!rep log [member]` — Rep history
`!rep set <member> <value>` — Set rep (staff)
`!rep delete <member>` — Clear rep (staff)

**🔗 Invites**
`!invites` — Your invite stats
`!invites leaderboard` — Top inviters
`!invites info <user>` — Someone's invites
`!invites codes` — List invite codes (staff)
`!inviteinfo` — Quick invite stats

**⏰ Reminders**
`!remindme <duration> <message>` — Set a reminder
`!listreminders` — List your reminders
`!deletereminder <id>` — Delete a reminder

**📊 Server Stats**
`!stats` — Show server statistics

**❓ Trivia**
`!trivia` — Start a trivia game
`!trivia rank [member]` — Show trivia score
`!trivia leaderboard [sort]` — Trivia leaderboard

**📍 Timezone**
`!settimezone <tz>` — Set your timezone
`!time [member]` — Show member's current time
`!mytimezone` — Show your timezone
`!deletetimezone` — Remove your timezone

**📅 Events**
`!events create <title>` — Create event
`!events list` — List events
`!events info <id>` — Event details
`!events edit <id> <opts>` — Edit event
`!events delete <id>` — Delete event
`!events rsvp <id>` — RSVP to event
`!events unrsvp <id>` — Cancel RSVP

**⚙️ Custom Commands**
`!customcommand add <trigger> <response>` — Add custom command
`!customcommand remove <trigger>` — Remove custom command
`!customcommand list` — List custom commands

**📋 Self Roles**
`!selfrole add <role_id> <name>` — Add assignable role
`!selfrole remove <role_id>` — Remove assignable role
`!selfrole list` — List assignable roles
"""

class Help(commands.Gear):
    """Built-in help command."""

    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @is_staff()
    async def help(self, ctx):
        """Show all available commands."""
        prefix = ctx.prefix or "!"
        formatted = HELP_TEXT.replace("`!", f"`{prefix}")
        await ctx.send(embeds=[info_embed("Commands", formatted.strip())])

async def setup(bot):
    await bot.add_gear(Help(bot))
