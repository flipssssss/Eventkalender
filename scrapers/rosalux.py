"""Rosa-Luxemburg-Stiftung -- politische Vorträge/Diskussionen.

The events page (rosalux.de/veranstaltungen) is server-rendered HTML (no
JSON-LD): each event is a ``section.elasticsearch__result`` carrying a
``data-ts`` start timestamp (ms), with the title, city and type inside a
``.teaser--event``. Foundation events are nationwide, so only Berlin ones are
kept. All kept events are category Vortrag; genre Polit is set in
scrapers/genres.py.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Event
from . import metacache

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/Berlin")
except Exception:  # noqa: BLE001
    _TZ = None

BASE = "https://www.rosalux.de"
URL = BASE + "/veranstaltungen"
MAX_PAGES = 8
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
TIME_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")
OG_DESC_RE = re.compile(
    r'<meta\b[^>]*\b(?:property|name)=["\'](?:og:description|description)["\'][^>]*>',
    re.I)
CONTENT_RE = re.compile(r'content=["\']([^"\']*)', re.I)

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}


class RosaLuxScraper(BaseScraper):
    name = "Rosa-Luxemburg-Stiftung"

    def __init__(self, city: str = "Berlin", write_debug: bool = True):
        self.city = city
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(URL, headers=BROWSER).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        secs, pages, pager_links = self._collect(html)
        events: list[Event] = []
        seen: set[tuple] = set()
        other_city = 0
        for sec in secs:
            ev, city = self._build(sec)
            if ev is None:
                continue
            if self.city and self.city.lower() not in (city or "").lower():
                other_city += 1
                continue
            key = (ev.source_url, ev.start)
            if key in seen:
                continue
            seen.add(key)
            events.append(ev)
        self._add_descriptions(events)
        last = max((e.start for e in events), default=None)
        self._dump(f"Seiten: {len(pages)} | Teaser: {len(secs)} | "
                   f"{self.city}: {len(events)} | andere Städte: {other_city} | "
                   f"mit Beschreibung: {sum(1 for e in events if e.description)} | "
                   f"letzter Termin: {last}\n"
                   "Gelesene Seiten:\n" + "\n".join(f"  {u}" for u in pages) +
                   "\nBlätter-Kandidaten auf Seite 1:\n" +
                   "\n".join(f"  {u}" for u in pager_links[:20]) + "\n" +
                   "\n".join(f"  {e.start} | {e.location} | {e.title}"
                             for e in events[:60]))
        return events

    def _collect(self, first_html: str) -> tuple[list, list[str], list[str]]:
        """Teasers of the first listing page plus its follow-up pages.

        The listing only shows the current batch (about a month, all cities),
        so without paging Berlin events end after a few weeks. Pager links are
        recognised generically (rel=next, pagination containers, or
        cb_elasticsearch ``page`` parameters) because the markup is not
        documented; paging stops when a page brings no new teasers."""
        soup = BeautifulSoup(first_html, "html.parser")
        secs = list(soup.select("section.elasticsearch__result"))
        pages = [URL]
        pager_links = self._pager_links(soup)
        seen_teasers = {self._teaser_key(s) for s in secs}
        queue = list(pager_links)
        visited = {URL}
        while queue and len(pages) < MAX_PAGES:
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                page = BeautifulSoup(self.get(url, headers=BROWSER).text,
                                     "html.parser")
            except Exception:  # noqa: BLE001
                continue
            new = [s for s in page.select("section.elasticsearch__result")
                   if self._teaser_key(s) not in seen_teasers]
            pages.append(url)
            if not new:
                continue
            seen_teasers.update(self._teaser_key(s) for s in new)
            secs.extend(new)
            queue.extend(u for u in self._pager_links(page)
                         if u not in visited and u not in queue)
        return secs, pages, pager_links

    @staticmethod
    def _teaser_key(sec) -> tuple:
        link = sec.select_one("a.teaser__link")
        return ((link.get("href") if link else None), sec.get("data-ts"))

    @staticmethod
    def _pager_links(soup) -> list[str]:
        out: list[str] = []
        for a in soup.select("a[href]"):
            href = a.get("href") or ""
            if href.startswith("#") or href.startswith("javascript"):
                continue
            classes = " ".join(a.get("class") or [])
            parent_cls = " ".join(
                " ".join(p.get("class") or []) for p in a.parents
                if getattr(p, "get", None) and p.name in ("nav", "ul", "div", "li"))
            rel = " ".join(a.get("rel") or [])
            low = href.lower()
            is_pager = (
                "next" in rel
                or "pagination" in parent_cls.lower() or "pager" in parent_cls.lower()
                or "next" in classes.lower()
                or (("cbelasticsearch" in low or "veranstaltungen" in low)
                    and re.search(r"(%5b|\[)page(%5d|\])=\d+|[?&]page=\d+", low))
            )
            if not is_pager:
                continue
            url = urljoin(URL, href).split("#", 1)[0]
            if not url.startswith(BASE) or url == URL:
                continue
            if url not in out:
                out.append(url)
        return out

    def _add_descriptions(self, events) -> None:
        """Full description from each event's detail page (og:description),
        cached so every page is fetched only once. Falls back to the teaser
        text already set when no detail description is available."""
        for url in dict.fromkeys(
                e.source_url for e in events if (e.source_url or "").startswith("http")):
            if url == URL or metacache.get(url) is not None:
                continue
            desc = None
            try:
                html = self.get(url, headers=BROWSER).text
                m = OG_DESC_RE.search(html)
                if m:
                    c = CONTENT_RE.search(m.group(0))
                    if c and c.group(1).strip():
                        desc = c.group(1).strip()[:600]
            except Exception:  # noqa: BLE001
                continue
            metacache.put(url, None, desc)
        metacache.save()
        for e in events:
            c = metacache.get(e.source_url)
            if c and c["desc"]:
                e.description = c["desc"]

    def _build(self, sec) -> tuple[Event | None, str | None]:
        link = sec.select_one("a.teaser__link")
        title_el = sec.select_one(".teaser__title-text")
        ts = sec.get("data-ts")
        if not (link and title_el and ts and ts.isdigit()):
            return None, None
        start = self._start(ts)
        if not start:
            return None, None
        title = title_el.get_text(" ", strip=True)
        if not title:
            return None, None
        city = self._city(sec)
        desc_el = sec.select_one(".teaser__text")
        href = link.get("href") or ""
        return Event(
            title=title[:160],
            start=start,
            source_url=urljoin(BASE, href) if href else URL,
            source_name=self.name,
            location=city or "Berlin",
            description=(desc_el.get_text(" ", strip=True)[:500] if desc_el else None),
            tags=["Vortrag"],
        ), city

    @staticmethod
    def _start(ts: str) -> _dt.datetime | None:
        try:
            epoch = int(ts) / 1000
        except (TypeError, ValueError):
            return None
        if _TZ:
            return _dt.datetime.fromtimestamp(epoch, _TZ).replace(tzinfo=None)
        return _dt.datetime.utcfromtimestamp(epoch)

    @staticmethod
    def _city(sec) -> str | None:
        # The right-hand date group holds the city as a class-less span
        # (the date itself sits in .teaser__date-day/-month/-year spans).
        for sp in sec.select(".teaser__date-group--right > span"):
            if sp.select_one(".teaser__date-day"):
                continue
            txt = sp.get_text(" ", strip=True)
            if txt and not TIME_RE.search(txt):
                return txt
        return None

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "rosa-luxemburg-stiftung.txt").write_text(
                text, encoding="utf-8")
        except OSError:
            pass
