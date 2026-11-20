"""A polite HTTP client for public RERA portals.

* identifies itself (config.USER_AGENT) and honours robots.txt
* waits `delay` seconds between requests to the same host
* keeps cookies per run (some portals need a session for form posts)
* caches every response on disk, so re-running an import does not hit the portal
  again (delete data/cache/rera or pass refresh=True to fetch fresh copies)
* retries transient failures with backoff
"""

from __future__ import annotations

import hashlib
import http.cookiejar
import time
import urllib.error
import urllib.parse
import urllib.request
import urllib.robotparser
from pathlib import Path

from .. import config

CACHE_DIR = config.DATA_DIR / "cache" / "rera"


class BlockedByRobots(Exception):
    pass


class PoliteFetcher:
    def __init__(self, delay: float = 2.0, cache_dir: Path | None = CACHE_DIR, refresh: bool = False,
                 timeout: int = 180, verbose: bool = True):
        self.delay = delay
        self.cache_dir = Path(cache_dir) if cache_dir else None
        self.refresh = refresh
        self.timeout = timeout
        self.verbose = verbose
        self._last: dict[str, float] = {}
        self._robots: dict[str, urllib.robotparser.RobotFileParser | None] = {}
        self.jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.jar))
        self.requests_made = 0

    # ----------------------------------------------------------------- helpers
    def _allowed(self, url: str) -> bool:
        p = urllib.parse.urlparse(url)
        host = f"{p.scheme}://{p.netloc}"
        if host not in self._robots:
            rp = urllib.robotparser.RobotFileParser()
            try:
                req = urllib.request.Request(host + "/robots.txt", headers={"User-Agent": config.USER_AGENT})
                with self.opener.open(req, timeout=30) as r:
                    rp.parse(r.read().decode("utf-8", "replace").splitlines())
                self._robots[host] = rp
            except urllib.error.HTTPError as e:
                # 404 = no robots.txt = no restrictions. 401/403 on robots.txt alone is treated
                # as "no rules published" too (common on government portals behind a WAF).
                self._robots[host] = None if e.code in (401, 403, 404, 410) else rp
            except Exception:
                self._robots[host] = None
        rp = self._robots[host]
        return True if rp is None else rp.can_fetch(config.USER_AGENT, url)

    def _cache_path(self, method: str, url: str, body: bytes | None) -> Path | None:
        if not self.cache_dir:
            return None
        key = hashlib.sha1(method.encode() + url.encode() + (body or b"")).hexdigest()
        host = urllib.parse.urlparse(url).netloc
        return self.cache_dir / host / f"{key}.html"

    def _wait(self, url: str) -> None:
        host = urllib.parse.urlparse(url).netloc
        gap = time.monotonic() - self._last.get(host, 0)
        if gap < self.delay:
            time.sleep(self.delay - gap)
        self._last[host] = time.monotonic()

    # --------------------------------------------------------------------- API
    def get(self, url: str, params: dict | None = None, use_cache: bool = True) -> str:
        if params:
            url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
        return self._request("GET", url, None, use_cache)

    def post(self, url: str, data: dict, use_cache: bool = True, ignore_in_cache_key: tuple = ("_token",)) -> str:
        # Session tokens change every visit; leave them out of the cache key so the same
        # logical request is served from cache on re-runs.
        key = urllib.parse.urlencode({k: v for k, v in data.items() if k not in ignore_in_cache_key}).encode()
        return self._request("POST", url, urllib.parse.urlencode(data).encode(), use_cache, key)

    def _request(self, method: str, url: str, body: bytes | None, use_cache: bool, cache_body: bytes | None = None) -> str:
        cp = self._cache_path(method, url, cache_body if cache_body is not None else body)
        if use_cache and cp and cp.exists() and not self.refresh:
            return cp.read_text(encoding="utf-8")
        if not self._allowed(url):
            raise BlockedByRobots(f"robots.txt disallows {url}")
        last_err = None
        for attempt in range(4):
            self._wait(url)
            req = urllib.request.Request(url, data=body, method=method, headers={
                "User-Agent": config.USER_AGENT,
                "Accept": "text/html,application/xhtml+xml",
                **({"Content-Type": "application/x-www-form-urlencoded"} if body else {}),
            })
            try:
                with self.opener.open(req, timeout=self.timeout) as r:  # noqa: S310 (https portals)
                    raw = r.read()
                    charset = r.headers.get_content_charset() or "utf-8"
                self.requests_made += 1
                text = raw.decode(charset, "replace")
                if cp and use_cache:
                    cp.parent.mkdir(parents=True, exist_ok=True)
                    cp.write_text(text, encoding="utf-8")
                return text
            except urllib.error.HTTPError as e:
                if e.code in (400, 401, 403, 404):
                    raise
                last_err = e
            except Exception as e:  # timeouts, resets
                last_err = e
            backoff = self.delay * (2 ** attempt) + 2
            if self.verbose:
                print(f"  retry {attempt + 1} for {url} after error: {last_err} (waiting {backoff:.0f}s)")
            time.sleep(backoff)
        raise RuntimeError(f"Failed to fetch {url}: {last_err}")
