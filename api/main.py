# api/main.py
"""
FastAPI web API for chess game analysis.

This module provides HTTP endpoints for analyzing chess games using the
chess coach system and returning results as JSON responses.
"""

import sys
import os
import tempfile
from fastapi import FastAPI, UploadFile, File, Depends, HTTPException
from fastapi.responses import JSONResponse
from shutil import copyfileobj
from typing import List, Dict, Any

# Add the project root to the Python path to allow importing from parent
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database import Database
from core.analysis import StockfishAnalyzer, LLMCoach, GameProcessor

app = FastAPI(title="Chess Coach API", description="API for analyzing chess games and providing coaching feedback")

# --- Constants ---
STOCKFISH_PATH = os.getenv("STOCKFISH_PATH", "stockfish")
BLUNDER_THRESHOLD = 150  # Minimum centipawn loss to be considered a significant mistake
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "gemma3:1b")  # The Ollama model to use for analysis
SYSTEM_PROMPT_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "prompts", "system_prompt.txt")

def get_db():
    """
    FastAPI dependency that provides a database connection.
    It ensures the database is initialized and the connection is closed after the request.
    """
    db = Database()
    try:
        db.init_db()  # Ensure the schema exists
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    """
    Root endpoint that returns a welcome message.
    """
    return {"message": "Welcome to the Chess Coach API! Use /analyze/ to upload a PGN file for analysis."}

@app.post("/analyze/", response_model=Dict[str, List[Dict[str, Any]]])
async def analyze_pgn_file(
    pgn_file: UploadFile = File(..., description="A PGN file to be analyzed."),
    db: Database = Depends(get_db)
):
    """
    Analyzes a PGN file and returns a list of detected blunders with coaching comments.
    """
    # Create a temporary file to store the uploaded PGN
    with tempfile.NamedTemporaryFile(delete=False, suffix='.pgn', mode='wb') as tmp_file:
        # Copy the uploaded file to the temp file
        copyfileobj(pgn_file.file, tmp_file)
        tmp_path = tmp_file.name
    
    try:
        # Initialize components
        analyzer = StockfishAnalyzer(stockfish_path=STOCKFISH_PATH)
        coach = LLMCoach(model=OLLAMA_MODEL, system_prompt_path=SYSTEM_PROMPT_PATH)
        processor = GameProcessor(analyzer, coach, db, BLUNDER_THRESHOLD)
        
        # Analyze the game
        processor.analyze_game(tmp_path, side_to_analyze='both')
        
        # Get the analysis results from the database
        analysis_results = db.get_blunders_by_pgn_path(tmp_path)
        
        return {"analysis": analysis_results}
    
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analysis error: {str(e)}")
    finally:
        # Clean up the temporary file
        if os.path.exists(tmp_path):
            os.remove(tmp_path)
        if 'analyzer' in locals():
            analyzer.close()