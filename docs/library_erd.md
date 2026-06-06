# 라이브러리 ERD 상세

이 문서는 현재 코드 기준 스키마 설명서입니다.  
기준 소스는 `app/db/__init__.py`의 `ensure_schema` 로직과 `app/db/schema_migration.py`의 마이그레이션(v1–v15)이며, 문서는 최종 운영 스키마 관점으로 정리했습니다.

현재 `SCHEMA_VERSION = 15`

## 1. 스키마 범위

핵심 도메인
- 인입/검수
- 보유 상품과 상세 메타
- 장식장/슬롯과 위치 이력
- 내부 마스터와 외부 참조
- 구매 수입 큐
- 굿즈와 연계 관계
- 계정, 설정, 요청곡, 카메라
- Spotify 연동 및 카페 운영
- 로컬 음원 연결 및 이미지 관리
- 감사 로그 및 레이블 도메인 레지스트리

주요 코드값
- `domain_code`: `KOREA`, `JAPAN`, `GREATER_CHINA`, `WESTERN`, `OTHER_ASIA`, `WORLD`, `UNKNOWN`  
  (`WORLD_OTHER`는 레거시 값으로 DB 제약에 남아 있으나 신규 데이터는 `WORLD` 사용)
- `size_group`: `STD`, `BOOK`, `LP`, `LP10`, `LP7`, `OVERSIZE`, `CASSETTE`, `8TRACK`, `REEL_TO_REEL`, `GOODS`
- `cabinet_sort_policy`: `ARTIST_RELEASE_TITLE`, `LABEL_ID`
- `purchase_import_queue.queue_status`: `PENDING`, `CREATED`, `IGNORED`
- `review_queue.review_status`: `AUTO_APPROVED`, `NEEDS_REVIEW`, `APPROVED`, `REJECTED`
- `album_master_local_link.match_confidence`: `MANUAL`, `AUTO`

## 2. 관계도

```mermaid
erDiagram
    APP_SETTING {
      text setting_key PK
      text setting_value
      text updated_at
    }

    INGESTION_BATCH {
      int id PK
      text ingest_source
      text started_at
      int total_count
      int matched_count
      int review_count
      int failed_count
    }

    REVIEW_QUEUE {
      int id PK
      int batch_id FK
      int row_no
      text category
      text review_status
      real confidence_score
    }

    STORAGE_SLOT {
      int id PK
      text slot_code
      text cabinet_name
      text column_code
      text cell_code
      text allowed_size_group
      text cabinet_sort_policy
      text cabinet_domain_code
    }

    OWNED_ITEM {
      int id PK
      int linked_album_master_id FK
      int storage_slot_id FK
      text category
      text size_group
      text status
      text source_code
      text source_external_id
      text domain_code
    }

    MUSIC_ITEM_DETAIL {
      int owned_item_id PK_FK
      text format_name
      text artist_or_brand
      text cover_image_url
      text barcode
      text catalog_no
      text disc_type
      text package_contents
      int is_limited_edition
      text local_image_items_json
    }

    GOODS_ITEM {
      int id PK
      int storage_slot_id FK
      text category
      text goods_name
      text status
    }

    OWNED_ITEM_LOCATION_EVENT {
      int id PK
      int owned_item_id FK
      int from_storage_slot_id FK
      int to_storage_slot_id FK
      text movement_kind
      text created_at
    }

    ALBUM_MASTER {
      int id PK
      text source_code
      text source_master_id
      text title
      text artist_or_brand
      text sort_artist_name
      text domain_code
      int release_year
      text spotify_album_id
      text spotify_album_uri
      text review_text
      text review_source
      text review_url
      text genres_json
      text styles_json
    }

    ALBUM_MASTER_MEMBER {
      int id PK
      int album_master_id FK
      int owned_item_id FK
      text created_at
    }

    ALBUM_MASTER_EXTERNAL_REF {
      int id PK
      int album_master_id FK
      text source_code
      text source_master_id
    }

    ALBUM_MASTER_MERGE_HISTORY {
      int id PK
      int source_album_master_id
      int target_album_master_id
      int moved_member_count
      text created_at
      text rolled_back_at
    }

    ALBUM_MASTER_LOCAL_LINK {
      int album_master_id PK_FK
      text local_dir_path
      text match_confidence
      text linked_at
    }

    LABEL_DOMAIN_REGISTRY {
      text label_name_key PK
      text label_name
      text domain_code
      int confirmed_count
    }

    PURCHASE_IMPORT_QUEUE {
      int id PK
      int linked_owned_item_id FK
      text vendor_code
      text source_type
      text item_name
      text media_format
      text queue_status
    }

    CUSTOMER_TRACK_REQUEST {
      int id PK
      int owned_item_id FK
      text requested_track
      text status
      text created_at
    }

    TABLE_DEVICE {
      int id PK
      text device_name
      text device_type
      text device_id
      int is_active
    }

    TRACK_REACTION {
      int id PK
      int track_request_id FK
      text reaction_type
      text created_at
    }

    AUDIT_LOG {
      int id PK
      text entity_type
      int entity_id
      text action
      text changed_by
      text changed_fields
      text snapshot_json
      text created_at
    }

    CABINET_CAMERA {
      int id PK
      text cabinet_name
      text camera_name
      int is_active
    }

    AUTH_ACCOUNT {
      int id PK
      text username
      text role
      int is_active
    }

    INGESTION_BATCH ||--o{ REVIEW_QUEUE : contains
    STORAGE_SLOT ||--o{ OWNED_ITEM : stores
    STORAGE_SLOT ||--o{ GOODS_ITEM : stores
    OWNED_ITEM ||--o| MUSIC_ITEM_DETAIL : details
    OWNED_ITEM ||--o{ OWNED_ITEM_LOCATION_EVENT : moves
    ALBUM_MASTER ||--o{ OWNED_ITEM : linked_by
    ALBUM_MASTER ||--o{ ALBUM_MASTER_MEMBER : groups
    OWNED_ITEM ||--o{ ALBUM_MASTER_MEMBER : member_of
    ALBUM_MASTER ||--o{ ALBUM_MASTER_EXTERNAL_REF : references
    ALBUM_MASTER ||--o| ALBUM_MASTER_LOCAL_LINK : local_music
    PURCHASE_IMPORT_QUEUE }o--|| OWNED_ITEM : creates
    OWNED_ITEM ||--o{ CUSTOMER_TRACK_REQUEST : request_logs
    CUSTOMER_TRACK_REQUEST ||--o{ TRACK_REACTION : reacted_by
```

## 3. 테이블 카탈로그

### 3-1. 운영 설정과 보조 기준

| 테이블 | PK | 대표 컬럼 | 참조 | 설명 |
| --- | --- | --- | --- | --- |
| `app_setting` | `setting_key` | `setting_value`, `updated_at` | 없음 | 자동 백업 설정과 최근 실행 상태 저장 |
| `metadata_source` | `id` | `source_code`, `source_scope`, `priority`, `enabled` | 없음 | 외부 소스 우선순위/활성 상태 |
| `classification_option` | `id` | `option_group`, `label`, `sort_order`, `is_active` | 없음 | 서브타입/사운드트랙 분류 옵션 |
| `auth_account` | `id` | `username`, `role`, `is_active` | 없음 | 관리자/현장 운영자 계정 |
| `label_domain_registry` | `label_name_key` | `label_name`, `domain_code`, `confirmed_count`, `updated_at` | 없음 | 레이블명 → 도메인 코드 매핑 레지스트리. 도메인 자동 추론에 사용 (v14) |

### 3-2. 인입과 검수

| 테이블 | PK | 대표 컬럼 | 참조 | 설명 |
| --- | --- | --- | --- | --- |
| `ingestion_batch` | `id` | `ingest_source`, `started_at`, `completed_at`, `total_count`, `matched_count`, `review_count`, `failed_count` | 없음 | CSV 등 대량 인입 1회 단위 메타 |
| `review_queue` | `id` | `batch_id`, `row_no`, `category`, `payload_json`, `candidate_json`, `confidence_score`, `review_status`, `review_note` | `batch_id -> ingestion_batch.id` | 검수 대기/자동 승인 결과 |
| `purchase_import_queue` | `id` | `vendor_code`, `source_type`, `source_ref`, `email_from`, `email_subject`, `artist_name`, `item_name`, `media_format`, `quantity`, `unit_price`, `purchase_date`, `queue_status`, `linked_owned_item_id` | `linked_owned_item_id -> owned_item.id` | 구매 파일/메일 파싱 결과를 임시 적재 |

구매 수입 큐 운영 포인트
- 중복 판정은 `vendor_code`, `item_name`, `media_format`, `quantity`, `source_ref`, `email_subject`, `item_url`, `purchase_date`, `raw_line`, 가격 정보를 조합합니다.
- 후보 확정 후 `queue_status=CREATED`, 무시 시 `IGNORED`로 바뀝니다.

### 3-3. 위치와 장식장

| 테이블 | PK | 대표 컬럼 | 참조 | 설명 |
| --- | --- | --- | --- | --- |
| `storage_slot` | `id` | `slot_code`, `cabinet_name`, `column_code`, `cell_code`, `allowed_size_group`, `cabinet_sort_policy`, `cabinet_domain_code`, `max_thickness_mm`, `cabinet_group_name`, `cabinet_group_order`, `is_overflow_zone` | 없음 | 장식장/열/칸 구조 |
| `owned_item_location_event` | `id` | `owned_item_id`, `from_storage_slot_id`, `to_storage_slot_id`, `movement_kind`, `from_slot_display_name`, `to_slot_display_name`, `note`, `created_at` | `owned_item_id -> owned_item.id` | 위치 배치/이동/복구 이력 |
| `cabinet_camera` | `id` | `cabinet_name`, `camera_name`, `snapshot_url`, `stream_url`, `username`, `is_active` | 없음 | 장식장 연계 카메라 |

`storage_slot` 비고
- 실제 운영 문맥에서는 `slot_code`보다 `cabinet_name`, `column_code`, `cell_code` 삼중 값이 더 중요합니다.
- `cabinet_domain_code`는 장식장 단위 도메인 분류로, 예외 큐 도메인 필터에서 활용합니다.

### 3-4. 보유 상품 본체

| 테이블 | PK | 대표 컬럼 | 참조 | 설명 |
| --- | --- | --- | --- | --- |
| `owned_item` | `id` | `linked_album_master_id`, `category`, `domain_code`, `release_type`, `quantity`, `size_group`, `preferred_storage_size_group`, `status`, `source_code`, `source_external_id`, `purchase_source`, `storage_slot_id`, `thickness_mm`, `notes` | `linked_album_master_id -> album_master.id`, `storage_slot_id -> storage_slot.id` | 실제 소장품 1건의 기준 테이블 |
| `music_item_detail` | `owned_item_id` | `format_name`, `artist_or_brand`, `released_date`, `barcode`, `label_name`, `catalog_no`, `cover_image_url`, `track_list_json`, `genres_json`, `styles_json`, `disc_count`, `runout_matrix_json`, `image_items_json`, `disc_type`, `package_contents`, `is_limited_edition`, `edition_number`, `local_image_items_json` | `owned_item_id -> owned_item.id` | 음반 상세 메타. `disc_type`: 디스크 소재(Standard/Picture/Shaped/Colored/Clear). `local_image_items_json`: 운영자가 직접 업로드한 앞면·뒷면 등 로컬 이미지 목록 (v11) |
| `goods_item_detail` | `owned_item_id` | `image_urls_json`, `primary_image_url`, `poster_storage_spec`, `tshirt_size`, `cup_material`, `hat_size` | `owned_item_id -> owned_item.id` | 굿즈가 `owned_item` 흐름으로 들어온 경우의 상세 |
| `owned_item_subtype` | `id` | `owned_item_id`, `option_id` | `owned_item_id -> owned_item.id`, `option_id -> classification_option.id` | 서브타입 다중 분류 |
| `owned_item_soundtrack` | `id` | `owned_item_id`, `option_id` | `owned_item_id -> owned_item.id`, `option_id -> classification_option.id` | 사운드트랙 분류 |
| `digital_asset` | `id` | `asset_type`, `file_path`, `file_hash`, `file_size_bytes`, `duration_sec`, `metadata_json` | 없음 | 파일 자산 원본 |
| `owned_item_digital_link` | `id` | `owned_item_id`, `digital_asset_id`, `link_type`, `track_no`, `note` | `owned_item_id -> owned_item.id`, `digital_asset_id -> digital_asset.id` | 스캔/오디오/문서 링크 |

`owned_item` 비고
- 현재 조회/검색/정렬 대부분은 `owned_item.linked_album_master_id`를 바로 참조합니다.
- `master_item_id`, `copy_group_key`, `linked_artist_name`은 복제본/연계 맥락에서 보조적으로 사용됩니다.

### 3-5. 내부 마스터와 외부 참조

| 테이블 | PK | 대표 컬럼 | 참조 | 설명 |
| --- | --- | --- | --- | --- |
| `album_master` | `id` | `source_code`, `source_master_id`, `title`, `artist_or_brand`, `sort_artist_name`, `domain_code`, `release_year`, `override_domain_code`, `override_release_year`, `override_note`, `spotify_album_id`, `spotify_album_uri`, `spotify_matched_at`, `spotify_image_url`, `review_text`, `review_source`, `review_url`, `genres_json`, `styles_json`, `raw_json` | 없음 | 내부 작품 단위 기준 엔터티. Spotify 연동·리뷰·장르 정보 포함 |
| `album_master_member` | `id` | `album_master_id`, `owned_item_id`, `created_at` | `album_master_id -> album_master.id`, `owned_item_id -> owned_item.id` | 마스터-보유상품 연결 테이블 |
| `album_master_external_ref` | `id` | `album_master_id`, `source_code`, `source_master_id`, `title_hint`, `artist_or_brand_hint`, `release_year`, `raw_json` | `album_master_id -> album_master.id` | 내부 마스터와 외부 마스터의 안정적 매핑 |
| `album_master_merge_history` | `id` | `source_album_master_id`, `target_album_master_id`, `source_member_links_json`, `source_external_refs_json`, `overlap_owned_item_ids_json`, `moved_member_count`, `target_member_count`, `merged_by`, `created_at`, `rolled_back_at` | 논리적 참조 | 마스터 병합/롤백 이력 |
| `album_master_local_link` | `album_master_id` | `local_dir_path`, `match_confidence`, `linked_at` | `album_master_id -> album_master.id` | NAS 디렉터리 경로와 마스터 1:1 연결. 로컬 플레이어 재생 경로로 활용 (v15) |

마스터 설계 포인트
- `owned_item.linked_album_master_id`는 현재 상태 포인터입니다.
- `album_master_member`는 멤버십과 병합/롤백 처리를 위한 정규화 연결입니다.
- `album_master_external_ref`는 한 내부 마스터가 여러 외부 마스터 출처를 가질 수 있도록 합니다.
- `spotify_album_id`는 수동 또는 자동 매칭으로 설정되며, 예외 큐의 `SPOTIFY_UNMATCHED` 판별에 사용됩니다.
- `review_text`/`review_source`/`review_url`은 Wikipedia 자동 수집 또는 수동 작성으로 채웁니다.
- `genres_json`/`styles_json`은 마스터 레벨 장르 태그입니다. 예외 큐의 `GENRE_MISSING` 판별에 사용됩니다.

### 3-6. 굿즈 전용 구조

| 테이블 | PK | 대표 컬럼 | 참조 | 설명 |
| --- | --- | --- | --- | --- |
| `goods_item` | `id` | `category`, `goods_name`, `quantity`, `size_group`, `storage_slot_id`, `status`, `domain_code`, `memory_note`, `image_urls_json`, `primary_image_url` | `storage_slot_id -> storage_slot.id` | 음반 외 굿즈 본체 |
| `goods_item_album_master_map` | `id` | `goods_item_id`, `album_master_id` | `goods_item_id -> goods_item.id`, `album_master_id -> album_master.id` | 굿즈-앨범 연결 |
| `goods_item_artist_map` | `id` | `goods_item_id`, `artist_name`, `normalized_artist_name` | `goods_item_id -> goods_item.id` | 굿즈-아티스트 연결 |
| `goods_item_label_map` | `id` | `goods_item_id`, `label_name`, `normalized_label_name` | `goods_item_id -> goods_item.id` | 굿즈-레이블 연결 |
| `goods_item_collectible_relation` | `id` | `goods_item_id`, `relation_type`, `linked_goods_item_id`, `note`, `display_order` | `goods_item_id -> goods_item.id`, `linked_goods_item_id -> goods_item.id` | 시리즈/변형/세트 구성 관계 |

### 3-7. 카페 운영

| 테이블 | PK | 대표 컬럼 | 참조 | 설명 |
| --- | --- | --- | --- | --- |
| `customer_track_request` | `id` | `requested_track`, `owned_item_id`, `matched_track_title`, `current_slot_code_snapshot`, `previous_slot_code_snapshot`, `status`, `requested_by`, `handled_by`, `handled_at` | `owned_item_id -> owned_item.id` | 현장 요청곡 처리 로그 |
| `table_device` | `id` | `device_name`, `device_type`, `device_id`, `is_active`, `created_at` | 없음 | Spotify Connect 등 카페 재생 디바이스 등록 (v10) |
| `track_reaction` | `id` | `track_request_id`, `reaction_type`, `table_name`, `created_at` | `track_request_id -> customer_track_request.id` | 고객이 재생 중인 곡에 남기는 리액션 (v10) |

### 3-8. 시스템 보조

| 테이블 | PK | 대표 컬럼 | 참조 | 설명 |
| --- | --- | --- | --- | --- |
| `external_response_cache` | `id` | `cache_key`, `response_json`, `created_at`, `expires_at` | 없음 | 외부 API 응답 캐시 (v2). 반복 호출 비용 절감 |
| `audit_log` | `id` | `entity_type`, `entity_id`, `action`, `changed_by`, `changed_fields`, `snapshot_json`, `created_at` | 논리적 참조 | 메타 수정·위치 변경·계정 변경 등 주요 작업 이력 추적 |

## 4. 인덱스와 조회 포인트

대표 인덱스
- `idx_review_queue_status`
- `idx_owned_item_category_rank`
- `idx_owned_item_location_event_owned`
- `idx_album_master_lookup`
- `idx_album_master_external_ref_lookup`
- `idx_purchase_import_queue_status`
- `idx_purchase_import_queue_vendor`
- `idx_am_local_link_path` — `album_master_local_link.local_dir_path` (v15)
- `idx_label_domain_registry_domain` — `label_domain_registry.domain_code` (v14)
- `idx_audit_log_entity` — `(entity_type, entity_id, created_at DESC)`
- `idx_audit_log_created` — `created_at DESC`
- `idx_track_reaction_request` — `track_reaction.track_request_id`

조회 패턴
- 위치 조회: `owned_item → storage_slot → owned_item_location_event`
- 마스터 조회: `owned_item.linked_album_master_id`와 `album_master_member`
- 구매 수입 큐 조회: `queue_status`, `vendor_code` 중심
- 예외 큐: `owned_item`, `music_item_detail`, `album_master`, `storage_slot` 조합으로 계산
- 로컬 음원 조회: `album_master → album_master_local_link → local_dir_path`
- 도메인 자동 추론: `music_item_detail.label_name → label_domain_registry.domain_code`

## 5. 예외 큐 판별 기준 (13종)

| 예외 종류 | 판별 기준 |
|-----------|----------|
| `UNSLOTTED` | `storage_slot_id IS NULL` |
| `SOURCE_MISSING` | `source_code IS NULL` or `source_external_id IS NULL` |
| `MASTER_MISSING` | `linked_album_master_id IS NULL` |
| `COVER_MISSING` | `music_item_detail.cover_image_url IS NULL` |
| `PREFERRED_SIZE_MISMATCH` | `preferred_storage_size_group ≠ size_group` |
| `MEDIA_MISSING` | `music_item_detail.media_type IS NULL` |
| `SIZE_MISMATCH` | `storage_slot.allowed_size_group ≠ owned_item.size_group` |
| `TRACK_MISSING` | 트랙 정보 없음 |
| `SPOTIFY_UNMATCHED` | `album_master.spotify_album_id IS NULL` (마스터 기준) |
| `REVIEW_MISSING` | `album_master.review_text IS NULL` (마스터 기준) |
| `GENRE_MISSING` | `album_master.genres_json IS NULL` (마스터 기준) |
| `CATALOG_MISSING` | `music_item_detail.catalog_no IS NULL` |
| `LOCAL_MISSING` | `album_master_local_link` 연결 없음 (마스터 기준) |

## 6. CSV/구매 수입과 연결되는 컬럼

CSV 대량 입력에서 직접 영향을 받는 컬럼
- `owned_item.category`
- `owned_item.source_code`
- `owned_item.source_external_id`
- `owned_item.storage_slot_id`
- `music_item_detail.artist_or_brand`
- `music_item_detail.catalog_no`
- `music_item_detail.barcode`

CSV 위치 매핑 입력 키
- `cabinet_name`
- `column_code`
- `cell_code`
- `slot_code`
- 한글 별칭: `장식장명`, `열`, `칸`, `보관슬롯`

구매 수입에서 직접 영향을 받는 컬럼
- `purchase_import_queue.vendor_code`
- `purchase_import_queue.source_type`
- `purchase_import_queue.item_name`
- `purchase_import_queue.media_format`
- `purchase_import_queue.quantity`
- `purchase_import_queue.purchase_date`
- `purchase_import_queue.linked_owned_item_id`

## 7. 문서 해석 기준

- 이 문서는 운영 중인 최종 스키마를 설명합니다.
- 초기 `CREATE TABLE` 정의(`app/db/__init__.py`)와 이후 마이그레이션(`app/db/schema_migration.py` v1–v15)이 합쳐진 상태를 기준으로 읽습니다.
- 실제 배치/정렬/예외 판단은 스키마만으로 끝나지 않고 `app/db/` 도메인 로직을 함께 봐야 정확합니다.
