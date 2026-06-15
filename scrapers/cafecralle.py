"""Café Cralle (Wedding) -- "regelmäßige Veranstaltungen" (WordPress.com).

The page lists monthly recurring events as free text, each as a block of:

    Jeden 3. Montag im Monat        <- recurrence rule
    FLINTA*-Lesekreis               <- title
    <optional description lines>

We read those rules and turn them into concrete dates for the coming weeks
(e.g. "every 3rd Monday" -> the next few 3rd Mondays). Genre and category are
assigned downstream from the title/description.
"""

from __future__ import annotations

import calendar
import datetime as _dt
import pathlib
import re
from typing import Iterable

from bs4 import BeautifulSoup

from .base import BaseScraper, Event

URL = "https://cafecralle.wordpress.com/regelmasige-veranstaltungen/"
DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
HORIZON_DAYS = 70

BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "de-DE,de;q=0.9,en;q=0.8",
}

WEEKDAYS = {
    "montag": 0, "dienstag": 1, "mittwoch": 2, "donnerstag": 3,
    "freitag": 4, "samstag": 5, "sonntag": 6,
}
ORDINALS = {
    "1": 1, "erste": 1, "2": 2, "zweite": 2, "3": 3, "dritte": 3,
    "4": 4, "vierte": 4, "5": 5, "fünfte": 5, "letzte": "last",
}
RECUR_RE = re.compile(
    r"[Jj]eden?\s+"
    r"(\d|erste|zweite|dritte|vierte|fünfte|letzte)[nrs]?\.?\s+"
    r"(Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag)\s+im\s+Monat",
    re.IGNORECASE,
)
SHOW_RE = re.compile(r"Show\s*(\d{1,2}):(\d{2})", re.IGNORECASE)
HM_RE = re.compile(r"\b(\d{1,2}):(\d{2})\b")
UHR_RE = re.compile(r"\b(\d{1,2})\s*Uhr")


def _nth_weekday(year: int, month: int, weekday: int, n) -> _dt.date | None:
    if n == "last":
        last = calendar.monthrange(year, month)[1]
        d = _dt.date(year, month, last)
        return d - _dt.timedelta(days=(d.weekday() - weekday) % 7)
    first = _dt.date(year, month, 1)
    day = 1 + (weekday - first.weekday()) % 7 + (n - 1) * 7
    try:
        return _dt.date(year, month, day)
    except ValueError:
        return None  # e.g. a 5th Monday that doesn't exist this month


class CafeCralleScraper(BaseScraper):
    name = "Café Cralle"

    def __init__(self, write_debug: bool = True):
        self.write_debug = write_debug

    def fetch_events(self) -> Iterable[Event]:
        try:
            resp = self.get(URL, headers=BROWSER)
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        soup = BeautifulSoup(resp.text, "html.parser")
        for t in soup(["script", "style", "header", "footer", "nav", "title"]):
            t.decompose()
        main = soup.select_one(".entry-content, article, main") or soup
        text = re.sub(r"[ \t]+", " ", main.get_text("\n"))
        lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

        headers = [(i, RECUR_RE.search(ln)) for i, ln in enumerate(lines)]
        headers = [(i, m) for i, m in headers if m]

        events: list[Event] = []
        seen: set[str] = set()
        report = [f"Regeln gefunden: {len(headers)}"]

        for idx, (i, m) in enumerate(headers):
            nxt = headers[idx + 1][0] if idx + 1 < len(headers) else len(lines)
            if i + 1 >= nxt:
                continue
            title = lines[i + 1][:140]
            desc = " ".join(lines[i + 2:nxt]).strip()[:600] or None

            weekday = WEEKDAYS[m.group(2).lower()]
            n = ORDINALS.get(m.group(1).lower())
            if n is None:
                continue
            hh, mm, time_known = self._time(" ".join([lines[i], title, desc or ""]))

            for when in self._occurrences(weekday, n):
                start = _dt.datetime(when.year, when.month, when.day, hh, mm)
                key = f"{title.lower()}|{when}"
                if key in seen:
                    continue
                seen.add(key)
                events.append(Event(
                    title=title,
                    start=start,
                    source_url=URL,
                    source_name=self.name,
                    location="Café Cralle",
                    address="Hochstädterstraße 10a, 13347 Berlin",
                    description=desc,
                    time_known=time_known,
                    tags=[title],
                ))
            report.append(f"  {m.group(0)} -> {title}")

        self._dump(f"Events: {len(events)}\n" + "\n".join(report))
        return events

    def _occurrences(self, weekday: int, n) -> list[_dt.date]:
        today = _dt.date.today()
        out: list[_dt.date] = []
        year, month = today.year, today.month
        for _ in range(4):  # this month + next three
            d = _nth_weekday(year, month, weekday, n)
            if d and today <= d <= today + _dt.timedelta(days=HORIZON_DAYS):
                out.append(d)
            month += 1
            if month > 12:
                month, year = 1, year + 1
        return out

    @staticmethod
    def _time(text: str) -> tuple[int, int, bool]:
        m = SHOW_RE.search(text) or HM_RE.search(text)
        if m:
            return int(m.group(1)), int(m.group(2)), True
        m = UHR_RE.search(text)
        if m:
            return int(m.group(1)), 0, True
        return 20, 0, False  # no time on the page -> show date only

    def _dump(self, text: str) -> None:
        if not self.write_debug:
            return
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "cafe-cralle.txt").write_text(text, encoding="utf-8")
        except OSError:
            pass
