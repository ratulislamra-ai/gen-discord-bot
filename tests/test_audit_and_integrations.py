import unittest
import asyncio
import os
import sys

# Ensure project root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from database.db import (
    _init_db_sync,
    _get_connection,
    create_role_request,
    get_role_request,
    update_role_request_status,
    track_temporary_channel,
    mark_channel_cleanup_eligible,
    get_eligible_cleanup_channels,
    update_channel_cleanup_status,
    advance_bracket_and_create_next_match
)

class TestAuditAndIntegrations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        _init_db_sync()

    def run_async(self, coro):
        return asyncio.run(coro)

    def test_01_role_request_creation_and_approval_flow(self):
        """Test creating a role request, preventing duplicate pending requests, and updating approval status."""
        guild_id = "111222333"
        user_id = "444555666"
        role_id = "999888"
        role_name = "Player"

        # Create request
        success, req_id, msg = self.run_async(create_role_request(guild_id, user_id, role_id, role_name))
        self.assertTrue(success)
        self.assertIsNotNone(req_id)
        self.assertIn("submitted", msg)

        # Duplicate pending request should fail
        success2, req_id2, msg2 = self.run_async(create_role_request(guild_id, user_id, role_id, role_name))
        self.assertFalse(success2)
        self.assertIn("already have a pending", msg2)

        # Fetch request details
        req = self.run_async(get_role_request(req_id))
        self.assertIsNotNone(req)
        self.assertEqual(req["status"], "PENDING")
        self.assertEqual(req["requested_role_name"], role_name)

        # Approve request
        updated = self.run_async(update_role_request_status(req_id, "APPROVED", "admin_777"))
        self.assertTrue(updated)

        req_after = self.run_async(get_role_request(req_id))
        self.assertEqual(req_after["status"], "APPROVED")
        self.assertEqual(req_after["reviewed_by"], "admin_777")

    def test_02_temporary_channel_lifecycle_and_cleanup(self):
        """Test tracking temporary channels, marking eligible for cleanup, and updating deletion status."""
        channel_id = "9876543210"
        guild_id = "111222333"

        # Track channel
        tracked = self.run_async(track_temporary_channel(channel_id, guild_id, "MATCH_ROOM", related_match_id=101))
        self.assertTrue(tracked)

        # Mark cleanup eligible
        eligible = self.run_async(mark_channel_cleanup_eligible(channel_id))
        self.assertTrue(eligible)

        # Fetch eligible cleanup list
        cleanup_list = self.run_async(get_eligible_cleanup_channels("MATCH_ROOM"))
        matching = [c for c in cleanup_list if c["channel_id"] == channel_id]
        self.assertEqual(len(matching), 1)

        # Update to DELETED status
        updated = self.run_async(update_channel_cleanup_status(channel_id, "DELETED"))
        self.assertTrue(updated)

        cleanup_list_after = self.run_async(get_eligible_cleanup_channels("MATCH_ROOM"))
        matching_after = [c for c in cleanup_list_after if c["channel_id"] == channel_id]
        self.assertEqual(len(matching_after), 0)

    def test_03_bracket_advancement_and_next_round_creation(self):
        """Test automatic winner advancement to next round shell."""
        with _get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM matches WHERE tournament_id = 999;")
            cursor.execute("DELETE FROM tournaments WHERE tournament_id = 999;")
            cursor.execute("""
                INSERT INTO tournaments (tournament_id, slug, title, game_type, status, max_teams)
                VALUES (999, 'test-adv-tourn', 'Test Advancement Tournament', 'VALORANT', 'ONGOING', 8);
            """)
            cursor.execute("""
                INSERT INTO matches (match_id, tournament_id, stage_name, team1_id, team2_id, status, round_number, public_match_id)
                VALUES (801, 999, 'Quarterfinals', 50, 51, 'COMPLETED', 1, 'GEN-M-000801');
            """)
            conn.commit()

        next_m = self.run_async(advance_bracket_and_create_next_match(801, 50))
        self.assertIsNotNone(next_m)
        self.assertEqual(next_m["tournament_id"], 999)
        self.assertEqual(next_m["team1_id"], 50)
        self.assertEqual(next_m["round_number"], 2)


if __name__ == "__main__":
    unittest.main()
