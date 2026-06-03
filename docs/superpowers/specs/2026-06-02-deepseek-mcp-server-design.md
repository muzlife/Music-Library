# DeepSeek MCP 서버 설계

**날짜**: 2026-06-02  
**목적**: Claude Code가 DeepSeek을 코드 생성/수정 도구로 호출하는 로컬 MCP 서버 구축

---

## 개요

Claude가 기획/설계/검수를 담당하고, DeepSeek이 실제 코드 생성·수정·리팩토링·테스트 작성을 담당하는 분업 워크플로우를 구현한다. Claude Code의 MCP(Model Context Protocol) stdio 방식으로 통합한다.

---

## 아키텍처

```
Claude Code
    │
    │ MCP (stdio)
    ▼
mcp-deepseek/
├── server.py          # MCP 서버 진입점 (stdio 통신)
├── tools.py           # DeepSeek 도구 정의
└── requirements.txt   # mcp, openai 패키지
    │
    │ HTTP (OpenAI 호환 API)
    ▼
api.deepseek.com
```

- **위치**: 프로젝트 루트 `mcp-deepseek/` 서브디렉토리. FastAPI 앱(`app/`)과 완전히 분리.
- **등록**: `.claude/settings.json`에 프로젝트 로컬 MCP 서버로 등록. 이 프로젝트 안에서만 활성화.
- **API 키**: 기존 `.env.local`에 `DEEPSEEK_API_KEY=...` 추가. 별도 설정 파일 없음.

---

## MCP 도구 목록

| 도구명 | 입력 | 출력 | 용도 |
|--------|------|------|------|
| `deepseek_generate` | spec (요구사항 문자열), language | 생성된 코드 | 새 코드 작성 |
| `deepseek_modify` | code (기존 코드), instruction (수정 지시) | 수정된 코드 | 버그 수정/기능 추가 |
| `deepseek_refactor` | code (기존 코드), goal (목표) | 리팩토링된 코드 | 구조 개선 |
| `deepseek_write_tests` | code (대상 코드) | pytest 테스트 코드 | 테스트 작성 |

**모델 선택**:
- 기본: `deepseek-chat` (추론 포함 범용, 코드 작업 포함)
- 구현 시 DeepSeek 공식 문서에서 현재 사용 가능한 모델명 확인 필요 (`deepseek-coder`는 deprecated 가능성 있음)

**컨텍스트 주입**: 모든 도구 호출 시 system prompt에 프로젝트 컨텍스트 자동 포함.
```
이 프로젝트는 FastAPI 0.115 기반 음반 라이브러리 관리 콘솔입니다.
언어: Python 3.11+, 데이터 검증: Pydantic v2, DB: SQLite (WAL 모드)
코드 스타일: 타입 힌트 필수, 주석 최소화, 함수 단일 책임 원칙
```

---

## 데이터 흐름

```
1. Claude → 요구사항 분석 및 spec 작성
2. Claude → deepseek_* 도구 호출 (MCP)
3. MCP 서버 → DeepSeek API 요청 (OpenAI 호환, base_url=https://api.deepseek.com)
4. DeepSeek → 코드 생성/수정 결과 반환
5. MCP 서버 → 마크다운 코드블록으로 래핑해 Claude에 반환
6. Claude → 결과 검수 후 Edit/Write 도구로 파일 적용, 또는 수정 재요청
```

---

## 에러 처리

| 상황 | 처리 방식 |
|------|-----------|
| `DEEPSEEK_API_KEY` 없음 | 서버 시작 시 즉시 오류 출력, 도구 비활성화 |
| API 타임아웃 | 30초 타임아웃, 에러 메시지 반환 (재시도는 Claude 판단) |
| 응답에 코드 없음 | raw 응답 그대로 반환 (Claude가 해석) |
| API 호출 실패 | HTTP 상태코드 + 메시지를 MCP 에러로 전달 |

---

## 보안

- API 키는 환경변수로만 주입, 코드 하드코딩 금지
- MCP 서버는 로컬 stdio 통신만 사용 (네트워크 포트 없음)
- `.env.local`은 `.gitignore`에 이미 등록되어 있음

---

## 설치 및 등록 절차

```bash
# 1. 의존성 설치
cd mcp-deepseek
pip install -r requirements.txt

# 2. API 키 추가 (.env.local)
echo "DEEPSEEK_API_KEY=your-key-here" >> ../.env.local

# 3. Claude Code에 MCP 서버 등록 (.claude/settings.json)
# mcpServers 항목에 deepseek-coder 서버 추가
```

`.claude/settings.json` 등록 형태:
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

> Claude Code의 `settings.json` env 블록은 `${VAR}` 치환을 지원하지 않는다.
> 대신 `server.py`가 시작 시 프로젝트 루트의 `.env.local`을 직접 파싱해서 `DEEPSEEK_API_KEY`를 읽는다.

---

## 파일 구조

```
mcp-deepseek/
├── server.py          # MCP 서버 진입점, 도구 등록 및 stdio 루프
├── tools.py           # 도구별 DeepSeek 호출 로직
└── requirements.txt   # mcp>=1.0, openai>=1.0
```
