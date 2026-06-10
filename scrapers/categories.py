"""Map the many raw source categories onto one small, fixed tag set.

Every event ends up with exactly ONE tag from this list:

    Theater, Konzert, Party, Kink, Film, Diskussion, Essen, Protest,
    Sonstiges

Events categorised as advice/help ("Beratung") are dropped entirely.
When a source provides several categories, the first match in
:data:`PRIORITY` wins. Anything that maps to nothing becomes "Sonstiges".

Party and Kink have no matches in the current sources yet; they are kept
in the taxonomy for sources added later.
"""

from __future__ import annotations

# Priority order when an event carries several categories (first wins).
# A "real" category always beats Beratung, so an event is only dropped
# when Beratung (or help/advice) is essentially all it is.
PRIORITY = [
    "Protest",
    "Konzert",
    "Party",
    "Kink",
    "Film",
    "Theater",
    "Diskussion",
    "Essen",
]

# Special marker: events with such a category are removed from the feed.
DROP = "Beratung"

# Keyword (substring, case-insensitive) -> target tag.
KEYWORDS: dict[str, list[str]] = {
    "Theater": ["theater"],
    "Konzert": ["konzert", "musik"],
    "Film": ["film", "kino"],
    "Diskussion": ["diskussion", "vortrag"],
    "Essen": ["essen", "café", "cafe", "kneipe", "küfa", "kufa", "küche", "kueche"],
    "Protest": ["protest", "aktion", "demo", "kundgebung"],
    "Party": ["party", "tanz", "rave"],
    "Kink": ["kink", "fetisch", "bdsm"],
    DROP: ["beratung", "hilfe", "sprechstunde"],
}


def _map_one(raw: str) -> str | None:
    low = (raw or "").strip().lower()
    if not low:
        return None
    for tag, keys in KEYWORDS.items():
        if any(key in low for key in keys):
            return tag
    return None


def categorize(raw_tags) -> str | None:
    """Return the single display tag, or ``None`` if the event is dropped.

    A real category (Theater, Konzert, …) always wins. An event is only
    dropped when its sole recognised category is Beratung/help/advice.
    """
    matched: set[str] = {
        tag for raw in (raw_tags or []) if (tag := _map_one(raw))
    }
    for tag in PRIORITY:
        if tag in matched:
            return tag
    if DROP in matched:
        return None  # essentially a counselling/advice appointment
    return "Sonstiges"
