"""Resident Advisor -- events from the promoters/clubs/artists you follow.

RA's "following" list is login-gated, so it can't be auto-synced; instead the
followed entities are listed in ``RA_FOLLOWS`` (add/remove a line to change
them). All their upcoming Berlin events are pulled via RA's open GraphQL API
and shown as one source "Resident Advisor". Category Party; genre is Kink/Queer
(per-entity override in ``GENRE_OVERRIDE``, else inferred, else the default).
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Iterable

import requests

from .base import BaseScraper, Event, parse_datetime

SOURCE = "Resident Advisor"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

# (type, id-or-slug) -- followed RA entities. Add a line to follow more.
RA_FOLLOWS = [
    ("club", "28354"), ("club", "98993"),
    ("promoter", "82597"), ("promoter", "71007"), ("promoter", "80958"),
    ("promoter", "79889"), ("artist", "horsemeatdisco"),
    ("promoter", "84128"),  # Klub Verboten
    ("promoter", "167895"), ("promoter", "137536"), ("promoter", "169756"),
    ("promoter", "109496"), ("promoter", "112980"), ("promoter", "119317"),
    ("promoter", "52590"), ("promoter", "68628"), ("promoter", "110626"),
    ("promoter", "90524"),
]

# Genre per entity id/slug ("Kink"/"Queer"/"Kultur"/"Polit").
GENRE_OVERRIDE = {
    "28354": "Kultur",   # ://about blank
    "98993": "Kultur",   # Beate Uwe
    "82597": "Kink",     # BOAR Berlin
    "71007": "Queer",    # Buttons
    "80958": "Kink",     # Gegen
    "79889": "Queer",    # HE.SHE.THEY.
    "167895": "Queer",   # Lecken3000
    "137536": "Queer",   # Magic Dyke*
    "169756": "Queer",   # Mala Junta
    "109496": "Queer",   # PiepShow Berlin
    "112980": "Queer",   # Pinky Promise
    "119317": "Queer",   # Polyamor
    "52590": "Kink",     # Pornceptual
    "68628": "Polit",    # Room 4 Resistance
    "110626": "Queer",   # Supernature
    "90524": "Queer",    # ¡MASH-UP! Multigender
    "84128": "Kink",     # Klub Verboten
}
DEFAULT_GENRE = "Queer"
KINK_KW = ("kink", "fetish", "fetisch", "bdsm", "darkroom", "dark room", "cruise",
           "cruising", "naked", "nackt", "rubber", "latex", "leather", "hard",
           "play party", "dungeon", "pup", "bondage")
QUEER_KW = ("queer", "gay", "schwul", "lesbian", "lesb", "trans", "flinta", "drag",
            "homo", "dyke", "fag", "lgbt", "non-binary", "nonbinary", "sappho")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json",
    "Content-Type": "application/json",
    "Referer": "https://ra.co/",
    "Origin": "https://ra.co",
    "ra-content-language": "en",
}

_EVENT_FIELDS = ("id title date startTime endTime contentUrl flyerFront content "
                 "images{ filename } venue{ name area{ name } }")
QUERIES = {
    "promoter": "query($id:ID!){ promoter(id:$id){ name events(type:LATEST,"
                f" limit:40){{ {_EVENT_FIELDS} }} }} }}",
    "club": "query($id:ID!){ venue(id:$id){ name events(type:LATEST,"
            f" limit:40){{ {_EVENT_FIELDS} }} }} }}",
    "artist": "query($id:ID!){ artist(id:$id){ name events(type:LATEST,"
              f" limit:40){{ {_EVENT_FIELDS} }} }} }}",
}
NODE_KEY = {"club": "venue"}  # GraphQL field name differs from our label


def _genre(entity_id: str, text: str) -> str:
    if entity_id in GENRE_OVERRIDE:
        return GENRE_OVERRIDE[entity_id]
    low = text.lower()
    if any(k in low for k in KINK_KW):
        return "Kink"
    if any(k in low for k in QUEER_KW):
        return "Queer"
    return DEFAULT_GENRE


def _ra_image(e: dict) -> str | None:
    flyer = e.get("flyerFront")
    if isinstance(flyer, str) and flyer.startswith("http"):
        return flyer
    for img in (e.get("images") or []):
        fn = (img or {}).get("filename")
        if isinstance(fn, str) and fn:
            return fn if fn.startswith("http") else ("https://images.ra.co/" + fn.lstrip("/"))
    return None


def _ra_text(content) -> str | None:
    if not isinstance(content, str) or not content.strip():
        return None
    text = re.sub(r"<[^>]+>", " ", content)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500] or None


class ResidentAdvisorScraper(BaseScraper):
    name = SOURCE

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(HEADERS)
        events: list[Event] = []
        seen: set[str] = set()
        report: list[str] = []

        for kind, ident in RA_FOLLOWS:
            ent_id = ident
            if kind == "artist" and not ident.isdigit():
                ent_id = self._resolve_artist(session, ident) or ""
                if not ent_id:
                    report.append(f"{kind}/{ident}: ID nicht auflösbar")
                    continue
            name, raw, err = self._query(session, kind, ent_id)
            if err:
                report.append(f"{kind}/{ident} ({name}): {err}")
                continue
            kept = 0
            for e in raw:
                ev = self._build(e, ident)
                if ev and ev._ra_id not in seen:
                    seen.add(ev._ra_id)
                    events.append(ev)
                    kept += 1
            flyers = sum(1 for e in raw if e.get("flyerFront"))
            imgs = sum(1 for e in raw if e.get("images"))
            conts = sum(1 for e in raw if e.get("content"))
            report.append(f"{kind}/{ident} ({name}): {len(raw)} -> {kept} Berlin "
                          f"| flyer={flyers} images={imgs} content={conts}")

        with_img = sum(1 for e in events if e.image_url)
        with_desc = sum(1 for e in events if e.description)
        self._dump(f"Events gesamt: {len(events)} | mit Bild: {with_img} | "
                   f"mit Beschreibung: {with_desc}\n" + "\n".join(report) +
                   f"\nArtist-Auflösung: {getattr(self, '_artist_diag', '-')}")
        return events

    def _query(self, session, kind, ent_id):
        try:
            r = session.post("https://ra.co/graphql", timeout=25,
                             data=json.dumps({"query": QUERIES[kind],
                                              "variables": {"id": ent_id}}))
            data = r.json()
        except (requests.RequestException, ValueError) as exc:
            return "?", [], f"FEHLER {exc}"
        if data.get("errors"):
            return "?", [], str(data["errors"])[:120]
        node = (data.get("data") or {}).get(NODE_KEY.get(kind, kind)) or {}
        return node.get("name", "?"), node.get("events") or [], None

    def _build(self, e: dict, entity_id: str) -> Event | None:
        venue = e.get("venue") or {}
        area = ((venue.get("area") or {}).get("name") or "").strip()
        if area and "berlin" not in area.lower():
            return None  # keep Berlin and TBA (empty), drop other cities
        start = parse_datetime(e.get("startTime") or e.get("date"))
        title = (e.get("title") or "").strip()
        if not start or not title:
            return None
        path = e.get("contentUrl") or ""
        url = ("https://ra.co" + path) if path.startswith("/") else (path or "https://ra.co")
        vname = venue.get("name")
        ev = Event(
            title=title,
            start=start.replace(tzinfo=None),
            source_url=url,
            source_name=SOURCE,
            location=(vname + ", Berlin") if vname else "Berlin",
            image_url=_ra_image(e),
            description=_ra_text(e.get("content")),
            tags=["Party"],
            genre=_genre(entity_id, f"{title} {vname or ''}"),
        )
        ev._ra_id = str(e.get("id") or url)
        return ev

    def _resolve_artist(self, session, slug: str) -> str | None:
        try:
            r = requests.get(f"https://ra.co/dj/{slug}", headers={
                "User-Agent": HEADERS["User-Agent"],
                "Accept": "text/html"}, timeout=25)
            html = r.text
        except requests.RequestException as exc:
            self._artist_diag = f"FEHLER {exc}"
            return None
        for pat in (r'"Artist:(\d+)"', r'\\"Artist:(\d+)\\"',
                    r'"artist".{0,40}?"id":"(\d+)"', r'/dj/[^"]*"\s*,\s*"id":"(\d+)"'):
            m = re.search(pat, html)
            if m:
                return m.group(1)
        self._artist_diag = f"status={r.status_code} len={len(html)} keine ID"
        return None

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "resident-advisor.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
