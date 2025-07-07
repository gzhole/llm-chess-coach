# coach.py
"""
Chess game analyzer that identifies blunders and provides coaching feedback.

This module provides a CLI interface for analyzing chess games using Stockfish
and LLM-based coaching to help players improve their game.
"""

import os
import argparse
import chess.pgn
import tempfile
from pathlib import Path
from database import Database
from core.analysis import StockfishAnalyzer, LLMCoach, GameProcessor

# --- Constants ---
STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "D:/stockfish/stockfish-windows-x86-64-avx2.exe")

BLUNDER_THRESHOLD = 150  # Minimum centipawn loss to be considered a significant mistake
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")  # The Ollama model to use for analysis
SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(__file__), "prompts", "system_prompt.txt")

def main():
    """Main function to run the analysis from the command line."""
    parser = argparse.ArgumentParser(description="Analyzes a chess game to identify blunders and provide coaching feedback.")
    parser.add_argument("pgn_file", help="Path to the PGN file to analyze.")
    parser.add_argument("--side", choices=['white', 'black', 'both'], default='both', 
                       help="The side to analyze (white, black, or both). Default is both.")
    parser.add_argument("--output", help="Optional path to save the annotated PGN file.")
    args = parser.parse_args()

    # Initialize components
    db = Database()
    
    try:
        analyzer = StockfishAnalyzer(stockfish_path=STOCKFISH_PATH)
        coach = LLMCoach(model=OLLAMA_MODEL, system_prompt_path=SYSTEM_PROMPT_PATH)
        processor = GameProcessor(analyzer, coach, db, BLUNDER_THRESHOLD)
        
        # Analyze the game and get the annotated version
        annotated_game = processor.analyze_game(args.pgn_file, args.side)

        # Export the annotated game if requested
        if args.output:
            with open(args.output, "w", encoding="utf-8") as f:
                exporter = chess.pgn.FileExporter(f)
                annotated_game.accept(exporter)
            print(f"\nAnnotated game saved to {args.output}")

    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"An error occurred during analysis: {e}")
    finally:
        # Clean up resources
        db.close()
        if 'analyzer' in locals():
            analyzer.close()

def analyze_pgn_string(pgn_content: str) -> list:
    """
    Analyzes a PGN string by saving it to a temporary file and running the analysis.
    
    Args:
        pgn_content: A string containing the PGN data.
        
    Returns:
        A list of dictionaries, where each dictionary represents a blunder.
    """
    # Create a temporary file to store the PGN content
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pgn', encoding='utf-8') as tmp_file:
        tmp_file.write(pgn_content)
        tmp_file_path = tmp_file.name

    try:
        # Initialize components
        db = Database()
        analyzer = StockfishAnalyzer(stockfish_path=STOCKFISH_PATH)
        coach = LLMCoach(model=OLLAMA_MODEL, system_prompt_path=SYSTEM_PROMPT_PATH)
        processor = GameProcessor(analyzer, coach, db, BLUNDER_THRESHOLD)
        
        # Analyze the game
        processor.analyze_game(tmp_file_path)
        
        # Retrieve the results from the database
        results = db.get_blunders_by_pgn_path(tmp_file_path)
        return results
        
    finally:
        # Clean up resources
        if 'db' in locals():
            db.close()
        if 'analyzer' in locals():
            analyzer.close()
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)

if __name__ == "__main__":
    main()