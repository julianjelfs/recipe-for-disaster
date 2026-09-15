"""What Claude costs: prices, and a record of every import and re-read that called it."""

import sqlite3
import statistics
from dataclasses import dataclass

from app.importer.normalise import Usage


@dataclass(frozen=True)
class Price:
    """USD per million tokens."""

    input: float
    output: float

    @property
    def cache_write(self) -> float:
        # Writing to the five-minute prompt cache costs 1.25x the input price; reading costs 0.1x.
        return self.input * 1.25

    @property
    def cache_read(self) -> float:
        return self.input * 0.1


# Anthropic list prices as of September 2026. Calls to a model missing here are recorded with no cost.
PRICES = {
    "claude-haiku-4-5": Price(input=1.00, output=5.00),
    "claude-sonnet-5": Price(input=2.00, output=10.00),
    "claude-opus-5": Price(input=5.00, output=25.00),
}


def cost_usd(model: str, usage: Usage) -> float | None:
    price = PRICES.get(model)
    if price is None:
        return None
    return (
        usage.input_tokens * price.input
        + usage.output_tokens * price.output
        + usage.cache_creation_input_tokens * price.cache_write
        + usage.cache_read_input_tokens * price.cache_read
    ) / 1_000_000


def record(
    conn: sqlite3.Connection,
    *,
    purpose: str,
    source_url: str,
    recipe_id: int | None,
    succeeded: bool,
    model: str,
    usage: Usage,
) -> int | None:
    """Store the Claude usage of one import or re-read. Does nothing if Claude was never called."""
    if usage.calls == 0:
        return None
    with conn:
        return conn.execute(
            """
            INSERT INTO claude_usage (
                purpose, source_url, recipe_id, succeeded, model, calls, input_tokens, output_tokens,
                cache_creation_input_tokens, cache_read_input_tokens, cost_usd
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                purpose,
                source_url,
                recipe_id,
                succeeded,
                model,
                usage.calls,
                usage.input_tokens,
                usage.output_tokens,
                usage.cache_creation_input_tokens,
                usage.cache_read_input_tokens,
                cost_usd(model, usage),
            ),
        ).lastrowid


@dataclass(frozen=True)
class Spending:
    total_usd: float
    last_30_days_usd: float
    imports: int
    renormalises: int
    failures: int
    # Across successful imports only; failed attempts count towards the totals above.
    median_import_usd: float | None
    average_import_usd: float | None
    # Rows for models with no price, left out of every sum.
    unpriced: int


def spending(conn: sqlite3.Connection) -> Spending:
    rows = conn.execute(
        """
        SELECT purpose, succeeded, cost_usd, created_at >= datetime('now', '-30 days') AS recent
        FROM claude_usage
        """
    ).fetchall()
    import_costs = [
        row["cost_usd"] for row in rows if row["purpose"] == "import" and row["succeeded"] and row["cost_usd"] is not None
    ]
    return Spending(
        total_usd=sum(row["cost_usd"] or 0 for row in rows),
        last_30_days_usd=sum(row["cost_usd"] or 0 for row in rows if row["recent"]),
        imports=sum(1 for row in rows if row["purpose"] == "import" and row["succeeded"]),
        renormalises=sum(1 for row in rows if row["purpose"] == "renormalise" and row["succeeded"]),
        failures=sum(1 for row in rows if not row["succeeded"]),
        median_import_usd=statistics.median(import_costs) if import_costs else None,
        average_import_usd=statistics.fmean(import_costs) if import_costs else None,
        unpriced=sum(1 for row in rows if row["cost_usd"] is None),
    )


def most_expensive(conn: sqlite3.Connection, limit: int = 5) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM claude_usage WHERE cost_usd IS NOT NULL ORDER BY cost_usd DESC, id LIMIT ?",
        (limit,),
    ).fetchall()
