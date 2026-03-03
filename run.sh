#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo "=== BGG Data Explorer ==="

# Python deps
pip3 install -q -r requirements.txt

# Frontend build
if [ ! -d frontend/node_modules ]; then
  echo "Installing frontend dependencies..."
  cd frontend && npm install && cd ..
fi

echo "Building frontend..."
cd frontend && npm run build && cd ..

# Add SQLite indexes if not present
python3 -c "
import sqlite3
db = sqlite3.connect('bgg.db')
indexes = [
    'CREATE INDEX IF NOT EXISTS idx_games_year ON games(year_published)',
    'CREATE INDEX IF NOT EXISTS idx_games_users_rated ON games(users_rated)',
    'CREATE INDEX IF NOT EXISTS idx_games_average ON games(average)',
    'CREATE INDEX IF NOT EXISTS idx_gm_mechanic ON game_mechanics(mechanic_id)',
    'CREATE INDEX IF NOT EXISTS idx_gm_game ON game_mechanics(game_id)',
    'CREATE INDEX IF NOT EXISTS idx_gc_category ON game_categories(category_id)',
    'CREATE INDEX IF NOT EXISTS idx_gc_game ON game_categories(game_id)',
]
for idx in indexes:
    db.execute(idx)
db.commit()
db.close()
print('Database indexes ready.')
"

echo "Starting server at http://localhost:5000"
python3 app.py
