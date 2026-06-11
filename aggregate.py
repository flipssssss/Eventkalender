#!/usr/bin/env python3
"""Collect events from all sources and write the feed.

Run locally with::

    python aggregate.py

It will:
  1. load every source from ``sources.yml`` (generic JSON-LD scraper),
  2. add any custom scrapers registered below,
  3. fetch all events, drop duplicates and past events,
  4. sort everything by date,
  5. write ``docs/data/events.json`` (the file the web feed reads).

The GitHub Action runs exactly this script on a schedule.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
import sys

import yaml

from scrapers.base import Event
from scrapers.berlin_buehnen import BerlinBuehnenScraper
from scrapers.categories import categorize
from scrapers.donau115 import Donau115Scraper
from scrapers.siegessaeule import SiegessaeuleScraper
from scrapers.tipberlin import TipBerlinScraper
from scrapers.ical import ICalScraper
from scrapers.jsonld import JsonLdScraper
from scrapers.stressfaktor import StressfaktorScraper

ROOT = pathlib.Path(__file__).parent
OUTPUT = ROOT / "docs" / "data" / "events.json"
SOURCES_FILE = ROOT / "sources.yml"

# How many days into the past we still keep (e.g. multi-day events that
# already started). Everything older is dropped.
KEEP_PAST_DAYS = 1

# How far into the future the feed reaches. Events further out are dropped,
# and the scrapers use the same horizon so they don't fetch needlessly.
HORIZON_DAYS = 14


def load_yaml_scrapers() -> list[JsonLdScraper]:
    """Build a JSON-LD scraper for every entry in sources.yml."""
    if not SOURCES_FILE.exists():
        return []
    data = yaml.safe_load(SOURCES_FILE.read_text(encoding="utf-8")) or {}
    scrapers = []
    for entry in data.get("sources") or []:
        if isinstance(entry, str):
            entry = {"url": entry}
        url = entry.get("url")
        if not url:
            continue
        kind = (entry.get("type") or "jsonld").lower()
        if kind in ("ical", "ics"):
            scrapers.append(
                ICalScraper(
                    url=url,
                    name=entry.get("name"),
                    default_tags=entry.get("tags"),
                    category=entry.get("category"),
                )
            )
        else:
            scrapers.append(
                JsonLdScraper(
                    url=url,
                    name=entry.get("name"),
                    default_tags=entry.get("tags"),
                    category=entry.get("category"),
                    extra_urls=entry.get("extra_urls"),
                )
            )
    return scrapers


def get_scrapers():
    """The full list of scrapers to run.

    Add custom scrapers (for sites without JSON-LD) to ``custom`` below.
    """
    custom = [
        # Stressfaktor (Berlin) -- nächste HORIZON_DAYS Tage via Datums-Facet.
        StressfaktorScraper(days=HORIZON_DAYS),
        # berlin-buehnen.de, gefiltert auf die gewünschten Bühnen.
        BerlinBuehnenScraper(horizon_days=HORIZON_DAYS),
        # Donau115 (Jazz-Club) -- Events aus der Firebase-DB, alle "Konzert".
        Donau115Scraper(),
        # Siegessäule -- queerer Eventkalender, Kategorie automatisch.
        SiegessaeuleScraper(days=HORIZON_DAYS),
        # tip Berlin -- pausiert: REST-API hat kein Event-Datum, Ausstellungen
        # sind ohne festen Termin; siehe scrapers/tipberlin.py.
        # TipBerlinScraper(),
        # Tipsy Bear: deaktiviert -- Cloudflare-JS-Challenge blockt jeden
        # automatisierten Zugriff (scrapers/tipsybear.py belegt das).
        # TipsyBearScraper(),
        # Demo-Daten sind standardmäßig aus. Zum Ausprobieren einkommentieren:
        # from scrapers.demo import DemoScraper
        # DemoScraper(),
    ]
    return load_yaml_scrapers() + custom


def collect() -> tuple[list[Event], list[dict]]:
    events: list[Event] = []
    report: list[dict] = []

    for scraper in get_scrapers():
        name = getattr(scraper, "name", scraper.__class__.__name__)
        try:
            found = list(scraper.fetch_events())
            events.extend(found)
            report.append({"source": name, "count": len(found), "error": None})
            print(f"  ✓ {name}: {len(found)} Veranstaltungen")
        except Exception as exc:  # noqa: BLE001 - one bad source must not kill the run
            report.append({"source": name, "count": 0, "error": str(exc)})
            print(f"  ✗ {name}: FEHLER -> {exc}", file=sys.stderr)
    return events, report


def filter_and_sort(events: list[Event]) -> list[Event]:
    cutoff = _dt.datetime.now() - _dt.timedelta(days=KEEP_PAST_DAYS)
    horizon = _dt.datetime.now() + _dt.timedelta(days=HORIZON_DAYS)

    seen: set[str] = set()
    kept: list[Event] = []
    for event in events:
        if not event.start:
            continue
        # Compare naively to avoid tz-aware/naive mix-ups.
        start_naive = event.start.replace(tzinfo=None)
        if start_naive < cutoff or start_naive > horizon:
            continue
        # Map the source's raw categories onto the fixed tag set; drop
        # advice/help ("Beratung") events entirely.
        primary = categorize(event.tags)
        if primary is None:
            continue
        event.tags = [primary]
        key = event.dedupe_key()
        if key in seen:
            continue
        seen.add(key)
        kept.append(event)

    kept.sort(key=lambda e: e.start.replace(tzinfo=None))
    return kept


def write_output(events: list[Event], report: list[dict]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _dt.datetime.now().astimezone().isoformat(),
        "count": len(events),
        "sources": report,
        "events": [e.to_dict() for e in events],
    }
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n→ {len(events)} Veranstaltungen geschrieben nach {OUTPUT}")


def main() -> int:
    print("Sammle Veranstaltungen ...")
    raw, report = collect()
    events = filter_and_sort(raw)
    write_output(events, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
