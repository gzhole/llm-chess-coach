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

def get_stockfish_evaluation(stockfish: Stockfish, board: chess.Board) -> dict:
    """
    Gets the Stockfish evaluation for a given board position.
    
    Args:
        stockfish: An initialized Stockfish instance.
        board: A chess.Board object representing the position.
        
    Returns:
        The evaluation dictionary, e.g., {'type': 'cp', 'value': 21}.
    """
    stockfish.set_fen_position(board.fen())
    return stockfish.get_evaluation()

def get_centipawns(evaluation):
    """
    Converts a Stockfish evaluation dictionary to a centipawn value from White's perspective.
    A positive value is good for White, a negative value is good for Black.
    Handles both 'cp' (centipawns) and 'mate' scores.
    """
    if evaluation['type'] == 'cp':
        return evaluation['value']
    elif evaluation['type'] == 'mate':
        # A mate score is converted to a large centipawn value.
        # The sign indicates who is winning.
        mate_score = 30000
        if evaluation['value'] < 0:
            return -mate_score
        return mate_score
    return 0

def get_llm_analysis(position_fen: str, move_san: str, best_move_san: str, cp_loss: int, mate_missed: bool) -> tuple[str, str, str]:
    """
    Asks the local LLM to analyze a chess mistake and classify it.

    Args:
        position_fen: The FEN string of the board position where the mistake occurred.
        move_san: The move that was played (e.g., 'Nxf7?').
        best_move_san: The move Stockfish suggested as best (e.g., 'Qh5!').
        cp_loss: The centipawn loss from the mistake.
        mate_missed: A boolean indicating if a forced mate was missed.

    Returns:
        A tuple containing: (motif, severity, explanation).
    """
    system_prompt = """
    You are ChessTacticTagger v1.1. Your task is to analyze a single chess move and provide a detailed analysis in a strict JSON format.

    ──────────────────── YOUR TASK ────────────────────
    Based on the context provided, provide a JSON response with three keys: "motif", "severity", and "explanation".

    1.  **motif**: Choose the ONE tactical theme from the list below that best explains why the move is a mistake.
        -   Options: `Pin`, `Skewer`, `Fork`, `DiscoveredAttack`, `XRay`, `Zwischenzug`, `Overloading`, `Clearance`, `Interference`, `HangingPiece`, `Deflection`, `BackRankWeakness`, `Reloader`, `None`

    2.  **severity**: Classify the costliness of the move based on the centipawn loss and if a mate was missed.
        -   Options: `Inaccuracy` (50-99cp), `PositionalError` (100-199cp), `MissedTactic` (200-299cp), `Blunder` (300+ cp), `MissedMate`

    3.  **explanation**: Provide a clear, concise explanation for a human player. Describe why the player's move was weak and what made the engine's suggested move so much better. Focus on the most critical tactical or strategic ideas. Do not ask questions.

    ──────────────────── RESPONSE FORMAT ────────────────────
    Respond with STRICT JSON only. Do not include any introductory text, code fences, or extra keys.

    Example:
    {
      "motif": "HangingPiece",
      "severity": "Blunder",
      "explanation": "Your move left your knight undefended, allowing it to be captured for free. The engine's suggestion initiates a powerful attack on the king, forcing a win."
    }
    """

    user_prompt = f"""
    ──────────────────── ANALYSIS CONTEXT ────────────────────
    - FEN Before Move: {position_fen}
    - Player's Move: {move_san}
    - Engine's Best Move: {best_move_san}
    - Centipawn Loss: {cp_loss}
    - Was a forced mate missed? {'Yes' if mate_missed else 'No'}
    """

    messages = [
        {'role': 'system', 'content': system_prompt},
        {'role': 'user', 'content': user_prompt}
    ]

    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=messages,
            options={'temperature': 0.2, 'timeout': 60}  # Lower temperature and add a 60s timeout
        )
        content = response['message']['content']

        # Clean the content to extract the JSON object.
        if '```json' in content:
            content = content.split('```json')[1].split('```')[0]
        content = content.strip()

        # Attempt to parse the JSON response, with a fallback
        try:
            analysis_json = json.loads(content)
            motif = analysis_json.get("motif", "Uncategorized")
            severity = analysis_json.get("severity", "Unknown")
            explanation = analysis_json.get("explanation", "No explanation provided.")
            return motif, severity, explanation
        except (json.JSONDecodeError, KeyError):
            # If parsing fails, return the raw content as the explanation.
            return "Uncategorized", "Error", content

    except Exception as e:
        return "Error", "Error", f"Error getting analysis from Ollama: {e}"

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
        player_color = "White" if board.turn == chess.WHITE else "Black"
        move_number = board.fullmove_number
        
        # Get the evaluation BEFORE the move.
        eval_before_dict = get_stockfish_evaluation(stockfish, board)
        eval_before = get_centipawns(eval_before_dict)
        
        # Get the move in Standard Algebraic Notation (SAN) for printing
        move_san = board.san(move)
        
        # Make the move to get to the state of the current node
        board.push(move)

        # Get the evaluation AFTER the move.
        eval_after_dict = get_stockfish_evaluation(stockfish, board)
        eval_after = get_centipawns(eval_after_dict)

        # Calculate the evaluation drop based on the player who moved.
        if player_color == "White":
            eval_drop = eval_before - eval_after
        else: # Black's turn
            eval_drop = eval_after - eval_before
        
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
            
            # Check if a mate was missed.
            mate_missed = eval_before_dict['type'] == 'mate'
            
            # Set stockfish to the position *before* the blunder to find the best move.
            stockfish.set_fen_position(position_fen)
            best_move_uci = stockfish.get_best_move() # Use the correct, available method
            best_move_san = board.san(chess.Move.from_uci(best_move_uci))

            # Push the move back to restore the board state
            board.push(move)

            print(f"\n*** MISTAKE by {player_color} on move {move_san}! (Eval drop: {eval_drop}) ***")

            motif, severity, explanation = get_llm_analysis(
                position_fen=position_fen,
                move_san=move_san,
                best_move_san=best_move_san,
                cp_loss=eval_drop,
                mate_missed=mate_missed
            )

            print("\n--- Coach's Corner ---")
            print(f"{severity} ({motif}): {explanation}")
            print("----------------------")

            # Add the analysis as a comment to the PGN node
            node.comment = f"[COACH] {severity} ({motif}): {explanation}"

            # Save the blunder to the database
            db.save_blunder(
                pgn_path=pgn_path,
                move_number=move_number,
                player_color=player_color,
                move_san=move_san,
                position_fen=position_fen,
                eval_drop=eval_drop,
                best_move_san=best_move_san,
                coach_comment=explanation,
                motif=motif,
                severity=severity
            )

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
