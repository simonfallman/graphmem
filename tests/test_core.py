"""Tests for config and core module."""

from graphmem.config import DBBackend, EmbedderProvider, LLMProvider, Settings


def test_default_settings():
    """Test that default settings are sensible."""
    s = Settings(
        _env_file=None,  # Don't load from disk
    )
    assert s.db_backend == DBBackend.kuzu
    assert s.embedder == EmbedderProvider.openai
    assert s.llm == LLMProvider.openai


def test_settings_resolve_db_path(tmp_path):
    """Test that resolve_db_path creates the parent and returns expanded path."""
    db_path = str(tmp_path / "subdir" / "test_db")
    s = Settings(db_path=db_path, _env_file=None)
    resolved = s.resolve_db_path()
    assert resolved == db_path
    # Parent dir should exist, but db path itself is created by Kuzu
    assert (tmp_path / "subdir").is_dir()
