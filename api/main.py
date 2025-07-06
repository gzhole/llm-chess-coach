# api/main.py

import sys
import os
from fastapi import FastAPI, UploadFile, File, Depends
from fastapi.responses import JSONResponse

# Add the project root to the Python path to allow importing from 'coach'
# This is necessary because the API is in a subdirectory.
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from coach import analyze_pgn_string
from database import Database

app = FastAPI(
    title="Chess Coach API",
    description="An API to analyze PGN chess files for blunders and get coaching advice.",
    version="1.0.0"
)

# --- Dependency Injection for Database ---
def get_db():
    """
    FastAPI dependency that provides a database connection.
    It ensures the database is initialized and the connection is closed after the request.
    """
    db = Database()
    try:
        db.connect()
        db.init_db() # Ensure tables are created
        yield db
    finally:
        db.close()

@app.get("/", tags=["General"])
def read_root():
    """
    Root endpoint that returns a welcome message.
    """
    return {"message": "Welcome to the Chess Coach API!"}


@app.post("/analyze/", tags=["Analysis"])
async def analyze_pgn_file(
    pgn_file: UploadFile = File(..., description="A PGN file to be analyzed."),
    db: Database = Depends(get_db)
):
    """
    Analyzes a PGN file and returns a list of detected blunders with coaching comments.
    """
    try:
        pgn_content_bytes = await pgn_file.read()
        pgn_content = pgn_content_bytes.decode('utf-8')
        
        if not pgn_content:
            return JSONResponse(status_code=400, content={"error": "The uploaded PGN file is empty."})

        analysis_results = analyze_pgn_string(db, pgn_content)
        
        return JSONResponse(status_code=200, content={"analysis": analysis_results})

    except Exception as e:
        return JSONResponse(status_code=500, content={"error": f"An unexpected error occurred: {str(e)}"})
