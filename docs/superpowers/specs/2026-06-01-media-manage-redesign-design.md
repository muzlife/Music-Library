# Media > Manage Redesign — Design Spec

**Date**: 2026-06-01  
**Status**: Draft

## Overview

Redesign the "미디어 > 관리" (Media > Manage) section to separate master management from product editing, with a left sidebar for master info/Spotify player and right panel for product editing.

## Current Problems

1. `homeEditUnifiedDetails` mixes master correction AND product editing in one panel
2. `homeSection3MasterDelete` is an isolated section far from master info
3. Sections inconsistently wrapped (some in `.card`, some not)
4. `homeSection1MasterInfo` contains product edit form fields — structural error

## Layout

```
┌──────────────────┬─────────────────────────────────────┐
│ LEFT (280px)     │ RIGHT                               │
│                  │                                     │
│ [커버 이미지]     │ 📋 상품 편집                         │
│ 아티스트          │ - category, media_type, format      │
│ 타이틀 (연도)     │ - size_group, quantity              │
│ 마스터 #ID        │ - price, currency                   │
│ 소스 (DISCOGS)    │ - condition, signature              │
│                  │ - barcode, catalog_no               │
│ 🎵 Spotify       │ - label, release_year               │
│ (트랙 리스트)     │ - memory_note                      │
│ ▶️ 재생           │                                      │
│                  │ 📦 연관 상품 (마스터 멤버)            │
│ [마스터 교정 ⏷]   │ 🧸 콜렉터블                         │
│ - 아티스트        │                                      │
│ - 타이틀          │ [이전] [장식장 위치] [다음]          │
│ - 발매년          │                                      │
│ - 도메인          │                                      │
│ - 비고            │                                      │
│ [저장]            │                                      │
│                  │                                      │
│ ⚠️ 마스터 삭제     │                                      │
│ ☐ 연결상품도 삭제  │                                      │
│ [삭제]            │                                      │
└──────────────────┴─────────────────────────────────────┘
```

## Components

### Left Panel (`.ops-exception-left` style, 280px, sticky)

| Component | Description |
|-----------|-------------|
| Master Cover | 280x280 cover image |
| Master Info | Artist, Title (Year), master #ID, source badge |
| Spotify Player | Track list + play button (if spotify_album_id present) |
| Master Correction | Collapsible (`<details>`), fields: artist, title, year, domain, note |
| Master Delete | Collapsible, cascade checkbox + delete button |

### Right Panel (flex-1)

| Component | Description |
|-----------|-------------|
| Product Edit Form | Current `homeEditMusicMetaFieldsA` + `homeEditMusicMetaFieldsB` + `homeEditVinylMetaRow` |
| Related Products | Master members list |
| Collectibles | Linked goods items |
| Shelf Navigator | Previous/Next + current location display |

## Behavior

- Left panel visible only when a product is selected (master loaded)
- Spotify player shows if `spotify_album_id` exists
- Master correction changes are saved via existing `homeMasterCorrectionSaveBtn` endpoint
- Product edit form uses existing save logic
- Shelf navigator uses existing prev/next logic

## CSS

- Left panel: `width:280px; flex-shrink:0; position:sticky; top:8px; overflow-y:auto; max-height:calc(100vh - 120px)`
- Right panel: `flex:1; min-width:0`
- Master info card: compact layout with cover + text
- Spotify player: `max-height:300px; overflow-y:auto`

## Migration

- Move `homeEditMusicMetaFieldsA/B`, `homeEditVinylMetaRow` out of `homeEditUnifiedDetails` into right panel
- Move `homeMasterCorrectionRow` into left panel
- Move `homeSection3MasterDelete` into left panel
- Remove `homeEditUnifiedDetails` wrapper, `homeSection1MasterInfo` wrapper
- Keep `homeProductRelationSection`, `homeLinkedCollectiblesSection` in right panel
- Keep shelf navigator in right panel
