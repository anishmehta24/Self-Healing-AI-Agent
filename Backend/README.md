# Self-Healing Production System

Production-style AI DevOps agent prototype built with FastAPI and LangGraph.

## Features

- Stateful graph-based remediation workflow
- Conditional routing and retry loops
- SQLite-backed incident persistence
- Safe-action whitelist with approval gate
- Simulated production incident scenarios
- OpenAI-compatible LLM interface with deterministic fallback

## Run

```bash
pip install -e .
uvicorn app.main:app --reload
```

## Endpoints

- `POST /analyze`
- `POST /simulate`
- `GET /incidents/{incident_id}`
- `POST /incidents/{incident_id}/approve`
- `GET /workflow/diagram`
