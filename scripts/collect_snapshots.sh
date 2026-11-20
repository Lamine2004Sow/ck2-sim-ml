#!/bin/bash
# Keeps a gzip copy of the CK2 autosave every N in-game years (default 1).
# The game must autosave yearly (settings.txt: autosave="YEARLY",
# compress_autosaves=no) and run without ironman.
# Usage: collect_snapshots.sh [interval_years] [output_folder] [end_year]
# Stops by itself once the snapshot of end_year is saved (no limit if omitted).
INTERVAL="${1:-1}"
OUT="${2:-$HOME/ck2_dataset/run_001}"
END_YEAR="${3:-}"
SAVE="$HOME/.paradoxinteractive/Crusader Kings II/save games/autosave.ck2"
mkdir -p "$OUT"
last_mtime=""
echo "Watching $SAVE -> $OUT (every $INTERVAL years${END_YEAR:+, until $END_YEAR}). Ctrl+C to stop."
while true; do
  if [ -f "$SAVE" ]; then
    m=$(stat -c %Y "$SAVE")
    if [ "$m" != "$last_mtime" ]; then
      # wait until the game has finished writing (stable size)
      s1=-1; s2=$(stat -c %s "$SAVE")
      while [ "$s1" != "$s2" ]; do sleep 2; s1=$s2; s2=$(stat -c %s "$SAVE"); done
      last_mtime=$(stat -c %Y "$SAVE")
      date=$(head -c 200 "$SAVE" | grep -a -m1 -o 'date="[0-9.]*"' | cut -d'"' -f2)
      year=${date%%.*}
      if [ -n "$year" ] && [ $((year % INTERVAL)) -eq 0 ]; then
        dest="$OUT/save_${date}.ck2.gz"
        if [ ! -f "$dest" ] && [ ! -f "$OUT/save_${date}.ck2" ]; then
          gzip -c "$SAVE" > "$dest.part" && mv "$dest.part" "$dest" \
            && echo "[$(date +%T)] saved $dest"
        fi
      else
        echo "[$(date +%T)] autosave $date ignored"
      fi
      if [ -n "$END_YEAR" ] && [ -n "$year" ] && [ "$year" -ge "$END_YEAR" ]; then
        echo "[$(date +%T)] reached $END_YEAR: collection finished."
        exit 0
      fi
    fi
  fi
  sleep 5
done
