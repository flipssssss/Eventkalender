"""Rosa-Luxemburg-Stiftung -- politische Vorträge/Diskussionen.

The events page (rosalux.de/veranstaltungen) is server-rendered HTML (no
JSON-LD): each event is a ``section.elasticsearch__result`` carrying a
``data-ts`` start timestamp (ms), with the title, city and type inside a
``.teaser--event``. Foundation events are nationwide, so only Berlin ones are
kept. The listing shows one calendar month; the next months are fetched by
re-submitting its month form. All kept events are category Vortrag; genre Polit is set in
scrapers/genres.py.
"""

from __future__ import annotations

import datetime as _dt
import pathlib
import re
from typing import Iterable
from urllib.parse import urlencode, urljoin

import requests

from bs4 import BeautifulSoup

from .base import REQUEST_TIMEOUT, BaseScraper, Event, _throttle
from . import metacache

try:
    from zoneinfo import ZoneInfo
    _TZ = ZoneInfo("Europe/Berlin")
except Exception:  # noqa: BLE001
    _TZ = None

BASE = "https://www.rosalux.de"
URL = BASE + "/veranstaltungen"
# The listing shows one calendar month (hidden form fields year/month, sent
# by POST); further months are fetched by re-submitting that form.
MONTHS_AHEAD = 3
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
        self._session = requests.Session()
        try:
            html = self._request("GET", URL).text
        except Exception as exc:  # noqa: BLE001
            self._dump(f"FEHLER: {exc}")
            return []
        secs, month_log = self._collect(html)
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
        self._dump(f"Teaser: {len(secs)} | "
                   f"{self.city}: {len(events)} | andere Städte: {other_city} | "
                   f"mit Beschreibung: {sum(1 for e in events if e.description)} | "
                   f"letzter Termin: {last}\n"
                   "Monate:\n" + "\n".join(month_log) + "\n" +
                   "\n".join(f"  {e.start} | {e.location} | {e.title}"
                             for e in events[:80]))
        return events

    def _request(self, method: str, url: str, data=None):
        """GET/POST through one session (cookies of the first page are kept),
        with the site's browser headers."""
        _throttle(url)
        headers = dict(BROWSER)
        if method == "POST":
            headers.update({"Origin": BASE, "Referer": URL,
                            "Sec-Fetch-Site": "same-origin"})
        resp = self._session.request(method, url, data=data, headers=headers,
                                     timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        return resp

    def _collect(self, first_html: str) -> tuple[list, list[str]]:
        """Teasers of the current month plus the next MONTHS_AHEAD months.

        The month form carries Extbase hidden fields (__referrer,
        __trustedProperties) that must be sent back unchanged; only year and
        month are changed. POST like the browser; GET with the same fields as
        a fallback."""
        soup = BeautifulSoup(first_html, "html.parser")
        secs = list(soup.select("section.elasticsearch__result"))
        seen = {self._teaser_key(x) for x in secs}
        log = [self._month_line("aktuell", secs, len(secs), URL)]
        form = next((f for f in soup.select("form")
                     if f.select_one('input[name$="[month]"]')), None)
        if form is None:
            log.append("  kein Monatsformular gefunden")
            return secs, log
        fields = self._form_fields(form)
        mkey = next(k for k, _ in fields if k.endswith("[month]"))
        ykey = next((k for k, _ in fields if k.endswith("[year]")), None)
        try:
            month = int(dict(fields)[mkey])
            year = int(dict(fields)[ykey]) if ykey else _dt.date.today().year
        except (TypeError, ValueError):
            log.append(f"  Monatsfeld unlesbar: {dict(fields).get(mkey)!r}")
            return secs, log
        action = urljoin(URL, form.get("action") or URL).split("#", 1)[0]
        for _ in range(MONTHS_AHEAD):
            month += 1
            if month > 12:
                month, year = 1, year + 1
            data = [(k, str(month) if k == mkey else
                     str(year) if k == ykey else v) for k, v in fields]
            label = f"{year}-{month:02d}"
            found = None
            for method in ("POST", "GET"):
                try:
                    if method == "POST":
                        resp = self._request("POST", action, data=data)
                    else:
                        resp = self._request(
                            "GET", action + ("&" if "?" in action else "?") +
                            urlencode(data))
                except Exception as exc:  # noqa: BLE001
                    log.append(f"  {label} {method}: FEHLER {str(exc)[:80]}")
                    continue
                page = BeautifulSoup(resp.text, "html.parser")
                found = page.select("section.elasticsearch__result")
                new = [x for x in found if self._teaser_key(x) not in seen]
                log.append(self._month_line(f"{label} {method}", found, len(new),
                                            resp.url))
                if new:
                    seen.update(self._teaser_key(x) for x in new)
                    secs.extend(new)
                    break
        return secs, log

    @staticmethod
    def _form_fields(form) -> list[tuple[str, str]]:
        """Name/value pairs a browser would submit (no buttons, unchecked
        boxes or empty selects)."""
        out = []
        for el in form.select("input[name], select[name], textarea[name]"):
            name = el.get("name")
            if el.name == "input":
                typ = (el.get("type") or "text").lower()
                if typ in ("submit", "button", "image", "reset", "file"):
                    continue
                if typ in ("checkbox", "radio") and not el.has_attr("checked"):
                    continue
                out.append((name, el.get("value") or ""))
            elif el.name == "select":
                opt = el.select_one("option[selected]") or el.select_one("option")
                if opt is not None:
                    out.append((name, opt.get("value") or opt.get_text(strip=True)))
            else:
                out.append((name, el.get_text()))
        return out

    def _month_line(self, label: str, found, new: int, url: str) -> str:
        ts = sorted(int(x.get("data-ts")) for x in found
                    if (x.get("data-ts") or "").isdigit())
        span = (f"{self._start(str(ts[0]))} .. {self._start(str(ts[-1]))}"
                if ts else "-")
        return f"  {label}: {len(found)} Teaser, {new} neu, {span} | {url[:110]}"

    @staticmethod
    def _teaser_key(sec) -> tuple:
        link = sec.select_one("a.teaser__link")
        return ((link.get("href") if link else None), sec.get("data-ts"))

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
