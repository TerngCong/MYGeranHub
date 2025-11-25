# MYGeranHub

MYGeranHub helps Malaysian founders discover grants via a JamAI-powered backend and a React/Vite frontend.

## Structure

- `backend/fastapi`: FastAPI app with Firebase-authenticated endpoints.
- `backend/agents`: scaffolding for future crawler/verifier/corrector workers.
- `frontend`: Vite + React client with Firebase authentication and chat UI.

## Getting Started

### Backend

1. Copy `backend/env.example` to `.env` (or export the variables another way) and fill in your Firebase + JamAI details.
2. Install dependencies: `python -m venv .venv && .venv\\Scripts\\activate && pip install -r backend/requirements.txt`
3. Run the API: `uvicorn backend.fastapi.main:app --reload`

### Frontend

1. Copy `frontend/env.example` to `.env` and provide the Firebase web config plus `VITE_API_BASE_URL`.
2. Install dependencies: `cd frontend && npm install`
3. Start the dev server: `npm run dev`

The frontend expects the backend to be available at `VITE_API_BASE_URL` (default `http://localhost:8000`).



