import sys
import os
import time
import logging

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.spotify import SpotifyService
from app.db.album_master_spotify import batch_match_spotify
from spotipy.exceptions import SpotifyException

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("spotify_daemon")

def main():
    logger.info("Starting Spotify Batch Match Daemon")
    sp = SpotifyService()
    if not sp.configured:
        logger.error("Spotify is not configured. Exiting.")
        sys.exit(1)
        
    while True:
        logger.info("Starting batch match run...")
        try:
            result = batch_match_spotify(sp, limit=100, only_unmatched=True)
            matched = result.get("matched", 0)
            skipped = result.get("skipped", 0)
            errors = result.get("errors", 0)
            
            logger.info(f"Batch completed: matched={matched}, skipped={skipped}, errors={errors}")
            
            # If nothing was matched or skipped or errored, we processed everything. Exit.
            if matched == 0 and skipped == 0 and errors == 0:
                logger.info("No more unmatched albums found. Exiting.")
                break
                
            logger.info("Waiting 30 seconds before next batch...")
            time.sleep(30)
            
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = 3600
                if hasattr(e, "headers") and e.headers and "Retry-After" in e.headers:
                    try:
                        retry_after = int(e.headers["Retry-After"])
                    except ValueError:
                        pass
                retry_after = max(retry_after, 60)  # Min sleep 60s
                logger.warning(f"Spotify rate limit (429) hit. Sleeping for {retry_after} seconds ({retry_after/3600:.2f} hours)...")
                time.sleep(retry_after)
            else:
                logger.error(f"Spotify API error: {e}. Sleeping 5 minutes...")
                time.sleep(300)
        except Exception as e:
            logger.error(f"Unexpected error: {e}. Sleeping 5 minutes...")
            time.sleep(300)

if __name__ == "__main__":
    main()
