"""Utility helpers for GraphMem."""

from __future__ import annotations

from pathlib import Path


def get_graphmem_home() -> Path:
    """Return the GraphMem home directory (~/.graphmem)."""
    home = Path.home() / ".graphmem"
    home.mkdir(parents=True, exist_ok=True)
    return home


def get_env_path() -> Path:
    """Return the path to the .env file."""
    return get_graphmem_home() / ".env"
