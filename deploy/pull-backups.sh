#!/usr/bin/env bash
# Pull the Pi's backups onto this laptop. Run daily by a launchd agent, and safe by hand.
set -euo pipefail

HOST="${RECIPE_PI_HOST:-julian_jelfs@pi.local}"
DEST="${RECIPE_BACKUP_DEST:-$HOME/Backups/recipe-for-disaster}"
KEEP=30

mkdir -p "$DEST"

# No --delete: if the Pi ever loses its backups, this side should not helpfully
# lose them too. Pruning below is this machine's own decision.
rsync -az -e "ssh -o BatchMode=yes -o ConnectTimeout=10" "$HOST:~/recipe-backups/" "$DEST/"

ls -1t "$DEST"/recipes-*.db 2>/dev/null | tail -n +$((KEEP + 1)) | xargs -I{} rm -f {}
echo "$(ls -1 "$DEST"/recipes-*.db 2>/dev/null | wc -l | tr -d ' ') backups in $DEST"
ls -1t "$DEST"/recipes-*.db 2>/dev/null | head -1 | xargs -I{} echo "newest: {}"
