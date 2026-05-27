import pytest
from app.db import track_tag


def test_track_tag_insert_and_list():
    """Insert a tag and retrieve it by type."""
    tag_id = track_tag.insert_track_tag(
        tag_type="MOOD", tag_value="비오는 날",
        spotify_track_id="spotify:track:test123",
        created_by="admin"
    )
    assert tag_id > 0

    tags = track_tag.list_track_tags(tag_type="MOOD")
    assert len(tags) >= 1
    found = [t for t in tags if t["tag_value"] == "비오는 날"]
    assert len(found) == 1
    assert found[0]["spotify_track_id"] == "spotify:track:test123"

    # cleanup
    track_tag.delete_track_tag(tag_id)


def test_track_tag_delete():
    """Insert a tag, delete it, verify it's gone."""
    tag_id = track_tag.insert_track_tag(
        tag_type="GENRE", tag_value="재즈",
        created_by="admin"
    )
    assert track_tag.delete_track_tag(tag_id) is True

    tags = track_tag.list_track_tags(tag_type="GENRE")
    found = [t for t in tags if t["id"] == tag_id]
    assert len(found) == 0


def test_find_tracks_by_tag():
    """Find tracks matching a tag value."""
    tag_id = track_tag.insert_track_tag(
        tag_type="MOOD", tag_value="테스트_찾기",
        owned_item_id=99999,
        created_by="admin"
    )
    results = track_tag.find_tracks_by_tag("테스트_찾기", limit=5)
    assert len(results) >= 1
    assert results[0]["owned_item_id"] == 99999

    track_tag.delete_track_tag(tag_id)
