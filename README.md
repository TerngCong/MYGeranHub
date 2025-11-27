# MYGeranHub

MYGeranHub helps Malaysian founders discover government grants via a JamAI-powered backend and a React/Vite frontend. The system uses AI agents to scrape, verify, and recommend grants based on user business profiles.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              FRONTEND                                   │
│                     Vite + React + TypeScript                           │
│                     Firebase Authentication                             │
└────────────────────────────────┬────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                              BACKEND                                    │
│                             FastAPI                                     │
├─────────────────────────────────────────────────────────────────────────┤
│  API Routes:                                                            │
│   • /auth - Firebase authentication                                     │
│   • /jamai/session - Create chat session                                │
│   • /jamai/message - Send message (with routing logic)                  │
│   • /jamai/reset - Reset chat session                                   │
│   • /jamai/sync-grants - Trigger knowledge sync                         │
├─────────────────────────────────────────────────────────────────────────┤
│  Services:                                                              │
│   • ChatTableService - Chat routing (general vs grant search)           │
│   • GrantAgent - Multi-stage grant discovery workflow                   │
│   • GrantSyncService - Knowledge table synchronization                  │
├─────────────────────────────────────────────────────────────────────────┤
│  Agents:                                                                │
│   • Agent 1 (WebScraperAgent) - Gemini-powered grant scraping           │
│   • Agent 2 (GrantVerificationAgent) - OpenAI-powered verification      │
├─────────────────────────────────────────────────────────────────────────┤
│  Workers:                                                               │
│   • grant_pipeline_worker - Full orchestration (daily at 03:30)         │
│   • grant_sync_worker - Knowledge sync only (daily at 04:00)            │
└────────────────────────────────────────────────────────────────────────┘
                                 │
                                 ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            JAMAI BASE                                   │
├─────────────────────────────────────────────────────────────────────────┤
│  Chat Tables:                                                           │
│   • User_Chat_Agent - Routing logic (grant search vs general chat)      │
├─────────────────────────────────────────────────────────────────────────┤
│  Action Tables:                                                         │
│   • scrap_result - Scraped grant data with LLM columns                  │
│   • First_Grant - Grant analysis with follow-up questions               │
│   • Input_Guardrail - User input classification                         │
│   • Final_Grant - Final RAG-based grant recommendations                 │
├─────────────────────────────────────────────────────────────────────────┤
│  Knowledge Tables:                                                      │
│   • grants - Verified grant data with embeddings                        │
└─────────────────────────────────────────────────────────────────────────┘
```

## Project Structure

```
├── backend/
│   ├── agents/
│   │   ├── agent1.py              # WebScraperAgent (Gemini-powered)
│   │   ├── agent2.py              # GrantVerificationAgent (OpenAI-powered)
│   │   └── prompts/
│   │       ├── first_grant_analysis_prompt.md
│   │       └── grant_decider_prompt.md
│   ├── server/
│   │   ├── api/
│   │   │   ├── auth.py            # Firebase authentication
│   │   │   ├── jamai_routes.py    # Chat and message endpoints
│   │   │   └── grant_sync.py      # Knowledge sync endpoint
│   │   ├── core/
│   │   │   ├── config.py          # Settings from environment
│   │   │   ├── deps.py            # FastAPI dependencies
│   │   │   └── firebase.py        # Firebase admin SDK
│   │   ├── services/
│   │   │   ├── chat_table_service.py  # Chat routing logic
│   │   │   ├── grant_manager.py       # Multi-stage grant workflow
│   │   │   └── grant_sync.py          # Knowledge table sync
│   │   ├── workers/
│   │   │   ├── grant_pipeline_worker.py  # Full daily pipeline
│   │   │   └── grant_sync_worker.py      # Sync-only worker
│   │   └── main.py
│   └── requirements.txt
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   │   ├── ChatWindow.tsx
│   │   │   ├── LoadingOverlay.tsx
│   │   │   └── MessageBubble.tsx
│   │   ├── context/
│   │   │   └── AuthContext.tsx
│   │   ├── pages/
│   │   │   ├── ChatPage.tsx
│   │   │   └── LoginPage.tsx
│   │   ├── services/
│   │   │   ├── api.ts
│   │   │   └── firebase.ts
│   │   ├── App.tsx
│   │   └── main.tsx
│   └── package.json
│
└── README.md
```

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Firebase project with Authentication enabled
- JamAI Base account with configured tables
- Gemini API key (for Agent 1)
- OpenAI API key (for Agent 2)

### Backend Setup

1. Navigate to the backend directory and create a virtual environment:

   ```sh
   cd backend
   python -m venv venv
   
   # Windows
   venv\Scripts\activate
   
   # macOS/Linux
   source venv/bin/activate
   ```

2. Install dependencies:

   ```sh
   pip install -r requirements.txt
   ```

3. Copy `env.example` to `.env` and configure all required variables:

   ```sh
   cp env.example .env
   ```

4. Run the API server (from the repository root):

   ```sh
   uvicorn backend.server.main:app --reload
   ```

### Frontend Setup

1. Navigate to the frontend directory:

   ```sh
   cd frontend
   ```

2. Install dependencies:

   ```sh
   npm install
   ```

3. Copy `env.example` to `.env` and configure Firebase:

   ```sh
   cp env.example .env
   ```

4. Start the development server:

   ```sh
   npm run dev
   ```

The frontend expects the backend at `VITE_API_BASE_URL` (default `http://localhost:8000`).

## Environment Variables

### Backend (`backend/.env`)

| Variable | Description | Example |
|----------|-------------|---------|
| `APP_NAME` | Application name | `MYGeranHub API` |
| `APP_ENV` | Environment (local/production) | `local` |
| `FIREBASE_PROJECT_ID` | Firebase project ID | `mygeranhub-xxxxx` |
| `FIREBASE_CREDENTIALS_PATH` | Path to service account JSON | `serviceAccountKey.json` |
| `FIREBASE_CREDENTIALS_JSON` | Service account JSON (alternative) | `{...}` |
| `JAMAI_BASE_URL` | JamAI Base API URL | `https://api.jamaibase.com` |
| `JAMAI_PROJECT_ID` | JamAI project ID | `your-project-id` |
| `JAMAI_API_KEY` | JamAI API key/PAT | `pat_xxxxx` |
| `JAMAI_SCRAP_RESULT_TABLE_ID` | Action table for scraped grants | `scrap_result` |
| `JAMAI_GRANTS_TABLE_ID` | Knowledge table for verified grants | `grants` |
| `JAMAI_KNOWLEDGE_SYNC_STATUS_COL` | Sync status column name | `knowledge_sync_status` |
| `JAMAI_KNOWLEDGE_EMBEDDING_MODEL` | Embedding model for knowledge table | `ellm/text-embedding-3-large` |
| `GEMINI_API_KEY` | Google Gemini API key | `AIza...` |
| `GEMINI_MODEL` | Gemini model name | `gemini-2.0-flash` |
| `OPENAI_API_KEY` | OpenAI API key | `sk-...` |
| `OPENAI_MODEL` | OpenAI model name | `o4-mini` |
| `FRONTEND_ORIGINS` | Allowed CORS origins | `http://localhost:5173` |

### Frontend (`frontend/.env`)

| Variable | Description |
|----------|-------------|
| `VITE_API_BASE_URL` | Backend API URL |
| `VITE_FIREBASE_API_KEY` | Firebase web API key |
| `VITE_FIREBASE_AUTH_DOMAIN` | Firebase auth domain |
| `VITE_FIREBASE_PROJECT_ID` | Firebase project ID |
| `VITE_FIREBASE_APP_ID` | Firebase app ID |
| `VITE_FIREBASE_MESSAGING_SENDER_ID` | Firebase messaging sender ID |

## Grant Discovery Pipeline

### How It Works

1. **Chat Routing**: User messages are first processed by the `User_Chat_Agent` chat table:
   - If the message contains grant-related intent → triggers `<<REDIRECT_TO_SEARCH>>` token
   - Otherwise → responds as a general consultant

2. **Grant Search Workflow**: When triggered, the multi-stage flow begins:
   - **Input Guardrail** (`Input_Guardrail` table): Classifies user input as `VALID_ANSWER`, `GIBBERISH`, `INTERRUPTION`, or `EXIT_INTENT`
   - **First Grant Analysis** (`First_Grant` table): Analyzes business profile and generates follow-up questions
   - **Final Grant** (`Final_Grant` table): When enough info is gathered, performs RAG-based grant matching

3. **Agent 1 - Web Scraper** (`agent1.py`):
   - Uses Gemini AI to discover and scrape Malaysian government grants
   - Stores structured grant data in the `scrap_result` action table
   - Runs daily via `grant_pipeline_worker` or on-demand

4. **Agent 2 - Verification** (`agent2.py`):
   - Uses OpenAI to verify scraped grant information
   - Updates `grant_verified` and `grant_final` columns
   - Validates claims against source URLs

5. **Grant Decider** (LLM column in `scrap_result`):
   - Evaluates if verified grants are ready for knowledge sync
   - Outputs `proceed to knowledge table sync` or failure reason

6. **Knowledge Sync** (`grant_sync.py`):
   - Transfers approved grants from action table to knowledge table
   - Creates embeddings for semantic search
   - Updates sync status to prevent reprocessing

### Required JamAI Table Schema

#### `scrap_result` Action Table

| Column | Type | Description |
|--------|------|-------------|
| `grant_scrap` | text | Raw scraped JSON from Agent 1 |
| `grant_verified` | text (LLM) | Verification results from Agent 2 |
| `grant_final` | text (LLM) | Final verified JSON or "failed to verify" |
| `grant_decider` | text (LLM) | Sync decision (see prompt below) |
| `knowledge_sync_status` | text | Sync status: pending/synced/failed/skipped |

#### `grants` Knowledge Table

The sync service auto-creates this table with:
- `grant_name` - Official grant name
- `grant_period` - Application period
- `grant_description` - Full description
- `eligibility_criteria` - Who can apply
- `application_steps` - How to apply
- `document_required` - Required documents
- Corresponding `*_embed` columns for semantic search

### Grant Decider Prompt

Copy this prompt to the `grant_decider` column configuration in JamAI:

```
Table name: "scrap_result"

grant_scrap: ${grant_scrap}
grant_verified: ${grant_verified}
grant_final: ${grant_final}

Based on the available information, provide an appropriate response for the column "grant_decider".

Rules:
1. If `grant_final` already contains a verified JSON object that follows the structure
   {grantName, period, grantDescription, applicationProcess, requiredDocuments},
   respond with the exact text: proceed to knowledge table sync
2. If `grant_final` equals the string "failed to verify" (case-insensitive) or is missing required fields,
   respond with a short factual explanation quoting the problematic field(s).
3. Use only the evidence provided in grant_scrap, grant_verified, and grant_final.
4. Do not hallucinate, add pleasantries, or include markdown. Return a single sentence.
5. Remember that you act as a single spreadsheet cell; stay concise.
```

**Model Configuration:**
- Model: `ellm/qwen/qwen3-30b-a3b-2507`
- Temperature: `0.0`
- Max Tokens: `200`
- Top-p: `0.1`

## Workers

### Grant Pipeline Worker (Full Orchestration)

Runs the complete flow: Scrape → Verify → Wait for Decider → Sync

```sh
# Run once immediately
python -m backend.server.workers.grant_pipeline_worker --once

# Run as daily scheduler (default 03:30 local time)
python -m backend.server.workers.grant_pipeline_worker --hour 3 --minute 30

# With options
python -m backend.server.workers.grant_pipeline_worker \
  --hour 3 \
  --minute 30 \
  --limit 50 \
  --max-candidates 15 \
  --verbose
```

### Grant Sync Worker (Knowledge Sync Only)

Just syncs verified grants to the knowledge table:

```sh
# Run once immediately
python -m backend.server.workers.grant_sync_worker --once

# Run as daily scheduler (default 04:00 local time)
python -m backend.server.workers.grant_sync_worker --hour 4 --minute 0

# With options
python -m backend.server.workers.grant_sync_worker \
  --hour 4 \
  --minute 0 \
  --limit 50 \
  --verbose
```

### Deploying Workers

Workers handle SIGINT/SIGTERM for graceful shutdowns. Deploy using:
- **systemd** (Linux)
- **PM2** (Node.js process manager)
- **Supervisor** (Python)
- **Container orchestrators** (Docker, Kubernetes)

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Verify Firebase token |

### Chat

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jamai/session` | Create chat session for user |
| POST | `/jamai/message` | Send message (routes to chat or grant search) |
| POST | `/jamai/reset` | Reset user's chat session |

### Grant Sync

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/jamai/sync-grants?limit=N` | Trigger knowledge sync (1-100 rows) |

**Example:**

```sh
curl -X POST "https://your-backend/jamai/sync-grants?limit=50" \
  -H "Authorization: Bearer <service-token>"
```

**Response:**

```json
{
  "processed": 10,
  "synced": 8,
  "failed": 1,
  "skipped": 1
}
```

## Health Check

```sh
curl http://localhost:8000/health
# {"status": "ok"}
```

## Troubleshooting

### Common Issues

1. **JamAI API errors**: Ensure `JAMAI_BASE_URL` doesn't include `/api/v2` - the SDK adds it automatically.

2. **Firebase auth failures**: Check that the service account JSON is valid and has correct permissions.

3. **Quota limits (Gemini)**: Agent 1 implements retry logic with exponential backoff. Reduce `--max-candidates` if hitting limits.

4. **Missing columns**: The sync service auto-provisions `knowledge_sync_status` and knowledge table columns if missing.

5. **Grant final validation**: Ensure `grant_final` contains valid JSON or the literal string `failed to verify`.

### Debug Logs

The pipeline worker writes observability logs to `debug_grant_manager.log` at the project root.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## License

MIT License
