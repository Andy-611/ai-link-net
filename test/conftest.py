"""Pytest configuration and shared fixtures."""

import os
import tempfile
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolate_fp_home(monkeypatch):
    """自动隔离 FP_HOME，防止测试污染真实环境"""
    with tempfile.TemporaryDirectory() as tmpdir:
        monkeypatch.setenv("FP_HOME", tmpdir)
        yield Path(tmpdir)


@pytest.fixture
def temp_dir():
    """创建临时目录供测试使用"""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)
