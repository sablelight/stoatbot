"""
db.py — SQLite backend (aiosqlite)
All data is stored in stoat.db in the bot's folder. No external database needed.
"""

import aiosqlite
import json
import logging
from datetime import datetime, timezone

log = logging.getLogger("db")

DB_PATH = "stoat.db"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_dt(s):
    """Parse an ISO datetime string back to a datetime object."""
    if s is None:
        return None
    try:
        return datetime.fromisoformat(s)
    except Exception:
        return None


class Row(dict):
    """dict subclass that also supports attribute access, mimicking asyncpg Record."""
    def __getattr__(self, item):
        try:
            return self[item]
        except KeyError:
            raise AttributeError(item)


def _row(cursor_row, description) -> Row:
    if cursor_row is None:
        return None
    keys = [d[0] for d in description]
    r = Row(zip(keys, cursor_row))
    # Convert ISO strings back to datetime where column name ends with _at
    for k, v in list(r.items()):
        if k.endswith("_at") and isinstance(v, str):
            r[k] = _parse_dt(v)
    # Parse JSON lists stored as text
    for k in ("winners", "bad_words"):
        if k in r and isinstance(r[k], str):
            try:
                r[k] = json.loads(r[k])
            except Exception:
                r[k] = []
    return r


def _rows(cursor_rows, description):
    return [_row(r, description) for r in cursor_rows]


class Database:
    def __init__(self, url: str = None):
        # url is ignored — we always use local SQLite
        self._conn: aiosqlite.Connection = None

    async def connect(self):
        self._conn = await aiosqlite.connect(DB_PATH)
        self._conn.row_factory = None          # we handle rows ourselves
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        log.info(f"SQLite database opened: {DB_PATH}")

    async def close(self):
        if self._conn:
            await self._conn.close()

    # ── Internal helpers ────────────────────────────────────────────────────

    async def _exec(self, sql, params=()):
        await self._conn.execute(sql, params)
        await self._conn.commit()

    async def _fetchone(self, sql, params=()):
        async with self._conn.execute(sql, params) as cur:
            row = await cur.fetchone()
            if row is None:
                return None
            return _row(row, cur.description)

    async def _fetchall(self, sql, params=()):
        async with self._conn.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return _rows(rows, cur.description)

    async def _fetchval(self, sql, params=()):
        async with self._conn.execute(sql, params) as cur:
            row = await cur.fetchone()
            return row[0] if row else None

    async def _insert_returning(self, sql, params=()):
        """Execute an INSERT and return the last inserted row by rowid."""
        async with self._conn.execute(sql, params) as cur:
            await self._conn.commit()
            rowid = cur.lastrowid
        # Re-query by rowid to return the full row
        table = sql.strip().split()[2]          # INSERT INTO <table> ...
        return await self._fetchone(f"SELECT * FROM {table} WHERE rowid=?", (rowid,))

    # ── Schema ──────────────────────────────────────────────────────────────

    async def init_tables(self):
        stmts = """
        CREATE TABLE IF NOT EXISTS guild_config (
            guild_id            TEXT PRIMARY KEY,
            prefix              TEXT DEFAULT '!',
            log_channel         TEXT,
            welcome_channel     TEXT,
            welcome_message     TEXT,
            mute_role           TEXT,
            staff_role          TEXT,
            mod_role            TEXT,
            buyer_role          TEXT,
            ticket_category     TEXT,
            ticket_log_channel  TEXT,
            created_at          TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS tickets (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id    TEXT NOT NULL,
            channel_id  TEXT UNIQUE NOT NULL,
            user_id     TEXT NOT NULL,
            category    TEXT DEFAULT 'general',
            status      TEXT DEFAULT 'open',
            transcript  TEXT,
            opened_at   TEXT DEFAULT (datetime('now')),
            closed_at   TEXT
        );

        CREATE TABLE IF NOT EXISTS ticket_categories (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id    TEXT NOT NULL,
            name        TEXT NOT NULL,
            description TEXT,
            emoji       TEXT,
            UNIQUE(guild_id, name)
        );

        CREATE TABLE IF NOT EXISTS giveaways (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id            TEXT NOT NULL,
            channel_id          TEXT NOT NULL,
            message_id          TEXT UNIQUE,
            host_id             TEXT NOT NULL,
            prize               TEXT NOT NULL,
            winner_count        INTEGER DEFAULT 1,
            required_role       TEXT,
            min_account_age_days INTEGER DEFAULT 0,
            min_messages        INTEGER DEFAULT 0,
            ends_at             TEXT NOT NULL,
            ended               INTEGER DEFAULT 0,
            winners             TEXT DEFAULT '[]',
            created_at          TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS giveaway_entries (
            giveaway_id INTEGER REFERENCES giveaways(id) ON DELETE CASCADE,
            user_id     TEXT NOT NULL,
            joined_at   TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (giveaway_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS mod_actions (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id     TEXT NOT NULL,
            target_id    TEXT NOT NULL,
            moderator_id TEXT NOT NULL,
            action       TEXT NOT NULL,
            reason       TEXT,
            duration     INTEGER,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS warnings (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id     TEXT NOT NULL,
            user_id      TEXT NOT NULL,
            moderator_id TEXT NOT NULL,
            reason       TEXT NOT NULL,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reaction_roles (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id   TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            message_id TEXT NOT NULL,
            emoji      TEXT NOT NULL,
            role_id    TEXT NOT NULL,
            mode       TEXT DEFAULT 'toggle',
            UNIQUE(message_id, emoji)
        );

        CREATE TABLE IF NOT EXISTS auto_roles (
            guild_id TEXT NOT NULL,
            role_id  TEXT NOT NULL,
            PRIMARY KEY (guild_id, role_id)
        );

        CREATE TABLE IF NOT EXISTS member_messages (
            guild_id      TEXT NOT NULL,
            user_id       TEXT NOT NULL,
            message_count INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS timed_mutes (
            guild_id  TEXT NOT NULL,
            user_id   TEXT NOT NULL,
            unmute_at TEXT NOT NULL,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS ticket_panels (
            guild_id   TEXT NOT NULL,
            message_id TEXT PRIMARY KEY
        );

        CREATE TABLE IF NOT EXISTS vouches (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id     TEXT NOT NULL,
            channel_id   TEXT,
            message_id   TEXT,
            author_id    TEXT NOT NULL,
            target_id    TEXT,
            content      TEXT NOT NULL,
            attachments  TEXT DEFAULT '[]',
            issue_number INTEGER,
            created_at   TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS automod_config (
            guild_id       TEXT PRIMARY KEY,
            anti_spam      INTEGER DEFAULT 0,
            anti_invite    INTEGER DEFAULT 0,
            anti_caps      INTEGER DEFAULT 0,
            caps_threshold INTEGER DEFAULT 70,
            spam_threshold INTEGER DEFAULT 5,
            spam_interval  INTEGER DEFAULT 5,
            bad_words      TEXT DEFAULT '[]'
        );

        CREATE TABLE IF NOT EXISTS reputation (
            guild_id   TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            rep        INTEGER DEFAULT 0,
            last_given TEXT,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS rep_log (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id   TEXT NOT NULL,
            giver_id   TEXT NOT NULL,
            target_id  TEXT NOT NULL,
            delta      INTEGER NOT NULL,
            reason     TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS reminders (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id   TEXT NOT NULL,
            channel_id TEXT NOT NULL,
            user_id    TEXT NOT NULL,
            message    TEXT NOT NULL,
            remind_at  TEXT NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS trivia_scores (
            guild_id      TEXT NOT NULL,
            user_id       TEXT NOT NULL,
            score         INTEGER DEFAULT 0,
            streak        INTEGER DEFAULT 0,
            max_streak    INTEGER DEFAULT 0,
            correct       INTEGER DEFAULT 0,
            incorrect     INTEGER DEFAULT 0,
            PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS self_roles (
            guild_id TEXT NOT NULL,
            role_id  TEXT NOT NULL,
            name     TEXT NOT NULL,
            description TEXT DEFAULT '',
            PRIMARY KEY (guild_id, role_id)
        );

        CREATE TABLE IF NOT EXISTS user_timezones (
            user_id  TEXT PRIMARY KEY,
            timezone TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS events (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id        TEXT NOT NULL,
            creator_id      TEXT NOT NULL,
            channel_id      TEXT,
            title           TEXT NOT NULL,
            description     TEXT DEFAULT '',
            event_time      TEXT,
            max_participants INTEGER DEFAULT 0,
            created_at      TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS event_rsvps (
            event_id INTEGER REFERENCES events(id) ON DELETE CASCADE,
            user_id  TEXT NOT NULL,
            PRIMARY KEY (event_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS custom_commands (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id     TEXT NOT NULL,
            trigger      TEXT NOT NULL,
            response     TEXT NOT NULL,
            trigger_type TEXT DEFAULT 'exact',
            created_at   TEXT DEFAULT (datetime('now')),
            UNIQUE(guild_id, trigger)
        );

        CREATE TABLE IF NOT EXISTS invite_codes (
            code       TEXT NOT NULL,
            guild_id   TEXT NOT NULL,
            creator_id TEXT NOT NULL,
            channel_id TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (code, guild_id)
        );

        CREATE TABLE IF NOT EXISTS invite_log (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id  TEXT NOT NULL,
            user_id   TEXT NOT NULL,
            inviter_id TEXT,
            invite_code TEXT,
            joined_at TEXT DEFAULT (datetime('now')),
            left_at   TEXT
        );
        """
        for stmt in stmts.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                await self._conn.execute(stmt)
        # Migration: add buyer_role column if missing (existing databases)
        try:
            await self._conn.execute("ALTER TABLE guild_config ADD COLUMN buyer_role TEXT")
        except Exception:
            pass
        await self._conn.commit()
        log.info("SQLite tables initialised")

    # ── Guild config ────────────────────────────────────────────────────────

    async def get_guild_config(self, guild_id: str) -> dict:
        row = await self._fetchone("SELECT * FROM guild_config WHERE guild_id=?", (guild_id,))
        return row if row else {}

    async def set_guild_config(self, guild_id: str, **kwargs):
        # Upsert: insert or update only the provided keys
        cols = list(kwargs.keys())
        vals = list(kwargs.values())
        placeholders = ",".join("?" * len(cols))
        set_clause   = ",".join(f"{c}=excluded.{c}" for c in cols)
        await self._exec(
            f"INSERT INTO guild_config (guild_id,{','.join(cols)}) VALUES (?{',?' * len(cols)}) "
            f"ON CONFLICT(guild_id) DO UPDATE SET {set_clause}",
            (guild_id, *vals)
        )

    # ── Tickets ─────────────────────────────────────────────────────────────

    async def create_ticket(self, guild_id, channel_id, user_id, category="general"):
        return await self._insert_returning(
            "INSERT INTO tickets (guild_id,channel_id,user_id,category) VALUES (?,?,?,?)",
            (guild_id, channel_id, user_id, category)
        )

    async def get_ticket(self, channel_id: str):
        return await self._fetchone("SELECT * FROM tickets WHERE channel_id=?", (channel_id,))

    async def get_ticket_by_id(self, ticket_id: int):
        return await self._fetchone("SELECT * FROM tickets WHERE id=?", (ticket_id,))

    async def close_ticket(self, channel_id: str, transcript: str = None):
        await self._exec(
            "UPDATE tickets SET status='closed', transcript=?, closed_at=? WHERE channel_id=?",
            (transcript, _now_iso(), channel_id)
        )

    async def get_user_open_tickets(self, guild_id, user_id):
        return await self._fetchall(
            "SELECT * FROM tickets WHERE guild_id=? AND user_id=? AND status='open'",
            (guild_id, user_id)
        )

    async def get_all_tickets(self, guild_id, status="open"):
        return await self._fetchall(
            "SELECT * FROM tickets WHERE guild_id=? AND status=? ORDER BY opened_at DESC",
            (guild_id, status)
        )

    async def get_ticket_categories(self, guild_id):
        return await self._fetchall("SELECT * FROM ticket_categories WHERE guild_id=?", (guild_id,))

    async def add_ticket_category(self, guild_id, name, description="", emoji="🎫"):
        await self._exec(
            "INSERT INTO ticket_categories (guild_id,name,description,emoji) VALUES (?,?,?,?) "
            "ON CONFLICT(guild_id,name) DO NOTHING",
            (guild_id, name, description, emoji)
        )

    async def add_ticket_panel(self, guild_id, message_id):
        await self._exec(
            "INSERT OR IGNORE INTO ticket_panels (guild_id,message_id) VALUES (?,?)",
            (guild_id, message_id)
        )

    async def remove_ticket_panel(self, message_id):
        await self._exec("DELETE FROM ticket_panels WHERE message_id=?", (message_id,))

    async def get_ticket_panel_guild(self, message_id):
        row = await self._fetchone("SELECT guild_id FROM ticket_panels WHERE message_id=?", (message_id,))
        return row["guild_id"] if row else None

    # ── Giveaways ───────────────────────────────────────────────────────────

    async def create_giveaway(self, guild_id, channel_id, host_id, prize,
                               winner_count, ends_at, required_role=None,
                               min_account_age_days=0, min_messages=0):
        ends_iso = ends_at.isoformat() if hasattr(ends_at, "isoformat") else ends_at
        return await self._insert_returning(
            "INSERT INTO giveaways (guild_id,channel_id,host_id,prize,winner_count,ends_at,"
            "required_role,min_account_age_days,min_messages) VALUES (?,?,?,?,?,?,?,?,?)",
            (guild_id, channel_id, host_id, prize, winner_count, ends_iso,
             required_role, min_account_age_days, min_messages)
        )

    async def set_giveaway_message(self, giveaway_id: int, message_id: str):
        await self._exec("UPDATE giveaways SET message_id=? WHERE id=?", (message_id, giveaway_id))

    async def get_giveaway(self, message_id: str):
        return await self._fetchone("SELECT * FROM giveaways WHERE message_id=?", (message_id,))

    async def get_active_giveaways(self):
        now = _now_iso()
        return await self._fetchall(
            "SELECT * FROM giveaways WHERE ended=0 AND ends_at<=?", (now,)
        )

    async def enter_giveaway(self, giveaway_id: int, user_id: str) -> bool:
        try:
            await self._exec(
                "INSERT INTO giveaway_entries (giveaway_id,user_id) VALUES (?,?)",
                (giveaway_id, user_id)
            )
            return True
        except Exception:
            return False

    async def leave_giveaway(self, giveaway_id: int, user_id: str):
        await self._exec(
            "DELETE FROM giveaway_entries WHERE giveaway_id=? AND user_id=?",
            (giveaway_id, user_id)
        )

    async def get_giveaway_entries(self, giveaway_id: int):
        return await self._fetchall(
            "SELECT user_id FROM giveaway_entries WHERE giveaway_id=?", (giveaway_id,)
        )

    async def end_giveaway(self, giveaway_id: int, winners: list):
        await self._exec(
            "UPDATE giveaways SET ended=1, winners=? WHERE id=?",
            (json.dumps(winners), giveaway_id)
        )

    # ── Moderation ──────────────────────────────────────────────────────────

    async def add_warning(self, guild_id, user_id, moderator_id, reason):
        return await self._insert_returning(
            "INSERT INTO warnings (guild_id,user_id,moderator_id,reason) VALUES (?,?,?,?)",
            (guild_id, user_id, moderator_id, reason)
        )

    async def get_warnings(self, guild_id, user_id):
        return await self._fetchall(
            "SELECT * FROM warnings WHERE guild_id=? AND user_id=? ORDER BY created_at DESC",
            (guild_id, user_id)
        )

    async def remove_warning(self, warning_id: int):
        await self._exec("DELETE FROM warnings WHERE id=?", (warning_id,))

    async def log_mod_action(self, guild_id, target_id, moderator_id, action, reason=None, duration=None):
        await self._exec(
            "INSERT INTO mod_actions (guild_id,target_id,moderator_id,action,reason,duration) "
            "VALUES (?,?,?,?,?,?)",
            (guild_id, target_id, moderator_id, action, reason, duration)
        )

    async def add_timed_mute(self, guild_id, user_id, unmute_at):
        unmute_iso = unmute_at.isoformat() if hasattr(unmute_at, "isoformat") else unmute_at
        await self._exec(
            "INSERT INTO timed_mutes (guild_id,user_id,unmute_at) VALUES (?,?,?) "
            "ON CONFLICT(guild_id,user_id) DO UPDATE SET unmute_at=excluded.unmute_at",
            (guild_id, user_id, unmute_iso)
        )

    async def remove_timed_mute(self, guild_id, user_id):
        await self._exec("DELETE FROM timed_mutes WHERE guild_id=? AND user_id=?", (guild_id, user_id))

    async def get_expired_mutes(self):
        return await self._fetchall(
            "SELECT * FROM timed_mutes WHERE unmute_at<=?", (_now_iso(),)
        )

    # ── Reaction roles ──────────────────────────────────────────────────────

    async def add_reaction_role(self, guild_id, channel_id, message_id, emoji, role_id, mode="toggle"):
        await self._exec(
            "INSERT INTO reaction_roles (guild_id,channel_id,message_id,emoji,role_id,mode) "
            "VALUES (?,?,?,?,?,?) ON CONFLICT(message_id,emoji) DO UPDATE SET role_id=excluded.role_id, mode=excluded.mode",
            (guild_id, channel_id, message_id, emoji, role_id, mode)
        )

    async def get_reaction_role(self, message_id, emoji):
        return await self._fetchone(
            "SELECT * FROM reaction_roles WHERE message_id=? AND emoji=?", (message_id, emoji)
        )

    async def get_all_reaction_roles(self, guild_id):
        return await self._fetchall("SELECT * FROM reaction_roles WHERE guild_id=?", (guild_id,))

    async def remove_reaction_role(self, message_id, emoji):
        await self._exec(
            "DELETE FROM reaction_roles WHERE message_id=? AND emoji=?", (message_id, emoji)
        )

    # ── Auto roles ──────────────────────────────────────────────────────────

    async def add_auto_role(self, guild_id, role_id):
        await self._exec(
            "INSERT INTO auto_roles VALUES (?,?) ON CONFLICT DO NOTHING", (guild_id, role_id)
        )

    async def remove_auto_role(self, guild_id, role_id):
        await self._exec("DELETE FROM auto_roles WHERE guild_id=? AND role_id=?", (guild_id, role_id))

    async def get_auto_roles(self, guild_id):
        return await self._fetchall("SELECT role_id FROM auto_roles WHERE guild_id=?", (guild_id,))

    # ── Message counts ───────────────────────────────────────────────────────

    async def increment_message_count(self, guild_id, user_id):
        await self._exec(
            "INSERT INTO member_messages (guild_id,user_id,message_count) VALUES (?,?,1) "
            "ON CONFLICT(guild_id,user_id) DO UPDATE SET message_count=message_count+1",
            (guild_id, user_id)
        )

    async def get_message_count(self, guild_id, user_id) -> int:
        val = await self._fetchval(
            "SELECT message_count FROM member_messages WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )
        return val or 0

    # ── Automod ─────────────────────────────────────────────────────────────

    # ── Vouches ─────────────────────────────────────────────────────────────

    async def add_vouch(self, guild_id, author_id, content, target_id=None, attachments=None, issue_number=None):
        return await self._insert_returning(
            "INSERT INTO vouches (guild_id,author_id,target_id,content,attachments,issue_number) "
            "VALUES (?,?,?,?,?,?)",
            (guild_id, author_id, target_id, content,
             json.dumps(attachments or []), issue_number)
        )

    async def update_vouch_message(self, vouch_id: int, channel_id: str, message_id: str):
        await self._exec(
            "UPDATE vouches SET channel_id=?, message_id=? WHERE id=?",
            (channel_id, message_id, vouch_id)
        )

    async def get_vouch(self, vouch_id: int):
        return await self._fetchone("SELECT * FROM vouches WHERE id=?", (vouch_id,))

    async def get_all_vouches(self, guild_id):
        return await self._fetchall(
            "SELECT * FROM vouches WHERE guild_id=? ORDER BY created_at DESC", (guild_id,)
        )

    async def get_vouches_by_issue(self, issue_number: int):
        return await self._fetchall(
            "SELECT * FROM vouches WHERE issue_number=?", (issue_number,)
        )

    async def get_vouches_by_author(self, guild_id, author_id):
        return await self._fetchall(
            "SELECT * FROM vouches WHERE guild_id=? AND author_id=? ORDER BY created_at DESC",
            (guild_id, author_id)
        )

    async def get_automod_config(self, guild_id):
        return await self._fetchone("SELECT * FROM automod_config WHERE guild_id=?", (guild_id,))

    async def set_automod_config(self, guild_id, **kwargs):
        for k, v in kwargs.items():
            if isinstance(v, list):
                kwargs[k] = json.dumps(v)
        cols = list(kwargs.keys())
        vals = list(kwargs.values())
        set_clause = ",".join(f"{c}=excluded.{c}" for c in cols)
        await self._exec(
            f"INSERT INTO automod_config (guild_id,{','.join(cols)}) VALUES (?{',?' * len(cols)}) "
            f"ON CONFLICT(guild_id) DO UPDATE SET {set_clause}",
            (guild_id, *vals)
        )

    # ── Reputation ─────────────────────────────────────────────────────────

    async def get_rep(self, guild_id, user_id):
        row = await self._fetchone(
            "SELECT * FROM reputation WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        )
        return row or {"guild_id": guild_id, "user_id": user_id, "rep": 0, "last_given": None}

    async def update_rep(self, guild_id, user_id, delta):
        await self._exec(
            "INSERT INTO reputation (guild_id,user_id,rep) VALUES (?,?,?) "
            "ON CONFLICT(guild_id,user_id) DO UPDATE SET rep=rep+?",
            (guild_id, user_id, delta, delta)
        )

    async def set_rep(self, guild_id, user_id, value):
        await self._exec(
            "INSERT INTO reputation (guild_id,user_id,rep) VALUES (?,?,?) "
            "ON CONFLICT(guild_id,user_id) DO UPDATE SET rep=?",
            (guild_id, user_id, value, value)
        )

    async def get_rep_leaderboard(self, guild_id, limit=10):
        return await self._fetchall(
            "SELECT * FROM reputation WHERE guild_id=? ORDER BY rep DESC LIMIT ?",
            (guild_id, limit)
        )

    async def log_rep(self, guild_id, giver_id, target_id, delta, reason=None):
        await self._exec(
            "INSERT INTO rep_log (guild_id,giver_id,target_id,delta,reason) VALUES (?,?,?,?,?)",
            (guild_id, giver_id, target_id, delta, reason)
        )

    async def get_rep_log(self, guild_id, target_id, limit=10):
        return await self._fetchall(
            "SELECT * FROM rep_log WHERE guild_id=? AND target_id=? ORDER BY created_at DESC LIMIT ?",
            (guild_id, target_id, limit)
        )

    async def delete_rep(self, guild_id, user_id):
        await self._exec("DELETE FROM reputation WHERE guild_id=? AND user_id=?", (guild_id, user_id))
        await self._exec("DELETE FROM rep_log WHERE guild_id=? AND target_id=?", (guild_id, user_id))

    # ── Reminders ──────────────────────────────────────────────────────────

    async def create_reminder(self, guild_id, channel_id, user_id, message, remind_at):
        return await self._insert_returning(
            "INSERT INTO reminders (guild_id,channel_id,user_id,message,remind_at) VALUES (?,?,?,?,?)",
            (guild_id, channel_id, user_id, message, remind_at)
        )

    async def get_due_reminders(self):
        return await self._fetchall(
            "SELECT * FROM reminders WHERE remind_at<=datetime('now')"
        )

    async def get_user_reminders(self, guild_id, user_id):
        return await self._fetchall(
            "SELECT * FROM reminders WHERE guild_id=? AND user_id=? ORDER BY remind_at ASC",
            (guild_id, user_id)
        )

    async def delete_reminder(self, reminder_id: int):
        await self._exec("DELETE FROM reminders WHERE id=?", (reminder_id,))

    # ── Trivia ─────────────────────────────────────────────────────────────

    async def get_trivia_score(self, guild_id, user_id):
        row = await self._fetchone(
            "SELECT * FROM trivia_scores WHERE guild_id=? AND user_id=?", (guild_id, user_id)
        )
        return row or {"guild_id": guild_id, "user_id": user_id, "score": 0, "streak": 0,
                        "max_streak": 0, "correct": 0, "incorrect": 0}

    async def update_trivia_score(self, guild_id, user_id, correct: bool):
        if correct:
            await self._exec(
                "INSERT INTO trivia_scores (guild_id,user_id,score,streak,max_streak,correct) "
                "VALUES (?,?,1,1,1,1) "
                "ON CONFLICT(guild_id,user_id) DO UPDATE SET "
                "score=score+1, streak=streak+1, correct=correct+1, "
                "max_streak=CASE WHEN streak+1>max_streak THEN streak+1 ELSE max_streak END",
                (guild_id, user_id)
            )
        else:
            await self._exec(
                "INSERT INTO trivia_scores (guild_id,user_id,streak,incorrect) VALUES (?,?,0,1) "
                "ON CONFLICT(guild_id,user_id) DO UPDATE SET "
                "streak=0, incorrect=incorrect+1",
                (guild_id, user_id)
            )

    async def get_trivia_leaderboard(self, guild_id, sort_by="score", limit=10):
        valid_sorts = {"score", "streak", "max_streak", "correct", "incorrect"}
        col = sort_by if sort_by in valid_sorts else "score"
        return await self._fetchall(
            f"SELECT * FROM trivia_scores WHERE guild_id=? ORDER BY {col} DESC LIMIT ?",
            (guild_id, limit)
        )

    async def reset_trivia_leaderboard(self, guild_id):
        await self._exec("DELETE FROM trivia_scores WHERE guild_id=?", (guild_id,))

    # ── Self-roles ─────────────────────────────────────────────────────────

    async def add_self_role(self, guild_id, role_id, name, description=""):
        await self._exec(
            "INSERT INTO self_roles (guild_id,role_id,name,description) VALUES (?,?,?,?) "
            "ON CONFLICT(guild_id,role_id) DO UPDATE SET name=excluded.name, description=excluded.description",
            (guild_id, role_id, name, description)
        )

    async def remove_self_role(self, guild_id, role_id):
        await self._exec("DELETE FROM self_roles WHERE guild_id=? AND role_id=?", (guild_id, role_id))

    async def get_self_roles(self, guild_id):
        return await self._fetchall("SELECT * FROM self_roles WHERE guild_id=?", (guild_id,))

    # ── Timezone ───────────────────────────────────────────────────────────

    async def set_user_timezone(self, user_id, tz):
        await self._exec(
            "INSERT INTO user_timezones (user_id,timezone) VALUES (?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET timezone=excluded.timezone",
            (user_id, tz)
        )

    async def get_user_timezone(self, user_id):
        row = await self._fetchone("SELECT timezone FROM user_timezones WHERE user_id=?", (user_id,))
        return row["timezone"] if row else None

    async def delete_user_timezone(self, user_id):
        await self._exec("DELETE FROM user_timezones WHERE user_id=?", (user_id,))

    # ── Events ─────────────────────────────────────────────────────────────

    async def create_event(self, guild_id, creator_id, title, description="",
                           event_time=None, max_participants=0, channel_id=None):
        return await self._insert_returning(
            "INSERT INTO events (guild_id,creator_id,channel_id,title,description,event_time,max_participants) "
            "VALUES (?,?,?,?,?,?,?)",
            (guild_id, creator_id, channel_id, title, description, event_time, max_participants)
        )

    async def get_event(self, event_id: int):
        return await self._fetchone("SELECT * FROM events WHERE id=?", (event_id,))

    async def get_guild_events(self, guild_id):
        return await self._fetchall(
            "SELECT * FROM events WHERE guild_id=? ORDER BY event_time ASC", (guild_id,)
        )

    async def update_event(self, event_id: int, **kwargs):
        cols = list(kwargs.keys())
        vals = list(kwargs.values())
        set_clause = ",".join(f"{c}=?" for c in cols)
        await self._exec(
            f"UPDATE events SET {set_clause} WHERE id=?", (*vals, event_id)
        )

    async def delete_event(self, event_id: int):
        await self._exec("DELETE FROM events WHERE id=?", (event_id,))

    async def add_rsvp(self, event_id: int, user_id: str) -> bool:
        try:
            await self._exec(
                "INSERT INTO event_rsvps (event_id,user_id) VALUES (?,?)", (event_id, user_id)
            )
            return True
        except Exception:
            return False

    async def remove_rsvp(self, event_id: int, user_id: str):
        await self._exec("DELETE FROM event_rsvps WHERE event_id=? AND user_id=?", (event_id, user_id))

    async def get_rsvps(self, event_id: int):
        return await self._fetchall(
            "SELECT user_id FROM event_rsvps WHERE event_id=?", (event_id,)
        )

    async def is_rsvped(self, event_id: int, user_id: str) -> bool:
        row = await self._fetchone(
            "SELECT 1 FROM event_rsvps WHERE event_id=? AND user_id=?", (event_id, user_id)
        )
        return row is not None

    # ── Custom Commands ─────────────────────────────────────────────────

    async def add_custom_command(self, guild_id, trigger, response, trigger_type="exact"):
        try:
            await self._exec(
                "INSERT INTO custom_commands (guild_id,trigger,response,trigger_type) VALUES (?,?,?,?)",
                (guild_id, trigger, response, trigger_type)
            )
            return True
        except Exception:
            return False

    async def remove_custom_command(self, guild_id, trigger):
        await self._exec(
            "DELETE FROM custom_commands WHERE guild_id=? AND trigger=?", (guild_id, trigger)
        )

    async def get_custom_commands(self, guild_id):
        return await self._fetchall(
            "SELECT * FROM custom_commands WHERE guild_id=? ORDER BY trigger ASC", (guild_id,)
        )

    async def get_custom_command(self, guild_id, trigger):
        return await self._fetchone(
            "SELECT * FROM custom_commands WHERE guild_id=? AND trigger=?", (guild_id, trigger)
        )

    async def get_all_custom_triggers(self, guild_id):
        rows = await self._fetchall(
            "SELECT trigger, response, trigger_type FROM custom_commands WHERE guild_id=?", (guild_id,)
        )
        return rows
        # Serialise lists to JSON
        for k, v in kwargs.items():
            if isinstance(v, list):
                kwargs[k] = json.dumps(v)
        cols = list(kwargs.keys())
        vals = list(kwargs.values())
        set_clause = ",".join(f"{c}=excluded.{c}" for c in cols)
        await self._exec(
            f"INSERT INTO automod_config (guild_id,{','.join(cols)}) VALUES (?{',?' * len(cols)}) "
            f"ON CONFLICT(guild_id) DO UPDATE SET {set_clause}",
            (guild_id, *vals)
        )

    # ── Invite Codes ────────────────────────────────────────────────────────

    async def sync_invite_codes(self, guild_id: str, codes: list[dict]):
        await self._exec("DELETE FROM invite_codes WHERE guild_id=?", (guild_id,))
        for c in codes:
            await self._exec(
                "INSERT INTO invite_codes (code,guild_id,creator_id,channel_id) VALUES (?,?,?,?)",
                (c["code"], guild_id, c["creator_id"], c.get("channel_id"))
            )

    async def get_invite_codes(self, guild_id: str):
        return await self._fetchall(
            "SELECT * FROM invite_codes WHERE guild_id=?", (guild_id,)
        )

    async def get_invite_creator(self, guild_id: str, code: str):
        row = await self._fetchone(
            "SELECT creator_id FROM invite_codes WHERE guild_id=? AND code=?",
            (guild_id, code)
        )
        return row["creator_id"] if row else None

    # ── Invite Log ──────────────────────────────────────────────────────────

    async def log_join(self, guild_id: str, user_id: str, inviter_id: str = None, invite_code: str = None):
        await self._exec(
            "INSERT INTO invite_log (guild_id,user_id,inviter_id,invite_code) VALUES (?,?,?,?)",
            (guild_id, user_id, inviter_id, invite_code)
        )

    async def log_leave(self, guild_id: str, user_id: str):
        await self._exec(
            "UPDATE invite_log SET left_at=? WHERE guild_id=? AND user_id=? AND left_at IS NULL",
            (_now_iso(), guild_id, user_id)
        )

    async def get_invite_count(self, guild_id: str, user_id: str) -> int:
        val = await self._fetchval(
            "SELECT COUNT(*) FROM invite_log WHERE guild_id=? AND inviter_id=? AND left_at IS NULL",
            (guild_id, user_id)
        )
        return val or 0

    async def get_total_invites(self, guild_id: str, user_id: str) -> int:
        val = await self._fetchval(
            "SELECT COUNT(*) FROM invite_log WHERE guild_id=? AND inviter_id=?",
            (guild_id, user_id)
        )
        return val or 0

    async def get_invite_leaderboard(self, guild_id: str, limit: int = 10):
        return await self._fetchall(
            "SELECT inviter_id, COUNT(*) AS cnt FROM invite_log "
            "WHERE guild_id=? AND left_at IS NULL "
            "GROUP BY inviter_id ORDER BY cnt DESC LIMIT ?",
            (guild_id, limit)
        )

    async def get_user_invites_detail(self, guild_id: str, user_id: str):
        return await self._fetchall(
            "SELECT * FROM invite_log WHERE guild_id=? AND inviter_id=? ORDER BY joined_at DESC",
            (guild_id, user_id)
        )

    async def get_join_log(self, guild_id: str, user_id: str):
        row = await self._fetchone(
            "SELECT * FROM invite_log WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        )
        return row

    async def get_invite_stats(self, guild_id: str):
        total_joins = await self._fetchval(
            "SELECT COUNT(*) FROM invite_log WHERE guild_id=?", (guild_id,)
        )
        tracked = await self._fetchval(
            "SELECT COUNT(*) FROM invite_log WHERE guild_id=? AND inviter_id IS NOT NULL",
            (guild_id,)
        )
        return {"total_joins": total_joins or 0, "tracked": tracked or 0}
