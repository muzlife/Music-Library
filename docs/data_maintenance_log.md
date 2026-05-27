# 데이터 보정 작업 로그

> 운영 콘솔을 거치지 않고 직접 DB/코드에 적용된 보정 작업들을 기록합니다.
> 이후 유사 작업 시 참조하며, 작업 내역 추적 및 회귀 방지를 목적으로 합니다.

---

## 작업 내역

### 1. 미디어타입 정규화 (2026-05-16)

**파일**: `fix_media.sql`, `fix_media_all.sql`

| 내용 | SQL |
|------|-----|
| `media_type = 'LP'` → `'Vinyl'` 로 일괄 변경 | `fix_media.sql` |
| `media_type = 'DIGITAL'` → `'CD'` 로 일괄 변경 | `fix_media_all.sql` |
| 기타 비정규 값 확인용 쿼리 | `query.sql`, `query2.sql`, `query_all_blank.sql`, `query_check.sql` |

**배경**: 미디어타입 드롭다운 도입 후 기존 데이터의 media_type 값을 새 분류체계에 맞춤

---

### 2. CD 미디어타입 누락 조회 (2026-05-16)

**파일**: `get_remaining_cds.sql`

CD 카테고리인데 media_type이 NULL/공백인 항목 조회 (약 135건)

---

### 3. 마스터 편집 패치 (2026-04-29 ~ 2026-05-16)

**파일**: `patch_master_edit_backend.py`, `patch_master_edit_ui.py`

**백엔드** (275줄):
- DB migration: `album_master` 테이블에 `override_title`, `override_artist_or_brand` 컬럼 추가
- `album_master_correction.py` DB 함수 확장
- `schemas.py` Request/Response 모델 추가

**프론트엔드** (172줄):
- 메타 카드 하단에 인라인 편집 행 추가
- 아티스트명, 앨범명, 발매년도, 도메인 필드
- 기존 `/album-masters/{id}/correction` PATCH 엔드포인트 사용

**상태**: ✅ 코드에 반영 완료 (app/api/album_masters.py, app/static/index.html)

---

### 4. 마스터 섹션 구조 변경 (2026-05-17)

**파일**: `patch_master_section.py` (306줄)

- P1: ManiaDB 링크 함수 추가
- P2: `renderHomeMasterMetaCard` — 현재 상품의 마스터 필드 + ManiaDB 링크 표시
- P3: 상품 로드 후 마스터 필드를 `homeLoadedMusicDetail`에 주입

**상태**: ✅ 코드에 반영 완료

---

### 5. 통합 편집 UI (2026-05-17)

**파일**: `patch_unified_edit.py` (425줄)

마스터 + 상품 편집 UI를 메타 카드 하단 하나의 접이식 패널로 통합

**상태**: ✅ 코드에 반영 완료

---

### 6. owned_item 2944번 복구 (운영 서버)

**파일**: `restore_2944.py` (26줄)

Discogs 스냅샷 데이터를 기반으로 특정 owned_item(2944번)의 메타데이터 복구

**실행 위치**: Mac mini 2018 (matia 계정)
**상태**: ✅ 1회 실행 완료

---

### 7. 알라딘 → Discogs 마스터 백필

**파일**: `scripts/backfill_aladin_discogs_master.py` (214줄)

알라딘으로 입수된 owned_item 중 Discogs 마스터가 없는 항목에 대해
Discogs 검색으로 마스터 연결 및 포맷 정보 업데이트

**실행 방법**: `python3 scripts/backfill_aladin_discogs_master.py`
**상태**: 필요시 실행 (idempotent)

---

### 8. 알라딘 API 진단

**파일**: `scripts/diagnose_aladin_api.py` (123줄)

알라딘 TTB API 응답 구조 확인용 진단 스크립트

**실행 방법**: `python3 scripts/diagnose_aladin_api.py`
**상태**: 개발/디버깅 완료

---

### 9. item_name_override 정규화

**파일**: `scripts/normalize_item_name.py` (69줄)

`"아티스트 - 앨범"` 형태로 저장된 `item_name_override`를 `"앨범"`만 남도록 정리

**상태**: 필요시 실행

---

## 작성 규칙

1. 새 보정 작업 발생 시 이 파일에 추가
2. 각 항목은 `파일`, `내용`, `배경`, `상태` 포함
3. 1회성 SQL은 SQL 파일을 `scripts/`에 보관하고 여기에 참조 기록
4. 콘솔을 통해 정상 처리된 작업은 기록 불필요 (audit log가 별도 존재)
