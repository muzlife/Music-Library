"""startup_cleanup — ensure_startup_db_ready 전용 도메인 분리 패키지.

도메인별 서브모듈:
  domain_code  — domain_code 값 교정 (ManiaDB, 한글신호, 수동확인, owned_item 동기화)
  artist_name  — 아티스트명/정렬명 교정 (팝 한글정렬명, 라틴명 복원, 한글명 제거)

각 서브모듈은 app.db 패키지 surface(_column_exists, _table_exists, utc_now_iso)만 의존한다.
"""
