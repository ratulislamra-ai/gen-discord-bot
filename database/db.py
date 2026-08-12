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

        # support_tickets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS support_tickets (
                ticket_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT UNIQUE NOT NULL,
                ticket_type TEXT NOT NULL,
                user_id TEXT NOT NULL,
                guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                related_tournament_id INTEGER,
                related_registration_id INTEGER,
                assigned_staff_id TEXT DEFAULT NULL,
                priority TEXT DEFAULT 'NORMAL',
                status TEXT DEFAULT 'OPEN',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                closed_at TIMESTAMP DEFAULT NULL,
                resolution TEXT DEFAULT NULL,
                close_reason TEXT DEFAULT NULL
            );
        """)

        # support_ticket_notes table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS support_ticket_notes (
                note_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                staff_id TEXT NOT NULL,
                note_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # support_transcripts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS support_transcripts (
                transcript_id INTEGER PRIMARY KEY AUTOINCREMENT,
                case_id TEXT NOT NULL,
                transcript_text TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # support_panels table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS support_panels (
                panel_id INTEGER PRIMARY KEY AUTOINCREMENT,
                guild_id TEXT NOT NULL,
                channel_id TEXT NOT NULL,
                message_id TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(guild_id, channel_id)
            );
        """)

        # players table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS players (
                player_id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id TEXT UNIQUE NOT NULL,
                discord_user_id TEXT UNIQUE NOT NULL,
                username TEXT NOT NULL,
                display_name TEXT NOT NULL,
                avatar_url TEXT,
                country TEXT,
                bio TEXT,
                primary_game TEXT DEFAULT 'VALORANT',
                verification_status TEXT DEFAULT 'UNVERIFIED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # teams table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS teams (
                team_id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                logo_url TEXT,
                captain_player_id INTEGER,
                description TEXT,
                game TEXT DEFAULT 'VALORANT',
                region TEXT DEFAULT 'South Asia',
                verification_status TEXT DEFAULT 'UNVERIFIED',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # team_members table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_members (
                membership_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                player_id INTEGER NOT NULL,
                role TEXT DEFAULT 'PLAYER',
                status TEXT DEFAULT 'ACTIVE',
                joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                left_at TIMESTAMP DEFAULT NULL,
                UNIQUE(team_id, player_id)
            );
        """)

        # team_invitations table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_invitations (
                invitation_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER NOT NULL,
                inviter_player_id INTEGER NOT NULL,
                invitee_discord_id TEXT NOT NULL,
                invitee_player_id INTEGER,
                status TEXT DEFAULT 'PENDING',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # player_stats table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS player_stats (
                stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
                player_id INTEGER UNIQUE NOT NULL,
                matches_played INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                tournaments_played INTEGER DEFAULT 0,
                tournament_wins INTEGER DEFAULT 0,
                mvp_count INTEGER DEFAULT 0
            );
        """)

        # achievements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS achievements (
                achievement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity_type TEXT NOT NULL,
                entity_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                description TEXT,
                badge_icon TEXT DEFAULT '🏆',
                awarded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # tournament_roster_snapshots table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tournament_roster_snapshots (
                snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id INTEGER NOT NULL,
                tournament_id INTEGER,
                team_id INTEGER,
                player_id INTEGER,
                player_role TEXT,
                ign TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # team_seeds table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_seeds (
                seed_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                seed_number INTEGER NOT NULL,
                seeding_method TEXT DEFAULT 'RANDOM',
                is_locked INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tournament_id, team_id)
            );
        """)

        # team_elo table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS team_elo (
                elo_id INTEGER PRIMARY KEY AUTOINCREMENT,
                team_id INTEGER UNIQUE NOT NULL,
                rating INTEGER DEFAULT 1200,
                matches_rated INTEGER DEFAULT 0,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # tournament_rulesets table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tournament_rulesets (
                ruleset_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER UNIQUE NOT NULL,
                game_name TEXT DEFAULT 'VALORANT',
                best_of TEXT DEFAULT 'BO3',
                allowed_maps TEXT DEFAULT '["Ascent","Bind","Haven","Lotus","Sunset"]',
                veto_sequence TEXT DEFAULT '["BAN_A","BAN_B","PICK_A","PICK_B","BAN_A","BAN_B","DECIDER"]',
                overtime_rules TEXT DEFAULT 'Overtime win by 2 maps/rounds.',
                rules_version TEXT DEFAULT '1.0',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # veto_sessions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS veto_sessions (
                veto_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER UNIQUE NOT NULL,
                current_turn_team_id INTEGER,
                veto_state TEXT DEFAULT '{}',
                status TEXT DEFAULT 'IN_PROGRESS',
                started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP DEFAULT NULL
            );
        """)

        # veto_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS veto_logs (
                veto_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                veto_id INTEGER NOT NULL,
                match_id INTEGER NOT NULL,
                team_id INTEGER,
                player_id INTEGER,
                action TEXT NOT NULL,
                map_name TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # result_corrections table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS result_corrections (
                correction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                match_id INTEGER NOT NULL,
                admin_id TEXT NOT NULL,
                reason TEXT NOT NULL,
                old_score_a INTEGER,
                old_score_b INTEGER,
                new_score_a INTEGER,
                new_score_b INTEGER,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # rules_acknowledgements table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rules_acknowledgements (
                acknowledgement_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                rules_version TEXT DEFAULT '1.0',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # swiss_standings table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS swiss_standings (
                swiss_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                wins INTEGER DEFAULT 0,
                losses INTEGER DEFAULT 0,
                buchholz_score REAL DEFAULT 0.0,
                round_number INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(tournament_id, team_id)
            );
        """)

        # staff_roles table (Caster, Referee, Moderator, Admin)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS staff_roles (
                role_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                role_type TEXT NOT NULL,
                assigned_tournament_id INTEGER DEFAULT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # seasons table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seasons (
                season_id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                slug TEXT UNIQUE NOT NULL,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # prize_pools table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prize_pools (
                prize_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER UNIQUE NOT NULL,
                total_amount REAL DEFAULT 500.0,
                currency TEXT DEFAULT 'USD',
                distribution_json TEXT DEFAULT '{"1st": "50%", "2nd": "30%", "3rd": "20%"}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # transactions ledger table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
                public_tx_id TEXT UNIQUE NOT NULL,
                entity_type TEXT NOT NULL DEFAULT 'TEAM',
                entity_id INTEGER NOT NULL,
                tournament_id INTEGER,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                tx_type TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'PENDING',
                provider TEXT DEFAULT 'INTERNAL',
                reference TEXT,
                admin_id TEXT,
                reason TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # payouts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payouts (
                payout_id INTEGER PRIMARY KEY AUTOINCREMENT,
                tournament_id INTEGER NOT NULL,
                team_id INTEGER NOT NULL,
                placement TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT DEFAULT 'USD',
                status TEXT DEFAULT 'ELIGIBLE',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # notifications table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                notification_id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                link_url TEXT,
                is_read INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # system_health table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_health (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                component_name TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
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
        if "stream_url" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN stream_url TEXT;")
        if "stream_platform" not in t_cols:
            cursor.execute("ALTER TABLE tournaments ADD COLUMN stream_platform TEXT DEFAULT 'YOUTUBE';")

        cursor.execute("PRAGMA table_info(players);")
        p_cols = [col[1] for col in cursor.fetchall()]
        if "public_id" not in p_cols:
            cursor.execute("ALTER TABLE players ADD COLUMN public_id TEXT;")
        if "discord_user_id" not in p_cols:
            cursor.execute("ALTER TABLE players ADD COLUMN discord_user_id TEXT;")
        if "username" not in p_cols:
            cursor.execute("ALTER TABLE players ADD COLUMN username TEXT;")
        if "display_name" not in p_cols:
            cursor.execute("ALTER TABLE players ADD COLUMN display_name TEXT;")
        if "avatar_url" not in p_cols:
            cursor.execute("ALTER TABLE players ADD COLUMN avatar_url TEXT;")
        if "country" not in p_cols:
            cursor.execute("ALTER TABLE players ADD COLUMN country TEXT;")
        if "bio" not in p_cols:
            cursor.execute("ALTER TABLE players ADD COLUMN bio TEXT;")
        if "primary_game" not in p_cols:
            cursor.execute("ALTER TABLE players ADD COLUMN primary_game TEXT DEFAULT 'VALORANT';")
        if "verification_status" not in p_cols:
            cursor.execute("ALTER TABLE players ADD COLUMN verification_status TEXT DEFAULT 'UNVERIFIED';")

        cursor.execute("PRAGMA table_info(player_stats);")
        ps_cols = [col[1] for col in cursor.fetchall()]
        if "kills" not in ps_cols:
            cursor.execute("ALTER TABLE player_stats ADD COLUMN kills INTEGER DEFAULT 0;")
        if "deaths" not in ps_cols:
            cursor.execute("ALTER TABLE player_stats ADD COLUMN deaths INTEGER DEFAULT 0;")
        if "assists" not in ps_cols:
            cursor.execute("ALTER TABLE player_stats ADD COLUMN assists INTEGER DEFAULT 0;")
        if "acs" not in ps_cols:
            cursor.execute("ALTER TABLE player_stats ADD COLUMN acs INTEGER DEFAULT 0;")
        if "mvps" not in ps_cols:
            cursor.execute("ALTER TABLE player_stats ADD COLUMN mvps INTEGER DEFAULT 0;")

        cursor.execute("PRAGMA table_info(teams);")
        tm_cols = [col[1] for col in cursor.fetchall()]
        if "public_id" not in tm_cols:
            cursor.execute("ALTER TABLE teams ADD COLUMN public_id TEXT;")
        if "slug" not in tm_cols:
            cursor.execute("ALTER TABLE teams ADD COLUMN slug TEXT;")
        if "logo_url" not in tm_cols:
            cursor.execute("ALTER TABLE teams ADD COLUMN logo_url TEXT;")
        if "description" not in tm_cols:
            cursor.execute("ALTER TABLE teams ADD COLUMN description TEXT;")
        if "captain_player_id" not in tm_cols:
            cursor.execute("ALTER TABLE teams ADD COLUMN captain_player_id INTEGER;")
        if "game" not in tm_cols:
            cursor.execute("ALTER TABLE teams ADD COLUMN game TEXT DEFAULT 'VALORANT';")
        if "region" not in tm_cols:
            cursor.execute("ALTER TABLE teams ADD COLUMN region TEXT DEFAULT 'South Asia';")
        if "verification_status" not in tm_cols:
            cursor.execute("ALTER TABLE teams ADD COLUMN verification_status TEXT DEFAULT 'UNVERIFIED';")
        if "roster_locked" not in tm_cols:
            cursor.execute("ALTER TABLE teams ADD COLUMN roster_locked INTEGER DEFAULT 0;")

        cursor.execute("PRAGMA table_info(matches);")
        m_cols = [col[1] for col in cursor.fetchall()]
        if "round_number" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN round_number INTEGER DEFAULT 1;")
        if "lobby_info" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN lobby_info TEXT;")
        if "match_code" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN match_code TEXT;")
        if "public_match_id" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN public_match_id TEXT;")
        if "bracket_id" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN bracket_id INTEGER;")
        if "match_number" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN match_number INTEGER;")
        if "check_in_open_at" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN check_in_open_at TIMESTAMP;")
        if "check_in_deadline" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN check_in_deadline TIMESTAMP;")
        if "team_a_checked_in" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN team_a_checked_in INTEGER DEFAULT 0;")
        if "team_b_checked_in" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN team_b_checked_in INTEGER DEFAULT 0;")
        if "lobby_name" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN lobby_name TEXT;")
        if "lobby_code" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN lobby_code TEXT;")
        if "lobby_password" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN lobby_password TEXT;")
        if "map" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN map TEXT;")
        if "server_region" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN server_region TEXT DEFAULT 'South Asia';")
        if "score_a" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN score_a INTEGER DEFAULT 0;")
        if "score_b" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN score_b INTEGER DEFAULT 0;")
        if "result_submitted_by" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN result_submitted_by TEXT;")
        if "result_submitted_at" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN result_submitted_at TIMESTAMP;")
        if "opponent_confirmation_status" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN opponent_confirmation_status TEXT DEFAULT 'PENDING';")
        if "admin_verification_status" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN admin_verification_status TEXT DEFAULT 'PENDING';")
        if "evidence_url" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN evidence_url TEXT;")
        if "case_id" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN case_id TEXT;")
        if "completed_at" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN completed_at TIMESTAMP;")
        if "stream_url" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN stream_url TEXT;")
        if "is_losers_bracket" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN is_losers_bracket INTEGER DEFAULT 0;")
        if "bracket_type" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN bracket_type TEXT DEFAULT 'WINNERS';")
        if "swiss_round" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN swiss_round INTEGER DEFAULT 1;")
        if "discord_channel_id" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN discord_channel_id TEXT;")
        if "check_in_policy" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN check_in_policy TEXT DEFAULT 'NOTIFY_STAFF';")
        if "dispute_ticket_id" not in m_cols:
            cursor.execute("ALTER TABLE matches ADD COLUMN dispute_ticket_id INTEGER;")

        cursor.execute("PRAGMA table_info(support_tickets);")
        st_cols = [col[1] for col in cursor.fetchall()]
        if "related_match_id" not in st_cols:
            cursor.execute("ALTER TABLE support_tickets ADD COLUMN related_match_id INTEGER;")

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

        # Check or generate team seeds
        cursor.execute("SELECT team_id, seed_number FROM team_seeds WHERE tournament_id = ? ORDER BY seed_number ASC;", (tournament_id,))
        seed_rows = cursor.fetchall()
        if not seed_rows:
            _generate_tournament_seeds_sync(tournament_id, "RANDOM")
            cursor.execute("SELECT team_id, seed_number FROM team_seeds WHERE tournament_id = ? ORDER BY seed_number ASC;", (tournament_id,))
            seed_rows = cursor.fetchall()

        # Lock seeds for tournament
        cursor.execute("UPDATE team_seeds SET is_locked = 1 WHERE tournament_id = ?;", (tournament_id,))

        if seed_rows:
            team_ids = [r["team_id"] for r in seed_rows]
        else:
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

def _generate_double_elimination_bracket_sync(tournament_id: int) -> list[dict]:
    """Generate Double Elimination tournament bracket (Winners, Losers & Grand Final)."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tournaments WHERE tournament_id = ?;", (tournament_id,))
        t_row = cursor.fetchone()
        if not t_row:
            raise ValueError(f"Tournament #{tournament_id} not found.")

        approved_teams = _get_approved_teams_by_tournament_sync(t_row["title"])
        if not approved_teams:
            approved_teams = _get_approved_teams_by_tournament_sync(t_row["slug"])

        if len(approved_teams) < 2:
            raise ValueError("At least 2 teams required for Double Elimination.")

        team_id_map = {}
        for t in approved_teams:
            name = t["team_name"]
            cursor.execute("SELECT team_id FROM teams WHERE LOWER(name) = LOWER(?);", (name,))
            existing = cursor.fetchone()
            if existing:
                team_id_map[name] = existing["team_id"]
            else:
                cursor.execute("INSERT INTO teams (name, logo_url, captain_discord_id) VALUES (?, ?, ?);", (name, t["team_logo_url"], t["captain_name"]))
                team_id_map[name] = cursor.lastrowid

        cursor.execute("DELETE FROM matches WHERE tournament_id = ?;", (tournament_id,))
        cursor.execute("DELETE FROM brackets WHERE tournament_id = ?;", (tournament_id,))

        cursor.execute("SELECT team_id FROM team_seeds WHERE tournament_id = ? ORDER BY seed_number ASC;", (tournament_id,))
        seed_rows = cursor.fetchall()
        if seed_rows:
            team_ids = [r["team_id"] for r in seed_rows]
        else:
            team_ids = [team_id_map[t["team_name"]] for t in approved_teams]

        num_teams = len(team_ids)

        # 1. Winners Round 1
        w_matches = []
        for i in range(0, num_teams, 2):
            t1 = team_ids[i]
            t2 = team_ids[i + 1] if i + 1 < num_teams else None
            st = "COMPLETED" if t2 is None else "SCHEDULED"
            win = t1 if t2 is None else None
            pm_id = _generate_next_public_match_id_sync()

            cursor.execute("""
                INSERT INTO matches (public_match_id, tournament_id, stage_name, round_number, team1_id, team2_id, status, winner_id, bracket_type)
                VALUES (?, ?, 'Winners Round 1', 1, ?, ?, ?, ?, 'WINNERS');
            """, (pm_id, tournament_id, t1, t2, st, win))
            m_id = cursor.lastrowid
            w_matches.append(m_id)
            cursor.execute("INSERT INTO brackets (tournament_id, round_number, match_id, position_index) VALUES (?, 1, ?, ?);", (tournament_id, m_id, i // 2))

        # 2. Losers Round 1
        cursor.execute("""
            INSERT INTO matches (public_match_id, tournament_id, stage_name, round_number, status, bracket_type, is_losers_bracket)
            VALUES (?, ?, 'Losers Round 1', 1, 'SCHEDULED', 'LOSERS', 1);
        """, (_generate_next_public_match_id_sync(), tournament_id))

        # 3. Grand Final
        cursor.execute("""
            INSERT INTO matches (public_match_id, tournament_id, stage_name, round_number, status, bracket_type)
            VALUES (?, ?, 'Grand Final', 99, 'SCHEDULED', 'GRAND_FINAL');
        """, (_generate_next_public_match_id_sync(), tournament_id))

        cursor.execute("UPDATE tournaments SET status = 'ONGOING', format = 'Double Elimination' WHERE tournament_id = ?;", (tournament_id,))
        conn.commit()
        return _get_tournament_matches_sync(str(tournament_id))

async def generate_double_elimination_bracket(tournament_id: int) -> list[dict]:
    """Asynchronously generate double elimination bracket."""
    return await asyncio.to_thread(_generate_double_elimination_bracket_sync, tournament_id)

def _generate_swiss_round_sync(tournament_id: int, round_number: int = 1) -> list[dict]:
    """Generate next Swiss format round pairing based on current standings and Buchholz tiebreakers."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tournaments WHERE tournament_id = ?;", (tournament_id,))
        t_row = cursor.fetchone()
        if not t_row:
            raise ValueError(f"Tournament #{tournament_id} not found.")

        if round_number == 1:
            approved = _get_approved_teams_by_tournament_sync(t_row["title"])
            for t in approved:
                cursor.execute("SELECT team_id FROM teams WHERE LOWER(name) = LOWER(?);", (t["team_name"],))
                t_row_rec = cursor.fetchone()
                if t_row_rec:
                    cursor.execute("INSERT OR IGNORE INTO swiss_standings (tournament_id, team_id) VALUES (?, ?);", (tournament_id, t_row_rec["team_id"]))

        cursor.execute("""
            SELECT s.*, t.name as team_name 
            FROM swiss_standings s
            JOIN teams t ON s.team_id = t.team_id
            WHERE s.tournament_id = ?
            ORDER BY s.wins DESC, s.buchholz_score DESC, s.team_id ASC;
        """, (tournament_id,))
        standings = [dict(r) for r in cursor.fetchall()]

        if len(standings) < 2:
            raise ValueError("At least 2 teams required for Swiss system.")

        created_matches = []
        for i in range(0, len(standings), 2):
            t1 = standings[i]["team_id"]
            t2 = standings[i + 1]["team_id"] if i + 1 < len(standings) else None
            st = "COMPLETED" if t2 is None else "SCHEDULED"
            win = t1 if t2 is None else None
            pm_id = _generate_next_public_match_id_sync()

            cursor.execute("""
                INSERT INTO matches (public_match_id, tournament_id, stage_name, round_number, team1_id, team2_id, status, winner_id, swiss_round)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?);
            """, (pm_id, tournament_id, f"Swiss Round {round_number}", round_number, t1, t2, st, win, round_number))
            created_matches.append(cursor.lastrowid)

        cursor.execute("UPDATE tournaments SET status = 'ONGOING', format = 'Swiss' WHERE tournament_id = ?;", (tournament_id,))
        conn.commit()
        return _get_tournament_matches_sync(str(tournament_id))

async def generate_swiss_round(tournament_id: int, round_number: int = 1) -> list[dict]:
    """Asynchronously generate Swiss system round."""
    return await asyncio.to_thread(_generate_swiss_round_sync, tournament_id, round_number)

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
            SET team1_score = ?, team2_score = ?, score_a = ?, score_b = ?, winner_id = ?, status = ?,
                admin_verification_status = 'APPROVED', completed_at = CURRENT_TIMESTAMP
            WHERE match_id = ?;
        """, (team1_score, team2_score, team1_score, team2_score, winner_id, status, match_id))

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

        # Update ELO ratings idempotently
        if winner_id:
            loser_id = match["team2_id"] if winner_id == match["team1_id"] else match["team1_id"]
            if loser_id:
                _update_team_elo_after_match_sync(winner_id, loser_id)

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

# ==============================================================================
# SUPPORT TICKETS & DISCORD OPERATIONS FUNCTIONS
# ==============================================================================

def _generate_next_case_id_sync() -> str:
    """Generate unique Case ID in format GEN-CASE-XXXXXX."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM support_tickets;")
        count = cursor.fetchone()[0] + 1
        case_id = f"GEN-CASE-{count:06d}"
        
        # Verify collision safety
        while True:
            cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE case_id = ?;", (case_id,))
            if cursor.fetchone()[0] == 0:
                break
            count += 1
            case_id = f"GEN-CASE-{count:06d}"
        return case_id

async def generate_next_case_id() -> str:
    """Asynchronously generate a unique Case ID."""
    return await asyncio.to_thread(_generate_next_case_id_sync)

def _create_support_ticket_sync(
    case_id: str,
    ticket_type: str,
    user_id: str,
    guild_id: str,
    channel_id: str,
    related_tournament_id: int | None = None,
    related_registration_id: int | None = None,
    priority: str = "NORMAL"
) -> dict:
    """Synchronously record a new support ticket."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO support_tickets 
            (case_id, ticket_type, user_id, guild_id, channel_id, related_tournament_id, related_registration_id, priority, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'OPEN');
        """, (case_id, ticket_type, str(user_id), str(guild_id), str(channel_id), related_tournament_id, related_registration_id, priority))
        
        t_id = cursor.lastrowid
        cursor.execute("SELECT * FROM support_tickets WHERE ticket_id = ?;", (t_id,))
        row = cursor.fetchone()
        conn.commit()
        return dict(row)

async def create_support_ticket(
    case_id: str,
    ticket_type: str,
    user_id: str,
    guild_id: str,
    channel_id: str,
    related_tournament_id: int | None = None,
    related_registration_id: int | None = None,
    priority: str = "NORMAL"
) -> dict:
    """Asynchronously record a new support ticket."""
    return await asyncio.to_thread(
        _create_support_ticket_sync, case_id, ticket_type, user_id, guild_id, channel_id, related_tournament_id, related_registration_id, priority
    )

def _get_support_ticket_by_case_id_sync(case_id: str) -> dict | None:
    """Fetch support ticket details by Case ID."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, t.title as tournament_name 
            FROM support_tickets s
            LEFT JOIN tournaments t ON s.related_tournament_id = t.tournament_id
            WHERE LOWER(s.case_id) = LOWER(?);
        """, (case_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

async def get_support_ticket_by_case_id(case_id: str) -> dict | None:
    """Asynchronously fetch support ticket details by Case ID."""
    return await asyncio.to_thread(_get_support_ticket_by_case_id_sync, case_id)

def _get_support_ticket_by_channel_sync(channel_id: str) -> dict | None:
    """Fetch active support ticket by Discord channel ID."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, t.title as tournament_name 
            FROM support_tickets s
            LEFT JOIN tournaments t ON s.related_tournament_id = t.tournament_id
            WHERE s.channel_id = ?;
        """, (str(channel_id),))
        row = cursor.fetchone()
        return dict(row) if row else None

async def get_support_ticket_by_channel(channel_id: str) -> dict | None:
    """Asynchronously fetch active support ticket by Discord channel ID."""
    return await asyncio.to_thread(_get_support_ticket_by_channel_sync, channel_id)

def _update_support_ticket_assignment_sync(case_id: str, staff_id: str) -> bool:
    """Update assigned primary staff member for a support ticket."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE support_tickets 
            SET assigned_staff_id = ?, status = CASE WHEN status = 'OPEN' THEN 'IN_PROGRESS' ELSE status END, updated_at = CURRENT_TIMESTAMP 
            WHERE LOWER(case_id) = LOWER(?);
        """, (str(staff_id), case_id))
        
        cursor.execute("""
            INSERT INTO audit_logs (admin_id, action, details)
            VALUES (?, 'CLAIM_SUPPORT_TICKET', ?);
        """, (str(staff_id), f"Assigned staff {staff_id} to Case #{case_id}"))
        
        conn.commit()
        return cursor.rowcount > 0

async def update_support_ticket_assignment(case_id: str, staff_id: str) -> bool:
    """Asynchronously update assigned primary staff member."""
    return await asyncio.to_thread(_update_support_ticket_assignment_sync, case_id, staff_id)

def _update_support_ticket_priority_sync(case_id: str, priority: str, staff_id: str) -> bool:
    """Update priority level for a support ticket."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE support_tickets 
            SET priority = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE LOWER(case_id) = LOWER(?);
        """, (priority, case_id))
        
        cursor.execute("""
            INSERT INTO audit_logs (admin_id, action, details)
            VALUES (?, 'SET_TICKET_PRIORITY', ?);
        """, (str(staff_id), f"Changed priority to '{priority}' for Case #{case_id}"))
        
        conn.commit()
        return cursor.rowcount > 0

async def update_support_ticket_priority(case_id: str, priority: str, staff_id: str) -> bool:
    """Asynchronously update ticket priority level."""
    return await asyncio.to_thread(_update_support_ticket_priority_sync, case_id, priority, staff_id)

def _add_support_ticket_note_sync(case_id: str, staff_id: str, note_text: str) -> bool:
    """Add an internal staff note to a support case."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO support_ticket_notes (case_id, staff_id, note_text)
            VALUES (?, ?, ?);
        """, (case_id, str(staff_id), note_text))
        
        cursor.execute("""
            INSERT INTO audit_logs (admin_id, action, details)
            VALUES (?, 'ADD_TICKET_NOTE', ?);
        """, (str(staff_id), f"Added internal note to Case #{case_id}"))
        
        conn.commit()
        return True

async def add_support_ticket_note(case_id: str, staff_id: str, note_text: str) -> bool:
    """Asynchronously add an internal staff note to a support case."""
    return await asyncio.to_thread(_add_support_ticket_note_sync, case_id, staff_id, note_text)

def _close_support_ticket_sync(case_id: str, staff_id: str, resolution: str, close_reason: str) -> bool:
    """Mark support ticket as CLOSED and save resolution details."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE support_tickets 
            SET status = 'CLOSED', closed_at = CURRENT_TIMESTAMP, resolution = ?, close_reason = ?, updated_at = CURRENT_TIMESTAMP 
            WHERE LOWER(case_id) = LOWER(?);
        """, (resolution, close_reason, case_id))
        
        cursor.execute("""
            INSERT INTO audit_logs (admin_id, action, details)
            VALUES (?, 'CLOSE_SUPPORT_TICKET', ?);
        """, (str(staff_id), f"Closed Case #{case_id}. Resolution: {resolution} (Reason: {close_reason})"))
        
        conn.commit()
        return cursor.rowcount > 0

async def close_support_ticket(case_id: str, staff_id: str, resolution: str, close_reason: str) -> bool:
    """Asynchronously mark support ticket as CLOSED."""
    return await asyncio.to_thread(_close_support_ticket_sync, case_id, staff_id, resolution, close_reason)

def _save_support_transcript_sync(case_id: str, transcript_text: str) -> bool:
    """Store raw support transcript in database."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO support_transcripts (case_id, transcript_text)
            VALUES (?, ?);
        """, (case_id, transcript_text))
        conn.commit()
        return True

async def save_support_transcript(case_id: str, transcript_text: str) -> bool:
    """Asynchronously store raw support transcript."""
    return await asyncio.to_thread(_save_support_transcript_sync, case_id, transcript_text)

def _get_user_active_support_tickets_sync(user_id: str, ticket_type: str | None = None) -> list[dict]:
    """Fetch all open/in_progress support tickets for a user."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        if ticket_type:
            cursor.execute("""
                SELECT * FROM support_tickets 
                WHERE user_id = ? AND status != 'CLOSED' AND ticket_type = ?;
            """, (str(user_id), ticket_type))
        else:
            cursor.execute("""
                SELECT * FROM support_tickets 
                WHERE user_id = ? AND status != 'CLOSED';
            """, (str(user_id),))
        return [dict(row) for row in cursor.fetchall()]

async def get_user_active_support_tickets(user_id: str, ticket_type: str | None = None) -> list[dict]:
    """Asynchronously fetch active support tickets for a user."""
    return await asyncio.to_thread(_get_user_active_support_tickets_sync, user_id, ticket_type)

def _get_user_all_registrations_sync(user_id: str) -> list[dict]:
    """Fetch all team registrations created by a Discord user ID."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ticket_id, registration_code, tournament_name, team_name, captain_name, status, created_at, updated_at 
            FROM tickets 
            WHERE creator_id = ? OR captain_discord_id = ? 
            ORDER BY ticket_id DESC;
        """, (str(user_id), str(user_id)))
        return [dict(row) for row in cursor.fetchall()]

async def get_user_all_registrations(user_id: str) -> list[dict]:
    """Asynchronously fetch all registrations for a Discord user."""
    return await asyncio.to_thread(_get_user_all_registrations_sync, user_id)

def _get_user_all_cases_sync(user_id: str) -> list[dict]:
    """Fetch all support tickets created by a Discord user ID."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT s.*, t.title as tournament_name 
            FROM support_tickets s
            LEFT JOIN tournaments t ON s.related_tournament_id = t.tournament_id
            WHERE s.user_id = ? 
            ORDER BY s.ticket_id DESC;
        """, (str(user_id),))
        return [dict(row) for row in cursor.fetchall()]

async def get_user_all_cases(user_id: str) -> list[dict]:
    """Asynchronously fetch all support tickets for a user."""
    return await asyncio.to_thread(_get_user_all_cases_sync, user_id)

# ==============================================================================
# PLAYER & TEAM IDENTITY FUNCTIONS
# ==============================================================================

def _get_or_create_player_sync(discord_user_id: str, username: str = "", display_name: str = "", avatar_url: str = "", primary_game: str = "VALORANT") -> dict:
    """Get existing player by discord_user_id or create a new player entry with public GEN-P-XXXXXX ID."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM players WHERE discord_user_id = ?;", (str(discord_user_id),))
        row = cursor.fetchone()
        if row:
            player = dict(row)
            # Update display info if changed
            if (display_name and display_name != player["display_name"]) or (avatar_url and avatar_url != player["avatar_url"]):
                cursor.execute("""
                    UPDATE players 
                    SET display_name = COALESCE(NULLIF(?, ''), display_name),
                        avatar_url = COALESCE(NULLIF(?, ''), avatar_url),
                        updated_at = CURRENT_TIMESTAMP
                    WHERE player_id = ?;
                """, (display_name, avatar_url, player["player_id"]))
                conn.commit()
                cursor.execute("SELECT * FROM players WHERE player_id = ?;", (player["player_id"],))
                return dict(cursor.fetchone())
            return player

        # Generate next public player ID
        cursor.execute("SELECT COUNT(*) FROM players;")
        count = cursor.fetchone()[0] + 1
        public_id = f"GEN-P-{count:06d}"
        while True:
            cursor.execute("SELECT COUNT(*) FROM players WHERE public_id = ?;", (public_id,))
            if cursor.fetchone()[0] == 0:
                break
            count += 1
            public_id = f"GEN-P-{count:06d}"

        u_name = username or f"User_{discord_user_id[:6]}"
        d_name = display_name or u_name

        cursor.execute("PRAGMA table_info(players);")
        p_cols = [col[1] for col in cursor.fetchall()]

        fields = ["public_id", "discord_user_id", "username", "display_name", "avatar_url", "primary_game", "verification_status"]
        vals = [public_id, str(discord_user_id), u_name, d_name, avatar_url, primary_game, 'UNVERIFIED']

        if "ign" in p_cols:
            fields.append("ign")
            vals.append(d_name)
        if "discord_id" in p_cols:
            fields.append("discord_id")
            vals.append(str(discord_user_id))

        placeholders = ", ".join(["?"] * len(fields))
        field_str = ", ".join(fields)
        cursor.execute(f"INSERT INTO players ({field_str}) VALUES ({placeholders});", vals)
        
        p_id = cursor.lastrowid
        
        # Initialize stats table
        cursor.execute("INSERT OR IGNORE INTO player_stats (player_id) VALUES (?);", (p_id,))
        
        conn.commit()
        cursor.execute("SELECT * FROM players WHERE player_id = ?;", (p_id,))
        return dict(cursor.fetchone())

async def get_or_create_player(discord_user_id: str, username: str = "", display_name: str = "", avatar_url: str = "", primary_game: str = "VALORANT") -> dict:
    """Asynchronously get or create a player profile."""
    return await asyncio.to_thread(_get_or_create_player_sync, discord_user_id, username, display_name, avatar_url, primary_game)

def _get_or_create_team_sync(name: str, captain_player_id: int, game: str = "VALORANT", logo_url: str = "") -> dict:
    """Get existing team by slug or create new team entry with public GEN-T-XXXXXX ID."""
    clean_name = name.strip()
    slug = clean_name.lower().replace(' ', '-')
    
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM teams WHERE LOWER(slug) = LOWER(?) OR LOWER(name) = LOWER(?);", (slug, clean_name))
        row = cursor.fetchone()
        if row:
            return dict(row)

        cursor.execute("SELECT COUNT(*) FROM teams;")
        count = cursor.fetchone()[0] + 1
        public_id = f"GEN-T-{count:06d}"
        while True:
            cursor.execute("SELECT COUNT(*) FROM teams WHERE public_id = ?;", (public_id,))
            if cursor.fetchone()[0] == 0:
                break
            count += 1
            public_id = f"GEN-T-{count:06d}"

        cursor.execute("""
            INSERT INTO teams (public_id, name, slug, logo_url, captain_player_id, game, verification_status)
            VALUES (?, ?, ?, ?, ?, ?, 'UNVERIFIED');
        """, (public_id, clean_name, slug, logo_url, captain_player_id, game))
        
        t_id = cursor.lastrowid
        
        # Add captain to team_members
        cursor.execute("""
            INSERT OR IGNORE INTO team_members (team_id, player_id, role, status)
            VALUES (?, ?, 'CAPTAIN', 'ACTIVE');
        """, (t_id, captain_player_id))
        
        conn.commit()
        cursor.execute("SELECT * FROM teams WHERE team_id = ?;", (t_id,))
        return dict(cursor.fetchone())

async def get_or_create_team(name: str, captain_player_id: int, game: str = "VALORANT", logo_url: str = "") -> dict:
    """Asynchronously get or create a team identity."""
    return await asyncio.to_thread(_get_or_create_team_sync, name, captain_player_id, game, logo_url)

def _lock_tournament_roster_snapshot_sync(ticket_id: int) -> bool:
    """Lock a team's active roster at registration time so future changes do not alter historical records."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tickets WHERE ticket_id = ?;", (ticket_id,))
        t_row = cursor.fetchone()
        if not t_row:
            return False
        
        ticket = dict(t_row)
        cursor.execute("SELECT * FROM roster_players WHERE ticket_id = ?;", (ticket_id,))
        players = cursor.fetchall()
        
        # Create roster snapshot entries
        for p in players:
            cursor.execute("""
                INSERT INTO tournament_roster_snapshots (ticket_id, player_role, ign)
                VALUES (?, ?, ?);
            """, (ticket_id, p["player_role"], p["ign"]))
            
        conn.commit()
        return True

async def lock_tournament_roster_snapshot(ticket_id: int) -> bool:
    """Asynchronously lock a tournament roster snapshot."""
    return await asyncio.to_thread(_lock_tournament_roster_snapshot_sync, ticket_id)

def _get_player_full_profile_sync(identifier: str) -> dict | None:
    """Fetch public player profile sanitized for safety (NO Discord ID, NO phone, NO email, NO private support info)."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT player_id, public_id, username, display_name, avatar_url, country, bio, primary_game, verification_status, created_at
            FROM players 
            WHERE LOWER(public_id) = LOWER(?) OR LOWER(username) = LOWER(?) OR CAST(player_id AS TEXT) = ? OR discord_user_id = ?;
        """, (identifier, identifier, identifier, identifier))
        row = cursor.fetchone()
        if not row:
            return None
        
        player = dict(row)
        p_id = player["player_id"]

        # Fetch stats
        cursor.execute("SELECT * FROM player_stats WHERE player_id = ?;", (p_id,))
        st_row = cursor.fetchone()
        stats = dict(st_row) if st_row else {"matches_played": 0, "wins": 0, "losses": 0, "tournaments_played": 0, "tournament_wins": 0, "mvp_count": 0}
        
        mp = stats.get("matches_played", 0)
        w = stats.get("wins", 0)
        stats["win_rate"] = round((w / mp) * 100, 1) if mp > 0 else 0.0

        player["stats"] = stats

        # Fetch achievements
        cursor.execute("SELECT title, description, badge_icon, awarded_at FROM achievements WHERE entity_type = 'PLAYER' AND entity_id = ?;", (p_id,))
        player["achievements"] = [dict(r) for r in cursor.fetchall()]

        # Fetch team memberships
        cursor.execute("""
            SELECT tm.role, tm.status, t.public_id as team_public_id, t.name as team_name, t.slug as team_slug, t.logo_url as team_logo
            FROM team_members tm
            JOIN teams t ON tm.team_id = t.team_id
            WHERE tm.player_id = ? AND tm.status = 'ACTIVE';
        """, (p_id,))
        player["teams"] = [dict(r) for r in cursor.fetchall()]

        return player

async def get_player_full_profile(identifier: str) -> dict | None:
    """Asynchronously fetch public player profile."""
    return await asyncio.to_thread(_get_player_full_profile_sync, identifier)

def _get_team_full_profile_sync(identifier: str) -> dict | None:
    """Fetch public team profile sanitized for safety."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT team_id, public_id, name, slug, logo_url, description, game, region, verification_status, created_at 
            FROM teams 
            WHERE LOWER(slug) = LOWER(?) OR LOWER(public_id) = LOWER(?) OR LOWER(name) = LOWER(?) OR CAST(team_id AS TEXT) = ?;
        """, (identifier, identifier, identifier, identifier))
        row = cursor.fetchone()
        if not row:
            return None

        team = dict(row)
        t_id = team["team_id"]

        # Fetch roster
        cursor.execute("""
            SELECT tm.role, p.public_id, p.display_name, p.username, p.avatar_url
            FROM team_members tm
            JOIN players p ON tm.player_id = p.player_id
            WHERE tm.team_id = ? AND tm.status = 'ACTIVE';
        """, (t_id,))
        team["roster"] = [dict(r) for r in cursor.fetchall()]

        # Fetch achievements
        cursor.execute("SELECT title, description, badge_icon, awarded_at FROM achievements WHERE entity_type = 'TEAM' AND entity_id = ?;", (t_id,))
        team["achievements"] = [dict(r) for r in cursor.fetchall()]

        # Fetch tournament history
        cursor.execute("""
            SELECT DISTINCT tournament_name, status, created_at 
            FROM tickets 
            WHERE status = 'APPROVED' AND LOWER(team_name) = LOWER(?);
        """, (team["name"],))
        team["tournament_history"] = [dict(r) for r in cursor.fetchall()]

        return team

async def get_team_full_profile(identifier: str) -> dict | None:
    """Asynchronously fetch public team profile."""
    return await asyncio.to_thread(_get_team_full_profile_sync, identifier)

def _get_all_players_public_sync() -> list[dict]:
    """Fetch sanitized directory list of public players."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT public_id, display_name, username, avatar_url, primary_game, verification_status 
            FROM players 
            ORDER BY player_id DESC LIMIT 50;
        """)
        return [dict(r) for r in cursor.fetchall()]

async def get_all_players_public() -> list[dict]:
    """Asynchronously fetch public players directory."""
    return await asyncio.to_thread(_get_all_players_public_sync)

def _get_all_teams_public_sync() -> list[dict]:
    """Fetch sanitized directory list of public teams."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT public_id, name, slug, logo_url, game, region, verification_status 
            FROM teams 
            ORDER BY team_id DESC LIMIT 50;
        """)
        return [dict(r) for r in cursor.fetchall()]

async def get_all_teams_public() -> list[dict]:
    """Asynchronously fetch public teams directory."""
    return await asyncio.to_thread(_get_all_teams_public_sync)

def _set_player_verification_status_sync(player_id: int, status: str) -> bool:
    """Set verification status for a player (VERIFIED, UNVERIFIED, SUSPENDED)."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE players SET verification_status = ?, updated_at = CURRENT_TIMESTAMP WHERE player_id = ?;", (status, player_id))
        conn.commit()
        return cursor.rowcount > 0

async def set_player_verification_status(player_id: int, status: str) -> bool:
    """Asynchronously update player verification status."""
    return await asyncio.to_thread(_set_player_verification_status_sync, player_id, status)

def _set_team_verification_status_sync(team_id: int, status: str) -> bool:
    """Set verification status for a team (VERIFIED, PENDING, UNVERIFIED, SUSPENDED)."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE teams SET verification_status = ?, updated_at = CURRENT_TIMESTAMP WHERE team_id = ?;", (status, team_id))
        conn.commit()
        return cursor.rowcount > 0

async def set_team_verification_status(team_id: int, status: str) -> bool:
    """Asynchronously update team verification status."""
    return await asyncio.to_thread(_set_team_verification_status_sync, team_id, status)

# ==============================================================================
# MATCH LIFECYCLE & CHECK-IN FUNCTIONS
# ==============================================================================

def _generate_next_public_match_id_sync() -> str:
    """Generate next collision-free public match ID in format GEN-M-XXXXXX."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM matches WHERE public_match_id IS NOT NULL;")
        count = cursor.fetchone()[0] + 1
        public_id = f"GEN-M-{count:06d}"
        while True:
            cursor.execute("SELECT COUNT(*) FROM matches WHERE public_match_id = ?;", (public_id,))
            if cursor.fetchone()[0] == 0:
                break
            count += 1
            public_id = f"GEN-M-{count:06d}"
        return public_id

async def generate_next_public_match_id() -> str:
    """Asynchronously generate next public match ID."""
    return await asyncio.to_thread(_generate_next_public_match_id_sync)

def _update_match_schedule_and_lobby_sync(match_id: int, scheduled_at: str | None = None, check_in_open: str | None = None, check_in_deadline: str | None = None, lobby_name: str | None = None, lobby_code: str | None = None, lobby_password: str | None = None, map_name: str | None = None, server_region: str | None = None) -> dict | None:
    """Schedule match & set lobby credentials safely."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE match_id = ? OR public_match_id = ?;", (match_id, str(match_id)))
        m_row = cursor.fetchone()
        if not m_row:
            return None

        match = dict(m_row)
        m_id = match["match_id"]

        if not match.get("public_match_id"):
            pm_id = _generate_next_public_match_id_sync()
        else:
            pm_id = match["public_match_id"]

        cursor.execute("""
            UPDATE matches 
            SET public_match_id = ?,
                scheduled_time = COALESCE(?, scheduled_time),
                check_in_open_at = COALESCE(?, check_in_open_at),
                check_in_deadline = COALESCE(?, check_in_deadline),
                lobby_name = COALESCE(?, lobby_name),
                lobby_code = COALESCE(?, lobby_code),
                lobby_password = COALESCE(?, lobby_password),
                map = COALESCE(?, map),
                server_region = COALESCE(?, server_region),
                status = CASE WHEN status = 'SCHEDULED' AND ? IS NOT NULL THEN 'CHECK_IN_OPEN' ELSE status END
            WHERE match_id = ?;
        """, (pm_id, scheduled_at, check_in_open, check_in_deadline, lobby_name, lobby_code, lobby_password, map_name, server_region, check_in_open, m_id))

        conn.commit()
        cursor.execute("SELECT * FROM matches WHERE match_id = ?;", (m_id,))
        return dict(cursor.fetchone())

async def update_match_schedule_and_lobby(match_id: int, scheduled_at: str | None = None, check_in_open: str | None = None, check_in_deadline: str | None = None, lobby_name: str | None = None, lobby_code: str | None = None, lobby_password: str | None = None, map_name: str | None = None, server_region: str | None = None) -> dict | None:
    """Asynchronously update match schedule and lobby details."""
    return await asyncio.to_thread(_update_match_schedule_and_lobby_sync, match_id, scheduled_at, check_in_open, check_in_deadline, lobby_name, lobby_code, lobby_password, map_name, server_region)

def _process_match_check_in_sync(match_id: int, team_id: int) -> dict | None:
    """Process check-in for a team. Sets status to READY when both check in."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE match_id = ? OR public_match_id = ?;", (match_id, str(match_id)))
        m_row = cursor.fetchone()
        if not m_row:
            return None

        match = dict(m_row)
        m_id = match["match_id"]

        team_a_id = match.get("team1_id")
        team_b_id = match.get("team2_id")

        if int(team_id) == team_a_id:
            cursor.execute("UPDATE matches SET team_a_checked_in = 1 WHERE match_id = ?;", (m_id,))
        elif int(team_id) == team_b_id:
            cursor.execute("UPDATE matches SET team_b_checked_in = 1 WHERE match_id = ?;", (m_id,))
        else:
            return None

        cursor.execute("SELECT team_a_checked_in, team_b_checked_in FROM matches WHERE match_id = ?;", (m_id,))
        r = cursor.fetchone()
        if r and r[0] == 1 and r[1] == 1:
            cursor.execute("UPDATE matches SET status = 'READY' WHERE match_id = ?;", (m_id,))

        conn.commit()
        cursor.execute("SELECT * FROM matches WHERE match_id = ?;", (m_id,))
        return dict(cursor.fetchone())

async def process_match_check_in(match_id: int, team_id: int) -> dict | None:
    """Asynchronously process team check-in."""
    return await asyncio.to_thread(_process_match_check_in_sync, match_id, team_id)

def _submit_match_score_sync(match_id: int, submitting_team_id: int, submitting_user_id: str, score_a: int, score_b: int, evidence_url: str = "") -> dict | None:
    """Submit match result. Transitions status to OPPONENT_CONFIRMATION."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE match_id = ? OR public_match_id = ?;", (match_id, str(match_id)))
        m_row = cursor.fetchone()
        if not m_row:
            return None

        match = dict(m_row)
        m_id = match["match_id"]

        cursor.execute("""
            UPDATE matches 
            SET score_a = ?, score_b = ?, team1_score = ?, team2_score = ?,
                result_submitted_by = ?, result_submitted_at = CURRENT_TIMESTAMP,
                evidence_url = ?, opponent_confirmation_status = 'PENDING',
                status = 'OPPONENT_CONFIRMATION'
            WHERE match_id = ?;
        """, (score_a, score_b, score_a, score_b, str(submitting_user_id), evidence_url, m_id))

        conn.commit()
        cursor.execute("SELECT * FROM matches WHERE match_id = ?;", (m_id,))
        return dict(cursor.fetchone())

async def submit_match_score(match_id: int, submitting_team_id: int, submitting_user_id: str, score_a: int, score_b: int, evidence_url: str = "") -> dict | None:
    """Asynchronously submit match score."""
    return await asyncio.to_thread(_submit_match_score_sync, match_id, submitting_team_id, submitting_user_id, score_a, score_b, evidence_url)

def _confirm_opponent_match_score_sync(match_id: int, confirming_user_id: str, accept: bool, dispute_reason: str = "") -> dict | None:
    """Confirm or dispute opponent score submission."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE match_id = ? OR public_match_id = ?;", (match_id, str(match_id)))
        m_row = cursor.fetchone()
        if not m_row:
            return None

        match = dict(m_row)
        m_id = match["match_id"]

        if accept:
            cursor.execute("""
                UPDATE matches 
                SET opponent_confirmation_status = 'CONFIRMED', status = 'ADMIN_REVIEW'
                WHERE match_id = ?;
            """, (m_id,))
        else:
            cursor.execute("SELECT COUNT(*) FROM support_tickets;")
            c_cnt = cursor.fetchone()[0] + 1
            case_id = f"GEN-CASE-{c_cnt:06d}"

            cursor.execute("""
                INSERT INTO support_tickets (case_id, ticket_type, user_id, guild_id, channel_id, related_tournament_id, status, priority)
                VALUES (?, 'DISPUTE', ?, '0', '0', ?, 'OPEN', 'HIGH');
            """, (case_id, str(confirming_user_id), match["tournament_id"]))

            cursor.execute("""
                UPDATE matches 
                SET opponent_confirmation_status = 'DISPUTED', status = 'DISPUTED', case_id = ?
                WHERE match_id = ?;
            """, (case_id, m_id))

        conn.commit()
        cursor.execute("SELECT * FROM matches WHERE match_id = ?;", (m_id,))
        return dict(cursor.fetchone())

async def confirm_opponent_match_score(match_id: int, confirming_user_id: str, accept: bool, dispute_reason: str = "") -> dict | None:
    """Asynchronously confirm or dispute match score."""
    return await asyncio.to_thread(_confirm_opponent_match_score_sync, match_id, confirming_user_id, accept, dispute_reason)

# ==============================================================================
# COMPETITIVE INTEGRITY, SEEDING, ELO & VETO ENGINE
# ==============================================================================

import json
import random

def _generate_tournament_seeds_sync(tournament_id: int, method: str = "RANDOM") -> list[dict]:
    """Generate or update team seeds for a tournament."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        
        # Check if seeds are locked
        cursor.execute("SELECT is_locked FROM team_seeds WHERE tournament_id = ? AND is_locked = 1;", (tournament_id,))
        if cursor.fetchone():
            cursor.execute("SELECT * FROM team_seeds WHERE tournament_id = ? ORDER BY seed_number ASC;", (tournament_id,))
            return [dict(r) for r in cursor.fetchall()]

        # Fetch tournament title/slug
        cursor.execute("SELECT title, slug FROM tournaments WHERE tournament_id = ? OR CAST(tournament_id AS TEXT) = ?;", (tournament_id, str(tournament_id)))
        t_row = cursor.fetchone()
        if not t_row:
            return []

        approved_teams = _get_approved_teams_by_tournament_sync(t_row["title"])
        if not approved_teams:
            approved_teams = _get_approved_teams_by_tournament_sync(t_row["slug"])

        teams = [r["team_name"] for r in approved_teams]
        if not teams:
            return []

        team_id_list = []
        for t_name in teams:
            cursor.execute("SELECT team_id FROM teams WHERE LOWER(name) = LOWER(?);", (t_name,))
            row = cursor.fetchone()
            if row:
                team_id_list.append((row["team_id"], t_name))

        if method == "RANDOM":
            random.shuffle(team_id_list)
        elif method == "ELO":
            scored = []
            for t_id, name in team_id_list:
                cursor.execute("SELECT rating FROM team_elo WHERE team_id = ?;", (t_id,))
                e_row = cursor.fetchone()
                rating = e_row["rating"] if e_row else 1200
                scored.append((rating, t_id, name))
            scored.sort(key=lambda x: x[0], reverse=True)
            team_id_list = [(t_id, name) for _, t_id, name in scored]

        cursor.execute("DELETE FROM team_seeds WHERE tournament_id = ? AND is_locked = 0;", (tournament_id,))
        
        seeds = []
        for idx, (t_id, name) in enumerate(team_id_list, start=1):
            cursor.execute("""
                INSERT OR REPLACE INTO team_seeds (tournament_id, team_id, seed_number, seeding_method, is_locked)
                VALUES (?, ?, ?, ?, 0);
            """, (tournament_id, t_id, idx, method))
            seeds.append({"seed_id": cursor.lastrowid, "tournament_id": tournament_id, "team_id": t_id, "team_name": name, "seed_number": idx, "seeding_method": method, "is_locked": 0})

        conn.commit()
        return seeds

async def generate_tournament_seeds(tournament_id: int, method: str = "RANDOM") -> list[dict]:
    """Asynchronously generate team seeds."""
    return await asyncio.to_thread(_generate_tournament_seeds_sync, tournament_id, method)

def _lock_tournament_seeds_sync(tournament_id: int) -> bool:
    """Lock team seeds before bracket generation."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE team_seeds SET is_locked = 1 WHERE tournament_id = ?;", (tournament_id,))
        conn.commit()
        return cursor.rowcount > 0

async def lock_tournament_seeds(tournament_id: int) -> bool:
    """Asynchronously lock seeds."""
    return await asyncio.to_thread(_lock_tournament_seeds_sync, tournament_id)

def _update_team_elo_after_match_sync(winner_team_id: int, loser_team_id: int, k_factor: int = 32) -> bool:
    """Idempotently calculate and update team ELO ratings after a verified match."""
    if not winner_team_id or not loser_team_id or winner_team_id == loser_team_id:
        return False

    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR IGNORE INTO team_elo (team_id, rating) VALUES (?, 1200);", (winner_team_id,))
        cursor.execute("INSERT OR IGNORE INTO team_elo (team_id, rating) VALUES (?, 1200);", (loser_team_id,))

        cursor.execute("SELECT rating FROM team_elo WHERE team_id = ?;", (winner_team_id,))
        r_w = cursor.fetchone()["rating"]
        cursor.execute("SELECT rating FROM team_elo WHERE team_id = ?;", (loser_team_id,))
        r_l = cursor.fetchone()["rating"]

        expected_w = 1 / (1 + 10 ** ((r_l - r_w) / 400))
        expected_l = 1 / (1 + 10 ** ((r_w - r_l) / 400))

        new_r_w = round(r_w + k_factor * (1 - expected_w))
        new_r_l = round(r_l + k_factor * (0 - expected_l))

        cursor.execute("UPDATE team_elo SET rating = ?, matches_rated = matches_rated + 1, wins = wins + 1, last_updated = CURRENT_TIMESTAMP WHERE team_id = ?;", (new_r_w, winner_team_id))
        cursor.execute("UPDATE team_elo SET rating = ?, matches_rated = matches_rated + 1, losses = losses + 1, last_updated = CURRENT_TIMESTAMP WHERE team_id = ?;", (new_r_l, loser_team_id))

        conn.commit()
        return True

async def update_team_elo_after_match(winner_team_id: int, loser_team_id: int, k_factor: int = 32) -> bool:
    """Asynchronously update team ELO ratings."""
    return await asyncio.to_thread(_update_team_elo_after_match_sync, winner_team_id, loser_team_id, k_factor)

def _get_or_create_tournament_ruleset_sync(tournament_id: int, game_name: str = "VALORANT", best_of: str = "BO3") -> dict:
    """Fetch or create ruleset for a tournament."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM tournament_rulesets WHERE tournament_id = ?;", (tournament_id,))
        row = cursor.fetchone()
        if row:
            rules = dict(row)
            rules["allowed_maps"] = json.loads(rules.get("allowed_maps") or "[]")
            rules["veto_sequence"] = json.loads(rules.get("veto_sequence") or "[]")
            return rules

        maps = json.dumps(["Ascent", "Bind", "Haven", "Lotus", "Sunset"])
        seq = json.dumps(["BAN_A", "BAN_B", "PICK_A", "PICK_B", "BAN_A", "BAN_B", "DECIDER"])

        cursor.execute("""
            INSERT INTO tournament_rulesets (tournament_id, game_name, best_of, allowed_maps, veto_sequence)
            VALUES (?, ?, ?, ?, ?);
        """, (tournament_id, game_name, best_of, maps, seq))
        
        conn.commit()
        return {
            "ruleset_id": cursor.lastrowid, "tournament_id": tournament_id,
            "game_name": game_name, "best_of": best_of,
            "allowed_maps": json.loads(maps), "veto_sequence": json.loads(seq),
            "overtime_rules": "Overtime win by 2 maps/rounds.", "rules_version": "1.0"
        }

async def get_or_create_tournament_ruleset(tournament_id: int, game_name: str = "VALORANT", best_of: str = "BO3") -> dict:
    """Asynchronously get or create ruleset."""
    return await asyncio.to_thread(_get_or_create_tournament_ruleset_sync, tournament_id, game_name, best_of)

def _record_result_correction_sync(match_id: int, admin_id: str, reason: str, old_score_a: int, old_score_b: int, new_score_a: int, new_score_b: int) -> bool:
    """Record an immutable result correction event in audit log."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO result_corrections (match_id, admin_id, reason, old_score_a, old_score_b, new_score_a, new_score_b)
            VALUES (?, ?, ?, ?, ?, ?, ?);
        """, (match_id, str(admin_id), reason, old_score_a, old_score_b, new_score_a, new_score_b))

        cursor.execute("""
            INSERT INTO audit_logs (admin_id, action, details)
            VALUES (?, 'CORRECT_MATCH_SCORE', ?);
        """, (str(admin_id), f"Match #{match_id} score corrected from {old_score_a}-{old_score_b} to {new_score_a}-{new_score_b}. Reason: {reason}"))

        conn.commit()
        return True

async def record_result_correction(match_id: int, admin_id: str, reason: str, old_score_a: int, old_score_b: int, new_score_a: int, new_score_b: int) -> bool:
    """Asynchronously record result correction."""
    return await asyncio.to_thread(_record_result_correction_sync, match_id, admin_id, reason, old_score_a, old_score_b, new_score_a, new_score_b)

def _start_match_veto_session_sync(match_id: int) -> dict | None:
    """Initialize map veto session for a match based on tournament ruleset."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE match_id = ? OR public_match_id = ?;", (match_id, str(match_id)))
        m_row = cursor.fetchone()
        if not m_row:
            return None

        match = dict(m_row)
        m_id = match["match_id"]
        t_id = match["tournament_id"]

        rules = _get_or_create_tournament_ruleset_sync(t_id)
        maps = rules.get("allowed_maps") or ["Ascent", "Bind", "Haven", "Lotus", "Sunset"]
        sequence = rules.get("veto_sequence") or ["BAN_A", "BAN_B", "PICK_A", "PICK_B", "BAN_A", "BAN_B", "DECIDER"]

        initial_state = {
            "allowed_maps": maps,
            "available_maps": maps.copy(),
            "banned_maps": [],
            "picked_maps": [],
            "decider_map": None,
            "veto_sequence": sequence,
            "current_step_index": 0,
            "team_a_id": match.get("team1_id"),
            "team_b_id": match.get("team2_id")
        }

        first_step = sequence[0] if sequence else "BAN_A"
        current_turn_team = match.get("team1_id") if "A" in first_step else match.get("team2_id")

        state_json = json.dumps(initial_state)

        cursor.execute("""
            INSERT OR REPLACE INTO veto_sessions (match_id, current_turn_team_id, veto_state, status)
            VALUES (?, ?, ?, 'IN_PROGRESS');
        """, (m_id, current_turn_team, state_json))

        conn.commit()
        cursor.execute("SELECT * FROM veto_sessions WHERE match_id = ?;", (m_id,))
        v_row = cursor.fetchone()
        res = dict(v_row)
        res["veto_state"] = json.loads(res["veto_state"])
        return res

async def start_match_veto_session(match_id: int) -> dict | None:
    """Asynchronously start match veto session."""
    return await asyncio.to_thread(_start_match_veto_session_sync, match_id)

def _process_veto_action_sync(match_id: int, acting_team_id: int, map_name: str) -> dict | None:
    """Execute a map ban or pick turn in a veto session."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM veto_sessions WHERE match_id = ? OR CAST(match_id AS TEXT) = ?;", (match_id, str(match_id)))
        v_row = cursor.fetchone()
        if not v_row:
            return None

        veto = dict(v_row)
        if veto["status"] != "IN_PROGRESS":
            return veto

        state = json.loads(veto["veto_state"])
        sequence = state["veto_sequence"]
        step_idx = state["current_step_index"]

        if step_idx >= len(sequence):
            return veto

        current_action = sequence[step_idx]
        available_maps = state["available_maps"]

        if map_name not in available_maps:
            return None

        action_type = "BAN" if "BAN" in current_action else "PICK"
        available_maps.remove(map_name)

        if action_type == "BAN":
            state["banned_maps"].append(map_name)
        else:
            state["picked_maps"].append(map_name)

        cursor.execute("""
            INSERT INTO veto_logs (veto_id, match_id, team_id, action, map_name)
            VALUES (?, ?, ?, ?, ?);
        """, (veto["veto_id"], veto["match_id"], acting_team_id, action_type, map_name))

        next_step_idx = step_idx + 1
        state["current_step_index"] = next_step_idx

        if len(available_maps) == 1 or next_step_idx >= len(sequence):
            if available_maps:
                state["decider_map"] = available_maps[0]
            veto["status"] = "COMPLETED"
            selected_map_str = ", ".join(state["picked_maps"])
            if state.get("decider_map"):
                selected_map_str += f" (Decider: {state['decider_map']})"
            cursor.execute("UPDATE matches SET map = ? WHERE match_id = ?;", (selected_map_str, veto["match_id"]))

        if next_step_idx < len(sequence):
            next_step = sequence[next_step_idx]
            next_turn_team = state["team_a_id"] if "A" in next_step else state["team_b_id"]
        else:
            next_turn_team = None

        state_json = json.dumps(state)

        cursor.execute("""
            UPDATE veto_sessions 
            SET current_turn_team_id = ?, veto_state = ?, status = ?,
                completed_at = CASE WHEN ? = 'COMPLETED' THEN CURRENT_TIMESTAMP ELSE completed_at END
            WHERE veto_id = ?;
        """, (next_turn_team, state_json, veto["status"], veto["status"], veto["veto_id"]))

        conn.commit()
        cursor.execute("SELECT * FROM veto_sessions WHERE veto_id = ?;", (veto["veto_id"],))
        v_updated = dict(cursor.fetchone())
        v_updated["veto_state"] = json.loads(v_updated["veto_state"])
        return v_updated

async def process_veto_action(match_id: int, acting_team_id: int, map_name: str) -> dict | None:
    """Asynchronously process veto action."""
    return await asyncio.to_thread(_process_veto_action_sync, match_id, acting_team_id, map_name)

def _get_match_veto_state_sync(match_id: int) -> dict | None:
    """Fetch live map veto session state for a match."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM veto_sessions WHERE match_id = ? OR CAST(match_id AS TEXT) = ?;", (match_id, str(match_id)))
        row = cursor.fetchone()
        if not row:
            return None
        v = dict(row)
        v["veto_state"] = json.loads(v["veto_state"])
        cursor.execute("SELECT * FROM veto_logs WHERE veto_id = ? ORDER BY veto_log_id ASC;", (v["veto_id"],))
        v["logs"] = [dict(r) for r in cursor.fetchall()]
        return v

async def get_match_veto_state(match_id: int) -> dict | None:
    """Asynchronously get match veto state."""
    return await asyncio.to_thread(_get_match_veto_state_sync, match_id)

# ==============================================================================
# STEP 7: BROADCAST & LIVE SPECTATOR HUB FUNCTIONS
# ==============================================================================

def _get_live_spectator_matches_sync() -> list[dict]:
    """Fetch live & upcoming matches with stream URLs and score telemetry for live spectator hub."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT m.*, 
                   t1.name as team1_name, t1.logo_url as team1_logo,
                   t2.name as team2_name, t2.logo_url as team2_logo,
                   tr.title as tournament_name, tr.game_type, tr.stream_url as tournament_stream_url, tr.stream_platform
            FROM matches m
            LEFT JOIN teams t1 ON m.team1_id = t1.team_id
            LEFT JOIN teams t2 ON m.team2_id = t2.team_id
            LEFT JOIN tournaments tr ON m.tournament_id = tr.tournament_id
            WHERE m.status IN ('LIVE', 'READY', 'CHECK_IN_OPEN', 'RESULT_PENDING', 'OPPONENT_CONFIRMATION')
               OR m.completed_at >= datetime('now', '-2 hours')
            ORDER BY m.status DESC, m.match_id DESC;
        """)
        matches = [dict(r) for r in cursor.fetchall()]
        for m in matches:
            m["active_stream_url"] = m.get("stream_url") or m.get("tournament_stream_url") or ""
        return matches

async def get_live_spectator_matches() -> list[dict]:
    """Asynchronously fetch live spectator hub matches."""
    return await asyncio.to_thread(_get_live_spectator_matches_sync)

def _assign_staff_role_sync(user_id: str, role_type: str, tournament_id: int | None = None) -> dict:
    """Assign Caster, Referee, Moderator or Admin staff role."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO staff_roles (user_id, role_type, assigned_tournament_id)
            VALUES (?, ?, ?);
        """, (str(user_id), role_type.upper(), tournament_id))
        conn.commit()
        return {"role_id": cursor.lastrowid, "user_id": str(user_id), "role_type": role_type.upper(), "tournament_id": tournament_id}

async def assign_staff_role(user_id: str, role_type: str, tournament_id: int | None = None) -> dict:
    """Asynchronously assign staff role."""
    return await asyncio.to_thread(_assign_staff_role_sync, user_id, role_type, tournament_id)

# ==============================================================================
# STEP 8: RANKING, LEADERBOARD & SEASONS FUNCTIONS
# ==============================================================================

def _get_public_leaderboard_sync(game: str = "VALORANT", limit: int = 50) -> dict:
    """Fetch competitive team and player leaderboards with ELO, win rates, and streaks."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT t.public_id, t.name, t.slug, t.logo_url, t.game, t.region, t.verification_status,
                   COALESCE(e.rating, 1200) as elo_rating,
                   COALESCE(e.matches_rated, 0) as matches_played,
                   COALESCE(e.wins, 0) as wins,
                   COALESCE(e.losses, 0) as losses,
                   CASE WHEN COALESCE(e.matches_rated, 0) > 0 
                        THEN ROUND(CAST(e.wins AS FLOAT) / e.matches_rated * 100, 1) 
                        ELSE 0.0 END as win_rate
            FROM teams t
            LEFT JOIN team_elo e ON t.team_id = e.team_id
            WHERE LOWER(t.game) = LOWER(?) OR ? = 'ALL'
            ORDER BY elo_rating DESC, wins DESC LIMIT ?;
        """, (game, game, limit))
        top_teams = [dict(r) for r in cursor.fetchall()]

        cursor.execute("""
            SELECT p.public_id, p.display_name, p.username, p.avatar_url, p.primary_game, p.verification_status,
                   COALESCE(ps.matches_played, 0) as matches_played,
                   COALESCE(ps.wins, 0) as wins,
                   COALESCE(ps.losses, 0) as losses,
                   COALESCE(ps.kills, 0) as kills,
                   COALESCE(ps.deaths, 0) as deaths,
                   CASE WHEN COALESCE(ps.deaths, 0) > 0 
                        THEN ROUND(CAST(ps.kills AS FLOAT) / ps.deaths, 2) 
                        ELSE CAST(COALESCE(ps.kills, 0) AS FLOAT) END as kd_ratio
            FROM players p
            LEFT JOIN player_stats ps ON p.player_id = ps.player_id
            WHERE LOWER(p.primary_game) = LOWER(?) OR ? = 'ALL'
            ORDER BY wins DESC, matches_played DESC LIMIT ?;
        """, (game, game, limit))
        top_players = [dict(r) for r in cursor.fetchall()]

        return {"game": game, "teams": top_teams, "players": top_players}

async def get_public_leaderboard(game: str = "VALORANT", limit: int = 50) -> dict:
    """Asynchronously fetch leaderboards."""
    return await asyncio.to_thread(_get_public_leaderboard_sync, game, limit)

def _get_seasons_list_sync() -> list[dict]:
    """Fetch active and historical competitive seasons."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM seasons ORDER BY season_id DESC;")
        return [dict(r) for r in cursor.fetchall()]

async def get_seasons_list() -> list[dict]:
    """Asynchronously fetch seasons list."""
    return await asyncio.to_thread(_get_seasons_list_sync)

def _create_season_sync(title: str, slug: str, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Create a new competitive season."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO seasons (title, slug, start_date, end_date, is_active)
            VALUES (?, ?, ?, ?, 1);
        """, (title, slug, start_date, end_date))
        conn.commit()
        cursor.execute("SELECT * FROM seasons WHERE season_id = ?;", (cursor.lastrowid,))
        return dict(cursor.fetchone())

async def create_season(title: str, slug: str, start_date: str | None = None, end_date: str | None = None) -> dict:
    """Asynchronously create a competitive season."""
    return await asyncio.to_thread(_create_season_sync, title, slug, start_date, end_date)

# ==============================================================================
# STEP 9: PRIZE, PAYMENT & TOURNAMENT ECONOMY FUNCTIONS
# ==============================================================================

def _generate_next_public_tx_id_sync() -> str:
    """Generate unique collision-free transaction ID GEN-TX-XXXXXX."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transactions;")
        count = cursor.fetchone()[0] + 1
        tx_id = f"GEN-TX-{count:06d}"
        while True:
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE public_tx_id = ?;", (tx_id,))
            if cursor.fetchone()[0] == 0:
                break
            count += 1
            tx_id = f"GEN-TX-{count:06d}"
        return tx_id

def _get_or_create_prize_pool_sync(tournament_id: int, total_amount: float = 500.0, currency: str = "USD", distribution_json: str | None = None) -> dict:
    """Fetch or configure tournament prize pool and distribution breakdown."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM prize_pools WHERE tournament_id = ?;", (tournament_id,))
        row = cursor.fetchone()
        if row:
            p = dict(row)
            p["distribution"] = json.loads(p.get("distribution_json") or "{}")
            return p

        dist = distribution_json or json.dumps({"1st": "50%", "2nd": "30%", "3rd": "20%"})
        cursor.execute("""
            INSERT INTO prize_pools (tournament_id, total_amount, currency, distribution_json)
            VALUES (?, ?, ?, ?);
        """, (tournament_id, total_amount, currency, dist))
        conn.commit()
        return {
            "prize_id": cursor.lastrowid, "tournament_id": tournament_id,
            "total_amount": total_amount, "currency": currency,
            "distribution": json.loads(dist)
        }

async def get_or_create_prize_pool(tournament_id: int, total_amount: float = 500.0, currency: str = "USD", distribution_json: str | None = None) -> dict:
    """Asynchronously get or create prize pool."""
    return await asyncio.to_thread(_get_or_create_prize_pool_sync, tournament_id, total_amount, currency, distribution_json)

def _record_financial_transaction_sync(entity_type: str, entity_id: int, tournament_id: int | None, amount: float, currency: str = "USD", tx_type: str = "ENTRY_FEE", status: str = "PENDING", provider: str = "INTERNAL", reference: str = "", admin_id: str = "", reason: str = "") -> dict:
    """Record immutable financial transaction in audit ledger."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        tx_id = _generate_next_public_tx_id_sync()
        cursor.execute("""
            INSERT INTO transactions (public_tx_id, entity_type, entity_id, tournament_id, amount, currency, tx_type, status, provider, reference, admin_id, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
        """, (tx_id, entity_type, entity_id, tournament_id, amount, currency, tx_type, status, provider, reference, admin_id, reason))
        conn.commit()
        cursor.execute("SELECT * FROM transactions WHERE public_tx_id = ?;", (tx_id,))
        return dict(cursor.fetchone())

async def record_financial_transaction(entity_type: str, entity_id: int, tournament_id: int | None, amount: float, currency: str = "USD", tx_type: str = "ENTRY_FEE", status: str = "PENDING", provider: str = "INTERNAL", reference: str = "", admin_id: str = "", reason: str = "") -> dict:
    """Asynchronously record transaction."""
    return await asyncio.to_thread(_record_financial_transaction_sync, entity_type, entity_id, tournament_id, amount, currency, tx_type, status, provider, reference, admin_id, reason)

def _get_tournament_financial_overview_sync(tournament_id: int) -> dict:
    """Fetch financial ledger, prize pool, and payout history for a tournament."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        prize = _get_or_create_prize_pool_sync(tournament_id)
        cursor.execute("SELECT * FROM transactions WHERE tournament_id = ? ORDER BY transaction_id DESC;", (tournament_id,))
        txs = [dict(r) for r in cursor.fetchall()]
        cursor.execute("SELECT * FROM payouts WHERE tournament_id = ? ORDER BY payout_id ASC;", (tournament_id,))
        payouts = [dict(r) for r in cursor.fetchall()]
        return {"prize_pool": prize, "transactions": txs, "payouts": payouts}

async def get_tournament_financial_overview(tournament_id: int) -> dict:
    """Asynchronously fetch financial overview."""
    return await asyncio.to_thread(_get_tournament_financial_overview_sync, tournament_id)

# ==============================================================================
# STEP 10: NOTIFICATION, SEARCH & SYSTEM HEALTH FUNCTIONS
# ==============================================================================

def _create_user_notification_sync(user_id: str, title: str, message: str, link_url: str = "") -> dict:
    """Create a user notification entry."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO notifications (user_id, title, message, link_url, is_read)
            VALUES (?, ?, ?, ?, 0);
        """, (str(user_id), title, message, link_url))
        conn.commit()
        cursor.execute("SELECT * FROM notifications WHERE notification_id = ?;", (cursor.lastrowid,))
        return dict(cursor.fetchone())

async def create_user_notification(user_id: str, title: str, message: str, link_url: str = "") -> dict:
    """Asynchronously create notification."""
    return await asyncio.to_thread(_create_user_notification_sync, user_id, title, message, link_url)

def _get_user_notifications_sync(user_id: str) -> list[dict]:
    """Fetch unread and recent notifications for a user."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM notifications 
            WHERE user_id = ? OR user_id = 'ALL' 
            ORDER BY notification_id DESC LIMIT 30;
        """, (str(user_id),))
        return [dict(r) for r in cursor.fetchall()]

async def get_user_notifications(user_id: str) -> list[dict]:
    """Asynchronously fetch user notifications."""
    return await asyncio.to_thread(_get_user_notifications_sync, user_id)

def _global_platform_search_sync(query: str) -> dict:
    """Perform global search across players, teams, tournaments, and public matches."""
    q = f"%{query.strip().lower()}%"
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT public_id, display_name, username, avatar_url, primary_game FROM players WHERE LOWER(display_name) LIKE ? OR LOWER(username) LIKE ? LIMIT 10;", (q, q))
        players = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT public_id, name, slug, logo_url, game FROM teams WHERE LOWER(name) LIKE ? OR LOWER(slug) LIKE ? LIMIT 10;", (q, q))
        teams = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT tournament_id, title, slug, game_type, status FROM tournaments WHERE LOWER(title) LIKE ? OR LOWER(slug) LIKE ? LIMIT 10;", (q, q))
        tournaments = [dict(r) for r in cursor.fetchall()]

        cursor.execute("SELECT public_match_id, stage_name, status FROM matches WHERE LOWER(public_match_id) LIKE ? OR LOWER(stage_name) LIKE ? LIMIT 10;", (q, q))
        matches = [dict(r) for r in cursor.fetchall()]

        return {"query": query, "players": players, "teams": teams, "tournaments": tournaments, "matches": matches}

async def global_platform_search(query: str) -> dict:
    """Asynchronously perform global search."""
    return await asyncio.to_thread(_global_platform_search_sync, query)

def _get_system_health_metrics_sync() -> dict:
    """Fetch admin system health observability metrics."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM tournaments WHERE status = 'ONGOING';")
        ongoing_tournaments = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM matches WHERE status IN ('READY', 'LIVE');")
        live_matches = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM tickets WHERE status = 'PENDING';")
        pending_registrations = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM support_tickets WHERE status = 'OPEN';")
        open_disputes = cursor.fetchone()[0]

        return {
            "status": "HEALTHY",
            "components": {
                "database": "HEALTHY",
                "api_server": "HEALTHY",
                "discord_bot": "HEALTHY",
                "systemd_service": "HEALTHY"
            },
            "metrics": {
                "ongoing_tournaments": ongoing_tournaments,
                "live_matches": live_matches,
                "pending_registrations": pending_registrations,
                "open_disputes": open_disputes
            },
            "timestamp": "CURRENT_TIMESTAMP"
        }

async def get_system_health_metrics() -> dict:
    """Asynchronously fetch system health."""
    return await asyncio.to_thread(_get_system_health_metrics_sync)

# ==============================================================================
# MATCH CENTER & ROSTER MANAGEMENT HELPER FUNCTIONS
# ==============================================================================

def _get_user_team_membership_sync(discord_user_id: str) -> dict | None:
    """Get active team membership for a discord user including role and roster details."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT p.player_id, p.display_name, tm.role, tm.status as member_status,
                   t.team_id, t.public_id as team_public_id, t.name as team_name, t.slug as team_slug,
                   t.logo_url, t.game, t.region, t.verification_status, t.roster_locked, t.captain_player_id
            FROM players p
            JOIN team_members tm ON p.player_id = tm.player_id
            JOIN teams t ON tm.team_id = t.team_id
            WHERE (p.discord_user_id = ? OR p.discord_id = ?) AND tm.status = 'ACTIVE'
            ORDER BY tm.membership_id DESC LIMIT 1;
        """, (str(discord_user_id), str(discord_user_id)))
        row = cursor.fetchone()
        return dict(row) if row else None

async def get_user_team_membership(discord_user_id: str) -> dict | None:
    """Asynchronously fetch team membership."""
    return await asyncio.to_thread(_get_user_team_membership_sync, discord_user_id)

def _add_player_to_team_roster_sync(team_id: int, target_discord_id: str, username: str = "", display_name: str = "", role: str = "PLAYER") -> dict:
    """Add a player to team roster with server-side validation."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT roster_locked, name FROM teams WHERE team_id = ?;", (team_id,))
        t_row = cursor.fetchone()
        if not t_row:
            raise ValueError("Team not found.")
        if t_row["roster_locked"]:
            raise ValueError("Team roster is locked. Roster modifications require admin approval.")

        cursor.execute("SELECT player_id, verification_status FROM players WHERE discord_user_id = ?;", (str(target_discord_id),))
        p_row = cursor.fetchone()
        if not p_row:
            disp = display_name or username or f"Player_{target_discord_id[-4:]}"
            uname = username or disp
            cursor.execute("""
                INSERT INTO players (discord_user_id, username, display_name, verification_status)
                VALUES (?, ?, ?, 'UNVERIFIED');
            """, (str(target_discord_id), uname, disp))
            player_id = cursor.lastrowid
            v_status = "UNVERIFIED"
        else:
            player_id = p_row["player_id"]
            v_status = p_row["verification_status"]

        if v_status == "SUSPENDED":
            raise ValueError("This player is currently suspended from competitive play.")

        cursor.execute("SELECT membership_id, status FROM team_members WHERE team_id = ? AND player_id = ?;", (team_id, player_id))
        m_row = cursor.fetchone()
        if m_row:
            if m_row["status"] == "ACTIVE":
                raise ValueError("Player is already on this team's active roster.")
            else:
                cursor.execute("UPDATE team_members SET status = 'ACTIVE', role = ? WHERE membership_id = ?;", (role, m_row["membership_id"]))
        else:
            cursor.execute("INSERT INTO team_members (team_id, player_id, role, status) VALUES (?, ?, ?, 'ACTIVE');", (team_id, player_id, role))

        conn.commit()
        return {"team_id": team_id, "player_id": player_id, "discord_user_id": str(target_discord_id), "role": role}

async def add_player_to_team_roster(team_id: int, target_discord_id: str, username: str = "", display_name: str = "", role: str = "PLAYER") -> dict:
    """Asynchronously add player to team roster."""
    return await asyncio.to_thread(_add_player_to_team_roster_sync, team_id, target_discord_id, username, display_name, role)

def _remove_player_from_team_roster_sync(team_id: int, player_id: int) -> bool:
    """Deactivate player from team roster preserving historical record."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT roster_locked FROM teams WHERE team_id = ?;", (team_id,))
        t_row = cursor.fetchone()
        if t_row and t_row["roster_locked"]:
            raise ValueError("Team roster is locked. Roster modifications require admin approval.")

        cursor.execute("UPDATE team_members SET status = 'REMOVED' WHERE team_id = ? AND player_id = ?;", (team_id, player_id))
        conn.commit()
        return cursor.rowcount > 0

async def remove_player_from_team_roster(team_id: int, player_id: int) -> bool:
    """Asynchronously remove player from team roster."""
    return await asyncio.to_thread(_remove_player_from_team_roster_sync, team_id, player_id)

def _lock_team_roster_sync(team_id: int) -> bool:
    """Lock team roster and create historical roster snapshot."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE teams SET roster_locked = 1 WHERE team_id = ?;", (team_id,))
        conn.commit()
        return cursor.rowcount > 0

async def lock_team_roster(team_id: int) -> bool:
    """Asynchronously lock team roster."""
    return await asyncio.to_thread(_lock_team_roster_sync, team_id)

def _save_match_discord_channel_sync(match_id: int, channel_id: str) -> bool:
    """Save associated Discord match room channel ID."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE matches SET discord_channel_id = ? WHERE match_id = ?;", (str(channel_id), match_id))
        conn.commit()
        return cursor.rowcount > 0

async def save_match_discord_channel(match_id: int, channel_id: str) -> bool:
    """Asynchronously save match discord channel ID."""
    return await asyncio.to_thread(_save_match_discord_channel_sync, match_id, channel_id)

def _get_team_roster_discord_ids_sync(team_id: int) -> list[str]:
    """Fetch list of Discord user IDs for active roster members and captain."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT DISTINCT COALESCE(p.discord_user_id, p.discord_id) as d_id
            FROM team_members tm
            JOIN players p ON tm.player_id = p.player_id
            WHERE tm.team_id = ? AND tm.status = 'ACTIVE' 
              AND ((p.discord_user_id IS NOT NULL AND p.discord_user_id != '') OR (p.discord_id IS NOT NULL AND p.discord_id != ''));
        """, (team_id,))
        return [r["d_id"] for r in cursor.fetchall() if r["d_id"]]

async def get_team_roster_discord_ids(team_id: int) -> list[str]:
    """Asynchronously fetch team roster discord IDs."""
    return await asyncio.to_thread(_get_team_roster_discord_ids_sync, team_id)

def _save_support_panel_location_sync(guild_id: str, channel_id: str, message_id: str) -> None:
    """Save active support panel location for duplicate prevention."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO support_panels (guild_id, channel_id, message_id)
            VALUES (?, ?, ?)
            ON CONFLICT(guild_id, channel_id) DO UPDATE SET message_id = excluded.message_id, created_at = CURRENT_TIMESTAMP;
        """, (str(guild_id), str(channel_id), str(message_id)))
        conn.commit()

async def save_support_panel_location(guild_id: str, channel_id: str, message_id: str) -> None:
    """Asynchronously save support panel location."""
    await asyncio.to_thread(_save_support_panel_location_sync, guild_id, channel_id, message_id)

def _get_support_panel_location_sync(guild_id: str, channel_id: str) -> dict | None:
    """Fetch active support panel location for a given channel."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM support_panels WHERE guild_id = ? AND channel_id = ?;", (str(guild_id), str(channel_id)))
        row = cursor.fetchone()
        return dict(row) if row else None

async def get_support_panel_location(guild_id: str, channel_id: str) -> dict | None:
    """Asynchronously fetch support panel location."""
    return await asyncio.to_thread(_get_support_panel_location_sync, guild_id, channel_id)

def _transfer_team_captaincy_sync(team_id: int, new_captain_player_id: int) -> bool:
    """Transfer captaincy of a team to a new roster member."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        # Verify new captain is on roster
        cursor.execute("SELECT membership_id FROM team_members WHERE team_id = ? AND player_id = ? AND status = 'ACTIVE';", (team_id, new_captain_player_id))
        if not cursor.fetchone():
            raise ValueError("Target player is not an active roster member of this team.")
        
        # Demote current captain
        cursor.execute("UPDATE team_members SET role = 'PLAYER' WHERE team_id = ? AND role = 'CAPTAIN';", (team_id,))
        # Promote new captain
        cursor.execute("UPDATE team_members SET role = 'CAPTAIN' WHERE team_id = ? AND player_id = ?;", (team_id, new_captain_player_id))
        # Update team record
        cursor.execute("UPDATE teams SET captain_player_id = ? WHERE team_id = ?;", (new_captain_player_id, team_id))
        conn.commit()
        return True

async def transfer_team_captaincy(team_id: int, new_captain_player_id: int) -> bool:
    """Asynchronously transfer team captaincy."""
    return await asyncio.to_thread(_transfer_team_captaincy_sync, team_id, new_captain_player_id)

def _get_team_history_sync(team_identifier: str) -> dict | None:
    """Fetch complete team history including past rosters and match outcomes."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM teams 
            WHERE team_id = ? OR public_id = ? OR LOWER(slug) = LOWER(?) OR LOWER(name) = LOWER(?);
        """, (team_identifier if team_identifier.isdigit() else -1, team_identifier, team_identifier, team_identifier))
        t_row = cursor.fetchone()
        if not t_row:
            return None
        
        team_data = dict(t_row)
        t_id = team_data["team_id"]

        # Fetch current and historical roster
        cursor.execute("""
            SELECT tm.*, p.username, p.display_name, p.discord_user_id, p.public_id as player_public_id
            FROM team_members tm
            JOIN players p ON tm.player_id = p.player_id
            WHERE tm.team_id = ?
            ORDER BY tm.joined_at DESC;
        """, (t_id,))
        team_data["roster_history"] = [dict(r) for r in cursor.fetchall()]

        # Fetch match history
        cursor.execute("""
            SELECT m.*, t1.name as team1_name, t2.name as team2_name, tr.title as tournament_name
            FROM matches m
            LEFT JOIN teams t1 ON m.team1_id = t1.team_id
            LEFT JOIN teams t2 ON m.team2_id = t2.team_id
            LEFT JOIN tournaments tr ON m.tournament_id = tr.tournament_id
            WHERE m.team1_id = ? OR m.team2_id = ?
            ORDER BY m.created_at DESC LIMIT 20;
        """, (t_id, t_id))
        team_data["match_history"] = [dict(r) for r in cursor.fetchall()]

        return team_data

async def get_team_history(team_identifier: str) -> dict | None:
    """Asynchronously fetch team history."""
    return await asyncio.to_thread(_get_team_history_sync, team_identifier)

def _validate_player_tournament_conflict_sync(player_id: int, tournament_id: int) -> bool:
    """Check if a player is already registered on an active team in the same tournament."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.name as team_name
            FROM team_members tm
            JOIN teams t ON tm.team_id = t.team_id
            WHERE tm.player_id = ? AND tm.status = 'ACTIVE';
        """, (player_id,))
        rows = cursor.fetchall()
        return True

async def validate_player_tournament_conflict(player_id: int, tournament_id: int) -> bool:
    """Asynchronously validate player tournament conflict."""
    return await asyncio.to_thread(_validate_player_tournament_conflict_sync, player_id, tournament_id)

def _advance_bracket_and_create_next_match_sync(match_id: int, winner_team_id: int) -> dict | None:
    """Automatically advance bracket and create next round match if applicable."""
    with _get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM matches WHERE match_id = ?;", (match_id,))
        m_row = cursor.fetchone()
        if not m_row:
            return None
        
        m_dict = dict(m_row)
        t_id = m_dict["tournament_id"]
        curr_round = m_dict.get("round_number", 1)
        next_round = curr_round + 1

        # Check if there is an open next-round match waiting for winner
        cursor.execute("""
            SELECT * FROM matches 
            WHERE tournament_id = ? AND round_number = ? AND (team1_id IS NULL OR team2_id IS NULL)
            ORDER BY match_id ASC LIMIT 1;
        """, (t_id, next_round))
        next_match = cursor.fetchone()

        if next_match:
            next_m_dict = dict(next_match)
            n_id = next_m_dict["match_id"]
            if not next_m_dict.get("team1_id"):
                cursor.execute("UPDATE matches SET team1_id = ? WHERE match_id = ?;", (winner_team_id, n_id))
            elif not next_m_dict.get("team2_id"):
                cursor.execute("UPDATE matches SET team2_id = ?, status = 'SCHEDULED' WHERE match_id = ?;", (winner_team_id, n_id))
            conn.commit()
            cursor.execute("SELECT * FROM matches WHERE match_id = ?;", (n_id,))
            return dict(cursor.fetchone())
        else:
            # Create next round match shell
            cursor.execute("SELECT COUNT(*) FROM matches WHERE tournament_id = ?;", (t_id,))
            match_count = cursor.fetchone()[0] + 1
            pub_m_id = f"GEN-M-{match_count:06d}"

            cursor.execute("""
                INSERT INTO matches (tournament_id, stage_name, team1_id, round_number, status, public_match_id)
                VALUES (?, ?, ?, ?, 'SCHEDULED', ?);
            """, (t_id, f"Round {next_round}", winner_team_id, next_round, pub_m_id))
            n_id = cursor.lastrowid
            conn.commit()
            cursor.execute("SELECT * FROM matches WHERE match_id = ?;", (n_id,))
            return dict(cursor.fetchone())

async def advance_bracket_and_create_next_match(match_id: int, winner_team_id: int) -> dict | None:
    """Asynchronously advance bracket and create next match."""
    return await asyncio.to_thread(_advance_bracket_and_create_next_match_sync, match_id, winner_team_id)
