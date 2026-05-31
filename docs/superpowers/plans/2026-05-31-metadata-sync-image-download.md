# Metadata Sync Image Download — Implementation Plan

> Use superpowers:executing-plans to implement task-by-task.

**Goal:** Add automatic image download to metadata sync pipeline (individual + bulk).

**Architecture:** Individual sync calls download_images() inline. Bulk sync queues IDs, downloads in background thread after completion.

---

### Task 1: Add image download to individual sync

**File:** `app/api/owned_items.py`

- [ ] Find `sync_single_item_metadata` function
- [ ] After successful update (status=UPDATED), call `_schedule_image_download` or `download_images`
- [ ] Commit

### Task 2: Add image download queue to bulk sync

**File:** `app/main.py`

- [ ] In `_run_metadata_sync`, after `db.upsert_music_detail()`: append `owned_item_id` to an image queue list
- [ ] After main loop ends, check if queue is non-empty
- [ ] If yes, start background thread that calls `download_images` for each item
- [ ] For DISCOGS: use `snapshot.image_items`
- [ ] For ALADIN: use `cover_image_url` + `_fetch_aladin_images_from_web`
- [ ] For MANIADB: use `cover_image_url` only
- [ ] Commit

### Task 3: Update UI status message

**File:** `app/static/index.html`

- [ ] In status polling, check for `image_download_count` in the response
- [ ] Show "이미지 N건 다운로드 중..." message
- [ ] Commit

### Task 4: Sync to QA + test

- [ ] Rsync all changed files to QA
- [ ] Restart QA server
- [ ] Test individual sync + verify image download
- [ ] Test bulk sync + verify image download
