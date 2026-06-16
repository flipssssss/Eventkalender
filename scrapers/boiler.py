"""Boiler (queere Party-Location, Berlin) -- WordPress events.

The iCal export returned HTML, so we try The Events Calendar REST API
(``/wp-json/tribe/events/v1/events``) and parse it when available. If that is
unavailable we dump the page's event markup for diagnosis. Category Party,
genre Queer (forced in genres.py).
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
import re
from typing import Iterable

import requests
from bs4 import BeautifulSoup

from .base import BaseScraper, Event, parse_datetime

BASE = "https://boiler-berlin.de"
REST = BASE + "/wp-json/tribe/events/v1/events?per_page=50&start_date=now"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/html, */*",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


class BoilerScraper(BaseScraper):
    name = "Boiler Berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(BROWSER)

        # Modern Events Calendar (MEC) exposes an iCal feed.
        events, ical_note = self._from_ical(session)
        if events:
            self._dump(f"iCal ok -> {len(events)} Events\n" +
                       "\n".join(f"  {e.start} | {e.title}" for e in events[:20]))
            return events

        _, rest_note = self._from_rest(session)
        html_note = self._diagnose_html(session)
        self._dump(f"iCal: {ical_note}\nREST: {rest_note}\n\n{html_note}")
        return events

    def _from_ical(self, session) -> tuple[list[Event], str]:
        from icalendar import Calendar
        for url in (BASE + "/?mec-ical-feed=1", BASE + "/events/?ical=1",
                    BASE + "/?ical=1"):
            try:
                r = session.get(url, timeout=25)
            except requests.RequestException as exc:
                return [], f"FEHLER {exc}"
            if r.status_code != 200 or "BEGIN:VCALENDAR" not in r.text[:200]:
                continue
            events = []
            for comp in Calendar.from_ical(r.content).walk("VEVENT"):
                start = parse_datetime(str(comp.get("dtstart").dt)) \
                    if comp.get("dtstart") else None
                title = str(comp.get("summary") or "").strip()
                if not start or not title:
                    continue
                events.append(Event(
                    title=title[:140],
                    start=start.replace(tzinfo=None),
                    source_url=str(comp.get("url") or url),
                    source_name=self.name,
                    location=str(comp.get("location") or "") or None,
                    description=str(comp.get("description") or "") or None,
                    tags=["Party"],
                ))
            return events, f"{url} -> {len(events)}"
        return [], "kein iCal-Feed gefunden"

    def _from_rest(self, session) -> tuple[list[Event], str]:
        try:
            r = session.get(REST, timeout=25)
        except requests.RequestException as exc:
            return [], f"FEHLER {exc}"
        if r.status_code != 200 or "application/json" not in r.headers.get("content-type", ""):
            return [], f"status={r.status_code} type={r.headers.get('content-type')}"
        try:
            data = r.json()
        except ValueError:
            return [], "kein JSON"
        events = []
        for e in data.get("events") or []:
            start = parse_datetime(e.get("start_date"))
            title = (e.get("title") or "").strip()
            if not start or not title:
                continue
            venue = e.get("venue") or {}
            addr = ", ".join(str(venue[k]).strip() for k in ("address", "zip", "city")
                             if venue.get(k))
            img = e.get("image") or {}
            events.append(Event(
                title=re.sub(r"\s+", " ", title)[:140],
                start=start.replace(tzinfo=None),
                end=(parse_datetime(e.get("end_date")) or start).replace(tzinfo=None),
                source_url=e.get("url") or BASE,
                source_name=self.name,
                location=venue.get("venue"),
                address=addr or None,
                description=BeautifulSoup(e.get("description") or "", "html.parser")
                .get_text(" ").strip()[:400] or None,
                image_url=img.get("url") if isinstance(img, dict) else None,
                tags=["Party"],
            ))
        return events, f"{len(events)} Events"

    def _diagnose_html(self, session) -> str:
        try:
            html = session.get(BASE + "/en/", timeout=25).text
        except requests.RequestException as exc:
            return f"HTML FEHLER {exc}"
        soup = BeautifulSoup(html, "html.parser")
        counts = {sel: len(soup.select(sel)) for sel in (
            ".mec-event-article", "[class*=mec-event]", ".mec-event-title",
            "[class*=mec-date]", "[class*=mec-start]")}
        node = (soup.select_one(".mec-event-article")
                or soup.select_one("[class*=mec-event]"))
        sample = node.prettify()[:1800] if node else "(kein mec-event gefunden)"
        return f"Selektoren: {counts}\n--- MEC-BEISPIEL ---\n{sample}"

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "boiler.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
