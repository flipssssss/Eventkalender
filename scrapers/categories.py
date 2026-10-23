"""Map the many raw source categories onto one small, fixed tag set.

Every event ends up with exactly ONE tag from this list:

    Theater, Konzert, Party, Kink, Kino, Diskussion, Essen, Protest,
    Festival, Sonstiges

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
    "Festival",
    "Konzert",
    "Party",
    "Kino",
    "Ausstellung",
    "Theater",
    "Workshop",
    "Vortrag",
    "Essen",
    "Markt",
]

# Special marker: events with such a category are removed from the feed.
DROP = "Beratung"

# Keyword (substring, case-insensitive) -> target tag.
KEYWORDS: dict[str, list[str]] = {
    # ACHTUNG, Reihenfolge ist Programm: _map_one() nimmt den ERSTEN Treffer
    # in diesem Dict. PRIORITY greift nur, wenn eine Quelle MEHRERE Kategorien
    # liefert -- innerhalb eines einzelnen Strings entscheidet die Position
    # hier. "Festival" muss deshalb vor Konzert und Kino stehen, sonst wird
    # "Musikfestival" zu Konzert (Stichwort "musik") und "Filmfest" zu Kino.
    #
    # Bewusst eng gehalten: "fest" allein würde zu viel fangen (Stadtfest,
    # Hoffest, Sommerfest sind keine Festivals im Sinne dieser Kategorie).
    "Festival": ["festival", "festspiele", "filmfest", "musikfest",
                 "literaturfest", "theaterfest", "biennale"],
    "Theater": ["theater", "theatre", "stage", "performance", "schauspiel"],
    "Konzert": ["konzert", "musik", "concert", "live music", "livemusik", "gig"],
    "Kino": ["film", "kino", "cinema", "movie", "screening", "kurzfilm"],
    "Vortrag": ["vortrag", "diskussion", "talk", "panel", "lesung",
                "reading", "discussion", "q&a", "lecture"],
    "Essen": ["essen", "café", "cafe", "kneipe", "küfa", "kufa", "küche",
              "kueche", "food", "dinner", "brunch"],
    "Protest": ["protest", "aktion", "demo", "kundgebung", "pride march"],
    "Party": ["party", "tanz", "rave", "club", "drag", "barnight", "karaoke",
              "gogo", "disco", "dancefloor", "ball"],
    "Workshop": ["workshop", "seminar", "skillshare", "skill-share",
                 "training", "kurs", "tutorial", "klasse"],
    "Ausstellung": ["ausstellung", "galerie", "gallery", "kunst", "museum",
                    "museen", "exhibition", "vernissage"],
    "Markt": ["markt", "flohmarkt", "trödel", "troedel", "trödelmarkt",
              "wochenmarkt", "antikmarkt", "kunstmarkt", "fahrradmarkt"],
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
