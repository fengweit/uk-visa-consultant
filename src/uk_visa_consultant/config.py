"""Environment/bootstrap helpers.

Call ``load_env()`` at process start to read ``.env`` into ``os.environ`` before
constructing adapters or clients. Kept separate from the adapters so they stay
env-agnostic and unit-testable.
"""
from __future__ import annotations

from pathlib import Path


def load_env(path: str | Path = ".env") -> None:
    """Load ``.env`` (if present) into the environment; no-op if dotenv missing."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - dotenv is a declared dep
        return
    load_dotenv(path, override=False)
