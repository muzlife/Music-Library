"""Spotify API integration via spotipy SDK.

Provides search (Client Credentials), playback control (OAuth),
and current playback status. Dual auth: client credentials for
search, OAuth user token for playback.
"""

from __future__ import annotations

import logging
import os
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)


import time

_PLAYBACK_CACHE = {
    "timestamp": 0.0,
    "value": None,
}


class SpotifyService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client_id = str(settings.spotify_client_id or "").strip()
        self.client_secret = str(settings.spotify_client_secret or "").strip()
        self.redirect_uri = str(settings.spotify_redirect_uri or "").strip()
        self._sp: Any = None
        self._sp_cc: Any = None  # client credentials client for search

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _ensure_client_cc(self) -> Any:
        """Client Credentials client — for search (no user auth needed)."""
        if not self.configured:
            return None
        if self._sp_cc is not None:
            return self._sp_cc
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyClientCredentials
            self._sp_cc = spotipy.Spotify(
                client_credentials_manager=SpotifyClientCredentials(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                )
            )
        except Exception:
            logger.exception("failed to initialize spotipy CC client")
            return None
        return self._sp_cc

    def _ensure_client(self) -> Any:
        """OAuth client — for playback (user auth needed)."""
        if not self.configured:
            return None
        if self._sp is not None:
            return self._sp
        try:
            import spotipy
            from spotipy.oauth2 import SpotifyOAuth
            cache_path = os.path.join(os.path.expanduser("~"), ".spotify_cache")
            self._sp = spotipy.Spotify(
                auth_manager=SpotifyOAuth(
                    client_id=self.client_id,
                    client_secret=self.client_secret,
                    redirect_uri=self.redirect_uri,
                    scope="user-modify-playback-state user-read-playback-state",
                    cache_path=cache_path,
                    open_browser=False,
                )
            )
        except Exception:
            logger.exception("failed to initialize spotipy OAuth client")
            return None
        return self._sp

    # ── search (uses Client Credentials) ─────────────────────────

    def search_tracks_sync(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        limit = min(limit, 10)  # Spotify rejects limit > 10
        sp = self._ensure_client_cc()
        if sp is None:
            return []
        # Spotify search API currently rejects limits > 10 for this application/integration
        api_limit = min(limit, 10)
        try:
            results = sp.search(q=query, type="track", limit=api_limit)
        except Exception:
            logger.exception("spotify search failed")
            return []
        items: list[dict[str, Any]] = []
        for item in (results.get("tracks", {}).get("items") or []):
            album = item.get("album", {})
            images = album.get("images") or []
            items.append({
                "spotify_track_id": item.get("id"),
                "title": item.get("name"),
                "artist": ", ".join(a.get("name", "") for a in item.get("artists", [])),
                "album_name": album.get("name"),
                "album_art_url": images[1]["url"] if len(images) > 1 else (images[0]["url"] if images else None),
                "duration_ms": item.get("duration_ms"),
                "track_uri": item.get("uri"),
            })
        return items

    def search_albums_sync(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        limit = min(limit, 10)
        sp = self._ensure_client_cc()
        if sp is None:
            return []
        try:
            results = sp.search(q=query, type="album", limit=limit)
        except Exception:
            logger.exception("spotify album search failed")
            return []
        items: list[dict[str, Any]] = []
        for item in (results.get("albums", {}).get("items") or []):
            images = item.get("images") or []
            items.append({
                "spotify_album_id": item.get("id"),
                "spotify_album_uri": item.get("uri"),
                "name": item.get("name"),
                "artist": ", ".join(a.get("name", "") for a in item.get("artists", [])),
                "release_date": item.get("release_date"),
                "total_tracks": item.get("total_tracks", 0),
                "image_url": images[1]["url"] if len(images) > 1 else (images[0]["url"] if images else None),
            })
        return items

    def track_sync(self, track_id: str) -> dict[str, Any] | None:
        """Get a single track by ID (CC client)."""
        sp = self._ensure_client_cc()
        if sp is None:
            return None
        try:
            return sp.track(track_id)
        except Exception:
            return None

    def album_tracks_sync(self, album_id: str) -> list[dict[str, Any]]:
        """Get tracks for an album (CC client)."""
        sp = self._ensure_client_cc()
        if sp is None:
            return []
        try:
            result = sp.album_tracks(album_id)
            return result.get("items", []) if result else []
        except Exception:
            return []

    # ── recommendations ──────────────────────────────────────────

    def get_recommendations_sync(self, seed_track_id: str, limit: int = 10) -> list[dict[str, Any]]:
        sp = self._ensure_client_cc()
        if sp is None:
            return []
        try:
            results = sp.recommendations(seed_tracks=[seed_track_id], limit=limit)
        except Exception:
            return []
        items: list[dict[str, Any]] = []
        for item in (results.get("tracks") or []):
            album = item.get("album", {})
            images = album.get("images") or []
            items.append({
                "spotify_track_id": item.get("id"),
                "title": item.get("name"),
                "artist": ", ".join(a.get("name", "") for a in item.get("artists", [])),
                "album_name": album.get("name"),
                "album_art_url": images[1]["url"] if len(images) > 1 else (images[0]["url"] if images else None),
                "duration_ms": item.get("duration_ms"),
                "track_uri": item.get("uri"),
            })
        return items

    # ── playback (uses OAuth) ────────────────────────────────────

    def play_sync(self, track_uri: str) -> bool:
        sp = self._ensure_client()
        if sp is None:
            return False
        try:
            sp.start_playback(uris=[track_uri])
            return True
        except Exception:
            return False

    def pause_sync(self) -> bool:
        sp = self._ensure_client()
        if sp is None:
            return False
        try:
            sp.pause_playback()
            return True
        except Exception:
            return False

    def current_playback_sync(self) -> dict[str, Any] | None:
        now = time.time()
        if now - _PLAYBACK_CACHE["timestamp"] < 5.0:
            return _PLAYBACK_CACHE["value"]

        sp = self._ensure_client()
        if sp is None:
            _PLAYBACK_CACHE["timestamp"] = now
            _PLAYBACK_CACHE["value"] = None
            return None
        try:
            pb = sp.current_playback()
        except Exception:
            _PLAYBACK_CACHE["timestamp"] = now
            _PLAYBACK_CACHE["value"] = None
            return None
        if not pb or not pb.get("is_playing"):
            _PLAYBACK_CACHE["timestamp"] = now
            _PLAYBACK_CACHE["value"] = None
            return None
        item = pb.get("item") or {}
        album = item.get("album", {})
        images = album.get("images") or []
        val = {
            "spotify_track_id": item.get("id"),
            "title": item.get("name"),
            "artist": ", ".join(a.get("name", "") for a in item.get("artists", [])),
            "album_name": album.get("name"),
            "album_art_url": images[1]["url"] if len(images) > 1 else (images[0]["url"] if images else None),
            "duration_ms": item.get("duration_ms"),
            "position_ms": pb.get("progress_ms"),
            "track_uri": item.get("uri"),
            "is_playing": True,
        }
        _PLAYBACK_CACHE["timestamp"] = now
        _PLAYBACK_CACHE["value"] = val
        return val
