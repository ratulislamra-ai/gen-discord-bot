import sqlite3
import asyncio
import os
from typing import Optional, Dict, Any

from config.settings import DB_PATH

def _get_connection():
    """Helper function to create a database connection with row factory."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def _init_db_sync():
    """Synchronously initialize SQLite database tables, columns, and indexes."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        # Create base tickets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                guild_id INTEGER NOT NULL,
                channel_id INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_user_guild_status 
            ON tickets(user_id, guild_id, status);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_channel_id 
            ON tickets(channel_id);
        """)

        # Safely migrate schema: add team & tournament columns if missing
        cursor.execute("PRAGMA table_info(tickets);")
        columns = [column[1] for column in cursor.fetchall()]
        if "tournament_name" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN tournament_name TEXT;")
        if "team_name" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN team_name TEXT;")
        if "captain_name" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN captain_name TEXT;")
        if "captain_discord_id" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN captain_discord_id TEXT;")
        if "captain_phone" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN captain_phone TEXT;")
        if "registration_code" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN registration_code TEXT;")
        if "submitted_at" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN submitted_at TIMESTAMP;")
        if "team_logo_url" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN team_logo_url TEXT;")
        if "approved_at" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN approved_at TIMESTAMP;")
        if "approved_by" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN approved_by TEXT;")
        if "rejected_at" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN rejected_at TIMESTAMP;")
        if "rejected_by" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN rejected_by TEXT;")
        if "rejection_reason" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN rejection_reason TEXT;")
        if "review_channel_id" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN review_channel_id INTEGER;")
        if "review_message_id" not in columns:
            cursor.execute("ALTER TABLE tickets ADD COLUMN review_message_id INTEGER;")

        # Create bot_settings table for storing key-value configurations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bot_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Create roster_players table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS roster_players (
                roster_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                player_role TEXT NOT NULL,
                ign TEXT NOT NULL,
                discord_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (ticket_id) REFERENCES tickets (ticket_id) ON DELETE CASCADE
            );
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_roster_ticket_id 
            ON roster_players(ticket_id);
        """)

        # -------------------------------------------------------------
        # Extended Normalized Platform Entities
        # -------------------------------------------------------------
        
        # users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                discord_id TEXT UNIQUE,
                username TEXT NOT NULL,
                email TEXT,
                role TEXT NOT NULL DEFAULT 'PLAYER',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # admins table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS admins (
                admin_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL UNIQUE,
                permissions_level TEXT NOT NULL DEFAULT 'SUPERADMIN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (user_id) ON DELETE CASCADE
            );
        """)

        # tournaments table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tournaments (
                tournament_id INTEGER PRIMARY KEY AUTOINCREMENT,
                slug TEXT UNIQUE NOT NULL,
                title TEXT NOT NULL,
                game_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'REGISTRATION_OPEN',
                max_teams INTEGER NOT NULL DEFAULT 16,
                start_date TIMESTAMP,
                banner_url TEXT,
                rules_text TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # teams table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                tag TEXT,
                logo_url TEXT,
                captain_discord_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # players table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ign TEXT NOT NULL,
                discord_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # team_players junction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_players (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                role TEXT NOT NULL,
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (team_id) REFERENCES teams (team_id) ON DELETE CASCADE,
                FOREIGN KEY (player_id) REFERENCES players (player_id) ON DELETE CASCADE
            );
        """)

        # matches table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS matches (
                match_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                stage_name TEXT NOT NULL,
                team1_id INTEGER,
                team2_id INTEGER,
                team1_score INTEGER DEFAULT 0,
                team2_score INTEGER DEFAULT 0,
                winner_id INTEGER,
                status TEXT NOT NULL DEFAULT 'SCHEDULED',
                scheduled_time TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tournament_id) REFERENCES tournaments (tournament_id) ON DELETE CASCADE
            );
        """)

        # brackets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS brackets (
                bracket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                round_number INTEGER NOT NULL,
                match_id INTEGER NOT NULL,
                position_index INTEGER NOT NULL,
                FOREIGN KEY (tournament_id) REFERENCES tournaments (tournament_id) ON DELETE CASCADE,
                FOREIGN KEY (match_id) REFERENCES matches (match_id) ON DELETE CASCADE
            );
        """)

        # results table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS results (
                result_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                rank INTEGER NOT NULL,
                prize_amount REAL DEFAULT 0.0,
                points INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (tournament_id) REFERENCES tournaments (tournament_id) ON DELETE CASCADE,
                FOREIGN KEY (team_id) REFERENCES teams (team_id) ON DELETE CASCADE
            );
        """)

        # media table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS media (
                media_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                file_path TEXT NOT NULL,
                file_url TEXT NOT NULL,
                mime_type TEXT NOT NULL,
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # audit_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                admin_id TEXT NOT NULL,
                action TEXT NOT NULL,
                tournament_id INTEGER,
                details TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # Safely migrate schema: add tournament & match columns if missing
        cursor.execute("PRAGMA table_info(tournaments);")
        t_cols = [col[1] for col in cursor.fetchall()]
        if "description" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN description TEXT;")
        if "registration_start" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN registration_start TIMESTAMP;")
        if "registration_deadline" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN registration_deadline TIMESTAMP;")
        if "tournament_start" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN tournament_start TIMESTAMP;")
        if "tournament_end" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN tournament_end TIMESTAMP;")
        if "prize_info" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN prize_info TEXT;")
        if "format" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN format TEXT DEFAULT 'Single Elimination';")
        if "registration_status" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN registration_status TEXT DEFAULT 'OPEN';")
        if "min_players" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN min_players INTEGER DEFAULT 5;")
        if "max_players" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN max_players INTEGER DEFAULT 6;")
        if "logo_url" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN logo_url TEXT;")
        if "updated_at" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN updated_at TIMESTAMP;")

        cursor.execute("PRAGMA table_info(matches);")
        m_cols = [col[1] for col in cursor.fetchall()]
        if "round_number" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN round_number INTEGER DEFAULT 1;")
        if "lobby_info" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN lobby_info TEXT;")
        if "match_code" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN match_code TEXT;")

        # Seed initial tournaments if empty or purge legacy seeds
        cursor.execute("DELETE FROM tournaments WHERE slug = 'gen-lol-cup' OR LOWER(game_type) LIKE '%league%' OR LOWER(title) LIKE '%league%';")
        cursor.execute("UPDATE tickets SET tournament_name = 'GEN PUBG Mobile Championship' WHERE tournament_name LIKE '%League%';")

        cursor.execute("SELECT COUNT(*) FROM tournaments;")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO tournaments (slug, title, game_type, status, registration_status, max_teams, prize_info, description, rules_text) VALUES
                ('gen-valorant-championship', 'GEN Valorant Championship', 'VALORANT', 'REGISTRATION_OPEN', 'OPEN', 16, '$500 USD', 'Official GEN Esports 5v5 VALORANT Tournament Series.', 'GEN Esports 5v5 VALORANT Tournament Series Rules.'),
                ('gen-pubg-mobile-championship', 'GEN PUBG Mobile Championship', 'PUBG MOBILE', 'REGISTRATION_OPEN', 'OPEN', 16, '$300 USD', 'Official GEN Esports PUBG Mobile Championship.', 'GEN Esports PUBG Mobile Championship Rules.');
            """)
        else:
            # Ensure PUBG Mobile tournament exists and update defaults
            cursor.execute("SELECT COUNT(*) FROM tournaments WHERE slug = 'gen-pubg-mobile-championship';")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO tournaments (slug, title, game_type, status, registration_status, max_teams, prize_info, description, rules_text) VALUES
                    ('gen-pubg-mobile-championship', 'GEN PUBG Mobile Championship', 'PUBG MOBILE', 'REGISTRATION_OPEN', 'OPEN', 16, '$300 USD', 'Official GEN Esports PUBG Mobile Championship.', 'GEN Esports PUBG Mobile Championship Rules.');
                """)
            cursor.execute("UPDATE tournaments SET registration_status = 'OPEN' WHERE registration_status IS NULL OR registration_status = '';")

        conn.commit()

async def init_db():
    """Asynchronously initialize the database schema."""
    await asyncio.to_thread(_init_db_sync)

def _create_ticket_sync(user_id: int, guild_id: int, channel_id: int) -> int:
    """Synchronously insert a new ticket record."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tickets (user_id, guild_id, channel_id, status)
            VALUES (?, ?, ?, 'OPEN');
        """, (user_id, guild_id, channel_id))
        conn.commit()
        return cursor.lastrowid

async def create_ticket(user_id: int, guild_id: int, channel_id: int) -> int:
    """Asynchronously create a ticket record in SQLite."""
    return await asyncio.to_thread(_create_ticket_sync, user_id, guild_id, channel_id)

def _get_active_ticket_sync(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Synchronously query if user has an active OPEN ticket."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tickets 
            WHERE user_id = ? AND guild_id = ? AND status = 'OPEN'
            ORDER BY ticket_id DESC LIMIT 1;
        """, (user_id, guild_id))
        row = cursor.fetchone()
        return dict(row) if row else None

async def get_active_ticket(user_id: int, guild_id: int) -> Optional[Dict[str, Any]]:
    """Asynchronously check for an active ticket."""
    return await asyncio.to_thread(_get_active_ticket_sync, user_id, guild_id)

def _get_ticket_by_channel_sync(channel_id: int) -> Optional[Dict[str, Any]]:
    """Synchronously fetch ticket details by channel_id."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tickets WHERE channel_id = ?;
        """, (channel_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

async def get_ticket_by_channel(channel_id: int) -> Optional[Dict[str, Any]]:
    """Asynchronously fetch ticket by channel ID."""
    return await asyncio.to_thread(_get_ticket_by_channel_sync, channel_id)

def _update_ticket_tournament_sync(channel_id: int, tournament_name: str) -> bool:
    """Synchronously update the selected tournament for a ticket."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets 
            SET tournament_name = ? 
            WHERE channel_id = ? AND status = 'OPEN';
        """, (tournament_name, channel_id))
        conn.commit()
        return cursor.rowcount > 0

async def update_ticket_tournament(channel_id: int, tournament_name: str) -> bool:
    """Asynchronously update selected tournament name."""
    return await asyncio.to_thread(_update_ticket_tournament_sync, channel_id, tournament_name)

def _update_ticket_team_info_sync(
    channel_id: int, 
    team_name: str, 
    captain_name: str, 
    captain_discord_id: str, 
    captain_phone: str
) -> bool:
    """Synchronously update team information for a ticket."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets 
            SET team_name = ?, captain_name = ?, captain_discord_id = ?, captain_phone = ? 
            WHERE channel_id = ? AND status = 'OPEN';
        """, (team_name, captain_name, captain_discord_id, captain_phone, channel_id))
        conn.commit()
        return cursor.rowcount > 0

async def update_ticket_team_info(
    channel_id: int, 
    team_name: str, 
    captain_name: str, 
    captain_discord_id: str, 
    captain_phone: str
) -> bool:
    """Asynchronously update team information for a ticket."""
    return await asyncio.to_thread(
        _update_ticket_team_info_sync, 
        channel_id, 
        team_name, 
        captain_name, 
        captain_discord_id, 
        captain_phone
    )

def _close_ticket_sync(channel_id: int) -> bool:
    """Synchronously mark ticket as CLOSED."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets 
            SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP 
            WHERE channel_id = ? AND status = 'OPEN';
        """, (channel_id,))
        conn.commit()
        return cursor.rowcount > 0

async def close_ticket(channel_id: int) -> bool:
    """Asynchronously mark a ticket as closed."""
    return await asyncio.to_thread(_close_ticket_sync, channel_id)

def _save_roster_players_sync(ticket_id: int, players: list) -> bool:
    """Synchronously save or update roster player records for a ticket."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        for p in players:
            # Check if role exists for ticket
            cursor.execute("""
                SELECT roster_id FROM roster_players 
                WHERE ticket_id = ? AND player_role = ?;
            """, (ticket_id, p["player_role"]))
            row = cursor.fetchone()
            if row:
                cursor.execute("""
                    UPDATE roster_players 
                    SET ign = ?, discord_id = ? 
                    WHERE ticket_id = ? AND player_role = ?;
                """, (p["ign"], p["discord_id"], ticket_id, p["player_role"]))
            else:
                cursor.execute("""
                    INSERT INTO roster_players (ticket_id, player_role, ign, discord_id) 
                    VALUES (?, ?, ?, ?);
                """, (ticket_id, p["player_role"], p["ign"], p["discord_id"]))
        conn.commit()
        return True

async def save_roster_players(ticket_id: int, players: list) -> bool:
    """Asynchronously save/update roster players for a ticket."""
    return await asyncio.to_thread(_save_roster_players_sync, ticket_id, players)

def _get_roster_players_sync(ticket_id: int) -> list:
    """Synchronously fetch all roster players for a ticket."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM roster_players 
            WHERE ticket_id = ? 
            ORDER BY roster_id ASC;
        """, (ticket_id,))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

async def get_roster_players(ticket_id: int) -> list:
    """Asynchronously fetch all roster players for a ticket."""
    return await asyncio.to_thread(_get_roster_players_sync, ticket_id)

def _submit_ticket_registration_sync(channel_id: int, registration_code: str) -> bool:
    """Synchronously mark ticket registration as PENDING and record registration_code and submitted_at."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets 
            SET status = 'PENDING', registration_code = ?, submitted_at = CURRENT_TIMESTAMP 
            WHERE channel_id = ? AND status = 'OPEN';
        """, (registration_code, channel_id))
        conn.commit()
        return cursor.rowcount > 0

async def submit_ticket_registration(channel_id: int, registration_code: str) -> bool:
    """Asynchronously submit ticket registration."""
    return await asyncio.to_thread(_submit_ticket_registration_sync, channel_id, registration_code)

def _update_ticket_logo_sync(channel_id: int, logo_url: str) -> bool:
    """Synchronously update team_logo_url for a ticket."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets 
            SET team_logo_url = ? 
            WHERE channel_id = ? AND status = 'OPEN';
        """, (logo_url, channel_id))
        conn.commit()
        return cursor.rowcount > 0

async def update_ticket_logo(channel_id: int, logo_url: str) -> bool:
    """Asynchronously update team_logo_url for a ticket."""
    return await asyncio.to_thread(_update_ticket_logo_sync, channel_id, logo_url)

def _set_bot_setting_sync(key: str, value: str) -> bool:
    """Synchronously set or update a bot setting key-value pair."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO bot_settings (key, value, updated_at) 
            VALUES (?, ?, CURRENT_TIMESTAMP) 
            ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP;
        """, (key, value))
        conn.commit()
        return True

async def set_bot_setting(key: str, value: str) -> bool:
    """Asynchronously set a bot setting."""
    return await asyncio.to_thread(_set_bot_setting_sync, key, str(value))

def _get_bot_setting_sync(key: str) -> str | None:
    """Synchronously fetch a bot setting value."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM bot_settings WHERE key = ?;", (key,))
        row = cursor.fetchone()
        return row["value"] if row else None

async def get_bot_setting(key: str) -> str | None:
    """Asynchronously fetch a bot setting value."""
    return await asyncio.to_thread(_get_bot_setting_sync, key)

def _get_ticket_by_id_sync(ticket_id: int) -> dict | None:
    """Synchronously fetch ticket by ticket_id."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?;", (ticket_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

async def get_ticket_by_id(ticket_id: int) -> dict | None:
    """Asynchronously fetch ticket by ticket_id."""
    return await asyncio.to_thread(_get_ticket_by_id_sync, ticket_id)

def _update_ticket_review_message_sync(ticket_id: int, review_channel_id: int, review_message_id: int) -> bool:
    """Synchronously update review_channel_id and review_message_id for a ticket."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets 
            SET review_channel_id = ?, review_message_id = ? 
            WHERE ticket_id = ?;
        """, (review_channel_id, review_message_id, ticket_id))
        conn.commit()
        return cursor.rowcount > 0

async def update_ticket_review_message(ticket_id: int, review_channel_id: int, review_message_id: int) -> bool:
    """Asynchronously update review message references for a ticket."""
    return await asyncio.to_thread(_update_ticket_review_message_sync, ticket_id, review_channel_id, review_message_id)

def _approve_ticket_registration_sync(ticket_id: int, admin_id: str) -> bool:
    """Synchronously approve a ticket registration, log action, and update full status if max capacity reached."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?;", (ticket_id,))
        t_row = cursor.fetchone()
        if not t_row:
            return False

        ticket = dict(t_row)
        cursor.execute("""
            UPDATE tickets 
            SET status = 'APPROVED', approved_at = CURRENT_TIMESTAMP, approved_by = ? 
            WHERE ticket_id = ? AND status = 'PENDING';
        """, (str(admin_id), ticket_id))

        if cursor.rowcount > 0:
            # Audit Log
            cursor.execute("""
                INSERT INTO audit_logs (admin_id, action, details)
                VALUES (?, 'APPROVE_REGISTRATION', ?);
            """, (str(admin_id), f"Approved team '{ticket.get('team_name')}' for '{ticket.get('tournament_name')}' (Ticket #{ticket_id})"))

            # Check capacity for tournament
            tourn_name = ticket.get("tournament_name")
            if tourn_name:
                cursor.execute("""
                    SELECT tournament_id, max_teams FROM tournaments 
                    WHERE LOWER(title) = LOWER(?) OR LOWER(slug) = LOWER(?);
                """, (tourn_name, tourn_name))
                tr_row = cursor.fetchone()
                if tr_row:
                    t_id = tr_row["tournament_id"]
                    max_t = tr_row["max_teams"] or 16
                    cursor.execute("""
                        SELECT COUNT(*) FROM tickets 
                        WHERE status = 'APPROVED' 
                        AND LOWER(tournament_name) = LOWER(?);
                    """, (tourn_name,))
                    app_count = cursor.fetchone()[0]
                    if app_count >= max_t:
                        cursor.execute("UPDATE tournaments SET registration_status = 'FULL' WHERE tournament_id = ?;", (t_id,))

            conn.commit()
            return True
        return False

async def approve_ticket_registration(ticket_id: int, admin_id: str) -> bool:
    """Asynchronously approve a ticket registration."""
    return await asyncio.to_thread(_approve_ticket_registration_sync, ticket_id, admin_id)

def _reject_ticket_registration_sync(ticket_id: int, admin_id: str, reason: str) -> bool:
    """Synchronously reject a ticket registration with a reason and log action."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets 
            SET status = 'REJECTED', rejected_at = CURRENT_TIMESTAMP, rejected_by = ?, rejection_reason = ? 
            WHERE ticket_id = ? AND status = 'PENDING';
        """, (str(admin_id), reason, ticket_id))
        if cursor.rowcount > 0:
            cursor.execute("""
                INSERT INTO audit_logs (admin_id, action, details)
                VALUES (?, 'REJECT_REGISTRATION', ?);
            """, (str(admin_id), f"Rejected ticket #{ticket_id}. Reason: {reason}"))
            conn.commit()
            return True
        return False

async def reject_ticket_registration(ticket_id: int, admin_id: str, reason: str) -> bool:
    """Asynchronously reject a ticket registration with a reason."""
    return await asyncio.to_thread(_reject_ticket_registration_sync, ticket_id, admin_id, reason)

def _get_ticket_by_review_message_sync(message_id: int) -> dict | None:
    """Synchronously fetch ticket by review_message_id."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE review_message_id = ?;", (message_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

async def get_ticket_by_review_message(message_id: int) -> dict | None:
    """Asynchronously fetch ticket by review_message_id."""
    return await asyncio.to_thread(_get_ticket_by_review_message_sync, message_id)

def _get_approved_teams_by_tournament_sync(tournament: str) -> list[dict]:
    """Synchronously fetch all APPROVED registrations for a given tournament."""
    clean_search = tournament.replace('-', ' ').lower()
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tickets 
            WHERE status = 'APPROVED' 
            AND (
                LOWER(tournament_name) = LOWER(?)
                OR LOWER(REPLACE(tournament_name, ' ', '-')) = LOWER(?)
                OR LOWER(tournament_name) LIKE LOWER(?)
                OR LOWER(?) LIKE '%' || LOWER(REPLACE(tournament_name, ' ', '-')) || '%'
            );
        """, (tournament, tournament, f"%{clean_search}%", tournament))
        rows = cursor.fetchall()
        
        approved_teams = []
        for row in rows:
            ticket = dict(row)
            ticket_id = ticket["ticket_id"]
            
            # Fetch roster players
            cursor.execute("""
                SELECT player_role, ign, discord_id 
                FROM roster_players 
                WHERE ticket_id = ? 
                ORDER BY roster_id ASC;
            """, (ticket_id,))
            roster_rows = cursor.fetchall()
            roster = [{"role": r["player_role"], "ign": r["ign"], "discord_id": r["discord_id"]} for r in roster_rows]
            
            # Return sanitized record (NO phone number, NO internal DB IDs, NO admin info)
            approved_teams.append({
                "registration_id": ticket["registration_code"] or f"GEN-{ticket_id:06d}",
                "tournament": ticket["tournament_name"],
                "team_name": ticket["team_name"],
                "team_logo_url": ticket["team_logo_url"],
                "captain_name": ticket["captain_name"],
                "roster": roster,
                "approved_at": ticket["approved_at"]
            })
            
        return approved_teams

async def get_approved_teams_by_tournament(tournament: str) -> list[dict]:
    """Asynchronously fetch all APPROVED registrations for a given tournament."""
    return await asyncio.to_thread(_get_approved_teams_by_tournament_sync, tournament)

def _get_registration_by_code_sync(registration_code: str) -> dict | None:
    """Synchronously fetch a single registration by registration code."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tickets 
            WHERE registration_code = ? OR registration_code = UPPER(?);
        """, (registration_code, registration_code))
        row = cursor.fetchone()
        
        if not row:
            # Fallback: check integer ticket_id if format is GEN-XXXXXX
            if registration_code.startswith("GEN-") and registration_code[4:].isdigit():
                ticket_id = int(registration_code[4:])
                cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?;", (ticket_id,))
                row = cursor.fetchone()
        
        if not row:
            return None
            
        ticket = dict(row)
        ticket_id = ticket["ticket_id"]
        
        cursor.execute("""
            SELECT player_role, ign, discord_id 
            FROM roster_players 
            WHERE ticket_id = ? 
            ORDER BY roster_id ASC;
        """, (ticket_id,))
        roster_rows = cursor.fetchall()
        roster = [{"role": r["player_role"], "ign": r["ign"], "discord_id": r["discord_id"]} for r in roster_rows]
        
        # Return sanitized registration record (NO phone number, NO internal IDs)
        return {
            "registration_id": ticket["registration_code"] or f"GEN-{ticket_id:06d}",
            "tournament": ticket["tournament_name"],
            "team_name": ticket["team_name"],
            "team_logo_url": ticket["team_logo_url"],
            "captain_name": ticket["captain_name"],
            "status": ticket["status"],
            "roster": roster,
            "submitted_at": ticket["submitted_at"],
            "approved_at": ticket["approved_at"]
        }

async def get_registration_by_code(registration_code: str) -> dict | None:
    """Asynchronously fetch a single registration by registration code."""
    return await asyncio.to_thread(_get_registration_by_code_sync, registration_code)

def _get_all_tournaments_sync() -> list[str]:
    """Synchronously fetch all active tournament titles dynamically from DB."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT title FROM tournaments WHERE status != 'CANCELLED' ORDER BY tournament_id ASC;")
        rows = cursor.fetchall()
        db_tournaments = [row["title"] for row in rows]

        cursor.execute("SELECT DISTINCT tournament_name FROM tickets WHERE tournament_name IS NOT NULL;")
        t_rows = cursor.fetchall()
        ticket_tournaments = [row["tournament_name"] for row in t_rows if row["tournament_name"] and "League" not in row["tournament_name"]]

        all_tournaments = list(dict.fromkeys(db_tournaments + ticket_tournaments))
        return all_tournaments if all_tournaments else ["GEN Valorant Championship", "GEN PUBG Mobile Championship"]

async def get_all_tournaments() -> list[str]:
    """Asynchronously fetch all active tournament titles."""
    return await asyncio.to_thread(_get_all_tournaments_sync)

def _log_admin_action_sync(admin_id: str, action: str, tournament_id: int | None = None, details: str | None = None) -> bool:
    """Synchronously record an admin audit log entry."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_logs (admin_id, action, tournament_id, details)
            VALUES (?, ?, ?, ?);
        """, (str(admin_id), str(action), tournament_id, details))
        conn.commit()
        return True

async def log_admin_action(admin_id: str, action: str, tournament_id: int | None = None, details: str | None = None) -> bool:
    """Asynchronously record an admin audit log entry."""
    return await asyncio.to_thread(_log_admin_action_sync, admin_id, action, tournament_id, details)

def _get_admin_audit_logs_sync(limit: int = 50) -> list[dict]:
    """Synchronously fetch audit log history."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.log_id, a.admin_id, a.action, a.tournament_id, a.details, a.timestamp,
                   t.title as tournament_name
            FROM audit_logs a
            LEFT JOIN tournaments t ON a.tournament_id = t.tournament_id
            ORDER BY a.log_id DESC LIMIT ?;
        """, (limit,))
        return [dict(row) for row in cursor.fetchall()]

async def get_admin_audit_logs(limit: int = 50) -> list[dict]:
    """Asynchronously fetch audit log history."""
    return await asyncio.to_thread(_get_admin_audit_logs_sync, limit)

def _set_tournament_registration_status_sync(tournament_id: int, reg_status: str, main_status: str | None = None) -> bool:
    """Synchronously update tournament registration status and optional main status."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        if main_status:
            cursor.execute("""
                UPDATE tournaments 
                SET registration_status = ?, status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE tournament_id = ?;
            """, (reg_status, main_status, tournament_id))
        else:
            cursor.execute("""
                UPDATE tournaments 
                SET registration_status = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE tournament_id = ?;
            """, (reg_status, tournament_id))
        conn.commit()
        return cursor.rowcount > 0

async def set_tournament_registration_status(tournament_id: int, reg_status: str, main_status: str | None = None) -> bool:
    """Asynchronously update tournament registration status."""
    return await asyncio.to_thread(_set_tournament_registration_status_sync, tournament_id, reg_status, main_status)

def _get_open_tournaments_sync(include_full: bool = False) -> list[dict]:
    """Fetch all open tournaments where registration_status is OPEN and team capacity is not reached."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tournaments 
            WHERE (registration_status = 'OPEN' OR status = 'REGISTRATION_OPEN')
            AND status != 'CANCELLED'
            ORDER BY tournament_id ASC;
        """)
        rows = cursor.fetchall()
        open_tournaments = []
        for row in rows:
            t = dict(row)
            # Calculate current team count
            cursor.execute("""
                SELECT COUNT(*) FROM tickets 
                WHERE status = 'APPROVED' 
                AND (LOWER(tournament_name) = LOWER(?) OR LOWER(REPLACE(tournament_name, ' ', '-')) = LOWER(?));
            """, (t["title"], t["slug"]))
            t["current_approved_team_count"] = cursor.fetchone()[0]
            
            # Check capacity
            max_teams = t.get("max_teams") or 16
            if t["current_approved_team_count"] >= max_teams:
                t["registration_status"] = "FULL"
                t["is_full"] = True
            else:
                t["is_full"] = False

            if include_full or not t["is_full"]:
                open_tournaments.append(t)
        return open_tournaments

async def get_open_tournaments(include_full: bool = False) -> list[dict]:
    """Asynchronously fetch open tournaments for Discord dropdown & Website."""
    return await asyncio.to_thread(_get_open_tournaments_sync, include_full)

def _get_tournaments_detailed_sync() -> list[dict]:
    """Synchronously fetch detailed list of all tournaments with calculated team counts."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tournaments WHERE status != 'CANCELLED' ORDER BY tournament_id ASC;")
        rows = cursor.fetchall()
        results = []
        for row in rows:
            t = dict(row)
            cursor.execute("""
                SELECT COUNT(*) FROM tickets 
                WHERE status = 'APPROVED' 
                AND (LOWER(tournament_name) = LOWER(?) OR LOWER(REPLACE(tournament_name, ' ', '-')) = LOWER(?));
            """, (t["title"], t["slug"]))
            t["current_approved_team_count"] = cursor.fetchone()[0]
            results.append(t)
        return results

async def get_tournaments_detailed() -> list[dict]:
    """Asynchronously fetch detailed list of all tournaments."""
    return await asyncio.to_thread(_get_tournaments_detailed_sync)

def _get_tournament_by_slug_sync(slug: str) -> dict | None:
    """Synchronously fetch single tournament details by slug or title."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tournaments 
            WHERE LOWER(slug) = LOWER(?) OR LOWER(title) = LOWER(?) OR CAST(tournament_id AS TEXT) = ?;
        """, (slug, slug, slug))
        row = cursor.fetchone()
        if not row:
            return None
        t = dict(row)
        cursor.execute("""
            SELECT COUNT(*) FROM tickets 
            WHERE status = 'APPROVED' 
            AND (LOWER(tournament_name) = LOWER(?) OR LOWER(REPLACE(tournament_name, ' ', '-')) = LOWER(?));
        """, (t["title"], t["slug"]))
        t["current_approved_team_count"] = cursor.fetchone()[0]
        return t

async def get_tournament_by_slug(slug: str) -> dict | None:
    """Asynchronously fetch single tournament details by slug."""
    return await asyncio.to_thread(_get_tournament_by_slug_sync, slug)

def _create_tournament_sync(data: dict) -> dict:
    """Synchronously create a new tournament in the database."""
    title = data.get("title") or "GEN Tournament"
    slug = data.get("slug") or title.lower().replace(" ", "-").replace("'", "").replace('"', "")
    game_type = data.get("game_type") or data.get("game") or "VALORANT"
    status = data.get("status") or "REGISTRATION_OPEN"
    registration_status = data.get("registration_status") or "OPEN"
    max_teams = int(data.get("max_teams") or 16)
    start_date = data.get("start_date")
    registration_deadline = data.get("registration_deadline")
    prize_info = data.get("prize_info") or "$500 USD"
    description = data.get("description") or f"Official {title} Series"
    rules_text = data.get("rules_text") or f"Official {title} Rules and Regulations."
    format_type = data.get("format") or "Single Elimination"
    min_players = int(data.get("min_players") or 5)
    max_players = int(data.get("max_players") or 6)
    banner_url = data.get("banner_url")

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO tournaments (
                slug, title, game_type, status, registration_status, max_teams,
                start_date, registration_deadline, prize_info, description,
                rules_text, format, min_players, max_players, banner_url
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (
            slug, title, game_type, status, registration_status, max_teams,
            start_date, registration_deadline, prize_info, description,
            rules_text, format_type, min_players, max_players, banner_url
        ))
        conn.commit()
        tournament_id = cursor.lastrowid
        cursor.execute("SELECT * FROM tournaments WHERE tournament_id = ?;", (tournament_id,))
        return dict(cursor.fetchone())

async def create_tournament(data: dict) -> dict:
    """Asynchronously create a new tournament."""
    return await asyncio.to_thread(_create_tournament_sync, data)

def _update_tournament_sync(tournament_id: int, data: dict) -> dict | None:
    """Synchronously update an existing tournament."""
    allowed_fields = [
        "title", "slug", "game_type", "status", "registration_status", "max_teams",
        "start_date", "registration_deadline", "prize_info", "description",
        "rules_text", "format", "min_players", "max_players", "banner_url", "logo_url"
    ]
    updates = []
    values = []

    for field in allowed_fields:
        if field in data and data[field] is not None:
            updates.append(f"{field} = ?")
            values.append(data[field])

    if not updates:
        return _get_tournament_by_slug_sync(str(tournament_id))

    values.append(tournament_id)

    with _get_connection() as conn:
        cursor = conn.cursor()
        query = f"UPDATE tournaments SET {', '.join(updates)} WHERE tournament_id = ?;"
        cursor.execute(query, values)
        conn.commit()
        return _get_tournament_by_slug_sync(str(tournament_id))

async def update_tournament(tournament_id: int, data: dict) -> dict | None:
    """Asynchronously update a tournament."""
    return await asyncio.to_thread(_update_tournament_sync, tournament_id, data)

def _delete_tournament_sync(tournament_id: int) -> bool:
    """Synchronously mark tournament as CANCELLED."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE tournaments SET status = 'CANCELLED', registration_status = 'CLOSED' WHERE tournament_id = ?;", (tournament_id,))
        conn.commit()
        return cursor.rowcount > 0

async def delete_tournament(tournament_id: int) -> bool:
    """Asynchronously delete/cancel a tournament."""
    return await asyncio.to_thread(_delete_tournament_sync, tournament_id)

def _get_tournament_roster_rules_sync(tournament_identifier: str) -> dict:
    """Get roster rules (min_players, max_players) for a tournament."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT min_players, max_players, game_type FROM tournaments 
            WHERE LOWER(title) = LOWER(?) OR LOWER(slug) = LOWER(?) OR CAST(tournament_id AS TEXT) = ?;
        """, (tournament_identifier, tournament_identifier, tournament_identifier))
        row = cursor.fetchone()
        if row:
            return {
                "min_players": row["min_players"] or 5,
                "max_players": row["max_players"] or 6,
                "game_type": row["game_type"]
            }
        # Fallback defaults
        is_pubg = "pubg" in tournament_identifier.lower()
        return {
            "min_players": 4 if is_pubg else 5,
            "max_players": 5 if is_pubg else 6,
            "game_type": "PUBG MOBILE" if is_pubg else "VALORANT"
        }

async def get_tournament_roster_rules(tournament_identifier: str) -> dict:
    """Asynchronously get roster rules for a tournament."""
    return await asyncio.to_thread(_get_tournament_roster_rules_sync, tournament_identifier)

def _generate_tournament_bracket_sync(tournament_id_or_slug: str) -> list[dict]:
    """Generate a single-elimination tournament bracket from approved teams."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tournaments 
            WHERE CAST(tournament_id AS TEXT) = ? OR LOWER(slug) = LOWER(?) OR LOWER(title) = LOWER(?);
        """, (tournament_id_or_slug, tournament_id_or_slug, tournament_id_or_slug))
        t_row = cursor.fetchone()
        if not t_row:
            raise ValueError(f"Tournament '{tournament_id_or_slug}' not found.")
        
        tournament = dict(t_row)
        tournament_id = tournament["tournament_id"]

        # Fetch approved teams for this tournament
        approved_teams = _get_approved_teams_by_tournament_sync(tournament["title"])
        if not approved_teams:
            approved_teams = _get_approved_teams_by_tournament_sync(tournament["slug"])

        if len(approved_teams) < 2:
            raise ValueError(f"At least 2 approved teams are required to generate bracket. Current approved: {len(approved_teams)}")

        # Sync teams to teams table if not existing
        team_id_map = {}
        for t in approved_teams:
            name = t["team_name"]
            logo = t["team_logo_url"]
            captain = t["captain_name"]
            cursor.execute("SELECT team_id FROM teams WHERE LOWER(name) = LOWER(?);", (name,))
            existing = cursor.fetchone()
            if existing:
                team_id_map[name] = existing["team_id"]
            else:
                cursor.execute("""
                    INSERT INTO teams (name, logo_url, captain_discord_id) 
                    VALUES (?, ?, ?);
                """, (name, logo, captain))
                team_id_map[name] = cursor.lastrowid

        # Delete existing matches/brackets for fresh generation
        cursor.execute("DELETE FROM matches WHERE tournament_id = ?;", (tournament_id,))
        cursor.execute("DELETE FROM brackets WHERE tournament_id = ?;", (tournament_id,))

        team_ids = [team_id_map[t["team_name"]] for t in approved_teams]
        num_teams = len(team_ids)

        # Generate Round 1 matches
        created_matches = []
        round_1_match_ids = []

        for i in range(0, num_teams, 2):
            team1_id = team_ids[i]
            team2_id = team_ids[i + 1] if i + 1 < num_teams else None
            status = "COMPLETED" if team2_id is None else "SCHEDULED"
            winner_id = team1_id if team2_id is None else None

            cursor.execute("""
                INSERT INTO matches (tournament_id, stage_name, round_number, team1_id, team2_id, status, winner_id)
                VALUES (?, ?, 1, ?, ?, ?, ?);
            """, (tournament_id, "Quarterfinals" if num_teams <= 4 else "Round 1", team1_id, team2_id, status, winner_id))
            match_id = cursor.lastrowid
            round_1_match_ids.append(match_id)

            cursor.execute("""
                INSERT INTO brackets (tournament_id, round_number, match_id, position_index)
                VALUES (?, 1, ?, ?);
            """, (tournament_id, match_id, i // 2))

        # Generate Round 2 (Semifinals / Finals placeholder)
        if len(round_1_match_ids) > 1:
            for j in range(0, len(round_1_match_ids), 2):
                cursor.execute("""
                    INSERT INTO matches (tournament_id, stage_name, round_number, status)
                    VALUES (?, ?, 2, 'SCHEDULED');
                """, (tournament_id, "Semifinals" if len(round_1_match_ids) > 2 else "Finals"))
                match_id = cursor.lastrowid
                cursor.execute("""
                    INSERT INTO brackets (tournament_id, round_number, match_id, position_index)
                    VALUES (?, 2, ?, ?);
                """, (tournament_id, match_id, j // 2))

        # Update tournament status to ONGOING
        cursor.execute("UPDATE tournaments SET status = 'ONGOING' WHERE tournament_id = ?;", (tournament_id,))
        conn.commit()

        return _get_tournament_matches_sync(str(tournament_id))

async def generate_tournament_bracket(tournament_id_or_slug: str) -> list[dict]:
    """Asynchronously generate bracket for a tournament."""
    return await asyncio.to_thread(_generate_tournament_bracket_sync, tournament_id_or_slug)

def _get_tournament_matches_sync(tournament_id_or_slug: str) -> list[dict]:
    """Synchronously fetch all matches for a tournament."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.match_id, m.tournament_id, m.stage_name, m.round_number, m.team1_id, m.team2_id,
                   m.team1_score, m.team2_score, m.winner_id, m.status, m.scheduled_time, m.lobby_info,
                   t1.name as team1_name, t1.logo_url as team1_logo,
                   t2.name as team2_name, t2.logo_url as team2_logo,
                   tw.name as winner_name,
                   tr.title as tournament_name
            FROM matches m
            LEFT JOIN teams t1 ON m.team1_id = t1.team_id
            LEFT JOIN teams t2 ON m.team2_id = t2.team_id
            LEFT JOIN teams tw ON m.winner_id = tw.team_id
            LEFT JOIN tournaments tr ON m.tournament_id = tr.tournament_id
            WHERE CAST(m.tournament_id AS TEXT) = ? OR LOWER(tr.slug) = LOWER(?) OR LOWER(tr.title) = LOWER(?)
            ORDER BY m.round_number ASC, m.match_id ASC;
        """, (tournament_id_or_slug, tournament_id_or_slug, tournament_id_or_slug))
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

async def get_tournament_matches(tournament_id_or_slug: str) -> list[dict]:
    """Asynchronously fetch matches for a tournament."""
    return await asyncio.to_thread(_get_tournament_matches_sync, tournament_id_or_slug)

def _update_match_result_sync(match_id: int, team1_score: int, team2_score: int, winner_id: int | None = None, status: str = "COMPLETED") -> dict | None:
    """Synchronously record match result and auto-advance winner to next round match."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE match_id = ?;", (match_id,))
        m_row = cursor.fetchone()
        if not m_row:
            return None

        match = dict(m_row)
        # Determine winner if not explicitly passed
        if winner_id is None:
            if team1_score > team2_score:
                winner_id = match["team1_id"]
            elif team2_score > team1_score:
                winner_id = match["team2_id"]

        cursor.execute("""
            UPDATE matches 
            SET team1_score = ?, team2_score = ?, winner_id = ?, status = ?
            WHERE match_id = ?;
        """, (team1_score, team2_score, winner_id, status, match_id))

        # Check bracket progression
        cursor.execute("SELECT * FROM brackets WHERE match_id = ?;", (match_id,))
        b_row = cursor.fetchone()
        if b_row and winner_id:
            bracket = dict(b_row)
            current_round = bracket["round_number"]
            pos_index = bracket["position_index"]

            # Next round match position
            next_round = current_round + 1
            next_pos = pos_index // 2

            cursor.execute("""
                SELECT match_id FROM brackets 
                WHERE tournament_id = ? AND round_number = ? AND position_index = ?;
            """, (match["tournament_id"], next_round, next_pos))
            next_b_row = cursor.fetchone()

            if next_b_row:
                next_match_id = next_b_row["match_id"]
                cursor.execute("SELECT team1_id, team2_id FROM matches WHERE match_id = ?;", (next_match_id,))
                next_m_row = cursor.fetchone()
                if next_m_row:
                    if pos_index % 2 == 0:
                        cursor.execute("UPDATE matches SET team1_id = ? WHERE match_id = ?;", (winner_id, next_match_id))
                    else:
                        cursor.execute("UPDATE matches SET team2_id = ? WHERE match_id = ?;", (winner_id, next_match_id))

        conn.commit()
        cursor.execute("SELECT * FROM matches WHERE match_id = ?;", (match_id,))
        return dict(cursor.fetchone())

async def update_match_result(match_id: int, team1_score: int, team2_score: int, winner_id: int | None = None, status: str = "COMPLETED") -> dict | None:
    """Asynchronously record match result."""
    return await asyncio.to_thread(_update_match_result_sync, match_id, team1_score, team2_score, winner_id, status)

def _get_tournament_standings_sync(tournament_id_or_slug: str) -> list[dict]:
    """Calculate tournament leaderboard standings based on match results."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        matches = _get_tournament_matches_sync(tournament_id_or_slug)
        standings_map = {}

        for m in matches:
            if m["status"] == "COMPLETED" and m["team1_name"] and m["team2_name"]:
                t1 = m["team1_name"]
                t2 = m["team2_name"]
                s1 = m["team1_score"] or 0
                s2 = m["team2_score"] or 0

                for t_name in [t1, t2]:
                    if t_name not in standings_map:
                        standings_map[t_name] = {"team_name": t_name, "played": 0, "wins": 0, "losses": 0, "points": 0}

                standings_map[t1]["played"] += 1
                standings_map[t2]["played"] += 1

                if s1 > s2:
                    standings_map[t1]["wins"] += 1
                    standings_map[t1]["points"] += 3
                    standings_map[t2]["losses"] += 1
                elif s2 > s1:
                    standings_map[t2]["wins"] += 1
                    standings_map[t2]["points"] += 3
                    standings_map[t1]["losses"] += 1
                else:
                    standings_map[t1]["points"] += 1
                    standings_map[t2]["points"] += 1

        standings_list = list(standings_map.values())
        standings_list.sort(key=lambda x: (x["points"], x["wins"]), reverse=True)
        return standings_list

async def get_tournament_standings(tournament_id_or_slug: str) -> list[dict]:
    """Asynchronously calculate tournament standings."""
    return await asyncio.to_thread(_get_tournament_standings_sync, tournament_id_or_slug)

def _get_all_registrations_sync(status_filter: str | None = None) -> list[dict]:
    """Fetch all ticket registrations for Admin review."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM tickets"
        params = []
        if status_filter:
            query += " WHERE status = ?"
            params.append(status_filter)
        query += " ORDER BY ticket_id DESC;"

        cursor.execute(query, params)
        rows = cursor.fetchall()
        registrations = []
        for r in rows:
            ticket = dict(r)
            ticket_id = ticket["ticket_id"]
            cursor.execute("SELECT player_role, ign, discord_id FROM roster_players WHERE ticket_id = ? ORDER BY roster_id ASC;", (ticket_id,))
            ticket["roster"] = [dict(ro) for ro in cursor.fetchall()]
            registrations.append(ticket)
        return registrations

async def get_all_registrations(status_filter: str | None = None) -> list[dict]:
    """Asynchronously fetch registrations for Admin view."""
    return await asyncio.to_thread(_get_all_registrations_sync, status_filter)

def _get_platform_stats_sync() -> dict:
    """Synchronously calculate high-level platform statistics for Website & Admin Dashboard."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tickets;")
        total_tickets = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'APPROVED';")
        approved_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'PENDING';")
        pending_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'REJECTED';")
        rejected_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tournaments WHERE status != 'CANCELLED';")
        tournaments_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM matches WHERE status = 'COMPLETED';")
        completed_matches_count = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM roster_players;")
        registered_players_count = cursor.fetchone()[0]

        return {
            "total_registrations": total_tickets,
            "approved_registrations": approved_count,
            "pending_registrations": pending_count,
            "rejected_registrations": rejected_count,
            "total_tournaments": tournaments_count,
            "completed_matches": completed_matches_count,
            "registered_players": registered_players_count
        }

async def get_platform_stats() -> dict:
    """Asynchronously calculate platform statistics."""
    return await asyncio.to_thread(_get_platform_stats_sync)

def _get_public_matches_sync() -> list[dict]:
    """Synchronously fetch public match records."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.match_id, m.stage_name, m.round_number, m.team1_score, m.team2_score, m.status, m.scheduled_time,
                   t1.name as team1_name, t1.logo_url as team1_logo,
                   t2.name as team2_name, t2.logo_url as team2_logo,
                   tr.title as tournament_name
            FROM matches m
            LEFT JOIN teams t1 ON m.team1_id = t1.team_id
            LEFT JOIN teams t2 ON m.team2_id = t2.team_id
            LEFT JOIN tournaments tr ON m.tournament_id = tr.tournament_id
            ORDER BY m.match_id DESC;
        """)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

async def get_public_matches() -> list[dict]:
    """Asynchronously fetch public match records."""
    return await asyncio.to_thread(_get_public_matches_sync)
