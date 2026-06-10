"""Solve the Anubis proof-of-work challenge (TecharoHQ/anubis).

Anubis shows an interstitial page to non-JavaScript clients and expects a
small SHA-256 proof of work before serving the real page -- exactly the
computation a normal web browser performs automatically when a person
opens the site. We replicate that here so the aggregator can read pages
that are publicly visible to any browser but gated behind Anubis.

Challenge format (Anubis 1.25, algorithm "fast")::

    <script id="anubis_challenge" type="application/json">
    {"rules":{"algorithm":"fast","difficulty":2},
     "challenge":{"id":"...","randomData":"<hex>","difficulty":2, ...}}
    </script>

The proof is a nonce such that ``sha256(randomData + nonce)`` (hex) starts
with ``difficulty`` zero nibbles. It is submitted to the pass-challenge
endpoint, which sets an auth cookie; the original request then succeeds.
"""

from __future__ import annotations

import hashlib
import json
import time
from urllib.parse import urlencode, urlparse

import requests
from bs4 import BeautifulSoup

# A normal browser UA -- Anubis binds the challenge to the UA, so it must
# stay identical across the challenge, the proof submission and the retry.
BROWSER_UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)
PASS_ENDPOINT = "/.within.website/x/cmd/anubis/api/pass-challenge"
MAX_NONCE = 20_000_000


class AnubisSession:
    """A requests session that transparently solves Anubis challenges."""

    def __init__(self, user_agent: str = BROWSER_UA, timeout: int = 25):
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,*/*"}
        )
        self.timeout = timeout
        self.notes: list[str] = []

    def get(self, url: str, headers: dict | None = None) -> requests.Response:
        response = self.session.get(url, headers=headers, timeout=self.timeout)
        if 'id="anubis_challenge"' not in response.text:
            return response
        try:
            self._solve(response.text, url)
        except Exception as exc:  # noqa: BLE001
            self.notes.append(f"Anubis-Löser-Fehler: {exc}")
            return response
        return self.session.get(url, headers=headers, timeout=self.timeout)

    # -- internals -------------------------------------------------------

    def _solve(self, html: str, url: str) -> None:
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("script", id="anubis_challenge")
        if not tag:
            raise RuntimeError("kein anubis_challenge-Block gefunden")
        data = json.loads(tag.string or tag.get_text())
        rules = data.get("rules") or {}
        chal = data.get("challenge") or {}

        difficulty = int(rules.get("difficulty") or chal.get("difficulty") or 4)
        seed = chal.get("randomData") or chal.get("challenge") or ""
        chal_id = chal.get("id", "")
        if not seed:
            raise RuntimeError("kein randomData im Challenge")

        nonce, digest, elapsed = self._proof_of_work(seed, difficulty)

        base = f"{urlparse(url).scheme}://{urlparse(url).netloc}"
        params = {
            "id": chal_id,
            "response": digest,
            "nonce": nonce,
            "redir": url,
            "elapsedTime": elapsed,
        }
        passed = self.session.get(
            base + PASS_ENDPOINT + "?" + urlencode(params),
            timeout=self.timeout,
            allow_redirects=True,
        )
        self.notes.append(
            f"PoW: difficulty={difficulty} nonce={nonce} hash={digest[:12]}… "
            f"pass-status={passed.status_code} "
            f"cookies={list(self.session.cookies.keys())}"
        )

    @staticmethod
    def _proof_of_work(seed: str, difficulty: int) -> tuple[int, str, int]:
        prefix = "0" * difficulty
        start = time.time()
        nonce = 0
        while nonce < MAX_NONCE:
            digest = hashlib.sha256(f"{seed}{nonce}".encode()).hexdigest()
            if digest.startswith(prefix):
                elapsed = max(1, int((time.time() - start) * 1000))
                return nonce, digest, elapsed
            nonce += 1
        raise RuntimeError(f"keine Lösung < {MAX_NONCE} Versuche")
