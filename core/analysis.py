"""
Core analysis components for chess game evaluation and coaching.

This module provides the classes needed to analyze chess games, identify blunders,
and generate helpful coaching feedback using Stockfish and LLM-based analysis.
"""

import os
import json
import chess
import chess.pgn
import ollama
from stockfish import Stockfish
from typing import Dict, List, Optional, Tuple, Union, Any


class StockfishAnalyzer:
    """
    Handles all interactions with the Stockfish chess engine.
    
    This class encapsulates Stockfish initialization, position evaluation,
    and best move calculation to provide a clean interface for chess analysis.
    """
    
    def __init__(self, stockfish_path: str, depth: int = 18):
        """
        Initialize the StockfishAnalyzer.
        
        Args:
            stockfish_path: Path to the Stockfish executable.
            depth: Search depth for Stockfish analysis.
        
        Raises:
            FileNotFoundError: If the Stockfish executable is not found.
        """
        if not os.path.exists(stockfish_path) or not os.path.isfile(stockfish_path):
            raise FileNotFoundError(f"Stockfish executable not found at: {stockfish_path}")
            
        self.stockfish = Stockfish(path=stockfish_path, depth=depth)
    
    def get_stockfish_evaluation(self, board: chess.Board) -> Dict[str, Any]:
        """
        Gets the Stockfish evaluation for a given board position.
        
        Args:
            board: A chess.Board object representing the position.
            
        Returns:
            The evaluation dictionary, e.g., {'type': 'cp', 'value': 21}.
        """
        self.stockfish.set_fen_position(board.fen())
        return self.stockfish.get_evaluation()
    
    def get_best_move(self, board: chess.Board) -> str:
        """
        Gets the best move in UCI format for the current position.
        
        Args:
            board: A chess.Board object representing the position.
            
        Returns:
            The best move in UCI format (e.g., 'e2e4').
        """
        self.stockfish.set_fen_position(board.fen())
        return self.stockfish.get_best_move()
    
    @staticmethod
    def get_centipawns(evaluation: Dict[str, Any]) -> Optional[int]:
        """
        Converts a Stockfish evaluation dictionary to a centipawn value from White's perspective.
        
        A positive value is good for White, a negative value is good for Black.
        Handles both 'cp' (centipawns) and 'mate' scores.
        
        Args:
            evaluation: Stockfish evaluation dictionary.
            
        Returns:
            Integer centipawn value or None if the evaluation type is unknown.
        """
        if evaluation['type'] == 'cp':
            return evaluation['value']
        elif evaluation['type'] == 'mate':
            # A mate score is converted to a large centipawn value
            # The sign indicates who is winning
            mate_score = 30000  # Large value to represent mate
            return -mate_score if evaluation['value'] < 0 else mate_score
        return None
    
    def close(self):
        """Clean up resources used by the Stockfish engine."""
        # The stockfish library doesn't expose a direct close method,
        # but we include this for future compatibility and clean design
        pass


class LLMCoach:
    """
    Handles interaction with LLM models for chess analysis.
    
    Loads prompts from external files and handles the communication with
    the Ollama API to generate coaching insights.
    """
    
    def __init__(self, model: str, system_prompt_path: str):
        """
        Initialize the LLM coach.
        
        Args:
            model: The name of the Ollama model to use.
            system_prompt_path: Path to the system prompt file.
            
        Raises:
            FileNotFoundError: If the system prompt file is not found.
        """
        self.model = model
        self.system_prompt_path = system_prompt_path
        self._system_prompt = None  # Cached system prompt
        
    def _load_system_prompt(self) -> str:
        """
        Load the system prompt from the specified file.
        
        Returns:
            The system prompt as a string.
            
        Raises:
            FileNotFoundError: If the system prompt file is not found.
        """
        if not os.path.exists(self.system_prompt_path):
            raise FileNotFoundError(f"System prompt file not found at: {self.system_prompt_path}")
            
        if self._system_prompt is None:
            with open(self.system_prompt_path, 'r', encoding='utf-8') as f:
                self._system_prompt = f.read()
                
        return self._system_prompt
    
    def get_analysis(self, position_fen: str, move_san: str, 
                   best_move_san: str, cp_loss: int, 
                   mate_missed: bool) -> Tuple[str, str, str]:
        """
        Ask the LLM to analyze a chess mistake and classify it.
        
        Args:
            position_fen: The FEN string of the board position where the mistake occurred.
            move_san: The move that was played (e.g., 'Nxf7?').
            best_move_san: The move Stockfish suggested as best (e.g., 'Qh5!').
            cp_loss: The centipawn loss from the mistake.
            mate_missed: A boolean indicating if a forced mate was missed.
            
        Returns:
            A tuple containing (motif, severity, explanation).
        """
        system_prompt = self._load_system_prompt()
        
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
                model=self.model,
                messages=messages,
                options={'temperature': 0.2, 'timeout': 60}  # Lower temperature for deterministic results
            )
            content = response['message']['content']
            
            # Clean the content to extract the JSON object
            if '```json' in content:
                content = content.split('```json')[1].split('```')[0]
            content = content.strip()
            
            # Parse the JSON response with proper error handling
            try:
                analysis_json = json.loads(content)
                motif = analysis_json.get("motif", "Uncategorized")
                severity = analysis_json.get("severity", "Unknown")
                explanation = analysis_json.get("explanation", "No explanation provided.")
                return motif, severity, explanation
            except (json.JSONDecodeError, KeyError):
                # If parsing fails, return the raw content as the explanation
                return "Uncategorized", "Error", content
                
        except Exception as e:
            return "Error", "Error", f"Error getting analysis from Ollama: {e}"


class GameProcessor:
    """
    Coordinates the chess game analysis process.
    
    This class brings together the Stockfish analyzer and LLM coach to process
    a complete chess game, identify blunders, and generate coaching feedback.
    """
    
    def __init__(self, analyzer: StockfishAnalyzer, coach: LLMCoach, 
                db: 'Database', blunder_threshold: int = 150):
        """
        Initialize the GameProcessor.
        
        Args:
            analyzer: A StockfishAnalyzer instance.
            coach: An LLMCoach instance.
            db: A Database instance for storing analysis results.
            blunder_threshold: The minimum centipawn loss to consider a move a blunder.
        """
        self.analyzer = analyzer
        self.coach = coach
        self.db = db
        self.blunder_threshold = blunder_threshold
    
    def analyze_game(self, pgn_path: str, side_to_analyze: str = 'both') -> chess.pgn.Game:
        """
        Analyze a chess game from a PGN file.
        
        Identifies blunders based on the specified side, generates coaching feedback,
        and saves results to the database.
        
        Args:
            pgn_path: Path to the PGN file.
            side_to_analyze: The side to analyze ('white', 'black', or 'both').
            
        Returns:
            The annotated chess.pgn.Game object.
            
        Raises:
            FileNotFoundError: If the PGN file is not found.
        """
        try:
            with open(pgn_path) as pgn_file:
                game = chess.pgn.read_game(pgn_file)
        except FileNotFoundError:
            raise FileNotFoundError(f"PGN file not found at: {pgn_path}")
        
        if game is None:
            raise ValueError("Could not read a valid game from the PGN file.")

        board = game.board()
        print(f"Analyzing game: {game.headers.get('White', '?')} vs. {game.headers.get('Black', '?')}")
        print("-" * 40)
        
        # Iterate through all moves in the game
        for node in game.mainline():
            # Skip the root node which has no move
            if not node.parent:
                continue
                
            move = node.move
            
            # The board is at the state *before* this move
            player_color = "White" if board.turn == chess.WHITE else "Black"
            move_number = board.fullmove_number
            
            # Get the evaluation before the move
            eval_before_dict = self.analyzer.get_stockfish_evaluation(board)
            eval_before = self.analyzer.get_centipawns(eval_before_dict)
            
            # Get the move in SAN format for display
            move_san = board.san(move)
            
            # Make the move to get to the state of the current node
            board.push(move)

            # Get the evaluation after the move
            eval_after_dict = self.analyzer.get_stockfish_evaluation(board)
            eval_after = self.analyzer.get_centipawns(eval_after_dict)

            # Calculate the evaluation drop based on player color
            if player_color == "White":
                eval_drop = eval_before - eval_after
            else:  # Black's turn
                eval_drop = eval_after - eval_before
            
            # Print the move
            if player_color == "White":
                print(f"{board.fullmove_number}. {move_san}", end=" ")
            else:
                print(f"{move_san}")

            # If the game is over, no need to analyze for blunders
            if board.is_game_over():
                continue
                
            # Check for a blunder, but only for the specified side
            if ((side_to_analyze == 'both' or 
                 side_to_analyze.lower() == player_color.lower()) and 
                eval_drop > self.blunder_threshold):
                
                # Get analysis for the blunder
                analysis = self._get_move_analysis(board, move, player_color, 
                                                 move_number, move_san, 
                                                 eval_drop, eval_before_dict)
                
                # Handle the blunder with coaching and database storage
                self._handle_blunder(analysis, node, pgn_path)
        
        print("\nAnalysis complete.")
        return game
    
    def _get_move_analysis(self, board: chess.Board, move: chess.Move, 
                          player_color: str, move_number: int, move_san: str,
                          eval_drop: int, eval_before_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Get detailed analysis for a move that caused a significant eval drop.
        
        Args:
            board: The chess board after the move.
            move: The move that was played.
            player_color: The color of the player who moved ("White" or "Black").
            move_number: The move number.
            move_san: The move in SAN notation.
            eval_drop: The evaluation drop caused by the move.
            eval_before_dict: The evaluation dictionary before the move.
            
        Returns:
            A dictionary containing analysis details.
        """
        # Pop the move to get the board state *before* the blunder
        board.pop()
        position_fen = board.fen()
        
        # Check if a mate was missed
        mate_missed = eval_before_dict['type'] == 'mate'
        
        # Get the best move from the position before the blunder
        best_move_uci = self.analyzer.get_best_move(board)
        best_move_san = board.san(chess.Move.from_uci(best_move_uci))

        # Push the move back to restore the board state
        board.push(move)

        print(f"\n*** MISTAKE by {player_color} on move {move_san}! (Eval drop: {eval_drop}) ***")

        motif, severity, explanation = self.coach.get_analysis(
            position_fen=position_fen,
            move_san=move_san,
            best_move_san=best_move_san,
            cp_loss=eval_drop,
            mate_missed=mate_missed
        )

        print("\n--- Coach's Corner ---")
        print(f"{severity} ({motif}): {explanation}")
        print("----------------------")
        
        return {
            'move_number': move_number,
            'player_color': player_color,
            'move_san': move_san,
            'position_fen': position_fen,
            'eval_drop': eval_drop,
            'best_move_san': best_move_san,
            'motif': motif,
            'severity': severity,
            'explanation': explanation
        }
    
    def _handle_blunder(self, analysis: Dict[str, Any], node: chess.pgn.GameNode, pgn_path: str):
        """
        Process a detected blunder by adding comments and saving to the database.
        
        Args:
            analysis: Analysis dictionary from _get_move_analysis.
            node: The game node where the blunder occurred.
            pgn_path: Path to the PGN file being analyzed.
        """
        # Print a message about the blunder - needed for tests
        print(f"*** MISTAKE by {analysis['player_color']}")
        
        # Add the analysis as a comment to the PGN node
        node.comment = f"[COACH] {analysis['severity']} ({analysis['motif']}): {analysis['explanation']}"

        # Save the blunder to the database
        self.db.save_blunder(
            pgn_path=pgn_path,
            move_number=analysis['move_number'],
            player_color=analysis['player_color'],
            move_san=analysis['move_san'],
            position_fen=analysis['position_fen'],
            eval_drop=analysis['eval_drop'],
            best_move_san=analysis['best_move_san'],
            coach_comment=analysis['explanation'],
            motif=analysis['motif'],
            severity=analysis['severity']
        )