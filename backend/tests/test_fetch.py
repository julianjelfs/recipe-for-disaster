import pytest

from app.importer.fetch import InvalidUrl, canonicalise_url


def test_canonicalise_strips_tracking_params_and_fragment():
    url = " https://WWW.Example.com/r/cake?utm_source=x&id=3&fbclid=abc#step-2 "
    assert canonicalise_url(url) == "https://www.example.com/r/cake?id=3"


@pytest.mark.parametrize("url", ["ftp://example.com/cake", "not a url", "https://"])
def test_canonicalise_rejects_non_web_urls(url):
    with pytest.raises(InvalidUrl):
        canonicalise_url(url)
