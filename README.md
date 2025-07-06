# LLM Chess Coach

An **engine-grounded, long-term-memory chess coach** that combines Stockfish analysis with a local LLM to deliver personalized feedback on your games.

This project analyzes your chess games from PGN files, identifies blunders using the Stockfish engine, and uses a local Large Language Model (via Ollama) to provide clear, actionable coaching advice. All analysis is saved to a local SQLite database, allowing the coach to remember your games and identify recurring mistakes.

---

## Features

- **Blunder Detection**: Uses Stockfish to find significant errors in your games.
- **LLM-Powered Coaching**: Generates easy-to-understand explanations for why a move was a mistake and what a better alternative would have been.
- **Mistake Classification**: Tags blunders with common tactical motifs (e.g., "Hanging Piece," "Missed Tactic") for targeted improvement.
- **Persistent Memory**: Saves all analysis to a local SQLite database (`chess_coach.db`).
- **Side-Specific Analysis**: Use the `--side` flag to analyze for only White or Black.
- **Annotated PGN Export**: Use the `--output` flag to save a new PGN file with the coach's comments included.
- **Web API**: A FastAPI server provides an `/analyze` endpoint to run analysis via an API.

---

## Tech Stack

| Layer     | Choice                         |
|-----------|--------------------------------|
| Engine    | Stockfish                      |
| Backend   | Python, FastAPI                |
| Storage   | SQLite                         |
| LLM       | Ollama (e.g., Llama 3)         |

---

## Getting Started

### 1. Prerequisites

- **Python 3.10+**
- **Stockfish**: You must have the Stockfish engine executable downloaded and available on your system. You can download it from the [official Stockfish website](https://stockfishchess.org/download/).
- **Ollama**: You need a local Ollama instance running with a downloaded model (e.g., `llama3`). See the [Ollama website](https://ollama.com/) for installation instructions.

### 2. Installation

```bash
# Clone the repository
git clone https://github.com/gzhole/llm-chess-coach.git
cd llm-chess-coach

# Create and activate a Python virtual environment
python -m venv .venv
# On Windows:
source .venv/Scripts/activate
# On macOS/Linux:
source .venv/bin/activate

# Install the required dependencies
pip install -r requirements.txt
```

### 3. Configuration

Before running the application, you must configure the path to your Stockfish executable.

1.  Open the `coach.py` file.
2.  Find the line `STOCKFISH_PATH = "/path/to/your/stockfish"`.
3.  Replace `/path/to/your/stockfish` with the actual absolute path to your Stockfish executable (e.g., `C:\Users\YourUser\Downloads\stockfish\stockfish.exe` on Windows or `/usr/local/bin/stockfish` on Linux).

---

## Usage

### Command-Line Interface (CLI)

The primary way to use the coach is through the `coach.py` script. A sample game is provided in `games/sample_game.pgn`.

**Basic Analysis:**
```bash
python coach.py games/sample_game.pgn
```

**Analyze for Black Only:**
```bash
python coach.py games/sample_game.pgn --side black
```

**Analyze and Export Annotated PGN:**
```bash
python coach.py games/sample_game.pgn --output games/annotated_game.pgn
```

### Web API

The project includes a FastAPI server for running analysis programmatically.

**1. Run the Server:**
```bash
# Make sure your virtual environment is active
uvicorn api.main:app --reload
```

**2. Send an Analysis Request:**

You can send a PGN file to the `/analyze/` endpoint using a tool like `curl`.

```bash
curl -X POST -F "pgn_file=@games/sample_game.pgn;type=application/vnd.chess-pgn" http://127.0.0.1:8000/analyze/
```

The API will return a JSON object containing the analysis results.

### Testing

To run the test suite, which includes unit and integration tests:

```bash
pytest
```

## Roadmap

1. **v0.1** – PGN import + analysis + metrics dashboard  
2. **v0.2** – Post‑game conversational review (RAG)  
3. **v0.3** – Daily 15‑minute drill scheduler  
4. **v0.4** – Mental‑skills toolbox & mood tracking  
5. **v1.0** – Real‑time overlay (beta)

---

## Usage

To analyze a game, run the `coach.py` script from your terminal. You can specify a PGN file and optionally the side to analyze.

```bash
# Analyze both sides (default)
python coach.py games/sample_game.pgn

# Analyze only White's moves
python coach.py games/sample_game.pgn --side white

# Analyze only Black's moves
python coach.py games/sample_game.pgn --side black

# Analyze a game and save the annotated PGN to a new file
python coach.py games/sample_game.pgn --output games/annotated_game.pgn
```

---

## Contributing

Contributions are welcome!  
Open an issue or start a discussion to pitch features or bug fixes.

To run the test suite:

```bash
# lint & tests
.\.venv\Scripts\Activate.ps1
python -m pytest
```

---

## License

MIT © 2025 Your Name
