"""Serve the built frontend from the API, so the installed app is one process on one port."""

import mimetypes
from pathlib import Path

from starlette.exceptions import HTTPException
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

# Python doesn't know .webmanifest, and would serve the PWA manifest as text/plain.
mimetypes.add_type("application/manifest+json", ".webmanifest")


class UiFiles(StaticFiles):
    """The SvelteKit build, with a fallback to index.html for client-side routes like /r/12.

    Unknown paths under /api still 404, so a mistyped API call fails loudly instead of
    returning a page of HTML.
    """

    async def get_response(self, path: str, scope: Scope) -> Response:
        try:
            return await super().get_response(path, scope)
        except HTTPException as error:
            if error.status_code != 404 or path == "api" or path.startswith("api/"):
                raise
            return await super().get_response("index.html", scope)

    def file_response(self, full_path, stat_result, scope, status_code=200) -> Response:
        response = super().file_response(full_path, stat_result, scope, status_code)
        # SvelteKit fingerprints everything under _app/immutable, so those never change.
        # Everything else, index.html above all, must be revalidated or a phone that is
        # rarely hard-refreshed stays pinned to an old build.
        if "/_app/immutable/" in Path(full_path).as_posix():
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            response.headers["Cache-Control"] = "no-cache"
        return response
