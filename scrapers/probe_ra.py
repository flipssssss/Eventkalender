"""One-off probe: can we read a public RA following list?

RA HTML profile pages usually 403 to bots; the GraphQL endpoint is open but
private data (who you follow) is normally login-gated. This checks both for the
given profile and dumps whatever is reachable.
"""

from __future__ import annotations

import json
import pathlib
import re
from typing import Iterable

import requests

from .base import BaseScraper, Event

DEBUG_DIR = pathlib.Path(__file__).resolve().parents[1] / "docs" / "data" / "_debug"
SLUG = "flipss"
BROWSER = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,*/*;q=0.8",
    "Accept-Language": "en;q=0.9,de;q=0.8",
}
GQL_HEADERS = {
    **BROWSER, "Accept": "application/json", "Content-Type": "application/json",
    "Referer": "https://ra.co/", "Origin": "https://ra.co",
    "ra-content-language": "en",
}


class ProbeRaScraper(BaseScraper):
    name = "Probe RA"

    def fetch_events(self) -> Iterable[Event]:
        out = [self._html(), self._graphql()]
        try:
            DEBUG_DIR.mkdir(parents=True, exist_ok=True)
            (DEBUG_DIR / "probe-ra.txt").write_text("\n\n".join(out), encoding="utf-8")
        except OSError:
            pass
        return []

    def _html(self) -> str:
        res = []
        for path in (f"/profile/{SLUG}", f"/profile/{SLUG}/following",
                     f"/u/{SLUG}"):
            url = "https://ra.co" + path
            try:
                r = requests.get(url, headers=BROWSER, timeout=25)
            except requests.RequestException as exc:
                res.append(f"{path}: FEHLER {exc}")
                continue
            note = f"{path}: status={r.status_code} len={len(r.text)}"
            if r.status_code == 200:
                m = re.search(r'id="__NEXT_DATA__"[^>]*>(.*?)</script>', r.text, re.S)
                if m:
                    try:
                        data = json.loads(m.group(1))
                        flat = json.dumps(data)
                        note += (f"\n  __NEXT_DATA__: ja | 'following' enthalten: "
                                 f"{'ollowing' in flat}\n  promoter/club/dj-Slugs: "
                                 + str(sorted(set(re.findall(
                                     r'/(?:promoters|clubs|dj|labels)/[\w\-]+', flat)))[:15]))
                    except ValueError:
                        note += "\n  __NEXT_DATA__: nicht parsebar"
            res.append(note)
        return "### HTML\n" + "\n".join(res)

    def _graphql(self) -> str:
        q = ('query($slug:String!){ user(slug:$slug){ id username '
             'followingCount } }')
        try:
            r = requests.post("https://ra.co/graphql",
                              data=json.dumps({"query": q, "variables": {"slug": SLUG}}),
                              headers=GQL_HEADERS, timeout=25)
            return f"### GraphQL user(slug)\nstatus={r.status_code}\n{r.text[:400]}"
        except requests.RequestException as exc:
            return f"### GraphQL\nFEHLER {exc}"
