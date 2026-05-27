# Router Split Status

> Updated: 2026-05-27

## ✅ Extracted (49 routes)

| Module | Routes | Status |
|--------|--------|--------|
| `app.api.auth` | 4 (login, /auth/*) | Phase A ✅ |
| `app.api.admin_auth_accounts` | 0 (helpers) | Phase B ✅ |
| `app.api.purchase_imports` | 9 | Phase C ✅ |
| `app.api.album_masters` | 14 | Phase D ✅ |
| `app.api.owned_items` | 22 | Phase E ✅ |
| \`app.api.ops_system\` | 13 (health, export, provider-settings) | Phase F-H ✅ |
| **Total** | **62** | **465 tests pass** |

## ⏳ Remaining (~13 routes in main.py)

```
ops_system.py: 9 route groups
  /catalog-stats
  /health
  /ops/artist-context
  /ops/export/*
  /ops/owned-items/{id}/collector-info
  /ops/placement-hints
  /ops/provider-settings/*
  /system/status
  /tool-docs/{doc_key}

operator_home.py: 5 route groups
  /operator/catalog-search
  /operator/customer-requests/*
  /operator/home/*
  /operator/office-climate
  /operator/roon/*

ingest.py: 4 route groups
  /ingest/barcode
  /ingest/csv
  /ingest/search
  /review-queue

storage.py: 4 route groups
  /classification-options/*
  /dashboard/collection
  /storage-cabinets/*
  /storage-slots/*

misc_catalog.py: 4 route groups
  /cabinet-cameras/*
  /goods-items/*
  /goods-targets
  /product-groups

discogs_integration.py: 3 route groups
  /aladin-discogs-backfill/*
  /discogs-korean-backfill/*
  /discogs/*

metadata_routes.py: 2 route groups
  /metadata-sync/*
  /owned-items/{id}/sync-metadata

static_pages.py: 4 route groups
  /
  /admin
  /ops
  /ui/*

```
