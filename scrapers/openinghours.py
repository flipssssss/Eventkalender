"""Curated opening hours per exhibition venue ("Haus").

Exhibitions run over a period but their venue is only open on certain weekdays.
This module maps a venue (matched as a substring of the event location) to its
weekly opening hours, so the feed can

* hide an exhibition on days the house is closed, and
* show the day's opening time instead of a meaningless "23:59".

The table is curated by hand (museum hours are stable). A venue is looked up
**once** per build; venues we don't know yet are collected by ``unknown`` so
they can be added here later -- until then they simply fall back to
"shown every day, no time".

Schedule shape: a dict with the seven weekday keys ``mo di mi do fr sa so``;
each value is a time range string like ``"10–18"`` or ``None`` when closed.
"""

from __future__ import annotations

DAYS = ["mo", "di", "mi", "do", "fr", "sa", "so"]


def sched(default: str, closed=(), **overrides) -> dict:
    """Build a weekly schedule: ``default`` hours, ``closed`` days None,
    per-day ``overrides`` (e.g. ``do="10–20"``)."""
    out = {}
    for d in DAYS:
        if d in closed:
            out[d] = None
        elif d in overrides:
            out[d] = overrides[d]
        else:
            out[d] = default
    return out


# Key = substring matched (case-insensitively) against the event location.
# Longer/more specific keys win (we test them longest-first).
HOURS = {
    "Neue Nationalgalerie": sched("10–18", closed=["mo"], do="10–20"),
    "Hamburger Bahnhof": sched("10–18", closed=["mo"], do="10–20",
                               sa="11–18", so="11–18"),
    "Museum für Fotografie": sched("11–19", closed=["mo"], do="11–20"),
    "Gropius Bau": sched("10–19", closed=["di"]),
    "James-Simon-Galerie": sched("10–18", closed=["mo"]),
    "Berlinische Galerie": sched("10–18", closed=["di"]),
    "Alte Nationalgalerie": sched("10–18", closed=["mo"]),
    "Kulturforum": sched("10–18", closed=["mo"], sa="11–18", so="11–18"),
    "KW - Institute": sched("11–19", closed=["di"], do="11–21"),
    "Kinemathek": sched("10–18", closed=["di"], do="10–20"),
    "Kindl": sched("12–18", closed=["mo", "di"]),
    "C/O Berlin": sched("11–20"),
    "PalaisPopulaire": sched("11–18", closed=["di"]),
    "Schinkel Pavillon": sched("12–18", closed=["mo", "di"]),
    "Anti-Kriegs-Museum": sched("16–20"),
    "Capitain Petzel": sched("11–18", closed=["so", "mo"]),
}

# Venue keys longest-first so e.g. a very generic key can't shadow a specific one.
_KEYS = sorted(HOURS, key=len, reverse=True)

# Locations seen during a build that we have no hours for (for the debug log).
unknown: set[str] = set()


def lookup(location: str | None) -> dict | None:
    """Return the weekly schedule for a location, or None if unknown.

    Unknown locations are remembered in ``unknown`` so new houses surface in
    the debug report and can be added to ``HOURS``.
    """
    if not location:
        return None
    low = location.lower()
    for key in _KEYS:
        if key.lower() in low:
            return HOURS[key]
    unknown.add(location)
    return None
