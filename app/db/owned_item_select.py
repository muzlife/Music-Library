"""owned_item SELECT 쿼리/정규화 도메인 (owned_item_select).

db/__init__.py 에서 분리된 슬라이스. owned_item 목록 조회에 쓰이는
SQL 쿼리 문자열 생성기와 DB row → dict 정규화 함수를 소유한다.

공개 surface (app.db re-export)
  _owned_item_select_query    — owned_item JOIN 포함 SELECT 절 반환
  _normalize_owned_item_row   — sqlite3.Row → 정규화된 dict 변환

내부 중첩 helper (정규화 함수 내부에서만 사용)
  _json_to_string_list, _json_to_dict_list
  _csv_to_int_list, _csv_to_label_list

변경격리: upsert 로직은 owned_item_detail.py, 쓰기는 owned_item_write.py 담당.
테스트 단위: test_owned_item_select.py 에서 독립 검증.

Cross-package dependencies: 없음 (표준 라이브러리 json 만 사용)
"""

from __future__ import annotations

import json
from typing import Any

def _owned_item_select_query() -> str:
    return """
      SELECT
        oi.id,
        oi.master_item_id,
        oi.linked_album_master_id,
        oi.linked_artist_name,
        oi.copy_group_key,
        oi.category,
        oi.domain_code,
        oi.release_type,
        oi.item_name_override,
        oi.quantity,
        oi.size_group,
        COALESCE(oi.preferred_storage_size_group, oi.size_group) AS preferred_storage_size_group,
        oi.status,
        oi.condition_grade,
        oi.display_rank,
        oi.order_key,
        oi.storage_slot_id,
        ss.slot_code,
        oi.is_second_hand,
        oi.signature_type,
        oi.source_code,
        oi.source_external_id,
        oi.purchase_price,
        oi.currency_code,
        oi.purchase_source,
        oi.memory_note,
        oi.thickness_mm,
        oi.notes,
        oi.created_at,
        oi.updated_at,
        mid.format_name,
        mid.artist_or_brand,
        mid.release_year,
        mid.released_date,
        am.title AS master_title,
        am.artist_or_brand AS master_artist_or_brand,
        am.sort_artist_name AS master_sort_artist_name,
        am.release_year AS master_release_year,
        mid.barcode,
        mid.label_name,
        mid.catalog_no,
        COALESCE(mid.cover_image_url, gid.primary_image_url) AS cover_image_url,
        mid.track_list_json,
        mid.media_type,
        mid.genres_json,
        mid.styles_json,
        mid.disc_count,
        mid.speed_rpm,
        mid.has_obi,
        mid.runout_matrix,
        mid.runout_matrix_json,
        mid.pressing_country,
        mid.disc_type,
        mid.package_contents,
        mid.is_limited_edition,
        mid.edition_number,
        mid.source_notes,
        mid.credits_json,
        mid.identifier_items_json,
        mid.image_items_json,
        mid.company_items_json,
        mid.series_json,
        mid.format_items_json,
        mid.track_items_json,
        mid.label_items_json,
        mid.sleeve_condition AS cover_condition,
        mid.media_condition AS disc_condition,
        mid.is_promotional_not_for_sale,
        gid.image_urls_json,
        gid.primary_image_url AS goods_primary_image_url,
        gid.poster_storage_spec,
        gid.tshirt_size,
        gid.cup_material,
        gid.hat_size,
        COALESCE((
          SELECT GROUP_CONCAT(co.id)
          FROM owned_item_subtype ois
          JOIN classification_option co ON co.id = ois.option_id
          WHERE ois.owned_item_id = oi.id
          ORDER BY co.sort_order ASC, co.id ASC
        ), '') AS subtype_option_ids_csv,
        COALESCE((
          SELECT GROUP_CONCAT(co.label, '|')
          FROM owned_item_subtype ois
          JOIN classification_option co ON co.id = ois.option_id
          WHERE ois.owned_item_id = oi.id
          ORDER BY co.sort_order ASC, co.id ASC
        ), '') AS subtype_labels_csv,
        COALESCE((
          SELECT GROUP_CONCAT(co.id)
          FROM owned_item_soundtrack ois
          JOIN classification_option co ON co.id = ois.option_id
          WHERE ois.owned_item_id = oi.id
          ORDER BY co.sort_order ASC, co.id ASC
        ), '') AS soundtrack_option_ids_csv,
        COALESCE((
          SELECT GROUP_CONCAT(co.label, '|')
          FROM owned_item_soundtrack ois
          JOIN classification_option co ON co.id = ois.option_id
          WHERE ois.owned_item_id = oi.id
          ORDER BY co.sort_order ASC, co.id ASC
        ), '') AS soundtrack_labels_csv,
        COALESCE((
          SELECT COUNT(*)
          FROM owned_item_digital_link l
          JOIN digital_asset da ON da.id = l.digital_asset_id
          WHERE l.owned_item_id = oi.id
            AND da.asset_type = 'AUDIO'
        ), 0) AS audio_asset_count
      FROM owned_item oi
      LEFT JOIN storage_slot ss ON ss.id = oi.storage_slot_id
      LEFT JOIN music_item_detail mid ON mid.owned_item_id = oi.id
      LEFT JOIN album_master am ON am.id = oi.linked_album_master_id
      LEFT JOIN goods_item_detail gid ON gid.owned_item_id = oi.id
    """


def _normalize_owned_item_row(obj: dict[str, Any]) -> dict[str, Any]:
    track_list_raw = obj.pop("track_list_json", None)
    if track_list_raw:
        try:
            track_list = json.loads(track_list_raw)
            obj["track_list"] = track_list if isinstance(track_list, list) else []
        except json.JSONDecodeError:
            obj["track_list"] = []
    else:
        obj["track_list"] = []

    genres_raw = obj.pop("genres_json", None)
    if genres_raw:
        try:
            parsed_genres = json.loads(genres_raw)
            obj["genres"] = [str(v).strip() for v in parsed_genres if str(v).strip()] if isinstance(parsed_genres, list) else []
        except json.JSONDecodeError:
            obj["genres"] = []
    else:
        obj["genres"] = []

    styles_raw = obj.pop("styles_json", None)
    if styles_raw:
        try:
            parsed_styles = json.loads(styles_raw)
            obj["styles"] = [str(v).strip() for v in parsed_styles if str(v).strip()] if isinstance(parsed_styles, list) else []
        except json.JSONDecodeError:
            obj["styles"] = []
    else:
        obj["styles"] = []

    goods_images_raw = obj.pop("image_urls_json", None)
    goods_image_urls: list[str] = []
    if goods_images_raw:
        try:
            parsed_goods_images = json.loads(str(goods_images_raw))
            if isinstance(parsed_goods_images, list):
                goods_image_urls = [str(v).strip() for v in parsed_goods_images if str(v).strip()]
        except json.JSONDecodeError:
            goods_image_urls = []
    obj["goods_image_urls"] = goods_image_urls
    goods_primary_image_url = str(obj.pop("goods_primary_image_url", "") or "").strip() or None
    if goods_primary_image_url is None and goods_image_urls:
        goods_primary_image_url = goods_image_urls[0]
    obj["goods_primary_image_url"] = goods_primary_image_url
    obj["poster_storage_spec"] = str(obj.get("poster_storage_spec") or "").strip() or None
    obj["tshirt_size"] = str(obj.get("tshirt_size") or "").strip() or None
    obj["cup_material"] = str(obj.get("cup_material") or "").strip() or None
    obj["hat_size"] = str(obj.get("hat_size") or "").strip() or None

    obj["is_second_hand"] = bool(obj.get("is_second_hand"))
    if obj.get("recently_moved_to_current_slot") is not None:
        obj["recently_moved_to_current_slot"] = bool(obj.get("recently_moved_to_current_slot"))
    if obj.get("is_promotional_not_for_sale") is not None:
        obj["is_promotional_not_for_sale"] = bool(obj.get("is_promotional_not_for_sale"))
    if obj.get("is_limited_edition") is not None:
        obj["is_limited_edition"] = bool(int(obj.get("is_limited_edition") or 0))
    if obj.get("has_obi") is not None:
        obj["has_obi"] = True if int(obj.get("has_obi")) == 1 else None

    runout_json_raw = obj.pop("runout_matrix_json", None)
    runout_values: list[str] = []
    if runout_json_raw:
        try:
            parsed_runout = json.loads(runout_json_raw)
            if isinstance(parsed_runout, list):
                runout_values = [str(v).strip() for v in parsed_runout if str(v).strip()]
        except json.JSONDecodeError:
            runout_values = []
    if not runout_values:
        legacy_runout = str(obj.get("runout_matrix") or "").strip()
        if legacy_runout:
            runout_values = [p.strip() for p in legacy_runout.split("|") if p.strip()]
    obj["runout_matrix"] = runout_values

    def _json_to_string_list(raw: Any) -> list[str]:
        if not raw:
            return []
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        return [str(v).strip() for v in parsed if str(v).strip()]

    def _json_to_dict_list(raw: Any) -> list[dict[str, Any]]:
        if not raw:
            return []
        try:
            parsed = json.loads(str(raw))
        except json.JSONDecodeError:
            return []
        if not isinstance(parsed, list):
            return []
        out: list[dict[str, Any]] = []
        for row in parsed:
            if isinstance(row, dict):
                out.append(row)
        return out

    obj["credits"] = _json_to_string_list(obj.pop("credits_json", None))
    obj["identifier_items"] = _json_to_dict_list(obj.pop("identifier_items_json", None))
    obj["image_items"] = _json_to_dict_list(obj.pop("image_items_json", None))
    obj["company_items"] = _json_to_dict_list(obj.pop("company_items_json", None))
    obj["series"] = _json_to_string_list(obj.pop("series_json", None))
    obj["format_items"] = _json_to_dict_list(obj.pop("format_items_json", None))
    obj["track_items"] = _json_to_dict_list(obj.pop("track_items_json", None))
    obj["label_items"] = _json_to_dict_list(obj.pop("label_items_json", None))

    def _csv_to_int_list(raw: Any) -> list[int]:
        text = str(raw or "").strip()
        if not text:
            return []
        out: list[int] = []
        for part in text.split(","):
            p = str(part).strip()
            if not p:
                continue
            try:
                value = int(p)
            except ValueError:
                continue
            if value > 0:
                out.append(value)
        return out

    def _csv_to_label_list(raw: Any) -> list[str]:
        text = str(raw or "").strip()
        if not text:
            return []
        return [p.strip() for p in text.split("|") if p.strip()]

    obj["subtype_option_ids"] = _csv_to_int_list(obj.pop("subtype_option_ids_csv", None))
    obj["subtype_labels"] = _csv_to_label_list(obj.pop("subtype_labels_csv", None))
    obj["soundtrack_option_ids"] = _csv_to_int_list(obj.pop("soundtrack_option_ids_csv", None))
    obj["soundtrack_labels"] = _csv_to_label_list(obj.pop("soundtrack_labels_csv", None))

    audio_count = int(obj.get("audio_asset_count") or 0)
    obj["audio_asset_count"] = audio_count
    obj["has_audio"] = audio_count > 0
    return obj
