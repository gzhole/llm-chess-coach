# database.py

import sqlite3
import os

# Default database path, can be overridden for tests
DB_PATH = 'chess_coach.db'

class Database:
    """
    Handles all database operations for the chess coach.
    """
    def __init__(self, db_path=None):
        """
        Initializes the database connection.
        If no path is provided, it uses the default DB_PATH.
        """
        if db_path is None:
            db_path = DB_PATH
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """Establishes a connection to the database."""
        try:
            # Allow the connection to be used across multiple threads, which is necessary for FastAPI.
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            # Use Row factory to access columns by name
            self.conn.row_factory = sqlite3.Row
        except sqlite3.Error as e:
            print(f"Database connection error: {e}")
            raise

    def close(self):
        """Closes the database connection."""
        if self.conn:
            self.conn.close()

    def init_db(self):
        """
        Initializes the database schema by creating the necessary tables
        if they don't already exist. The connection is not closed here.
        """
        if not self.conn:
            self.connect()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS blunders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_pgn_path TEXT NOT NULL,
                move_number INTEGER NOT NULL,
                player_color TEXT NOT NULL,
                move_san TEXT NOT NULL,
                position_fen TEXT NOT NULL,
                eval_drop INTEGER NOT NULL,
                best_move_san TEXT NOT NULL,
                coach_comment TEXT,
                mistake_tag TEXT,
                analysis_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error initializing database: {e}")

    def save_blunder(self, pgn_path, move_number, player_color, move_san, position_fen, eval_drop, best_move_san, coach_comment, mistake_tag):
        """
        Saves a detected blunder to the database.
        """
        if not self.conn:
            self.connect()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
            INSERT INTO blunders (game_pgn_path, move_number, player_color, move_san, position_fen, eval_drop, best_move_san, coach_comment, mistake_tag)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (pgn_path, move_number, player_color, move_san, position_fen, eval_drop, best_move_san, coach_comment, mistake_tag))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error saving blunder to database: {e}")

    def get_blunders_by_pgn_path(self, pgn_path: str) -> list:
        """
        Retrieves all blunder records for a specific PGN file.
        """
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM blunders WHERE game_pgn_path = ? ORDER BY move_number ASC", (pgn_path,))
            blunders = cursor.fetchall()
            # Convert Row objects to dictionaries for JSON serialization
            return [dict(blunder) for blunder in blunders]
        except sqlite3.Error as e:
            print(f"Error fetching blunders from database: {e}")
            return []

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Closes the connection upon exiting the context."""
        self.close()
