# MYGeranHub

MYGeranHub helps Malaysian founders discover grants via a JamAI-powered backend and a React/Vite frontend.

## Structure

- `backend/server`: FastAPI app with Firebase-authenticated endpoints.
- `backend/agents`: scaffolding for future crawler/verifier/corrector workers.
- `frontend`: Vite + React client with Firebase authentication and chat UI.

## Getting Started

### Backend

1. Copy `backend/env.example` to `.env` (or export the variables another way) and fill in your Firebase + JamAI details (base URL, project ID, API key, and table identifiers).
2. Install dependencies: `python -m venv .venv && .venv\\Scripts\\activate && pip install -r backend/requirements.txt`
3. Run the API (from the repository root): `uvicorn backend.server.main:app --reload`

### Frontend

1. Copy `frontend/env.example` to `.env` and provide the Firebase web config plus `VITE_API_BASE_URL`.
2. Install dependencies: `cd frontend && npm install`
3. Start the dev server: `npm run dev`

The frontend expects the backend to be available at `VITE_API_BASE_URL` (default `http://localhost:8000`).

## Grant Sync Workflow

- The `grant_decider` LLM prompt lives in `backend/agents/prompts/grant_decider_prompt.md`. Copy the template (including model settings) into the JamAI Action Table column configuration.
- The Action Table (`scrap_result`) needs a plain text column named `knowledge_sync_status` (or any name configured via `JAMAI_KNOWLEDGE_SYNC_STATUS_COL`). Initialize new rows with `pending`.
- `grant_final` must either contain the verified JSON schema `{grantName, period, grantDescription, applicationProcess, requiredDocuments}` or the literal string `failed to verify`.

### Required environment variables

Set these values inside `backend/.env`:

- `JAMAI_BASE_URL` (e.g., `https://api.jamaibase.com`). The backend automatically prefixes `/api/v2` as required by the [JamAI REST specification](https://jamaibase.readme.io/reference/create_project_api_v2_projects_post).
- `JAMAI_PROJECT_ID`
- `JAMAI_API_KEY`
- `JAMAI_SCRAP_RESULT_TABLE_ID` (defaults to `scrap_result`)
- `JAMAI_GRANTS_TABLE_ID` (defaults to `grants`)
- `JAMAI_KNOWLEDGE_SYNC_STATUS_COL` (defaults to `knowledge_sync_status`)

### Syncing verified grants

- Endpoint: `POST /jamai/sync-grants?limit=25`
- Response: `{"processed": X, "synced": Y, "failed": Z, "skipped": W}`
- Example cron call:

  ```sh
  curl -X POST "https://<backend-host>/jamai/sync-grants?limit=50" \
    -H "Authorization: Bearer <service-token>"
  ```

- Successful rows are inserted into the `grants` knowledge table and marked as `synced`. Rows that fail validation are tagged with `failed: <reason>` (or `skipped: ...`) in `knowledge_sync_status` so the cron can ignore them until someone fixes the upstream data.

### Background worker (cron replacement)

- A lightweight worker at `backend/server/workers/grant_sync_worker.py` runs the sync in-process on a daily schedule (default 04:00 local time).
- Run it manually (or via a process supervisor) with:

  ```sh
  python -m backend.server.workers.grant_sync_worker --hour 4 --minute 0
  ```

- Use `--once` to trigger an immediate run, or override `--limit` to cap rows per batch.
- Deploy it the same way you would deploy a cron job: e.g., `systemd`, PM2, Supervisor, or a container orchestrator. The worker handles SIGINT/SIGTERM for graceful shutdowns.
