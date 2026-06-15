"""kulturdaten.berlin -- öffentliche Kultur-API (Lesen ohne Token).

Wir holen die Events der nächsten Tage, lösen die Kategorie über die
Attraktion auf und behalten nur die gewünschten Kategorien (Bühne, Musik,
Tanz, Festivals, Ausstellungen/Kunst). Weil Ausstellungen pro Tag ein Event
erzeugen, wird pro Attraktion nur der früheste Termin behalten.
"""

from __future__ import annotations

import datetime as _dt
from typing import Iterable

import requests

from .base import BaseScraper, Event, parse_datetime

BASE = "https://api-v2.kulturdaten.berlin"
HEADERS = {
    "User-Agent": "EventkalenderBot/1.0 (+https://github.com/flipssssss/eventkalender)",
    "Accept": "application/json",
}

# Gewählte kulturdaten-Kategorien -> unser Tag.
INCLUDE = {
    "Music": "Konzert",
    "Stages": "Theater",
    "Dance": "Party",
    "Festivals": "Party",
    "Exhibitions": "Ausstellung",
    "Art": "Ausstellung",
}


def _de(label) -> str | None:
    if isinstance(label, dict):
        return (label.get("de") or label.get("en") or "").strip() or None
    return None


class KulturdatenScraper(BaseScraper):
    name = "kulturdaten.berlin"

    def __init__(self, days: int = 14, include: dict | None = None):
        self.days = days
        self.include = include or INCLUDE

    def fetch_events(self) -> Iterable[Event]:
        session = requests.Session()
        session.headers.update(HEADERS)

        attr = self._attraction_map(session)
        raw = self._events_window(session)

        built: list[tuple[str, Event]] = []
        for e in raw:
            pair = self._build(e, attr)
            if pair:
                built.append(pair)

        # Pro Attraktion nur den frühesten Termin behalten (gegen tägliche
        # Wiederholung von Ausstellungen/Reihen).
        built.sort(key=lambda x: x[1].start)
        seen: set[str] = set()
        out: list[Event] = []
        for aid, ev in built:
            if aid in seen:
                continue
            seen.add(aid)
            out.append(ev)
        return out

    # -- API-Helfer ------------------------------------------------------

    def _get(self, session, path) -> dict:
        try:
            r = session.get(BASE + path, timeout=30)
            return r.json().get("data", {}) if r.status_code == 200 else {}
        except Exception:  # noqa: BLE001
            return {}

    def _attraction_map(self, session) -> dict:
        """id -> {cat, desc, link} über alle Attraktionen."""
        attr, page, empty = {}, 1, 0
        while page <= 140:
            d = self._get(session, f"/api/attractions?pageSize=200&page={page}")
            items = d.get("attractions") or []
            if not items:
                empty += 1
                if empty > 3:
                    break
                page += 1
                continue
            for a in items:
                tags = [t.replace("attraction.category.", "") for t in a.get("tags", [])]
                link = a.get("website")
                ext = a.get("externalLinks") or []
                if not link and ext:
                    link = ext[0].get("url")
                if link and not link.startswith("http"):
                    link = "https://" + link.lstrip("/")
                attr[a.get("identifier")] = {
                    "cat": tags[0] if tags else None,
                    "desc": _de(a.get("description")),
                    "link": link,
                }
            if page * 200 >= (d.get("totalCount") or 0):
                break
            page += 1
        return attr

    def _events_window(self, session) -> list:
        today = _dt.date.today()
        end = today + _dt.timedelta(days=self.days)
        events, page = [], 1
        while page <= 40:
            d = self._get(
                session,
                f"/api/events?startDate={today}&endDate={end}&pageSize=200&page={page}",
            )
            batch = d.get("events") or []
            events.extend(batch)
            if not batch or page * 200 >= (d.get("totalCount") or 0):
                break
            page += 1
        return events

    # -- Bauen -----------------------------------------------------------

    def _build(self, e: dict, attr: dict):
        refs = e.get("attractions") or []
        if not refs:
            return None
        aid = refs[0].get("referenceId")
        info = attr.get(aid) or {}
        cat = info.get("cat")
        if cat not in self.include:
            return None

        title = _de(refs[0].get("referenceLabel"))
        if not title:
            return None

        sch = e.get("schedule") or {}
        time = sch.get("startTime") or "00:00:00"
        start = parse_datetime(f"{sch.get('startDate')} {time}")
        if not start:
            return None
        time_known = time not in ("00:00:00", "", None)

        loc = e.get("locations") or []
        venue = _de(loc[0].get("referenceLabel")) if loc else None

        desc = info.get("desc")
        if (e.get("admission") or {}).get("ticketType") == "ticketType.freeOfCharge":
            desc = ("Eintritt frei. " + (desc or "")).strip()

        return aid, Event(
            title=title,
            start=start,
            source_url=info.get("link") or "https://www.kulturdaten.berlin",
            source_name=self.name,
            location=venue,
            description=desc,
            tags=[self.include[cat]],
            time_known=time_known,
            subcategory=cat,  # kulturdaten-Kategorie (Music/Exhibitions/…)
        )
