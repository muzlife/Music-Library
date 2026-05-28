"""Local file player using VLC (fallback: afplay).

Controls VLC via its RC (Remote Control) UNIX socket interface,
providing play/pause/stop/volume. Falls back to afplay if VLC
is not available.
"""

from __future__ import annotations

import logging
import os
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

MUSIC_ROOT = "/Volumes/Music"
AUDIO_EXTS = {".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".aiff", ".wma"}
VLC_BIN = "/opt/homebrew/bin/vlc"
VLC_SOCKET = "/tmp/vlc_rc.sock"


class LocalPlayer:
    def __init__(self) -> None:
        self._vlc_proc: subprocess.Popen | None = None
        self._afplay_proc: subprocess.Popen | None = None
        self._current_file: str | None = None
        self._use_vlc = os.path.isfile(VLC_BIN) and os.access(VLC_BIN, os.X_OK)

    @property
    def configured(self) -> bool:
        return Path(MUSIC_ROOT).is_dir()

    # ── VLC RC socket control ──────────────────────────────────

    def _send_rc(self, cmd: str) -> str | None:
        """Send a command to VLC RC socket."""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect(VLC_SOCKET)
            sock.sendall((cmd + "\n").encode())
            time.sleep(0.1)
            try:
                return sock.recv(4096).decode().strip()
            except socket.timeout:
                return None
            finally:
                sock.close()
        except Exception:
            return None

    def _ensure_vlc(self) -> bool:
        """Start VLC with RC interface if not running."""
        if not self._use_vlc:
            return False
        if os.path.exists(VLC_SOCKET):
            # Test if socket is alive
            resp = self._send_rc("status")
            if resp is not None:
                return True
            # Dead socket - remove it
            os.unlink(VLC_SOCKET)
        try:
            self._vlc_proc = subprocess.Popen(
                [VLC_BIN, "-I", "rc", "--rc-unix", VLC_SOCKET, "--no-video", "--play-and-exit"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            # Wait for socket to appear
            for _ in range(50):
                if os.path.exists(VLC_SOCKET):
                    time.sleep(0.5)
                    return True
                time.sleep(0.1)
            return False
        except Exception:
            logger.exception("failed to start VLC")
            return False

    # ── playback ───────────────────────────────────────────────

    def play(self, file_path: str) -> bool:
        """Play a local audio file."""
        if not os.path.isfile(file_path):
            return False
        self.stop()
        self._current_file = file_path
        if self._use_vlc:
            return self._play_vlc(file_path)
        else:
            return self._play_afplay(file_path)

    def _play_vlc(self, file_path: str) -> bool:
        if not self._ensure_vlc():
            return self._play_afplay(file_path)
        # Clear playlist and add new file
        self._send_rc("clear")
        resp = self._send_rc(f"add {file_path}")
        if resp is None:
            return self._play_afplay(file_path)
        self._send_rc("play")
        return True

    def _play_afplay(self, file_path: str) -> bool:
        try:
            self._afplay_proc = subprocess.Popen(
                ["afplay", file_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        except Exception:
            return False

    def stop(self) -> bool:
        if self._use_vlc and os.path.exists(VLC_SOCKET):
            self._send_rc("stop")
        if self._afplay_proc is not None:
            try:
                self._afplay_proc.terminate()
                self._afplay_proc.wait(timeout=3)
            except Exception:
                try:
                    self._afplay_proc.kill()
                except Exception:
                    pass
            self._afplay_proc = None
        self._current_file = None
        return True

    def pause(self) -> bool:
        if self._use_vlc and os.path.exists(VLC_SOCKET):
            self._send_rc("pause")
            return True
        return self.stop()

    @property
    def is_playing(self) -> bool:
        if self._use_vlc and os.path.exists(VLC_SOCKET):
            resp = self._send_rc("is_playing")
            return resp == "1" if resp else False
        if self._afplay_proc is not None:
            return self._afplay_proc.poll() is None
        return False

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

    # ── search ─────────────────────────────────────────────────

    def scan_files(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search local music files using SQLite index."""
        results: list[dict[str, Any]] = []
        q = query.strip()
        if not q or not self.configured:
            return results

        from app.db import search_local_index as db_search
        rows = db_search(q, limit=limit)
        for row in rows:
            fp = row["file_path"]
            if os.path.isfile(fp):
                results.append({
                    "source": "local",
                    "file_path": fp,
                    "title": row["title"],
                    "artist": row["artist"],
                    "album_art_url": None,
                    "rel_path": os.path.relpath(fp, MUSIC_ROOT) if fp.startswith(MUSIC_ROOT) else fp,
                })

        # Fallback: find (if index is empty)
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
                    if fp and os.path.isfile(fp) and Path(fp).suffix.lower() in AUDIO_EXTS:
                        results.append(self._file_to_item(fp))
            except Exception:
                pass

        return results

    def _file_to_item(self, fp: str) -> dict[str, Any]:
        name = Path(fp).stem
        artist, title = name, name
        if " - " in name:
            parts = name.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].strip()
        return {
            "source": "local",
            "file_path": fp,
            "title": title,
            "artist": artist,
            "album_art_url": None,
            "rel_path": os.path.relpath(fp, MUSIC_ROOT) if fp.startswith(MUSIC_ROOT) else fp,
        }
