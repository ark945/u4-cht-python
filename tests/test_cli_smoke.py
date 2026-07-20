"""CLI 冒煙測試 — 確認 package 可 import、CLI 可執行、版本可讀。"""

from __future__ import annotations

from click.testing import CliRunner

from u4cht import __version__
from u4cht.cli import main


def test_version_matches() -> None:
    assert __version__.startswith("0.")


def test_cli_info_runs() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["info"])
    assert result.exit_code == 0
    assert "Phase 0" in result.output


def test_cli_version_flag() -> None:
    runner = CliRunner()
    result = runner.invoke(main, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output
