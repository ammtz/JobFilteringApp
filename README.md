# JobFilteringApp

A job capture and ranking tool. Capture job postings from LinkedIn (via Chrome extension), store them in a local database, and rank them against your resume using an LLM.

**Stack:** Flask · SQLAlchemy · Alembic · PostgreSQL · OpenAI-compatible LLM

---

## Quick Start

### 1. Start Postgres

```bash
docker-compose up -d
```

### 2. Install backend dependencies

```bash
cd backend
pip install -r requirements.txt
```

### 3. Configure environment

```bash
cp .env.example .env
# Edit .env — add OPENAI_API_KEY if you want LLM features
```

### 4. Run migrations

```bash
# from inside backend/
alembic upgrade head
```

### 5. Start the server

```bash
flask --app app.main run
# or: python -m app.main
```

The server starts at **http://localhost:5000** and serves both the API and the frontend UI.

---

## Chrome Extension

The `extension/` directory contains a Manifest V3 Chrome extension that captures LinkedIn job postings and sends them to your local server.

To load it:
1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked** → select the `extension/` folder

The extension is already configured to talk to `http://localhost:5000`.

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/v1/ingest` | Capture a job posting |
| GET | `/api/v1/jobs` | List all jobs |
| GET | `/api/v1/jobs/<id>` | Get a single job |
| PATCH | `/api/v1/jobs/<id>` | Update a job |
| DELETE | `/api/v1/jobs/<id>` | Delete a job |
| POST | `/api/v1/parse` | Parse job descriptions into structured fields |
| POST | `/api/v1/analyze` | Analyze jobs with LLM (stub if no API key) |
| POST | `/api/v1/resume` | Upload your resume text |
| GET | `/api/v1/resume` | Get resume info |
| POST | `/api/v1/cull` | Rank jobs against resume |

---

## Tests

```bash
cd backend
pytest                     # unit tests only (no DB required)
pytest tests/integration/  # requires Postgres DATABASE_URL in .env
```

---

## LLM Configuration

Works with any OpenAI-compatible API:

```env
# OpenAI
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Local (e.g. Ollama)
OPENAI_BASE_URL=http://localhost:11434/v1
OPENAI_MODEL=llama3
# OPENAI_API_KEY can be empty for local servers
```

Without an API key the analyzer runs in stub mode (deterministic scores, no real LLM calls).
