# LLM Chess Coach

An **engine‑grounded, long‑term‑memory chess coach** that combines Stockfish analysis with an LLM to deliver personalised, 15‑minute daily training sessions.

---

## Why this project?

* **Affordable coaching** – get master‑level feedback without paying hourly rates.  
* **Perfect recall** – the bot remembers every game you play and surfaces repeating mistakes automatically.  
* **Adaptive drills** – sessions stay short but target your weakest motifs using spaced repetition.  
* **Holistic help** – flags mental bottlenecks (tilt, clock‑panic) and offers focus drills.

---

## MVP Architecture (text diagram)

```
+-------------------------------+
|  PGN Importer (APIs / OAuth)  |
+---------------+---------------+
                |
                v
+---------------+---------------+
|  Analysis Pipeline            |
|  - Stockfish (depth 18)       |
|  - Mistake & motif tagging    |
+---------------+---------------+
                |
                v
+---------------+---------------+
|  Event / Metrics DB           |
|  PostgreSQL (+Timescale)      |
+---------------+---------------+
                |                +-----------------------------+
                |                |  Vector Store (pgvector)    |
                |                +-------------+---------------+
                |                              ^
                v                              |
+---------------+---------------+              |
|  LLM Service (GPT‑4o / Llama) | <-------------+
|  • Pulls context from DB & VS |
|  • Generates chat / drills    |
|  • Guard‑checks with engine   |
+---------------+---------------+
                |
                v
+---------------+---------------+
|  Chat / Drill UI (Next.js)    |
|  (Chessground board)          |
+-------------------------------+
```

---

## Tech stack

| Layer     | Choice                         |
|-----------|--------------------------------|
| Engine    | Stockfish 16.1 (Docker)        |
| Backend   | FastAPI + Celery workers       |
| Storage   | PostgreSQL + pgvector          |
| LLM       | OpenAI GPT‑4o **or** Llama‑3‑70B (Ollama) |
| Frontend  | Next.js + Tailwind + Chessground |
| CI/CD     | GitHub Actions + Fly.io        |

---

## Getting started

```bash
# Clone
git clone https://github.com/gzhole/llm-chess-coach.git
cd llm-chess-coach

# Dev containers (recommended)
docker compose up --build
```

The default compose file spins up:

* `api` – FastAPI server  
* `analysis` – Stockfish worker pool  
* `db` – Postgres + pgvector  
* `ui` – Next.js dev server  

Visit `http://localhost:3000` to open the web UI.

### Environment variables

| Var                  | Description                     |
|----------------------|---------------------------------|
| `OPENAI_API_KEY`     | (if using GPT‑4o)               |
| `OLLAMA_BASE_URL`    | (if using local Llama)          |
| `LICHESS_TOKEN`      | OAuth token for PGN import      |
| `CHESSCOM_TOKEN`     | OAuth token for PGN import      |

Create `.env` from `.env.sample` and fill in the keys you need.

---

## Roadmap

1. **v0.1** – PGN import + analysis + metrics dashboard  
2. **v0.2** – Post‑game conversational review (RAG)  
3. **v0.3** – Daily 15‑minute drill scheduler  
4. **v0.4** – Mental‑skills toolbox & mood tracking  
5. **v1.0** – Real‑time overlay (beta)

---

## Contributing

Contributions are welcome!  
Open an issue or start a discussion to pitch features or bug fixes.

```bash
# lint & tests
.\.venv\Scripts\Activate.ps1
python.exe -m pytest
```

---

## License

MIT © 2025 Your Name
