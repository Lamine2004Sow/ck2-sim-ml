# ck2-sim-ml — Crusader Kings II saves to tidy tables

Crusader Kings II simulates about 20 000 AI-driven characters (marriages, wars, successions) from 1066 to 1453.
In **observer mode** the game runs on its own and writes a yearly save. This project is the data pipeline that
turns those saves — a proprietary, untyped text format of ~75 MB each — into clean, documented CSV tables.

## Pipeline

```
simulate  CK2 observe mode, yearly autosave
  -> collect  scripts/collect_snapshots.sh   copy + gzip each new save (75 -> 14 MB)
  -> parse    ck2sim.parser                  Clausewitz text format, 5 sections only (~13 s per save)
  -> enrich   ck2sim.gamedata                trait names, historical dynasties, province -> county
  -> extract  ck2sim.extract                 8 tidy CSV tables per run
```

## Tables (`data/processed/<run_id>/*.csv`)

Volumes for `run_001`: 94 yearly saves, 1230 → 1330, 258 MB of CSV.

| table | grain | rows |
|---|---|---|
| `characters` | one row per character, alive or dead (last save) | 165 881 |
| `edges` | character → character link (father, spouse, liege, killer…) | 424 899 |
| `title_history` | each holder change of each title, with how it was acquired | 68 275 |
| `titles` | title × snapshot (holder, liege, de jure liege, laws) | 791 994 |
| `realms` | independent realm × snapshot (78 columns: size, vassals, cultural/religious diversity, laws, ruler, dynasty, wars) | 11 390 |
| `provinces` | province × snapshot (culture, religion, holdings) | 164 970 |
| `wars` | one row per war, with first/last snapshot where it is seen | 2 639 |
| `battles` | one row per battle (troops, losses, winner) | 4 747 |

Column-by-column description and annotated save excerpts: [docs/formats.md](docs/formats.md).

## Usage

```bash
# while the game runs in observe mode (uncompressed autosaves, no ironman)
scripts/collect_snapshots.sh 1 ~/ck2_dataset/run_001 1330

python -m ck2sim.extract ~/ck2_dataset/run_001/*.ck2* --run-id run_001 --out data/processed
python -m unittest discover -s tests -t .
```

Only the Python standard library is required.

## Data notes

- Saves are windows-1252 text without types: every value is a string, keys can repeat, dates and ids are block keys.
  The parser handles all three, and only tokenizes the sections it needs.
- Trait ids in saves are positions in the game's trait load order; they are decoded from `game/common/traits`.
- Historical dynasties live in `game/common/dynasties`; characters omit culture/religion when equal to their
  dynasty's, so both sources are merged.
- `characters`, `edges` and `title_history` are cumulative in the game, so they are read from the last save only
  (`--characters all` to read every save). The other tables are snapshots.
- A war appears in every save while it lasts; `wars` keeps one row with `first_seen` / `last_seen`.
- Realm evolution columns (`*_change_10y`, `n_counties_growth_10y`, `holder_changes_10y`…) only read earlier
  snapshots. The reference snapshot is the one closest to 10 years earlier (±1.5 years); otherwise `has_past_10y`
  is false. Change the window with `--window`. Covered by `tests/test_evolution.py`.

Tools and why each one is used: [docs/outils.md](docs/outils.md).
Known data issues, their causes and planned fixes: [docs/limites.md](docs/limites.md).
