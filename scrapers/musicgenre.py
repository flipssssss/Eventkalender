"""Assign a coarse music genre to concerts (shown after the "Konzert" tag).

Deliberately broad buckets -- Jazz, Punk, Hip-Hop, Techno, House, Electro,
Rock, Metal, Pop, Klassik, Soul/Funk, Reggae, Folk, Indie -- not micro-genres.
A source default wins (e.g. a jazz club is always Jazz); otherwise keywords in
the title/description decide. Returns None when nothing fits.
"""

from __future__ import annotations

# Source -> fixed music genre (the venue's profile).
SOURCE_MUSIC = {
    "A-Trane": "Jazz",
    "B-flat": "Jazz",
    "Donau115": "Jazz",
    "visitBerlin Jazz": "Jazz",
    "askapunk": "Punk",
}

# Checked top to bottom; first hit wins. Keep buckets broad.
_KEYWORDS = [
    ("Jazz", ("jazz", "bebop", "swing", "improvis", "bigband", "big band")),
    ("Punk", ("punk", "hardcore", "oi!", "streetpunk", "ska-punk", "crust")),
    ("Metal", ("metal", "doom", "grindcore", "death-metal", "black metal")),
    ("Hip-Hop", ("hip hop", "hip-hop", "hiphop", "rap", "trap", "cypher")),
    ("Techno", ("techno", "tekno", "acid")),
    ("House", ("house", "disco")),
    ("Electro", ("electro", "electronic", "drum and bass", "drum'n'bass",
                 "dnb", "dubstep", "edm", "ambient", "synth")),
    ("Reggae", ("reggae", "dancehall", "dub ", "ragga")),
    ("Soul/Funk", ("soul", "funk", "r&b", "rnb", "rhythm and blues")),
    ("Klassik", ("klassik", "classical", "sinfon", "orchester", "kammermusik",
                 "philharmon", "barock", "oper", "chor ")),
    ("Folk", ("folk", "singer-songwriter", "liedermacher", "americana",
              "bluegrass", "chanson")),
    ("Blues", ("blues",)),
    ("Indie", ("indie", "shoegaze", "post-rock")),
    ("Rock", ("rock", "garage", "psych", "stoner")),
    ("Pop", ("pop", "synthpop", "dreampop")),
    ("Schlager", ("schlager",)),
]


def music_genre_for(source_name: str | None, text: str) -> str | None:
    if source_name in SOURCE_MUSIC:
        return SOURCE_MUSIC[source_name]
    low = (text or "").lower()
    for genre, kws in _KEYWORDS:
        if any(k in low for k in kws):
            return genre
    return None
