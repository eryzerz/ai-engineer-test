# Receipt Management

## How to run

1. **Prerequisites:** [Docker](https://docs.docker.com/get-docker/) with Compose.

2. **Environment:** copy `.env.example` to `.env` and edit as needed.

   - Set `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` .
   - Set **`GOOGLE_API_KEY`** or **`GEMINI_API_KEY`** (optional `GEMINI_MODEL`, default `gemini-3-flash-preview` in Compose).
   - Set **RAG / embeddings:** optional `GEMINI_EMBEDDING_MODEL` (default `gemini-embedding-001`).

3. **Start the stack:**

   ```bash
   docker compose up --build
   ```

4. **Open the app:** [http://localhost:8501](http://localhost:8501) (Streamlit). Postgres and the MCP server run on the internal Docker network as well

To stop: `Ctrl+C`, then `docker compose down`

## Project layout

- `mcp/server.py` — FastMCP + `streamable-http` on port **8000** (`query_postgres`, `insert_receipt`, vector tools)
- `streamlit/` — Streamlit app + `receipt_rag.py` (embeddings), `qa_flow.py` (SQL Q&A)
- `docker/postgres/init/01-receipts.sql` — `receipts` table
- `docker/postgres/init/02-receipt-embeddings.sql` — pgvector + `receipt_embeddings`
