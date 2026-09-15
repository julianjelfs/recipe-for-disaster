import pytest

from app import config, costs
from app.importer.fetch import FetchError
from app.importer.normalise import Usage
from app.importer.pipeline import import_url, renormalise_recipe
from app.importer.validate import ValidationFailed
from tests.helpers import BBC_URL, FakeClient, add_recipe, fetch_fixture, make_recipe, step

# FakeClient reports 1,000 input and 500 output tokens per call.
ONE_CALL_USD = costs.cost_usd(config.MODEL, Usage(calls=1, input_tokens=1000, output_tokens=500))


def broken_recipe():
    return make_recipe(steps=[step("Mix.", ["nope"])])


def usage_rows(conn):
    return conn.execute("SELECT * FROM claude_usage ORDER BY id").fetchall()


def test_inv18_successful_import_records_its_cost(conn):
    """Invariant 18: every import or re-read that calls Claude records its token counts and cost, whether it succeeds or fails."""
    recipe, _ = import_url(conn, BBC_URL, FakeClient(make_recipe()), fetch_fixture("bbcgoodfood.html"))

    [row] = usage_rows(conn)
    assert (row["purpose"], row["recipe_id"], row["succeeded"], row["model"]) == ("import", recipe.id, 1, config.MODEL)
    assert (row["calls"], row["input_tokens"], row["output_tokens"]) == (1, 1000, 500)
    assert row["cost_usd"] == pytest.approx(ONE_CALL_USD)


def test_inv18_failed_import_records_both_attempts(conn):
    """Invariant 18: a failed import still records every call it paid for."""
    with pytest.raises(ValidationFailed):
        import_url(conn, BBC_URL, FakeClient(broken_recipe(), broken_recipe()), fetch_fixture("bbcgoodfood.html"))

    [row] = usage_rows(conn)
    assert (row["succeeded"], row["recipe_id"], row["calls"], row["input_tokens"]) == (0, None, 2, 2000)
    assert row["cost_usd"] == pytest.approx(2 * ONE_CALL_USD)


def test_inv18_a_crash_before_the_retry_still_records_the_first_call(conn):
    """Invariant 18: usage is kept even when something unexpected breaks the import part way."""
    # One canned response, so the retry's call raises IndexError inside the fake client.
    with pytest.raises(IndexError):
        import_url(conn, BBC_URL, FakeClient(broken_recipe()), fetch_fixture("bbcgoodfood.html"))

    [row] = usage_rows(conn)
    assert (row["calls"], row["succeeded"]) == (1, 0)


def test_inv18_renormalise_records_its_cost(conn):
    """Invariant 18: re-reads are recorded as well as imports."""
    recipe = add_recipe(conn, BBC_URL)
    renormalise_recipe(conn, recipe.id, FakeClient(make_recipe(title="Read again")))

    assert [(row["purpose"], row["recipe_id"], row["succeeded"]) for row in usage_rows(conn)] == [
        ("import", recipe.id, 1),
        ("renormalise", recipe.id, 1),
    ]


def test_nothing_is_recorded_when_claude_is_not_called(conn):
    def blocked(url: str) -> str:
        raise FetchError(f"{url} returned HTTP 403.")

    with pytest.raises(FetchError):
        import_url(conn, BBC_URL, FakeClient(), blocked)
    add_recipe(conn, BBC_URL)
    import_url(conn, BBC_URL, FakeClient(), fetch_fixture("bbcgoodfood.html"))  # already imported

    assert len(usage_rows(conn)) == 1


def test_cost_counts_cache_tokens_and_skips_unknown_models():
    million = Usage(
        calls=1,
        input_tokens=1_000_000,
        output_tokens=1_000_000,
        cache_creation_input_tokens=1_000_000,
        cache_read_input_tokens=1_000_000,
    )
    assert costs.cost_usd("claude-haiku-4-5", million) == pytest.approx(1.00 + 5.00 + 1.25 + 0.10)
    assert costs.cost_usd("a-model-with-no-price", million) is None


def test_spending_summary(conn):
    for name in ("one", "two", "three"):
        add_recipe(conn, f"https://example.com/{name}")
    with pytest.raises(ValidationFailed):
        import_url(conn, BBC_URL, FakeClient(broken_recipe(), broken_recipe()), fetch_fixture("bbcgoodfood.html"))

    spent = costs.spending(conn)
    assert (spent.imports, spent.renormalises, spent.failures, spent.unpriced) == (3, 0, 1, 0)
    assert spent.total_usd == pytest.approx(5 * ONE_CALL_USD)
    assert spent.last_30_days_usd == pytest.approx(5 * ONE_CALL_USD)
    assert spent.median_import_usd == pytest.approx(ONE_CALL_USD)
    assert spent.average_import_usd == pytest.approx(ONE_CALL_USD)
    assert costs.most_expensive(conn)[0]["calls"] == 2
