import sqlite3
import math
import os
from flask import Flask, g, jsonify, request, send_from_directory

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "bgg.db")
STATIC_DIR = os.path.join(BASE_DIR, "frontend", "dist")

app = Flask(__name__, static_folder=STATIC_DIR, static_url_path="")


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA journal_mode=WAL")
    return g.db


@app.teardown_appcontext
def close_db(exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


# ---------- helpers ----------

def rows_to_dicts(rows):
    return [dict(r) for r in rows]


def int_param(name, default=None):
    v = request.args.get(name)
    if v is None:
        return default
    try:
        return int(v)
    except ValueError:
        return default


def float_param(name, default=None):
    v = request.args.get(name)
    if v is None:
        return default
    try:
        return float(v)
    except ValueError:
        return default


@app.route("/api/meta")
def api_meta():
    db = get_db()
    row = db.execute("SELECT value FROM metadata WHERE key = 'snapshot_date'").fetchone()
    snapshot_date = row[0] if row else None
    game_count = db.execute("SELECT COUNT(*) FROM games").fetchone()[0]
    return jsonify({"snapshot_date": snapshot_date, "game_count": game_count})


def build_game_filter(prefix="g"):
    """Build WHERE clauses + params from standard filter query args."""
    clauses = []
    params = []
    min_year = int_param("min_year")
    max_year = int_param("max_year")
    min_weight = float_param("min_weight")
    max_weight = float_param("max_weight")
    min_rating = float_param("min_rating")
    min_users = int_param("min_users_rated")
    if min_year is not None:
        clauses.append(f"{prefix}.year_published >= ?")
        params.append(min_year)
    if max_year is not None:
        clauses.append(f"{prefix}.year_published <= ?")
        params.append(max_year)
    if min_weight is not None:
        clauses.append(f"{prefix}.weight >= ?")
        params.append(min_weight)
    if max_weight is not None:
        clauses.append(f"{prefix}.weight <= ?")
        params.append(max_weight)
    if min_rating is not None:
        clauses.append(f"{prefix}.average >= ?")
        params.append(min_rating)
    if min_users is not None:
        clauses.append(f"{prefix}.users_rated >= ?")
        params.append(min_users)
    return clauses, params


# ---------- basic endpoints ----------

@app.route("/api/mechanics")
def api_mechanics():
    db = get_db()
    rows = db.execute("""
        SELECT m.id, m.name, COUNT(gm.game_id) as game_count
        FROM mechanics m
        JOIN game_mechanics gm ON gm.mechanic_id = m.id
        GROUP BY m.id
        ORDER BY game_count DESC
    """).fetchall()
    return jsonify(rows_to_dicts(rows))


@app.route("/api/categories")
def api_categories():
    db = get_db()
    rows = db.execute("""
        SELECT c.id, c.name, COUNT(gc.game_id) as game_count
        FROM categories c
        JOIN game_categories gc ON gc.category_id = c.id
        GROUP BY c.id
        ORDER BY game_count DESC
    """).fetchall()
    return jsonify(rows_to_dicts(rows))


@app.route("/api/filters/ranges")
def api_filter_ranges():
    db = get_db()
    row = db.execute("""
        SELECT
            MIN(year_published) as min_year,
            MAX(year_published) as max_year,
            ROUND(MIN(weight), 1) as min_weight,
            ROUND(MAX(weight), 1) as max_weight,
            ROUND(MIN(average), 1) as min_rating,
            ROUND(MAX(average), 1) as max_rating,
            MIN(users_rated) as min_users_rated,
            MAX(users_rated) as max_users_rated
        FROM games
        WHERE year_published IS NOT NULL
    """).fetchone()
    return jsonify(dict(row))


# ---------- mechanic co-occurrence ----------

@app.route("/api/mechanic-cooccurrence")
def api_mechanic_cooccurrence():
    db = get_db()
    top_n = int_param("top_n", 25)
    clauses, params = build_game_filter("g")
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""

    # Get top N mechanics by game count (within filter)
    top_mechs = db.execute(f"""
        SELECT m.id, m.name, COUNT(DISTINCT gm.game_id) as cnt
        FROM mechanics m
        JOIN game_mechanics gm ON gm.mechanic_id = m.id
        JOIN games g ON g.id = gm.game_id
        {where}
        GROUP BY m.id
        ORDER BY cnt DESC
        LIMIT ?
    """, params + [top_n]).fetchall()

    mech_ids = [r["id"] for r in top_mechs]
    mech_names = [r["name"] for r in top_mechs]

    if not mech_ids:
        return jsonify({"mechanics": [], "matrix": []})

    placeholders = ",".join("?" * len(mech_ids))

    # Co-occurrence: count games that have both mechanic i and mechanic j
    mech_clauses = [
        f"gm1.mechanic_id IN ({placeholders})",
        f"gm2.mechanic_id IN ({placeholders})"
    ]
    all_clauses = clauses + mech_clauses
    cooc_where = "WHERE " + " AND ".join(all_clauses)
    rows = db.execute(f"""
        SELECT gm1.mechanic_id as m1, gm2.mechanic_id as m2, COUNT(DISTINCT gm1.game_id) as cnt
        FROM game_mechanics gm1
        JOIN game_mechanics gm2 ON gm1.game_id = gm2.game_id AND gm1.mechanic_id < gm2.mechanic_id
        JOIN games g ON g.id = gm1.game_id
        {cooc_where}
        GROUP BY gm1.mechanic_id, gm2.mechanic_id
    """, params + mech_ids + mech_ids).fetchall()

    # Build symmetric matrix
    idx = {mid: i for i, mid in enumerate(mech_ids)}
    n = len(mech_ids)
    matrix = [[0] * n for _ in range(n)]
    for r in rows:
        i, j = idx.get(r["m1"]), idx.get(r["m2"])
        if i is not None and j is not None:
            matrix[i][j] = r["cnt"]
            matrix[j][i] = r["cnt"]

    # Diagonal = self count
    self_clauses = clauses + [f"gm.mechanic_id IN ({placeholders})"]
    self_where = "WHERE " + " AND ".join(self_clauses)
    self_counts = db.execute(f"""
        SELECT gm.mechanic_id as mid, COUNT(DISTINCT gm.game_id) as cnt
        FROM game_mechanics gm
        JOIN games g ON g.id = gm.game_id
        {self_where}
        GROUP BY gm.mechanic_id
    """, params + mech_ids).fetchall()
    for r in self_counts:
        i = idx.get(r["mid"])
        if i is not None:
            matrix[i][i] = r["cnt"]

    return jsonify({
        "mechanics": [{"id": mid, "name": name} for mid, name in zip(mech_ids, mech_names)],
        "matrix": matrix
    })


@app.route("/api/mechanic-stats/<int:mechanic_id>")
def api_mechanic_stats(mechanic_id):
    db = get_db()
    # Basic info
    mech = db.execute("SELECT id, name FROM mechanics WHERE id = ?", [mechanic_id]).fetchone()
    if not mech:
        return jsonify({"error": "Not found"}), 404

    game_count = db.execute(
        "SELECT COUNT(*) as c FROM game_mechanics WHERE mechanic_id = ?", [mechanic_id]
    ).fetchone()["c"]

    # Aggregate stats across games with this mechanic
    stats = db.execute("""
        SELECT
            ROUND(AVG(g.average), 2) as avg_rating,
            ROUND(AVG(g.weight), 2) as avg_weight,
            ROUND(AVG(g.users_rated), 0) as avg_users_rated,
            MIN(g.year_published) as earliest_year,
            MAX(g.year_published) as latest_year,
            ROUND(AVG(g.playing_time), 0) as avg_playtime
        FROM games g
        JOIN game_mechanics gm ON gm.game_id = g.id
        WHERE gm.mechanic_id = ?
    """, [mechanic_id]).fetchone()

    # Top 10 games by bayes_average
    top_games = db.execute("""
        SELECT g.id, g.name, g.year_published, g.average, g.users_rated, g.weight, g.rank
        FROM games g
        JOIN game_mechanics gm ON gm.game_id = g.id
        WHERE gm.mechanic_id = ?
        ORDER BY g.bayes_average DESC
        LIMIT 10
    """, [mechanic_id]).fetchall()

    # Top co-occurring mechanics
    co_mechs = db.execute("""
        SELECT m.name, COUNT(*) as cnt
        FROM game_mechanics gm1
        JOIN game_mechanics gm2 ON gm2.game_id = gm1.game_id AND gm2.mechanic_id != gm1.mechanic_id
        JOIN mechanics m ON m.id = gm2.mechanic_id
        WHERE gm1.mechanic_id = ?
        GROUP BY gm2.mechanic_id
        ORDER BY cnt DESC
        LIMIT 8
    """, [mechanic_id]).fetchall()

    # Games per year (last 30 years)
    yearly = db.execute("""
        SELECT g.year_published as year, COUNT(*) as cnt
        FROM games g
        JOIN game_mechanics gm ON gm.game_id = g.id
        WHERE gm.mechanic_id = ? AND g.year_published >= 1995
        GROUP BY g.year_published
        ORDER BY g.year_published
    """, [mechanic_id]).fetchall()

    return jsonify({
        "id": mech["id"],
        "name": mech["name"],
        "game_count": game_count,
        "avg_rating": stats["avg_rating"],
        "avg_weight": stats["avg_weight"],
        "avg_users_rated": int(stats["avg_users_rated"] or 0),
        "avg_playtime": int(stats["avg_playtime"] or 0),
        "earliest_year": stats["earliest_year"],
        "latest_year": stats["latest_year"],
        "top_games": rows_to_dicts(top_games),
        "co_mechanics": rows_to_dicts(co_mechs),
        "yearly": rows_to_dicts(yearly),
    })


@app.route("/api/mechanic-pair-games")
def api_mechanic_pair_games():
    db = get_db()
    m1 = int_param("m1")
    m2 = int_param("m2")
    if m1 is None or m2 is None:
        return jsonify([])

    if m1 == m2:
        rows = db.execute("""
            SELECT g.id, g.name, g.year_published, g.average, g.users_rated, g.weight, g.rank
            FROM games g
            JOIN game_mechanics gm ON gm.game_id = g.id AND gm.mechanic_id = ?
            ORDER BY g.bayes_average DESC
            LIMIT 100
        """, [m1]).fetchall()
    else:
        rows = db.execute("""
            SELECT g.id, g.name, g.year_published, g.average, g.users_rated, g.weight, g.rank
            FROM games g
            JOIN game_mechanics gm1 ON gm1.game_id = g.id AND gm1.mechanic_id = ?
            JOIN game_mechanics gm2 ON gm2.game_id = g.id AND gm2.mechanic_id = ?
            ORDER BY g.bayes_average DESC
            LIMIT 100
        """, [m1, m2]).fetchall()

    return jsonify(rows_to_dicts(rows))


# ---------- market opportunity ----------

@app.route("/api/opportunity-matrix")
def api_opportunity_matrix():
    db = get_db()
    min_users = int_param("min_users_rated", 100)
    min_year = int_param("min_year")
    min_games = int_param("min_games", 3)

    extra_clauses = []
    params = []
    if min_year is not None:
        extra_clauses.append("g.year_published >= ?")
        params.append(min_year)
    if min_users is not None:
        extra_clauses.append("g.users_rated >= ?")
        params.append(min_users)
    where = ("WHERE " + " AND ".join(extra_clauses)) if extra_clauses else ""

    rows = db.execute(f"""
        SELECT
            m.id as mechanic_id, m.name as mechanic_name,
            c.id as category_id, c.name as category_name,
            COUNT(*) as game_count,
            ROUND(AVG(g.average), 2) as avg_rating,
            CAST(AVG(g.users_rated) AS INTEGER) as avg_users_rated
        FROM games g
        JOIN game_mechanics gm ON gm.game_id = g.id
        JOIN game_categories gc ON gc.game_id = g.id
        JOIN mechanics m ON m.id = gm.mechanic_id
        JOIN categories c ON c.id = gc.category_id
        {where}
        GROUP BY m.id, c.id
        HAVING COUNT(*) >= ?
        ORDER BY COUNT(*) DESC
    """, params + [min_games]).fetchall()

    results = []
    for r in rows:
        d = dict(r)
        ur = d["avg_users_rated"] or 1
        gc = d["game_count"] or 1
        d["opportunity_score"] = round(
            d["avg_rating"] * math.log(max(ur, 1)) / math.sqrt(gc), 2
        )
        results.append(d)

    return jsonify(results)


@app.route("/api/opportunity-games")
def api_opportunity_games():
    db = get_db()
    mechanic_id = int_param("mechanic_id")
    category_id = int_param("category_id")
    if mechanic_id is None or category_id is None:
        return jsonify([])

    rows = db.execute("""
        SELECT g.id, g.name, g.year_published, g.average, g.users_rated, g.weight, g.rank
        FROM games g
        JOIN game_mechanics gm ON gm.game_id = g.id AND gm.mechanic_id = ?
        JOIN game_categories gc ON gc.game_id = g.id AND gc.category_id = ?
        ORDER BY g.bayes_average DESC
        LIMIT 100
    """, [mechanic_id, category_id]).fetchall()
    return jsonify(rows_to_dicts(rows))


# ---------- trends ----------

@app.route("/api/trends/mechanics")
def api_trends_mechanics():
    db = get_db()
    ids_str = request.args.get("mechanic_ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    if not ids:
        return jsonify([])
    normalize = request.args.get("normalize", "false") == "true"
    min_year = int_param("min_year", 1990)
    max_year = int_param("max_year", 2025)

    placeholders = ",".join("?" * len(ids))
    rows = db.execute(f"""
        SELECT g.year_published as year, m.id as mechanic_id, m.name as mechanic_name, COUNT(*) as cnt
        FROM games g
        JOIN game_mechanics gm ON gm.game_id = g.id
        JOIN mechanics m ON m.id = gm.mechanic_id
        WHERE gm.mechanic_id IN ({placeholders})
          AND g.year_published BETWEEN ? AND ?
        GROUP BY g.year_published, gm.mechanic_id
        ORDER BY g.year_published
    """, ids + [min_year, max_year]).fetchall()

    if normalize:
        totals = {}
        for r in db.execute("""
            SELECT year_published as year, COUNT(*) as cnt FROM games
            WHERE year_published BETWEEN ? AND ?
            GROUP BY year_published
        """, [min_year, max_year]).fetchall():
            totals[r["year"]] = r["cnt"]
        results = []
        for r in rows:
            d = dict(r)
            total = totals.get(d["year"], 1)
            d["value"] = round(d["cnt"] / total * 100, 2)
            results.append(d)
        return jsonify(results)

    return jsonify([{**dict(r), "value": dict(r)["cnt"]} for r in rows])


@app.route("/api/trends/categories")
def api_trends_categories():
    db = get_db()
    ids_str = request.args.get("category_ids", "")
    ids = [int(x) for x in ids_str.split(",") if x.strip().isdigit()]
    if not ids:
        return jsonify([])
    normalize = request.args.get("normalize", "false") == "true"
    min_year = int_param("min_year", 1990)
    max_year = int_param("max_year", 2025)

    placeholders = ",".join("?" * len(ids))
    rows = db.execute(f"""
        SELECT g.year_published as year, c.id as category_id, c.name as category_name, COUNT(*) as cnt
        FROM games g
        JOIN game_categories gc ON gc.game_id = g.id
        JOIN categories c ON c.id = gc.category_id
        WHERE gc.category_id IN ({placeholders})
          AND g.year_published BETWEEN ? AND ?
        GROUP BY g.year_published, gc.category_id
        ORDER BY g.year_published
    """, ids + [min_year, max_year]).fetchall()

    if normalize:
        totals = {}
        for r in db.execute("""
            SELECT year_published as year, COUNT(*) as cnt FROM games
            WHERE year_published BETWEEN ? AND ?
            GROUP BY year_published
        """, [min_year, max_year]).fetchall():
            totals[r["year"]] = r["cnt"]
        results = []
        for r in rows:
            d = dict(r)
            total = totals.get(d["year"], 1)
            d["value"] = round(d["cnt"] / total * 100, 2)
            results.append(d)
        return jsonify(results)

    return jsonify([{**dict(r), "value": dict(r)["cnt"]} for r in rows])


@app.route("/api/trends/overview")
def api_trends_overview():
    db = get_db()
    # Compare last 5 years vs prior 5 years
    recent_start = 2020
    prior_start = 2015
    prior_end = 2019

    recent_total = db.execute(
        "SELECT COUNT(*) as c FROM games WHERE year_published >= ?", [recent_start]
    ).fetchone()["c"] or 1
    prior_total = db.execute(
        "SELECT COUNT(*) as c FROM games WHERE year_published BETWEEN ? AND ?",
        [prior_start, prior_end]
    ).fetchone()["c"] or 1

    mechs = db.execute("""
        SELECT m.id, m.name,
            SUM(CASE WHEN g.year_published >= ? THEN 1 ELSE 0 END) as recent_count,
            SUM(CASE WHEN g.year_published BETWEEN ? AND ? THEN 1 ELSE 0 END) as prior_count
        FROM mechanics m
        JOIN game_mechanics gm ON gm.mechanic_id = m.id
        JOIN games g ON g.id = gm.game_id
        WHERE g.year_published >= ?
        GROUP BY m.id
        HAVING recent_count + prior_count >= 20
    """, [recent_start, prior_start, prior_end, prior_start]).fetchall()

    results = []
    for r in mechs:
        recent_share = r["recent_count"] / recent_total * 100
        prior_share = r["prior_count"] / prior_total * 100
        change = recent_share - prior_share
        results.append({
            "id": r["id"],
            "name": r["name"],
            "recent_count": r["recent_count"],
            "prior_count": r["prior_count"],
            "recent_share": round(recent_share, 2),
            "prior_share": round(prior_share, 2),
            "share_change": round(change, 2)
        })

    results.sort(key=lambda x: x["share_change"], reverse=True)
    rising = results[:10]
    falling = results[-10:][::-1]

    return jsonify({"rising": rising, "falling": falling})


# ---------- static file serving ----------

@app.route("/")
def serve_index():
    return send_from_directory(STATIC_DIR, "index.html")


@app.route("/<path:path>")
def serve_static(path):
    if os.path.exists(os.path.join(STATIC_DIR, path)):
        return send_from_directory(STATIC_DIR, path)
    return send_from_directory(STATIC_DIR, "index.html")


if __name__ == "__main__":
    app.run(debug=True, port=5000)
