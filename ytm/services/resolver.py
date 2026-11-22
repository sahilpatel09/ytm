from __future__ import annotations

import threading
import time

import yt_dlp

YDL_OPTS = {
    "format": "bestaudio/best",
    "noplaylist": True,
    "quiet": True,
    "no_warnings": True,
    "skip_download": True,
    "extractor_args": {"youtube": {"skip": ["translated_subs", "dash"]}},
}


class StreamResolver:
    """Resolves short-lived YouTube Music audio stream URLs via yt-dlp."""

    def __init__(self, ttl: int = 1800) -> None:
        self._ttl = ttl
        self._cache: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()

    def resolve(self, video_id: str) -> str:
        with self._lock:
            hit = self._cache.get(video_id)
            if hit and time.time() - hit[1] < self._ttl:
                return hit[0]

        url = self._extract(video_id)
        with self._lock:
            if len(self._cache) > 32:
                self._cache.clear()
            self._cache[video_id] = (url, time.time())
        return url

    def _extract(self, video_id: str) -> str:
        watch_url = f"https://music.youtube.com/watch?v={video_id}"
        with yt_dlp.YoutubeDL(YDL_OPTS) as ydl:
            info = ydl.extract_info(watch_url, download=False)
        if not info:
            raise RuntimeError("yt-dlp returned no info")
        if info.get("url"):
            return info["url"]
        for fmt in info.get("requested_formats") or []:
            if fmt.get("url"):
                return fmt["url"]
        raise RuntimeError("no audio stream url found")
