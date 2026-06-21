"""Wochenmarkt & Flohmarkt Berlin (wochenmarkt-flohmarkt.de).

Die Seite hat kein JSON-LD, bettet aber pro Markt-Termin einen Google-Calendar-
"Zum Kalender hinzufügen"-Link ein (``action=TEMPLATE``). In dessen Query-String
stecken Titel (``text``), Datum/Uhrzeit (``dates``), Ort (``location``) und eine
HTML-Beschreibung (``details``). Genau die lesen wir aus -> saubere, datierte
Markt-/Flohmarkt-Termine (Kategorie "Markt").
"""

from __future__ import annotations

import datetime as _dt
import html as _html
import re
from typing import Iterable
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

BASE = "https://www.wochenmarkt-flohmarkt.de"
_DT = re.compile(r"(\d{8})T(\d{6})")
_IMG = re.compile(r'src="(https?://[^"]+\.(?:jpg|jpeg|png|webp))"', re.I)


def _parse_dt(value: str):
    m = _DT.match(value or "")
    if not m:
        return None
    d, t = m.group(1), m.group(2)
    try:
        return _dt.datetime(int(d[:4]), int(d[4:6]), int(d[6:8]),
                            int(t[:2]), int(t[2:4]), int(t[4:6]))
    except ValueError:
        return None


def _clean(htmltext: str):
    if not htmltext:
        return None
    txt = _html.unescape(htmltext)
    txt = BeautifulSoup(txt, "html.parser").get_text(" ")
    txt = txt.replace("­", "")
    txt = re.sub(r"\s+", " ", txt).strip()
    return txt or None


class MaerkteScraper(BaseScraper):
    name = "Wochenmarkt & Flohmarkt"

    def fetch_events(self) -> Iterable[Event]:
        try:
            html = self.get(BASE).text
        except Exception:  # noqa: BLE001
            return []
        soup = BeautifulSoup(html, "html.parser")
        events: list[Event] = []
        seen: set[str] = set()
        for a in soup.select('a[href*="action=TEMPLATE"]'):
            qs = parse_qs(urlparse(a.get("href", "")).query)
            title = (qs.get("text") or [""])[0].strip()
            dates = (qs.get("dates") or [""])[0]
            if not title or "/" not in dates:
                continue
            s_raw, e_raw = dates.split("/", 1)
            start = _parse_dt(s_raw)
            if not start:
                continue
            end = _parse_dt(e_raw)
            # Ganztags-Muster (00:00:00 .. 23:59:59) -> nur Datum anzeigen.
            allday = s_raw.endswith("T000000") and e_raw.endswith(("T235959", "T000000"))
            if allday:
                end = None
            elif end and end <= start:
                end = None
            details = (qs.get("details") or [""])[0]
            img = _IMG.search(details)
            key = title + "|" + start.isoformat()
            if key in seen:
                continue
            seen.add(key)
            events.append(Event(
                title=title[:140],
                start=start,
                end=end,
                source_url=BASE,
                source_name=self.name,
                location=(qs.get("location") or [""])[0].strip() or None,
                description=_clean(details),
                image_url=img.group(1) if img else None,
                tags=["Markt"],
                time_known=not allday,
            ))
        return events
