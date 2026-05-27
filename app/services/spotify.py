"""Spotify API integration via spotipy SDK.

Provides search, playback control, and current playback status.
All methods are synchronous wrappers around spotipy — the cafe
API layer calls them via asyncio.to_thread where needed.
"""

from __future__ import annotations

import logging
from typing import Any

from ..config import get_settings

logger = logging.getLogger(__name__)


class SpotifyService:
    def __init__(self) -> None:
        settings = get_settings()
        self.client_id = str(settings.spotify_client_id or "").strip()
        self.client_secret = str(settings.spotify_client_secret or "").strip()
        self.redirect_uri = str(settings.spotify_redirect_uri or "").strip()
        self._sp: Any = None

    @property
    def configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _ensure_client(self) -> Any:
        if not self.configured:
            return None
        try:
            import spotipy  # type: ignore[import-untyped]
            from spotipy.oauth2 import SpotifyOAuth  # type: ignore[import-untyped]

            import os
            cache_path = "/Users/jingunpark/.spotify_cache"
            return spotipy.Spotify(
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
            logger.exception("failed to initialize spotipy client")
            return None

    # ── search ──────────────────────────────────────────────────

    def search_tracks_sync(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        sp = self._ensure_client()
        if sp is None:
            return []
        try:
            results = sp.search(q=query, type="track", limit=limit)
        except Exception:
            logger.exception("spotify search failed")
            return []
        items: list[dict[str, Any]] = []
        for item in (results.get("tracks", {}).get("items") or []):
            album = item.get("album", {})
            images = album.get("images") or []
            items.append(
                {
                    "spotify_track_id": item.get("id"),
                    "title": item.get("name"),
                    "artist": ", ".join(
                        a.get("name", "") for a in item.get("artists", [])
                    ),
                    "album_name": album.get("name"),
                    "album_art_url": images[1]["url"]
                    if len(images) > 1
                    else (images[0]["url"] if images else None),
                    "duration_ms": item.get("duration_ms"),
                    "track_uri": item.get("uri"),
                }
            )
        return items

    # ── recommendations ──────────────────────────────────────────

    def get_recommendations_sync(
        self, seed_track_id: str, limit: int = 10
    ) -> list[dict[str, Any]]:
        sp = self._ensure_client()
        if sp is None:
            return []
        try:
            results = sp.recommendations(
                seed_tracks=[seed_track_id], limit=limit
            )
        except Exception:
            logger.exception("spotify recommendations failed")
            return []
        items: list[dict[str, Any]] = []
        for item in (results.get("tracks") or []):
            album = item.get("album", {})
            images = album.get("images") or []
            items.append(
                {
                    "spotify_track_id": item.get("id"),
                    "title": item.get("name"),
                    "artist": ", ".join(
                        a.get("name", "") for a in item.get("artists", [])
                    ),
                    "album_name": album.get("name"),
                    "album_art_url": images[1]["url"]
                    if len(images) > 1
                    else (images[0]["url"] if images else None),
                    "duration_ms": item.get("duration_ms"),
                    "track_uri": item.get("uri"),
                }
            )
        return items

    # ── playback ─────────────────────────────────────────────────

    def play_sync(self, track_uri: str) -> bool:
        sp = self._ensure_client()
        if sp is None:
            return False
        try:
            sp.start_playback(uris=[track_uri])
            return True
        except Exception:
            logger.exception("spotify play failed")
            return False

    def pause_sync(self) -> bool:
        sp = self._ensure_client()
        if sp is None:
            return False
        try:
            sp.pause_playback()
            return True
        except Exception:
            logger.exception("spotify pause failed")
            return False

    def current_playback_sync(self) -> dict[str, Any] | None:
        sp = self._ensure_client()
        if sp is None:
            return None
        try:
            pb = sp.current_playback()
        except Exception:
            logger.exception("spotify current_playback failed")
            return None
        if not pb or not pb.get("is_playing"):
            return None
        item = pb.get("item") or {}
        album = item.get("album", {})
        images = album.get("images") or []
        return {
            "spotify_track_id": item.get("id"),
            "title": item.get("name"),
            "artist": ", ".join(
                a.get("name", "") for a in item.get("artists", [])
            ),
            "album_name": album.get("name"),
            "album_art_url": images[1]["url"]
            if len(images) > 1
            else (images[0]["url"] if images else None),
            "duration_ms": item.get("duration_ms"),
            "position_ms": pb.get("progress_ms"),
            "track_uri": item.get("uri"),
            "is_playing": True,
        }
