"""CLI entrypoint to execute the ingestion pipeline locally."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ingestion.config import AppConfig, DEFAULT_CONFIG
from ingestion.pipeline import IngestionPipeline


def load_env_file(env_path: str = ".env") -> None:
    """Load environment variables from .env file."""
    env_file = Path(ROOT) / env_path
    if not env_file.exists():
        logging.debug(f"Environment file not found: {env_path}")
        return

    logging.info(f"Loading environment from: {env_path}")
    with open(env_file) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                # Only set if not already in environment
                if key.strip() not in os.environ:
                    os.environ[key.strip()] = value.strip()


def expand_env_vars(data: dict | list | str) -> dict | list | str:
    """Recursively expand ${VAR} and $VAR references in config."""
    if isinstance(data, dict):
        return {key: expand_env_vars(value) for key, value in data.items()}
    elif isinstance(data, list):
        return [expand_env_vars(item) for item in data]
    elif isinstance(data, str):
        # Match ${VAR} or $VAR patterns
        def replacer(match):
            var_name = match.group(1) or match.group(2)
            return os.environ.get(var_name, match.group(0))

        return re.sub(r'\$\{(\w+)\}|\$(\w+)', replacer, data)
    else:
        return data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the ingestion pipeline")
    parser.add_argument(
        "--config",
        type=Path,
        help="Optional path to a JSON config file overriding defaults",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
        help="Verbosity for logging output",
    )
    parser.add_argument(
        "--env-file",
        default=".env",
        help="Path to .env file (default: .env)",
    )
    return parser.parse_args()


def load_config(path: Path | None) -> AppConfig:
    if not path:
        return DEFAULT_CONFIG
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    # Load JSON and expand environment variables
    with open(path) as f:
        raw_config = json.load(f)

    expanded_config = expand_env_vars(raw_config)
    return AppConfig.from_dict(expanded_config)


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    # Load environment variables from .env file
    load_env_file(args.env_file)

    config = load_config(args.config)
    pipeline = IngestionPipeline(config)
    results = pipeline.run()
    for result in results:
        logging.info(
            "Connector %s processed %d documents",
            result.connector_name,
            result.processed_documents,
        )


if __name__ == "__main__":
    main()
