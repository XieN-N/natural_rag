"""Small guard for user-supplied endpoint URLs in CLI utilities.

The Qdrant/LLM endpoints these tools talk to are operator-provided (CLI flag
or env var), frequently localhost — that is legitimate here. The only hard
requirement is the scheme: ``http`` or ``https``. ``urllib`` would happily
accept ``file://`` and friends, which is not something an endpoint flag
should ever do.
"""
from __future__ import annotations

from urllib.parse import urlparse

_ALLOWED_SCHEMES = ("http", "https")


def assert_http_url(url: str, *, what: str = "endpoint URL") -> str:
    """Return *url* unchanged if its scheme is http/https, else raise."""
    scheme = urlparse(url).scheme
    if scheme not in _ALLOWED_SCHEMES:
        raise ValueError(
            f"Refusing {what} {url!r}: only {'/'.join(_ALLOWED_SCHEMES)} is allowed"
        )
    return url
