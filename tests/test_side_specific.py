import unittest
import os
import chess
import chess.pgn
from unittest.mock import MagicMock, patch
import pytest
import sys

# Add the parent directory to the path to import modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from core.analysis import StockfishAnalyzer, LLMCoach, GameProcessor

# Get the absolute path to the tests directory
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))

# Create a simple test PGN path
TEST_PGN_PATH = os.path.join(TESTS_DIR, 'test_simple.pgn')

def setup_module():
    """Create a simple test PGN file for testing."""
    with open(TEST_PGN_PATH, 'w') as f:
        f.write('''[Event "Test Game"]
[White "Player A"]
[Black "Player B"]
[Result "*"]

1. e4 e5 2. Nf3 Nc6 3. Bc4 Bc5 *''')

def teardown_module():
    """Clean up the test PGN file."""
    if os.path.exists(TEST_PGN_PATH):
        os.remove(TEST_PGN_PATH)

@pytest.mark.parametrize("side_to_analyze, expected_blunder_detected", [
    ("white", True),  # White blunder should be detected when analyzing white
    ("black", False), # White blunder should not be detected when analyzing black
    ("both", True),   # White blunder should be detected when analyzing both
])
@patch('core.analysis.ollama.chat')
@patch('core.analysis.Stockfish')
def test_simple_side_specific_analysis(mock_stockfish_class, mock_ollama_chat, 
                                      capsys, side_to_analyze, expected_blunder_detected):
    """
    A simplified test that focuses only on side-specific analysis.
    We'll create a scenario where White makes a clear blunder and verify
    that it's detected only when analyzing White or both sides.
    """
    # ARRANGE
    # Setup mock for LLM response
    mock_ollama_chat.return_value = {'message': {'content': '{"motif": "Test", "severity": "High", "explanation": "Test explanation"}'}}
    
    # Create a complete Stockfish analyzer mock
    # We'll implement a proper StockfishAnalyzer that returns controlled values
    class MockStockfishAnalyzer:
        def __init__(self):
            self.eval_sequence = [
                # Initial position through 3...Bc5
                {'type': 'cp', 'value': 100},  # Initial position
                {'type': 'cp', 'value': 150},  # After 1. e4
                {'type': 'cp', 'value': 50},   # After 1...e5
                {'type': 'cp', 'value': 300},  # After 2. Nf3 (high value)
                {'type': 'cp', 'value': 200},  # After 2...Nc6
                {'type': 'cp', 'value': 50},   # After 3. Bc4 (big drop = blunder)
                {'type': 'cp', 'value': 0},    # After 3...Bc5
            ]
            self.eval_index = 0
            self.fen_positions = []
            
        def get_stockfish_evaluation(self, board):
            # Save the board position for debugging
            fen = board.fen()
            self.fen_positions.append(fen)
            print(f"DEBUG - Evaluating position: {fen}")
            
            # Return the next evaluation in sequence
            if self.eval_index < len(self.eval_sequence):
                eval_dict = self.eval_sequence[self.eval_index]
                self.eval_index += 1
                print(f"DEBUG - Returning evaluation: {eval_dict}")
                return eval_dict
            return {'type': 'cp', 'value': 0}
        
        def get_centipawns(self, eval_dict):
            if eval_dict['type'] == 'cp':
                val = eval_dict['value']
                print(f"DEBUG - get_centipawns returning: {val}")
                return val
            return 0
        
        def get_best_move(self, board):
            return 'd2d4'  # Dummy best move
        
        def close(self):
            pass
    
    # Use our custom mock analyzer instead of MagicMock
    mock_analyzer = MockStockfishAnalyzer()
    mock_stockfish_class.return_value = mock_analyzer

    # Create mocks for other dependencies
    db = MagicMock()
    coach = MagicMock()
    coach.get_analysis.return_value = ('Missed Tactic', 'Medium', 'You missed a better move')
    
    # Use a low blunder threshold to ensure detection
    blunder_threshold = 100
    
    # ACT
    # Create the processor and analyze the game
    processor = GameProcessor(mock_analyzer, coach, db, blunder_threshold)
    
    # Patch the _load_system_prompt method to avoid file system calls
    with patch('core.analysis.LLMCoach._load_system_prompt') as mock_load_prompt:
        mock_load_prompt.return_value = "Mock system prompt"
        processor.analyze_game(TEST_PGN_PATH, side_to_analyze=side_to_analyze)
    
    # ASSERT
    # Check the output for blunder detection
    captured = capsys.readouterr()
    output = captured.out
    
    print(f"DEBUG - Test output: {output}")
    
    if expected_blunder_detected:
        assert "*** MISTAKE by White" in output
    else:
        assert "*** MISTAKE by White" not in output
