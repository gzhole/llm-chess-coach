# Project Roadmap

This file tracks completed milestones and future project ideas for the LLM Chess Coach.

---

## Completed Milestones

### ✔️ Deeper Analysis (Enhanced CLI)
-   **Status:** Complete
-   **Details:** The CLI can now analyze blunders and use an LLM to tag them with tactical motifs like "Hanging Piece" or "Missed Tactic." It also supports side-specific analysis and can export an annotated PGN with coaching comments.

### ✔️ Web API
-   **Status:** Complete
-   **Details:** A FastAPI server is implemented with an `/analyze` endpoint that accepts a PGN file upload and returns analysis results as JSON. The API is fully tested and uses dependency injection for the database.

---

## Future Ideas

### Idea 1: Build a Web UI
-   **Goal:** Create a simple, browser-based user interface for interacting with the coach.
-   **Tasks:**
    -   Set up a basic frontend project (e.g., using Next.js or SvelteKit).
    -   Create a page where a user can upload a PGN file.
    -   Call the FastAPI `/analyze` endpoint and display the results, including the board state for each blunder.
-   **Benefit:** Makes the tool more accessible to non-technical users and provides a richer visual experience.

### Idea 2: Automatic Game Importing
-   **Goal:** Allow users to connect their online chess accounts (Lichess, Chess.com) to import games automatically.
-   **Tasks:**
    -   Implement OAuth2 for Lichess and/or Chess.com.
    -   Create a service that periodically fetches new games for a connected user.
    -   Add the imported games to a processing queue for analysis.
-   **Benefit:** Removes the manual step of downloading and uploading PGN files, creating a seamless user experience.

### Idea 3: Spaced Repetition and Drills
-   **Goal:** Help users actively train to overcome their most common mistakes.
-   **Tasks:**
    -   From the database, identify a user's most frequent mistake motifs.
    -   Create a "daily drill" feature that presents the user with the board position right before a past blunder.
    -   Ask the user to find the best move and provide feedback.
-   **Benefit:** Moves from passive analysis to active, targeted training, which is more effective for improvement.
