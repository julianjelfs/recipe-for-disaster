import json

import pytest

from app.importer.extract import ExtractError, count_sized_pieces, extract, prefer_metric
from tests.helpers import BBC_URL, fixture_html


def test_supported_site_keeps_ingredient_groups_and_image():
    page = extract(fixture_html("bbcgoodfood.html"), BBC_URL)
    assert page.text is None
    purposes = [group["purpose"] for group in page.structured["ingredient_groups"]]
    assert "For the buttercream" in purposes
    assert page.structured["instructions_list"]
    assert page.image_url.startswith("https://")


def test_unsupported_site_falls_back_to_schema_org():
    page = extract(fixture_html("bbcgoodfood.html"), "https://some-unknown-blog.example/chocolate-cake")
    assert page.structured is not None
    assert any("cocoa powder" in line for group in page.structured["ingredient_groups"] for line in group["ingredients"])


def test_advert_heavy_page_reduces_to_recipe_data():
    # The saved page is 531KB with 53 <script> tags and about 10,000 words of text.
    page = extract(fixture_html("sallysbakingaddiction.html"), "https://sallysbakingaddiction.com/best-banana-bread-recipe/")
    assert page.structured is not None
    lines = page.structured["ingredient_groups"][0]["ingredients"]
    assert len(lines) == 11
    assert lines[0] == "250g all-purpose flour (spooned & leveled)"
    assert len(page.structured["instructions_list"]) == 6
    assert len(json.dumps(page.structured)) < 10_000


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("2 cups (250g) all-purpose flour (spooned & leveled)", "250g all-purpose flour (spooned & leveled)"),
        ("1/2 cup (8 Tbsp; 113g) unsalted butter, softened", "113g unsalted butter, softened"),
        ("1 and 1/2 cups (345g) mashed bananas (about 3–4 ripe bananas)", "345g mashed bananas (about 3–4 ripe bananas)"),
        ("1 1/4 cups (300 ml) whole milk", "300ml whole milk"),
        ("180g (6oz ) chicken breast", "180g (6oz ) chicken breast"),
        ("1 teaspoon baking soda", "1 teaspoon baking soda"),
        ("3/4 cup chopped walnuts", "3/4 cup chopped walnuts"),
    ],
)
def test_prefer_metric_uses_the_grams_the_page_gives(line, expected):
    assert prefer_metric(line) == expected


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        # Report #2: Haiku stored "5cm piece of fresh ginger" as 5g.
        ("5cm piece of fresh ginger", "1 × 5cm piece of fresh ginger"),
        ("2.5 cm chunk ginger, grated", "1 × 2.5 cm chunk ginger, grated"),
        ('1" knob of ginger', '1 × 1" knob of ginger'),
        ("5 cloves of garlic", "5 cloves of garlic"),
        ("2cm slices of courgette", "2cm slices of courgette"),
    ],
)
def test_count_sized_pieces_puts_a_count_before_the_size(line, expected):
    assert count_sized_pieces(line) == expected


def test_page_without_structured_data_falls_back_to_main_text():
    page = extract(fixture_html("no_jsonld_blog.html"), "https://crumb-of-comfort.example/cheese-scones")
    assert page.structured is None
    assert "225g self-raising flour" in page.text
    assert "newsletter" not in page.text


def test_page_without_a_recipe_raises():
    with pytest.raises(ExtractError):
        extract("<html><body><p>Nothing to see here.</p></body></html>", "https://example.com/")
