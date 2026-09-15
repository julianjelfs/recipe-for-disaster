"""Review bad imports: recipes someone flagged and imports that failed. Also shows what Claude has cost.

  uv run python scripts/reports.py                      list open reports
  uv run python scripts/reports.py --all                include resolved reports
  uv run python scripts/reports.py show ID              print everything stored for a report
  uv run python scripts/reports.py retry ID             run the stored page data through the current prompt
  uv run python scripts/reports.py retry ID --refetch   fetch and extract the page again first
  uv run python scripts/reports.py resolve ID "what fixed it"
  uv run python scripts/reports.py costs                spending on Claude so far

retry saves nothing and isn't counted in costs. It shows what an import would produce now,
so a fix can be checked against the report.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import anthropic  # noqa: E402

from app import config, costs, db, reports  # noqa: E402
from app.importer.extract import extract, restore  # noqa: E402
from app.importer.fetch import fetch_html  # noqa: E402
from app.importer.normalise import normalise  # noqa: E402
from eval_import import cost, format_amount, print_recipe  # noqa: E402


def list_command(conn, include_resolved: bool) -> None:
    rows = reports.list_reports(conn, include_resolved)
    if not rows:
        print("No reports." if include_resolved else "No open reports.")
    for row in rows:
        status = f"resolved {row['resolved_at']}" if row["resolved_at"] else "open"
        summary = row["comment"] or row["error"] or ""
        print(f"#{row['id']:<4} {row['kind']:<8} {row['created_at']}  {status}")
        print(f"      {row['source_url']}")
        print(f"      {summary[:300]}")


def show_command(conn, report_id: int) -> None:
    row = _get(conn, report_id)
    for field in ("kind", "source_url", "recipe_id", "created_at", "model", "parse_version", "comment", "error",
                  "resolved_at", "resolution"):
        if row[field] not in (None, ""):
            print(f"{field}: {row[field]}")

    if row["recipe_snapshot"]:
        recipe = json.loads(row["recipe_snapshot"])
        print("\nRecipe when flagged:")
        print(f"     {recipe['title']} | serves {recipe['servings']} | {recipe['total_minutes']} min | complexity {recipe['complexity']}")
        for ingredient in recipe["ingredients"]:
            group = f"[{ingredient['group_name']}] " if ingredient["group_name"] else ""
            prep = f", {ingredient['preparation']}" if ingredient["preparation"] else ""
            amount = format_amount(ingredient["quantity"], ingredient["quantity_max"], ingredient["unit"])
            print(f"     - {group}{amount}{ingredient['name']}{prep}  ({ingredient['canonical_name']})")
        for number, step in enumerate(recipe["steps"], start=1):
            timer = f"  [timer {step['timer_seconds']}s]" if step["timer_seconds"] else ""
            print(f"     {number}. {step['text']}{timer}")

    if row["raw_extract"]:
        print("\nExtracted page data:")
        print(json.dumps(json.loads(row["raw_extract"]), indent=1, ensure_ascii=False))
    elif row["raw_text"]:
        print("\nExtracted page text:")
        print(row["raw_text"])


def retry_command(conn, report_id: int, refetch: bool) -> None:
    row = _get(conn, report_id)
    if refetch or not (row["raw_extract"] or row["raw_text"]):
        page = extract(fetch_html(row["source_url"]), row["source_url"])
    else:
        page = restore(row["raw_extract"], row["raw_text"])
    result = normalise(page, anthropic.Anthropic(), config.MODEL)
    print(f"Current output for report #{report_id} ({config.MODEL}, parse version {config.PARSE_VERSION}, ${cost(result):.4f}):")
    print_recipe(result.recipe)


def resolve_command(conn, report_id: int, resolution: str) -> None:
    _get(conn, report_id)
    if reports.resolve_report(conn, report_id, resolution):
        print(f"Resolved #{report_id}.")
    else:
        print(f"#{report_id} was already resolved.")


def costs_command(conn) -> None:
    spent = costs.spending(conn)
    if spent.imports + spent.renormalises + spent.failures == 0:
        print("No Claude calls recorded yet.")
        return
    print("Claude spending, at list prices in USD")
    def count(n: int, noun: str) -> str:
        return f"{n} {noun}{'' if n == 1 else 's'}"

    print(
        f"  total          ${spent.total_usd:.4f}"
        f"  ({count(spent.imports, 'import')}, {count(spent.renormalises, 're-read')}, {spent.failures} failed)"
    )
    print(f"  last 30 days   ${spent.last_30_days_usd:.4f}")
    if spent.median_import_usd is not None:
        print(f"  per import     median ${spent.median_import_usd:.4f}, average ${spent.average_import_usd:.4f}")
    if spent.unpriced:
        print(f"  {spent.unpriced} used a model with no price in app/costs.py and aren't in these totals")

    print("\nMost expensive:")
    for row in costs.most_expensive(conn):
        outcome = row["purpose"] if row["succeeded"] else f"{row['purpose']}, failed"
        print(f"  ${row['cost_usd']:.4f}  {row['created_at'][:10]}  {outcome}  {row['source_url']}")
        print(f"             {row['calls']} call(s), {row['input_tokens']:,} tokens in, {row['output_tokens']:,} out")


def _get(conn, report_id: int):
    row = reports.get_report(conn, report_id)
    if row is None:
        sys.exit(f"No report #{report_id}.")
    return row


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--all", action="store_true", help="include resolved reports when listing")
    commands = parser.add_subparsers(dest="command")
    commands.add_parser("show").add_argument("id", type=int)
    retry = commands.add_parser("retry")
    retry.add_argument("id", type=int)
    retry.add_argument("--refetch", action="store_true")
    resolve = commands.add_parser("resolve")
    resolve.add_argument("id", type=int)
    resolve.add_argument("resolution")
    commands.add_parser("costs")
    args = parser.parse_args()

    conn = db.connect(config.DB_PATH)
    db.migrate(conn)
    try:
        if args.command == "show":
            show_command(conn, args.id)
        elif args.command == "retry":
            retry_command(conn, args.id, args.refetch)
        elif args.command == "resolve":
            resolve_command(conn, args.id, args.resolution)
        elif args.command == "costs":
            costs_command(conn)
        else:
            list_command(conn, args.all)
    finally:
        conn.close()


if __name__ == "__main__":
    main()
