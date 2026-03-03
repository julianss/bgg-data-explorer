# BGG Data Project

## Goal

Build a dashboard for analyzing the BoardGameGeek database — focusing on mechanics combinations, underexplored niches, and design space gaps.

## Data Source

- **BGG XML API2** (`https://boardgamegeek.com/xmlapi2/thing?id=X&stats=1`)
- Auth: `Authorization: Bearer $BGG_API_TOKEN` (token in `.env`)
- Batch fetching supported (up to 20 IDs per request)
- Baseline game list: `boardgames_ranks.csv` (downloaded from BGG, all games with ranks)

## Database: `bgg.db` (SQLite)

Ingested via `ingest.py` — all 30,199 ranked board games.

### Schema

| Table | Rows | Description |
|-------|------|-------------|
| `games` | 30,199 | Core game data |
| `mechanics` | 192 | Unique mechanics |
| `categories` | 85 | Unique categories |
| `families` | 4,640 | Game families |
| `designers` | 13,176 | Designers |
| `game_mechanics` | junction | Game-to-mechanic links |
| `game_categories` | junction | Game-to-category links |
| `game_families` | junction | Game-to-family links |
| `game_designers` | junction | Game-to-designer links |

### `games` columns

`id`, `name`, `year_published`, `rank`, `bayes_average`, `average`, `users_rated`,
`is_expansion`, `min_players`, `max_players`, `playing_time`, `min_playtime`,
`max_playtime`, `min_age`, `weight`, `owned`, `wanting`, `wishing`, `description`

### Key stats

- **Years**: -3500 to 2027
- **Weight** (complexity): 1.0 – 4.81, avg 1.97
- **Avg mechanics per game**: 3.6
- **Top mechanics**: Dice Rolling (8226), Hand Management (6243), Set Collection (4261), Variable Player Powers (3720)
- **Top categories**: Card Game (9563), Wargame (4841), Fantasy (3926), Party Game (3001)

## Analysis Ideas

- **Mechanic co-occurrence matrix**: which mechanic pairs appear together frequently vs rarely
- **Missing mechanic combos**: pairs/triples that have zero or very few games
- **Niche detection**: category + mechanic combos that are underdeveloped relative to the popularity of each individually
- **Quality by niche**: average rating/weight for different mechanic combos
- **Trend analysis**: which mechanics/categories are growing over time
- **Design space map**: visualize the mechanic space and where density is high vs sparse
