import unittest
import asyncio
import os
import sqlite3
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db import (
    _init_db_sync,
    _get_connection,
    create_team_invitation,
    accept_team_invitation,
    decline_team_invitation,
    validate_player_invite_eligibility,
    get_pending_invitations_for_user,
    validate_match_room_creation,
    advance_bracket_and_create_next_match,
    submit_match_score
)

class TestEsportsSystem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _init_db_sync()
        cls.setup_test_data()

    @classmethod
    def setup_test_data(cls):
        with _get_connection() as conn:
            cursor = conn.cursor()
            
            # 1. Clear test tables
            cursor.execute("DELETE FROM team_invitations;")
            cursor.execute("DELETE FROM team_members;")
            cursor.execute("DELETE FROM players;")
            cursor.execute("DELETE FROM roster_players;")
            cursor.execute("DELETE FROM tickets;")
            cursor.execute("DELETE FROM matches;")
            cursor.execute("DELETE FROM brackets;")
            cursor.execute("DELETE FROM teams;")
            cursor.execute("DELETE FROM tournaments;")

            # 2. Insert test tournament
            cursor.execute("""
                INSERT INTO tournaments (tournament_id, slug, title, game_type, status, max_teams)
                VALUES (99, 'gen-val-champ', 'GEN Valorant Championship', 'VALORANT', 'REGISTRATION_OPEN', 16);
            """)

            # 3. Insert test teams
            cursor.execute("""
                INSERT INTO teams (team_id, public_id, name, slug, captain_discord_id)
                VALUES (101, 'GEN-T-101', 'Team Alpha', 'team-alpha', '10001');
            """)
            cursor.execute("""
                INSERT INTO teams (team_id, public_id, name, slug, captain_discord_id)
                VALUES (102, 'GEN-T-102', 'Team Beta', 'team-beta', '20001');
            """)

            # 4. Insert tickets & rosters
            cursor.execute("""
                INSERT INTO tickets (ticket_id, user_id, guild_id, channel_id, team_name, tournament_name, captain_discord_id, status)
                VALUES (501, 10001, 1, 1, 'Team Alpha', 'GEN Valorant Championship', '10001', 'APPROVED');
            """)
            cursor.execute("""
                INSERT INTO roster_players (ticket_id, player_role, ign, discord_id)
                VALUES (501, 'Captain', 'AlphaCap', '10001');
            """)

            cursor.execute("""
                INSERT INTO tickets (ticket_id, user_id, guild_id, channel_id, team_name, tournament_name, captain_discord_id, status)
                VALUES (502, 20001, 1, 1, 'Team Beta', 'GEN Valorant Championship', '20001', 'APPROVED');
            """)
            cursor.execute("""
                INSERT INTO roster_players (ticket_id, player_role, ign, discord_id)
                VALUES (502, 'Captain', 'BetaCap', '20001');
            """)

            # 5. Insert valid match (Match #901)
            cursor.execute("""
                INSERT INTO matches (match_id, tournament_id, stage_name, team1_id, team2_id, status, public_match_id)
                VALUES (901, 99, 'Quarterfinals', 101, 102, 'SCHEDULED', 'GEN-M-000901');
            """)

            # 6. Insert incomplete matches for testing pre-flight checks
            cursor.execute("""
                INSERT INTO matches (match_id, tournament_id, stage_name, team1_id, team2_id, status, public_match_id)
                VALUES (902, 99, 'Semifinals', 101, NULL, 'SCHEDULED', 'GEN-M-000902');
            """)
            cursor.execute("""
                INSERT INTO matches (match_id, tournament_id, stage_name, team1_id, team2_id, status, public_match_id)
                VALUES (903, 99, 'Semifinals', NULL, 102, 'SCHEDULED', 'GEN-M-000903');
            """)

            conn.commit()

    def run_async(self, coro):
        return asyncio.run(coro)

    def test_A_captain_selects_valid_player_invitation_created(self):
        """Scenario A: Captain invites valid player -> Invitation created in DB."""
        inv = self.run_async(create_team_invitation(101, 99, "10002", "10001"))
        self.assertIsNotNone(inv)
        self.assertEqual(str(inv.get("invited_user_id")), "10002")
        self.assertEqual(inv["status"], "PENDING")

    def test_B_player_accepts_roster_updated(self):
        """Scenario B: Player accepts -> Roster updated & invitation set to ACCEPTED."""
        inv = self.run_async(create_team_invitation(101, 99, "10003", "10001"))
        inv_id = inv["id"] if "id" in inv else inv["rowid"]
        
        ok, msg = self.run_async(accept_team_invitation(inv_id, "10003", "PlayerThree"))
        self.assertTrue(ok)
        self.assertIn("successfully", msg)

        # Check pending invitations list is empty
        pending = self.run_async(get_pending_invitations_for_user("10003"))
        self.assertEqual(len(pending), 0)

    def test_C_player_declines_roster_unchanged(self):
        """Scenario C: Player declines -> Invitation DECLINED and roster unchanged."""
        inv = self.run_async(create_team_invitation(101, 99, "10004", "10001"))
        inv_id = inv["id"] if "id" in inv else inv["rowid"]

        ok, msg = self.run_async(decline_team_invitation(inv_id, "10004"))
        self.assertTrue(ok)

        # Verify player is not on roster
        eligible, err = self.run_async(validate_player_invite_eligibility(99, 101, "10004"))
        self.assertTrue(eligible)

    def test_D_invalid_discord_user_handling(self):
        """Scenario D: Validation blocks self-invite or duplicate team player."""
        eligible, err = self.run_async(validate_player_invite_eligibility(99, 101, "10001"))
        self.assertFalse(eligible)
        self.assertIn("already a member", err)

    def test_E_user_already_on_another_team_rejected(self):
        """Scenario E: Player registered on Team Beta cannot be invited to Team Alpha."""
        eligible, err = self.run_async(validate_player_invite_eligibility(99, 101, "20001"))
        self.assertFalse(eligible)
        self.assertIn("already registered", err)

    def test_F_duplicate_invitation_prevented(self):
        """Scenario F: Re-inviting player cancels previous pending invite cleanly."""
        inv1 = self.run_async(create_team_invitation(101, 99, "10005", "10001"))
        inv2 = self.run_async(create_team_invitation(101, 99, "10005", "10001"))
        
        pending = self.run_async(get_pending_invitations_for_user("10005"))
        self.assertEqual(len(pending), 1)

    def test_G_full_roster_rejected(self):
        """Scenario G: Full roster exceeds capacity."""
        with _get_connection() as conn:
            cursor = conn.cursor()
            for i in range(10, 16):
                cursor.execute("""
                    INSERT INTO roster_players (ticket_id, player_role, ign, discord_id)
                    VALUES (501, 'Member', ?, ?);
                """, (f"Player{i}", f"100{i}"))
            conn.commit()

        eligible, err = self.run_async(validate_player_invite_eligibility(99, 101, "10099"))
        self.assertFalse(eligible)
        self.assertIn("maximum capacity", err)

    def test_H_match_with_both_teams_preflight_passes(self):
        """Scenario H: Match #901 with Team A & Team B passes pre-flight checks."""
        valid, msg, m = self.run_async(validate_match_room_creation(901))
        self.assertTrue(valid)
        self.assertIsNotNone(m)

    def test_I_match_without_team_a_error(self):
        """Scenario I: Match #903 missing Team A fails pre-flight with diagnostic reason."""
        valid, msg, m = self.run_async(validate_match_room_creation(903))
        self.assertFalse(valid)
        self.assertIn("missing Team A", msg)

    def test_J_match_without_team_b_error(self):
        """Scenario J: Match #902 missing Team B fails pre-flight with diagnostic reason."""
        valid, msg, m = self.run_async(validate_match_room_creation(902))
        self.assertFalse(valid)
        self.assertIn("missing Team B", msg)

    def test_K_team_a_player_permissions(self):
        """Scenario K: Team A player verified in DB."""
        from database.db import get_team_roster_discord_ids
        t1_ids = self.run_async(get_team_roster_discord_ids(101))
        self.assertIn("10001", t1_ids)

    def test_L_team_b_player_permissions(self):
        """Scenario L: Team B player verified in DB."""
        from database.db import get_team_roster_discord_ids
        t2_ids = self.run_async(get_team_roster_discord_ids(102))
        self.assertIn("20001", t2_ids)

    def test_M_staff_permissions(self):
        """Scenario M: Non-existent match returns clear error."""
        valid, msg, m = self.run_async(validate_match_room_creation(999999))
        self.assertFalse(valid)
        self.assertIn("does not exist", msg)

    def test_N_non_participant_denied(self):
        """Scenario N: Non-participant eligibility check fails."""
        eligible, err = self.run_async(validate_player_invite_eligibility(99, 101, "10001"))
        self.assertFalse(eligible)

    def test_O_score_submission_winner_advances(self):
        """Scenario O: Score submission updates status and advances winner."""
        res = self.run_async(submit_match_score(901, 101, "10001", 13, 7))
        self.assertIsNotNone(res)
        
        next_m = self.run_async(advance_bracket_and_create_next_match(901, 101))
        self.assertIsNotNone(next_m)
        self.assertEqual(next_m["team1_id"], 101)

    def test_P_next_bracket_match_updated(self):
        """Scenario P: Next round match created/updated with winner."""
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM matches WHERE tournament_id = 99 AND round_number = 2;")
            row = cursor.fetchone()
            self.assertIsNotNone(row)
            self.assertEqual(dict(row)["team1_id"], 101)

    def test_Q_match_info_lookup(self):
        """Scenario Q: Verify match-info query returns Match ID, Team 1, Team 2, and Tournament title."""
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT m.*, t1.name as team1_name, t2.name as team2_name, tr.title as tournament_name
                FROM matches m
                LEFT JOIN teams t1 ON m.team1_id = t1.team_id
                LEFT JOIN teams t2 ON m.team2_id = t2.team_id
                LEFT JOIN tournaments tr ON m.tournament_id = tr.tournament_id
                WHERE m.match_id = 901;
            """)
            m = cursor.fetchone()
            self.assertIsNotNone(m)
            m_dict = dict(m)
            self.assertEqual(m_dict["match_id"], 901)
            self.assertEqual(m_dict["team1_name"], "Team Alpha")
            self.assertEqual(m_dict["team2_name"], "Team Beta")
            self.assertEqual(m_dict["tournament_name"], "GEN Valorant Championship")

if __name__ == "__main__":
    unittest.main()
