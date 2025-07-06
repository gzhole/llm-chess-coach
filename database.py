# database.py

import sqlite3
import os

class Database:
    """
    Handles all database operations for the chess coach.
    """
    def __init__(self, db_path='chess_coach.db'):
        """
        Initializes the database connection.

        Args:
            db_path: The path to the SQLite database file.
        """
        self.db_path = db_path
        self.conn = None

    def connect(self):
        """Establishes a connection to the database."""
        try:
            self.conn = sqlite3.connect(self.db_path)
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
        if they don't already exist.
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
                analysis_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """)
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error initializing database: {e}")
        finally:
            self.close()

    def save_blunder(self, pgn_path, move_number, player_color, move_san, position_fen, eval_drop, best_move_san, coach_comment):
        """
        Saves a detected blunder to the database.
        """
        if not self.conn:
            self.connect()
        
        try:
            cursor = self.conn.cursor()
            cursor.execute("""
            INSERT INTO blunders (game_pgn_path, move_number, player_color, move_san, position_fen, eval_drop, best_move_san, coach_comment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (pgn_path, move_number, player_color, move_san, position_fen, eval_drop, best_move_san, coach_comment))
            self.conn.commit()
        except sqlite3.Error as e:
            print(f"Error saving blunder to database: {e}")

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
