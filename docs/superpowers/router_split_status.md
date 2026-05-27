# Router Split Status

> Updated: 2026-05-27

## ✅ Complete — 132/132 routes extracted

All routes have been extracted from `app/main.py` into dedicated `app/api/` modules.

| Module | Routes | Status |
|--------|--------|--------|
| `app.api.auth` | 4 (login, /auth/*) | Phase A ✅ |
| `app.api.admin_auth_accounts` | helpers | Phase B ✅ |
| `app.api.purchase_imports` | 9 | Phase C ✅ |
| `app.api.album_masters` | 14 | Phase D ✅ |
| `app.api.owned_items` | 22 | Phase E ✅ |
| `app.api.ops_system` | 14 (health, export, provider-settings, placement-hints) | Phase F-H, N-2 ✅ |
| `app.api.operator_home` | 13 (catalog, feed, roon, customer-requests, artist-context, cafe) | Phase G, N-1 ✅ |
| `app.api.ingest` | 5 | Phase H ✅ |
| `app.api.metadata_routes` | 8 (sync, audio-directory, track-mappings) | Phase I, N-4 ✅ |
| `app.api.storage` | 9 | Phase J ✅ |
| `app.api.misc_catalog` | 18 (goods, cameras, cabinets, collector-info, product-groups) | Phase K, N-3 ✅ |
| `app.api.discogs_integration` | 8 | Phase L ✅ |
| `app.api.static_pages` | 6 | Phase M ✅ |
| **Total** | **132** | **✅ Complete** |

## Remaining `app/main.py`

- **0 routes remaining** — `main.py` now only contains app bootstrap, middleware, shared helpers, and router registration.
- Shared helpers (`_clean_text`, `_preferred_storage_size_group`, `_normalize_domain_code`, `artist_context_service`, etc.) remain in `main.py` and are accessed via `_main()` lazy accessor from all route modules.
- `MUSIC_CATEGORIES`, `STATIC_DIR`, `HTML_NO_CACHE_HEADERS`, `HTML_PROD_CACHE_HEADERS`, `_is_qa_env()` also remain in `main.py`.

## Inline Schema Migration

The following schemas were migrated from inline `try/except` blocks in `main.py` to `app/schemas.py`:

- `OpsPlacementHintRequest` ✅
- `OpsPlacementHintRecommendation` ✅
- `OpsPlacementHintResponse` ✅
- `ProductGroupCreateRequest` ✅

## Test Status

- **425 passed, 3 pre-existing failures** (all Pydantic ForwardRef — see below)
- The 3 failures are unrelated to router split:
  - `TypeAdapter[ForwardRef('GoodsStatus | None')]` — `GoodsStatus`, `GoodsCategory`, `GoodsCollectibleRelationState` are `Literal` type aliases in `schemas.py`; Pydantic v2 `TypeAdapter` can't resolve ForwardRef when imported from separate module
