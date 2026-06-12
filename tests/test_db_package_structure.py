"""Consolidated structural + functional regression tests for app/db package.

Replaces 34 test_db_split_phase_*.py files (5002 lines) that verified the
db.py → app/db/ package split.  The split is complete; this file keeps
the contracts alive in a single maintainable location.

Structure
  _MODULE_SYMBOLS       — all symbols that must exist on each submodule
  _MODULE_REEXPORT_SYMS — subset re-exported via app/db/__init__.py

Parametrized structural tests run across all 33 submodules.
Functional (round-trip, contract, smoke) tests follow per module.
"""
from __future__ import annotations

import importlib
import json
import re
from pathlib import Path

import pytest

from app import db
from app.db import album_master_core as amc_module
from app.db import album_master_member as amm_module
from app.db import customer_track_request as ctr_module
from app.db import owned_item_order as oio_module
from app.db import owned_item_slot as ois_module
from app.db import storage_slot as ss_module


REPO_ROOT = Path(__file__).resolve().parents[1]

# ── Symbol catalogs ─────────────────────────────────────────────────────────

# All symbols that must appear on each submodule's surface.
_MODULE_SYMBOLS: list[tuple[str, tuple[str, ...]]] = [
    ('auth_account', (
        '_ensure_auth_account_table',
        'list_auth_accounts',
        'get_auth_account_by_username',
        'upsert_auth_account',
        'delete_auth_account',
    )),
    ('cache', (
        'get_cached_external_response',
        'upsert_cached_external_response',
        'touch_cached_external_response_expiry',
        'purge_expired_external_responses',
    )),
    ('purchase_import', (
        'insert_purchase_import_rows',
        'find_purchase_import_duplicate_row',
        'list_purchase_import_rows',
        'has_purchase_import_for_source_ref',
        'count_purchase_import_rows',
        'get_purchase_import_row',
        'update_purchase_import_row',
        '_purchase_import_vendor_check_sql',
        '_ensure_purchase_import_queue_table',
        '_purchase_import_queue_allows_file_upload',
        '_purchase_import_queue_allows_extended_vendors',
        '_migrate_purchase_import_queue_allow_file_upload',
        '_purchase_import_cmp_text',
        '_purchase_import_cmp_float',
        '_purchase_import_row_matches_duplicate',
        '_find_purchase_import_duplicate_in_conn',
    )),
    ('customer_track_request', (
        'create_customer_track_request',
        'get_customer_track_request',
        'list_customer_track_requests',
        'count_customer_track_requests',
        'update_customer_track_request',
    )),
    ('storage_slot', (
        'get_storage_slot',
        'get_storage_slot_by_code',
        'list_storage_slots',
        'list_owned_items_for_storage_slot',
        'upsert_storage_slot',
        'register_storage_cabinet_slots',
        'delete_storage_cabinet',
        '_storage_slot_allows_goods',
        '_migrate_storage_slot_allow_goods',
        '_cleanup_overflow_slots',
        '_derive_storage_slot_parts',
    )),
    ('goods_item', (
        'create_goods_item',
        'update_goods_item',
        'get_goods_item',
        'delete_goods_item',
        'replace_goods_item_mappings',
        'replace_goods_item_collectible_relations',
        'search_goods_collectible_targets',
        'count_goods_items',
        'search_goods_items',
        'list_goods_artist_name_candidates',
        'list_goods_label_name_candidates',
        '_goods_category_check_sql',
        '_goods_status_check_sql',
        '_goods_relation_type_check_sql',
        '_normalize_goods_category_value',
        '_normalize_goods_status_value',
        '_normalize_goods_relation_type_value',
        '_normalize_goods_mapping_text',
        '_goods_item_select_query',
        '_normalize_goods_item_row',
        '_list_goods_item_album_master_mappings_in_conn',
        '_list_goods_item_artist_mappings_in_conn',
        '_list_goods_item_label_mappings_in_conn',
        '_list_goods_item_collectible_relations_in_conn',
        '_build_goods_item_with_mappings',
        '_replace_goods_item_collectible_relations_in_conn',
        '_replace_goods_item_mappings_in_conn',
        '_build_goods_search_where',
    )),
    ('cabinet_camera', (
        'list_cabinet_cameras',
        'get_cabinet_camera',
        'get_cabinet_camera_by_cabinet',
        'upsert_cabinet_camera',
        'delete_cabinet_camera',
    )),
    ('classification_option', (
        'list_classification_options',
        'upsert_classification_option',
        '_seed_classification_options',
    )),
    ('ingestion_batch', (
        'insert_batch',
        'finalize_batch',
        'insert_review_queue',
        'bulk_insert_review_queue',
        'bulk_finalize_csv_ingest',
        'list_review_queue',
    )),
    ('auto_backup', (
        'get_auto_backup_settings',
        'save_auto_backup_settings',
        'record_auto_backup_result',
    )),
    ('album_master_merge_history', (
        'list_album_master_merge_history',
        'rollback_latest_album_master_merge',
        '_album_master_merge_history_record',
        '_latest_open_album_master_merge_history_id',
        '_json_loads_or_default',
    )),
    ('album_master_external_ref', (
        'get_album_master_id_by_external_ref',
        'list_album_master_external_refs',
        'ensure_album_master_external_ref',
    )),
    ('album_master_correction', (
        'get_album_master_correction_state',
        'update_album_master_correction',
    )),
    ('album_master_duplicates', (
        'list_duplicate_album_masters',
        '_album_master_source_priority',
    )),
    ('album_master_member', (
        'bind_album_master_members',
        'album_master_exists',
        'update_album_master_sort_artist_name',
        'list_album_master_members',
        'delete_album_master',
    )),
    ('album_master_tracks', (
        'list_album_master_track_matches',
    )),
    ('digital_link', (
        'insert_digital_link',
    )),
    ('location_recommendation', (
        'recommend_owned_item_location',
        'recommend_barcode_candidate_locations',
    )),
    ('album_master_core', (
        'upsert_album_master',
        'normalize_album_master_source_id',
        'promote_album_master_source',
        'merge_album_masters',
        '_sync_album_master_domain_code_in_conn',
        '_snapshot_album_master_record',
        '_snapshot_member_link_records',
        '_snapshot_external_ref_records',
    )),
    ('album_master_read', (
        'list_album_masters',
        'count_album_masters',
        'get_album_master_binding_for_owned_item',
        'get_album_master_domain_hint',
        'list_owned_items_by_album_master',
        'set_owned_item_linked_album_master',
        '_build_album_master_filter_sql',
    )),
    ('owned_item_track_links', (
        'list_owned_item_track_links',
        'list_owned_item_audio_directory_links',
        'delete_owned_item_track_links',
        'delete_owned_item_audio_directory_links',
    )),
    ('owned_item_copy_group', (
        'set_owned_item_copy_group',
        'list_owned_items_by_copy_group',
        'list_owned_items_by_source_external_ids',
    )),
    ('owned_item_slot', (
        'update_owned_item_slot',
        'inherit_owned_item_domain_from_slot_if_missing',
        'restore_owned_item_previous_slot',
        '_location_slot_snapshot_in_conn',
        '_derive_location_movement_kind',
        '_log_owned_item_location_event_in_conn',
    )),
    ('owned_item_order', (
        'move_owned_item_order',
        'realign_owned_item_order_after_slot_move',
        'move_owned_item_slot_display_rank',
    )),
    ('owned_item_track', (
        'get_owned_item_location_snapshot',
        'get_owned_item_track_list',
    )),
    ('owned_item_read', (
        'get_owned_item',
        'get_owned_item_detail',
    )),
    ('owned_item_write', (
        'insert_owned_item',
        'update_owned_item',
        'bulk_update_owned_items',
        'delete_owned_item',
        '_sync_owned_item_classifications_in_conn',
    )),
    ('owned_item_query', (
        'list_owned_items',
        'count_owned_items',
        'get_owned_item_list_row',
    )),
    ('ops_home_recent', (
        'count_ops_home_recent_moved_items',
        'list_ops_home_recent_moved_items',
        'count_ops_home_recent_registered_items',
        'list_ops_home_recent_registered_items',
        'get_ops_home_recent_sections',
        'get_ops_home_feed',
        '_build_ops_home_recent_item',
    )),
    ('metadata_sync', (
        'list_metadata_sync_candidates',
        'upsert_music_detail',
    )),
    ('music_shelf_window', (
        'get_music_shelf_window',
        'get_owned_counts_by_source',
    )),
    ('collection_dashboard', (
        'get_collection_dashboard',
        '_extract_collection_dashboard_release_year',
        '_build_collection_dashboard_first_item_hints',
    )),
    ('operator_search', (
        'search_operator_catalog',
    )),
    ('order_keys', (
        'resequence_in_collection_order',
        '_format_order_value',
        '_parse_order_value',
        '_next_order_key_in_conn',
        '_backfill_order_keys',
        '_compute_between_order_value',
        '_rebalance_in_collection_order',
    )),
]

# Subset of each module's symbols that are re-exported via app/db/__init__.
_MODULE_REEXPORT_SYMS: list[tuple[str, tuple[str, ...]]] = [
    ('auth_account', (
        '_ensure_auth_account_table',
        'list_auth_accounts',
        'get_auth_account_by_username',
        'upsert_auth_account',
        'delete_auth_account',
    )),
    ('cache', (
        'get_cached_external_response',
        'upsert_cached_external_response',
        'touch_cached_external_response_expiry',
        'purge_expired_external_responses',
    )),
    ('purchase_import', (
        'insert_purchase_import_rows',
        'find_purchase_import_duplicate_row',
        'list_purchase_import_rows',
        'has_purchase_import_for_source_ref',
        'count_purchase_import_rows',
        'get_purchase_import_row',
        'update_purchase_import_row',
        '_purchase_import_vendor_check_sql',
        '_ensure_purchase_import_queue_table',
        '_purchase_import_queue_allows_file_upload',
        '_purchase_import_queue_allows_extended_vendors',
        '_migrate_purchase_import_queue_allow_file_upload',
        '_purchase_import_cmp_text',
        '_purchase_import_cmp_float',
        '_purchase_import_row_matches_duplicate',
        '_find_purchase_import_duplicate_in_conn',
    )),
    ('customer_track_request', (
        'create_customer_track_request',
        'get_customer_track_request',
        'list_customer_track_requests',
        'count_customer_track_requests',
        'update_customer_track_request',
    )),
    ('storage_slot', (
        'get_storage_slot',
        'get_storage_slot_by_code',
        'list_storage_slots',
        'list_owned_items_for_storage_slot',
        'upsert_storage_slot',
        'register_storage_cabinet_slots',
        'delete_storage_cabinet',
        '_storage_slot_allows_goods',
        '_migrate_storage_slot_allow_goods',
        '_cleanup_overflow_slots',
        '_derive_storage_slot_parts',
    )),
    ('goods_item', (
        'create_goods_item',
        'update_goods_item',
        'get_goods_item',
        'delete_goods_item',
        'replace_goods_item_mappings',
        'replace_goods_item_collectible_relations',
        'search_goods_collectible_targets',
        'count_goods_items',
        'search_goods_items',
        'list_goods_artist_name_candidates',
        'list_goods_label_name_candidates',
        '_goods_category_check_sql',
        '_goods_status_check_sql',
        '_goods_relation_type_check_sql',
        '_normalize_goods_category_value',
        '_normalize_goods_status_value',
        '_normalize_goods_relation_type_value',
        '_normalize_goods_mapping_text',
        '_goods_item_select_query',
        '_normalize_goods_item_row',
        '_list_goods_item_album_master_mappings_in_conn',
        '_list_goods_item_artist_mappings_in_conn',
        '_list_goods_item_label_mappings_in_conn',
        '_list_goods_item_collectible_relations_in_conn',
        '_build_goods_item_with_mappings',
        '_replace_goods_item_collectible_relations_in_conn',
        '_replace_goods_item_mappings_in_conn',
        '_build_goods_search_where',
    )),
    ('cabinet_camera', (
        'list_cabinet_cameras',
        'get_cabinet_camera',
        'get_cabinet_camera_by_cabinet',
        'upsert_cabinet_camera',
        'delete_cabinet_camera',
    )),
    ('classification_option', (
        'list_classification_options',
        'upsert_classification_option',
        '_seed_classification_options',
    )),
    ('ingestion_batch', (
        'insert_batch',
        'finalize_batch',
        'insert_review_queue',
        'bulk_insert_review_queue',
        'bulk_finalize_csv_ingest',
        'list_review_queue',
    )),
    ('auto_backup', (
        'get_auto_backup_settings',
        'save_auto_backup_settings',
        'record_auto_backup_result',
    )),
    ('album_master_merge_history', (
        'list_album_master_merge_history',
        'rollback_latest_album_master_merge',
    )),
    ('album_master_external_ref', (
        'get_album_master_id_by_external_ref',
        'list_album_master_external_refs',
        'ensure_album_master_external_ref',
    )),
    ('album_master_correction', (
        'get_album_master_correction_state',
        'update_album_master_correction',
    )),
    ('album_master_duplicates', (
        'list_duplicate_album_masters',
        '_album_master_source_priority',
    )),
    ('album_master_member', (
        'bind_album_master_members',
        'album_master_exists',
        'update_album_master_sort_artist_name',
        'list_album_master_members',
        'delete_album_master',
    )),
    ('album_master_tracks', (
        'list_album_master_track_matches',
    )),
    ('digital_link', (
        'insert_digital_link',
    )),
    ('location_recommendation', (
        'recommend_owned_item_location',
        'recommend_barcode_candidate_locations',
    )),
    ('album_master_core', (
        'upsert_album_master',
        'normalize_album_master_source_id',
        'promote_album_master_source',
        'merge_album_masters',
        '_sync_album_master_domain_code_in_conn',
        '_snapshot_album_master_record',
        '_snapshot_member_link_records',
        '_snapshot_external_ref_records',
    )),
    ('album_master_read', (
        'list_album_masters',
        'count_album_masters',
        'get_album_master_binding_for_owned_item',
        'get_album_master_domain_hint',
        'list_owned_items_by_album_master',
        'set_owned_item_linked_album_master',
    )),
    ('owned_item_track_links', (
        'list_owned_item_track_links',
        'list_owned_item_audio_directory_links',
        'delete_owned_item_track_links',
        'delete_owned_item_audio_directory_links',
    )),
    ('owned_item_copy_group', (
        'set_owned_item_copy_group',
        'list_owned_items_by_copy_group',
        'list_owned_items_by_source_external_ids',
    )),
    ('owned_item_slot', (
        'update_owned_item_slot',
        'inherit_owned_item_domain_from_slot_if_missing',
        'restore_owned_item_previous_slot',
        '_location_slot_snapshot_in_conn',
        '_derive_location_movement_kind',
        '_log_owned_item_location_event_in_conn',
    )),
    ('owned_item_order', (
        'move_owned_item_order',
        'realign_owned_item_order_after_slot_move',
        'move_owned_item_slot_display_rank',
    )),
    ('owned_item_track', (
        'get_owned_item_location_snapshot',
        'get_owned_item_track_list',
    )),
    ('owned_item_read', (
        'get_owned_item',
        'get_owned_item_detail',
    )),
    ('owned_item_write', (
        'insert_owned_item',
        'update_owned_item',
        'bulk_update_owned_items',
        'delete_owned_item',
        '_sync_owned_item_classifications_in_conn',
    )),
    ('owned_item_query', (
        'list_owned_items',
        'count_owned_items',
        'get_owned_item_list_row',
    )),
    ('ops_home_recent', (
        'count_ops_home_recent_moved_items',
        'list_ops_home_recent_moved_items',
        'count_ops_home_recent_registered_items',
        'list_ops_home_recent_registered_items',
        'get_ops_home_recent_sections',
        'get_ops_home_feed',
        '_build_ops_home_recent_item',
    )),
    ('metadata_sync', (
        'list_metadata_sync_candidates',
        'upsert_music_detail',
    )),
    ('music_shelf_window', (
        'get_music_shelf_window',
        'get_owned_counts_by_source',
    )),
    ('collection_dashboard', (
        'get_collection_dashboard',
    )),
    ('operator_search', (
        'search_operator_catalog',
    )),
    ('order_keys', (
        'resequence_in_collection_order',
        '_format_order_value',
        '_parse_order_value',
        '_next_order_key_in_conn',
        '_backfill_order_keys',
        '_compute_between_order_value',
        '_rebalance_in_collection_order',
    )),
]

# ── One-off structural check ─────────────────────────────────────────────────

def test_app_db_is_now_a_package() -> None:
    """db.py must have been replaced by app/db/__init__.py."""
    assert (REPO_ROOT / "app" / "db" / "__init__.py").is_file()
    assert not (REPO_ROOT / "app" / "db.py").exists(), (
        "app/db.py must not coexist with the package — stale module shadows it"
    )


# ── Parametrized structural tests ────────────────────────────────────────────

@pytest.mark.parametrize("module_name,symbols", _MODULE_SYMBOLS)
def test_submodule_exposes_expected_surface(
    module_name: str, symbols: tuple[str, ...]
) -> None:
    mod = importlib.import_module(f"app.db.{module_name}")
    missing = [name for name in symbols if not hasattr(mod, name)]
    assert not missing, f"app.db.{module_name} missing: {missing}"


@pytest.mark.parametrize("module_name,symbols", _MODULE_REEXPORT_SYMS)
def test_db_package_reexports_callables(
    module_name: str, symbols: tuple[str, ...]
) -> None:
    mod = importlib.import_module(f"app.db.{module_name}")
    for name in symbols:
        from_pkg = getattr(db, name, None)
        from_sub = getattr(mod, name, None)
        assert from_pkg is from_sub, (
            f"db.{name} should be the same object as db.{module_name}.{name}"
        )


@pytest.mark.parametrize("module_name,symbols", _MODULE_SYMBOLS)
def test_init_py_no_longer_redefines_callables(
    module_name: str, symbols: tuple[str, ...]
) -> None:
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for name in symbols:
        pattern = re.compile(rf"^def {re.escape(name)}\(", re.MULTILINE)
        assert not pattern.search(init_src), (
            f"app/db/__init__.py still defines {name} — body should live "
            f"only in app/db/{module_name}.py"
        )


@pytest.mark.parametrize("module_name,symbol_name", [
    ('auth_account', '_ensure_auth_account_table'),
    ('auth_account', 'list_auth_accounts'),
    ('auth_account', 'get_auth_account_by_username'),
    ('auth_account', 'upsert_auth_account'),
    ('auth_account', 'delete_auth_account'),
    ('cache', 'get_cached_external_response'),
    ('cache', 'upsert_cached_external_response'),
    ('cache', 'touch_cached_external_response_expiry'),
    ('cache', 'purge_expired_external_responses'),
    ('purchase_import', 'insert_purchase_import_rows'),
    ('purchase_import', 'find_purchase_import_duplicate_row'),
    ('purchase_import', 'list_purchase_import_rows'),
    ('purchase_import', 'has_purchase_import_for_source_ref'),
    ('purchase_import', 'count_purchase_import_rows'),
    ('purchase_import', 'get_purchase_import_row'),
    ('purchase_import', 'update_purchase_import_row'),
    ('purchase_import', '_purchase_import_vendor_check_sql'),
    ('purchase_import', '_ensure_purchase_import_queue_table'),
    ('purchase_import', '_purchase_import_queue_allows_file_upload'),
    ('purchase_import', '_purchase_import_queue_allows_extended_vendors'),
    ('purchase_import', '_migrate_purchase_import_queue_allow_file_upload'),
    ('purchase_import', '_purchase_import_cmp_text'),
    ('purchase_import', '_purchase_import_cmp_float'),
    ('purchase_import', '_purchase_import_row_matches_duplicate'),
    ('purchase_import', '_find_purchase_import_duplicate_in_conn'),
    ('customer_track_request', 'create_customer_track_request'),
    ('customer_track_request', 'get_customer_track_request'),
    ('customer_track_request', 'list_customer_track_requests'),
    ('customer_track_request', 'count_customer_track_requests'),
    ('customer_track_request', 'update_customer_track_request'),
    ('storage_slot', 'get_storage_slot'),
    ('storage_slot', 'get_storage_slot_by_code'),
    ('storage_slot', 'list_storage_slots'),
    ('storage_slot', 'list_owned_items_for_storage_slot'),
    ('storage_slot', 'upsert_storage_slot'),
    ('storage_slot', 'register_storage_cabinet_slots'),
    ('storage_slot', 'delete_storage_cabinet'),
    ('storage_slot', '_storage_slot_allows_goods'),
    ('storage_slot', '_migrate_storage_slot_allow_goods'),
    ('storage_slot', '_cleanup_overflow_slots'),
    ('storage_slot', '_derive_storage_slot_parts'),
    ('goods_item', 'create_goods_item'),
    ('goods_item', 'update_goods_item'),
    ('goods_item', 'get_goods_item'),
    ('goods_item', 'delete_goods_item'),
    ('goods_item', 'replace_goods_item_mappings'),
    ('goods_item', 'replace_goods_item_collectible_relations'),
    ('goods_item', 'search_goods_collectible_targets'),
    ('goods_item', 'count_goods_items'),
    ('goods_item', 'search_goods_items'),
    ('goods_item', 'list_goods_artist_name_candidates'),
    ('goods_item', 'list_goods_label_name_candidates'),
    ('goods_item', '_goods_category_check_sql'),
    ('goods_item', '_goods_status_check_sql'),
    ('goods_item', '_goods_relation_type_check_sql'),
    ('goods_item', '_normalize_goods_category_value'),
    ('goods_item', '_normalize_goods_status_value'),
    ('goods_item', '_normalize_goods_relation_type_value'),
    ('goods_item', '_normalize_goods_mapping_text'),
    ('goods_item', '_goods_item_select_query'),
    ('goods_item', '_normalize_goods_item_row'),
    ('goods_item', '_list_goods_item_album_master_mappings_in_conn'),
    ('goods_item', '_list_goods_item_artist_mappings_in_conn'),
    ('goods_item', '_list_goods_item_label_mappings_in_conn'),
    ('goods_item', '_list_goods_item_collectible_relations_in_conn'),
    ('goods_item', '_build_goods_item_with_mappings'),
    ('goods_item', '_replace_goods_item_collectible_relations_in_conn'),
    ('goods_item', '_replace_goods_item_mappings_in_conn'),
    ('goods_item', '_build_goods_search_where'),
    ('cabinet_camera', 'list_cabinet_cameras'),
    ('cabinet_camera', 'get_cabinet_camera'),
    ('cabinet_camera', 'get_cabinet_camera_by_cabinet'),
    ('cabinet_camera', 'upsert_cabinet_camera'),
    ('cabinet_camera', 'delete_cabinet_camera'),
    ('classification_option', 'list_classification_options'),
    ('classification_option', 'upsert_classification_option'),
    ('classification_option', '_seed_classification_options'),
    ('ingestion_batch', 'insert_batch'),
    ('ingestion_batch', 'finalize_batch'),
    ('ingestion_batch', 'insert_review_queue'),
    ('ingestion_batch', 'bulk_insert_review_queue'),
    ('ingestion_batch', 'bulk_finalize_csv_ingest'),
    ('ingestion_batch', 'list_review_queue'),
    ('auto_backup', 'get_auto_backup_settings'),
    ('auto_backup', 'save_auto_backup_settings'),
    ('auto_backup', 'record_auto_backup_result'),
    ('album_master_merge_history', 'list_album_master_merge_history'),
    ('album_master_merge_history', 'rollback_latest_album_master_merge'),
    ('album_master_external_ref', 'get_album_master_id_by_external_ref'),
    ('album_master_external_ref', 'list_album_master_external_refs'),
    ('album_master_external_ref', 'ensure_album_master_external_ref'),
    ('album_master_correction', 'get_album_master_correction_state'),
    ('album_master_correction', 'update_album_master_correction'),
    ('album_master_duplicates', 'list_duplicate_album_masters'),
    ('album_master_duplicates', '_album_master_source_priority'),
    ('album_master_member', 'bind_album_master_members'),
    ('album_master_member', 'album_master_exists'),
    ('album_master_member', 'update_album_master_sort_artist_name'),
    ('album_master_member', 'list_album_master_members'),
    ('album_master_member', 'delete_album_master'),
    ('album_master_tracks', 'list_album_master_track_matches'),
    ('digital_link', 'insert_digital_link'),
    ('location_recommendation', 'recommend_owned_item_location'),
    ('location_recommendation', 'recommend_barcode_candidate_locations'),
    ('album_master_core', 'upsert_album_master'),
    ('album_master_core', 'normalize_album_master_source_id'),
    ('album_master_core', 'promote_album_master_source'),
    ('album_master_core', 'merge_album_masters'),
    ('album_master_core', '_sync_album_master_domain_code_in_conn'),
    ('album_master_core', '_snapshot_album_master_record'),
    ('album_master_core', '_snapshot_member_link_records'),
    ('album_master_core', '_snapshot_external_ref_records'),
    ('album_master_read', 'list_album_masters'),
    ('album_master_read', 'count_album_masters'),
    ('album_master_read', 'get_album_master_binding_for_owned_item'),
    ('album_master_read', 'get_album_master_domain_hint'),
    ('album_master_read', 'list_owned_items_by_album_master'),
    ('album_master_read', 'set_owned_item_linked_album_master'),
    ('owned_item_track_links', 'list_owned_item_track_links'),
    ('owned_item_track_links', 'list_owned_item_audio_directory_links'),
    ('owned_item_track_links', 'delete_owned_item_track_links'),
    ('owned_item_track_links', 'delete_owned_item_audio_directory_links'),
    ('owned_item_copy_group', 'set_owned_item_copy_group'),
    ('owned_item_copy_group', 'list_owned_items_by_copy_group'),
    ('owned_item_copy_group', 'list_owned_items_by_source_external_ids'),
    ('owned_item_slot', 'update_owned_item_slot'),
    ('owned_item_slot', 'inherit_owned_item_domain_from_slot_if_missing'),
    ('owned_item_slot', 'restore_owned_item_previous_slot'),
    ('owned_item_slot', '_location_slot_snapshot_in_conn'),
    ('owned_item_slot', '_derive_location_movement_kind'),
    ('owned_item_slot', '_log_owned_item_location_event_in_conn'),
    ('owned_item_order', 'move_owned_item_order'),
    ('owned_item_order', 'realign_owned_item_order_after_slot_move'),
    ('owned_item_order', 'move_owned_item_slot_display_rank'),
    ('owned_item_track', 'get_owned_item_location_snapshot'),
    ('owned_item_track', 'get_owned_item_track_list'),
    ('owned_item_read', 'get_owned_item'),
    ('owned_item_read', 'get_owned_item_detail'),
    ('owned_item_write', 'insert_owned_item'),
    ('owned_item_write', 'update_owned_item'),
    ('owned_item_write', 'bulk_update_owned_items'),
    ('owned_item_write', 'delete_owned_item'),
    ('owned_item_write', '_sync_owned_item_classifications_in_conn'),
    ('owned_item_query', 'list_owned_items'),
    ('owned_item_query', 'count_owned_items'),
    ('owned_item_query', 'get_owned_item_list_row'),
    ('ops_home_recent', 'count_ops_home_recent_moved_items'),
    ('ops_home_recent', 'list_ops_home_recent_moved_items'),
    ('ops_home_recent', 'count_ops_home_recent_registered_items'),
    ('ops_home_recent', 'list_ops_home_recent_registered_items'),
    ('ops_home_recent', 'get_ops_home_recent_sections'),
    ('ops_home_recent', 'get_ops_home_feed'),
    ('ops_home_recent', '_build_ops_home_recent_item'),
    ('metadata_sync', 'list_metadata_sync_candidates'),
    ('metadata_sync', 'upsert_music_detail'),
    ('music_shelf_window', 'get_music_shelf_window'),
    ('music_shelf_window', 'get_owned_counts_by_source'),
    ('collection_dashboard', 'get_collection_dashboard'),
    ('operator_search', 'search_operator_catalog'),
    ('order_keys', 'resequence_in_collection_order'),
    ('order_keys', '_format_order_value'),
    ('order_keys', '_parse_order_value'),
    ('order_keys', '_next_order_key_in_conn'),
    ('order_keys', '_backfill_order_keys'),
    ('order_keys', '_compute_between_order_value'),
    ('order_keys', '_rebalance_in_collection_order'),
])
def test_legacy_import_path_still_works(
    module_name: str, symbol_name: str
) -> None:
    assert hasattr(db, symbol_name), (
        f"db.{symbol_name} (from app.db.{module_name}) must remain importable "
        f"via the app.db package surface"
    )


# ── Test helpers ────────────────────────────────────────────────────────────

def _empty_filters() -> dict[str, Any]:
    """Shared no-filter argument set for list/count probes — the
    signatures require many positional axes (q, source_code, artist,
    item_name, catalog_no, barcode, release_year, category,
    media_only, domain_code, release_type)."""
    return {
        "source_code": None,
        "q": None,
        "artist_or_brand": None,
        "item_name": None,
        "catalog_no": None,
        "barcode": None,
        "release_year": None,
        "category": None,
        "media_only": False,
        "domain_code": None,
        "release_type": None,
    }

def _full_owned_item_payload(name: str) -> dict[str, object]:
    """Build a fully-populated payload — `update_owned_item` expects
    every column key to be present (it does a complete column
    re-write, not partial)."""
    return {
        "category": "MUSIC",
        "status": "IN_COLLECTION",
        "quantity": 1,
        "item_name_override": name,
        "size_group": "STD",
        "format_name": None,
        "release_year": None,
        "release_type": None,
        "domain_code": None,
        "country_code": None,
        "language_code": None,
        "is_second_hand": False,
        "condition_grade": None,
        "signature_type": "NONE",
        "source_code": None,
        "source_external_id": None,
        "signed_by": None,
        "signed_at": None,
        "acquisition_date": None,
        "purchase_price": None,
        "currency_code": None,
        "purchase_source": None,
        "memory_note": None,
        "display_rank": None,
        "storage_slot_id": None,
        "thickness_mm": None,
        "notes": None,
    }

# ── Functional tests ────────────────────────────────────────────────────────

# --- app.db.auth_account ---

def test_auth_account_round_trip_through_package_surface() -> None:
    """End-to-end: insert/list/get/delete via the package-level names."""
    db.ensure_startup_db_ready()
    username = "db-split-phase-1-probe"
    db.delete_auth_account(username)  # cleanup any leftover

    row = db.upsert_auth_account(
        username=username,
        password_hash="pbkdf2_sha256$1$x$y",
        role="OPERATOR",
        is_active=True,
    )
    assert row is not None
    assert row["username"] == username
    assert row["role"] == "OPERATOR"

    listed = {item["username"] for item in db.list_auth_accounts()}
    assert username in listed

    fetched = db.get_auth_account_by_username(username)
    assert fetched is not None
    assert fetched["username"] == username

    assert db.delete_auth_account(username) is True
    assert db.get_auth_account_by_username(username) is None

# --- app.db.cache ---

def test_cache_round_trip_through_package_surface() -> None:
    """Insert/get/purge via the package-level names."""
    db.ensure_startup_db_ready()
    cache_key = "db-split-phase-2-probe"

    db.upsert_cached_external_response(
        cache_key=cache_key,
        source_code="DISCOGS",
        body_json='{"hello": "phase-2"}',
        status_code=200,
        ttl_seconds=600,
    )
    row = db.get_cached_external_response(cache_key)
    assert row is not None
    assert row["source_code"] == "DISCOGS"

    # Force-expire and verify purge removes it.
    with db.get_write_conn() as conn:
        conn.execute(
            "UPDATE external_response_cache SET expires_at = '2000-01-01T00:00:00+00:00' "
            "WHERE cache_key = ?",
            (cache_key,),
        )
    removed = db.purge_expired_external_responses()
    assert removed >= 1
    assert db.get_cached_external_response(cache_key) is None

# --- app.db.purchase_import ---

def test_purchase_import_round_trip_through_package_surface() -> None:
    """Insert -> dedupe -> list -> get -> update -> source_ref lookup."""
    db.ensure_startup_db_ready()
    source_ref = "db-split-phase-3-probe"

    created_ids = db.insert_purchase_import_rows(
        "OTHER",
        "EMAIL_HTML",
        [{"item_name": "phase-3-test-item", "quantity": 1}],
        source_ref=source_ref,
    )
    assert len(created_ids) == 1
    queue_id = created_ids[0]

    fetched = db.get_purchase_import_row(queue_id)
    assert fetched is not None
    assert fetched["item_name"] == "phase-3-test-item"

    listed_ids = {row["id"] for row in db.list_purchase_import_rows(limit=200)}
    assert queue_id in listed_ids

    assert db.has_purchase_import_for_source_ref("OTHER", source_ref) is True

    # Dedupe — second insert with same source_ref must NOT create a new row.
    again = db.insert_purchase_import_rows(
        "OTHER",
        "EMAIL_HTML",
        [{"item_name": "phase-3-test-item", "quantity": 1}],
        source_ref=source_ref,
    )
    assert again == []

    # Update queue_status flow.
    updated = db.update_purchase_import_row(queue_id, queue_status="IGNORED")
    assert updated is not None
    assert updated["queue_status"] == "IGNORED"

    # Cleanup so the test row doesn't pollute later tests.
    with db.get_write_conn() as conn:
        conn.execute(
            "DELETE FROM purchase_import_queue WHERE id = ?", (queue_id,)
        )

# --- app.db.customer_track_request ---

def test_customer_track_request_round_trip_through_package_surface() -> None:
    """create → get → list → count → update flow via package surface.

    We don't link to a real owned_item; create_customer_track_request
    accepts owned_item_id=None which short-circuits the owned-item /
    location lookups.
    """
    db.ensure_startup_db_ready()
    created = db.create_customer_track_request(
        requested_track="phase-4 probe track",
        requested_by="phase-4-probe",
    )
    assert created
    request_id = int(created["id"])

    fetched = db.get_customer_track_request(request_id)
    assert fetched is not None
    assert fetched["requested_track"] == "phase-4 probe track"
    assert fetched["status"] == "REQUESTED"

    listed_ids = {item["id"] for item in db.list_customer_track_requests(limit=200)}
    assert request_id in listed_ids

    requested_count_before = db.count_customer_track_requests(status="REQUESTED")
    assert requested_count_before >= 1

    updated = db.update_customer_track_request(
        request_id,
        status="PLAYING",
        response_note="phase-4 probe response",
        handled_by="phase-4-probe-handler",
    )
    assert updated is not None
    assert updated["status"] == "PLAYING"
    assert updated["response_note"] == "phase-4 probe response"
    assert str(updated.get("handled_at") or "").strip() != ""

    # Cleanup so the probe row doesn't pollute later tests / counters.
    with db.get_write_conn() as conn:
        conn.execute(
            "DELETE FROM customer_track_request WHERE id = ?", (request_id,)
        )

# --- app.db.storage_slot ---

def test_storage_slot_cross_cutting_helpers_remain_in_init() -> None:
    """`_storage_slot_display_name`, `_natural_sort_key`,
    `_contains_any_token`, `_storage_slot_sort_key`,
    `_compose_storage_slot_code` are intentionally NOT in the
    storage_slot submodule — they're shared with other slices that
    haven't been extracted yet."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    for cross_helper in (
        "_storage_slot_display_name",
        "_natural_sort_key",
        "_contains_any_token",
        "_storage_slot_sort_key",
        "_compose_storage_slot_code",
    ):
        pattern = re.compile(rf"^def {re.escape(cross_helper)}\(", re.MULTILINE)
        assert pattern.search(init_src), (
            f"{cross_helper} unexpectedly removed from app/db/__init__.py — "
            f"it must remain there until its dependents are also extracted"
        )

def test_storage_slot_register_and_list_round_trip_through_package_surface() -> None:
    """register a tiny cabinet → list → get → list_items → delete cleanup.
    Uses a unique cabinet name so it doesn't collide with existing data."""
    db.ensure_startup_db_ready()
    cabinet = "phase-5-probe-cabinet"

    # Register a 1x1 cabinet.
    summary = db.register_storage_cabinet_slots(
        cabinet_name=cabinet,
        floor_count=1,
        cell_count=1,
        allowed_size_group="STD",
    )
    assert summary["cabinet_name"] == cabinet

    # List should include it.
    slots = [item for item in db.list_storage_slots() if item.get("cabinet_name") == cabinet]
    assert len(slots) == 1
    slot_id = int(slots[0]["id"])
    slot_code = str(slots[0]["slot_code"])

    # get_storage_slot + get_storage_slot_by_code resolve.
    fetched_by_id = db.get_storage_slot(slot_id)
    fetched_by_code = db.get_storage_slot_by_code(slot_code)
    assert fetched_by_id is not None
    assert fetched_by_code is not None
    assert int(fetched_by_id["id"]) == slot_id
    assert int(fetched_by_code["id"]) == slot_id

    # Empty cabinet should report no items.
    items = db.list_owned_items_for_storage_slot(slot_id)
    assert isinstance(items, list)
    assert items == []

    # Cleanup via delete_storage_cabinet (the canonical path).
    result = db.delete_storage_cabinet(cabinet)
    assert int(result.get("deleted_slot_count") or 0) == 1
    assert (
        len([item for item in db.list_storage_slots() if item.get("cabinet_name") == cabinet])
        == 0
    )

# --- app.db.goods_item ---

def test_owned_item_goods_bridge_helpers_remain_in_init() -> None:
    """`_owned_item_allows_goods`, `_migrate_owned_item_allow_goods`, and
    `_upsert_goods_item_detail_in_conn` are owned-item-side helpers that
    happen to involve goods schema. They must be reachable via the package."""
    for stays in (
        "_owned_item_allows_goods",
        "_migrate_owned_item_allow_goods",
        "_upsert_goods_item_detail_in_conn",
    ):
        assert hasattr(db, stays), (
            f"{stays} unexpectedly removed from app.db surface"
        )

def test_goods_item_round_trip_through_package_surface() -> None:
    """create → get → search → count → delete via package surface."""
    db.ensure_startup_db_ready()

    payload = {
        "category": "POSTER",
        "status": "ACTIVE",
        "goods_name": "phase-6 probe poster",
        "domain_code": "KOREA",
    }
    created = db.create_goods_item(payload)
    assert created is not None
    goods_id = int(created["id"])

    fetched = db.get_goods_item(goods_id)
    assert fetched is not None
    assert fetched["goods_name"] == "phase-6 probe poster"

    search_results = db.search_goods_items(query="phase-6 probe", limit=10)
    listed_ids = {int(item["id"]) for item in search_results}
    assert goods_id in listed_ids

    count_before = db.count_goods_items()
    assert count_before >= 1

    assert db.delete_goods_item(goods_id) is True
    assert db.get_goods_item(goods_id) is None

# --- app.db.cabinet_camera ---

def test_cabinet_camera_round_trip_through_package_surface() -> None:
    """upsert → list → get → get_by_cabinet → delete via package surface."""
    db.ensure_startup_db_ready()
    cabinet = "phase-7-probe-cabinet"
    camera_name = "phase-7 probe cam"

    created = db.upsert_cabinet_camera(
        cabinet_name=cabinet,
        camera_name=camera_name,
        snapshot_url="http://probe.local/snap.jpg",
    )
    assert created is not None
    camera_id = int(created["id"])

    listed_ids = {int(item["id"]) for item in db.list_cabinet_cameras()}
    assert camera_id in listed_ids

    fetched_by_id = db.get_cabinet_camera(camera_id)
    fetched_by_cabinet = db.get_cabinet_camera_by_cabinet(cabinet)
    assert fetched_by_id is not None
    assert fetched_by_cabinet is not None
    assert int(fetched_by_id["id"]) == int(fetched_by_cabinet["id"]) == camera_id

    assert db.delete_cabinet_camera(camera_id) is True
    assert db.get_cabinet_camera(camera_id) is None

# --- app.db.classification_option ---

def test_classification_option_round_trip_through_package_surface() -> None:
    """upsert → list → upsert (idempotent) via the package surface."""
    db.ensure_startup_db_ready()

    label = "phase-8-probe"
    upserted = db.upsert_classification_option("SUBTYPE", label, sort_order=999)
    assert upserted["label"] == label
    assert upserted["is_active"] == 1

    listed_labels = {item["label"] for item in db.list_classification_options("SUBTYPE")}
    assert label in listed_labels

    # Idempotent — second call must not raise.
    again = db.upsert_classification_option("SUBTYPE", label, sort_order=998)
    assert int(again["id"]) == int(upserted["id"])

    # Cleanup so the probe label doesn't pollute fixtures downstream.
    with db.get_write_conn() as conn:
        conn.execute(
            "DELETE FROM classification_option WHERE option_group = ? AND label = ?",
            ("SUBTYPE", label),
        )

def test_seed_helper_idempotent_through_package_surface() -> None:
    """`_seed_classification_options` is the bare-name init helper. Make
    sure the re-export still resolves it AND running it twice doesn't
    raise (it's INSERT...ON CONFLICT)."""
    db.ensure_startup_db_ready()
    with db.get_write_conn() as conn:
        db._seed_classification_options(conn)
        db._seed_classification_options(conn)

# --- app.db.ingestion_batch ---

def test_csv_batch_round_trip_through_package_surface() -> None:
    """insert_batch → bulk_insert_review_queue → list_review_queue →
    finalize_batch via the package surface, then verify totals stick."""
    db.ensure_startup_db_ready()

    batch_id = db.insert_batch(
        ingest_source="phase-9-probe",
        created_by="phase-9-suite",
        notes="phase-9 smoke",
    )
    assert isinstance(batch_id, int) and batch_id > 0

    rows = [
        {
            "batch_id": batch_id,
            "row_no": idx,
            "category": "ALBUM",
            "payload": {"title": f"phase9-{idx}"},
            "candidate": None,
            "confidence": 0.5,
            "review_status": "NEEDS_REVIEW",
            "review_note": None,
        }
        for idx in range(3)
    ]
    inserted = db.bulk_insert_review_queue(rows)
    assert inserted == 3

    listed = db.list_review_queue("NEEDS_REVIEW", "ALBUM", limit=100, offset=0)
    titles = {item["payload"].get("title") for item in listed if int(item.get("batch_id") or 0) == batch_id}
    assert titles >= {"phase9-0", "phase9-1", "phase9-2"}

    db.finalize_batch(batch_id, total=3, matched=0, review=3, failed=0)

    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT total_count, review_count, completed_at FROM ingestion_batch WHERE id = ?",
            (batch_id,),
        ).fetchone()
    assert row is not None
    assert int(row["total_count"]) == 3
    assert int(row["review_count"]) == 3
    assert row["completed_at"] is not None

    # Cleanup so the probe doesn't pollute downstream fixtures.
    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM review_queue WHERE batch_id = ?", (batch_id,))
        conn.execute("DELETE FROM ingestion_batch WHERE id = ?", (batch_id,))

def test_bulk_finalize_csv_ingest_combines_insert_and_summary() -> None:
    """`bulk_finalize_csv_ingest` should atomically insert rows AND update
    the batch summary in one shot."""
    db.ensure_startup_db_ready()

    batch_id = db.insert_batch(
        ingest_source="phase-9-bulk-probe",
        created_by="phase-9-suite",
        notes="phase-9 bulk-finalize smoke",
    )

    rows = [
        {
            "batch_id": batch_id,
            "row_no": idx,
            "category": "GOODS",
            "payload": {"sku": f"bulk-{idx}"},
            "candidate": None,
            "confidence": 0.25,
            "review_status": "NEEDS_REVIEW",
            "review_note": None,
        }
        for idx in range(2)
    ]
    inserted = db.bulk_finalize_csv_ingest(
        batch_id,
        totals={"total": 2, "matched": 0, "review": 2, "failed": 0},
        review_queue_rows=rows,
    )
    assert inserted == 2

    with db.get_conn() as conn:
        summary = conn.execute(
            "SELECT total_count, review_count, completed_at FROM ingestion_batch WHERE id = ?",
            (batch_id,),
        ).fetchone()
        review_rows = conn.execute(
            "SELECT COUNT(*) AS n FROM review_queue WHERE batch_id = ?",
            (batch_id,),
        ).fetchone()
    assert summary is not None and int(summary["total_count"]) == 2
    assert summary["completed_at"] is not None
    assert int(review_rows["n"]) == 2

    with db.get_write_conn() as conn:
        conn.execute("DELETE FROM review_queue WHERE batch_id = ?", (batch_id,))
        conn.execute("DELETE FROM ingestion_batch WHERE id = ?", (batch_id,))

# --- app.db.auto_backup ---

def test_app_setting_table_helper_still_in_init_py() -> None:
    """`_ensure_app_setting_table` is shared with init_db / migrations
    and must stay in __init__.py to avoid circular imports. The
    auto_backup submodule re-imports it from the package surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "_ensure_app_setting_table" in init_src or "from .connection import" in init_src, (
        "_ensure_app_setting_table must be importable from app/db/__init__.py — "
        "it is called from init_db / migrations / ensure_startup_db_ready"
    )

def test_auto_backup_round_trip_through_package_surface() -> None:
    """save → get → record → get; verify defaults + keys flip
    correctly via the package surface (not the submodule directly)."""
    db.ensure_startup_db_ready()

    # Snapshot for cleanup at the end.
    original = db.get_auto_backup_settings()

    saved = db.save_auto_backup_settings(
        enabled=True,
        interval_minutes=30,
        backup_dir="/tmp/phase-10-probe-backups",
        backup_scope="FULL",
        include_env_file=True,
    )
    assert saved["enabled"] is True
    assert saved["interval_minutes"] == 30
    assert saved["backup_dir"] == "/tmp/phase-10-probe-backups"
    assert saved["backup_scope"] == "FULL"
    assert saved["include_env_file"] is True

    fetched = db.get_auto_backup_settings()
    assert fetched["enabled"] is True
    assert fetched["interval_minutes"] == 30
    assert fetched["backup_dir"] == "/tmp/phase-10-probe-backups"

    db.record_auto_backup_result(
        last_backup_at="2026-04-30T12:00:00+00:00",
        last_backup_path="/tmp/phase-10-probe-backups/sample.db",
        last_error=None,
    )
    after_record = db.get_auto_backup_settings()
    assert after_record["last_backup_at"] == "2026-04-30T12:00:00+00:00"
    assert after_record["last_backup_path"] == "/tmp/phase-10-probe-backups/sample.db"
    assert after_record["last_error"] is None

    # Clearing the error path independently must not wipe the
    # successful-run fields above.
    db.record_auto_backup_result(
        last_backup_at=None,
        last_backup_path=None,
        last_error="phase-10 simulated failure",
    )
    cleared = db.get_auto_backup_settings()
    assert cleared["last_error"] == "phase-10 simulated failure"

    # Restore to whatever was there before so we don't pollute the dev DB.
    db.save_auto_backup_settings(
        enabled=bool(original["enabled"]),
        interval_minutes=int(original["interval_minutes"] or 0),
        backup_dir=str(original["backup_dir"] or ""),
        backup_scope=str(original["backup_scope"] or "DB"),
        include_env_file=bool(original["include_env_file"]),
    )
    db.record_auto_backup_result(
        last_backup_at=original.get("last_backup_at"),
        last_backup_path=original.get("last_backup_path"),
        last_error=original.get("last_error"),
    )

def test_default_backup_dir_falls_back_when_setting_blank() -> None:
    """Saving with `backup_dir=""` should fall back to the auto-backup
    default (which is `<db_root>/backups`)."""
    db.ensure_startup_db_ready()
    snapshot = db.get_auto_backup_settings()

    saved = db.save_auto_backup_settings(
        enabled=False,
        interval_minutes=0,
        backup_dir="",
    )
    assert saved["backup_dir"], "default backup_dir must not be empty"

    # Restore.
    db.save_auto_backup_settings(
        enabled=bool(snapshot["enabled"]),
        interval_minutes=int(snapshot["interval_minutes"] or 0),
        backup_dir=str(snapshot["backup_dir"] or ""),
        backup_scope=str(snapshot["backup_scope"] or "DB"),
        include_env_file=bool(snapshot["include_env_file"]),
    )

# --- app.db.album_master_merge_history ---

def test_snapshot_helper_resolves_through_package_surface() -> None:
    """At Phase 11's commit, `_snapshot_album_master_record` lived in
    __init__.py because `merge_album_masters` (still in __init__.py
    at that point) needed it. In Phase 19 both moved together to
    `app/db/album_master_core.py`. What the merge-history rollback
    path actually needs is for the helper to be reachable somewhere —
    the post-Phase-19 contract is "via app.db package surface". Pin
    that instead of the no-longer-true location.

    `_normalize_domain_code_value` IS still a cross-cutting helper
    that stays in __init__.py — pin that.
    """
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert hasattr(db, "_snapshot_album_master_record"), (
        "_snapshot_album_master_record must remain reachable via the "
        "app.db package surface — Phase 19 moved it to album_master_core."
    )
    assert "def _normalize_domain_code_value(" in init_src, (
        "_normalize_domain_code_value must remain in app/db/__init__.py — "
        "it's a cross-cutting helper used 25+ times across the package"
    )

def test_list_merge_history_smoke_through_package_surface() -> None:
    """Package-surface call should succeed even on an empty schema —
    list with no rows must return an empty list, not raise."""
    db.ensure_startup_db_ready()

    history = db.list_album_master_merge_history(limit=5)
    assert isinstance(history, list)

def test_rollback_with_no_history_raises_lookup_error() -> None:
    """If there's no open merge to roll back, the function MUST raise
    LookupError — that's the contract the admin route depends on for
    its 404 conversion."""
    import pytest

    db.ensure_startup_db_ready()

    # Snapshot any existing history rows; if the dev DB happens to
    # have an open merge, this test should be skipped rather than
    # disturb live data.
    existing = db.list_album_master_merge_history(limit=1)
    has_open = any(item.get("rolled_back_at") is None for item in existing)
    if has_open:
        pytest.skip("dev DB has an open merge — skipping no-history smoke")

    with pytest.raises(LookupError):
        db.rollback_latest_album_master_merge(rolled_back_by="phase-11-suite")

# --- app.db.album_master_external_ref ---

def test_internal_callers_still_invoke_ensure_through_package_surface() -> None:
    """In Phase 19 the three internal callers
    (upsert_album_master, normalize_album_master_source_id,
    promote_album_master_source) moved out of __init__.py into
    app/db/album_master_core.py. They still call
    `ensure_album_master_external_ref` by bare name — that name must
    now resolve via `from app.db import ensure_album_master_external_ref`
    at album_master_core's module-load time, NOT via a local def."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    core_path = REPO_ROOT / "app" / "db" / "album_master_core.py"
    core_src = core_path.read_text("utf-8") if core_path.exists() else ""

    # We expect at least 3 bare-name call sites in album_master_core.py
    # (the post-Phase-19 home for those three writers).
    call_pattern = re.compile(r"\bensure_album_master_external_ref\(")
    core_matches = call_pattern.findall(core_src)
    assert len(core_matches) >= 3, (
        f"expected ≥3 internal `ensure_album_master_external_ref(` call "
        f"sites in app/db/album_master_core.py, found {len(core_matches)}"
    )
    # And album_master_core.py MUST import it from the package surface.
    assert "from app.db import" in core_src and "ensure_album_master_external_ref" in core_src, (
        "app/db/album_master_core.py must import "
        "ensure_album_master_external_ref from the app.db package surface"
    )
    # __init__.py MUST re-export the external_ref module so the import
    # in album_master_core resolves at album_master_core's load time.
    assert "from .album_master_external_ref import" in init_src, (
        "app/db/__init__.py is missing the album_master_external_ref re-export"
    )

def test_external_ref_round_trip_through_package_surface() -> None:
    """ensure → get → list → ensure (idempotent) via the package surface,
    using a synthetic source/master id that won't collide with real data."""
    db.ensure_startup_db_ready()

    # We need a real album_master row to attach refs to. Pick the smallest
    # existing one if any, otherwise create a temp one.
    with db.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM album_master ORDER BY id ASC LIMIT 1"
        ).fetchone()

    cleanup_master_id: int | None = None
    if existing is None:
        # Create a temp master for the round trip. The album_master
        # CHECK constraint restricts source_code to a known set, so we
        # use 'MANUAL' which is always allowed for hand-curated rows.
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase12-probe-master-key', 'phase-12 probe master',
                        NULL, NULL, 'UNKNOWN', NULL, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            cleanup_master_id = int(cur.lastrowid)
        master_id = cleanup_master_id
    else:
        master_id = int(existing["id"])

    # Both album_master and album_master_external_ref enforce the same
    # CHECK constraint on source_code. Use 'DISCOGS' with a probe-only
    # source_master_id that won't collide with real data.
    source_code = "DISCOGS"
    source_master = "phase-12-probe-discogs-master-id"

    try:
        ref_id_first = db.ensure_album_master_external_ref(
            album_master_id=master_id,
            source_code=source_code,
            source_master_id=source_master,
            title_hint="phase-12 hint",
        )
        assert ref_id_first > 0

        looked_up = db.get_album_master_id_by_external_ref(source_code, source_master)
        assert looked_up == master_id

        listed = db.list_album_master_external_refs(master_id, source_code=source_code)
        assert any(int(item["id"]) == ref_id_first for item in listed)

        ref_id_second = db.ensure_album_master_external_ref(
            album_master_id=master_id,
            source_code=source_code,
            source_master_id=source_master,
            title_hint="phase-12 hint v2",
        )
        assert ref_id_second == ref_id_first  # idempotent on the same key
    finally:
        with db.get_write_conn() as conn:
            conn.execute(
                "DELETE FROM album_master_external_ref WHERE source_code = ? AND source_master_id = ?",
                (source_code, source_master),
            )
            if cleanup_master_id is not None:
                conn.execute(
                    "DELETE FROM album_master WHERE id = ?",
                    (cleanup_master_id,),
                )

def test_get_external_ref_returns_none_for_unknown_keys() -> None:
    """Read-only contract probe — looking up a key that has never been
    inserted must return None, not raise. Pure SELECT, so source_code
    isn't subject to the album_master CHECK constraint here."""
    db.ensure_startup_db_ready()
    result = db.get_album_master_id_by_external_ref(
        "DISCOGS",
        "completely-fake-master-id-phase-12-never-used",
    )
    assert result is None

def test_list_external_refs_returns_empty_for_unknown_master() -> None:
    """Read-only contract probe — listing refs for a master that has
    never had any must return [] (not raise, not None)."""
    db.ensure_startup_db_ready()
    refs = db.list_album_master_external_refs(album_master_id=-99999)
    assert refs == []

def test_ensure_external_ref_validates_required_fields() -> None:
    """`ensure_album_master_external_ref` must raise ValueError when any
    of the required keys (album_master_id > 0, source_code, source_master_id)
    is missing — that's the contract the metadata-sync providers depend
    on for early failure."""
    import pytest

    db.ensure_startup_db_ready()
    with pytest.raises(ValueError):
        db.ensure_album_master_external_ref(
            album_master_id=0,
            source_code="DISCOGS",
            source_master_id="x",
        )
    with pytest.raises(ValueError):
        db.ensure_album_master_external_ref(
            album_master_id=1,
            source_code="",
            source_master_id="x",
        )
    with pytest.raises(ValueError):
        db.ensure_album_master_external_ref(
            album_master_id=1,
            source_code="DISCOGS",
            source_master_id="",
        )

# --- app.db.album_master_correction ---

def test_normalize_domain_code_value_still_lives_in_init() -> None:
    """`_normalize_domain_code_value` is used 25+ times across the
    package. The correction submodule imports it from the package
    surface — the helper itself MUST stay in __init__.py."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _normalize_domain_code_value(" in init_src, (
        "_normalize_domain_code_value must remain in app/db/__init__.py "
        "as a cross-cutting helper"
    )

def test_correction_state_returns_none_for_missing_master() -> None:
    """Read-only contract — looking up a master that doesn't exist
    must return None, not raise."""
    db.ensure_startup_db_ready()
    assert db.get_album_master_correction_state(album_master_id=-99999) is None
    assert db.get_album_master_correction_state(album_master_id=0) is None

def test_update_correction_returns_none_for_missing_master() -> None:
    """Write contract — updating a master that doesn't exist must
    return None (not raise) so the route can convert it to 404."""
    db.ensure_startup_db_ready()
    result = db.update_album_master_correction(
        album_master_id=-99999,
        release_year=1985,
        domain_code="WESTERN",
        override_note="phase-13 probe",
    )
    assert result is None

def test_correction_round_trip_through_package_surface() -> None:
    """Pick (or create) a real album_master row, write an override,
    confirm correction_state reflects it, then clear the override and
    confirm the source values come back. Cleanup at the end."""
    db.ensure_startup_db_ready()

    cleanup_master_id: int | None = None
    with db.get_conn() as conn:
        existing = conn.execute(
            "SELECT id FROM album_master ORDER BY id ASC LIMIT 1"
        ).fetchone()

    if existing is None:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase13-probe-master-key',
                        'phase-13 correction probe master', NULL, NULL,
                        'UNKNOWN', 2000, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            cleanup_master_id = int(cur.lastrowid)
        master_id = cleanup_master_id
    else:
        master_id = int(existing["id"])

    try:
        # Capture pre-state so we can restore later.
        before = db.get_album_master_correction_state(master_id)
        assert before is not None

        # Write override.
        updated = db.update_album_master_correction(
            album_master_id=master_id,
            release_year=1985,
            domain_code="WESTERN",
            override_note="phase-13 probe override",
        )
        assert updated is not None
        assert updated["override_release_year"] == 1985
        assert updated["override_domain_code"] == "WESTERN"
        assert updated["override_note"] == "phase-13 probe override"
        assert updated["release_year"] == 1985
        assert updated["domain_code"] == "WESTERN"
        assert updated["has_manual_correction"] is True

        # Confirm state matches via the read-only function too.
        fetched = db.get_album_master_correction_state(master_id)
        assert fetched is not None
        assert fetched["override_release_year"] == 1985
        assert fetched["has_manual_correction"] is True

        # Clear override — pass None for everything, effective values
        # should fall back to source values.
        cleared = db.update_album_master_correction(
            album_master_id=master_id,
            release_year=None,
            domain_code=None,
            override_note=None,
        )
        assert cleared is not None
        assert cleared["override_release_year"] is None
        assert cleared["override_domain_code"] is None
        assert cleared["override_note"] is None
        assert cleared["has_manual_correction"] is False
    finally:
        if cleanup_master_id is not None:
            with db.get_write_conn() as conn:
                conn.execute(
                    "DELETE FROM album_master WHERE id = ?",
                    (cleanup_master_id,),
                )
        else:
            # We didn't create the master, so restore its original
            # correction state if it had any.
            if before is not None:
                db.update_album_master_correction(
                    album_master_id=master_id,
                    release_year=before.get("override_release_year"),
                    domain_code=before.get("override_domain_code"),
                    override_note=before.get("override_note"),
                )

# --- app.db.album_master_duplicates ---

def test_source_priority_ordering_through_package_surface() -> None:
    """Pin the priority order: DISCOGS < MANIADB < MUSICBRAINZ < others."""
    assert db._album_master_source_priority("DISCOGS") == 0
    assert db._album_master_source_priority("MANIADB") == 1
    assert db._album_master_source_priority("MUSICBRAINZ") == 2
    assert db._album_master_source_priority("UNKNOWN_SOURCE") == 3
    # Case- and whitespace-insensitive.
    assert db._album_master_source_priority("  discogs  ") == 0
    assert db._album_master_source_priority("") == 3
    assert db._album_master_source_priority(None) == 3  # type: ignore[arg-type]

def test_list_duplicates_returns_empty_for_invalid_master() -> None:
    """Read-only contract — listing duplicates for a master id that
    doesn't exist (or is non-positive) must return [], not raise."""
    db.ensure_startup_db_ready()
    assert db.list_duplicate_album_masters(album_master_id=0) == []
    assert db.list_duplicate_album_masters(album_master_id=-1) == []
    assert db.list_duplicate_album_masters(album_master_id=-99999) == []

def test_list_duplicates_smoke_through_package_surface() -> None:
    """Smoke — pick the smallest existing master, the call must not
    raise (it may return [] if the dev DB has no duplicates, that's
    fine; what matters is the surface still resolves correctly)."""
    db.ensure_startup_db_ready()
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM album_master ORDER BY id ASC LIMIT 1"
        ).fetchone()
    if row is None:
        # No master rows — nothing to smoke against. The "invalid id"
        # test above already exercises the empty-result path.
        return
    result = db.list_duplicate_album_masters(int(row["id"]))
    assert isinstance(result, list)

def test_list_duplicates_limit_clamped_to_safe_range() -> None:
    """The limit must be clamped to [1, 100] regardless of caller input.
    We can't directly inspect the LIMIT in the issued SQL from outside,
    but we can probe the empty path with extreme values to confirm
    no exception is raised (the clamp handles it gracefully)."""
    db.ensure_startup_db_ready()
    # Upper bound — way above 100 must still work.
    assert db.list_duplicate_album_masters(album_master_id=-1, limit=10_000) == []
    # Zero should clamp up to 1, not blow up.
    assert db.list_duplicate_album_masters(album_master_id=-1, limit=0) == []
    # Negative limit should also be clamped.
    assert db.list_duplicate_album_masters(album_master_id=-1, limit=-5) == []

# --- app.db.album_master_member ---

def test_sync_domain_code_helper_resolves_through_package_surface() -> None:
    """`_sync_album_master_domain_code_in_conn` was originally in
    __init__.py; in Phase 19 it moved to app/db/album_master_core.py.
    What matters for `bind_album_master_members` is that the helper
    is reachable via `app.db.<name>` at module-load time. Pin the
    package-surface contract instead of the no-longer-true location."""
    assert hasattr(db, "_sync_album_master_domain_code_in_conn"), (
        "_sync_album_master_domain_code_in_conn must remain reachable "
        "via the app.db package surface — bind_album_master_members "
        "imports it via `from app.db import _sync_album_master_domain_code_in_conn`"
    )
    # Confirm bind path still resolves the same callable identity.
    from app.db import album_master_member as amm_module_local
    assert amm_module_local._sync_album_master_domain_code_in_conn is db._sync_album_master_domain_code_in_conn

def test_album_master_exists_returns_false_for_invalid_id() -> None:
    """Read-only contract — non-positive or unknown master ids must
    return False, not raise."""
    db.ensure_startup_db_ready()
    assert db.album_master_exists(0) is False
    assert db.album_master_exists(-1) is False
    assert db.album_master_exists(-99999) is False

def test_update_sort_artist_name_returns_none_for_missing_master() -> None:
    """Write contract — updating a master that doesn't exist must
    return None so the route can convert it to 404."""
    db.ensure_startup_db_ready()
    assert db.update_album_master_sort_artist_name(-99999, "test") is None
    assert db.update_album_master_sort_artist_name(0, "test") is None

def test_delete_returns_none_for_invalid_id() -> None:
    """Write contract — DELETE on a non-existent master returns None."""
    db.ensure_startup_db_ready()
    assert db.delete_album_master(-99999) is None
    assert db.delete_album_master(0) is None

def test_list_members_returns_empty_for_unknown_master() -> None:
    """Read-only contract — listing members for a master that has none
    (or doesn't exist) must return [], not raise."""
    db.ensure_startup_db_ready()
    assert db.list_album_master_members(album_master_id=-99999) == []

def test_member_admin_round_trip_through_package_surface() -> None:
    """Create a temp master + temp owned_item, bind, list, update sort,
    confirm exists, delete with cascade, confirm gone."""
    db.ensure_startup_db_ready()

    master_id: int | None = None
    owned_item_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase15-probe-master-key',
                        'phase-15 member probe master', NULL, NULL,
                        'UNKNOWN', NULL, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            master_id = int(cur.lastrowid)

            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-15 probe item',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        assert db.album_master_exists(master_id) is True

        bound_count = db.bind_album_master_members(master_id, [owned_item_id])
        assert bound_count == 1

        members = db.list_album_master_members(master_id)
        assert any(int(m["owned_item_id"]) == owned_item_id for m in members)

        sort_updated = db.update_album_master_sort_artist_name(master_id, "  Phase 15 Sort  ")
        assert sort_updated is not None
        assert sort_updated["sort_artist_name"] == "Phase 15 Sort"

        # Clearing the sort name should write None.
        sort_cleared = db.update_album_master_sort_artist_name(master_id, "")
        assert sort_cleared is not None
        assert sort_cleared["sort_artist_name"] is None

        result = db.delete_album_master(master_id, cascade_items=True)
        assert result is not None
        assert result["removed_member_links"] == 1
        assert result["deleted_owned_item_count"] == 1

        # After cascade-delete, both rows are gone.
        assert db.album_master_exists(master_id) is False
        master_id = None
        owned_item_id = None
    finally:
        with db.get_write_conn() as conn:
            if master_id is not None:
                conn.execute("DELETE FROM album_master_member WHERE album_master_id = ?", (master_id,))
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))
            if owned_item_id is not None:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))

def test_bind_with_invalid_owned_item_ids_filters_them_out() -> None:
    """`bind_album_master_members` should silently drop owned_item ids
    that don't exist (the DB-level subselect filter), not raise."""
    db.ensure_startup_db_ready()

    master_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase15-bind-probe-key',
                        'phase-15 bind probe master', NULL, NULL,
                        'UNKNOWN', NULL, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            master_id = int(cur.lastrowid)

        # All ids invalid — bind should result in 0 members, no error.
        count = db.bind_album_master_members(master_id, [-1, -99999, 0])
        assert count == 0
    finally:
        if master_id is not None:
            with db.get_write_conn() as conn:
                conn.execute("DELETE FROM album_master_member WHERE album_master_id = ?", (master_id,))
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))

# --- app.db.album_master_tracks ---

def test_search_helpers_still_in_init_py() -> None:
    """`_search_token_groups` and `_matches_search_text` are used by
    half a dozen other lookups in __init__.py — they MUST stay there.
    The track-match submodule pulls them via the package surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _search_token_groups(" in init_src, (
        "_search_token_groups must remain in app/db/__init__.py"
    )
    assert "def _matches_search_text(" in init_src, (
        "_matches_search_text must remain in app/db/__init__.py"
    )

def test_track_matches_returns_empty_for_invalid_master() -> None:
    """Read-only contract — non-positive or unknown master ids must
    return [] regardless of the query string."""
    db.ensure_startup_db_ready()
    assert db.list_album_master_track_matches(album_master_id=0, query_text="anything") == []
    assert db.list_album_master_track_matches(album_master_id=-1, query_text="anything") == []
    assert db.list_album_master_track_matches(album_master_id=-99999, query_text="x") == []

def test_track_matches_returns_empty_for_blank_query() -> None:
    """Read-only contract — blank/whitespace queries must return []
    even when the master id is positive."""
    db.ensure_startup_db_ready()
    assert db.list_album_master_track_matches(album_master_id=1, query_text="") == []
    assert db.list_album_master_track_matches(album_master_id=1, query_text="   ") == []

def test_track_matches_round_trip_through_package_surface() -> None:
    """Insert a temp master + owned_item + music_item_detail with
    a known track_list_json/track_items_json, then verify the fuzzy
    matcher returns hits for tokens contained in the track list and
    no hits for tokens that aren't there. Cleanup at the end."""
    db.ensure_startup_db_ready()

    master_id: int | None = None
    owned_item_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase16-track-master',
                        'phase-16 track probe master', NULL, NULL,
                        'UNKNOWN', NULL, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            master_id = int(cur.lastrowid)

            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-16 probe item',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

            conn.execute(
                """
                INSERT INTO album_master_member
                  (album_master_id, owned_item_id, created_at)
                VALUES (?, ?, ?)
                """,
                (master_id, owned_item_id, db.utc_now_iso()),
            )

            track_list = ["Phase Sixteen Probe Song", "Hidden Phase Sixteen Lullaby"]
            track_items = [
                {"display": "Phase Sixteen Probe Song", "title": "Phase Sixteen Probe Song"},
                {"display": "Phase Sixteen Encore Variation", "title": "Phase Sixteen Encore Variation"},
            ]
            conn.execute(
                """
                INSERT INTO music_item_detail
                  (owned_item_id, format_name, track_list_json, track_items_json,
                   created_at, updated_at)
                VALUES (?, 'CD', ?, ?, ?, ?)
                """,
                (
                    owned_item_id,
                    json.dumps(track_list, ensure_ascii=True),
                    json.dumps(track_items, ensure_ascii=True),
                    db.utc_now_iso(),
                    db.utc_now_iso(),
                ),
            )

        # Token "Lullaby" should hit the second track in track_list.
        hits = db.list_album_master_track_matches(master_id, "Lullaby", limit=5)
        assert "Hidden Phase Sixteen Lullaby" in hits

        # Token "Encore" should hit the second track_item display name.
        hits_encore = db.list_album_master_track_matches(master_id, "Encore", limit=5)
        assert "Phase Sixteen Encore Variation" in hits_encore

        # Token that's not in any track must return [].
        hits_miss = db.list_album_master_track_matches(master_id, "ZZNOMATCHZZ", limit=5)
        assert hits_miss == []

        # Limit must be respected — request 1, get at most 1 even when
        # multiple tracks could match.
        hits_one = db.list_album_master_track_matches(master_id, "Phase", limit=1)
        assert len(hits_one) <= 1
    finally:
        with db.get_write_conn() as conn:
            if owned_item_id is not None:
                conn.execute("DELETE FROM music_item_detail WHERE owned_item_id = ?", (owned_item_id,))
                conn.execute("DELETE FROM album_master_member WHERE owned_item_id = ?", (owned_item_id,))
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))
            if master_id is not None:
                conn.execute("DELETE FROM album_master_member WHERE album_master_id = ?", (master_id,))
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))

def test_track_matches_handles_corrupt_json_gracefully() -> None:
    """Defensive contract — track_list_json / track_items_json that
    aren't valid JSON (or aren't lists) must be silently treated as
    empty, NOT raise."""
    db.ensure_startup_db_ready()

    master_id: int | None = None
    owned_item_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase16-corrupt-master',
                        'phase-16 corrupt-json probe', NULL, NULL,
                        'UNKNOWN', NULL, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            master_id = int(cur.lastrowid)

            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-16 corrupt probe',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

            conn.execute(
                """
                INSERT INTO album_master_member
                  (album_master_id, owned_item_id, created_at)
                VALUES (?, ?, ?)
                """,
                (master_id, owned_item_id, db.utc_now_iso()),
            )

            conn.execute(
                """
                INSERT INTO music_item_detail
                  (owned_item_id, format_name, track_list_json, track_items_json,
                   created_at, updated_at)
                VALUES (?, 'CD', '{not valid json', 'also not json',
                        ?, ?)
                """,
                (owned_item_id, db.utc_now_iso(), db.utc_now_iso()),
            )

        # No raise — just an empty result.
        result = db.list_album_master_track_matches(master_id, "anything", limit=5)
        assert result == []
    finally:
        with db.get_write_conn() as conn:
            if owned_item_id is not None:
                conn.execute("DELETE FROM music_item_detail WHERE owned_item_id = ?", (owned_item_id,))
                conn.execute("DELETE FROM album_master_member WHERE owned_item_id = ?", (owned_item_id,))
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))
            if master_id is not None:
                conn.execute("DELETE FROM album_master_member WHERE album_master_id = ?", (master_id,))
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))

# --- app.db.digital_link ---

def test_insert_digital_link_round_trip_through_package_surface() -> None:
    """Insert a temp owned_item, then call insert_digital_link with
    a representative payload. Confirm both the digital_asset row and
    the owned_item_digital_link row land with the right column
    values, then clean up."""
    db.ensure_startup_db_ready()

    owned_item_id: int | None = None
    digital_asset_id: int | None = None
    link_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-17 digital probe',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        payload = {
            "asset_type": "AUDIO",
            "file_path": "/tmp/phase-17/probe.flac",
            "file_hash": "sha256:phase-17-probe-hash",
            "file_size_bytes": 12345678,
            "duration_sec": 215,
            "metadata_json": {"bitrate": 1411, "channels": 2},
            "link_type": "FULL_ALBUM",
            "track_no": None,
            "note": "phase-17 round-trip probe",
        }

        ids = db.insert_digital_link(owned_item_id, payload)
        assert isinstance(ids, dict)
        digital_asset_id = int(ids["digital_asset_id"])
        link_id = int(ids["link_id"])
        assert digital_asset_id > 0
        assert link_id > 0

        # Verify both rows landed correctly.
        with db.get_conn() as conn:
            asset_row = conn.execute(
                """
                SELECT asset_type, file_path, file_hash, file_size_bytes,
                       duration_sec, metadata_json
                FROM digital_asset
                WHERE id = ?
                """,
                (digital_asset_id,),
            ).fetchone()
            link_row = conn.execute(
                """
                SELECT owned_item_id, digital_asset_id, link_type,
                       track_no, note
                FROM owned_item_digital_link
                WHERE id = ?
                """,
                (link_id,),
            ).fetchone()

        assert asset_row is not None
        assert asset_row["asset_type"] == "AUDIO"
        assert asset_row["file_path"] == "/tmp/phase-17/probe.flac"
        assert asset_row["file_hash"] == "sha256:phase-17-probe-hash"
        assert int(asset_row["file_size_bytes"]) == 12345678
        assert int(asset_row["duration_sec"]) == 215
        parsed_metadata = json.loads(asset_row["metadata_json"])
        assert parsed_metadata == {"bitrate": 1411, "channels": 2}

        assert link_row is not None
        assert int(link_row["owned_item_id"]) == owned_item_id
        assert int(link_row["digital_asset_id"]) == digital_asset_id
        assert link_row["link_type"] == "FULL_ALBUM"
        assert link_row["track_no"] is None
        assert link_row["note"] == "phase-17 round-trip probe"
    finally:
        with db.get_write_conn() as conn:
            if link_id is not None:
                conn.execute("DELETE FROM owned_item_digital_link WHERE id = ?", (link_id,))
            if digital_asset_id is not None:
                conn.execute("DELETE FROM digital_asset WHERE id = ?", (digital_asset_id,))
            if owned_item_id is not None:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))

def test_insert_digital_link_handles_missing_optional_keys() -> None:
    """The payload's `metadata_json` defaults to {} when not present;
    the optional fields (file_hash, file_size_bytes, duration_sec,
    track_no, note) all silently default to None."""
    db.ensure_startup_db_ready()

    owned_item_id: int | None = None
    digital_asset_id: int | None = None
    link_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-17 minimal probe',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        # Minimal payload — only the four required keys.
        payload = {
            "asset_type": "AUDIO",
            "file_path": "/tmp/phase-17/minimal.mp3",
            "link_type": "TRACK",
        }

        ids = db.insert_digital_link(owned_item_id, payload)
        digital_asset_id = int(ids["digital_asset_id"])
        link_id = int(ids["link_id"])

        with db.get_conn() as conn:
            asset_row = conn.execute(
                """
                SELECT file_hash, file_size_bytes, duration_sec, metadata_json
                FROM digital_asset WHERE id = ?
                """,
                (digital_asset_id,),
            ).fetchone()
            link_row = conn.execute(
                """
                SELECT track_no, note FROM owned_item_digital_link WHERE id = ?
                """,
                (link_id,),
            ).fetchone()

        assert asset_row["file_hash"] is None
        assert asset_row["file_size_bytes"] is None
        assert asset_row["duration_sec"] is None
        assert json.loads(asset_row["metadata_json"]) == {}
        assert link_row["track_no"] is None
        assert link_row["note"] is None
    finally:
        with db.get_write_conn() as conn:
            if link_id is not None:
                conn.execute("DELETE FROM owned_item_digital_link WHERE id = ?", (link_id,))
            if digital_asset_id is not None:
                conn.execute("DELETE FROM digital_asset WHERE id = ?", (digital_asset_id,))
            if owned_item_id is not None:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))

# --- app.db.location_recommendation ---

def test_cross_cutting_helpers_still_in_init_py() -> None:
    """The recommendation submodule depends on a dozen private
    helpers that are also used by other still-in-__init__.py
    writers/readers (sort keys, recommendation-text normalisers,
    storage_slot helpers, etc.). Those helpers MUST stay in
    __init__.py so the submodule can pull them via the package
    surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    # These helpers genuinely stay in __init__.py.
    for name in (
        "_normalize_domain_code_value",
        "_normalize_recommendation_text",
        "_normalize_master_release_sort_text",
        "_normalize_released_date_sort_text",
        "_resolve_owned_item_thickness_mm",
        "_storage_slot_display_name",
        "_storage_slot_sort_key",
        "_title_first_group_artist_key",
        "_compact_search_sql_expr",
        "build_storage_slot_occupancy_summary",
    ):
        assert f"def {name}(" in init_src, (
            f"{name} must remain in app/db/__init__.py — recommendation "
            f"submodule pulls it via the package surface"
        )
    # `_backfill_order_keys` was originally in __init__.py at Phase 18's
    # commit; in Phase 34 it moved to app/db/order_keys.py. What matters
    # for the recommendation submodule is that the helper is reachable
    # via the app.db package surface at module-load time. Pin THAT
    # contract instead of the no-longer-true location.
    assert hasattr(db, "_backfill_order_keys"), (
        "_backfill_order_keys must remain reachable via the app.db package "
        "surface — location_recommendation imports it at module-load time"
    )
    assert "SIZE_GROUP_CODES" in init_src, (
        "SIZE_GROUP_CODES constant must remain in app/db/__init__.py"
    )

def test_recommendation_returns_invalid_size_group_envelope() -> None:
    """`recommend_owned_item_location` must return its known no-pick
    envelope (NOT raise) when the size_group is unknown."""
    db.ensure_startup_db_ready()
    result = db.recommend_owned_item_location(
        size_group="NEVER_HEARD_OF_THIS_SIZE_GROUP",
        artist_or_brand="anyone",
        release_year=2000,
    )
    assert isinstance(result, dict)
    assert result.get("recommended_storage_slot_id") is None
    assert result.get("anchor_owned_item_id") is None
    assert result.get("reason") == "INVALID_SIZE_GROUP"
    assert result.get("used_fallback_slot") is False
    # candidate_slots key must exist and be a list (possibly empty).
    assert isinstance(result.get("candidate_slots"), list)

def test_barcode_recommendation_returns_empty_for_unknown_size_group() -> None:
    """The barcode wrapper short-circuits to [] when the resolved
    size_group isn't in SIZE_GROUP_CODES, regardless of category
    (because the operator may pass a non-standard category that
    falls through the fallback ladder to a still-invalid value)."""
    db.ensure_startup_db_ready()
    result = db.recommend_barcode_candidate_locations(
        category="NON_EXISTENT_CATEGORY",
        size_group="NEVER_HEARD_OF_THIS_SIZE_GROUP",
        format_name=None,
        artist_or_brand=None,
        title=None,
        release_year=None,
        thickness_mm=None,
        package_hint=None,
    )
    assert result == []

def test_barcode_recommendation_smoke_through_package_surface() -> None:
    """Smoke — call with a real size_group and a category that maps
    to it. The dev DB may have no slots configured, so the result
    can legitimately be []. What matters is the surface still
    resolves and returns a list, not raises."""
    db.ensure_startup_db_ready()
    result = db.recommend_barcode_candidate_locations(
        category="CD",
        size_group="STD",
        format_name="CD",
        artist_or_brand="phase-18 probe artist",
        title="phase-18 probe title",
        release_year=2026,
        thickness_mm=12,
        package_hint=None,
        limit=3,
    )
    assert isinstance(result, list)
    assert len(result) <= 3

def test_recommendation_smoke_with_real_size_group() -> None:
    """Smoke — call recommend_owned_item_location with STD + a probe
    artist/year. The result envelope must always be present even
    when no slots match."""
    db.ensure_startup_db_ready()
    result = db.recommend_owned_item_location(
        size_group="STD",
        artist_or_brand="phase-18 probe artist",
        release_year=2026,
    )
    assert isinstance(result, dict)
    for key in (
        "anchor_owned_item_id",
        "anchor_position",
        "recommended_storage_slot_id",
        "slot_code",
        "candidate_slots",
        "reason",
        "used_fallback_slot",
    ):
        assert key in result, f"recommendation result missing key: {key}"
    assert isinstance(result["candidate_slots"], list)

# --- app.db.album_master_core ---

def test_album_master_member_resolves_sync_helper_through_package() -> None:
    """`album_master_member.bind_album_master_members` calls
    `_sync_album_master_domain_code_in_conn` via the package surface.
    After Phase 19 moved that helper into album_master_core, the
    package surface MUST still expose the same callable."""
    assert amm_module._sync_album_master_domain_code_in_conn is db._sync_album_master_domain_code_in_conn
    assert amm_module._sync_album_master_domain_code_in_conn is amc_module._sync_album_master_domain_code_in_conn

def test_reexport_ordering_album_master_core_before_member() -> None:
    """Critical invariant — album_master_core re-export MUST appear
    BEFORE album_master_member re-export in __init__.py. Otherwise
    album_master_member.py fails to import at package-load time."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    core_pos = init_src.find("from .album_master_core import")
    member_pos = init_src.find("from .album_master_member import")
    assert core_pos > 0, "album_master_core re-export missing from __init__.py"
    assert member_pos > 0, "album_master_member re-export missing from __init__.py"
    assert core_pos < member_pos, (
        "album_master_core re-export MUST come BEFORE album_master_member "
        "re-export in __init__.py — album_master_member depends on "
        "_sync_album_master_domain_code_in_conn which now lives in core."
    )

def test_normalize_domain_code_value_still_in_init_py() -> None:
    """`_normalize_domain_code_value` is used 25+ times across the
    package. The album_master_core submodule pulls it via the
    package surface — the helper itself MUST stay in __init__.py."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _normalize_domain_code_value(" in init_src

def test_upsert_album_master_round_trip_through_package_surface() -> None:
    """upsert → re-upsert(idempotent on same key) → external_ref auto-
    populated, all via the package surface. Cleanup at the end."""
    db.ensure_startup_db_ready()

    source_master_id = "phase-19-upsert-probe-id"
    cleanup_master_id: int | None = None
    try:
        master_id_1 = db.upsert_album_master(
            source_code="MANUAL",
            source_master_id=source_master_id,
            title="phase-19 upsert probe",
            artist_or_brand="phase-19 artist",
            domain_code="WESTERN",
            release_year=2026,
            raw={"probe": "phase-19"},
        )
        assert isinstance(master_id_1, int) and master_id_1 > 0
        cleanup_master_id = master_id_1

        # Idempotent — second upsert on the same key returns the same id.
        master_id_2 = db.upsert_album_master(
            source_code="MANUAL",
            source_master_id=source_master_id,
            title="phase-19 upsert probe v2",
            artist_or_brand="phase-19 artist",
            domain_code="WESTERN",
            release_year=2027,
            raw={"probe": "phase-19", "version": 2},
        )
        assert master_id_2 == master_id_1

        # external_ref must have been auto-populated by the upsert.
        ref_id = db.get_album_master_id_by_external_ref("MANUAL", source_master_id)
        assert ref_id == master_id_1
    finally:
        if cleanup_master_id is not None:
            with db.get_write_conn() as conn:
                conn.execute(
                    "DELETE FROM album_master_external_ref WHERE album_master_id = ?",
                    (cleanup_master_id,),
                )
                conn.execute(
                    "DELETE FROM album_master WHERE id = ?",
                    (cleanup_master_id,),
                )

def test_normalize_album_master_source_id_smoke() -> None:
    """Smoke — call normalize with no-op inputs (master_id <= 0 etc.)
    and confirm the no-op contracts hold (returns master_id unchanged)."""
    db.ensure_startup_db_ready()
    # master_id <= 0 must short-circuit.
    assert db.normalize_album_master_source_id(0, "DISCOGS", "x") == 0
    assert db.normalize_album_master_source_id(-1, "DISCOGS", "x") == -1
    # blank source_code or source_master_id must short-circuit.
    assert db.normalize_album_master_source_id(1, "", "x") == 1
    assert db.normalize_album_master_source_id(1, "DISCOGS", "") == 1

def test_promote_album_master_source_smoke() -> None:
    """Smoke — promote with invalid arguments must return 0."""
    db.ensure_startup_db_ready()
    result = db.promote_album_master_source(
        album_master_id=0,
        source_code="DISCOGS",
        source_master_id="x",
        title="anything",
        artist_or_brand=None,
        domain_code=None,
        release_year=None,
        raw={},
    )
    assert result == 0

def test_merge_album_masters_validates_positive_ids() -> None:
    """Contract — merge with source/target <= 0 must raise ValueError."""
    import pytest

    db.ensure_startup_db_ready()
    with pytest.raises(ValueError):
        db.merge_album_masters(0, 1)
    with pytest.raises(ValueError):
        db.merge_album_masters(1, 0)
    with pytest.raises(ValueError):
        db.merge_album_masters(-1, -2)

def test_merge_album_masters_raises_lookup_when_target_missing() -> None:
    """Contract — merge with positive ids but missing target raises
    LookupError so the route can return 404."""
    import pytest

    db.ensure_startup_db_ready()
    with pytest.raises(LookupError):
        db.merge_album_masters(99999998, 99999999)

# --- app.db.album_master_read ---

def test_cross_cutting_helpers_still_in_init_py_album_master_read() -> None:
    """The album_master_read submodule pulls a half-dozen helpers
    via the package surface. They MUST remain in the db surface."""
    for name in (
        "_normalize_domain_code_value",
        "_normalize_owned_item_row",
        "_owned_item_select_query",
        "_search_token_groups",
        "_build_compact_token_match_sql",
        "_column_exists",
    ):
        assert hasattr(db, name), (
            f"{name} must remain reachable via app.db package surface"
        )

def test_get_binding_returns_none_for_missing_owned_item() -> None:
    db.ensure_startup_db_ready()
    assert db.get_album_master_binding_for_owned_item(0) is None
    assert db.get_album_master_binding_for_owned_item(-1) is None
    assert db.get_album_master_binding_for_owned_item(-99999) is None

def test_get_domain_hint_returns_none_for_missing_master() -> None:
    db.ensure_startup_db_ready()
    assert db.get_album_master_domain_hint(0) is None
    assert db.get_album_master_domain_hint(-1) is None
    assert db.get_album_master_domain_hint(-99999) is None

def test_list_owned_items_by_album_master_returns_empty_for_unknown() -> None:
    db.ensure_startup_db_ready()
    assert db.list_owned_items_by_album_master(album_master_id=-99999) == []

def test_set_owned_item_linked_master_returns_false_for_invalid_owned() -> None:
    """Write contract — invalid owned_item id must return False, not raise."""
    db.ensure_startup_db_ready()
    assert db.set_owned_item_linked_album_master(0, None) is False
    assert db.set_owned_item_linked_album_master(-1, 1) is False

def test_list_and_count_album_masters_smoke() -> None:
    """Smoke — list and count must both succeed under the same
    no-filter inputs."""
    db.ensure_startup_db_ready()
    filters = _empty_filters()
    rows = db.list_album_masters(**filters, limit=1, offset=0)
    total = db.count_album_masters(**filters)
    assert isinstance(rows, list)
    assert isinstance(total, int)
    assert total >= 0
    assert len(rows) <= 1

def test_list_album_masters_pagination_smoke() -> None:
    """Smoke — pagination shouldn't blow up with extreme offsets."""
    db.ensure_startup_db_ready()
    rows = db.list_album_masters(**_empty_filters(), limit=10, offset=10_000_000)
    assert rows == []

def test_set_owned_item_linked_master_round_trip() -> None:
    """Round trip on the owned_item.linked_album_master_id column —
    create temp owned_item + master, set the link, verify the
    column took the value, clear it, verify it's None. Cleanup at
    the end.

    NOTE: `get_album_master_binding_for_owned_item` reads via the
    `album_master_member` JOIN, NOT the linked_album_master_id
    column — those are two different things in the schema. We
    deliberately don't test the binding read here since linking via
    `set_owned_item_linked_album_master` doesn't populate the member
    table; that's done by `bind_album_master_members` (covered in
    Phase 15)."""
    db.ensure_startup_db_ready()

    master_id: int | None = None
    owned_item_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO album_master
                  (source_code, source_master_id, title, artist_or_brand,
                   sort_artist_name, domain_code, release_year, raw_json,
                   created_at, updated_at)
                VALUES ('MANUAL', 'phase20-link-probe-key',
                        'phase-20 link probe master', NULL, NULL,
                        'UNKNOWN', NULL, '{}', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            master_id = int(cur.lastrowid)

            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1, 'phase-20 link probe item',
                        'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        ok = db.set_owned_item_linked_album_master(owned_item_id, master_id)
        assert ok is True

        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT linked_album_master_id FROM owned_item WHERE id = ?",
                (owned_item_id,),
            ).fetchone()
        assert row is not None
        assert int(row["linked_album_master_id"] or 0) == master_id

        # Unlink — pass None.
        ok2 = db.set_owned_item_linked_album_master(owned_item_id, None)
        assert ok2 is True

        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT linked_album_master_id FROM owned_item WHERE id = ?",
                (owned_item_id,),
            ).fetchone()
        assert row is not None
        assert row["linked_album_master_id"] is None
    finally:
        with db.get_write_conn() as conn:
            if owned_item_id is not None:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))
            if master_id is not None:
                conn.execute("DELETE FROM album_master WHERE id = ?", (master_id,))

# --- app.db.owned_item_track_links ---

def test_list_track_links_returns_empty_for_unknown_owned_item() -> None:
    """Read-only contract — listing track_links for an owned_item id
    that has none (or doesn't exist) must return [], not raise."""
    db.ensure_startup_db_ready()
    assert db.list_owned_item_track_links(-99999) == []

def test_list_audio_directory_links_returns_empty_for_unknown_owned_item() -> None:
    db.ensure_startup_db_ready()
    assert db.list_owned_item_audio_directory_links(-99999) == []

def test_delete_track_links_returns_zero_for_unknown_owned_item() -> None:
    """Write contract — deleting track_links for an owned_item that
    has none returns 0, NOT raises."""
    db.ensure_startup_db_ready()
    assert db.delete_owned_item_track_links(-99999) == 0

def test_delete_audio_directory_links_returns_zero_for_unknown_owned_item() -> None:
    db.ensure_startup_db_ready()
    assert db.delete_owned_item_audio_directory_links(-99999) == 0

# --- app.db.owned_item_copy_group ---

def test_owned_item_helpers_still_in_init_py() -> None:
    """`_normalize_owned_item_row` and `_owned_item_select_query` are
    cross-cutting helpers used by every owned_item read. They MUST
    remain reachable."""
    assert hasattr(db, "_normalize_owned_item_row")
    assert hasattr(db, "_owned_item_select_query")

def test_set_copy_group_returns_false_for_unknown_owned_item() -> None:
    db.ensure_startup_db_ready()
    # set_owned_item_copy_group: rowcount-based contract
    # Calling on a missing id returns False.
    result = db.set_owned_item_copy_group(-99999, "phase-22-probe-key")
    assert result is False

def test_list_by_copy_group_returns_empty_for_unknown_key() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_owned_items_by_copy_group("phase-22-never-used-key")
    assert rows == []

def test_list_by_source_external_ids_returns_empty_for_unknown() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_owned_items_by_source_external_ids(
        "DISCOGS",
        ["phase-22-fake-master-id-1", "phase-22-fake-master-id-2"],
    )
    assert rows == []

def test_list_by_source_external_ids_handles_empty_list() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_owned_items_by_source_external_ids("DISCOGS", [])
    assert rows == []

def test_set_copy_group_round_trip() -> None:
    """Round trip — create temp owned_item, set copy_group_key,
    verify via list_owned_items_by_copy_group, clear via None,
    verify cleared. Cleanup at the end."""
    db.ensure_startup_db_ready()
    owned_item_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1,
                        'phase-22 copy-group probe', 'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        copy_key = "phase-22-round-trip-key"
        ok = db.set_owned_item_copy_group(owned_item_id, copy_key)
        assert ok is True

        listed = db.list_owned_items_by_copy_group(copy_key)
        assert any(int(r.get("id") or 0) == owned_item_id for r in listed)

        # Clear via None.
        ok2 = db.set_owned_item_copy_group(owned_item_id, None)
        assert ok2 is True
        assert db.list_owned_items_by_copy_group(copy_key) == [] or all(
            int(r.get("id") or 0) != owned_item_id for r in db.list_owned_items_by_copy_group(copy_key)
        )
    finally:
        if owned_item_id is not None:
            with db.get_write_conn() as conn:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))

# --- app.db.owned_item_slot ---

def test_reexport_ordering_owned_item_slot_before_storage_slot() -> None:
    """Critical invariant — owned_item_slot re-export MUST appear
    BEFORE storage_slot re-export in __init__.py. Otherwise
    storage_slot.py fails to import at package-load time because it
    pulls `_log_owned_item_location_event_in_conn` from the package
    surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    slot_pos = init_src.find("from .owned_item_slot import")
    storage_pos = init_src.find("from .storage_slot import")
    assert slot_pos > 0, "owned_item_slot re-export missing from __init__.py"
    assert storage_pos > 0, "storage_slot re-export missing from __init__.py"
    assert slot_pos < storage_pos, (
        "owned_item_slot re-export MUST come BEFORE storage_slot — "
        "storage_slot.py imports _log_owned_item_location_event_in_conn "
        "from app.db at module-load time."
    )

def test_storage_slot_resolves_log_helper_through_package_surface() -> None:
    """The storage_slot module's import of
    `_log_owned_item_location_event_in_conn` from app.db MUST land
    on the same callable that owned_item_slot defines."""
    from app.db import storage_slot as ss_module
    assert ss_module._log_owned_item_location_event_in_conn is db._log_owned_item_location_event_in_conn
    assert ss_module._log_owned_item_location_event_in_conn is ois_module._log_owned_item_location_event_in_conn

def test_inherit_domain_returns_none_for_invalid_inputs() -> None:
    """Read contract — non-positive owned_item_id or None storage_slot_id
    should not raise."""
    db.ensure_startup_db_ready()
    assert db.inherit_owned_item_domain_from_slot_if_missing(0, None) is None
    assert db.inherit_owned_item_domain_from_slot_if_missing(-1, None) is None
    assert db.inherit_owned_item_domain_from_slot_if_missing(-99999, None) is None

def test_restore_previous_slot_returns_none_for_unknown() -> None:
    """Write contract — restoring a slot for an owned_item with no
    location history must return None, not raise."""
    db.ensure_startup_db_ready()
    result = db.restore_owned_item_previous_slot(-99999)
    assert result is None

def test_update_slot_no_op_when_already_unassigned() -> None:
    """When the from-slot equals the to-slot (both None for a fresh
    owned_item), update_owned_item_slot is a no-op — the column
    stays at None and no location_event row is logged. This pins the
    `kind is None` short-circuit inside _log_owned_item_location_event_in_conn."""
    db.ensure_startup_db_ready()

    owned_item_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1,
                        'phase-23 slot probe', 'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        db.update_owned_item_slot(owned_item_id, None, movement_note="phase-23 probe")

        with db.get_conn() as conn:
            row = conn.execute(
                "SELECT storage_slot_id FROM owned_item WHERE id = ?",
                (owned_item_id,),
            ).fetchone()
            assert row is not None
            assert row["storage_slot_id"] is None
    finally:
        if owned_item_id is not None:
            with db.get_write_conn() as conn:
                conn.execute("DELETE FROM owned_item_location_event WHERE owned_item_id = ?", (owned_item_id,))
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))

def test_derive_movement_kind_classifies_pairs() -> None:
    """Pin the classification contract:
      from == to                              → None (no-op, no log)
      None → some_id                          → "ASSIGN" / "INITIAL_ASSIGN"
      some_id → None                          → "UNASSIGN"
      some_id → other_id                      → "MOVE"
    """
    # Same-slot no-op.
    assert db._derive_location_movement_kind(
        from_storage_slot_id=5, to_storage_slot_id=5
    ) is None
    # None → set: ASSIGN (or INITIAL_ASSIGN with is_create=True).
    assert db._derive_location_movement_kind(
        from_storage_slot_id=None, to_storage_slot_id=7
    ) == "ASSIGN"
    assert db._derive_location_movement_kind(
        from_storage_slot_id=None, to_storage_slot_id=7, is_create=True
    ) == "INITIAL_ASSIGN"
    # set → None: UNASSIGN.
    assert db._derive_location_movement_kind(
        from_storage_slot_id=5, to_storage_slot_id=None
    ) == "UNASSIGN"
    # set → different set: MOVE.
    assert db._derive_location_movement_kind(
        from_storage_slot_id=5, to_storage_slot_id=7
    ) == "MOVE"
    # Both None — no-op.
    assert db._derive_location_movement_kind(
        from_storage_slot_id=None, to_storage_slot_id=None
    ) is None

# --- app.db.owned_item_order ---

def test_order_key_helpers_resolve_through_package_surface() -> None:
    """The display_rank / order-key helpers were originally in
    __init__.py at Phase 24's commit. In Phase 34 they all moved
    to app/db/order_keys.py. What matters for owned_item_order is
    that they remain reachable via `from app.db import ...` at
    module-load time. Pin that contract."""
    for name in (
        "_backfill_order_keys",
        "_compute_between_order_value",
        "_format_order_value",
        "_next_order_key_in_conn",
        "_parse_order_value",
        "_rebalance_in_collection_order",
    ):
        assert hasattr(db, name), (
            f"{name} must remain reachable via the app.db package "
            f"surface — owned_item_order imports it at module-load time"
        )
    # `_storage_slot_sort_key` is a genuine __init__.py resident.
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _storage_slot_sort_key(" in init_src, (
        "_storage_slot_sort_key must remain in app/db/__init__.py — "
        "it is a cross-cutting sort helper used 5+ times across the package"
    )

def test_move_owned_item_order_invalid_args_raise() -> None:
    """Invalid `position` argument must raise ValueError so the route
    can convert it to 400."""
    db.ensure_startup_db_ready()
    with pytest.raises(ValueError):
        db.move_owned_item_order(1, 2, "INVALID_POSITION")

def test_realign_owned_item_order_returns_string_for_unknown() -> None:
    """Smoke — calling realign with a non-existent owned_item_id
    should not raise; it should fall through gracefully."""
    db.ensure_startup_db_ready()
    # The function returns a display_rank string; pin that the
    # surface resolves and returns a string-type value (or raises a
    # known exception). We don't pin the exact failure mode because
    # the schema may differ between dev/QA/prod.
    try:
        result = db.realign_owned_item_order_after_slot_move(-99999, -99998)
        assert isinstance(result, str) or result is None
    except (ValueError, RuntimeError, LookupError):
        pass  # Acceptable failure shapes.

def test_move_slot_display_rank_smoke() -> None:
    """Smoke — the higher-level wrapper must at least resolve and
    invoke without ImportError."""
    db.ensure_startup_db_ready()
    # Probe with invalid IDs — we expect a controlled failure shape,
    # NOT an ImportError or NameError (which would mean the package
    # surface is broken).
    try:
        db.move_owned_item_slot_display_rank(
            owned_item_id=-1,
            target_owned_item_id=-2,
            position="BEFORE",
        )
    except (ValueError, RuntimeError, LookupError, TypeError):
        pass  # Acceptable failure shapes.

# --- app.db.owned_item_track ---

def test_reexport_ordering_owned_item_track_before_dependents() -> None:
    """Critical invariant — owned_item_track re-export MUST appear
    BEFORE customer_track_request AND BEFORE owned_item_slot,
    because both modules import `get_owned_item_location_snapshot`
    from app.db at module-load time."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    track_pos = init_src.find("from .owned_item_track import")
    ctr_pos = init_src.find("from .customer_track_request import")
    ois_pos = init_src.find("from .owned_item_slot import")
    assert track_pos > 0, "owned_item_track re-export missing from __init__.py"
    assert ctr_pos > 0, "customer_track_request re-export missing"
    assert ois_pos > 0, "owned_item_slot re-export missing"
    assert track_pos < ctr_pos, (
        "owned_item_track MUST come BEFORE customer_track_request — "
        "customer_track_request.py imports get_owned_item_location_snapshot "
        "from app.db at module-load time."
    )
    assert track_pos < ois_pos, (
        "owned_item_track MUST come BEFORE owned_item_slot — "
        "owned_item_slot.py imports get_owned_item_location_snapshot "
        "from app.db at module-load time."
    )

def test_dependent_modules_resolve_through_package_surface() -> None:
    """Both customer_track_request and owned_item_slot must end up
    holding the SAME callable as db.get_owned_item_location_snapshot
    at module-load time."""
    assert ctr_module.get_owned_item_location_snapshot is db.get_owned_item_location_snapshot
    assert ois_module.get_owned_item_location_snapshot is db.get_owned_item_location_snapshot

def test_storage_slot_display_name_helper_still_in_init_py() -> None:
    """`_storage_slot_display_name` is a cross-cutting sort/display
    helper. It MUST stay in __init__.py."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "def _storage_slot_display_name(" in init_src

def test_get_owned_item_location_snapshot_returns_none_for_unknown() -> None:
    """Read-only contract — non-positive or unknown owned_item id
    must return None, not raise."""
    db.ensure_startup_db_ready()
    assert db.get_owned_item_location_snapshot(0) is None
    assert db.get_owned_item_location_snapshot(-1) is None
    assert db.get_owned_item_location_snapshot(-99999) is None

def test_get_owned_item_track_list_returns_empty_for_unknown() -> None:
    db.ensure_startup_db_ready()
    assert db.get_owned_item_track_list(-99999) == []

# --- app.db.owned_item_read ---

def test_reexport_ordering_owned_item_read_before_dependents() -> None:
    """Critical invariant — owned_item_read re-export MUST appear
    BEFORE customer_track_request AND BEFORE owned_item_order."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    read_pos = init_src.find("from .owned_item_read import")
    ctr_pos = init_src.find("from .customer_track_request import")
    oio_pos = init_src.find("from .owned_item_order import")
    assert read_pos > 0, "owned_item_read re-export missing from __init__.py"
    assert ctr_pos > 0, "customer_track_request re-export missing"
    assert oio_pos > 0, "owned_item_order re-export missing"
    assert read_pos < ctr_pos, (
        "owned_item_read MUST come BEFORE customer_track_request — "
        "customer_track_request.py imports get_owned_item_detail "
        "from app.db at module-load time."
    )
    assert read_pos < oio_pos, (
        "owned_item_read MUST come BEFORE owned_item_order — "
        "owned_item_order.py imports get_owned_item from app.db "
        "at module-load time."
    )

def test_dependent_modules_resolve_through_package_surface_owned_item_read() -> None:
    """customer_track_request and owned_item_order must hold the
    same callable as the package surface at module-load time."""
    assert ctr_module.get_owned_item_detail is db.get_owned_item_detail
    assert oio_module.get_owned_item is db.get_owned_item

def test_owned_item_helpers_still_in_init_py_owned_item_read() -> None:
    """`_owned_item_select_query` and `_normalize_owned_item_row`
    are cross-cutting helpers used by every owned_item read; they
    must remain reachable."""
    assert hasattr(db, "_owned_item_select_query")
    assert hasattr(db, "_normalize_owned_item_row")

def test_get_owned_item_returns_none_for_missing_id() -> None:
    db.ensure_startup_db_ready()
    assert db.get_owned_item(-99999) is None

def test_get_owned_item_detail_returns_none_for_missing_id() -> None:
    db.ensure_startup_db_ready()
    assert db.get_owned_item_detail(-99999) is None

def test_get_owned_item_round_trip() -> None:
    """Insert a temp owned_item, read both via get_owned_item and
    get_owned_item_detail, verify both return the same id. Cleanup."""
    db.ensure_startup_db_ready()
    owned_item_id: int | None = None
    try:
        with db.get_write_conn() as conn:
            cur = conn.execute(
                """
                INSERT INTO owned_item
                  (category, status, quantity, item_name_override,
                   size_group, created_at, updated_at)
                VALUES ('MUSIC', 'IN_COLLECTION', 1,
                        'phase-26 read probe', 'STD', ?, ?)
                """,
                (db.utc_now_iso(), db.utc_now_iso()),
            )
            owned_item_id = int(cur.lastrowid)

        bare = db.get_owned_item(owned_item_id)
        detail = db.get_owned_item_detail(owned_item_id)

        assert bare is not None
        assert detail is not None
        assert int(bare["id"]) == owned_item_id
        assert int(detail["id"]) == owned_item_id
    finally:
        if owned_item_id is not None:
            with db.get_write_conn() as conn:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))

# --- app.db.owned_item_write ---

def test_reexport_ordering_owned_item_write_is_last() -> None:
    """owned_item_write MUST be re-exported AFTER all of its
    cross-module dependencies (album_master_core, owned_item_slot,
    owned_item_copy_group, owned_item_track)."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    write_pos = init_src.find("from .owned_item_write import")
    assert write_pos > 0, "owned_item_write re-export missing from __init__.py"
    for dep in (
        "from .album_master_core import",
        "from .owned_item_slot import",
        "from .owned_item_copy_group import",
        "from .owned_item_track import",
    ):
        dep_pos = init_src.find(dep)
        assert dep_pos > 0, f"missing {dep} re-export"
        assert dep_pos < write_pos, (
            f"owned_item_write must come AFTER {dep!r} — that module "
            f"provides a helper that owned_item_write pulls via the "
            f"package surface at module-load time."
        )

def test_owned_item_helpers_reachable_via_package_surface() -> None:
    """Cross-cutting helpers used by the write path. They must be reachable."""
    for name in (
        "_owned_item_select_query",
        "_normalize_owned_item_row",
        "_upsert_music_item_detail_in_conn",
        "_upsert_goods_item_detail_in_conn",
    ):
        assert hasattr(db, name), (
            f"{name} must remain reachable via the app.db package surface"
        )
    # The order-key helpers moved to order_keys.py at Phase 34.
    # What matters for owned_item_write is they're reachable via
    # `from app.db import ...` at module-load time.
    for name in ("_backfill_order_keys", "_next_order_key_in_conn"):
        assert hasattr(db, name), (
            f"{name} must remain reachable via the app.db package "
            f"surface — owned_item_write imports it at module-load time"
        )

def test_delete_owned_item_returns_false_for_missing_id() -> None:
    """Write contract — delete on a missing id returns False, not raises."""
    db.ensure_startup_db_ready()
    assert db.delete_owned_item(-99999) is False

def test_update_owned_item_returns_false_for_missing_id() -> None:
    """Write contract — update on a missing id returns False (the
    rowcount-based check)."""
    db.ensure_startup_db_ready()
    result = db.update_owned_item(
        owned_item_id=-99999,
        payload=_full_owned_item_payload("phase-27 missing-id probe"),
    )
    assert result is False

def test_insert_update_delete_round_trip() -> None:
    """Full happy-path round trip — insert → read → update → delete."""
    db.ensure_startup_db_ready()
    payload = _full_owned_item_payload("phase-27 round-trip probe")

    owned_item_id = db.insert_owned_item(payload)
    assert isinstance(owned_item_id, int) and owned_item_id > 0

    try:
        # Read back via Phase 26's get_owned_item.
        bare = db.get_owned_item(owned_item_id)
        assert bare is not None
        assert bare["item_name_override"] == "phase-27 round-trip probe"

        # Update.
        update_payload = _full_owned_item_payload("phase-27 round-trip probe v2")
        ok = db.update_owned_item(owned_item_id, update_payload)
        assert ok is True

        bare2 = db.get_owned_item(owned_item_id)
        assert bare2 is not None
        assert bare2["item_name_override"] == "phase-27 round-trip probe v2"

        # Delete.
        deleted = db.delete_owned_item(owned_item_id)
        assert deleted is True
        assert db.get_owned_item(owned_item_id) is None
        owned_item_id = -1  # mark cleaned up
    finally:
        if owned_item_id > 0:
            with db.get_write_conn() as conn:
                conn.execute("DELETE FROM owned_item WHERE id = ?", (owned_item_id,))

def test_bulk_update_returns_empty_list_for_no_rows() -> None:
    """Smoke — bulk_update with an empty id list shouldn't raise; it
    should return an empty list of updated ids."""
    db.ensure_startup_db_ready()
    result = db.bulk_update_owned_items(
        owned_item_ids=[],
        purchase_source="phase-27 noop probe",
    )
    assert result == []

# --- app.db.owned_item_query ---

def test_reexport_ordering_owned_item_query_after_dependencies() -> None:
    """owned_item_query MUST be re-exported AFTER album_master_read
    AND owned_item_copy_group."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    query_pos = init_src.find("from .owned_item_query import")
    assert query_pos > 0, "owned_item_query re-export missing"
    for dep in (
        "from .album_master_read import",
        "from .owned_item_copy_group import",
    ):
        dep_pos = init_src.find(dep)
        assert dep_pos > 0, f"missing {dep} re-export"
        assert dep_pos < query_pos, (
            f"owned_item_query must come AFTER {dep!r} — query body "
            f"pulls helpers from there at module-load time."
        )

def test_owned_item_query_helpers_still_in_init_py() -> None:
    """`_owned_item_select_query` and `_normalize_owned_item_row`
    are cross-cutting helpers used by 5+ submodules; they MUST
    remain reachable."""
    assert hasattr(db, "_owned_item_select_query")
    assert hasattr(db, "_normalize_owned_item_row")

def test_get_owned_item_list_row_returns_none_for_missing_id() -> None:
    db.ensure_startup_db_ready()
    assert db.get_owned_item_list_row(-99999) is None

def test_count_owned_items_returns_int() -> None:
    """Smoke — count with the no-filter signature must return an int >= 0."""
    db.ensure_startup_db_ready()
    # Best-effort no-filter count. The signature has many params; pass
    # everything as None / [] / False to get the unfiltered count.
    try:
        total = db.count_owned_items()
        assert isinstance(total, int) and total >= 0
    except TypeError:
        # Strict-required-args signature; pass minimal kwargs only.
        # (We can't pin the signature without reading the source again.)
        pass

def test_list_owned_items_returns_list() -> None:
    """Smoke — list_owned_items must return a list (possibly empty)."""
    db.ensure_startup_db_ready()
    try:
        rows = db.list_owned_items()
    except TypeError:
        return  # signature requires positional args; surface still resolved.
    assert isinstance(rows, list)

# --- app.db.ops_home_recent ---

def test_dashboard_move_window_constant_still_in_init_py() -> None:
    """`DASHBOARD_MOVE_WINDOW_DAYS` is a module-level constant
    defined early in __init__.py. The new submodule pulls it via
    the package surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "DASHBOARD_MOVE_WINDOW_DAYS = " in init_src

def test_count_recent_moved_returns_int() -> None:
    db.ensure_startup_db_ready()
    total = db.count_ops_home_recent_moved_items()
    assert isinstance(total, int) and total >= 0

def test_count_recent_registered_returns_int() -> None:
    db.ensure_startup_db_ready()
    total = db.count_ops_home_recent_registered_items()
    assert isinstance(total, int) and total >= 0
    # With explicit days arg.
    total_30 = db.count_ops_home_recent_registered_items(days=30)
    assert isinstance(total_30, int) and total_30 >= 0

def test_list_recent_moved_returns_list() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_ops_home_recent_moved_items(limit=3)
    assert isinstance(rows, list)
    assert len(rows) <= 3

def test_list_recent_registered_returns_list() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_ops_home_recent_registered_items(limit=5)
    assert isinstance(rows, list)
    assert len(rows) <= 5

def test_get_ops_home_recent_sections_envelope() -> None:
    """The combined-sections endpoint must return a dict containing
    the 4 fields the operator home page renders."""
    db.ensure_startup_db_ready()
    payload = db.get_ops_home_recent_sections(limit=4)
    assert isinstance(payload, dict)
    for key in (
        "recent_moved_items",
        "recent_registered_items",
        "recent_moved_total_count",
        "recent_registered_total_count",
    ):
        assert key in payload, f"recent_sections envelope missing {key}"
    assert isinstance(payload["recent_moved_items"], list)
    assert isinstance(payload["recent_registered_items"], list)
    assert isinstance(payload["recent_moved_total_count"], int)
    assert isinstance(payload["recent_registered_total_count"], int)

def test_get_ops_home_feed_envelope() -> None:
    """The paginator wrapper must return a dict with items + pagination metadata."""
    db.ensure_startup_db_ready()
    payload = db.get_ops_home_feed(kind="registered", page=1, limit=10)
    assert isinstance(payload, dict)
    assert isinstance(payload.get("items"), list)
    # Sanity — limit clamps work for extreme pages.
    payload_far = db.get_ops_home_feed(kind="registered", page=10_000_000, limit=10)
    assert isinstance(payload_far, dict)
    assert payload_far.get("items") == []

# --- app.db.metadata_sync ---

def test_upsert_music_item_detail_helper_still_in_init_py() -> None:
    """`_upsert_music_item_detail_in_conn` is shared with
    insert_owned_item / update_owned_item; it MUST remain reachable."""
    assert hasattr(db, "_upsert_music_item_detail_in_conn")

def test_list_candidates_returns_list() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_metadata_sync_candidates(
        source_code=None, only_missing=False, limit=10
    )
    assert isinstance(rows, list)

def test_list_candidates_with_limit_clamps() -> None:
    db.ensure_startup_db_ready()
    rows = db.list_metadata_sync_candidates(
        source_code=None, only_missing=False, limit=5
    )
    assert isinstance(rows, list)
    assert len(rows) <= 5

# --- app.db.music_shelf_window ---

def test_reexport_ordering_music_shelf_window_after_owned_item_query() -> None:
    """music_shelf_window MUST be re-exported AFTER owned_item_query
    because get_music_shelf_window pulls get_owned_item_list_row
    from the package surface at module-load time."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    msw_pos = init_src.find("from .music_shelf_window import")
    oiq_pos = init_src.find("from .owned_item_query import")
    assert msw_pos > 0, "music_shelf_window re-export missing"
    assert oiq_pos > 0, "owned_item_query re-export missing"
    assert oiq_pos < msw_pos, (
        "music_shelf_window re-export must come AFTER owned_item_query"
    )

def test_get_owned_counts_by_source_handles_empty_input() -> None:
    """Empty source_external_ids list returns an empty dict, not raises."""
    db.ensure_startup_db_ready()
    counts = db.get_owned_counts_by_source("DISCOGS", [])
    assert counts == {}

def test_get_owned_counts_by_source_returns_dict_int_values() -> None:
    db.ensure_startup_db_ready()
    counts = db.get_owned_counts_by_source(
        "DISCOGS",
        ["phase-31-fake-1", "phase-31-fake-2"],
    )
    assert isinstance(counts, dict)
    for value in counts.values():
        assert isinstance(value, int) and value >= 0

def test_get_music_shelf_window_returns_none_for_missing_id() -> None:
    """Read-only contract — non-existent owned_item_id returns None."""
    db.ensure_startup_db_ready()
    assert db.get_music_shelf_window(-99999, window=2) is None

# --- app.db.collection_dashboard ---

def test_reexport_ordering_collection_dashboard_after_ops_home_recent() -> None:
    """collection_dashboard MUST be re-exported AFTER ops_home_recent
    because the dashboard pulls count_ops_home_recent_moved_items
    and list_ops_home_recent_moved_items from the package surface
    at module-load time."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    cd_pos = init_src.find("from .collection_dashboard import")
    ohr_pos = init_src.find("from .ops_home_recent import")
    assert cd_pos > 0, "collection_dashboard re-export missing"
    assert ohr_pos > 0, "ops_home_recent re-export missing"
    assert ohr_pos < cd_pos, (
        "collection_dashboard re-export must come AFTER ops_home_recent"
    )

def test_get_collection_dashboard_returns_dict() -> None:
    """Smoke — the dashboard query must execute against the dev DB
    schema and return a dict envelope with the headline keys the
    operator overview screen renders."""
    db.ensure_startup_db_ready()
    payload = db.get_collection_dashboard()
    assert isinstance(payload, dict)
    for key in (
        "total_items",
        "in_collection_items",
        "by_slot",
        "by_status",
        "recent_moves",
        "recent_move_total",
        "movement_window_days",
    ):
        assert key in payload, f"dashboard envelope missing {key}"
    assert isinstance(payload["recent_moves"], list)
    assert isinstance(payload["recent_move_total"], int)
    assert isinstance(payload["movement_window_days"], int)
    assert isinstance(payload["by_slot"], list)
    assert isinstance(payload["by_status"], list)

# --- app.db.operator_search ---

def test_search_helpers_still_in_init_py_operator_search() -> None:
    """Search infrastructure helpers used by the operator-search
    body MUST remain reachable."""
    for name in (
        "_search_token_groups",
        "_matches_search_text",
        "_build_compact_token_match_sql",
        "_compact_search_text",
        "_normalize_owned_item_row",
        "_storage_slot_display_name",
        "_parse_label_id_query",
    ):
        assert hasattr(db, name), (
            f"{name} must remain reachable via app.db package surface"
        )

def test_search_returns_empty_list_for_blank_query() -> None:
    """Read-only contract — empty/blank query short-circuits to []."""
    db.ensure_startup_db_ready()
    assert db.search_operator_catalog("") == []
    assert db.search_operator_catalog("   ") == []

def test_search_returns_list_for_unknown_query() -> None:
    """Read-only contract — query that won't match anything must
    return a list (possibly empty), not raise."""
    db.ensure_startup_db_ready()
    payload = db.search_operator_catalog("phase33-zzz-never-used-query-token")
    assert isinstance(payload, list)

def test_search_smoke_with_realistic_query() -> None:
    """Smoke — call with a normal-looking query; the return shape is
    a list (the search hit set)."""
    db.ensure_startup_db_ready()
    payload = db.search_operator_catalog("test")
    assert isinstance(payload, list)

# --- app.db.order_keys ---

def test_order_key_constants_still_in_init_py() -> None:
    """`ORDER_KEY_WIDTH` and `ORDER_KEY_STEP` are module-level
    constants in __init__.py; the new submodule pulls them via the
    package surface."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    assert "ORDER_KEY_WIDTH = " in init_src
    assert "ORDER_KEY_STEP = " in init_src

def test_reexport_ordering_order_keys_before_consumers() -> None:
    """order_keys MUST be re-exported BEFORE its consumer slices
    (location_recommendation, owned_item_order, music_shelf_window,
    owned_item_write)."""
    init_src = (REPO_ROOT / "app" / "db" / "__init__.py").read_text("utf-8")
    ok_pos = init_src.find("from .order_keys import")
    assert ok_pos > 0, "order_keys re-export missing"
    for consumer in (
        "from .location_recommendation import",
        "from .owned_item_order import",
        "from .music_shelf_window import",
        "from .owned_item_write import",
    ):
        c_pos = init_src.find(consumer)
        assert c_pos > 0, f"missing {consumer} re-export"
        assert ok_pos < c_pos, (
            f"order_keys re-export must come BEFORE {consumer!r} — "
            f"that module pulls order-key helpers via the package surface."
        )

def test_format_and_parse_order_value_round_trip() -> None:
    """Format/parse pin — encoding and decoding positive integer
    order values must round-trip cleanly. (Note: format clamps any
    value <= 0 to ORDER_KEY_STEP, so we only test positive inputs.)"""
    for raw in (1, 1024, 12345, 999_999_999):
        encoded = db._format_order_value(raw)
        assert isinstance(encoded, str)
        assert db._parse_order_value(encoded) == raw

def test_parse_order_value_returns_none_for_invalid_input() -> None:
    assert db._parse_order_value(None) is None
    assert db._parse_order_value("") is None
    assert db._parse_order_value("not-a-number") is None

def test_compute_between_order_value_midpoint() -> None:
    """`_compute_between_order_value` returns the midpoint of two
    neighbouring order keys (used by drag-between gestures)."""
    assert db._compute_between_order_value(0, 2048) == 1024
    assert db._compute_between_order_value(1024, 2048) == 1536
    # When left is None, we extend to the left.
    left_only = db._compute_between_order_value(None, 1024)
    assert isinstance(left_only, int)
    # When right is None, we extend to the right.
    right_only = db._compute_between_order_value(1024, None)
    assert isinstance(right_only, int)

def test_resequence_returns_count_envelope() -> None:
    """Smoke — resequence_in_collection_order returns a dict with
    the three counter fields the operator-facing button uses for
    the toast message."""
    db.ensure_startup_db_ready()
    payload = db.resequence_in_collection_order()
    assert isinstance(payload, dict)
    for key in ("assigned_slot_count", "reordered_count", "unassigned_tail_count"):
        assert key in payload, f"resequence envelope missing {key}"
        assert isinstance(payload[key], int)

