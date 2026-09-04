"""Rate-limited EDGAR client.

The SEC publishes a 10 request/second ceiling and enforces it, and it blocks
clients that do not send a User-Agent identifying who is making the request.
Both are handled here rather than at every call site.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any

import httpx

FULL_TEXT_SEARCH = "https://efts.sec.gov/LATEST/search-index"
ARCHIVES = "https://www.sec.gov/Archives/edgar/data"

# The stated ceiling is 10/s. Sit under it: the cost of being slightly slow is
# a few extra seconds, the cost of being blocked is the whole pull.
DEFAULT_RATE = 8.0

USER_AGENT_ENV = "SEC_USER_AGENT"


class MissingUserAgent(RuntimeError):
    pass


def user_agent() -> str:
    """Read the declared User-Agent, which SEC requires to be a real contact.

    Kept in the environment rather than in source so a public repo never
    carries a personal email address.
    """
    ua = os.environ.get(USER_AGENT_ENV, "").strip()
    if not ua:
        raise MissingUserAgent(
            f"{USER_AGENT_ENV} is not set. SEC requires a User-Agent naming a "
            f"real person and email, and will block requests without one.\n"
            f'  export {USER_AGENT_ENV}="Your Name your@email.com"'
        )
    return ua


@dataclass
class RateLimiter:
    """Spacing-based limiter. Simpler than a token bucket and sufficient here,
    because requests are issued serially."""

    rate: float = DEFAULT_RATE
    _next_allowed: float = field(default=0.0, init=False)

    def wait(self) -> None:
        now = time.monotonic()
        if now < self._next_allowed:
            time.sleep(self._next_allowed - now)
        self._next_allowed = max(now, self._next_allowed) + 1.0 / self.rate


class EdgarClient:
    """Serial EDGAR client with rate limiting and retry on transient failures."""

    def __init__(self, rate: float = DEFAULT_RATE, timeout: float = 30.0) -> None:
        self.limiter = RateLimiter(rate)
        self.client = httpx.Client(
            headers={
                "User-Agent": user_agent(),
                "Accept-Encoding": "gzip, deflate",
            },
            timeout=timeout,
            follow_redirects=True,
        )
        self.request_count = 0

    def __enter__(self) -> EdgarClient:
        return self

    def __exit__(self, *exc: object) -> None:
        self.client.close()

    def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        last_error: Exception | None = None
        for attempt in range(5):
            self.limiter.wait()
            try:
                self.request_count += 1
                response = self.client.get(url, params=params)
            except httpx.RequestError as exc:  # network flake
                last_error = exc
                time.sleep(2**attempt)
                continue

            if response.status_code == 200:
                return response
            # 429 means we misjudged the rate; 5xx is EDGAR being EDGAR.
            if response.status_code in (429, 500, 502, 503, 504):
                last_error = httpx.HTTPStatusError(
                    f"{response.status_code} from {url}",
                    request=response.request,
                    response=response,
                )
                time.sleep(2**attempt)
                continue
            response.raise_for_status()

        raise RuntimeError(f"giving up on {url} after 5 attempts") from last_error

    def search(
        self,
        phrase: str,
        forms: str,
        startdt: str,
        enddt: str,
        offset: int = 0,
    ) -> dict[str, Any]:
        """One page of EDGAR full-text search. Pages are 100 hits."""
        params = {
            "q": f'"{phrase}"',
            "forms": forms,
            "startdt": startdt,
            "enddt": enddt,
        }
        if offset:
            params["from"] = offset
        return self._get(FULL_TEXT_SEARCH, params).json()

    def document(self, cik: str, accession: str, filename: str) -> bytes:
        """Fetch one filing document from the EDGAR archives."""
        acc = accession.replace("-", "")
        url = f"{ARCHIVES}/{int(cik)}/{acc}/{filename}"
        return self._get(url).content
