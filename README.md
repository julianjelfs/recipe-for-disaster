# Recipe for Disaster

A family recipe library. Paste a recipe URL and the backend fetches the page, pulls the recipe out, and has Claude Haiku 4.5 rewrite it in UK measures with short steps. The recipe is then stored in SQLite.

- `backend/`: FastAPI, SQLite, importer pipeline (fetch, extract, normalise, validate, store)
- `frontend/`: SvelteKit single-page app, built with adapter-static

## Setup

Put your Anthropic API key in `backend/.env` (gitignored):

```
ANTHROPIC_API_KEY=sk-ant-...
```

## Running in development

```sh
cd backend && uv run uvicorn app.main:app --reload --port 8011   # API; the service has 8010, Triad Trainer 8000
cd frontend && pnpm dev                                  # app on http://localhost:5173, proxies /api
```

The database is `backend/recipes.db`. Set `RECIPE_DB_PATH` to put it somewhere else.

## Tests

```sh
cd backend && uv run pytest
cd frontend && pnpm check && pnpm test
```

Backend tests run offline. They use saved pages in `backend/tests/fixtures/` and a fake Claude client.

To check real Claude output without saving anything:

```sh
cd backend && uv run python scripts/eval_import.py scripts/eval_urls.txt
```

It prints each normalised recipe and what the call cost.

## Reviewing bad imports

The recipe page has a "Flag a problem" link. A flag saves the comment, a copy of the recipe as it was, and the page data Claude was given. Failed imports are saved the same way, apart from invalid URLs and Claude API outages.

```sh
cd backend
uv run python scripts/reports.py                  # open reports
uv run python scripts/reports.py show 3           # the comment, the recipe as flagged, the page data
uv run python scripts/reports.py retry 3          # what the current prompt makes of the same page data
uv run python scripts/reports.py retry 3 --refetch
uv run python scripts/reports.py resolve 3 "Sizes like 5cm now stay in the ingredient name"
uv run python scripts/reports.py costs            # what Claude has cost so far
```

Every import and re-read that calls Claude stores its token counts and cost, including failed attempts, since those are paid for too. `costs` totals them at list prices, from `backend/app/costs.py`. It's an estimate: check the Anthropic console for the actual bill.

To work through a report: `show` it to see what went wrong, change the prompt or the code, `retry` to check the fix, add a test for the case, then `resolve` it.

## Invariants

| # | Invariant | Tests |
|---|-----------|-------|
| 1 | Every stored ingredient unit is in the allowed UK unit set or null. | `test_validate.py::test_inv1_units_are_uk_validator_rejects_us_units`, `test_inv1_units_are_uk_database_accepts_only_uk_units` |
| 2 | Importing the same URL twice (after canonicalisation) returns the existing recipe and creates no new row. | `test_import.py::test_inv2_same_url_imports_once` |
| 3 | Every stored recipe has at least one ingredient and at least one step. | `test_validate.py::test_inv3_recipe_needs_ingredients_and_steps`, `test_import.py::test_inv3_stored_recipe_has_ingredients_and_steps` |
| 4 | Every `step_ingredients` row references an ingredient belonging to the same recipe. | `test_import.py::test_inv4_step_ingredients_belong_to_same_recipe` |
| 5 | Renormalise from stored raw data produces a recipe without any network fetch of the source URL. | `test_library.py::test_inv5_renormalise_uses_saved_page_data_without_fetching` |
| 6 | A validation failure after one retry returns 422 and writes no recipe data. | `test_import.py::test_inv6_validation_failure_is_retried_with_errors`, `test_inv6_second_validation_failure_writes_nothing`, `test_inv6_api_returns_422_and_writes_nothing` |
| 7 | `has=a,b` returns only recipes with an ingredient whose canonical name contains a (singular or plural) and one that contains b. | `test_library.py::test_inv7_has_requires_every_ingredient`, `test_inv7_has_matches_plurals_and_whole_words` |
| 8 | Scaling servings by factor k multiplies every non-null quantity by k and leaves null quantities null. | `frontend/src/lib/scale.test.ts` "invariant 8: multiplies every non-null quantity by k and leaves null quantities null" |
| 9 | Cooking mode "next" on the last step does not advance past it; "back" on the first does not go below it. | `frontend/src/lib/cook.test.ts` "invariant 9: …" (three tests) |
| 10 | No temperature in stored step text is in °F. | `test_validate.py::test_inv10_fahrenheit_is_converted`, `test_inv10_validate_removes_fahrenheit_from_steps` |
| 11 | No stored step text mentions cups, ounces or pounds. | `test_validate.py::test_inv11_steps_have_no_us_measures`, `test_inv11_words_containing_measures_are_allowed` |
| 12 | A flag keeps the recipe as it was when flagged, even after the recipe is edited or deleted. | `test_reports.py::test_inv12_flag_keeps_recipe_as_it_was` |
| 13 | An import that fails after its URL is accepted is recorded with the URL, the error and any extracted data. | `test_reports.py::test_inv13_validation_failure_is_recorded`, `test_inv13_fetch_failure_is_recorded` |
| 14 | Each recipe has exactly one search index row matching its current content, and a deleted recipe has none. | `test_library.py::test_inv14_search_index_follows_every_change` |
| 15 | No ingredient whose name gives a size in cm or mm is stored with that size as its weight or volume. | `test_validate.py::test_inv15_size_in_name_is_not_stored_as_a_weight` |
| 16 | Any non-API path that isn't a file returns the app's index.html; paths under /api never do. | `test_ui.py::test_inv16_client_routes_get_the_app`, `test_inv16_api_paths_never_get_the_app` |
| 17 | A link shared to the app reaches /add as ?url= or inside ?text=, and the add page finds it in either. | `frontend/src/lib/share.test.ts` "invariant 17: …" (two tests) |
| 18 | Every import, creation or re-read that calls Claude records its token counts and cost, whether it succeeds or fails. | `test_costs.py::test_inv18_successful_import_records_its_cost`, `test_inv18_failed_import_records_both_attempts`, `test_inv18_a_crash_before_the_retry_still_records_the_first_call`, `test_inv18_renormalise_records_its_cost` |
| 19 | The shopping list includes every ingredient exactly once, and a merged line's quantity is the sum of the quantities it replaces. | `frontend/src/lib/shopping.test.ts` "invariant 19: …" (two tests) |
| 20 | Tin, pan, dish and tray sizes in stored step text and equipment are in inches. | `test_validate.py::test_inv20_tin_sizes_are_in_inches`, `test_inv20_validate_converts_steps_and_equipment` |
| 21 | Every stored recipe is either imported (source URL, no brief) or created (brief, no source URL). | `test_create.py::test_inv21_every_recipe_is_imported_or_created` |
| 22 | A created recipe is stored exactly like an imported one, and "try again" reuses its brief without fetching anything. | `test_create.py::test_inv22_created_recipe_is_stored_like_an_imported_one`, `test_inv22_try_again_reinvents_from_the_saved_brief` |
| 23 | Migrating a database that already holds recipes preserves their ingredients, steps and tags. | `test_migrations.py::test_inv23_migrating_keeps_existing_recipe_content` |
| 24 | Every recipe without a photo gets an illustration, and every course has one. | `frontend/src/lib/course-art.test.ts` "invariant 24: …" (two tests) |
| 25 | Reading the recipe list page by page returns every match exactly once, in the same order as the whole list, for every sort. | `test_library.py::test_inv25_pages_together_return_every_match_once_in_order`, `test_inv25_every_order_breaks_ties_by_id` |
| 26 | A page's `total` is the number of recipes matching the search and filters, whatever the page size or offset. | `test_library.py::test_inv26_total_counts_every_match_whatever_the_page` |
| 27 | The list API returns 48 recipes when no page size is given and refuses more than 100 in one request. | `test_library.py::test_inv27_api_pages_are_bounded` |

## Where it runs

The app lives on a Raspberry Pi 4 on the house wifi, not on a laptop. One systemd unit
runs uvicorn on loopback, and Caddy in front of it holds a Let's Encrypt certificate for
`recipes.julianjelfs.co.uk`. Anyone on the wifi can open it with nothing installed.

Drive it from the laptop with `recipes`, which does everything over SSH:

```sh
recipes            # open it
recipes status     # app, Caddy, certificate, backups, disk, temperature
recipes rebuild    # after changing code
recipes logs
recipes backup     # snapshot now and pull it here
```

`recipes rebuild` pulls the code on the Pi, syncs backend dependencies there, builds the
frontend **here** and copies the result across, then restarts. The Pi never runs Vite or
sharp, which is what keeps a 2GB board comfortable.

The certificate comes over a DNS-01 challenge, so nothing is exposed to the internet and
no port is open on the router. Caddy renews it every 60 days on its own. Away from the
house the app is still on the tailnet at `https://pi.tail50bfbf.ts.net:8445`, and
`recipes url` picks whichever of the two applies.

To set a Pi up from scratch, or to put the units and Caddyfile back after changing them,
run `./deploy/install-pi.sh` on the Pi. It is safe to re-run and never touches the
database or the Cloudflare token. `docs/home-server.md` has the whole build.

The database is backed up nightly on the Pi, keeping 14, and pulled to
`~/Backups/recipe-for-disaster` on the laptop, keeping 30.

## Installing on a phone

The app is a PWA. On the house wifi, open `https://recipes.julianjelfs.co.uk`, then:

- **Android (Chrome):** menu, then "Install app" or "Add to home screen". Once installed,
  Recipes appears in the share sheet, so sharing a recipe page from the browser imports it.
- **iPhone (Safari):** Share, then "Add to Home Screen". iOS doesn't let web apps receive
  shares. A Shortcut that opens `https://recipes.julianjelfs.co.uk/add?url=` followed by
  the shared link does the same job.

Install from the house address rather than the tailnet one. A PWA is installed per origin,
so installing both gives you two separate apps with two separate caches.

The icons come from one drawing in `frontend/scripts/icons.mjs`. After changing it, run
`node scripts/icons.mjs` in `frontend/` and commit what it writes to `static/`.

## Known limits

Some big US recipe sites (Allrecipes, Simply Recipes, Serious Eats) return HTTP 403 to server-side fetches. The import shows that error. A bookmarklet that sends the page HTML from your browser is planned for later.
