#!/usr/bin/env python3
"""Rephrase mechanic descriptions using Haiku to create short original summaries."""

import json
import os
import sqlite3
import time
import urllib.request

DB_PATH = "bgg.db"
API_KEY = os.environ["ANTHROPIC_API_KEY"]
MODEL = "claude-haiku-4-5-20251001"
BATCH_SIZE = 40  # mechanics per API call


def call_haiku(prompt, system=""):
    data = {
        "model": MODEL,
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        data["system"] = system
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(data).encode(),
        headers={
            "x-api-key": API_KEY,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
    )
    resp = urllib.request.urlopen(req, timeout=60)
    result = json.loads(resp.read())
    print(f"  Usage: {result['usage']}")
    return result["content"][0]["text"]


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # Add summary column if needed
    cols = [r[1] for r in conn.execute("PRAGMA table_info(mechanics)")]
    if "summary" not in cols:
        conn.execute("ALTER TABLE mechanics ADD COLUMN summary TEXT")
        print("Added summary column")

    rows = conn.execute(
        "SELECT id, name, description FROM mechanics WHERE description != '' ORDER BY id"
    ).fetchall()
    print(f"Processing {len(rows)} mechanics in batches of {BATCH_SIZE}")

    system = (
        "You summarize board game mechanic descriptions. "
        "For each mechanic, write a 1-2 sentence summary (max 40 words) in your own words. "
        "Be concise and clear. A non-gamer should understand the gist. "
        "Reply ONLY with a JSON object mapping mechanic ID to summary string, no markdown."
    )

    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        print(f"\nBatch {i // BATCH_SIZE + 1} ({len(batch)} mechanics)...")

        entries = []
        for r in batch:
            entries.append(f'ID {r["id"]} "{r["name"]}": {r["description"]}')

        prompt = "Summarize each mechanic:\n\n" + "\n\n".join(entries)

        text = call_haiku(prompt, system)

        # Parse JSON response
        # Strip markdown fences if present
        text = text.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]

        try:
            summaries = json.loads(text)
        except json.JSONDecodeError:
            print(f"  ERROR: Could not parse JSON, saving raw response")
            print(text[:200])
            continue

        updated = 0
        for r in batch:
            key = str(r["id"])
            if key in summaries:
                conn.execute(
                    "UPDATE mechanics SET summary = ? WHERE id = ?",
                    (summaries[key], r["id"]),
                )
                updated += 1

        conn.commit()
        print(f"  Updated {updated}/{len(batch)}")
        time.sleep(1)

    # Final check
    total = conn.execute("SELECT COUNT(*) FROM mechanics").fetchone()[0]
    with_summary = conn.execute(
        "SELECT COUNT(*) FROM mechanics WHERE summary IS NOT NULL AND summary != ''"
    ).fetchone()[0]
    print(f"\nDone! {with_summary}/{total} mechanics have summaries")

    # Show a few examples
    for r in conn.execute("SELECT name, summary FROM mechanics LIMIT 5"):
        print(f"  {r[0]}: {r[1]}")

    conn.close()


if __name__ == "__main__":
    main()
