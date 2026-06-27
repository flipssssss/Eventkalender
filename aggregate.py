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

from scrapers.base import Event, parse_datetime
from scrapers.berlin_buehnen import BerlinBuehnenScraper
from scrapers.categories import categorize
from scrapers.genres import genre_for
from scrapers.musicgenre import music_genre_for
from scrapers import geocode
from scrapers.donau115 import Donau115Scraper
from scrapers.kulturdaten import KulturdatenScraper
from scrapers.silverfuture import SilverfutureScraper
from scrapers.ra import ResidentAdvisorScraper
from scrapers.siegessaeule import SiegessaeuleScraper
from scrapers.tipberlin import TipBerlinScraper
from scrapers.ical import ICalScraper
from scrapers.jsonld import JsonLdScraper
from scrapers.stressfaktor import StressfaktorScraper
from scrapers.partydyke import PartyDykeScraper
from scrapers.cafecralle import CafeCralleScraper
from scrapers.demoticker import DemoTickerScraper
from scrapers.berlin_ausstellungen import BerlinAusstellungenScraper
from scrapers.laboratory import LaboratoryScraper
from scrapers.timetoshine import TimeToShineScraper
from scrapers.mec import MecScraper
from scrapers.koenig import KoenigScraper
from scrapers.kino import BerlinKinoScraper, group_screenings
from scrapers import openinghours
from scrapers.rosalux import RosaLuxScraper
from scrapers.funfacts import FunFactsScraper
from scrapers.squarespace import SquarespaceEventsScraper
from scrapers.visitberlin import VisitBerlinJazzScraper
from scrapers.gancio import GancioScraper
from scrapers.moebelolfe import MoebelOlfeScraper
from scrapers.othernature import OtherNatureScraper
from scrapers.iksk import IkskScraper
from scrapers.planetarium import PlanetariumScraper
from scrapers.atrane import ATraneScraper
from scrapers.flohmarkt import FlohmarktScraper

ROOT = pathlib.Path(__file__).parent
OUTPUT = ROOT / "docs" / "data" / "events.json"
SOURCES_FILE = ROOT / "sources.yml"

# How many days into the past we still keep (e.g. multi-day events that
# already started). Everything older is dropped.
KEEP_PAST_DAYS = 1

# How far into the future the feed reaches. Events further out are dropped,
# and the scrapers use the same horizon so they don't fetch needlessly.
HORIZON_DAYS = 14

# Further-future windows for events that are planned well ahead. The effective
# window per event is the LARGEST that applies: default, its category, its
# source, and -- for sparse sources (< SPARSE_MIN events in the default
# window) -- SPARSE_HORIZON. Sparse sources stay small even when extended, so
# the load barely changes; dense categories add more, by design.
SOURCE_HORIZON = {
    "FunFacts": 90,
}
CATEGORY_HORIZON: dict[str, int] = {
    "Theater": 30,
    "Konzert": 30,
    "Party": 30,
}
SPARSE_MIN = 10      # fewer than this in the default window -> "sparse"
SPARSE_HORIZON = 30  # how far sparse sources may then reach

# Scrapers that cap their own fetch window must reach at least as far as the
# widest category window, else extended categories have no data to keep.
# (Kino stays at HORIZON_DAYS on purpose -- it is not extended and dense.)
FETCH_HORIZON_DAYS = max([HORIZON_DAYS, *CATEGORY_HORIZON.values()])


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
                    party_or_workshop=bool(entry.get("party_or_workshop")),
                    include=entry.get("include"),
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
                    city=entry.get("city"),
                )
            )
    return scrapers


def get_scrapers():
    """The full list of scrapers to run.

    Add custom scrapers (for sites without JSON-LD) to ``custom`` below.
    """
    custom = [
        # Stressfaktor (Berlin) -- weiter gefasst, damit Party/Konzert bis 30 Tage da sind.
        StressfaktorScraper(days=FETCH_HORIZON_DAYS),
        # berlin-buehnen.de, gefiltert auf die gewünschten Bühnen (Theater bis 30 Tage).
        BerlinBuehnenScraper(horizon_days=FETCH_HORIZON_DAYS),
        # Donau115 (Jazz-Club) -- Events aus der Firebase-DB, alle "Konzert".
        Donau115Scraper(),
        # kulturdaten.berlin -- deaktiviert (zu viel Community-Kleinkram).
        # KulturdatenScraper(),
        # Silverfuture (queere Bar) -- Jimdo-Text-Parser, Genre Queer.
        SilverfutureScraper(),
        # Resident Advisor -- gefolgte Promoter/Clubs/Artists (inkl. Klub Verboten).
        ResidentAdvisorScraper(),
        # Party Dyke Berlin (Wix) -- liest die Event-Detailseiten (JSON-LD).
        PartyDykeScraper(),
        # Café Cralle (Wedding) -- monatlich wiederkehrende Termine.
        CafeCralleScraper(),
        # Demo Ticker Berlin (Mastodon) -- kommende Demos, alle Polit/Protest.
        DemoTickerScraper(),
        # berlin.de/ausstellungen -- aktuelle Ausstellungen (JSON-LD).
        BerlinAusstellungenScraper(),
        # Lab.oratory (Fetisch-Partys) -- Klartext-Parser, Genre Kink.
        LaboratoryScraper(),
        # Time to Shine (Squarespace-JSON) -- Kink/Theater.
        TimeToShineScraper(),
        # Boiler & Club Sauna -- WordPress "Modern Events Calendar" (MEC).
        MecScraper("Boiler Berlin", "https://boiler-berlin.de/en/",
                   address="Mehringdamm 34, 10961 Berlin", fixed_hour=17),
        MecScraper("Club Sauna Berlin", "https://clubsauna.berlin/events/"),
        # König Drag Show (Google Sites) -- Textparser, Queer/Theater.
        KoenigScraper(),
        # Arthouse-Kinos via berlin.de (gruppiert nach Film/Tag).
        BerlinKinoScraper(horizon_days=HORIZON_DAYS),
        # Tipsy Bear: bleibt deaktiviert -- alle Endpunkte hängen hinter
        # Cloudflares JS-Challenge ("Just a moment...", 403), es gibt keinen
        # erreichbaren Daten-Endpunkt (Diagnose in _debug/tipsy-bear.txt).
        # TipsyBearScraper(),
        # Siegessäule -- queerer Eventkalender, Kategorie automatisch (bis 30 Tage).
        SiegessaeuleScraper(days=FETCH_HORIZON_DAYS),
        # Rosa-Luxemburg-Stiftung -- politische Vorträge, nur Berlin (HTML-Teaser).
        RosaLuxScraper(city="Berlin"),
        # FunFacts (Comedy/Talk) -- Wix-Events, nur Berlin (Mehringhof-Theater).
        FunFactsScraper(city="Berlin"),
        # Jazz: B-flat (Squarespace-JSON) und visitBerlin (Detailseiten-JSON-LD).
        SquarespaceEventsScraper(
            "B-flat", "https://b-flat-berlin.de/events", category="Konzert",
            address="Rosenthaler Str. 13, 10119 Berlin"),
        VisitBerlinJazzScraper(category="Konzert"),
        # askapunk (Gancio-DIY-Kalender) -- Punk-Konzerte über die JSON-API.
        GancioScraper("askapunk", "https://berlin.askapunk.de", category="Konzert"),
        # Möbel Olfe (queere Bar) -- statische Tabelle.
        MoebelOlfeScraper(),
        # Other Nature (sex-positiver Laden) -- Shopify-Atom-Feed.
        OtherNatureScraper(),
        # IKSK Berlin -- kuratierte Kink-Specials (server-gerendert).
        IkskScraper(),
        # Planetarium Berlin -- Drupal-Taxonomie-Seiten (Konzerte, Hörspiele).
        PlanetariumScraper(),
        # A-Trane -- JSON-LD, aber Titel aus dem <br>-Block destilliert.
        ATraneScraper(),
        # Flohmärkte Berlin (berlin.de): datierte Sondermärkte + GeoJSON.
        FlohmarktScraper(),
        # Öko-Wochenmärkte (berlin.de/biomarkt) -- gleiche Struktur wie Flohmärkte.
        FlohmarktScraper(
            "Öko-Wochenmärkte",
            "https://www.berlin.de/special/shopping/biomarkt/",
            "https://www.berlin.de/special/shopping/biomarkt/rubric.geojson"),
        # tip Berlin -- deaktiviert: keine erreichbare Quelle für Event-Daten
        # (proprietäres "rce"-Plugin, Bot-Schutz, Ausstellungen ohne Termin).
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
    # Drop anything before today (no "yesterday" events in the feed).
    now = _dt.datetime.now()
    cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
    default_horizon = now + _dt.timedelta(days=HORIZON_DAYS)

    # First pass: how many events each source has in the default window, so
    # "sparse" sources (< SPARSE_MIN) can be extended automatically.
    base_counts: dict[str, int] = {}
    for event in events:
        if not event.start or categorize(event.tags) is None:
            continue
        sn = event.start.replace(tzinfo=None)
        if cutoff <= sn <= default_horizon:
            base_counts[event.source_name] = base_counts.get(event.source_name, 0) + 1

    kept: dict[str, Event] = {}
    for event in events:
        if not event.start:
            continue
        # Map the source's raw categories onto the fixed tag set; drop
        # advice/help ("Beratung") events entirely.
        primary = categorize(event.tags)
        if primary is None:
            continue
        event.tags = [primary]
        # Compare naively to avoid tz-aware/naive mix-ups.
        start_naive = event.start.replace(tzinfo=None)
        # Drop only once an event has fully ended (so still-running multi-day
        # events stay); the frontend moves today's finished ones to "Schon
        # vorbei" and removes the whole day at midnight.
        end_naive = event.end.replace(tzinfo=None) if event.end else start_naive
        # Window = the largest that applies: default, category, source, and a
        # bonus for sparse sources.
        sparse = SPARSE_HORIZON if base_counts.get(event.source_name, 0) < SPARSE_MIN else 0
        days = max(
            HORIZON_DAYS,
            CATEGORY_HORIZON.get(primary, 0),
            SOURCE_HORIZON.get(event.source_name, 0),
            sparse,
        )
        horizon = now + _dt.timedelta(days=days)
        if end_naive < cutoff or start_naive > horizon:
            continue
        # One genre per event: a scraper may set it itself (e.g. RA per source),
        # otherwise it's the source default, overridden by keywords.
        if not event.genre:
            text = " ".join(filter(None, [
                event.title, event.description, event.location, " ".join(event.tags),
            ]))
            event.genre = genre_for(event.source_name, text)
        # Concerts get a coarse music genre (shown after "Konzert").
        if primary == "Konzert" and not event.music_genre:
            event.music_genre = music_genre_for(
                event.source_name,
                " ".join(filter(None, [event.title, event.description])))

        key = event.dedupe_key()
        existing = kept.get(key)
        if existing is None or _richer(event, existing):
            kept[key] = event

    result = list(kept.values())
    result.sort(key=lambda e: e.start.replace(tzinfo=None))
    return result


def _richer(a: Event, b: Event) -> bool:
    """Prefer the duplicate with an image, then with a description."""
    return (bool(a.image_url), bool(a.description)) > (
        bool(b.image_url), bool(b.description))


def write_output(events: list[Event], report: list[dict]) -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "generated_at": _dt.datetime.now().astimezone().isoformat(),
        "count": len(events),
        "sources": report,
        "events": [e.to_dict() for e in events],
    }
    # Minified (no indentation) -- smaller download + faster parse on phones.
    OUTPUT.write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    print(f"\n→ {len(events)} Veranstaltungen geschrieben nach {OUTPUT}")


def attach_opening_hours(events: list[Event]) -> None:
    """Give every exhibition its venue's weekly opening hours (curated cache).

    Looked up once per venue; venues we don't know yet are written to a debug
    file so they can be added to scrapers/openinghours.py later.
    """
    n = 0
    for event in events:
        if "Ausstellung" not in (event.tags or []):
            continue
        hours = openinghours.lookup(event.location)
        if hours:
            event.opening_hours = hours
            n += 1
    print(f"  ◷ {n} Ausstellungen mit Öffnungszeiten "
          f"({len(openinghours.unknown)} Häuser ohne)")
    if openinghours.unknown:
        try:
            path = ROOT / "docs" / "data" / "_debug" / "ausstellungshaeuser-todo.txt"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                "Häuser ohne kuratierte Öffnungszeiten (in scrapers/"
                "openinghours.py ergänzen):\n\n" +
                "\n".join(sorted(openinghours.unknown)) + "\n",
                encoding="utf-8")
        except OSError:
            pass


def locate(events: list[Event]) -> None:
    """Add address, coordinates and Berlin borough to every event."""
    located = 0
    for event in events:
        geocode.locate_event(event)
        if event.lat is not None:
            located += 1
    geocode.save_cache()
    print(f"  ⌖ {located}/{len(events)} Veranstaltungen verortet")


def _event_from_dict(d: dict) -> Event | None:
    """Rebuild an Event from a previously written feed entry."""
    start = parse_datetime(d.get("start"))
    if not start or not d.get("title"):
        return None
    end = parse_datetime(d.get("end")) if d.get("end") else None
    event = Event(
        title=d["title"],
        start=start.replace(tzinfo=None),
        source_url=d.get("source_url") or "",
        source_name=d.get("source_name") or "",
        end=end.replace(tzinfo=None) if end else None,
        location=d.get("location"),
        description=d.get("description"),
        image_url=d.get("image_url"),
        tags=list(d.get("tags") or []),
        time_known=d.get("time_known", True),
        genre=d.get("genre"),
        subcategory=d.get("subcategory"),
        address=d.get("address"),
        lat=d.get("lat"),
        lng=d.get("lng"),
        bezirk=d.get("bezirk"),
    )
    return event


def carry_over_failed(raw: list[Event], report: list[dict]) -> list[Event]:
    """Keep a source's last-good events when this run brought nothing.

    Some sites block intermittently (403 bot wall) or briefly return an empty
    list even though they usually deliver. Instead of dropping all of that
    source's events, re-use the ones from the previously written feed
    (still-future events stay, past ones age out on their own). Triggered for
    any source whose run errored OR returned zero events this time.
    """
    missing = {r["source"] for r in report if r.get("error") or not r.get("count")}
    if not missing:
        return raw
    try:
        old = json.loads(OUTPUT.read_text(encoding="utf-8")).get("events", [])
    except (OSError, ValueError):
        return raw
    added = 0
    for d in old:
        if d.get("source_name") in missing:
            event = _event_from_dict(d)
            if event:
                raw.append(event)
                added += 1
    if added:
        print(f"  ↻ {added} Events aus letztem Lauf übernommen "
              f"(Quellen ohne neue Events: {', '.join(sorted(missing))})")
    return raw


def main() -> int:
    print("Sammle Veranstaltungen ...")
    raw, report = collect()
    raw = carry_over_failed(raw, report)
    raw = group_screenings(raw)
    events = filter_and_sort(raw)
    attach_opening_hours(events)
    locate(events)
    write_output(events, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
