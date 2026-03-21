"""Configuration module for the sample project."""

import os
from pathlib import Path

DEFAULT_PORT = 8080
CONFIG_PATH = os.getenv("CONFIG_PATH", "config.yaml")


def parse_config(path: str) -> dict:
    """Parse a configuration file and return settings."""
    settings = {}
    raw = Path(path).read_text()
    settings["raw"] = raw
    return settings


def validate_config(config: dict) -> bool:
    """Validate that required keys are present."""
    required = ["host", "port", "debug"]
    for key in required:
        if key not in config:
            return False
    return True
