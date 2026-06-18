"""Planetarium Berlin -- Stiftung Planetarium Berlin (Drupal).

The /tickets page is a JS widget, but the taxonomy pages under
/veranstaltungsart/<art> are server-rendered catalogues of *programmes*
(e.g. "Cosmic Jazz"). Each programme teaser links to a detail page
/veranstaltungen/<slug> whose booking table lists the concrete showtimes
(Datum / Uhrzeit / Standort). We read the two wanted categories, follow
the programme links and emit one event per showtime.

No JSON-LD and no <time datetime> anywhere -- the table is plain text, so
we parse "DD.MM.YYYY" + "HH:MM Uhr" out of each table row.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

BASE = "https://www.planetarium.berlin"
SECTIONS = [
    ("/veranstaltungsart/highlights-konzerte", "Konzert"),
    ("/veranstaltungsart/hoerspiele-lesungen", "Vortrag"),
]
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

# Teaser links point to a programme page /veranstaltungen/<slug>.
DETAIL_RE = re.compile(r"^/veranstaltungen/[a-z0-9]", re.I)
DATE_RE = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})")
TIME_RE = re.compile(r"(\d{1,2})[:.](\d{2})\s*Uhr")
# Cap detail fetches so a run never explodes (there are ~30 programmes).
MAX_DETAILS = 45


class PlanetariumScraper(BaseScraper):
    name = "Planetarium Berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        # 1) Collect programme detail links per category (dedup, keep first
        #    category a programme appears under).
        detail: dict[str, str] = {}
        notes: list[str] = []
        for path, category in SECTIONS:
            try:
                html = self.get(BASE + path, headers=BROWSER).text
            except Exception as exc:  # noqa: BLE001
                notes.append(f"{path}: FEHLER {exc}")
                continue
            soup = BeautifulSoup(html, "html.parser")
            n = 0
            for a in soup.select("article.event-page a[href], article a[href]"):
                href = a.get("href", "")
                if DETAIL_RE.match(href):
                    url = urljoin(BASE, href.split("?")[0])
                    detail.setdefault(url, category)
                    n += 1
            notes.append(f"{path} ({category}): {n} Teaser")

        # 2) Visit each programme and emit one event per showtime.
        events: list[Event] = []
        seen: set[str] = set()
        for url, category in list(detail.items())[:MAX_DETAILS]:
            try:
                dhtml = self.get(url, headers=BROWSER).text
            except Exception:  # noqa: BLE001
                continue
            events.extend(self._detail(url, category, dhtml, seen))

        self._dump("Events: {}\n{}".format(
            len(events), "\n".join(notes
                                   + [f"Detailseiten: {len(detail)}"])))
        return events

    def _detail(self, url, category, html, seen) -> list[Event]:
        soup = BeautifulSoup(html, "html.parser")
        title = self._title(soup)
        if not title:
            return []
        img = soup.find("meta", property="og:image")
        image_url = img["content"] if img and img.get("content") else None

        out: list[Event] = []
        # Each booking row holds a date and a time in its text; the heading row
        # ("Datum Uhrzeit Standort Aktion") has no digits and is skipped.
        rows = soup.select(".event-date__table-cell")
        rowset = []
        seen_rows = set()
        for cell in rows:
            row = cell.find_parent(class_="row") or cell.parent
            if id(row) in seen_rows:
                continue
            seen_rows.add(id(row))
            rowset.append(row)
        for row in rowset:
            text = row.get_text(" ", strip=True)
            md = DATE_RE.search(text)
            if not md:
                continue
            mt = TIME_RE.search(text)
            day, mon, year = (int(md.group(1)), int(md.group(2)),
                              int(md.group(3)))
            hour = int(mt.group(1)) if mt else 0
            minute = int(mt.group(2)) if mt else 0
            try:
                start = _dt.datetime(year, mon, day, hour, minute)
            except ValueError:
                continue
            key = url + "|" + start.isoformat()
            if key in seen:
                continue
            seen.add(key)
            ev = Event(
                title=title[:160],
                start=start,
                source_url=url,
                source_name=self.name,
                location=self._standort(row) or "Planetarium Berlin",
                image_url=image_url,
                tags=[category],
                time_known=bool(mt),
            )
            out.append(ev)
        return out

    @staticmethod
    def _title(soup) -> str:
        h1 = soup.find("h1")
        if h1:
            t = re.sub(r"\s+", " ", h1.get_text(" ", strip=True)).strip()
            if t:
                return t
        og = soup.find("meta", property="og:title")
        if og and og.get("content"):
            return re.sub(r"\s*\|.*$", "", og["content"]).strip()
        return ""

    @staticmethod
    def _standort(row) -> str | None:
        # "Standort" cell: the one mentioning Planetarium/Zeiss, not a date/time.
        for cell in row.select(".event-date__table-cell"):
            t = cell.get_text(" ", strip=True)
            if t and not DATE_RE.search(t) and not TIME_RE.search(t) \
                    and ("planetarium" in t.lower() or "zeiss" in t.lower()
                         or "insulaner" in t.lower()):
                return re.sub(r"\s+", " ", t)[:80]
        return None

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "planetarium-berlin.txt").write_text(
                text, encoding="utf-8")
        except OSError:
            pass
