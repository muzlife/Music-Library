#!/usr/bin/env python3
from __future__ import annotations

import csv
import time
from pathlib import Path

from run_smoke_qa import BASE_URL, LOCAL_BASE_URL, LOCAL_HEALTH_URL, QA_CSV_PATH, _probe_health, build_client, note, request, request_json

FIELD_IDS = [
    'AUTH-002',
    'FIELD-001',
    'FIELD-002',
    'FIELD-003',
    'FIELD-004',
]


def update_csv(results: dict[str, tuple[str, str]]) -> None:
    with QA_CSV_PATH.open('r', encoding='utf-8', newline='') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        rows = list(reader)
    for row in rows:
        suite_id = row.get('suite_id', '')
        if suite_id in results:
            status, notes = results[suite_id]
            row['status'] = status
            row['notes'] = notes
    with QA_CSV_PATH.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run() -> int:
    operator_base_url = LOCAL_BASE_URL if _probe_health(LOCAL_HEALTH_URL) else BASE_URL
    results: dict[str, tuple[str, str]] = {suite_id: ('Blocked', '실행 안 함') for suite_id in FIELD_IDS}
    operator = build_client()
    login = None
    logged_in_user = ''
    import os
    candidates = [
        (os.environ.get("QA_OPERATOR_USER", ""), os.environ.get("QA_OPERATOR_PASS", "")),
        (os.environ.get("QA_ADMIN_USER", ""), os.environ.get("QA_ADMIN_PASS", "")),
    ]
    for username, password in [(u, p) for u, p in candidates if u and p]:
        for timeout in (20, 40, 60):
            try:
                response = request_json(operator, f'{operator_base_url}/auth/login', method='POST', form={'username': username, 'password': password}, timeout=timeout)
                if response.ok:
                    login = response
                    logged_in_user = username
                    break
            except Exception:
                time.sleep(1)
        if login is not None:
            break
    if login is None:
        results['AUTH-002'] = ('Fail', '현장 운영자 로그인 실패')
        update_csv(results)
        print('현장 운영자 로그인 실패')
        return 1

    session = request(operator, f'{operator_base_url}/auth/session', timeout=20)
    if session.ok and session.json().get('authenticated') and session.json().get('role') == 'OPERATOR':
        results['AUTH-002'] = ('Pass', note('현장 운영자 로그인 성공', f"user={session.json().get('username') or logged_in_user}"))
    else:
        results['AUTH-002'] = ('Fail', note('현장 운영자 세션 검증 실패', f'status={session.status_code}', session.text[:160]))

    search = request(operator, f'{operator_base_url}/operator/catalog-search?q=%EC%8A%AC%ED%94%88%20%EC%9E%A5%EB%82%9C%EA%B0%90&limit=10', timeout=30)
    first_item = None
    if search.ok and (search.json().get('items') or []):
        first_item = search.json()['items'][0]
        results['FIELD-001'] = ('Pass', note('현장 운영 조회 성공', f"owned_item_id={first_item.get('owned_item_id')}", f"track={first_item.get('track_matches', ['-'])[0]}"))
        current_pos = first_item.get('current_slot_display_name') or first_item.get('current_slot_code')
        previous_pos = first_item.get('previous_slot_display_name') or first_item.get('previous_slot_code') or '-'
        results['FIELD-003'] = ('Pass', note('현재/직전 위치 확인 가능', f'현재={current_pos}', f'직전={previous_pos}'))
    else:
        results['FIELD-001'] = ('Fail', note('현장 운영 조회 실패', f'status={search.status_code}', search.text[:160]))
        results['FIELD-003'] = ('Fail', '현장 운영 조회 실패로 위치 확인 불가')

    if first_item is not None:
        cabinet_name = str(first_item.get('current_cabinet_name') or '').strip()
        column_code = str(first_item.get('current_column_code') or '').strip()
        cell_code = str(first_item.get('current_cell_code') or '').strip()
        if cabinet_name and column_code and cell_code:
            results['FIELD-002'] = ('Pass', note('장식장 열기용 위치 필드 확인 가능', f'cabinet={cabinet_name}', f'column={column_code}', f'cell={cell_code}'))
        else:
            results['FIELD-002'] = ('Fail', note('장식장 열기용 위치 필드 누락', f'cabinet={cabinet_name or "-"}', f'column={column_code or "-"}', f'cell={cell_code or "-"}'))
    else:
        results['FIELD-002'] = ('Fail', '현장 운영 조회 결과가 없어 위치 필드 검증 불가')

    admin_redirect = request(
        operator,
        f'{operator_base_url}/admin',
        timeout=20,
        headers={'Accept': 'text/html'},
    )
    redirect_location = str(admin_redirect.headers.get('location') or '').strip()
    final_url = str(admin_redirect.final_url or '').strip()
    if (
        (admin_redirect.status_code in (302, 303, 307, 308) and redirect_location == '/ops')
        or final_url.endswith('/ops')
    ):
        results['FIELD-004'] = ('Pass', note('현장 운영자 /admin 차단 확인', f'location={redirect_location or "-"}', f'final={final_url or "-"}'))
    else:
        results['FIELD-004'] = ('Fail', note('현장 운영자 /admin 차단 실패', f'status={admin_redirect.status_code}', f'location={redirect_location or "-"}', f'final={final_url or "-"}', admin_redirect.text[:160]))

    update_csv(results)
    passed = [suite for suite, (status, _) in results.items() if status == 'Pass']
    failed = [suite for suite, (status, _) in results.items() if status == 'Fail']
    blocked = [suite for suite, (status, _) in results.items() if status == 'Blocked']
    print('현장 운영 QA 결과')
    print(f'- Pass: {len(passed)}')
    print(f'- Fail: {len(failed)}')
    print(f'- Blocked: {len(blocked)}')
    for suite_id in FIELD_IDS:
        status, notes = results[suite_id]
        print(f'[{status}] {suite_id} :: {notes}')
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(run())
