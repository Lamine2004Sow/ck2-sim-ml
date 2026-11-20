# ck2-sim-ml — Crusader Kings II as a simulation environment

Crusader Kings II is an agent-based simulation: ~20 000 living AI characters
make decisions (marriages, wars, plots, successions) over centuries. Running
the game in **observer mode** turns it into a synthetic data generator for
problems that are hard to study on real data: dynastic survival, social
networks, the evolution of political systems.

## Pipeline

```
simulate (CK2 observe mode, N independent runs)
  -> collect  scripts/collect_snapshots.sh   autosave copy every k in-game years
  -> extract  python -m ck2sim.extract       save files -> tidy CSV tables
  -> analyse / train / evaluate              (split by run_id, never by row)
```

## Tables (`data/processed/<run_id>/*.csv`)

| table | grain | use |
|---|---|---|
| `characters` | one row per character, alive or dead | survival, clustering, association rules |
| `edges` | character → character (father, spouse, liege, killer…) | graph ML |
| `title_history` | each holder change of each title | reign survival, succession |
| `titles` | title × snapshot | laws, de jure structure |
| `realms` | independent realm × snapshot (59 features: size, vassal structure, cultural/religious diversity, laws, ruler, dynasty, wars) | realm profiles, forecasting, realm survival |
| `wars` / `battles` | war in progress (first/last seen) / battle | war profiles by casus belli, battle outcome |
| `provinces` | province × snapshot | culture/religion diffusion |

## Usage

```bash
# while the game runs in observe mode (uncompressed autosaves, no ironman)
scripts/collect_snapshots.sh 5 ~/ck2_dataset/run_001

python -m ck2sim.extract ~/ck2_dataset/run_001/*.ck2 --run-id run_001 --out data/processed
python -m unittest discover -s tests -t .
```

Only the Python standard library is required for extraction (~13 s per save).

## Data notes

- Trait ids in saves are positions in the game's trait load order; they are
  decoded from `game/common/traits`.
- Historical dynasties live in `game/common/dynasties`; characters omit
  culture/religion when equal to their dynasty's, so both sources are merged.
- One run is one history: generalisation must be measured across runs.
- Realm evolution features (`*_change_10y`, `n_counties_growth_10y`,
  `holder_changes_10y`, `wars_*_mean_10y`…) only look at past snapshots, so
  they are safe as forecasting inputs. The reference snapshot is the one
  closest to 10 years earlier (±1.5 years); otherwise `has_past_10y` is false.
  Change the window with `--window`.
