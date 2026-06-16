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

        # Modern Events Calendar list markup.
        events = self._from_mec(session)
        self._dump(f"iCal: {ical_note}\nMEC-HTML -> {len(events)} Events\n" +
                   "\n".join(f"  {e.start} | {e.title}" for e in events[:25]))
        return events

    def _from_mec(self, session) -> list[Event]:
        try:
            html = session.get(BASE + "/en/", timeout=25).text
        except requests.RequestException:
            return []
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()
        for art in soup.select(".mec-event-article"):
            cls = " ".join(art.get("class", []))
            ym = re.search(r"mec-toggle-(\d{4})(\d{2})", cls)
            day_el = art.select_one(".event-d")
            link = art.select_one(".mec-event-title a") or art.select_one(".mec-event-title")
            if not (ym and day_el and link):
                continue
            try:
                year, month = int(ym.group(1)), int(ym.group(2))
                day = int(re.sub(r"\D", "", day_el.get_text()) or 0)
                start = _dt.datetime(year, month, day, 17, 0)  # immer 17:00 Uhr
            except ValueError:
                continue
            title = re.sub(r"\s+", " ", link.get_text(" ")).strip()
            if not title:
                continue
            key = f"{title.lower()}|{start.date()}"
            if key in seen:
                continue
            seen.add(key)
            href = link.get("href") if link.name == "a" else None
            events.append(Event(
                title=title[:140],
                start=start,
                source_url=href or (BASE + "/en/"),
                source_name=self.name,
                location="Boiler",
                address="Mehringdamm 34, 10961 Berlin",
                description=None,
                tags=["Party"],
            ))
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

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "boiler.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
