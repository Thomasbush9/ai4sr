"""
Runtime settings store — persists user-provided Azure configuration
to data/runtime_settings.json so it survives container restarts.

Settings here take priority over environment variables.
"""
import json
import os
from pathlib import Path

from config import REPO_ROOT

SETTINGS_FILE = Path(os.getenv("DATA_DIR", REPO_ROOT / "data")) / "runtime_settings.json"


def load() -> dict:
    """Load settings from file. Always reads from disk (multi-worker safe)."""
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save(settings: dict) -> None:
    """Atomically write settings to disk."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = SETTINGS_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(settings, f, indent=2)
    os.replace(str(tmp), str(SETTINGS_FILE))
    try:
        os.chmod(SETTINGS_FILE, 0o600)
    except OSError:
        pass


def get(key: str, default=None):
    """Get a single setting value. Returns default if not set."""
    return load().get(key, default)
