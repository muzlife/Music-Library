from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "mcp-deepseek"))

from tools import (
    _load_api_key,
    deepseek_generate,
    deepseek_modify,
    deepseek_refactor,
    deepseek_write_tests,
)


def test_load_api_key_from_env():
    with patch.dict(os.environ, {"DEEPSEEK_API_KEY": "test-key-from-env"}):
        assert _load_api_key() == "test-key-from-env"


def test_load_api_key_missing_raises(tmp_path):
    env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        with patch("tools._ENV_PATH", tmp_path / ".env.local"):
            with pytest.raises(RuntimeError, match="DEEPSEEK_API_KEY not found"):
                _load_api_key()


def test_load_api_key_from_env_file(tmp_path):
    env_file = tmp_path / ".env.local"
    env_file.write_text("DEEPSEEK_API_KEY=key-from-file\n")
    env = {k: v for k, v in os.environ.items() if k != "DEEPSEEK_API_KEY"}
    with patch.dict(os.environ, env, clear=True):
        with patch("tools._ENV_PATH", env_file):
            assert _load_api_key() == "key-from-file"


@patch("tools._call")
def test_deepseek_generate_calls_api(mock_call):
    mock_call.return_value = "def hello(): return 'world'"
    result = deepseek_generate("simple hello function", "python")
    assert result == "def hello(): return 'world'"
    mock_call.assert_called_once()
    prompt = mock_call.call_args[0][0]
    assert "python" in prompt
    assert "simple hello function" in prompt


@patch("tools._call")
def test_deepseek_modify_calls_api(mock_call):
    mock_call.return_value = "def hello(name): return f'hello {name}'"
    result = deepseek_modify("def hello(): pass", "이름 파라미터 추가")
    assert "hello" in result
    mock_call.assert_called_once()
    prompt = mock_call.call_args[0][0]
    assert "이름 파라미터 추가" in prompt
    assert "def hello(): pass" in prompt


@patch("tools._call")
def test_deepseek_refactor_calls_api(mock_call):
    mock_call.return_value = "def process(data): return [x for x in data]"
    result = deepseek_refactor("for loop code", "리스트 컴프리헨션으로 변경")
    assert result == "def process(data): return [x for x in data]"
    mock_call.assert_called_once()
    prompt = mock_call.call_args[0][0]
    assert "리스트 컴프리헨션으로 변경" in prompt


@patch("tools._call")
def test_deepseek_write_tests_calls_api(mock_call):
    mock_call.return_value = "def test_hello():\n    assert hello() == 'world'"
    result = deepseek_write_tests("def hello(): return 'world'")
    assert "def test_" in result
    mock_call.assert_called_once()
    prompt = mock_call.call_args[0][0]
    assert "def hello(): return 'world'" in prompt
    assert "pytest" in prompt
