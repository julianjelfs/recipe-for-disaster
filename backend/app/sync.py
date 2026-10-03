"""Tell a device what changed in the library since it last looked.

Every device keeps its own copy of the whole library and searches it itself. It syncs by sending
the revision and epoch of its copy. The triggers in migrations/006_sync.sql stamp every write with
a revision and record every deletion, so "since" is all this needs.
"""

import sqlite3

from app import store
from app.schemas import SyncResponse


def changes_since(conn: sqlite3.Connection, since: int, epoch: int | None) -> SyncResponse:
    # One read transaction, so the revision reported is exactly the one the changes were read at,
    # even if a write lands halfway through. (Already inside one: that one does the same job.)
    own = not conn.in_transaction
    if own:
        conn.execute("BEGIN")
    try:
        current_epoch = conn.execute("PRAGMA user_version").fetchone()[0]
        revision = conn.execute("SELECT revision FROM library_revision").fetchone()[0]
        # A copy from before a migration, or from ahead of this database (restored from a backup),
        # can't be patched. Start it again.
        full = since <= 0 or epoch != current_epoch or since > revision
        if full:
            ids = [row[0] for row in conn.execute("SELECT id FROM recipes ORDER BY id")]
            deleted: list[int] = []
        else:
            ids = [row[0] for row in conn.execute("SELECT id FROM recipes WHERE revision > ? ORDER BY id", (since,))]
            deleted = [
                row[0]
                for row in conn.execute("SELECT id FROM deleted_recipes WHERE revision > ? ORDER BY id", (since,))
            ]
        changed = [store.get_recipe(conn, recipe_id) for recipe_id in ids]
    finally:
        if own:
            conn.execute("COMMIT")
    return SyncResponse(epoch=current_epoch, revision=revision, full=full, changed=changed, deleted=deleted)
