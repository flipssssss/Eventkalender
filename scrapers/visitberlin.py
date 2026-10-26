"""visitBerlin -- folgt den Event-Detaillinks einer Listenseite.

Listenseiten von visitberlin.de rendern ihre Treffer clientseitig (kein
JSON-LD in der Liste), verlinken aber auf ``/de/event/<slug>``-Detailseiten,
und DIE tragen schema.org-Event-JSON-LD. Also: Links aus der Liste sammeln,
jede Detailseite lesen.

Zwei Instanzen laufen damit (siehe aggregate.py):

* ``blues-jazz``-Kategorieseite -> alles als Konzert,
* der Veranstaltungskalender, gefiltert auf die Festival-Kategorien
  -> alles als Festival. Festivals bringen aus dem JSON-LD eine endDate mit
  und laufen im Feed deshalb über ihren ganzen Zeitraum, wie Ausstellungen.
"""

from __future__ import annotations

import pathlib
import re
from typing import Iterable
from urllib.parse import urljoin

import datetime as _dt

from bs4 import BeautifulSoup

from .base import BaseScraper, Event, GERMAN_MONTHS
from .jsonld import extract_events_from_html

BASE = "https://www.visitberlin.de"
JAZZ_LISTING = BASE + "/de/kategorie/blues-jazz"
# Veranstaltungskalender, gefiltert auf die beiden Festival-Kategorien
# (cat[0]=9312, cat[1]=9782). Die Filter kommen unverändert aus der Auswahl
# auf der Seite -- die Zahlen sind deren Kategorie-IDs.
#
# OHNE page-Parameter: die Liste ist paginiert und wird durchgeblättert
# (siehe PAGED). Die ursprünglich übernommene Adresse endete auf "page=1".
# Die Filter sind Drupal-Views-Parameter, und Drupal zählt Seiten ab 0 --
# "page=1" war also die ZWEITE Seite. Die erste, mit den gerade laufenden
# Festivals, wurde nie abgerufen.
FESTIVAL_LISTING = (
    BASE + "/de/veranstaltungskalender-berlin"
    "?cat%5B0%5D=9312&cat%5B1%5D=9782&keys=&date_between%5Bmin%5D="
    "&date_between%5Bmax%5D=&district=All&items_per_page=21"
)
# Höchstzahl Listenseiten. Bei 21 Einträgen je Seite reicht das für rund
# 200 Festivals -- weit mehr, als in den 120-Tage-Horizont passen.
MAX_PAGES = 10
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
EVENT_LINK_RE = re.compile(r'href="(/de/event/[a-z0-9][a-z0-9\-]*)"', re.I)

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}


# --------------------------------------------------------------------------
# Unzuverlässige Startdaten im JSON-LD
#
# visitBerlin liefert bei manchen Einträgen als "startDate" einen
# Zeitstempel aus dem Redaktionssystem statt des Festivalbeginns. Beispiel:
# "Berliner Theatertreffen 2027" mit startDate 2025-05-07T14:49:20 und
# endDate 2027-05-23 -- das Festival galt damit zwei Jahre lang als
# "laufend" und stand jeden Tag im Feed, beginnt aber erst am 06.05.2027.
#
# Erkennungsmerkmale, beide objektiv:
#   * Sekunden ungleich 0 -- geplante Anfangszeiten sind nie sekundengenau,
#     Zeitstempel eines CMS fast immer. Unter 71 Festivals traf das genau
#     dieses eine.
#   * Der Titel nennt ein späteres Jahr als der Start ("... 2027", Start
#     2025), bei langer Spanne.
#
# Bewusst KEINE pauschale Längengrenze: die Berlin Biennale läuft wirklich
# rund drei Monate und würde dabei fälschlich mitgetroffen.
# --------------------------------------------------------------------------

_YEAR_RE = re.compile(r"\b(20\d\d)\b")
_MONTH_ALT = "|".join(sorted(GERMAN_MONTHS, key=len, reverse=True))
# "06.05.2027 – 23.05.2027", "06.05. – 23.05.2027", "6.5.-23.5.2027"
_NUM_RANGE = re.compile(
    r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})?\s*(?:–|-|—|bis)\s*"
    r"(\d{1,2})\.(\d{1,2})\.(\d{2,4})")
# "6. Mai – 23. Mai 2027", "6. Mai 2027 – 23. Mai 2027", "6.–23. Mai 2027"
_WORD_RANGE = re.compile(
    r"(\d{1,2})\.\s*(?:(" + _MONTH_ALT + r")\.?\s*(\d{4})?)?\s*(?:–|-|—|bis)\s*"
    r"(\d{1,2})\.\s*(" + _MONTH_ALT + r")\.?\s*(\d{4})", re.IGNORECASE)


def start_untrustworthy(ev: Event) -> bool:
    """True, wenn das Startdatum aus dem JSON-LD erkennbar kein Festivalbeginn ist."""
    if not ev.start:
        return False
    if ev.start.second != 0:
        return True
    years = [int(y) for y in _YEAR_RE.findall(ev.title or "")]
    if years and ev.end and ev.start.year < max(years) \
            and (ev.end - ev.start).days > 60:
        return True
    return False


def _year(y: str | None, default: int) -> int:
    if not y:
        return default
    y = int(y)
    return y + 2000 if y < 100 else y


def start_from_page(html: str, end: _dt.datetime | None) -> _dt.datetime | None:
    """Beginn aus dem sichtbaren Zeitraum der Seite.

    Akzeptiert wird NUR ein Zeitraum, dessen Ende auf den Tag mit dem
    bekannten endDate übereinstimmt. Eine Detailseite enthält viele Daten
    (Navigation, verwandte Termine, "aktualisiert am") -- ohne diesen Anker
    würde leicht das falsche gegriffen.
    """
    if not end:
        return None
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    target = end.date()
    found: list[_dt.date] = []

    for m in _NUM_RANGE.finditer(text):
        try:
            e = _dt.date(_year(m.group(6), target.year), int(m.group(5)), int(m.group(4)))
            if e != target:
                continue
            sy = _year(m.group(3), e.year)
            s = _dt.date(sy, int(m.group(2)), int(m.group(1)))
            if s > e and not m.group(3):          # Jahreswechsel: 28.12.–03.01.
                s = s.replace(year=s.year - 1)
            found.append(s)
        except ValueError:
            continue

    for m in _WORD_RANGE.finditer(text):
        try:
            e_month = GERMAN_MONTHS[m.group(5).lower().rstrip(".")]
            e = _dt.date(int(m.group(6)), e_month, int(m.group(4)))
            if e != target:
                continue
            s_month = (GERMAN_MONTHS[m.group(2).lower().rstrip(".")]
                       if m.group(2) else e_month)
            s = _dt.date(_year(m.group(3), e.year), s_month, int(m.group(1)))
            if s > e and not m.group(3):
                s = s.replace(year=s.year - 1)
            found.append(s)
        except (ValueError, KeyError):
            continue

    # Plausibel: vor dem Ende, und kein Monate langer Zeitraum.
    found = [s for s in found if s <= target and (target - s).days <= 120]
    if not found:
        return None
    start = max(found)              # engster passender Zeitraum
    return _dt.datetime(start.year, start.month, start.day)


def date_snippets(html: str, limit: int = 12) -> list[str]:
    """Datumsähnliche Textstellen der Seite -- für die Diagnose."""
    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    out = []
    for m in re.finditer(r".{0,40}\b\d{1,2}\.\s*(?:\d{1,2}\.|" + _MONTH_ALT
                         + r")[^|]{0,40}", text, re.IGNORECASE):
        snip = re.sub(r"\s+", " ", m.group(0)).strip()
        if snip not in out:
            out.append(snip)
        if len(out) >= limit:
            break
    return out


class VisitBerlinJazzScraper(BaseScraper):
    name = "visitBerlin Jazz"

    def __init__(self, category: str = "Konzert", max_events: int = 50,
                 write_debug: bool = True, listing: str | None = None,
                 name: str | None = None, slug: str | None = None,
                 paged: bool = False):
        self.category = category
        self.max_events = max_events
        self.write_debug = write_debug
        self.listing = listing or JAZZ_LISTING
        if name:
            self.name = name
        # Dateiname der Diagnose; Standard bleibt der bisherige.
        self.slug = slug or "visitberlin-jazz"
        # Liste über "&page=N" durchblättern (Veranstaltungskalender) oder nur
        # die eine Seite lesen (Kategorieseite, wie bisher).
        self.paged = paged

    def _collect_links(self) -> tuple[list[str], list[str], str]:
        """Event-Links aus der Liste (ggf. über alle Seiten).

        Gibt (Links, Seitenprotokoll, HTML der letzten Seite) zurück.

        Blättern beginnt bei page=0. Ob die Seite ab 0 oder ab 1 zählt, lässt
        sich von hier aus nicht prüfen -- deshalb wird nicht beim ersten
        Durchgang ohne neue Links abgebrochen, sondern erst beim zweiten in
        Folge: zählt die Seite ab 1, liefern page=0 und page=1 dasselbe, und
        ein sofortiger Abbruch würde alles ab Seite 2 verschenken.
        """
        if not self.paged:
            html = self.get(self.listing, headers=BROWSER).text
            links = list(dict.fromkeys(EVENT_LINK_RE.findall(html)))
            return links, [f"eine Seite: {len(links)} Links"], html

        links: list[str] = []
        log: list[str] = []
        html = ""
        leer_in_folge = 0
        for page in range(MAX_PAGES):
            url = f"{self.listing}&page={page}"
            try:
                html = self.get(url, headers=BROWSER).text
            except Exception as exc:  # noqa: BLE001
                log.append(f"page={page}: FEHLER {exc}")
                break
            found = list(dict.fromkeys(EVENT_LINK_RE.findall(html)))
            neu = [p for p in found if p not in links]
            links.extend(neu)
            log.append(f"page={page}: {len(found)} Links, {len(neu)} neu")
            if not found:
                break                      # Ende der Liste
            leer_in_folge = 0 if neu else leer_in_folge + 1
            if leer_in_folge >= 2:
                break                      # zweimal nichts Neues -> fertig
            if len(links) >= self.max_events:
                log.append(f"Obergrenze {self.max_events} erreicht.")
                break
        return links, log, html

    def fetch_events(self) -> Iterable[Event]:
        try:
            all_paths, page_log, html = self._collect_links()
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER (Liste): {exc}")
            return []
        paths = all_paths[:self.max_events]
        events: list[Event] = []
        corrected: list[str] = []
        dropped: list[tuple] = []
        seen: set[str] = set()
        for path in paths:
            url = urljoin(BASE, path)
            try:
                dhtml = self.get(url, headers=BROWSER).text
            except Exception:  # noqa: BLE001
                continue
            for ev in extract_events_from_html(dhtml, url, self.name):
                ev.tags = [self.category]
                ev.source_url = url
                if start_untrustworthy(ev):
                    bad_start = ev.start
                    fixed = start_from_page(dhtml, ev.end)
                    if fixed:
                        ev.start = fixed
                        ev.time_known = False   # der Seitentext nennt nur Tage
                        corrected.append(f"  {ev.title}: {bad_start} -> {fixed.date()}"
                                         f" (bis {ev.end.date()})")
                    else:
                        # Lieber gar kein Eintrag als einer, der monatelang
                        # fälschlich als "laufend" im Feed steht.
                        dropped.append((ev.title, bad_start, ev.end,
                                        date_snippets(dhtml)))
                        continue
                key = url + "|" + (ev.start.isoformat() if ev.start else "")
                if key in seen:
                    continue
                seen.add(key)
                events.append(ev)
        lines = [f"Liste: {self.listing}",
                 f"Event-Links: {len(paths)} | Events: {len(events)}",
                 "", "Seiten:", *[f"  {l}" for l in page_log], ""]
        if corrected:
            lines += ["Startdatum aus dem Seitentext korrigiert "
                      "(JSON-LD-Start war ein Zeitstempel):", *corrected, ""]
        if dropped:
            lines.append("VERWORFEN -- Start unzuverlässig, kein passender "
                         "Zeitraum im Seitentext gefunden:")
            for title, bad, end, snips in dropped:
                lines.append(f"  {title}: JSON-LD {bad} -> {end}")
                lines += [f"      Seitentext: {sn}" for sn in snips]
            lines.append("")
        if events:
            starts = sorted(e.start for e in events if e.start)
            lines.append(f"Zeitraum der Starts: {starts[0]} … {starts[-1]}")
            lines.append("")
        # ALLE Titel, nicht nur die ersten 30: so lässt sich direkt prüfen,
        # ob ein bestimmtes Festival angekommen ist.
        lines += [f"  {e.start} → {e.end} | {e.location} | {e.title}"
                  for e in sorted(events, key=lambda x: x.start)]
        if not paths:
            # Keine Detaillinks: entweder rendert die Liste jetzt anders, oder
            # der Abruf wurde abgewiesen. Beides muss hier erkennbar sein.
            lines += ["",
                      "KEINE /de/event/-LINKS IN DER LISTE.",
                      f"  HTML-Länge: {len(html)} Zeichen",
                      f"  enthält '/de/event/': {'/de/event/' in html}",
                      f"  enthält 'veranstaltung': {'veranstaltung' in html.lower()}",
                      "", "HTML-Anfang (1500 Zeichen):", html[:1500]]
        self._dump("\n".join(lines))
        return events

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / f"{self.slug}.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
