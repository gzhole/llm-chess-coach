# coach.py

import chess
import chess.pgn
import ollama
from stockfish import Stockfish
import argparse
import os

# --- Configuration ---
# TODO: Update this path to your Stockfish executable
# You can download it from https://stockfishchess.org/download/
STOCKFISH_PATH = "D:/stockfish/stockfish-windows-x86-64-avx2.exe"

# Blunder threshold in centipawns. A drop of 150 is a significant mistake.
BLUNDER_THRESHOLD = 150 

# The name of the Ollama model to use for analysis
# OLLAMA_MODEL = 'llama3.2:1b'
OLLAMA_MODEL = 'deepseek-r1:1.5b'

def get_stockfish_evaluation(stockfish: Stockfish, board: chess.Board) -> int:
    """
    Gets the Stockfish evaluation for a given board position.
    
    Args:
        stockfish: An initialized Stockfish instance.
        board: A chess.Board object representing the position.
        
    Returns:
        The evaluation in centipawns. Positive is good for white, negative for black.
    """
    stockfish.set_fen_position(board.fen())
    eval_result = stockfish.get_evaluation()
    
    # The evaluation result is a dictionary, e.g., {'type': 'cp', 'value': 21}
    # We handle cases where there might be a mate score.
    if eval_result['type'] == 'cp':
        return eval_result['value']
    elif eval_result['type'] == 'mate':
        # Assign a very high score for mate to ensure it's treated as decisive
        return 10000 if eval_result['value'] > 0 else -10000
    return 0

def get_llm_analysis(position_fen: str, player_color: str, mistake: str, best_move: str) -> str:
    """
    Asks the local LLM to analyze a chess mistake.
    
    Args:
        position_fen: The FEN string of the board position where the mistake occurred.
        player_color: The color of the player who made the mistake ('White' or 'Black').
        mistake: The move that was played (e.g., 'e4e5').
        best_move: The move Stockfish suggested as best.
        
    Returns:
        A string containing the LLM's analysis.
    """
    prompt = f"""
    You are a friendly and encouraging chess coach.
    Analyze the following chess position from the perspective of the player who just moved.
    
    Position (FEN): {position_fen}
    
    The player ({player_color}) just played the move {mistake}.
    This was a mistake. The best move was {best_move}.
    
    Please explain in simple, clear terms:
    1. Why was {mistake} a bad move?
    2. What was the idea behind the better move, {best_move}?
    
    Keep your explanation concise and focused on the most important concepts.
    """
    
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}]
        )
        return response['message']['content']
    except Exception as e:
        return f"Error getting analysis from Ollama: {e}"

def analyze_game(pgn_path: str):
    """
    Analyzes a chess game from a PGN file, identifies blunders,
    and uses an LLM to provide coaching advice.
    
    Args:
        pgn_path: The file path to the PGN game.
    """
    if not os.path.exists(STOCKFISH_PATH) or not os.path.isfile(STOCKFISH_PATH):
        print(f"Error: Stockfish executable not found at '{STOCKFISH_PATH}'")
        print("Please download Stockfish and update the STOCKFISH_PATH variable in this script.")
        return

    try:
        stockfish = Stockfish(path=STOCKFISH_PATH, depth=18)
    except Exception as e:
        print(f"Failed to initialize Stockfish: {e}")
        return

    try:
        with open(pgn_path) as pgn_file:
            game = chess.pgn.read_game(pgn_file)
    except FileNotFoundError:
        print(f"Error: PGN file not found at '{pgn_path}'")
        return
    
    if game is None:
        print("Error: Could not read a valid game from the PGN file.")
        return

    board = game.board()
    print(f"Analyzing game: {game.headers.get('White', '?')} vs. {game.headers.get('Black', '?')}")
    print("-" * 40)
    
    for i, move in enumerate(game.mainline_moves()):
        move_number = (i // 2) + 1
        player_color = "White" if board.turn == chess.WHITE else "Black"
        
        # Get the evaluation BEFORE the move. Stockfish is always from White's perspective.
        stockfish.set_fen_position(board.fen())
        evaluation_from_white_perspective = get_stockfish_evaluation(stockfish, board)
        
        # We need the score from the current player's perspective.
        # If it's Black's turn, a positive score for White is a negative score for Black.
        score_before_move = evaluation_from_white_perspective if player_color == "White" else -evaluation_from_white_perspective

        # Make the move and get the move in Standard Algebraic Notation (SAN)
        move_san = board.san(move)
        board.push(move)

        # Get the evaluation after the move, from the opponent's perspective.
        stockfish.set_fen_position(board.fen())
        score_after_move_for_opponent = get_stockfish_evaluation(stockfish, board)

        # The player's new score is the negative of their opponent's score.
        score_after_move_for_player = -score_after_move_for_opponent

        # The drop in evaluation is the difference between the score before and after.
        eval_drop = score_before_move - score_after_move_for_player
        
        # Print the move
        if player_color == "White":
            print(f"{move_number}. {move_san}", end=" ")
        else:
            print(f"{move_san}")

        # If the game is over, no need to analyze for blunders on this move.
        if board.is_game_over():
            continue
            
        # Check for a blunder
        if eval_drop > BLUNDER_THRESHOLD:
            print(f"\n*** MISTAKE by {player_color} on move {move_san}! (Eval drop: {eval_drop:.0f}) ***")
            
            # We need the FEN *before* the bad move was made.
            board.pop()
            position_fen = board.fen()
            
            # Set stockfish to the position *before* the blunder to find the best move.
            stockfish.set_fen_position(position_fen)
            best_move_uci = stockfish.get_best_move()
            best_move_san = board.san(chess.Move.from_uci(best_move_uci))
            
            # Get LLM analysis
            analysis = get_llm_analysis(position_fen, player_color, move_san, best_move_san)
            print("\n--- Coach's Corner ---")
            print(analysis)
            print("----------------------\n")
            
            # Push the move back on to continue the game
            board.push(move)

    print("\nAnalysis complete.")


def main():
    """Main function to run the CLI."""
    parser = argparse.ArgumentParser(description="A simple CLI chess coach that analyzes a PGN file.")
    parser.add_argument("pgn_file", help="The path to the PGN file to analyze.")
    args = parser.parse_args()
    
    analyze_game(args.pgn_file)

if __name__ == "__main__":
    main()
