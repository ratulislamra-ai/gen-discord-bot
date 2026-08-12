#!/usr/bin/env python3
"""
Automated SQLite Database Backup Script for GEN Esports Discord Bot.

Uses SQLite's online backup API (conn.backup) to safely create a consistent
timestamped copy of tournament.db without locking the live database or corrupting data.
"""

import os
import sys
import sqlite3
import datetime
import logging

# Ensure project root is in python path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from config.settings import DB_PATH

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] backup_db: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("DBBackup")

def backup_database(max_backups: int = 30) -> str:
    """
    Perform safe online backup of SQLite database and prune old backups.
    """
    db_file = os.path.abspath(DB_PATH)
    if not os.path.exists(db_file):
        logger.error(f"Source database file not found at: {db_file}")
        sys.exit(1)

    backup_dir = os.path.join(PROJECT_ROOT, "backups")
    os.makedirs(backup_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"tournament_backup_{timestamp}.db"
    backup_path = os.path.join(backup_dir, backup_filename)

    logger.info(f"Starting online backup of {db_file} -> {backup_path}")

    try:
        source_conn = sqlite3.connect(db_file)
        dest_conn = sqlite3.connect(backup_path)

        with dest_conn:
            source_conn.backup(dest_conn)

        dest_conn.close()
        source_conn.close()

        file_size_kb = round(os.path.getsize(backup_path) / 1024, 2)
        logger.info(f"✅ Backup created successfully: {backup_filename} ({file_size_kb} KB)")

        # Prune old backups exceeding max_backups count
        existing_backups = sorted([
            os.path.join(backup_dir, f) for f in os.listdir(backup_dir)
            if f.startswith("tournament_backup_") and f.endswith(".db")
        ], key=os.path.getmtime)

        if len(existing_backups) > max_backups:
            to_remove = existing_backups[:-max_backups]
            for old_backup in to_remove:
                os.remove(old_backup)
                logger.info(f"Pruned older backup: {os.path.basename(old_backup)}")

        return backup_path

    except Exception as e:
        logger.critical(f"❌ Failed to backup database: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    backup_database()
