# StoatBot

A full-featured Stoat bot built with `stoat.py` and SQLite (aiosqlite). Inspired by YAGPDB — includes tickets, giveaways, moderation, automod, reaction roles, welcome messages, and logging.

---

## Features

### 🎫 Tickets
- Open tickets with categories (support, billing, etc.)
- Ticket transcripts automatically saved to the database and sent as a `.txt` file when closed
- Staff-only management commands
- Per-server ticket log channel

### 🎉 Giveaways
- Timed giveaways with configurable end time
- Multiple winners
- Required role to enter
- **Alt protection:** minimum account age (days) and minimum message count
- Reroll command for ended giveaways
- Enter/leave by reacting with 🎉

### 🔨 Moderation
- Kick, ban, unban
- Timed mutes with automatic unmute (background task)
- Warnings system with IDs, history, and deletion
- Purge messages (optionally filter by user)
- Full mod action log in database
- Mod log channel for all actions

### 📋 Logging
- Message edits and deletes logged to a channel
- Member join/leave events
- Configurable log channel

### 👋 Welcome
- Fully customizable welcome message with placeholders: `{user}`, `{username}`, `{server}`, `{count}`, `{id}`
- Test command to preview
- Configurable welcome channel

### 🎭 Roles
- Reaction roles (add a reaction to a message → get a role)
  - Three modes: `toggle`, `add`, `remove`
- Auto roles on join
- Give/take role commands

### 🛡️ Automod
- Anti-spam (configurable threshold and interval)
- Anti-invite link filter
- Anti-excessive-caps filter
- Bad words filter
- Message counting for alt protection (giveaway entries use this)

---

## Setup

### 1. Prerequisites
- Python 3.10+
- Nothing else — the database is created automatically on first run

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Configure environment
```bash
cp .env.example .env
# Edit .env with your bot token and database URL
```

### 4. Create the database
```sql
CREATE DATABASE stoatbot;
```
The bot will create all tables automatically on first run.

### 5. Run the bot
```bash
python bot.py
```

---

## Configuration Commands (run in your server)

### First-time setup
```
!setlogchannel <channel_id>       — Set mod log channel
!setstaffrole <role_id>           — Set staff/mod role
!setmuterole <role_id>            — Set the mute role
!welcome setchannel <channel_id>  — Set welcome channel
!welcome setmessage Welcome {user} to {server}!
!logs setchannel <channel_id>     — Set audit log channel
!ticket setup <log_channel_id>    — Set ticket log channel
```

### Ticket categories
```
!ticket addcategory support 🛠️ General support questions
!ticket addcategory billing 💳 Payment and billing issues
```

### Automod
```
!automod spam true 5 5      — Block 5+ messages in 5 seconds
!automod invite true         — Block invite links
!automod caps true 70        — Block 70%+ caps messages
!automod badwords add badword
```

### Giveaways
```
!giveaway start 1h 1 Nitro                                    — Basic 1h giveaway
!giveaway start 24h 3 Custom Prize --role 123456              — Role required
!giveaway start 2h 1 Cool Prize --age 30 --messages 50        — Alt protection
!giveaway reroll <message_id>                                  — Reroll winners
!giveaway end <message_id>                                     — End early
```

---

## Project Structure

```
stoat-bot/
├── bot.py                  — Entry point
├── requirements.txt
├── .env.example
├── utils/
│   ├── db.py               — All database queries (asyncpg)
│   └── helpers.py          — Shared utilities, embed helpers, duration parser
└── cogs/
    ├── tickets.py          — Ticket system
    ├── giveaways.py        — Giveaway system
    ├── moderation.py       — Mod commands
    ├── welcome.py          — Welcome + auto roles
    ├── logging.py          — Audit logging
    ├── roles.py            — Reaction roles + role management
    └── automod.py          — Automod filters
```

---

## Database Tables

| Table | Purpose |
|---|---|
| `guild_config` | Per-server settings |
| `tickets` | Ticket records and transcripts |
| `ticket_categories` | Custom ticket categories |
| `giveaways` | Giveaway records |
| `giveaway_entries` | Individual entries per giveaway |
| `mod_actions` | Moderation history |
| `warnings` | Per-user warnings |
| `reaction_roles` | Reaction role mappings |
| `auto_roles` | Auto-assigned roles on join |
| `member_messages` | Message counts (alt protection) |
| `timed_mutes` | Active timed mutes |
| `automod_config` | Automod settings per server |
