# tests/test_coach.py

import pytest
from unittest.mock import patch, MagicMock
import os
from coach import analyze_game, STOCKFISH_PATH

# Get the absolute path to the test PGN file
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_PGN_PATH = os.path.join(TESTS_DIR, 'scholars_mate.pgn')

# We patch the file system checks to make the test independent of the actual Stockfish executable's presence.
@patch('os.path.exists', return_value=True)
@patch('os.path.isfile', return_value=True)
@patch('coach.ollama.chat')
@patch('coach.Stockfish')
def test_blunder_triggers_analysis(mock_stockfish_class, mock_ollama_chat, mock_isfile, mock_exists, capsys):
    """
    Tests that a clear blunder triggers analysis by mocking both Stockfish and Ollama.
    This makes the test fast, reliable, and independent of external executables.
    """
    # 1. ARRANGE

    # --- Mock Ollama --- 
    mock_ollama_chat.return_value = {
        'message': {'content': 'This is a mock analysis from the LLM.'}
    }

    # --- Mock Stockfish ---
    mock_stockfish_instance = MagicMock()
    
    current_fen = ""
    def set_fen_side_effect(fen):
        nonlocal current_fen
        current_fen = fen
    mock_stockfish_instance.set_fen_position.side_effect = set_fen_side_effect

    # Correct FEN for the position BEFORE Black's blunder (after 3. Bc4)
    fen_before_blunder = 'r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3'
    # Correct FEN for the position AFTER Black's blunder (after 3... Nf6??)
    fen_after_blunder = 'r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4'

    def get_evaluation_side_effect():
        if current_fen == fen_before_blunder:
            return {'type': 'cp', 'value': 50}
        
        if current_fen == fen_after_blunder:
            return {'type': 'cp', 'value': 1000} # Large advantage for White
            
        return {'type': 'cp', 'value': 0}

    mock_stockfish_instance.get_evaluation.side_effect = get_evaluation_side_effect
    mock_stockfish_instance.get_best_move.return_value = 'g7g6' # UCI for g6
    mock_stockfish_class.return_value = mock_stockfish_instance

    # 2. ACT
    analyze_game(TEST_PGN_PATH)

    # 3. ASSERT
    captured = capsys.readouterr()
    output = captured.out

    assert "*** MISTAKE by Black" in output
    assert "--- Coach's Corner ---" in output
    mock_ollama_chat.assert_called_once()

    call_args, call_kwargs = mock_ollama_chat.call_args
    prompt = call_kwargs['messages'][0]['content']
    assert f'Position (FEN): {fen_before_blunder}' in prompt
    assert 'player (Black) just played the move Nf6' in prompt
    assert 'best move was g6' in prompt

# Get the absolute path to the new test PGN file
BLUNDERS_PGN_PATH = os.path.join(TESTS_DIR, 'blunders_both_sides.pgn')

@pytest.mark.parametrize("side_to_analyze, expected_mistake_by, not_expected_mistake_by", [
    ("white", "White", "Black"),
    ("black", "Black", "White"),
    ("both", "White", None), # When analyzing both, we expect to see White's mistake
])
@patch('os.path.exists', return_value=True)
@patch('os.path.isfile', return_value=True)
@patch('coach.ollama.chat')
@patch('coach.Stockfish')
def test_side_specific_analysis(mock_stockfish_class, mock_ollama_chat, mock_isfile, mock_exists, capsys, side_to_analyze, expected_mistake_by, not_expected_mistake_by):
    """
    Tests that the analysis is correctly filtered based on the --side argument.
    This test uses a real PGN with blunders from both sides and mocks Stockfish
    evaluation based on FEN strings to ensure reliable testing.
    """
    # 1. ARRANGE
    mock_ollama_chat.return_value = {'message': {'content': 'Mock LLM analysis.'}}
    mock_stockfish_instance = MagicMock()

    # Add a side effect to capture the FEN for the mock evaluation
    current_fen = ""
    def set_fen_side_effect(fen):
        nonlocal current_fen
        current_fen = fen
    mock_stockfish_instance.set_fen_position.side_effect = set_fen_side_effect

    # Define FENs for the positions before and after the blunders
    fen_before_black_blunder = 'rnbqkbnr/pppp1ppp/8/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R b KQkq - 1 2'
    fen_after_black_blunder = 'rnbqkbnr/pppp2pp/5p2/4p3/4P3/5N2/PPPP1PPP/RNBQKB1R w KQkq - 0 3'
    fen_before_white_blunder = 'r2qkb1r/p2n3p/2p2np1/1p1p2B1/8/2NP4/PPP2PPP/2KR1B1R w KQkq - 0 11'
    fen_after_white_blunder = 'r2qkb1r/p2n3p/2p2np1/1p1p2B1/8/2NP4/PPP2PPP/2K1RB1R b kq - 1 11'

    def get_evaluation_side_effect():
        # Default evaluation
        eval_cp = 20
        # --- Simulate Black's blunder (2...f6??) ---
        if current_fen == fen_before_black_blunder:
            eval_cp = 30  # Before: White has a small advantage
        elif current_fen == fen_after_black_blunder:
            eval_cp = 400  # After: White has a decisive advantage
        # --- Simulate White's blunder (11.Re1??) ---
        elif current_fen == fen_before_white_blunder:
            eval_cp = 900  # Before: White has a winning advantage
        elif current_fen == fen_after_white_blunder:
            eval_cp = 150  # After: White's advantage shrinks significantly
        
        return {'type': 'cp', 'value': eval_cp}

    mock_stockfish_instance.get_evaluation.side_effect = get_evaluation_side_effect
    mock_stockfish_instance.get_best_move.return_value = 'd2d4'  # Dummy best move
    mock_stockfish_class.return_value = mock_stockfish_instance

    # 2. ACT
    analyze_game(BLUNDERS_PGN_PATH, side_to_analyze)

    # 3. ASSERT
    captured = capsys.readouterr()
    output = captured.out

    assert f"*** MISTAKE by {expected_mistake_by}" in output
    if not_expected_mistake_by:
        assert f"*** MISTAKE by {not_expected_mistake_by}" not in output
    
    # A special check for the 'both' case to ensure Black's mistake is also caught
    if side_to_analyze == 'both':
        assert f"*** MISTAKE by Black" in output
