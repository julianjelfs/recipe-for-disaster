"""Settings read from the environment and backend/.env."""

import os
from pathlib import Path

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")

DB_PATH = Path(os.environ.get("RECIPE_DB_PATH") or BACKEND_DIR / "recipes.db")
MODEL = os.environ.get("RECIPE_MODEL") or "claude-haiku-4-5"
# The built frontend. Missing in a checkout that hasn't been built; use the Vite dev server then.
UI_DIR = Path(os.environ.get("RECIPE_UI_DIR") or BACKEND_DIR.parent / "frontend" / "build")

# Bump when the normalisation prompt or schema changes, so old recipes can be found and renormalised.
PARSE_VERSION = 2
