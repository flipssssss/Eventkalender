"""Arthouse cinema programmes via berlin.de.

berlin.de exposes a per-cinema page (``kinodetail.php/<id>``) listing every
film with a "Tag | Zeit" table. We read the five wanted cinemas, emit one raw
event per single screening (film + day + time + cinema), and a grouping step in
aggregate.py collapses them into one event per film per day with all showings.

All cinema events are source ``Kinoprogramm``, category Kino, genre Kultur.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

KINO_SOURCE = "Kinoprogramm"
BASE = "https://www.berlin.de"
DETAIL = BASE + "/kino/_bin/kinodetail.php/{id}"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

# Friendly name -> berlin.de cinema id (the five wanted arthouse cinemas).
CINEMAS = {
    "Sputnik": "31975",
    "Lichtblick": "30219",
    "Kino Zukunft": "35972",
    "Ladenkino": "35211",
    "Wolf Kino": "38197",
}

# Fixed addresses (for the map + Bezirk and the detail view).
CINEMA_ADDR = {
    "Sputnik": "Hasenheide 54, 10967 Berlin",
    "Lichtblick": "Kastanienallee 77, 10435 Berlin",
    "Kino Zukunft": "Laskerstraße 5, 10245 Berlin",
    "Ladenkino": "Gärtnerstraße 19, 10245 Berlin",
    "Wolf Kino": "Weserstraße 59, 12045 Berlin",
}
OG_META_RE = re.compile(
    r'<meta\b[^>]*\b(?:property|name)=["\'](?:og:image|twitter:image)["\'][^>]*>', re.I)
CONTENT_RE = re.compile(r'content=["\']([^"\']+)', re.I)
POSTER_IMG_RE = re.compile(
    r'<img\b[^>]*\bsrc=["\']([^"\']*(?:image_assets|/binaries/)[^"\']*)', re.I)


def _poster(html: str) -> str | None:
    m = OG_META_RE.search(html)
    if m:
        c = CONTENT_RE.search(m.group(0))
        if c:
            return c.group(1)
    m = POSTER_IMG_RE.search(html)
    return m.group(1) if m else None

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})")
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})\s*(?:\(([^)]+)\))?")


class BerlinKinoScraper(BaseScraper):
    name = KINO_SOURCE

    def __init__(self, horizon_days: int = 14, write_debug: bool = True):
        self.horizon_days = horizon_days
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        today = _dt.date.today()
        horizon = today + _dt.timedelta(days=self.horizon_days)
        events: list[Event] = []
        report = []
        for cinema, cid in CINEMAS.items():
            try:
                html = self.get(DETAIL.format(id=cid), headers=BROWSER).text
            except Exception as exc:  # noqa: BLE001
                report.append(f"{cinema}: FEHLER {exc}")
                continue
            n = self._parse_cinema(html, cinema, today, horizon, events)
            report.append(f"{cinema}: {n} Vorstellungen")

        imgs = self._add_images(events)
        self._dump(f"Vorstellungen gesamt: {len(events)} | Filmbilder: {imgs}\n"
                   + "\n".join(report) + getattr(self, "_img_diag", ""))
        return events

    def _add_images(self, events: list[Event]) -> int:
        """Fetch each unique film page once and read its poster image."""
        cache: dict[str, str] = {}
        urls = [u for u in dict.fromkeys(
            e.source_url for e in events if (e.source_url or "").startswith("http"))]
        self._img_diag = ""
        for i, url in enumerate(urls[:150]):
            try:
                html = self.get(url, headers=BROWSER).text
            except Exception:  # noqa: BLE001
                continue
            if i == 0:
                tag = OG_META_RE.search(html)
                self._img_diag = (f"\n1. Film {url}\n  'og:image' im html: "
                                  f"{'og:image' in html} | meta: "
                                  f"{tag.group(0)[:140] if tag else '-'}")
            img = _poster(html)
            if img:
                cache[url] = img if img.startswith("http") else (BASE + img)
        for e in events:
            if e.source_url in cache:
                e.image_url = cache[e.source_url]
        return len(cache)

    def _parse_cinema(self, html, cinema, today, horizon, out) -> int:
        soup = BeautifulSoup(html, "html.parser")
        count = 0
        for tbl in soup.select("table.table--compact"):
            link = tbl.find_previous(
                lambda t: t.name == "a" and "filmdetail" in (t.get("href") or ""))
            if not link:
                continue
            title = re.sub(r"\s+", " ", link.get_text(" ")).strip()
            url = link.get("href") or ""
            if url.startswith("/"):
                url = BASE + url
            for tr in tbl.select("tbody tr"):
                tds = tr.find_all("td")
                if len(tds) < 2:
                    continue
                dm = DATE_RE.search(tds[0].get_text(" "))
                if not dm:
                    continue
                day, mon, yr = int(dm.group(1)), int(dm.group(2)), int(dm.group(3))
                yr += 2000 if yr < 100 else 0
                try:
                    date = _dt.date(yr, mon, day)
                except ValueError:
                    continue
                if not (today <= date <= horizon):
                    continue
                for tm in TIME_RE.finditer(tds[1].get_text(" ")):
                    hh, mm = int(tm.group(1)), int(tm.group(2))
                    note = (tm.group(3) or "").strip() or None
                    out.append(Event(
                        title=title[:160],
                        start=_dt.datetime(yr, mon, day, hh, mm),
                        source_url=url or DETAIL.format(id=CINEMAS[cinema]),
                        source_name=KINO_SOURCE,
                        location=cinema,
                        subcategory=note,   # version (OmU/OV) for this screening
                        tags=["Kino"],
                    ))
                    count += 1
        return count

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "kinoprogramm.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass


# ---- grouping: one event per film per day, with all screenings -------------

_VERSION = (r"omu|omeu|o\.?m\.?e?\.?u|ov|engl|english|deutsch|untertitel|sneak|"
            r"preview|3d|2d|digital|35mm|70mm")


def _norm_title(title: str) -> str:
    t = re.sub(r"\([^)]*\)", " ", title.lower())
    t = re.sub(r"[^a-z0-9äöüß ]", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def _display_title(title: str) -> str:
    return re.sub(rf"\s*\(\s*(?:{_VERSION})[^)]*\)\s*$", "", title,
                  flags=re.IGNORECASE).strip()


def group_screenings(events: list[Event]) -> list[Event]:
    """Collapse Kinoprogramm screenings into one event per film per day."""
    cinema = [e for e in events if e.source_name == KINO_SOURCE]
    if not cinema:
        return events
    others = [e for e in events if e.source_name != KINO_SOURCE]

    groups: dict[tuple, list[Event]] = {}
    for e in cinema:
        groups.setdefault((_norm_title(e.title), e.start.date()), []).append(e)

    grouped: list[Event] = []
    for showings in groups.values():
        showings.sort(key=lambda e: e.start)
        first = showings[0]
        cinemas = sorted({s.location for s in showings})
        single = len(cinemas) == 1
        ev = Event(
            title=_display_title(first.title)[:140] or first.title[:140],
            start=first.start,            # earliest screening -> sort position
            source_url=first.source_url,
            source_name=KINO_SOURCE,
            location=cinemas[0] if single else f"{len(cinemas)} Kinos",
            # Single cinema -> address so it lands on the map; several cinemas
            # carry their addresses per screening instead.
            address=CINEMA_ADDR.get(cinemas[0]) if single else None,
            image_url=next((s.image_url for s in showings if s.image_url), None),
            time_known=False,             # date line shows the date only
            tags=["Kino"],
        )
        ev.showings = [{
            "time": s.start.strftime("%H:%M"),
            "cinema": s.location,
            "address": CINEMA_ADDR.get(s.location),
            "url": s.source_url,
            "note": s.subcategory,
        } for s in showings]
        grouped.append(ev)
    return others + grouped
