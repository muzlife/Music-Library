"""WESTERN 도메인 Spotify 배치 매칭 스크립트."""
import sys
import os
import time
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.spotify import SpotifyService
from app.db.album_master_spotify import batch_match_spotify
from spotipy.exceptions import SpotifyException

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("spotify_western")

BATCH_SIZE = 20
SLEEP_PER_ITEM = 55.0   # ~1 album/min (API 호출 시간 포함하면 약 60초)
SLEEP_BETWEEN_BATCHES = 60
DOMAIN = "WESTERN"


def main():
    sp = SpotifyService()
    if not sp.configured:
        logger.error("Spotify not configured. 종료.")
        sys.exit(1)

    total_matched = total_skipped = total_errors = 0
    run = 0

    while True:
        run += 1
        logger.info("배치 #%d 시작 (domain=%s, limit=%d)", run, DOMAIN, BATCH_SIZE)
        try:
            result = batch_match_spotify(sp, limit=BATCH_SIZE, only_unmatched=True, domain_code=DOMAIN, sleep_per_item=SLEEP_PER_ITEM)
            m, s, e = result["matched"], result["skipped"], result["errors"]
            total_matched += m
            total_skipped += s
            total_errors += e
            logger.info("배치 #%d 완료: 매칭=%d, 스킵=%d, 오류=%d | 누계: 매칭=%d, 스킵=%d, 오류=%d",
                        run, m, s, e, total_matched, total_skipped, total_errors)

            if m == 0 and s == 0 and e == 0:
                logger.info("미연결 항목 없음. 종료.")
                break

            logger.info("%d초 대기...", SLEEP_BETWEEN_BATCHES)
            time.sleep(SLEEP_BETWEEN_BATCHES)

        except SpotifyException as exc:
            if exc.http_status == 429:
                retry = 3600
                if hasattr(exc, "headers") and exc.headers and "Retry-After" in exc.headers:
                    try:
                        retry = int(exc.headers["Retry-After"])
                    except ValueError:
                        pass
                retry = max(retry, 60)
                logger.warning("Spotify 속도 제한(429). %d초 대기...", retry)
                time.sleep(retry)
            else:
                logger.error("Spotify API 오류: %s. 5분 대기...", exc)
                time.sleep(300)
        except Exception as exc:
            logger.exception("예상치 못한 오류: %s", exc)
            time.sleep(60)

    logger.info("완료. 최종: 매칭=%d, 스킵=%d, 오류=%d", total_matched, total_skipped, total_errors)


if __name__ == "__main__":
    main()
