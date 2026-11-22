"""Lyrics fetching via LRCLIB (free, no API key) with LRC parsing."""

from __future__ import annotations

import re
import threading
from dataclasses import dataclass, field

import requests

from ytm.services.music import Track

BASE_URL = "https://lrclib.net"
HEADERS = {"User-Agent": "ytm-terminal/0.1 (local dotfiles player)"}
TIMEOUT = 10.0

_LRC_TAG = re.compile(r"\[(\d+):(\d+(?:\.\d+)?)\]")
_WORD_TAG = re.compile(r"<\d+:\d+(?:\.\d+)?>")


@dataclass(slots=True)
class Lyrics:
    lines: list[tuple[float, str]] = field(default_factory=list)
    synced: bool = False
    instrumental: bool = False


def parse_lrc(text: str) -> list[tuple[float, str]]:
    out: list[tuple[float, str]] = []
    for raw in text.splitlines():
        raw = raw.strip()
        if not raw:
            continue
        tags = list(_LRC_TAG.finditer(raw))
        if not tags:
            continue  # metadata lines such as [ar: ...] or [offset: ...]
        body = _WORD_TAG.sub("", raw[tags[-1].end():]).strip()
        for match in tags:
            seconds = int(match.group(1)) * 60 + float(match.group(2))
            out.append((seconds, body))
    out.sort(key=lambda pair: pair[0])
    return out


def clean_title(title: str) -> str:
    """Strip YouTube suffix junk: ' | ...', ' [...]', ' (...)' (iterated)."""
    t = title.split("|")[0]
    t = re.sub(r"\s*\[[^\[\]]*\]\s*$", "", t)
    while True:
        stripped = re.sub(r"\s*\([^()]*\)\s*$", "", t)
        if stripped == t:
            break
        t = stripped
    t = t.strip()
    return t or title


def clean_artist(artist: str) -> str:
    """First credited artist — LRCLIB rarely stores full credit lists."""
    first = artist.split(",")[0].strip()
    return first or artist


def artists_overlap(track_artist: str, credited: str) -> bool:
    """True when any word of our artist appears in LRCLIB's credit (or we can't judge)."""
    if not track_artist or not credited:
        return True
    a, c = track_artist.casefold(), credited.casefold()
    if a in c or c in a:
        return True
    tokens = [t for t in re.split(r"[^a-z0-9]+", a) if len(t) >= 3]
    if not tokens:  # non-latin script or initials: can't judge
        return True
    return any(t in c for t in tokens)


class LyricsService:
    """Thread-safe lyrics lookup with a per-video cache."""

    def __init__(self) -> None:
        self._cache: dict[str, Lyrics | None] = {}
        self._lock = threading.Lock()

    def peek(self, video_id: str) -> tuple[bool, Lyrics | None]:
        """Return (hit, lyrics) without hitting the network. lyrics may be None on a negative hit."""
        with self._lock:
            if video_id in self._cache:
                return True, self._cache[video_id]
        return False, None

    def fetch(self, track: Track) -> Lyrics | None:
        """Fetch lyrics for a track; returns None when definitively not found.

        Raises requests.RequestException on network failure (not cached).
        """
        key = track.video_id
        with self._lock:
            if key in self._cache:
                return self._cache[key]
        lyrics = self._query(track)
        with self._lock:
            self._cache[key] = lyrics
        return lyrics

    @classmethod
    def _query(cls, track: Track) -> Lyrics | None:
        title, artist = track.title, track.artist
        ctitle, cartist = clean_title(title), clean_artist(artist)
        # YouTube titles carry junk ('Song (From "Movie") | Artist') and credit
        # lists that LRCLIB doesn't match, so escalate through normalized forms.
        # LRCLIB also hosts karaoke/instrumental uploads of vocal songs; keep
        # those as a last resort and keep looking for a vocal version.
        want_vocal = "instrumental" not in title.casefold()
        fallback: Lyrics | None = None
        base: dict[str, str | int] = {"track_name": title, "artist_name": artist}
        if track.duration_seconds:
            base["duration"] = int(round(track.duration_seconds))
        attempts = [base]
        if (ctitle, cartist) != (title, artist):
            attempts.append(dict(base, track_name=ctitle, artist_name=cartist))
        for params in attempts:
            response = requests.get(
                f"{BASE_URL}/api/get", params=params, headers=HEADERS, timeout=TIMEOUT
            )
            if response.status_code == 200:
                lyrics = cls._build(response.json())
                if lyrics is not None:
                    if lyrics.instrumental and want_vocal:
                        fallback = fallback or lyrics
                    else:
                        return lyrics
        # fallbacks: structured search, then a free-text query
        search_pairs: list[dict[str, str]] = [
            {"track_name": track.title, "artist_name": track.artist},
            {"track_name": ctitle, "artist_name": cartist},
            {"track_name": ctitle},
            {"q": f"{ctitle} {cartist}"},
        ]
        seen: set[frozenset] = set()
        for params in search_pairs:
            key = frozenset(params.items())
            if key in seen:
                continue
            seen.add(key)
            lyrics = cls._search(track, params)
            if lyrics is None:
                continue
            if lyrics.instrumental and want_vocal:
                fallback = fallback or lyrics
                continue
            return lyrics
        # Only-karaoke found: the song exists on LRCLIB, so drop the artist
        # gate and look for any vocal version with the same title.
        if fallback is not None and want_vocal:
            lyrics = cls._search(track, {"track_name": ctitle}, gate=False)
            if lyrics is not None and not lyrics.instrumental:
                return lyrics
        return fallback

    @classmethod
    def _search(
        cls, track: Track, params: dict[str, str], *, gate: bool = True
    ) -> Lyrics | None:
        response = requests.get(
            f"{BASE_URL}/api/search", params=params, headers=HEADERS, timeout=TIMEOUT
        )
        if response.status_code != 200:
            return None
        data = response.json()
        if not isinstance(data, list):
            return None
        candidates = [
            item
            for item in data
            if isinstance(item, dict)
            and (item.get("plainLyrics") or item.get("syncedLyrics") or item.get("instrumental"))
        ]
        # drop other artists' songs with the same title (covers, different films)
        if gate:
            candidates = [
                item
                for item in candidates
                if artists_overlap(track.artist, item.get("artistName") or "")
            ]
        if not candidates:
            return None

        want_vocal = "instrumental" not in track.title.casefold()

        def distance(item: dict) -> float:
            score = 0.0
            duration = item.get("duration") or 0
            if track.duration_seconds and duration:
                score += abs(float(duration) - float(track.duration_seconds))
            name = (item.get("trackName") or "").casefold()
            target = clean_title(track.title).casefold()
            if target != name:
                score += 5.0 if (target in name or name in target) else 30.0
            if item.get("instrumental") and want_vocal:
                score += 40.0
            if "instrumental" in name and "instrumental" not in target:
                score += 40.0
            return score

        return cls._build(min(candidates, key=distance))

    @staticmethod
    def _build(record: dict) -> Lyrics | None:
        synced_text = record.get("syncedLyrics") or ""
        if synced_text:
            lines = parse_lrc(synced_text)
            if lines:
                return Lyrics(lines=lines, synced=True)
        plain = record.get("plainLyrics") or ""
        plain_lines = plain.splitlines()
        if any(line.strip() for line in plain_lines):
            return Lyrics(lines=[(0.0, line.rstrip()) for line in plain_lines])
        if record.get("instrumental"):
            return Lyrics(instrumental=True)
        return None
