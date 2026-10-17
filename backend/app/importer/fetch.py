"""Fetch recipe pages and canonicalise their URLs."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36"
)
TRACKING_PARAMS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "ref_src", "igshid"}
BLOCKED_STATUSES = (401, 403, 429)


class InvalidUrl(ValueError):
    pass


class FetchError(Exception):
    pass


def canonicalise_url(url: str) -> str:
    """Normalise a URL for dedupe: lower-case scheme and host, no fragment, no tracking params."""
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ("http", "https") or not parts.netloc:
        raise InvalidUrl(f"Not a web URL: {url!r}")
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in TRACKING_PARAMS
    ]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path or "/", urlencode(query), ""))


def fetch_html(url: str, client: httpx.Client | None = None) -> str:
    with client or httpx.Client(follow_redirects=True, timeout=15) as http:
        response = _get(http, url, USER_AGENT)
        if response.status_code in BLOCKED_STATUSES:
            # Cloudflare challenges a browser User-Agent that lacks a browser's fingerprint, but some
            # sites (janespatisserie.com) let a client that says what it is through. Ask again as httpx.
            response = _get(http, url, f"python-httpx/{httpx.__version__}")
        if response.status_code in BLOCKED_STATUSES:
            raise FetchError(f"{url} returned HTTP {response.status_code}. The site blocks automated fetches.")
        if response.status_code >= 400:
            raise FetchError(f"{url} returned HTTP {response.status_code}.")
        return response.text


def _get(http: httpx.Client, url: str, user_agent: str) -> httpx.Response:
    headers = {
        "User-Agent": user_agent,
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en-GB,en;q=0.9",
    }
    try:
        return http.get(url, headers=headers)
    except httpx.HTTPError as error:
        raise FetchError(f"Could not fetch {url}: {error}") from error
