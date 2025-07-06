# Future Project Ideas

This file tracks potential future features and architectural changes for the LLM Chess Coach.

## Idea 1: Deeper Analysis (Enhance the CLI)

-   **Goal:** Teach the coach to recognize and classify common tactical mistakes.
-   **Tasks:**
    -   Use the LLM to analyze a blunder and tag it with motifs (e.g., "Hanging Piece," "Missed Fork," "Queen Blunder").
    -   Update the analysis output to include these tags.
-   **Benefit:** Provides richer, more targeted feedback to the user.

## Idea 2: Build the First Web API (Transition to a Web App)

-   **Goal:** Move from a CLI tool to a scalable backend service.
-   **Tasks:**
    -   Create a basic FastAPI server.
    -   Implement a `/analyze` endpoint that accepts a PGN file (or PGN string) and returns the analysis results as JSON.
-   **Benefit:** Aligns with the project's long-term architecture (FastAPI + Next.js) and decouples the analysis engine from the user interface.
