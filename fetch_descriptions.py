#!/usr/bin/env python3
"""Fetch mechanic and category descriptions from the geekdo JSON API."""

import json
import re
import sqlite3
import time
import urllib.request

DB_PATH = "bgg.db"
API_URL = "https://api.geekdo.com/api/geekitems?objectid={id}&objecttype=property"


def strip_html(html):
    """Strip HTML tags and decode entities."""
    text = re.sub(r"<[^>]+>", "", html)
    text = text.replace("&quot;", '"').replace("&amp;", "&")
    text = text.replace("&lt;", "<").replace("&gt;", ">")
    text = text.replace("&nbsp;", " ")
    return text.strip()


def fetch_description(obj_id):
    url = API_URL.format(id=obj_id)
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read())
    item = data.get("item", {})
    raw = item.get("description", "")
    return strip_html(raw) if raw else ""


def main():
    conn = sqlite3.connect(DB_PATH)

    # Add description columns if missing
    for table in ("mechanics", "categories"):
        cols = [r[1] for r in conn.execute(f"PRAGMA table_info({table})")]
        if "description" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN description TEXT")
            print(f"Added description column to {table}")

    for table in ("mechanics", "categories"):
        rows = conn.execute(f"SELECT id, name FROM {table} ORDER BY id").fetchall()
        print(f"\nFetching {len(rows)} {table} descriptions...")

        for i, (obj_id, name) in enumerate(rows):
            try:
                desc = fetch_description(obj_id)
                conn.execute(
                    f"UPDATE {table} SET description = ? WHERE id = ?",
                    (desc, obj_id),
                )
                status = f"{len(desc)} chars" if desc else "EMPTY"
                print(f"  [{i+1}/{len(rows)}] {name}: {status}")
                time.sleep(0.3)
            except Exception as e:
                print(f"  [{i+1}/{len(rows)}] {name}: ERROR - {e}")

            if (i + 1) % 50 == 0:
                conn.commit()

        conn.commit()

    # Summary
    for table in ("mechanics", "categories"):
        total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        with_desc = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE description IS NOT NULL AND description != ''"
        ).fetchone()[0]
        print(f"\n{table}: {with_desc}/{total} have descriptions")

    conn.close()
    print("\nDone!")


if __name__ == "__main__":
    main()
