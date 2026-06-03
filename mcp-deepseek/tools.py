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
