"""Assign each event a single 'genre' (scene / direction).

Genres: Kultur, Polit, Queer, Kink.

The genre defaults to the source's scene, but distinctive keywords in the
event override it -- so a kink or queer event from an otherwise political
source still gets the right genre. Exactly one genre per event.
"""

from __future__ import annotations

# Override priority: a more specific scene wins over a general one.
PRIORITY = ["Kink", "Queer", "Polit", "Kultur"]

# Default genre per source (used when no keyword override matches).
SOURCE_DEFAULT = {
    "Stressfaktor": "Polit",
    "Siegessäule": "Queer",
    "Quälgeist": "Kink",
    "Karada House": "Kink",
    "Berlin Bühnen": "Kultur",
    "Donau115": "Kultur",
    "Silverfuture": "Queer",
}
DEFAULT_GENRE = "Kultur"

# Distinctive keywords that override the source default (substring, lower).
KEYWORDS = {
    "Kink": [
        "kink", "fetisch", "fetish", "bdsm", "shibari", "bondage", "dungeon",
        "sex-positive", "sexpositive", "sexpositiv", "darkroom", "dark room",
        "cruising", "playparty", "play party", "munch ", "kinky", "latex",
        "spanking", "puppy play", "recon",
    ],
    "Queer": [
        "queer", "lgbtq", "lgbtiq", "lgbti", "schwul", "lesb", "drag",
        "csd", "pride", "flinta", "dyke", "gay ", "transgender", "trans*",
        "non-binary", "nonbinary", "sapphic", "homosexuell", "regenbogen",
    ],
    "Polit": [
        "antifa", "antifaschis", "demonstr", "kundgebung", "protest",
        "streik", "gewerkschaft", "besetzung", "räumung", "gentrifiz",
        "kapitalismus", "antikapital", "solidar", "soli-", "aktivis",
        "palästina", "palestine", "antira", "antirassis", "feminismus",
        "feminist", "klimagerecht", "klimacamp", "bleiberecht", "abschiebung",
        "vokü", "volxküche", "plenum", "gedenken", "no border", "queerfeminis",
    ],
}


def genre_for(source_name: str | None, text: str) -> str:
    low = (text or "").lower()
    for genre in PRIORITY:
        for kw in KEYWORDS.get(genre, []):
            if kw in low:
                return genre
    return SOURCE_DEFAULT.get(source_name or "", DEFAULT_GENRE)
