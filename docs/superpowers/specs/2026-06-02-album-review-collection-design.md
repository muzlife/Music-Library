# 앨범 리뷰 수집 기능 설계

## 목표

`album_master`에 리뷰 텍스트를 수집·저장하는 파이프라인을 구축한다. 배치(Wikipedia 자동)와 개별(URL 입력 / 직접 입력)을 모두 지원하고, 영문 텍스트는 DeepSeek API로 한국어 요약 후 저장한다.

---

## 아키텍처

### 파이프라인

```
소스 획득
  A. Wikipedia 자동검색 (버그 수정)
  B. 운영자 URL 입력 (이즘 등 임의 URL)
  C. 운영자 직접 텍스트 입력
      ↓
텍스트 추출 (BeautifulSoup) — A·B 경로만
      ↓
DeepSeek 처리 (한국어 요약 300자 이내) — A·B 경로만
  ※ 이미 한국어인 경우 번역 생략, 요약만
      ↓
album_master 저장
  review_text  (한국어 요약 또는 직접 입력 텍스트)
  review_source (WIKIPEDIA / 도메인 / MANUAL)
  review_url   (원본 URL, C 경로는 NULL)
```

### 변경 파일

| 파일 | 역할 |
|------|------|
| `app/services/providers.py` | Wikipedia 검색 버그 수정, `fetch_review_from_url()` 신규 |
| `app/services/review_pipeline.py` | DeepSeek 요약+번역 파이프라인 (신규) |
| `app/services/deepseek_client.py` | DeepSeek OpenAI 호환 HTTP 클라이언트 (신규) |
| `app/db/album_master_review.py` | 리뷰 저장/조회/배치 쿼리 (신규) |
| `app/api/album_masters.py` | 기존 `/review` 엔드포인트 교체 + 배치 엔드포인트 추가 |
| `app/static/index.html` | 개별 수집 UI + 배치 UI |

---

## 백엔드 설계

### Wikipedia 버그 수정 (`providers.py`)

**현재 버그:** `"{artist} {title} album"` 검색 시 아티스트 Wikipedia 페이지가 상위에 오면 그걸 가져옴.

**수정:** 검색 결과 최대 5개를 보고 페이지 제목에 앨범명이 포함된 결과를 우선 선택. 없으면 `None` 반환 (아티스트 페이지를 리뷰로 반환하지 않음).

```python
# providers.py — fetch_wikipedia_album_review 수정
query = f"{title} {artist} album"
# 검색 결과에서 앨범 페이지 선별
for page in pages[:5]:
    if title.lower() in page["title"].lower():
        page_title = page["title"]
        break
else:
    return None  # 앨범 페이지 없으면 수집 안 함
```

### `fetch_review_from_url(url: str) -> str | None` (신규, `providers.py`)

임의 URL에서 본문 텍스트를 추출한다. 이즘, Wikipedia 등 소스 무관하게 동일 함수 사용.

- httpx로 GET (타임아웃 15초, User-Agent 설정)
- BeautifulSoup으로 `<article>`, `<main>`, `<div class~=content>`, `<p>` 순서로 본문 추출
- 최대 3000자 반환
- 실패 시 `None` 반환

### `review_pipeline.py` (신규)

DeepSeek MCP 도구(`deepseek_generate`)를 호출해 한국어 요약을 생성한다.

```python
def summarize_to_korean(text: str) -> str:
    """영문이면 번역+요약, 한국어면 요약만. 결과 300자 이내."""
```

**프롬프트:**
```
다음 텍스트는 음악 앨범에 관한 글입니다.
한국어로 300자 이내로 요약하세요.
음악적 특징과 평가를 중심으로, 자연스러운 한국어 문어체로 작성하세요.
요약문만 출력하고 다른 설명은 붙이지 마세요.

[텍스트]
{text}
```

**언어 감지:** 한국어 비율(가나·한자 포함)이 30% 이상이면 번역 없이 요약만 수행하도록 프롬프트에 명시.

**DeepSeek 연동:** `app/services/deepseek_client.py`를 통해 OpenAI 호환 API 직접 호출 (MCP가 아닌 HTTP 클라이언트 사용, 배치 처리에서 subprocess 기반 MCP는 부적합).

### `album_master_review.py` (신규)

```python
def get_masters_without_review(conn, limit: int) -> list[dict]
    """review_text IS NULL인 마스터 조회 (id, artist_or_brand, title 반환)"""

def save_review(conn, master_id: int, review_text: str,
                review_source: str, review_url: str | None) -> None
    """review_text, review_source, review_url, updated_at 업데이트"""

def clear_review(conn, master_id: int) -> None
    """review 3개 컬럼 NULL로 초기화"""

def count_masters_without_review(conn) -> int
    """미수집 건수 반환"""
```

### API 엔드포인트 (`album_masters.py`)

| 메서드 | 경로 | 용도 |
|--------|------|------|
| `POST` | `/album-masters/{id}/review/auto` | Wikipedia 자동수집 → DeepSeek → 저장 |
| `POST` | `/album-masters/{id}/review/url` | body: `{"url": "..."}` → fetch → DeepSeek → 저장 |
| `POST` | `/album-masters/{id}/review/manual` | body: `{"text": "...", "source": "..."}` → 저장 (DeepSeek 없음) |
| `DELETE` | `/album-masters/{id}/review` | 리뷰 삭제 |
| `POST` | `/album-masters/review/batch` | 미수집 마스터 50건 Wikipedia 자동수집 |

**배치 응답:**
```json
{
  "processed": 50,
  "succeeded": 42,
  "failed": 8,
  "remaining": 1200
}
```

**기존 `POST /album-masters/{id}/review` 엔드포인트:** 삭제 (위 auto 엔드포인트로 대체).

---

## UI 설계

### 개별 수집 — 미디어>관리 마스터 상세 패널

마스터 상세 편집 영역 하단에 **리뷰 관리 블록** 추가.

**리뷰 없는 상태:**
```
[ 리뷰 ]
  [Wikipedia 자동수집]  [URL 입력]  [직접 입력]
```

**리뷰 있는 상태:**
```
[ 리뷰 ]  출처: WIKIPEDIA  [삭제]
  (리뷰 텍스트 미리보기 2줄)
  [Wikipedia 재수집]  [URL로 교체]  [직접 입력으로 교체]
```

**URL 입력 모드 (인라인 폼):**
```
URL: [_____________________________]  [수집]  [취소]
```

**직접 입력 모드 (인라인 폼):**
```
출처명: [________]
내용:   [                          ]
        [                          ]
[저장]  [취소]
```

- 각 버튼 클릭 시 폼 인라인 표시 (페이지 이동 없음)
- 수집 중 버튼 비활성화 + 로딩 표시
- 성공/실패 인라인 메시지

### 배치 수집 — 메타데이터 동기화 페이지 내 섹션

기존 메타 동기화 탭과 동일한 패턴의 버튼 섹션 추가.

```
[ 앨범 리뷰 자동수집 ]
  리뷰 미수집: N건
  [Wikipedia 자동수집 실행 (50건)]
  마지막 실행: YYYY-MM-DD HH:MM  성공 M건 / 실패 K건
```

- 1회 50건 처리 (Wikipedia API 부하 고려)
- 완료 후 미수집 건수 갱신

---

## 예외 처리

| 케이스 | 처리 |
|--------|------|
| Wikipedia에서 앨범 페이지 못 찾음 | `null` 반환, UI에 "찾을 수 없음" 표시 |
| URL fetch 실패 (타임아웃, 404 등) | 에러 메시지 반환 |
| DeepSeek API 실패 | 원문 텍스트 그대로 저장, review_source는 `WIKIPEDIA_RAW` 또는 `URL_RAW` |
| 배치 중 개별 실패 | 해당 건 skip, 나머지 계속 처리 |
| 이미 리뷰 있는 마스터 (배치 시) | 건너뜀 (덮어쓰기 안 함) |

---

## 테스트 전략

### 백엔드 단위 테스트

| 테스트 | 확인 항목 |
|--------|-----------|
| `test_wikipedia_album_fix` | 아티스트명과 앨범명 입력 시 앨범 페이지 제목이 포함된 결과 선택 |
| `test_wikipedia_no_album_page` | 앨범 페이지 없으면 None 반환 |
| `test_fetch_review_from_url` | HTML mock → 본문 텍스트 추출 |
| `test_review_pipeline_summarize` | DeepSeek mock → 300자 이내 반환 |
| `test_batch_skips_existing` | 리뷰 있는 마스터는 배치에서 제외 |

### 프론트엔드 수동 검증

| 시나리오 | 확인 항목 |
|----------|-----------|
| Wikipedia 자동수집 | 리뷰 카드에 한국어 요약 표시 |
| URL 입력 (이즘 등) | URL fetch → 요약 저장 |
| 직접 입력 | 텍스트 저장, DeepSeek 호출 없음 |
| 삭제 | 리뷰 삭제 후 "없는 상태" UI로 복귀 |
| 배치 실행 | 미수집 건수 감소 확인 |
