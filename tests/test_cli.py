"""Smoke tests for the CLI module."""

from typer.testing import CliRunner

from graphmem.cli import app

runner = CliRunner()


def test_help():
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "graphmem" in result.output.lower() or "Graph" in result.output


def test_init_help():
    result = runner.invoke(app, ["init", "--help"])
    assert result.exit_code == 0


def test_add_help():
    result = runner.invoke(app, ["add", "--help"])
    assert result.exit_code == 0
    assert "content" in result.output.lower() or "CONTENT" in result.output


def test_query_help():
    result = runner.invoke(app, ["query", "--help"])
    assert result.exit_code == 0


def test_status_help():
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0


def test_export_help():
    result = runner.invoke(app, ["export", "--help"])
    assert result.exit_code == 0
