"""Planetarium Berlin -- Drupal event listing (per category).

The Stiftung Planetarium Berlin site is Drupal; the /tickets page is a JS
widget, but the taxonomy pages under /veranstaltungsart/<art> are
server-rendered. We read just the two wanted categories (Konzerte,
Hörspiele & Lesungen).

The first dump showed no ``<time datetime>`` elements, so the parser is
structure-driven: we collect links to event detail pages and pull the
German date text from the surrounding teaser. A rich structure dump goes
to the debug file so the selectors can be refined from real markup.
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

MONTHS = {
    "januar": 1, "februar": 2, "märz": 3, "maerz": 3, "april": 4, "mai": 5,
    "juni": 6, "juli": 7, "august": 8, "september": 9, "oktober": 10,
    "november": 11, "dezember": 12,
    "jan": 1, "feb": 2, "mär": 3, "mar": 3, "apr": 4, "jun": 6, "jul": 7,
    "aug": 8, "sep": 9, "okt": 10, "nov": 11, "dez": 12,
}
# "18. Juni 2026", "18. Juni"
DATE_TXT = re.compile(r"(\d{1,2})\.\s*([A-Za-zäöüÄÖÜ]+)\.?\s*(\d{4})?", re.I)
# "18.06.2026", "18.06."
DATE_NUM = re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})?")
TIME_TXT = re.compile(r"(\d{1,2})[:.](\d{2})\s*Uhr|(\d{1,2})[:.](\d{2})")
# Teaser links point to a program page /veranstaltungen/<slug>.
DETAIL_RE = re.compile(r"/veranstaltungen/[a-z0-9]", re.I)


class PlanetariumScraper(BaseScraper):
    name = "Planetarium Berlin"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        events: list[Event] = []
        seen: set[str] = set()
        dump: list[str] = []
        for path, category in SECTIONS:
            url = BASE + path
            try:
                html = self.get(url, headers=BROWSER).text
            except Exception as exc:  # noqa: BLE001
                dump.append(f"{path}: FEHLER {exc}")
                continue
            soup = BeautifulSoup(html, "html.parser")
            found, info = self._parse(soup, category, seen, events)
            dump.append(f"{path} ({category}): +{found}\n{info}")
        self._dump(f"Events: {len(events)}\n\n" + "\n\n========\n".join(dump))
        return events

    def _parse(self, soup, category, seen, events):
        # Drop chrome we never want to scan.
        for tag in soup.select(
                "header, footer, nav, script, style, .region-navigation"):
            tag.decompose()

        # Collect candidate teasers: any link to an event detail page, climbed
        # to its surrounding card.
        cards = []
        seen_cards = set()
        for a in soup.find_all("a", href=True):
            if not DETAIL_RE.search(a["href"]):
                continue
            card = self._card(a)
            key = id(card)
            if key in seen_cards:
                continue
            seen_cards.add(key)
            cards.append((a, card))

        found = 0
        for a, card in cards:
            ev = self._build(a, card, category)
            if ev and ev._k not in seen:
                seen.add(ev._k)
                events.append(ev)
                found += 1

        # Debug: structure overview so we can refine selectors.
        info_lines = [
            f"Detail-Links: {len(cards)}",
            f"article-Elemente: {len(soup.select('article'))}",
            f"views-row: {len(soup.select('.views-row'))}",
            f"node-Elemente: {len(soup.select('[class*=node--]'))}",
            f"time[datetime]: {len(soup.select('time[datetime]'))}",
        ]
        # Probe: holt die erste Programm-Detailseite und prüft, ob dort
        # Termine server-seitig stehen (JSON-LD / <time> / Datumstext) oder
        # nur per Ticket-SPA. Entscheidet, ob Detail-Fetching sich lohnt.
        if cards:
            href = urljoin(BASE, cards[0][0]["href"])
            try:
                dhtml = self.get(href, headers=BROWSER).text
                dsoup = BeautifulSoup(dhtml, "html.parser")
                jsonld = dsoup.find_all("script", type="application/ld+json")
                times = dsoup.select("time[datetime]")
                txt = dsoup.get_text(" ", strip=True)
                dates = re.findall(
                    r"\d{1,2}\.\s*(?:Jan|Feb|Mär|Apr|Mai|Jun|Jul|Aug|Sep|Okt|"
                    r"Nov|Dez)[a-zäöü]*\.?\s*\d{0,4}|\d{1,2}\.\d{1,2}\.\d{2,4}",
                    txt, re.I)
                info_lines.append(f"--- Detail-Probe {href} ---")
                info_lines.append(
                    f"JSON-LD-Blöcke: {len(jsonld)} | time[datetime]: "
                    f"{len(times)} | Datumstreffer: {len(dates)}")
                # Kleinste Elemente, die eine Uhrzeit enthalten -> Termin-Zeilen.
                rows = []
                for el in dsoup.find_all(string=re.compile(r"\d{1,2}[:.]\d{2}\s*Uhr")):
                    parent = el.parent
                    cls = " ".join(parent.get("class", []))
                    rows.append(f"<{parent.name} class='{cls}'> "
                                + parent.get_text(" ", strip=True)[:120])
                    if len(rows) >= 8:
                        break
                info_lines.append(f"Uhrzeit-Zeilen: {len(rows)}")
                info_lines.extend(rows)
                if not rows and dates:
                    info_lines.append("Datum-Beispiele: " + ", ".join(dates[:10]))
                # Termin-Tabelle (event-date...) komplett dumpen.
                table = dsoup.find(class_=re.compile(r"event-date", re.I))
                if table:
                    top = table
                    for _ in range(4):
                        if top.parent and "event-date" in " ".join(
                                top.parent.get("class", [])):
                            top = top.parent
                        else:
                            break
                    info_lines.append("--- event-date-Block ---")
                    info_lines.append(top.prettify()[:1800])
            except Exception as exc:  # noqa: BLE001
                info_lines.append(f"Detail-Probe FEHLER: {exc}")

        arts = soup.select("article")
        if arts:
            info_lines.append("--- erstes <article> (roh) ---")
            info_lines.append(arts[0].prettify()[:1000])
        elif cards:
            info_lines.append("--- erstes Teaser-Element ---")
            info_lines.append(cards[0][1].prettify()[:1400])
        else:
            main = soup.select_one(
                "main, #main-content, .region-content, .main-content")
            info_lines.append("--- kein Detail-Link, main-Region (Text) ---")
            info_lines.append((main or soup).get_text(" ", strip=True)[:800])
        return found, "\n".join(info_lines)

    @staticmethod
    def _card(a):
        node = a
        for _ in range(6):
            if node.parent is None:
                break
            node = node.parent
            cls = " ".join(node.get("class", []))
            if node.name == "article" or re.search(
                    r"teaser|views-row|node--|card|event|item", cls, re.I):
                return node
        return a.parent or a

    def _build(self, a, card, category) -> Event | None:
        text = card.get_text(" ", strip=True)
        start = self._date(text)
        if not start:
            return None
        title = ""
        head = card.find(["h1", "h2", "h3", "h4"])
        if head:
            title = head.get_text(" ", strip=True)
        if not title:
            title = a.get_text(" ", strip=True)
        title = re.sub(r"\s+", " ", title).strip()
        if len(title) < 2:
            return None
        href = urljoin(BASE, a["href"])
        img = card.find("img", src=True)
        time_known = bool(TIME_TXT.search(text))
        ev = Event(
            title=title[:160],
            start=start,
            source_url=href,
            source_name=self.name,
            location="Planetarium Berlin",
            image_url=urljoin(BASE, img["src"]) if img else None,
            tags=[category],
            time_known=time_known,
        )
        ev._k = href + "|" + start.isoformat()
        return ev

    def _date(self, text):
        now = _dt.datetime.now()
        hour = minute = 0
        mt = TIME_TXT.search(text)
        if mt:
            g = mt.groups()
            hour = int(g[0] or g[2] or 0)
            minute = int(g[1] or g[3] or 0)
        m = DATE_TXT.search(text)
        if m:
            day = int(m.group(1))
            mon = MONTHS.get(m.group(2).lower())
            year = int(m.group(3)) if m.group(3) else None
            if mon:
                if year is None:
                    year = now.year
                    if (mon, day) < (now.month, now.day):
                        year += 1
                try:
                    return _dt.datetime(year, mon, day, hour, minute)
                except ValueError:
                    return None
        m = DATE_NUM.search(text)
        if m:
            day, mon = int(m.group(1)), int(m.group(2))
            year = int(m.group(3)) if m.group(3) else None
            if year is None:
                year = now.year
                if (mon, day) < (now.month, now.day):
                    year += 1
            try:
                return _dt.datetime(year, mon, day, hour, minute)
            except ValueError:
                return None
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
