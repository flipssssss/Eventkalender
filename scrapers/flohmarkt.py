"""Flohmärkte Berlin (berlin.de/special/shopping/flohmaerkte).

Ort, Adresse und Koordinaten kommen aus dem strukturierten ``rubric.geojson``-
Feed. Termine:
* Sondermärkte mit festem Datum -> aus dem Teaser-Feld ``teaser__meta``
  ("28. Juni 2026", "2. bis 4. Oktober 2026").
* Wiederkehrende Märkte -> von der Detailseite (``<dl>`` mit "Termine: Jeden
  Sonntag" + "Öffnungszeiten: 10 bis 18 Uhr"); daraus erzeugen wir die nächsten
  konkreten Termine.
"""

from __future__ import annotations

import calendar
import datetime as _dt
import json
import pathlib
import re
from datetime import timedelta
from typing import Iterable
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

BASE = "https://www.berlin.de"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
# Browser-User-Agent: berlin.de drosselt den Standard-Bot-UA deutlich härter.
BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}
PAGE = "https://www.berlin.de/special/shopping/flohmaerkte/bezirk/"
GEOJSON = "https://www.berlin.de/special/shopping/flohmaerkte/rubric.geojson"

MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
}
WEEKDAYS = {"montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3,
            "freitag": 4, "samstag": 5, "sonntag": 6}
ORDINALS = {"erste": 1, "ersten": 1, "1.": 1, "zweite": 2, "zweiten": 2,
            "2.": 2, "dritte": 3, "dritten": 3, "3.": 3, "vierte": 4,
            "vierten": 4, "4.": 4, "letzte": -1, "letzten": -1}
RECUR_DAYS = 35          # so weit in die Zukunft werden Termine erzeugt
MAX_DETAILS = 45         # Obergrenze für Detailseiten-Abrufe pro Lauf


def _dates(meta: str) -> list[_dt.datetime]:
    m = re.search(r"([A-Za-zäöüÄÖÜ]+)\s+(\d{4})", meta or "")
    if not m:
        return []
    mon = MONTHS.get(m.group(1).lower())
    if not mon:
        return []
    year = int(m.group(2))
    days = [int(d) for d in re.findall(r"\d{1,2}", meta[:m.start()])]
    if not days:
        return []
    if "bis" in meta[:m.start()].lower() and len(days) >= 2:
        days = list(range(days[0], days[-1] + 1))
    out = []
    for d in days:
        try:
            out.append(_dt.datetime(year, mon, d))
        except ValueError:
            pass
    return out


def _hours(text: str):
    m = re.search(r"(\d{1,2})(?:[:.](\d{2}))?\s*(?:bis|-|–|—|‐)\s*"
                  r"(\d{1,2})(?:[:.](\d{2}))?", text or "")
    if not m:
        return None
    return (int(m.group(1)), int(m.group(2) or 0),
            int(m.group(3)), int(m.group(4) or 0))


def _recurrence(termine: str):
    """(<wochentage>, <ordinals|None>) oder None."""
    low = (termine or "").lower()
    if "täglich" in low or "taeglich" in low:
        wds = list(range(7))
    else:
        wds = sorted({i for n, i in WEEKDAYS.items() if n in low})
    if not wds:
        return None
    ords = {v for k, v in ORDINALS.items() if k in low}
    return (wds, ords or None)


def _clean_addr(addr: str | None) -> str | None:
    if not addr:
        return None
    parts = [p.strip() for p in addr.split(",") if p.strip()]
    street = parts[0] if parts else ""
    plz = next((p for p in parts if re.fullmatch(r"\d{5}", p)), "")
    tail = (plz + " Berlin").strip() if plz else "Berlin"
    return ", ".join(x for x in [street, tail] if x) or addr


class FlohmarktScraper(BaseScraper):
    """Berliner Markt-Übersichten auf berlin.de (gleiche Struktur: Teaser +
    rubric.geojson + Detailseiten). Standardmäßig die Flohmärkte; mit anderen
    URLs auch z. B. die Öko-Wochenmärkte (/biomarkt/)."""

    name = "Flohmärkte Berlin"

    def __init__(self, name: str | None = None, page: str | None = None,
                 geojson: str | None = None):
        if name:
            self.name = name
        self.page = page or PAGE
        self.geojson_url = geojson or GEOJSON

    def fetch_events(self) -> Iterable[Event]:
        self._diag = {"teaser": 0, "dated": 0, "detail_ok": 0, "detail_err": 0,
                      "recur": 0, "no_geo": 0, "errors": [], "samples": []}
        geo = self._geojson()
        self._diag["geo"] = len(geo)
        try:
            soup = BeautifulSoup(self.get(self.page, headers=BROWSER).text,
                                 "html.parser")
        except Exception as exc:  # noqa: BLE001
            self._diag["errors"].append(f"PAGE {exc}")
            self._dump()
            return []

        today = _dt.date.today()
        events: list[Event] = []
        seen: set[str] = set()
        details_done = 0

        for art in soup.select("article.modul-teaser"):
            a = art.select_one("h3.title a, h3 a, .title a")
            if not a:
                continue
            self._diag["teaser"] += 1
            title = a.get_text(" ", strip=True)
            url = urljoin(BASE, a.get("href", ""))
            g = geo.get(url)
            meta_el = art.select_one(".teaser__meta, .text--meta")
            dated = _dates(meta_el.get_text(" ", strip=True) if meta_el else "")

            if dated:
                self._diag["dated"] += 1
                for d in dated:
                    self._add(events, seen, title, url, d, None, g, False)
                continue
            # Kein Datum: nur echte Märkte (im GeoJSON) -> Detailseite/Rhythmus.
            if not g:
                self._diag["no_geo"] += 1
                continue
            if details_done >= MAX_DETAILS:
                continue
            details_done += 1
            termine, oeff = self._detail(url)
            if len(self._diag["samples"]) < 8:
                self._diag["samples"].append(
                    f"{title[:24]} | termine={termine!r} | oeff={oeff!r}")
            recur = _recurrence(termine)
            if not recur:
                continue
            self._diag["recur"] += 1
            hrs = _hours(oeff)
            for d in self._occurrences(recur, today):
                self._add(events, seen, title, url, d, hrs, g, True)
        self._diag["events"] = len(events)
        self._dump()
        return events

    def _dump(self):
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
            lines = [f"{k}: {v}" for k, v in self._diag.items()
                     if k not in ("errors", "samples")]
            lines += ["SAMPLES:"] + self._diag.get("samples", [])
            lines += ["FEHLER:"] + self._diag.get("errors", [])
            (DEBUG_DIR / f"{slug}.txt").write_text("\n".join(lines), encoding="utf-8")
        except OSError:
            pass

    def _geojson(self) -> dict:
        geo: dict[str, dict] = {}
        try:
            data = json.loads(self.get(self.geojson_url, headers=BROWSER).text)
            for f in data.get("features", []):
                p = f.get("properties") or {}
                url = p.get("url")
                if not url:
                    continue
                c = (f.get("geometry") or {}).get("coordinates") or [None, None]
                geo[url] = {"address": p.get("address"),
                            "description": p.get("description"),
                            "lat": c[1], "lng": c[0]}
        except Exception:  # noqa: BLE001
            pass
        return geo

    def _detail(self, url: str):
        try:
            soup = BeautifulSoup(self.get(url, headers=BROWSER).text, "html.parser")
            self._diag["detail_ok"] += 1
        except Exception as exc:  # noqa: BLE001
            self._diag["detail_err"] += 1
            if len(self._diag["errors"]) < 5:
                self._diag["errors"].append(f"DETAIL {exc}")
            return None, None
        info: dict[str, str] = {}
        for dl in soup.select("dl"):
            dts = dl.find_all("dt")
            dds = dl.find_all("dd")
            for dt, dd in zip(dts, dds):
                info[dt.get_text(" ", strip=True).lower()] = \
                    dd.get_text(" ", strip=True)
        return info.get("termine"), info.get("öffnungszeiten")

    @staticmethod
    def _occurrences(recur, today) -> list[_dt.date]:
        wds, ords = recur
        out: list[_dt.date] = []
        if ords is None:                      # wöchentlich
            for off in range(RECUR_DAYS + 1):
                d = today + timedelta(days=off)
                if d.weekday() in wds:
                    out.append(d)
            return out
        for moff in range(3):                 # n-ter Wochentag im Monat
            y = today.year + (today.month - 1 + moff) // 12
            m = (today.month - 1 + moff) % 12 + 1
            for wd in wds:
                days = [d for d in range(1, calendar.monthrange(y, m)[1] + 1)
                        if _dt.date(y, m, d).weekday() == wd]
                for o in ords:
                    idx = o - 1 if o > 0 else len(days) - 1
                    if 0 <= idx < len(days):
                        cand = _dt.date(y, m, days[idx])
                        if today <= cand <= today + timedelta(days=70):
                            out.append(cand)
        return out

    def _add(self, events, seen, title, url, d, hrs, g, recurring):
        if hasattr(d, "date"):           # datetime -> date
            day = d.date()
        else:
            day = d
        if hrs:
            start = _dt.datetime(day.year, day.month, day.day, hrs[0], hrs[1])
            end = _dt.datetime(day.year, day.month, day.day, hrs[2], hrs[3])
        else:
            start = _dt.datetime(day.year, day.month, day.day)
            end = None
        key = url + "|" + start.isoformat()
        if key in seen:
            return
        seen.add(key)
        g = g or {}
        events.append(Event(
            title=title[:140],
            start=start,
            end=end,
            source_url=url,
            source_name=self.name,
            location=None,
            address=_clean_addr(g.get("address")),
            description=(g.get("description") or "").strip() or None,
            lat=g.get("lat"),
            lng=g.get("lng"),
            tags=["Markt"],
            time_known=bool(hrs),
        ))
