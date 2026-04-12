# Log-Based Monitoring Agent

This folder contains a lightweight, production-style Python log collection agent.

## Features

- tails multiple log files without rereading the full file
- batches logs before sending to a backend `/logs` endpoint
- retries with exponential backoff when the backend is unavailable
- keeps a durable local SQLite queue so unsent logs survive restart
- tracks file offsets to avoid duplicate ingestion
- detects truncation and log rotation, then reopens files automatically
- supports optional `ERROR` / `WARN` filtering

## Structure

- `config.py` loads YAML configuration
- `reader.py` tails log files and handles rotation
- `sender.py` batches and sends logs
- `storage.py` persists checkpoints and buffered logs
- `main.py` runs the agent loop
- `config.example.yaml` shows the expected configuration

## Run

```bash
cd Agent
python -m pip install -e .
copy config.example.yaml config.yaml
python main.py --config config.yaml
```

## Payload

The agent sends logs with this JSON shape:

```json
{
  "agent_id": "agent-dev-001",
  "logs": ["log line 1", "log line 2"]
}
```

## Notes

- By default, the first startup begins tailing from the end of each file.
- Buffered logs are stored in `state_db_path` until the backend accepts them.
- The backend should expose `POST /logs`.
