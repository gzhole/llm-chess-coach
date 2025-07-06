# coach.py

import chess
import chess.pgn
import json
import ollama
from stockfish import Stockfish
import argparse
import os
import tempfile
from database import Database

# --- Configuration ---
# TODO: Update this path to your Stockfish executable
# You can download it from https://stockfishchess.org/download/
STOCKFISH_PATH = "D:/stockfish/stockfish-windows-x86-64-avx2.exe"

# Blunder threshold in centipawns. A drop of 150 is a significant mistake.
BLUNDER_THRESHOLD = 150 

# The name of the Ollama model to use for analysis
# OLLAMA_MODEL = 'llama3.2:1b'
OLLAMA_MODEL = 'gemma3:1b'

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

def get_llm_analysis(position_fen: str, player_color: str, mistake: str, best_move: str) -> tuple[str, str]:
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

    Please provide your analysis in JSON format with two keys: "mistake_tag" and "explanation".

    For "mistake_tag", choose one of the following tactical motifs that best describes the error:
    - Hanging Piece
    - Missed Mate
    - Missed Tactic
    - Blunder
    - Inaccuracy
    - Positional Error

    For "explanation", provide a clear, concise explanation of:
    1. Why was {mistake} a bad move?
    2. What was the idea behind the better move, {best_move}?

    Keep your explanation focused on the most important concepts. Don't ask questions.
    """
    
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[{'role': 'user', 'content': prompt}],
            options={'temperature': 0.3} # Lower temperature for more deterministic JSON
        )
        content = response['message']['content']

        # Clean the content to extract the JSON object.
        # LLMs often wrap JSON in markdown code blocks (e.g., ```json ... ```).
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        
        content = content.strip()
        
        # Attempt to parse the JSON response, with a fallback
        try:
            analysis_json = json.loads(content)
            tag = analysis_json.get("mistake_tag", "Uncategorized")
            explanation = analysis_json.get("explanation", "No explanation provided.")
            return tag, explanation
        except (json.JSONDecodeError, KeyError):
            # If the response is not valid JSON, treat the whole thing as the explanation.
            return "Uncategorized", content

    except Exception as e:
        return "Error", f"Error getting analysis from Ollama: {e}"

def analyze_game(db: Database, pgn_path: str, side_to_analyze: str = 'both', output_path: str = None):
    """
    Analyzes a chess game from a PGN file, identifies blunders,
    adds coaching comments, and optionally saves the annotated game.
    
    Args:
        pgn_path: The file path to the PGN game.
        side_to_analyze: The side to analyze ('white', 'black', or 'both').
        output_path: Optional path to save the annotated PGN file.
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
    
    # We iterate through the game's nodes to be able to add comments.
    for node in game.mainline():
        # Skip the root node which has no move
        if not node.parent:
            continue
            
        move = node.move
        
        # The board is at the state *before* this move.
        # We need to determine the player color *before* pushing the move.
        player_color = "White" if board.turn == chess.WHITE else "Black"
        
        # Get the evaluation BEFORE the move.
        eval_before_white_pov = get_stockfish_evaluation(stockfish, board)
        
        # Get the move in Standard Algebraic Notation (SAN) for printing
        move_san = board.san(move)
        
        # Make the move to get to the state of the current node
        board.push(move)

        # Get the evaluation AFTER the move.
        eval_after_white_pov = get_stockfish_evaluation(stockfish, board)

        # Calculate the evaluation drop from the current player's perspective.
        if player_color == "White":
            eval_drop = eval_before_white_pov - eval_after_white_pov
        else: # Black
            eval_drop = eval_after_white_pov - eval_before_white_pov
        
        # Print the move
        if player_color == "White":
            print(f"{board.fullmove_number}. {move_san}", end=" ")
        else:
            print(f"{move_san}")

        # If the game is over, no need to analyze for blunders on this move.
        if board.is_game_over():
            continue
            
        # Check for a blunder, but only for the specified side.
        if (side_to_analyze == 'both' or side_to_analyze.lower() == player_color.lower()) and eval_drop > BLUNDER_THRESHOLD:
            
            # Pop the move to get the board state *before* the blunder
            board.pop()
            position_fen = board.fen()
            
            # Set stockfish to the position *before* the blunder to find the best move.
            stockfish.set_fen_position(position_fen)
            best_move_uci = stockfish.get_best_move()
            best_move_san = board.san(chess.Move.from_uci(best_move_uci))
            
            # Get LLM analysis
            mistake_tag, explanation = get_llm_analysis(position_fen, player_color, move_san, best_move_san)

            print(f"\n*** MISTAKE by {player_color} on move {move_san}! (Tag: {mistake_tag}, Eval drop: {eval_drop:.0f}) ***")
            print("\n--- Coach's Corner ---")
            print(explanation)
            print("----------------------\n")
            
            # Add the analysis as a comment to the game node
            node.comment = explanation

            # Save the blunder to the database
            db.save_blunder(
                    pgn_path=pgn_path,
                    move_number=board.fullmove_number,
                    player_color=player_color,
                    move_san=move_san,
                    position_fen=position_fen,
                    eval_drop=int(eval_drop),
                    best_move_san=best_move_san,
                    coach_comment=explanation,
                    mistake_tag=mistake_tag
                )
            
            # Push the move back on to restore the board state for the next iteration
            board.push(move)

    print("\nAnalysis complete.")

    # Export the annotated PGN if an output path is provided
    if output_path:
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                exporter = chess.pgn.FileExporter(f)
                game.accept(exporter)
            print(f"\nAnnotated game saved to {output_path}")
        except IOError as e:
            print(f"Error saving PGN file: {e}")


def analyze_pgn_string(db: Database, pgn_content: str) -> list:
    """
    Analyzes a PGN string by saving it to a temporary file and running the
    standard analysis pipeline.
    
    Args:
        pgn_content: A string containing the PGN data.
        
    Returns:
        A list of dictionaries, where each dictionary represents a blunder.
    """
    # Create a temporary file to store the PGN content
    # The delete=False flag is important for Windows compatibility, allowing the file to be opened by another process.
    with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.pgn', encoding='utf-8') as tmp_file:
        tmp_file.write(pgn_content)
        tmp_file_path = tmp_file.name

    try:
        # Run the existing analysis function on the temporary file
        analyze_game(db, tmp_file_path, side_to_analyze='both', output_path=None)

        # Retrieve the results from the database
        results = db.get_blunders_by_pgn_path(tmp_file_path)
        
        return results

    finally:
        # Clean up the temporary file
        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)


def main():
    """Main function to run the CLI."""
    parser = argparse.ArgumentParser(description="A simple CLI chess coach that analyzes a PGN file.")
    parser.add_argument("pgn_file", help="The path to the PGN file to analyze.")
    parser.add_argument("--side", type=str, default="both", choices=["white", "black", "both"], help="The side to analyze (white, black, or both). Default is both.")
    parser.add_argument("--output", type=str, default=None, help="The path to save the annotated PGN file.")
    args = parser.parse_args()

    # Initialize the database and ensure the schema is created
    with Database() as db:
        db.init_db()
        analyze_game(db, args.pgn_file, args.side, args.output)

if __name__ == "__main__":
    main()
