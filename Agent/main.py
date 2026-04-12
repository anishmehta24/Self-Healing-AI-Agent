from __future__ import annotations

import argparse
import signal
import sys
import time

from config import AgentConfig, load_config
from reader import LogReader
from sender import LogSender
from storage import StateStore


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the log-based monitoring agent.")
    parser.add_argument(
        "--config",
        default="config.yaml",
        help="Path to the YAML configuration file.",
    )
    return parser


def run_agent(config: AgentConfig) -> None:
    store = StateStore(config.state_db_path)
    readers = [LogReader(path, config, store) for path in config.log_paths]
    sender = LogSender(config, store)
    running = True

    def stop_handler(*_args) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    sender.start()
    print(f"Starting agent '{config.agent_id}' for {len(readers)} log file(s).")

    try:
        while running:
            wrote_logs = False
            for reader in readers:
                result = reader.poll()
                if result.lines and result.fingerprint:
                    store.append_logs_and_checkpoint(
                        path=str(reader.path),
                        fingerprint=result.fingerprint,
                        offset=result.offset,
                        log_lines=result.lines,
                    )
                    wrote_logs = True
                elif result.fingerprint:
                    store.save_checkpoint(str(reader.path), result.fingerprint, result.offset)

            if wrote_logs:
                sender.notify_new_logs()

            time.sleep(config.poll_interval_seconds)
    finally:
        sender.stop()
        print("Agent stopped.")


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    try:
        config = load_config(args.config)
    except Exception as exc:  # pragma: no cover - defensive CLI behavior
        print(f"Failed to load config: {exc}", file=sys.stderr)
        return 1

    run_agent(config)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
