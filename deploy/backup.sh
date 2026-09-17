#!/usr/bin/env bash
# Nightly snapshot of the recipe database, taken on the Pi.
#
# The Pi's SD card is the only copy of the library, so this runs every night and
# deploy/pull-backups.sh drags the results onto the laptop. A backup on the same
# card as the original is not a backup.
set -euo pipefail

DB="${RECIPE_DB_PATH:-/home/julian_jelfs/recipe-for-disaster/backend/recipes.db}"
DEST="${RECIPE_BACKUP_DIR:-/home/julian_jelfs/recipe-backups}"
KEEP=14

mkdir -p "$DEST"
out="$DEST/recipes-$(date +%Y%m%d-%H%M%S).db"

# SQLite's online backup API copies a consistent snapshot while uvicorn keeps serving.
# `cp` would catch a half-written page and give us a file that only looks like a backup.
python3 - "$DB" "$out" <<'PY'
import sqlite3
import sys

src, dst = sys.argv[1], sys.argv[2]
source = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
target = sqlite3.connect(dst)
with target:
    source.backup(target)

# A backup nobody checks is a rumour, so read it back before we trust it.
state = target.execute("PRAGMA integrity_check").fetchone()[0]
count = target.execute("select count(*) from recipes").fetchone()[0]
target.close()
source.close()

if state != "ok":
    raise SystemExit(f"integrity check failed: {state}")
# An empty backup means something went wrong upstream; fail loudly rather than
# quietly rotating fourteen good copies out in favour of fourteen empty ones.
if count == 0:
    raise SystemExit("backup holds no recipes")
print(f"backed up {count} recipes")
PY

echo "wrote $out ($(du -h "$out" | cut -f1))"

# Keep the newest KEEP, drop the rest.
ls -1t "$DEST"/recipes-*.db 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -r rm -f
echo "keeping $(ls -1 "$DEST"/recipes-*.db 2>/dev/null | wc -l | tr -d ' ') backups in $DEST"
