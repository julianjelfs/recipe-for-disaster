import httpx
import pytest

from app.importer.fetch import FetchError, InvalidUrl, canonicalise_url, fetch_html


def test_canonicalise_strips_tracking_params_and_fragment():
    url = " https://WWW.Example.com/r/cake?utm_source=x&id=3&fbclid=abc#step-2 "
    assert canonicalise_url(url) == "https://www.example.com/r/cake?id=3"


@pytest.mark.parametrize("url", ["ftp://example.com/cake", "not a url", "https://"])
def test_canonicalise_rejects_non_web_urls(url):
    with pytest.raises(InvalidUrl):
        canonicalise_url(url)


JANES_URL = "https://www.janespatisserie.com/2020/04/22/millionaires-shortbread-2/"


def _cloudflare_site(lets_httpx_through: bool) -> httpx.Client:
    """A site that challenges browser User-Agents, and maybe lets httpx's own through."""

    def handle(request: httpx.Request) -> httpx.Response:
        if lets_httpx_through and request.headers["User-Agent"].startswith("python-httpx/"):
            return httpx.Response(200, text="<html>recipe</html>")
        return httpx.Response(403, text="Just a moment...")

    return httpx.Client(transport=httpx.MockTransport(handle))


def test_blocked_page_is_fetched_again_as_httpx():
    assert fetch_html(JANES_URL, _cloudflare_site(lets_httpx_through=True)) == "<html>recipe</html>"


def test_page_blocked_both_ways_reports_the_block():
    with pytest.raises(FetchError, match="HTTP 403. The site blocks automated fetches"):
        fetch_html(JANES_URL, _cloudflare_site(lets_httpx_through=False))
