"""Local file player using macOS afplay.

Scans /Volumes/Music for audio files and provides a simple
playback interface compatible with the SpotifyService pattern.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MUSIC_ROOT = "/Volumes/Music"
AUDIO_EXTS = {".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".aiff", ".wma"}


class LocalPlayer:
    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None
        self._current_file: str | None = None

    @property
    def configured(self) -> bool:
        return Path(MUSIC_ROOT).is_dir()

    def scan_files(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search local music files using macOS Spotlight (mdfind)."""
        results: list[dict[str, Any]] = []
        q = query.strip()
        if not q or not self.configured:
            return results

        # Build mdfind query for audio files matching name
        ext_cond = " || ".join(f"kMDItemFSName == '*{ext}'" for ext in AUDIO_EXTS)
        cmd = [
            "mdfind", "-onlyin", MUSIC_ROOT,
            f"({ext_cond}) && kMDItemFSName == '*{q}*'cd"
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            for line in proc.stdout.strip().split("\n"):
                if len(results) >= limit:
                    break
                fp = line.strip()
                if not fp or not os.path.isfile(fp):
                    continue
                name = Path(fp).stem
                artist, title = name, name
                if " - " in name:
                    parts = name.split(" - ", 1)
                    artist = parts[0].strip()
                    title = parts[1].strip()
                results.append({
                    "source": "local",
                    "file_path": fp,
                    "title": title,
                    "artist": artist,
                    "album_art_url": None,
                    "rel_path": os.path.relpath(fp, MUSIC_ROOT) if fp.startswith(MUSIC_ROOT) else fp,
                })
        except Exception:
            logger.exception("mdfind failed")

        # Fallback: use find if mdfind returned nothing
        if not results:
            try:
                proc = subprocess.run(
                    ["find", MUSIC_ROOT, "-name", f"*{q}*", "-maxdepth", "4"],
                    capture_output=True, text=True, timeout=3,
                )
                for line in proc.stdout.strip().split("\n"):
                    if len(results) >= limit:
                        break
                    fp = line.strip()
                    if not fp or not os.path.isfile(fp):
                        continue
                    if Path(fp).suffix.lower() not in AUDIO_EXTS:
                        continue
                    name = Path(fp).stem
                    artist, title = name, name
                    if " - " in name:
                        parts = name.split(" - ", 1)
                        artist = parts[0].strip()
                        title = parts[1].strip()
                    results.append({
                        "source": "local",
                        "file_path": fp,
                        "title": title,
                        "artist": artist,
                        "album_art_url": None,
                        "rel_path": os.path.relpath(fp, MUSIC_ROOT) if fp.startswith(MUSIC_ROOT) else fp,
                    })
            except Exception:
                pass

        return results

    def play(self, file_path: str) -> bool:
        """Play a local audio file via afplay."""
        self.stop()
        if not os.path.isfile(file_path):
            return False
        try:
            self._proc = subprocess.Popen(
                ["afplay", file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            self._current_file = file_path
            return True
        except Exception:
            logger.exception("afplay failed")
            return False

    def stop(self) -> bool:
        if self._proc is not None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=3)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None
            self._current_file = None
            return True
        return False

    @property
    def is_playing(self) -> bool:
        if self._proc is None:
            return False
        return self._proc.poll() is None

    def current_track(self) -> dict[str, Any] | None:
        if not self._current_file:
            return None
        f = Path(self._current_file)
        name = f.stem
        artist = ""
        title = name
        if " - " in name:
            parts = name.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].strip()
        return {
            "source": "local",
            "title": title,
            "artist": artist,
            "album_art_url": None,
            "album_name": f.parent.name,
            "file_path": self._current_file,
            "is_playing": self.is_playing,
        }
