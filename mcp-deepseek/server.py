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
