# tests/test_coach.py

import os
import chess
import chess.pgn
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock
import pytest
from coach import analyze_game
from database import Database

# Get the absolute path to the test PGN file
TESTS_DIR = os.path.dirname(os.path.abspath(__file__))
TEST_PGN_PATH = os.path.join(TESTS_DIR, 'scholars_mate.pgn')

# We patch the file system checks to make the test independent of the actual Stockfish executable's presence.
@patch('coach.ollama.chat')
@patch('coach.Stockfish')
def test_blunder_triggers_analysis(mock_stockfish_class, mock_ollama_chat, capsys):
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
    analyze_game(MagicMock(), TEST_PGN_PATH)

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
@patch('coach.ollama.chat')
@patch('coach.Stockfish')
def test_side_specific_analysis(mock_stockfish_class, mock_ollama_chat, capsys, side_to_analyze, expected_mistake_by, not_expected_mistake_by):
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
    analyze_game(MagicMock(), BLUNDERS_PGN_PATH, side_to_analyze)

    # 3. ASSERT
    captured = capsys.readouterr()
    output = captured.out

    assert f"*** MISTAKE by {expected_mistake_by}" in output
    if not_expected_mistake_by:
        assert f"*** MISTAKE by {not_expected_mistake_by}" not in output
    
    # A special check for the 'both' case to ensure Black's mistake is also caught
    if side_to_analyze == 'both':
        assert f"*** MISTAKE by Black" in output

@patch('coach.ollama.chat')
@patch('coach.Stockfish')
def test_pgn_export_with_comments(mock_stockfish_class, mock_ollama_chat, capsys):
    """
    Tests that the annotated PGN is correctly exported with LLM comments.
    """
    # 1. ARRANGE
    output_pgn_path = os.path.join(TESTS_DIR, "annotated_game.pgn")
    mock_llm_comment = "This is a test comment from the mock LLM."
    mock_ollama_chat.return_value = {'message': {'content': mock_llm_comment}}

    mock_stockfish_instance = MagicMock()

    # FEN for the position BEFORE Black's blunder (after 3. Bc4)
    fen_before_blunder = 'r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3'
    # FEN for the position AFTER Black's blunder (after 3... Nf6??)
    fen_after_blunder = 'r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4'

    current_fen = ""
    def set_fen_side_effect(fen):
        nonlocal current_fen
        current_fen = fen
    mock_stockfish_instance.set_fen_position.side_effect = set_fen_side_effect

    def get_evaluation_side_effect():
        if current_fen == fen_before_blunder:
            return {'type': 'cp', 'value': 50}
        if current_fen == fen_after_blunder:
            return {'type': 'cp', 'value': 1000} # Blunder!
        return {'type': 'cp', 'value': 0}

    mock_stockfish_instance.get_evaluation.side_effect = get_evaluation_side_effect
    mock_stockfish_instance.get_best_move.return_value = 'g7g6'
    mock_stockfish_class.return_value = mock_stockfish_instance

    # 2. ACT
    try:
        analyze_game(MagicMock(), TEST_PGN_PATH, side_to_analyze='both', output_path=output_pgn_path)

        # 3. ASSERT
        assert os.path.exists(output_pgn_path)

        with open(output_pgn_path, 'r') as f:
            # Re-parse the exported game to check its content programmatically
            exported_game = chess.pgn.read_game(f)
        
        assert exported_game is not None, "Could not parse the exported PGN file."

        # Traverse the game to find the move and check for the comment
        node = exported_game
        found_comment = False
        # The blunder is on move 3... Nf6
        blunder_move_uci = 'g8f6'
        
        while node.variations:
            next_node = node.variations[0]
            # Check if the node corresponds to the blunder move
            if node.board().turn == chess.BLACK and node.board().fullmove_number == 3 and next_node.move.uci() == blunder_move_uci:
                assert next_node.comment == mock_llm_comment
                found_comment = True
                break
            node = next_node
        
        assert found_comment, f"Comment for the blunder move {blunder_move_uci} was not found."

    finally:
        # 4. CLEANUP
        if os.path.exists(output_pgn_path):
            os.remove(output_pgn_path)


@patch('coach.ollama.chat')
@patch('coach.Stockfish')
def test_blunder_is_saved_to_database(mock_stockfish_class, mock_ollama_chat, capsys):
    """
    Tests that a detected blunder is correctly saved to the SQLite database.
    """
    # 1. ARRANGE
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    mock_mistake_tag = "Hanging Piece"
    mock_explanation = "This is a test explanation for the database."
    mock_ollama_chat.return_value = {
        'message': {
            'content': f'{{"mistake_tag": "{mock_mistake_tag}", "explanation": "{mock_explanation}"}}'
        }
    }

    mock_stockfish_instance = MagicMock()

    # FEN for the position BEFORE Black's blunder (after 3. Bc4)
    fen_before_blunder = 'r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3'
    # FEN for the position AFTER Black's blunder (after 3... Nf6??)
    fen_after_blunder = 'r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4'

    current_fen = ""
    def set_fen_side_effect(fen):
        nonlocal current_fen
        current_fen = fen
    mock_stockfish_instance.set_fen_position.side_effect = set_fen_side_effect

    def get_evaluation_side_effect():
        if current_fen == fen_before_blunder:
            return {'type': 'cp', 'value': 50}  # before
        if current_fen == fen_after_blunder:
            return {'type': 'cp', 'value': 1000} # after (blunder)
        return {'type': 'cp', 'value': 0}

    mock_stockfish_instance.get_evaluation.side_effect = get_evaluation_side_effect
    mock_stockfish_instance.get_best_move.return_value = 'g7g6'  # best move
    mock_stockfish_class.return_value = mock_stockfish_instance

    db = Database(db_path=db_path)
    db.init_db()

    try:
        # 2. ACT
        analyze_game(db, TEST_PGN_PATH, side_to_analyze='black')

        # 3. ASSERT
        assert os.path.exists(db_path), "Database file was not created."

        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM blunders")
        blunders = cursor.fetchall()
        conn.close()

        assert len(blunders) == 1, "Incorrect number of blunders saved to the database."
        
        saved_blunder = blunders[0]
        assert saved_blunder['game_pgn_path'] == TEST_PGN_PATH
        assert saved_blunder['move_number'] == 3
        assert saved_blunder['player_color'] == "Black"
        assert saved_blunder['move_san'] == "Nf6"
        assert saved_blunder['position_fen'] == fen_before_blunder
        # For Black, drop is eval_after - eval_before = 1000 - 50 = 950
        assert saved_blunder['eval_drop'] == 950
        assert saved_blunder['best_move_san'] == "g6"
        assert saved_blunder['coach_comment'] == mock_explanation
        assert saved_blunder['mistake_tag'] == mock_mistake_tag

    finally:
        # 4. CLEANUP
        db.close()
        os.remove(db_path)


@patch('coach.ollama.chat')
@patch('coach.Stockfish')
def test_json_parsing_with_markdown_fences(mock_stockfish_class, mock_ollama_chat, capsys):
    """
    Tests that the JSON response is correctly parsed even when wrapped
    in markdown code fences (e.g., ```json ... ```).
    """
    # 1. ARRANGE
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(db_fd)

    mock_mistake_tag = "Missed Tactic"
    mock_explanation = "This is a test explanation inside a markdown block."
    # Simulate the LLM wrapping its response in a markdown code block
    raw_llm_content = f"```json\n{{\n  \"mistake_tag\": \"{mock_mistake_tag}\",\n  \"explanation\": \"{mock_explanation}\"\n}}\n```"
    mock_ollama_chat.return_value = {'message': {'content': raw_llm_content}}

    mock_stockfish_instance = MagicMock()

    # FEN for the position BEFORE Black's blunder (after 3. Bc4)
    fen_before_blunder = 'r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3'
    # FEN for the position AFTER Black's blunder (after 3... Nf6??)
    fen_after_blunder = 'r1bqkb1r/pppp1ppp/2n2n2/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 4 4'

    current_fen = ""
    def set_fen_side_effect(fen):
        nonlocal current_fen
        current_fen = fen
    mock_stockfish_instance.set_fen_position.side_effect = set_fen_side_effect

    def get_evaluation_side_effect():
        if current_fen == fen_before_blunder:
            return {'type': 'cp', 'value': 50}  # before
        if current_fen == fen_after_blunder:
            return {'type': 'cp', 'value': 1000} # after (blunder)
        return {'type': 'cp', 'value': 0}

    mock_stockfish_instance.get_evaluation.side_effect = get_evaluation_side_effect
    mock_stockfish_instance.get_best_move.return_value = 'g7g6'
    mock_stockfish_class.return_value = mock_stockfish_instance

    db = Database(db_path=db_path)
    db.init_db()

    try:
        # 2. ACT
        analyze_game(db, TEST_PGN_PATH, side_to_analyze='black')

        # 3. ASSERT
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT mistake_tag, coach_comment FROM blunders")
        blunder = cursor.fetchone()
        conn.close()

        assert blunder is not None, "No blunder was saved to the database."
        assert blunder['mistake_tag'] == mock_mistake_tag
        assert blunder['coach_comment'] == mock_explanation

    finally:
        # 4. CLEANUP
        db.close()
        os.remove(db_path)
