# Media > Manage Redesign — Requirements Spec

**Date**: 2026-06-01  
**Status**: Draft

## 요구사항 요약

### 1. 레이아웃: 좌측 마스터 패널 + 우측 상품 편집

```
┌──────────────────┬─────────────────────────────────────┐
│ LEFT (280px)     │ RIGHT                               │
│                  │                                     │
│ [마스터 커버]     │ 📋 상품 편집 폼                      │
│ 아티스트          │ - category, media_type, format      │
│ 타이틀 (연도)     │ - size_group, quantity              │
│ 마스터 #ID        │ - price, currency                   │
│ 소스              │ - condition, signature              │
│                  │ - barcode, catalog_no, label         │
│ 🎵 Spotify       │ - release_year, memory_note         │
│ [ID 입력______]   │                                      │
│ [연결] [해제]     │ 📦 연관 상품 (마스터 멤버)            │
│                  │ 🧸 콜렉터블                          │
│ [마스터 교정 ⏷]   │                                      │
│ - 아티스트        │ [이전] [장식장 위치] [다음]          │
│ - 타이틀          │                                      │
│ - 발매년          │                                      │
│ - 도메인          │                                      │
│ - 비고            │                                      │
│ [저장]            │                                      │
│                  │                                      │
│ ⚠️ 앨범 삭제       │                                      │
│ ☐ 연결상품도 삭제  │                                      │
│ [삭제]            │                                      │
└──────────────────┴─────────────────────────────────────┘
```

### 2. Spotify 연결 기능

- 마스터 정보 영역에 Spotify Album ID 입력 필드 추가
- [연결] 버튼: PUT `/album-masters/{id}/spotify/match`
- [해제] 버튼: DELETE `/album-masters/{id}/spotify/match`
- 저장 완료 시 "연결 완료" 메시지
- `homeMasterInfo?.spotify_album_id` 로 현재 값 자동 입력

### 3. 미디어 타입 ↔ 카테고리 연동

- `editMediaType` 변경 시 자동으로 `category`, `size_group`, `preferred_storage_size_group` 동기화
- 매핑:
  - Vinyl, LP, 10", 7", Box Set, All Media → category=LP, size_group=LP
  - CD, CDr, SACD, Digital → category=CD, size_group=STD
  - Cassette, 8-Track Cartridge → category=CASSETTE, size_group=CASSETTE
  - Reel-To-Reel → category=REEL_TO_REEL, size_group=REEL_TO_REEL

### 4. 구조적 문제 해결

| 현재 | 변경 |
|------|------|
| `homeSection1MasterInfo` 안에 상품 폼 필드 | 분리: 좌측 마스터 / 우측 상품 |
| `homeEditUnifiedDetails`에 교정+상품 혼재 | 교정은 좌측 접이식, 상품 편집은 우측 |
| `homeSection3MasterDelete` 동떨어짐 | 좌측 하단으로 이동 |
| section들을 card로 불일치 | 좌측 card + 우측 card로 통일 |

### 5. media_type Select 옵션

```
Vinyl (LP), 10", 7", CD, Cassette, 8-Track Cartridge, Digital, 
Reel-To-Reel, CDr, SACD, All Media
```

(Box Set은 media_type이 아닌 packaging/format_name으로만 관리)

### 6. 패키징 옵션 매핑

- CDr, SACD → CD와 동일 패키징 옵션
- All Media → Vinyl과 동일 패키징 옵션

### 7. 구현 시 주의사항

- `app/static/index.html`은 57K 라인의 단일 파일 → HTML 블록 이동 극도로 주의
- CSS-only 접근 우선 (flex/grid/order)
- JS 이벤트 위임 방식 사용
- `content.replace()` 다중 라인 치환 금지
