# Self-Healing AI Agent

Self-Healing AI Agent is a production-style incident response prototype that combines a FastAPI backend, a LangGraph workflow, and a lightweight React dashboard.

The system simulates how an autonomous DevOps agent can:

- ingest logs
- detect anomalies
- classify the issue type
- analyze likely root cause
- suggest a safe remediation
- request approval when needed
- execute a simulated fix
- validate the outcome
- retry with updated reasoning when the first fix fails

## Project Structure

```text
SELF-HEALING-AI-AGENT/
├── Backend/
└── Frontend/
```

### Backend

The backend is a FastAPI + LangGraph service that manages:

- shared incident state
- conditional workflow routing
- retry loops
- SQLite persistence
- safe-action execution
- approval and resume flow

Main backend entrypoint:

- `Backend/app/main.py`

### Frontend

The frontend is a React + Vite dashboard that lets you:

- run built-in incident simulations
- paste logs for analysis
- inspect incident state and final report
- approve a paused remediation
- view workflow history and diagram output

Main frontend entrypoint:

- `Frontend/src/App.jsx`

## Run Locally

### 1. Start the backend

```bash
cd Backend
python -m pip install -e .
uvicorn app.main:app --reload
```

Backend will be available at:

- `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

### 2. Start the frontend

```bash
cd Frontend
npm install
npm run dev
```

Frontend will be available at:

- `http://127.0.0.1:5173`

## Backend API

Available endpoints:

- `POST /analyze`
- `POST /simulate`
- `GET /incidents/{incident_id}`
- `POST /incidents/{incident_id}/approve`
- `GET /workflow/diagram`

## Notes

- No authentication is added in the current UI.
- The backend uses simulated remediation only; it does not execute real production actions.
- If `OPENAI_API_KEY` is not set, the backend falls back to deterministic diagnosis and fix suggestion logic.

## Testing

Run backend tests with:

```bash
cd Backend
python -m pytest -q -p no:cacheprovider
```
