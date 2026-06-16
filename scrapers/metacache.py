"""Shared, persistent cache for per-page metadata (poster + description).

Several scrapers fetch a detail page per event just to read an image and a
description (cinema films, Berlin Bühnen productions, MEC events). Those pages
barely change, so we cache the extracted ``{img, desc}`` per URL in
``docs/data/_metacache.json`` (committed by the Action). Subsequent runs reuse
the cache and skip the fetch -- cutting hundreds of requests per night.
"""

from __future__ import annotations

import json
import pathlib

CACHE_FILE = (pathlib.Path(__file__).resolve().parents[1]
              / "docs" / "data" / "_metacache.json")

_cache: dict | None = None


def _load() -> dict:
    global _cache
    if _cache is None:
        try:
            _cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache = {}
    return _cache


def get(url: str):
    """Return cached ``{"img":..., "desc":...}`` for url, or None if unseen."""
    return _load().get(url)


def put(url: str, img: str | None, desc: str | None) -> None:
    _load()[url] = {"img": img, "desc": desc}


def save() -> None:
    if _cache is None:
        return
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        CACHE_FILE.write_text(
            json.dumps(_cache, ensure_ascii=False, sort_keys=True),
            encoding="utf-8")
    except OSError:
        pass
