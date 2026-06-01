# DeepSeek MCP 서버 구현 계획

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Claude Code가 DeepSeek을 코드 생성/수정 도구로 호출하는 로컬 Python MCP 서버를 구축한다.

**Architecture:** `mcp-deepseek/` 서브디렉토리에 FastMCP 기반 stdio 서버를 구현한다. `tools.py`가 DeepSeek OpenAI 호환 API를 호출하고, `server.py`가 MCP 도구로 노출한다. `.claude/settings.json`에 등록해 이 프로젝트 내에서만 Claude Code 도구로 활성화된다.

**Tech Stack:** Python 3.11+, `mcp>=1.0` (FastMCP), `openai>=1.0` (DeepSeek OpenAI 호환 클라이언트), pytest, unittest.mock

---

## 파일 구조

| 경로 | 역할 |
|------|------|
| `mcp-deepseek/requirements.txt` | 신규 생성 — mcp, openai 의존성 |
| `mcp-deepseek/tools.py` | 신규 생성 — env 로딩 + DeepSeek API 호출 함수 4개 |
| `mcp-deepseek/server.py` | 신규 생성 — FastMCP 서버 진입점, 도구 등록 |
| `tests/test_deepseek_mcp_tools.py` | 신규 생성 — tools.py 유닛 테스트 (API mock) |
| `.claude/settings.json` | 신규 생성 — MCP 서버 등록 |

---

## Task 1: requirements.txt 작성 및 의존성 설치

**Files:**
- Create: `mcp-deepseek/requirements.txt`

- [ ] **Step 1: requirements.txt 작성**

```
mcp>=1.0
openai>=1.0
```

파일 경로: `mcp-deepseek/requirements.txt`

- [ ] **Step 2: 의존성 설치**

```bash
pip install -r mcp-deepseek/requirements.txt
```

Expected: `Successfully installed mcp-... openai-...` (이미 설치되어 있으면 `Requirement already satisfied`)

- [ ] **Step 3: 설치 확인**

```bash
python -c "import mcp; import openai; print('OK')"
```

Expected: `OK`

- [ ] **Step 4: 커밋**

```bash
git add mcp-deepseek/requirements.txt
git commit -m "feat(mcp): add deepseek mcp server requirements"
```

---

## Task 2: tools.py 구현 (TDD)

**Files:**
- Create: `mcp-deepseek/tools.py`
- Test: `tests/test_deepseek_mcp_tools.py`

- [ ] **Step 1: 테스트 파일 작성 (실패 상태)**

`tests/test_deepseek_mcp_tools.py`:

```python
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
```

- [ ] **Step 2: 테스트 실패 확인**

```bash
pytest tests/test_deepseek_mcp_tools.py -v 2>&1 | head -20
```

Expected: `ModuleNotFoundError: No module named 'tools'` (tools.py 없음)

- [ ] **Step 3: tools.py 구현**

`mcp-deepseek/tools.py`:

```python
from __future__ import annotations

import os
from pathlib import Path

from openai import OpenAI

_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_ENV_PATH = _PROJECT_ROOT / ".env.local"

_SYSTEM_PROMPT = (
    "이 프로젝트는 FastAPI 0.115 기반 음반 라이브러리 관리 콘솔입니다.\n"
    "언어: Python 3.11+, 데이터 검증: Pydantic v2, DB: SQLite (WAL 모드)\n"
    "코드 스타일: 타입 힌트 필수, 주석 최소화, 함수 단일 책임 원칙"
)


def _load_api_key() -> str:
    key = os.environ.get("DEEPSEEK_API_KEY", "").strip()
    if key:
        return key
    if _ENV_PATH.is_file():
        for raw in _ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if line.startswith("DEEPSEEK_API_KEY="):
                value = line.split("=", 1)[1].strip().strip("'\"")
                if value:
                    return value
    raise RuntimeError("DEEPSEEK_API_KEY not found in environment or .env.local")


def _call(prompt: str) -> str:
    client = OpenAI(api_key=_load_api_key(), base_url="https://api.deepseek.com")
    response = client.chat.completions.create(
        model="deepseek-chat",
        messages=[
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        timeout=30,
    )
    return response.choices[0].message.content or ""


def deepseek_generate(spec: str, language: str = "python") -> str:
    return _call(f"다음 요구사항에 맞는 {language} 코드를 작성하세요:\n\n{spec}")


def deepseek_modify(code: str, instruction: str) -> str:
    return _call(
        f"다음 코드를 수정하세요.\n\n지시사항: {instruction}\n\n코드:\n```\n{code}\n```"
    )


def deepseek_refactor(code: str, goal: str) -> str:
    return _call(
        f"다음 코드를 리팩토링하세요.\n\n목표: {goal}\n\n코드:\n```\n{code}\n```"
    )


def deepseek_write_tests(code: str) -> str:
    return _call(
        f"다음 코드에 대한 pytest 테스트 코드를 작성하세요:\n\n```python\n{code}\n```"
    )
```

- [ ] **Step 4: 테스트 통과 확인**

```bash
pytest tests/test_deepseek_mcp_tools.py -v
```

Expected: `7 passed`

- [ ] **Step 5: 커밋**

```bash
git add mcp-deepseek/tools.py tests/test_deepseek_mcp_tools.py
git commit -m "feat(mcp): add deepseek tools with unit tests"
```

---

## Task 3: server.py 구현

**Files:**
- Create: `mcp-deepseek/server.py`

- [ ] **Step 1: server.py 작성**

`mcp-deepseek/server.py`:

```python
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tools
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("deepseek-coder")


@mcp.tool()
def deepseek_generate(spec: str, language: str = "python") -> str:
    """요구사항(spec)에 맞는 코드를 생성합니다."""
    return tools.deepseek_generate(spec, language)


@mcp.tool()
def deepseek_modify(code: str, instruction: str) -> str:
    """기존 코드를 지시사항에 따라 수정합니다."""
    return tools.deepseek_modify(code, instruction)


@mcp.tool()
def deepseek_refactor(code: str, goal: str) -> str:
    """코드를 목표에 맞게 리팩토링합니다."""
    return tools.deepseek_refactor(code, goal)


@mcp.tool()
def deepseek_write_tests(code: str) -> str:
    """코드에 대한 pytest 테스트를 작성합니다."""
    return tools.deepseek_write_tests(code)


if __name__ == "__main__":
    mcp.run()
```

- [ ] **Step 2: 구문 검사**

```bash
python -m py_compile mcp-deepseek/server.py && echo OK
```

Expected: `OK`

- [ ] **Step 3: import 확인 (API 키 없어도 import는 성공해야 함)**

```bash
python -c "
import sys
sys.path.insert(0, 'mcp-deepseek')
from mcp.server.fastmcp import FastMCP
import tools
print('import OK')
"
```

Expected: `import OK`

- [ ] **Step 4: 커밋**

```bash
git add mcp-deepseek/server.py
git commit -m "feat(mcp): add fastmcp server entrypoint"
```

---

## Task 4: .claude/settings.json에 MCP 서버 등록

**Files:**
- Create: `.claude/settings.json`

> 현재 `.claude/settings.local.json`은 존재하지만 `settings.json`은 없다.
> `settings.json`은 git에 커밋되는 프로젝트 공유 설정이다.

- [ ] **Step 1: settings.json 작성**

`.claude/settings.json`:

```json
{
  "mcpServers": {
    "deepseek-coder": {
      "command": "python",
      "args": ["mcp-deepseek/server.py"]
    }
  }
}
```

> `command: "python"`은 Claude Code가 실행할 때의 PATH 기준이다.
> venv를 사용하는 경우 `python` 대신 `.venv/bin/python`으로 변경한다.

- [ ] **Step 2: venv 여부 확인 및 command 조정**

```bash
ls .venv/bin/python 2>/dev/null && echo "USE .venv/bin/python" || echo "USE python"
```

`USE .venv/bin/python`이 출력되면 `settings.json`의 `command`를 `.venv/bin/python`으로 수정한다.

- [ ] **Step 3: Claude Code 재시작 후 MCP 서버 확인**

Claude Code 터미널에서:
```
/mcp
```

Expected: `deepseek-coder` 서버가 목록에 표시되고, 4개 도구(`deepseek_generate`, `deepseek_modify`, `deepseek_refactor`, `deepseek_write_tests`)가 나열됨

- [ ] **Step 4: 커밋**

```bash
git add .claude/settings.json
git commit -m "feat(mcp): register deepseek-coder mcp server in project settings"
```

---

## Task 5: API 키 등록 및 엔드투엔드 동작 확인

> 이 태스크는 코드 변경이 없다. `.env.local`은 git에 추적되지 않으므로 별도 커밋 없음.

- [ ] **Step 1: .env.local에 API 키 추가**

`.env.local` 파일에 아래 줄 추가 (파일이 이미 존재함):

```
DEEPSEEK_API_KEY=<실제 DeepSeek API 키>
```

- [ ] **Step 2: 도구 직접 호출로 연결 확인**

```bash
python -c "
import sys
sys.path.insert(0, 'mcp-deepseek')
import tools
result = tools.deepseek_generate('return the string hello', 'python')
print(result[:200])
"
```

Expected: `def ...` 또는 `hello` 포함 Python 코드가 출력됨 (API 키가 유효하면 성공)

- [ ] **Step 3: Claude Code에서 도구 호출 확인**

Claude Code 대화창에서:
```
deepseek_generate 도구로 'SQLite에서 단일 레코드를 id로 조회하는 Python 함수' 생성해줘
```

Expected: DeepSeek이 생성한 Python 코드가 반환되고, Claude가 검수 후 응답함

---

## 완료 기준

- [ ] `pytest tests/test_deepseek_mcp_tools.py` 전체 통과
- [ ] `/mcp` 명령으로 `deepseek-coder` 서버와 4개 도구 확인
- [ ] `deepseek_generate` 실제 호출 시 DeepSeek 응답 수신 확인
