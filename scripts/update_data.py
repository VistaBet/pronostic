#!/usr/bin/env python3
"""Télécharge gratuitement les résultats et statistiques des clubs (première division) et des sélections.

Sources :
  - football-data.co.uk : 11 grands championnats (buts, corners, cartons) + 16 championnats
    supplémentaires (buts seulement).
  - github.com/martj42/international_results : tous les matchs internationaux (copie de secours).

Écrit : data/clubs.json  et  data/nations.csv
N'utilise que la bibliothèque standard de Python.
"""
import csv
import datetime
import io
import json
import os
import sys
import time
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(HERE, "..", "data"))
HISTORY_YEARS = 4          # nombre de saisons / années d'historique conservées
UA = "Mozilla/5.0 (compatible; pronostic-football/1.0)"

# (code du fichier, pays, nom du championnat) : première division uniquement.
MAIN = [
    ("E0", "Angleterre", "Premier League"),
    ("SC0", "Écosse", "Premiership"),
    ("D1", "Allemagne", "Bundesliga"),
    ("I1", "Italie", "Serie A"),
    ("SP1", "Espagne", "La Liga"),
    ("F1", "France", "Ligue 1"),
    ("N1", "Pays-Bas", "Eredivisie"),
    ("B1", "Belgique", "Jupiler Pro League"),
    ("P1", "Portugal", "Primeira Liga"),
    ("T1", "Turquie", "Süper Lig"),
    ("G1", "Grèce", "Super League"),
]
EXTRA = [
    ("ARG", "Argentine", "Primera División"),
    ("AUT", "Autriche", "Bundesliga"),
    ("BRA", "Brésil", "Série A"),
    ("CHN", "Chine", "Super League"),
    ("DNK", "Danemark", "Superliga"),
    ("FIN", "Finlande", "Veikkausliiga"),
    ("IRL", "Irlande", "Premier Division"),
    ("JPN", "Japon", "J1 League"),
    ("MEX", "Mexique", "Liga MX"),
    ("NOR", "Norvège", "Eliteserien"),
    ("POL", "Pologne", "Ekstraklasa"),
    ("ROU", "Roumanie", "Liga I"),
    ("RUS", "Russie", "Premier League"),
    ("SWE", "Suède", "Allsvenskan"),
    ("SWZ", "Suisse", "Super League"),
    ("USA", "États-Unis", "MLS"),
]
MAIN_URL = "https://www.football-data.co.uk/mmz4281/{season}/{code}.csv"
EXTRA_URL = "https://www.football-data.co.uk/new/{code}.csv"
NATIONS_URL = "https://raw.githubusercontent.com/martj42/international_results/master/results.csv"


def fetch_text(url, tries=3):
    """Renvoie le texte du fichier, ou None s'il n'existe pas / est inaccessible."""
    for attempt in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
            try:
                return raw.decode("utf-8-sig")
            except UnicodeDecodeError:
                return raw.decode("latin-1")
        except urllib.error.HTTPError as err:
            if err.code == 404:
                return None
        except Exception:
            pass
        time.sleep(2 * (attempt + 1))
    return None


def season_codes(today, n):
    start = today.year if today.month >= 7 else today.year - 1
    return ["%02d%02d" % ((start - i) % 100, (start - i + 1) % 100) for i in range(n)]


def parse_date(text):
    text = (text or "").strip()
    for fmt in ("%d/%m/%Y", "%d/%m/%y", "%Y-%m-%d"):
        try:
            return datetime.datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def to_int(value, maximum=100):
    try:
        number = int(float(str(value).strip()))
    except (ValueError, TypeError):
        return None
    return number if 0 <= number <= maximum else None


def clean_row(row):
    return {(k or "").strip(): (v or "").strip() for k, v in row.items() if k}


def parse_main(text):
    """Fichier d'un grand championnat : buts + corners + cartons."""
    out = []
    for raw in csv.DictReader(io.StringIO(text)):
        r = clean_row(raw)
        day = parse_date(r.get("Date"))
        home, away = r.get("HomeTeam"), r.get("AwayTeam")
        g1, g2 = to_int(r.get("FTHG"), 30), to_int(r.get("FTAG"), 30)
        if not (day and home and away) or g1 is None or g2 is None:
            continue
        stats = [to_int(r.get("HC"), 40), to_int(r.get("AC"), 40),
                 to_int(r.get("HY"), 15), to_int(r.get("AY"), 15),
                 to_int(r.get("HR"), 5), to_int(r.get("AR"), 5)]
        out.append((day, home, away, g1, g2, stats))
    return out


def parse_extra(text, since):
    """Fichier d'un championnat supplémentaire : buts seulement."""
    out = []
    for raw in csv.DictReader(io.StringIO(text)):
        r = clean_row(raw)
        day = parse_date(r.get("Date"))
        home = r.get("Home") or r.get("HomeTeam")
        away = r.get("Away") or r.get("AwayTeam")
        g1, g2 = to_int(r.get("HG") or r.get("FTHG"), 30), to_int(r.get("AG") or r.get("FTAG"), 30)
        if not (day and home and away) or g1 is None or g2 is None or day < since:
            continue
        out.append((day, home, away, g1, g2, [None] * 6))
    return out


def main():
    today = datetime.date.today()
    since = today.replace(year=today.year - HISTORY_YEARS)
    leagues, collected, report = [], [], []

    for code, country, name in MAIN:
        rows, missing = [], []
        for season in season_codes(today, HISTORY_YEARS):
            text = fetch_text(MAIN_URL.format(season=season, code=code))
            if text is None:
                missing.append(season)
                continue
            rows += [r for r in parse_main(text) if r[0] >= since]
        with_stats = sum(1 for r in rows if r[5][0] is not None and r[5][2] is not None)
        if rows:
            leagues.append({"code": code, "country": country, "name": name,
                            "stats": with_stats >= 50, "matches": len(rows)})
            collected.append(rows)
        report.append("%s %s : %d matchs (%d avec corners/cartons)%s" % (
            country, name, len(rows), with_stats,
            " ; saisons absentes : " + ",".join(missing) if missing else ""))

    for code, country, name in EXTRA:
        text = fetch_text(EXTRA_URL.format(code=code))
        rows = parse_extra(text, since) if text else []
        if rows:
            leagues.append({"code": code, "country": country, "name": name, "stats": False, "matches": len(rows)})
            collected.append(rows)
        report.append("%s %s : %d matchs (buts seulement)" % (country, name, len(rows)) + ("" if text else " ; fichier introuvable"))

    # Noms d'équipes présents dans plusieurs championnats : on ajoute le pays pour les distinguer.
    seen = {}
    for idx, rows in enumerate(collected):
        for r in rows:
            for team in (r[1], r[2]):
                seen.setdefault(team.strip(), set()).add(idx)
    clash = {t for t, where in seen.items() if len(where) > 1}

    matches = []
    for idx, rows in enumerate(collected):
        country = leagues[idx]["country"]
        label = lambda t: ("%s (%s)" % (t.strip(), country)) if t.strip() in clash else t.strip()
        for day, home, away, g1, g2, st in rows:
            matches.append([day.isoformat(), label(home), label(away), g1, g2] + st + [idx])
    matches.sort(key=lambda m: m[0])

    if len(matches) < 500:
        print("ERREUR : trop peu de matchs téléchargés (%d). Les fichiers existants sont conservés." % len(matches))
        print("\n".join(report))
        return 1

    os.makedirs(DATA_DIR, exist_ok=True)
    payload = {"updated": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
               "history_years": HISTORY_YEARS, "leagues": leagues, "matches": matches, "report": report}
    with open(os.path.join(DATA_DIR, "clubs.json"), "w", encoding="utf-8") as fh:
        json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))

    nations = fetch_text(NATIONS_URL)
    if nations and len(nations) > 1_000_000:
        with open(os.path.join(DATA_DIR, "nations.csv"), "w", encoding="utf-8", newline="") as fh:
            fh.write(nations)
    else:
        report.append("Sélections : copie de secours non mise à jour.")

    print("OK : %d matchs de clubs, %d championnats." % (len(matches), len(leagues)))
    print("\n".join(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
