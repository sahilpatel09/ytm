from __future__ import annotations

from dataclasses import dataclass

from ytmusicapi import YTMusic


@dataclass(slots=True)
class Track:
    video_id: str
    title: str
    artist: str
    album: str = ""
    duration: str = ""
    duration_seconds: int = 0
    thumbnail: str = ""

    @property
    def watch_url(self) -> str:
        return f"https://music.youtube.com/watch?v={self.video_id}"


def _join_artists(artists: list | None) -> str:
    if not artists:
        return ""
    return ", ".join(a.get("name", "") for a in artists if a)


class MusicService:
    def __init__(self) -> None:
        self._ytm = YTMusic()

    def search(self, query: str, limit: int = 20) -> list[Track]:
        raw = self._ytm.search(query, filter="songs", limit=limit)
        tracks: list[Track] = []
        for item in raw:
            video_id = item.get("videoId")
            if not video_id:
                continue
            thumbs = item.get("thumbnails") or []
            thumb = thumbs[-1].get("url", "") if thumbs else ""
            album = item.get("album") or {}
            tracks.append(
                Track(
                    video_id=video_id,
                    title=item.get("title", ""),
                    artist=_join_artists(item.get("artists")),
                    album=album.get("name", ""),
                    duration=item.get("duration") or "",
                    duration_seconds=item.get("duration_seconds") or 0,
                    thumbnail=thumb,
                )
            )
        return tracks
