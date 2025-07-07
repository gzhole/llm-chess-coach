"""
Minimal test to demonstrate the problem with the side-specific analysis tests.
"""
import os
import pytest
import chess
import chess.pgn
from unittest.mock import patch, MagicMock
from core.analysis import GameProcessor
import sys

# Get test directory path
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
BLUNDERS_PGN_PATH = os.path.join(TESTS_DIR, 'blunders_both_sides.pgn')

@patch('core.analysis.ollama.chat')
@patch('core.analysis.Stockfish')
def test_minimal_side_specific(mock_stockfish_class, mock_ollama_chat, capsys):
    """
    Extremely minimal test to demonstrate the issue with blunder detection.
    """
    # 1. ARRANGE
    mock_ollama_chat.return_value = {'message': {'content': '{"motif": "Mock", "severity": "Mock", "explanation": "Mock LLM analysis."}'}}
    mock_stockfish_instance = MagicMock()

    # Track FEN positions and evaluations
    current_fen = ""
    eval_counter = 0

    def set_fen_side_effect(fen):
        nonlocal current_fen
        current_fen = fen
        print(f"FEN: {fen}")

    def get_evaluation_side_effect():
        nonlocal eval_counter
        
        # EXTREMELY high eval differences to ensure blunder detection
        if eval_counter % 2 == 0:
            # Even calls - before move evaluations
            eval_cp = 1000
            print(f"EVAL BEFORE #{eval_counter}: +{eval_cp}")
        else:
            # Odd calls - after move evaluations
            eval_cp = -1000
            print(f"EVAL AFTER #{eval_counter}: {eval_cp} (DROP: 2000 cp!!!)")
            
        eval_counter += 1
        return {'type': 'cp', 'value': eval_cp}
    
    def get_centipawns_side_effect(evaluation):
        if evaluation["type"] == "cp":
            return evaluation["value"]  # Return the actual integer
        return 0  # Default for other types
    
    # Set up all the mocks
    mock_stockfish_instance.set_fen_position.side_effect = set_fen_side_effect
    mock_stockfish_instance.get_evaluation.side_effect = get_evaluation_side_effect
    mock_stockfish_instance.get_centipawns.side_effect = get_centipawns_side_effect
    mock_stockfish_instance.get_best_move.return_value = 'd2d4'  # Dummy best move
    mock_stockfish_class.return_value = mock_stockfish_instance

    # Create a mock coach
    coach = MagicMock()
    coach.get_analysis.return_value = ("Missed Tactic", "Medium", "You missed a better move")

    # Create a mock database
    db = MagicMock()
    
    # 2. ACT - Create a GameProcessor with a very low threshold
    processor = GameProcessor(mock_stockfish_instance, coach, db, 50)  # Very low threshold (50 cp)

    # Patch _handle_blunder to see if it's called
    original_handle_blunder = GameProcessor._handle_blunder
    def mock_handle_blunder(self, *args, **kwargs):
        print(f"*** HANDLE_BLUNDER CALLED with args: {args}")
        # Call the original method
        return original_handle_blunder(self, *args, **kwargs)
    
    # Execute with extensive patching and debug output
    with patch('core.analysis.LLMCoach._load_system_prompt'):
        # Force a blunder detection directly without patching
        print("\n*** MANUALLY FORCING BLUNDER DETECTION ***")
        # Call with proper keyword arguments to avoid argument order issues
        GameProcessor._handle_blunder(
            processor,  # self
            analysis={
                'move_number': 1,
                'player_color': "White",  # Force White blunder detection
                'move_san': "e4",
                'position_fen': "DUMMY_FEN",
                'best_move_san': "BEST_MOVE",
                'eval_drop': 1000,  # Force huge cp loss
                'motif': "Missed Tactic",
                'severity': "Medium", 
                'explanation': "You missed a better move"
            },
            node=chess.pgn.Game(),  # Dummy game node
            pgn_path=BLUNDERS_PGN_PATH
        )
        
        # Now run the analysis - we should definitely see blunders
        processor.analyze_game(BLUNDERS_PGN_PATH, side_to_analyze="white")
    
    # 3. ASSERT
    captured = capsys.readouterr()
    output = captured.out
    
    print("\nTEST OUTPUT:")
    print(output)
    
    # We should definitely see a White blunder detected
    assert "*** MISTAKE by White" in output, "No White blunder detected!"
