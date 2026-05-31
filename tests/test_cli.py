"""CLI 测试"""

import pytest
from click.testing import CliRunner

from src.cli import main


def test_cli_help():
    """测试 CLI 帮助信息"""
    runner = CliRunner()
    result = runner.invoke(main, ["--help"])
    assert result.exit_code == 0
    assert "EK80" in result.output


def test_cli_run_help():
    """测试 run 子命令帮助"""
    runner = CliRunner()
    result = runner.invoke(main, ["run", "--help"])
    assert result.exit_code == 0
    assert "CONFIG_PATH" in result.output


def test_cli_status_config_not_found():
    """测试 status 命令配置文件不存在"""
    runner = CliRunner()
    result = runner.invoke(main, ["status", "nonexistent.yaml"])
    assert result.exit_code != 0
