"""JSON over HTTP with the standard library."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Mapping

# Cloudflare in front of api.apyguard.com refuses urllib's default "Python-urllib/3.x" with 403
# "error code: 1010", so every request names the action. GitHub's API also asks for a real one.
USER_AGENT = "apyguard-action/2 (+https://github.com/ApyGuard/apyguard-action)"


class HttpError(RuntimeError):
    """A request that failed: its status (0 when there was no reply) and the start of the body."""

    def __init__(self, status: int, detail: str) -> None:
        super().__init__(f"HTTP {status}: {detail[:300]}")
        self.status = status


def request_json(
    method: str,
    url: str,
    headers: Mapping[str, str],
    body: Any | None = None,
    timeout: float = 30,
) -> Any:
    data = None if body is None else json.dumps(body).encode("utf-8")
    request = urllib.request.Request(url, data=data, method=method)
    request.add_header("User-Agent", USER_AGENT)
    for name, value in headers.items():
        request.add_header(name, value)
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            content = response.read()
    except urllib.error.HTTPError as error:
        raise HttpError(error.code, error.read().decode("utf-8", "replace")) from error
    except urllib.error.URLError as error:
        # Headers stay out of the message: they carry the tokens.
        raise HttpError(0, f"{method} {url} failed: {error.reason}") from error
    except TimeoutError as error:
        raise HttpError(0, f"{method} {url} timed out after {timeout:g} s") from error
    return json.loads(content) if content else None
