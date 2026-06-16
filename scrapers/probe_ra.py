"""One-off probe: can we read a public RA following list?

RA HTML profile pages usually 403 to bots; the GraphQL endpoint is open but
private data (who you follow) is normally login-gated. This checks both for the
given profile and dumps whatever is reachable.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Iterable

import requests

from .base import BaseScraper, Event

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
SLUG = "flipss"
BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en;q=0.9,de;q=0.8",
}
GQL_HEADERS = {
    **BROWSER, "Accept": "application/json", "Content-Type": "application/json",
    "Referer": "https://ra.co/", "Origin": "https://ra.co",
    "ra-content-language": "en",
}


class ProbeRaScraper(BaseScraper):
    name = "Probe RA"

    def fetch_events(self) -> Iterable[Event]:
        out = self._dump_following()
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "probe-ra.txt").write_text(out, encoding="utf-8")
        except OSError:
            pass
        return []

    def _dump_following(self) -> str:
        url = f"https://ra.co/profile/{SLUG}"
        try:
            html = requests.get(url, headers=BROWSER, timeout=25).text
        except requests.RequestException as exc:
            return f"FEHLER {exc}"
        m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
        if not m:
            return "kein __NEXT_DATA__"
        try:
            data = json.loads(m.group(1))
        except ValueError:
            return "NEXT_DATA nicht parsebar"

        # RA uses Apollo; followed entities are objects like "Artist:123",
        # "Promoter:456", "Club:789", "Label:...". Collect those + anything with
        # a "following" connection.
        apollo = _find_key(data, "apolloState") or {}
        if not isinstance(apollo, dict):
            apollo = {}
        types = {}
        entities = []
        for key, val in apollo.items():
            t = key.split(":")[0]
            types[t] = types.get(t, 0) + 1
            if isinstance(val, dict) and t in (
                    "Artist", "Promoter", "Club", "Label", "Venue"):
                name = val.get("name") or val.get("title") or ""
                slug = val.get("contentUrl") or val.get("slug") or ""
                if name:
                    entities.append(f"{t}: {name}  [{slug}]")

        foll = [k for k in _flat_keys(data) if "follow" in k.lower()][:20]
        return (f"profile {url} | apollo-objekte: {sum(types.values())}\n"
                f"Typen: {types}\n"
                f"following-Felder im NEXT_DATA: {foll}\n\n"
                f"--- Entitäten (max 60) ---\n" + "\n".join(sorted(set(entities))[:60]))


def _find_key(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return obj[key]
        for v in obj.values():
            r = _find_key(v, key)
            if r is not None:
                return r
    elif isinstance(obj, list):
        for v in obj:
            r = _find_key(v, key)
            if r is not None:
                return r
    return None


def _flat_keys(obj, prefix=""):
    out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            out.append(k)
            out += _flat_keys(v, k)
    elif isinstance(obj, list):
        for v in obj[:3]:
            out += _flat_keys(v, prefix)
    return out
