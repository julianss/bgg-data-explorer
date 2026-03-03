#!/usr/bin/env python3
"""Ingest BGG ranked games into SQLite, enriching with mechanics/categories from the API."""

import csv
import os
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET
from urllib.request import Request, urlopen
from urllib.error import HTTPError

DB_PATH = "bgg.db"
CSV_PATH = "boardgames_ranks.csv"
API_BASE = "https://boardgamegeek.com/xmlapi2"
BATCH_SIZE = 20  # max IDs per API request
RATE_LIMIT_PAUSE = 1.0  # seconds between API calls

TOKEN = os.environ.get("BGG_API_TOKEN")
if not TOKEN:
    sys.exit("Set BGG_API_TOKEN environment variable")


def create_schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS games (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            year_published INTEGER,
            rank INTEGER,
            bayes_average REAL,
            average REAL,
            users_rated INTEGER,
            is_expansion INTEGER,
            min_players INTEGER,
            max_players INTEGER,
            playing_time INTEGER,
            min_playtime INTEGER,
            max_playtime INTEGER,
            min_age INTEGER,
            weight REAL,
            owned INTEGER,
            wanting INTEGER,
            wishing INTEGER,
            description TEXT
        );

        CREATE TABLE IF NOT EXISTS mechanics (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS game_mechanics (
            game_id INTEGER REFERENCES games(id),
            mechanic_id INTEGER REFERENCES mechanics(id),
            PRIMARY KEY (game_id, mechanic_id)
        );

        CREATE TABLE IF NOT EXISTS game_categories (
            game_id INTEGER REFERENCES games(id),
            category_id INTEGER REFERENCES categories(id),
            PRIMARY KEY (game_id, category_id)
        );

        CREATE TABLE IF NOT EXISTS families (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS game_families (
            game_id INTEGER REFERENCES games(id),
            family_id INTEGER REFERENCES families(id),
            PRIMARY KEY (game_id, family_id)
        );

        CREATE TABLE IF NOT EXISTS designers (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS game_designers (
            game_id INTEGER REFERENCES games(id),
            designer_id INTEGER REFERENCES designers(id),
            PRIMARY KEY (game_id, designer_id)
        );

        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    """)


def load_csv_ids(path):
    """Load game IDs with rank > 0 from the BGG CSV export."""
    ids = []
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rank = int(row["rank"])
            if rank > 0:
                ids.append(int(row["id"]))
    return ids


def fetch_batch(game_ids):
    """Fetch a batch of games from the BGG API, returns parsed XML root."""
    ids_str = ",".join(str(i) for i in game_ids)
    url = f"{API_BASE}/thing?id={ids_str}&type=boardgame&stats=1"
    req = Request(url, headers={"Authorization": f"Bearer {TOKEN}"})

    for attempt in range(3):
        try:
            with urlopen(req, timeout=30) as resp:
                return ET.parse(resp).getroot()
        except HTTPError as e:
            if e.code == 429:
                wait = 2 ** (attempt + 1)
                print(f"  Rate limited, waiting {wait}s...")
                time.sleep(wait)
            else:
                raise
        except Exception as e:
            if attempt < 2:
                print(f"  Retrying after error: {e}")
                time.sleep(2)
            else:
                raise
    return None


def parse_and_store(root, conn):
    """Parse XML response and insert into database."""
    if root is None:
        return 0

    count = 0
    for item in root.findall("item"):
        game_id = int(item.get("id"))

        name_el = item.find('name[@type="primary"]')
        name = name_el.get("value") if name_el is not None else "Unknown"

        def intval(tag):
            el = item.find(tag)
            if el is not None:
                try:
                    return int(el.get("value"))
                except (ValueError, TypeError):
                    pass
            return None

        def floatval(tag):
            el = item.find(tag)
            if el is not None:
                try:
                    return float(el.get("value"))
                except (ValueError, TypeError):
                    pass
            return None

        # Stats are nested under statistics/ratings
        stats = item.find("statistics/ratings")
        avg = bayes = weight = users_rated = owned = wanting = wishing = None
        rank = None
        if stats is not None:
            avg = floatval_el(stats, "average")
            bayes = floatval_el(stats, "bayesaverage")
            weight = floatval_el(stats, "averageweight")
            users_rated = intval_el(stats, "usersrated")
            owned = intval_el(stats, "owned")
            wanting = intval_el(stats, "wanting")
            wishing = intval_el(stats, "wishing")
            rank_el = stats.find('.//rank[@name="boardgame"]')
            if rank_el is not None:
                try:
                    rank = int(rank_el.get("value"))
                except (ValueError, TypeError):
                    pass

        desc_el = item.find("description")
        description = desc_el.text if desc_el is not None else None

        conn.execute("""
            INSERT OR REPLACE INTO games
            (id, name, year_published, rank, bayes_average, average, users_rated,
             is_expansion, min_players, max_players, playing_time, min_playtime,
             max_playtime, min_age, weight, owned, wanting, wishing, description)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            game_id, name, intval("yearpublished"), rank, bayes, avg, users_rated,
            0,  # we're filtering to non-expansions via rank>0
            intval("minplayers"), intval("maxplayers"),
            intval("playingtime"), intval("minplaytime"), intval("maxplaytime"),
            intval("minage"), weight, owned, wanting, wishing, description,
        ))

        # Links: mechanics, categories, families, designers
        for link in item.findall('link[@type="boardgamemechanic"]'):
            lid, lname = int(link.get("id")), link.get("value")
            conn.execute("INSERT OR IGNORE INTO mechanics (id, name) VALUES (?,?)", (lid, lname))
            conn.execute("INSERT OR IGNORE INTO game_mechanics (game_id, mechanic_id) VALUES (?,?)", (game_id, lid))

        for link in item.findall('link[@type="boardgamecategory"]'):
            lid, lname = int(link.get("id")), link.get("value")
            conn.execute("INSERT OR IGNORE INTO categories (id, name) VALUES (?,?)", (lid, lname))
            conn.execute("INSERT OR IGNORE INTO game_categories (game_id, category_id) VALUES (?,?)", (game_id, lid))

        for link in item.findall('link[@type="boardgamefamily"]'):
            lid, lname = int(link.get("id")), link.get("value")
            conn.execute("INSERT OR IGNORE INTO families (id, name) VALUES (?,?)", (lid, lname))
            conn.execute("INSERT OR IGNORE INTO game_families (game_id, family_id) VALUES (?,?)", (game_id, lid))

        for link in item.findall('link[@type="boardgamedesigner"]'):
            lid, lname = int(link.get("id")), link.get("value")
            conn.execute("INSERT OR IGNORE INTO designers (id, name) VALUES (?,?)", (lid, lname))
            conn.execute("INSERT OR IGNORE INTO game_designers (game_id, designer_id) VALUES (?,?)", (game_id, lid))

        count += 1

    return count


def floatval_el(parent, tag):
    el = parent.find(tag)
    if el is not None:
        try:
            return float(el.get("value"))
        except (ValueError, TypeError):
            pass
    return None


def intval_el(parent, tag):
    el = parent.find(tag)
    if el is not None:
        try:
            return int(el.get("value"))
        except (ValueError, TypeError):
            pass
    return None


def main():
    print("Loading game IDs from CSV...")
    all_ids = load_csv_ids(CSV_PATH)
    print(f"Found {len(all_ids)} ranked games")

    conn = sqlite3.connect(DB_PATH)
    create_schema(conn)

    # Find which IDs we already have
    existing = set(r[0] for r in conn.execute("SELECT id FROM games").fetchall())
    todo = [gid for gid in all_ids if gid not in existing]
    print(f"Already ingested: {len(existing)}, remaining: {len(todo)}")

    if not todo:
        print("Nothing to do!")
        conn.close()
        return

    batches = [todo[i:i + BATCH_SIZE] for i in range(0, len(todo), BATCH_SIZE)]
    total_done = 0

    for i, batch in enumerate(batches):
        try:
            root = fetch_batch(batch)
            count = parse_and_store(root, conn)
            total_done += count
            conn.commit()

            if (i + 1) % 50 == 0 or i == len(batches) - 1:
                print(f"  Batch {i+1}/{len(batches)}: {total_done} games ingested so far")

            time.sleep(RATE_LIMIT_PAUSE)
        except Exception as e:
            print(f"  Error on batch {i+1} (ids {batch[0]}-{batch[-1]}): {e}")
            conn.commit()
            time.sleep(5)

    print(f"\nDone! Ingested {total_done} games total.")

    # Record snapshot date
    from datetime import date
    conn.execute(
        "INSERT OR REPLACE INTO metadata (key, value) VALUES ('snapshot_date', ?)",
        (date.today().isoformat(),)
    )
    conn.commit()

    # Quick summary
    for table in ["games", "mechanics", "categories", "families", "designers"]:
        count = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        print(f"  {table}: {count} rows")

    conn.close()


if __name__ == "__main__":
    main()
