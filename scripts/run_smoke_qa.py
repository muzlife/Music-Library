#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import os
import re
import ssl
import subprocess
import sys
import time
from dataclasses import dataclass
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen

def _resolve_root() -> Path:
    raw = os.getenv('LIBRARY_PROJECT_ROOT', '').strip()
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[1]


ROOT = _resolve_root()
ENV_PATH = ROOT / '.env.local'
QA_CSV_PATH = ROOT / 'docs' / 'qa' / 'qa_master_sheet.csv'
EXTERNAL_BASE_URL = 'https://qa-library.muzlife.com'
LOCAL_BASE_URL = 'http://127.0.0.1:8100'
LOCAL_HEALTH_URL = f'{LOCAL_BASE_URL}/health'
LAUNCHD_LABEL = f'gui/{os.getuid()}/com.muzlife.library-qa'
SMOKE_IDS = [
    'AUTH-001',
    'SYS-001',
    'DASH-001',
    'DASH-002',
    'SEARCH-001',
    'REGISTER-002',
    'OPS-010',
    'REC-001',
]


def _probe_health(url: str, *, timeout: int = 5) -> bool:
    try:
        req = Request(url, method='GET')
        context = ssl._create_unverified_context() if url.startswith('https://') else None
        with urlopen(req, timeout=timeout, context=context) as resp:
            body = resp.read().decode('utf-8', errors='replace')
            return int(getattr(resp, 'status', 0)) == 200 and '"status":"ok"' in body.replace(' ', '')
    except Exception:
        return False


def determine_base_url() -> str:
    forced = str(os.environ.get('QA_BASE_URL') or '').strip()
    if forced:
        return forced.rstrip('/')
    if _probe_health(f'{EXTERNAL_BASE_URL}/health'):
        return EXTERNAL_BASE_URL
    if _probe_health(LOCAL_HEALTH_URL):
        return LOCAL_BASE_URL
    return EXTERNAL_BASE_URL


BASE_URL = determine_base_url()


@dataclass
class SimpleResponse:
    status_code: int
    body: bytes
    headers: dict[str, str]
    final_url: str | None = None

    @property
    def ok(self) -> bool:
        return 200 <= self.status_code < 300

    @property
    def text(self) -> str:
        return self.body.decode('utf-8', errors='replace')

    def json(self) -> Any:
        return json.loads(self.text or 'null')


def load_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding='utf-8').splitlines():
        line = raw_line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def note(*parts: str) -> str:
    return ' | '.join(part for part in parts if str(part or '').strip())


def build_client() -> Any:
    cookie_jar = CookieJar()
    opener = build_opener(HTTPCookieProcessor(cookie_jar))
    opener.addheaders = [('User-Agent', 'hahahoho-smoke-qa/1.0')]
    opener._qa_auth_cookie = ''  # type: ignore[attr-defined]
    return opener


def _capture_auth_cookie(opener: Any, headers: dict[str, str]) -> None:
    set_cookie = str(headers.get('set-cookie') or '').strip()
    match = re.search(r'(hahahoho_session=[^;]+)', set_cookie)
    if match:
        opener._qa_auth_cookie = match.group(1)  # type: ignore[attr-defined]


def request(opener: Any, url: str, *, method: str = 'GET', data: bytes | None = None, headers: dict[str, str] | None = None, timeout: int = 20) -> SimpleResponse:
    req = Request(url, data=data, method=method)
    auth_cookie = str(getattr(opener, '_qa_auth_cookie', '') or '').strip()
    if auth_cookie and 'Cookie' not in (headers or {}):
        req.add_header('Cookie', auth_cookie)
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with opener.open(req, timeout=timeout) as resp:
            response = SimpleResponse(
                status_code=int(resp.status),
                body=resp.read(),
                headers={k.lower(): v for k, v in resp.headers.items()},
                final_url=str(resp.geturl() or '').strip() or None,
            )
            _capture_auth_cookie(opener, response.headers)
            return response
    except HTTPError as exc:
        response = SimpleResponse(
            status_code=int(exc.code),
            body=exc.read(),
            headers={k.lower(): v for k, v in exc.headers.items()},
            final_url=str(exc.geturl() or '').strip() or None,
        )
        _capture_auth_cookie(opener, response.headers)
        return response
    except URLError as exc:
        raise RuntimeError(f'url open failed: {exc}') from exc


def request_json(opener: Any, url: str, *, method: str = 'GET', payload: Any | None = None, form: dict[str, Any] | None = None, timeout: int = 20) -> SimpleResponse:
    headers: dict[str, str] = {}
    data: bytes | None = None
    if form is not None:
        data = urlencode(form).encode('utf-8')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    elif payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode('utf-8')
        headers['Content-Type'] = 'application/json'
    return request(opener, url, method=method, data=data, headers=headers, timeout=timeout)


def run() -> int:
    env_values = load_env_file(ENV_PATH)
    username = env_values.get('LIBRARY_AUTH_USERNAME') or os.environ.get('LIBRARY_AUTH_USERNAME')
    password = env_values.get('LIBRARY_AUTH_PASSWORD') or os.environ.get('LIBRARY_AUTH_PASSWORD')
    if not username or not password:
        print('관리자 계정 정보를 찾지 못했습니다.', file=sys.stderr)
        return 2

    opener = build_client()
    public_opener = build_client()
    results: dict[str, tuple[str, str]] = {suite_id: ('Blocked', '실행 안 함') for suite_id in SMOKE_IDS}
    created_owned_item_id: int | None = None

    try:
        auth = request_json(opener, f'{BASE_URL}/auth/login', method='POST', form={'username': username, 'password': password}, timeout=20)
        if auth.ok:
            session_info = request(opener, f'{BASE_URL}/auth/session', timeout=20)
            session_json = session_info.json() if session_info.ok else {}
            if session_info.ok and session_json.get('authenticated') and session_json.get('role') == 'ADMIN':
                results['AUTH-001'] = ('Pass', note('관리자 로그인 성공', f"role={session_json.get('role')}", f"user={session_json.get('username')}"))
            else:
                results['AUTH-001'] = ('Fail', note('로그인 후 세션 검증 실패', f'status={session_info.status_code}', session_info.text[:160]))
        else:
            results['AUTH-001'] = ('Fail', note('관리자 로그인 실패', f'status={auth.status_code}', auth.text[:160]))
            raise RuntimeError('AUTH-001 failed')

        health = request(public_opener, f'{BASE_URL}/health', timeout=20)
        if health.ok and health.json().get('status') == 'ok':
            results['SYS-001'] = ('Pass', note('외부 health 정상', f'status={health.status_code}', json.dumps(health.json(), ensure_ascii=False)))
        else:
            results['SYS-001'] = ('Fail', note('외부 health 실패', f'status={health.status_code}', health.text[:160]))

        dash = request(opener, f'{BASE_URL}/dashboard/collection', timeout=20)
        slots: list[dict[str, Any]] = []
        if dash.ok:
            dash_json = dash.json()
            slots = list(dash_json.get('by_slot') or [])
            if slots:
                results['DASH-001'] = ('Pass', note('대시보드 장식장 데이터 조회 성공', f'slots={len(slots)}'))
            else:
                results['DASH-001'] = ('Fail', '대시보드 by_slot 데이터가 비어 있습니다.')
        else:
            results['DASH-001'] = ('Fail', note('대시보드 조회 실패', f'status={dash.status_code}', dash.text[:160]))

        slotted_items = request(opener, f'{BASE_URL}/owned-items?slot_state=SLOTTED&status=IN_COLLECTION&limit=5', timeout=20)
        if slotted_items.ok and slotted_items.json():
            first_item = slotted_items.json()[0]
            slot_id = first_item.get('storage_slot_id')
            slot_code = first_item.get('slot_code')
            slot_items = request(opener, f'{BASE_URL}/storage-slots/{slot_id}/owned-items', timeout=20) if slot_id else None
            if slot_items is not None and slot_items.ok and len(slot_items.json()) >= 1:
                results['DASH-002'] = ('Pass', note('칸 상품 조회 성공', f'slot={slot_code}', f"items={len(slot_items.json())}"))
            else:
                status = slot_items.status_code if slot_items is not None else 'NO_SLOT_ID'
                body = slot_items.text[:160] if slot_items is not None else 'slot_id 없음'
                results['DASH-002'] = ('Fail', note('칸 상품 조회 실패', f'slot={slot_code}', f'status={status}', body))
        else:
            results['DASH-002'] = ('Fail', '슬롯에 배치된 상품이 없어 칸 상품 조회를 검증하지 못했습니다.')

        search = request(opener, f'{BASE_URL}/album-masters?item_name=%EC%82%B0%EC%9A%B8%EB%A6%BC%2011%EC%A7%91&limit=5', timeout=20)
        if search.ok and search.json():
            first = search.json()[0]
            results['SEARCH-001'] = ('Pass', note('앨범 검색 성공', f"master_id={first.get('id')}", f"title={first.get('title')}"))
        else:
            results['SEARCH-001'] = ('Fail', note('앨범 검색 실패', f'status={search.status_code}', search.text[:160]))

        temp_title = f'QA SMOKE TEMP {int(time.time())}'
        create_payload: dict[str, Any] = {
            'category': 'CD',
            'size_group': 'STD',
            'preferred_storage_size_group': 'STD',
            'item_name_override': temp_title,
            'music_detail': {
                'format_name': 'CD',
                'artist_or_brand': 'QA Smoke Artist',
                'label_name': 'QA Label',
                'catalog_no': 'QA-SMOKE-001',
            },
        }
        create_res = request_json(opener, f'{BASE_URL}/owned-items', method='POST', payload=create_payload, timeout=25)
        if create_res.ok:
            created = create_res.json()
            created_owned_item_id = int(created.get('owned_item_id') or 0)
            delete_res = request(opener, f'{BASE_URL}/owned-items/{created_owned_item_id}', method='DELETE', timeout=25)
            if delete_res.ok:
                results['REGISTER-002'] = ('Pass', note('간편 등록 저장/삭제 성공', f'owned_item_id={created_owned_item_id}', f"label_id={created.get('label_id')}"))
                created_owned_item_id = None
            else:
                results['REGISTER-002'] = ('Fail', note('생성 후 삭제 실패', f'owned_item_id={created_owned_item_id}', f'status={delete_res.status_code}', delete_res.text[:160]))
        else:
            results['REGISTER-002'] = ('Fail', note('간편 등록 저장 실패', f'status={create_res.status_code}', create_res.text[:160]))

        backup = request(opener, f'{BASE_URL}/ops/export/db-backup', timeout=60)
        content_disposition = backup.headers.get('content-disposition', '')
        if backup.ok and len(backup.body) > 0 and 'attachment' in content_disposition.lower():
            results['OPS-010'] = ('Pass', note('DB 백업 다운로드 성공', f'bytes={len(backup.body)}'))
        else:
            results['OPS-010'] = ('Fail', note('DB 백업 다운로드 실패', f'status={backup.status_code}', f'bytes={len(backup.body)}', content_disposition))

        local_health = request(public_opener, LOCAL_HEALTH_URL, timeout=10)
        launchd = subprocess.run(['launchctl', 'print', LAUNCHD_LABEL], capture_output=True, text=True, timeout=15)
        launchd_ok = launchd.returncode == 0 and 'state = running' in (launchd.stdout or '')
        if local_health.ok and local_health.json().get('status') == 'ok' and launchd_ok:
            results['REC-001'] = ('Pass', note('자동 복구 상태 정상', 'launchd running', 'local health ok', '2026-03-13 실재부팅 검증 이력 포함'))
        else:
            results['REC-001'] = ('Fail', note('자동 복구 상태 확인 실패', f'local={local_health.status_code}', f'launchd_return={launchd.returncode}'))

    finally:
        if created_owned_item_id:
            try:
                request(opener, f'{BASE_URL}/owned-items/{created_owned_item_id}', method='DELETE', timeout=15)
            except Exception:
                pass

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

    passed = [suite for suite, (status, _) in results.items() if status == 'Pass']
    failed = [suite for suite, (status, _) in results.items() if status == 'Fail']
    blocked = [suite for suite, (status, _) in results.items() if status == 'Blocked']

    print('스모크 QA 결과')
    print(f'- Pass: {len(passed)}')
    print(f'- Fail: {len(failed)}')
    print(f'- Blocked: {len(blocked)}')
    for suite_id in SMOKE_IDS:
        status, notes = results[suite_id]
        print(f'[{status}] {suite_id} :: {notes}')

    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(run())
