# 앨범 리뷰 표시 기능 설계

## 목표

미디어>검색 탭에서 아이템을 선택했을 때 우측 패널의 운영 플러그인 섹션 바로 아래에 앨범 리뷰를 표시한다. 긴 리뷰는 3줄(약 150자)까지 미리보기를 보여주고, 펼치기 버튼으로 전체 텍스트를 확인할 수 있다.

## 아키텍처

### 변경 파일

| 파일 | 변경 내용 |
|------|-----------|
| `app/db/operator_search.py` | 검색 쿼리에 `review_text`, `review_source` 컬럼 추가 |
| `app/schemas.py` | 검색 결과 스키마에 `review_text`, `review_source` 필드 추가 (optional) |
| `app/static/index.html` | `renderAlbumReviewSection()` 신규 함수 + `renderMediaSearchContextSelection()` 내 삽입 |

### 데이터 흐름

```
사용자가 검색 결과 아이템 클릭
  → operator_search.py 쿼리 (album_master JOIN 시 review_text, review_source 포함)
  → 검색 결과 JSON에 review_text, review_source 포함
  → renderMediaSearchContextSelection(item) 호출
  → renderOpsPluginSection() 렌더링
  → renderAlbumReviewSection(item) 렌더링 (운영 플러그인 섹션 바로 아래)
```

## 백엔드 변경

### operator_search.py

`album_master` JOIN 쿼리에서 `am.review_text`, `am.review_source` 컬럼을 SELECT에 추가한다. 해당 컬럼이 없는 경우(`NULL`) 그대로 반환한다.

### schemas.py

검색 결과 아이템 스키마에 아래 필드를 추가한다:

```python
review_text: str | None = None
review_source: str | None = None
```

## 프론트엔드 변경

### renderAlbumReviewSection(item)

```
입력: item (검색 결과 아이템 객체)
조건: item.review_text가 null/빈 문자열이면 빈 문자열 반환 (섹션 숨김)
조건: item.master_id가 없으면 빈 문자열 반환

렌더링:
  - 섹션 제목: "앨범 리뷰"
  - review_text 150자 이하: 전체 표시, 버튼 없음
  - review_text 150자 초과: 150자까지 표시 + [펼치기 ▼] 버튼
  - review_source가 있으면: "출처: {review_source}" 텍스트 표시
  - review_source가 없으면: 출처 라인 숨김
```

### 펼치기/접기 동작

- `[펼치기 ▼]` 클릭 → 전체 텍스트 표시, 버튼 텍스트 `[접기 ▲]`로 변경
- `[접기 ▲]` 클릭 → 150자 미리보기로 복귀
- 다른 아이템 클릭 시 접힌 상태(미리보기)로 초기화

### renderMediaSearchContextSelection() 삽입 위치

```javascript
// 기존 순서
renderOpsPluginSection(item)
// 신규 삽입
renderAlbumReviewSection(item)
// 기존 이후
현재 위치 details ...
```

## 예외 처리

| 케이스 | 처리 |
|--------|------|
| `review_text` null / 빈 문자열 | 섹션 전체 숨김 |
| `review_source` null | 출처 라인 숨김 (텍스트만 표시) |
| `master_id` 없는 아이템 (굿즈 등) | 섹션 숨김 |
| 150자 이하 리뷰 | 버튼 없이 전체 표시 |

## 테스트 전략

### 백엔드

- `operator_search.py` 쿼리 결과에 `review_text`, `review_source` 컬럼 포함 여부 단위 테스트

### 프론트엔드 (수동 검증)

| 시나리오 | 확인 항목 |
|----------|-----------|
| 리뷰 없는 아이템 클릭 | 리뷰 섹션 미표시 |
| 150자 이하 리뷰 아이템 클릭 | 전체 텍스트 표시, 버튼 없음 |
| 150자 초과 리뷰 아이템 클릭 | 미리보기 + [펼치기 ▼] 버튼 표시 |
| [펼치기] 클릭 | 전체 텍스트 + [접기 ▲] 버튼 |
| 다른 아이템 클릭 | 이전 리뷰 섹션 초기화 |
| 출처 없는 리뷰 | 출처 라인 미표시 |
