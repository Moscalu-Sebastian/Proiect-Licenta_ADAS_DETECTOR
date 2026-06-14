"""
Persistenta aplicatiei in SQLite (adas.db). Doua tabele: setari (config, valori
JSON) si videoclipuri (istoric). config-ul ramane dict in memorie, incarcat/salvat
din DB. La prima rulare migram vechiul config.json daca exista.
"""

import os
import json
import sqlite3
from datetime import datetime, timedelta


def _dir_app():
    return os.environ.get(
        "ADAS_BASE_DIR",
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )


def cale_db():
    return os.path.join(_dir_app(), "adas.db")


def _con():
    con = sqlite3.connect(cale_db())
    con.row_factory = sqlite3.Row
    return con


def init_db():
    """Creeaza tabelele daca nu exista."""
    with _con() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS setari (
                cheie   TEXT PRIMARY KEY,
                valoare TEXT NOT NULL
            )
        """)
        con.execute("""
            CREATE TABLE IF NOT EXISTS videoclipuri (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                cale          TEXT UNIQUE NOT NULL,
                ultima_rulare TEXT NOT NULL,
                nr_rulari     INTEGER NOT NULL DEFAULT 1
            )
        """)


# ------------------------------------------------------------------ #
# Setari (config-ul aplicatiei) - tabel cheie/valoare, valori JSON
# ------------------------------------------------------------------ #

def incarca_setari():
    """Returneaza un dict cu toate setarile (valorile sunt JSON-decodate)."""
    with _con() as con:
        randuri = con.execute("SELECT cheie, valoare FROM setari").fetchall()
    out = {}
    for r in randuri:
        try:
            out[r["cheie"]] = json.loads(r["valoare"])
        except Exception:
            out[r["cheie"]] = r["valoare"]
    return out


def salveaza_setari(dictionar):
    """Scrie (upsert) toate perechile cheie -> valoare din dict (JSON-encode)."""
    with _con() as con:
        for cheie, val in dictionar.items():
            con.execute("""
                INSERT INTO setari (cheie, valoare) VALUES (?, ?)
                ON CONFLICT(cheie) DO UPDATE SET valoare = excluded.valoare
            """, (cheie, json.dumps(val, ensure_ascii=False)))


# ------------------------------------------------------------------ #
# Istoric videoclipuri
# ------------------------------------------------------------------ #

def adauga_video(cale):
    """Adauga/actualizeaza un video in istoric (incrementeaza nr_rulari)."""
    acum = datetime.now().isoformat(timespec="seconds")
    with _con() as con:
        con.execute("""
            INSERT INTO videoclipuri (cale, ultima_rulare, nr_rulari) VALUES (?, ?, 1)
            ON CONFLICT(cale) DO UPDATE SET
                ultima_rulare = excluded.ultima_rulare,
                nr_rulari     = nr_rulari + 1
        """, (cale, acum))


def lista_videoclipuri(limita=100):
    """Lista de dict-uri {cale, ultima_rulare, nr_rulari}, cele mai recente primele."""
    with _con() as con:
        randuri = con.execute("""
            SELECT cale, ultima_rulare, nr_rulari FROM videoclipuri
            ORDER BY ultima_rulare DESC LIMIT ?
        """, (limita,)).fetchall()
    return [dict(r) for r in randuri]


def sterge_video(cale):
    with _con() as con:
        con.execute("DELETE FROM videoclipuri WHERE cale = ?", (cale,))


# ------------------------------------------------------------------ #
# Migrare din config.json vechi (o singura data)
# ------------------------------------------------------------------ #

def migreaza_din_json(cale_json):
    """Daca exista un config.json vechi, ii muta continutul in DB si il redenumeste."""
    if not os.path.exists(cale_json):
        return
    try:
        with open(cale_json, "r", encoding="utf-8") as f:
            date = json.load(f)
    except Exception:
        return

    istoric = date.pop("istoric_video", []) or []
    date.pop("istoric_migrat", None)
    salveaza_setari(date)

    base = datetime.now()
    with _con() as con:
        for i, cale in enumerate(istoric):
            # i=0 (cel mai recent) primeste cel mai mare timestamp -> ordinea se pastreaza
            ts = (base - timedelta(seconds=i)).isoformat(timespec="seconds")
            con.execute("""
                INSERT INTO videoclipuri (cale, ultima_rulare, nr_rulari) VALUES (?, ?, 1)
                ON CONFLICT(cale) DO NOTHING
            """, (cale, ts))

    # Redenumim config.json ca sa nu se mai migreze si sa nu mai fie folosit
    try:
        os.replace(cale_json, cale_json + ".migrat")
    except Exception:
        pass
