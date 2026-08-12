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

        # Seed initial tournaments if empty or purge legacy seeds
        cursor.execute("DELETE FROM tournaments WHERE slug = 'gen-lol-cup' OR LOWER(game_type) LIKE '%league%' OR LOWER(title) LIKE '%league%';")
        cursor.execute("UPDATE tickets SET tournament_name = 'GEN PUBG Mobile Championship' WHERE tournament_name LIKE '%League%';")

        cursor.execute("SELECT COUNT(*) FROM tournaments;")
        if cursor.fetchone()[0] == 0:
            cursor.execute("""
                INSERT INTO tournaments (slug, title, game_type, status, max_teams, rules_text) VALUES
                ('gen-valorant-championship', 'GEN Valorant Championship', 'VALORANT', 'REGISTRATION_OPEN', 16, 'GEN Esports 5v5 VALORANT Tournament Series Rules.'),
                ('gen-pubg-mobile-championship', 'GEN PUBG Mobile Championship', 'PUBG MOBILE', 'REGISTRATION_OPEN', 16, 'GEN Esports PUBG Mobile Championship Rules.');
            """)
        else:
            # Ensure PUBG Mobile tournament exists
            cursor.execute("SELECT COUNT(*) FROM tournaments WHERE slug = 'gen-pubg-mobile-championship';")
            if cursor.fetchone()[0] == 0:
                cursor.execute("""
                    INSERT INTO tournaments (slug, title, game_type, status, max_teams, rules_text) VALUES
                    ('gen-pubg-mobile-championship', 'GEN PUBG Mobile Championship', 'PUBG MOBILE', 'REGISTRATION_OPEN', 16, 'GEN Esports PUBG Mobile Championship Rules.');
                """)

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
    """Synchronously approve a ticket registration."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets 
            SET status = 'APPROVED', approved_at = CURRENT_TIMESTAMP, approved_by = ? 
            WHERE ticket_id = ? AND status = 'PENDING';
        """, (str(admin_id), ticket_id))
        conn.commit()
        return cursor.rowcount > 0

async def approve_ticket_registration(ticket_id: int, admin_id: str) -> bool:
    """Asynchronously approve a ticket registration."""
    return await asyncio.to_thread(_approve_ticket_registration_sync, ticket_id, admin_id)

def _reject_ticket_registration_sync(ticket_id: int, admin_id: str, reason: str) -> bool:
    """Synchronously reject a ticket registration with a reason."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tickets 
            SET status = 'REJECTED', rejected_at = CURRENT_TIMESTAMP, rejected_by = ?, rejection_reason = ? 
            WHERE ticket_id = ? AND status = 'PENDING';
        """, (str(admin_id), reason, ticket_id))
        conn.commit()
        return cursor.rowcount > 0

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
    """Synchronously fetch all active tournament names."""
    default_tournaments = ["GEN Valorant Championship", "GEN PUBG Mobile Championship"]
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT tournament_name FROM tickets WHERE tournament_name IS NOT NULL;")
        rows = cursor.fetchall()
        db_tournaments = [row["tournament_name"] for row in rows if row["tournament_name"] and "League" not in row["tournament_name"]]
        
        # Combine default tournaments and DB tournaments uniquely
        all_tournaments = list(dict.fromkeys(default_tournaments + db_tournaments))
        return all_tournaments

async def get_all_tournaments() -> list[str]:
    """Asynchronously fetch all active tournament names."""
    return await asyncio.to_thread(_get_all_tournaments_sync)

def _get_tournaments_detailed_sync() -> list[dict]:
    """Synchronously fetch detailed list of all tournaments."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tournaments ORDER BY tournament_id ASC;")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

async def get_tournaments_detailed() -> list[dict]:
    """Asynchronously fetch detailed list of all tournaments."""
    return await asyncio.to_thread(_get_tournaments_detailed_sync)

def _get_tournament_by_slug_sync(slug: str) -> dict | None:
    """Synchronously fetch single tournament details by slug or title."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM tournaments 
            WHERE LOWER(slug) = LOWER(?) OR LOWER(title) = LOWER(?);
        """, (slug, slug))
        row = cursor.fetchone()
        return dict(row) if row else None

async def get_tournament_by_slug(slug: str) -> dict | None:
    """Asynchronously fetch single tournament details by slug."""
    return await asyncio.to_thread(_get_tournament_by_slug_sync, slug)

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

        cursor.execute("SELECT COUNT(*) FROM tournaments;")
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
            SELECT m.match_id, m.stage_name, m.team1_score, m.team2_score, m.status, m.scheduled_time,
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
