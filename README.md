# 📅 Eventkalender

Ein kleines Tool, das Veranstaltungen von verschiedenen Websites einsammelt
und als übersichtlichen Feed anzeigt — abrufbar im Browser auf **iPhone und
Mac** (und jedem anderen Gerät).

Die Veranstaltungen sind:

- ✅ nach **Termin sortiert** (gruppiert nach Tag),
- 🏷️ mit **Tags** versehen (z. B. Musik, Kunst, Stadt),
- 🖼️ mit **Bild** (falls vorhanden),
- 🔗 jede Karte ist ein **Link zur Original-Seite** der Veranstaltung.

Alles läuft **kostenlos und automatisch** über GitHub — du musst dafür
keinen eigenen Server betreiben und nichts auf deinem Mac laufen lassen.

---

## 🚀 So nimmst du es in Betrieb (einmalig, ca. 2 Minuten)

> Die Programm-Dateien sind bereits fertig. Du musst nur GitHub erlauben,
> daraus eine Webseite zu machen.

1. Öffne dein Repository auf **github.com**.
2. Klicke oben auf **Settings** (Einstellungen).
3. Links im Menü auf **Pages**.
4. Bei **„Build and deployment" → „Source"** wähle **GitHub Actions** aus.
5. Fertig. Gehe oben auf den Tab **Actions**, öffne den Lauf
   *„Eventkalender aktualisieren & veröffentlichen"* und klicke ggf. auf
   **Run workflow**, um ihn sofort zu starten.

Nach ein bis zwei Minuten findest du den **Link zu deinem Feed** unter
**Settings → Pages** (etwas wie
`https://flipssssss.github.io/eventkalender/`).

> 📱 **Tipp fürs iPhone:** Öffne den Link in Safari, tippe auf das
> Teilen-Symbol und „Zum Home-Bildschirm hinzufügen". Dann hast du den
> Eventkalender wie eine App auf dem Startbildschirm.

Der Feed aktualisiert sich danach **automatisch jede Nacht**. Du kannst ihn
über **Actions → Run workflow** auch jederzeit von Hand aktualisieren.

---

## ✅ Bereits eingerichtete Quellen

| Quelle | Methode | Status |
| --- | --- | --- |
| **Stressfaktor** (Berlin) | iCal-Feed von radar.squat.net | ✅ eingerichtet |
| **Berlin Bühnen** – nur HAU (Hebbel am Ufer), Maxim Gorki, Volksbühne | Webseite, gefiltert nach Bühne | 🟡 wird beim 1. Lauf geprüft |

> Bei „Berlin Bühnen" lädt die Seite ihre Termine teils per JavaScript nach.
> Der Ausleser sammelt beim ersten Lauf auf GitHub automatisch technische
> Infos (in `docs/data/_debug/`), mit denen die genaue Anbindung an die
> offizielle Export-API fertiggestellt wird. Falls dort zunächst keine
> Veranstaltungen erscheinen, ist das erwartet — kurz Bescheid geben.

---

## ➕ Weitere Veranstaltungs-Websites hinzufügen

Trage neue Quellen in die Datei [`sources.yml`](sources.yml) ein:

```yaml
sources:
  - url: https://www.beispielstadt.de/veranstaltungen
    name: Stadt Beispielstadt      # Anzeigename (optional)
    tags: [Beispielstadt]          # Tags für alle Events dieser Quelle (optional)

  - url: https://www.konzerthaus-xy.de/programm
    name: Konzerthaus XY
    tags: [Musik]
```

Speichern, committen — fertig. Beim nächsten (automatischen oder manuellen)
Lauf werden die neuen Quellen mit ausgelesen.

### Funktioniert das bei jeder Website?

Das Tool nutzt einen **generischen Ausleser**, der dem weit verbreiteten
Standard *schema.org/Event* folgt. **Sehr viele** Veranstaltungs-, Theater-,
Konzert- und Stadt-Websites liefern ihre Termine in genau diesem Format —
dort funktioniert es **ohne weitere Programmierung**.

Manche Seiten tun das nicht. Wenn nach einem Lauf von einer Quelle keine
(oder zu wenige) Veranstaltungen erscheinen, braucht diese Seite einen
kleinen, eigens geschriebenen Ausleser. Sag einfach Bescheid und nenne die
Adresse — so etwas ist schnell ergänzt (siehe
[`scrapers/demo.py`](scrapers/demo.py) als kleinstes Beispiel).

---

## 🧪 Lokal testen (optional, nur für Neugierige)

Wenn du es auf dem Mac selbst ausprobieren willst:

```bash
pip install -r requirements.txt
python aggregate.py          # erzeugt docs/data/events.json

# Feed im Browser ansehen:
python -m http.server -d docs 8000
# -> http://localhost:8000 öffnen
```

---

## 🗂️ Was steckt wo? (Kurzübersicht)

| Datei / Ordner | Bedeutung |
| --- | --- |
| `sources.yml` | **Hier trägst du die Websites ein.** |
| `aggregate.py` | Sammelt alle Events, sortiert sie, schreibt die Daten. |
| `scrapers/` | Die „Ausleser" (generisch + Beispiel). |
| `docs/` | Die Feed-Webseite (das, was du im Browser siehst). |
| `docs/data/events.json` | Die gesammelten Veranstaltungen (wird automatisch erzeugt). |
| `.github/workflows/` | Die Automatik, die alles regelmäßig ausführt. |

---

Viel Freude mit deinem Eventkalender! 🎉
