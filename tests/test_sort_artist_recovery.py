from app.services.sort_artist_recovery import build_sort_artist_restore_plan


def test_build_sort_artist_restore_plan_prefers_source_key_matches():
    current_rows = [
        {
            "id": 1057,
            "source_code": "DISCOGS",
            "source_master_id": "3331849",
            "title": "The World EP.Fin:Will",
            "artist_or_brand": "Ateez (2)",
            "release_year": 2023,
            "sort_artist_name": None,
        }
    ]
    backup_rows = [
        {
            "id": 9001,
            "source_code": "DISCOGS",
            "source_master_id": "3331849",
            "title": "The World EP.Fin:Will",
            "artist_or_brand": "Ateez (2)",
            "release_year": 2023,
            "sort_artist_name": "에이티즈",
        }
    ]

    plan = build_sort_artist_restore_plan(current_rows=current_rows, backup_rows=backup_rows)

    assert plan == [
        {
            "album_master_id": 1057,
            "source_code": "DISCOGS",
            "source_master_id": "3331849",
            "title": "The World EP.Fin:Will",
            "artist_or_brand": "Ateez (2)",
            "release_year": 2023,
            "current_sort_artist_name": None,
            "backup_sort_artist_name": "에이티즈",
            "strategy": "source_key_exact",
            "backup_album_master_id": 9001,
        }
    ]


def test_build_sort_artist_restore_plan_uses_unique_title_artist_year_fallback():
    current_rows = [
        {
            "id": 1110,
            "source_code": "MANUAL",
            "source_master_id": "OWNED-1244",
            "title": "나의 여름은 아직 안 끝났어",
            "artist_or_brand": "Yun Seok Cheol Trio*",
            "release_year": 2024,
            "sort_artist_name": None,
        }
    ]
    backup_rows = [
        {
            "id": 8123,
            "source_code": "DISCOGS",
            "source_master_id": "3123456",
            "title": "나의 여름은 아직 안 끝났어",
            "artist_or_brand": "Yun Seok Cheol Trio*",
            "release_year": 2024,
            "sort_artist_name": "윤석철 트리오",
        }
    ]

    plan = build_sort_artist_restore_plan(current_rows=current_rows, backup_rows=backup_rows)

    assert plan == [
        {
            "album_master_id": 1110,
            "source_code": "MANUAL",
            "source_master_id": "OWNED-1244",
            "title": "나의 여름은 아직 안 끝났어",
            "artist_or_brand": "Yun Seok Cheol Trio*",
            "release_year": 2024,
            "current_sort_artist_name": None,
            "backup_sort_artist_name": "윤석철 트리오",
            "strategy": "title_artist_year_exact",
            "backup_album_master_id": 8123,
        }
    ]


def test_build_sort_artist_restore_plan_skips_ambiguous_title_artist_year_fallback():
    current_rows = [
        {
            "id": 1110,
            "source_code": "MANUAL",
            "source_master_id": "OWNED-1244",
            "title": "나의 여름은 아직 안 끝났어",
            "artist_or_brand": "Yun Seok Cheol Trio*",
            "release_year": 2024,
            "sort_artist_name": None,
        }
    ]
    backup_rows = [
        {
            "id": 8123,
            "source_code": "DISCOGS",
            "source_master_id": "3123456",
            "title": "나의 여름은 아직 안 끝났어",
            "artist_or_brand": "Yun Seok Cheol Trio*",
            "release_year": 2024,
            "sort_artist_name": "윤석철 트리오",
        },
        {
            "id": 8124,
            "source_code": "MANIADB",
            "source_master_id": "999999",
            "title": "나의 여름은 아직 안 끝났어",
            "artist_or_brand": "Yun Seok Cheol Trio*",
            "release_year": 2024,
            "sort_artist_name": "윤석철 트리오",
        },
    ]

    plan = build_sort_artist_restore_plan(current_rows=current_rows, backup_rows=backup_rows)

    assert plan == []
