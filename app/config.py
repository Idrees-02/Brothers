"""Application-wide paths and constants."""

import os
import sys
from pathlib import Path

APP_NAME = "Brothers"


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def data_dir() -> Path:
    """Directory where the SQLite database file lives.

    On Windows this resolves to %APPDATA%\\Brothers so the data survives
    reinstalls/updates of the packaged app. On macOS/Linux (dev environment)
    it falls back to a ./data folder next to the project so nothing is
    written outside the repo during development.
    """
    appdata = os.environ.get("APPDATA")
    if appdata:
        path = Path(appdata) / APP_NAME
    else:
        path = Path(__file__).resolve().parent.parent / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def db_path() -> Path:
    return data_dir() / "brothers.db"


def resources_dir() -> Path:
    return Path(__file__).resolve().parent / "resources"
