"""Bounded HTTP with exact host allowlists, pinned DNS and explicit redirects."""

import ipaddress
import random
import socket
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

import httpx
from redis import Redis

from medguide.infrastructure.errors import PipelineError
from medguide.infrastructure.settings import Settings

CONITEC_HOSTS = frozenset({"www.gov.br", "bvsms.saude.gov.br"})


def public_addresses(host: str) -> list[str]:
    try:
        addresses = list(
            {str(item[4][0]) for item in socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)}
        )
    except OSError as exc:
        raise PipelineError("DNS_FAILURE", transient=True) from exc
    if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
        raise PipelineError("PRIVATE_ADDRESS")
    return sorted(addresses)


@dataclass(frozen=True)
class Resource:
    url: str
    data: bytes
    media_type: str
    headers: dict[str, str]


class SafeHttpClient:
    def __init__(
        self,
        settings: Settings,
        *,
        allowed_hosts: frozenset[str] = CONITEC_HOSTS,
        transport: httpx.BaseTransport | None = None,
        resolver: Callable[[str], list[str]] = public_addresses,
        sleeper: Callable[[float], None] = time.sleep,
        rate_store: Redis | None = None,
    ) -> None:
        self.settings = settings
        self.allowed_hosts = allowed_hosts
        self.resolver = resolver
        self.sleep = sleeper
        self.rate_store = rate_store
        self.client = httpx.Client(
            transport=transport,
            timeout=settings.http_timeout,
            follow_redirects=False,
            trust_env=False,
        )
        self.robots: dict[str, RobotFileParser] = {}
        self.last_request: dict[str, float] = {}

    def __enter__(self) -> "SafeHttpClient":
        return self

    def __exit__(self, *args: object) -> None:
        self.client.close()

    def validate_url(self, url: str) -> tuple[str, list[str]]:
        parsed = urlsplit(url)
        host = parsed.hostname or ""
        if (
            parsed.scheme != "https"
            or host not in self.allowed_hosts
            or parsed.username
            or parsed.password
            or parsed.port not in (None, 443)
        ):
            raise PipelineError("UNAPPROVED_URL")
        addresses = self.resolver(host)
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise PipelineError("PRIVATE_ADDRESS")
        return host, addresses

    def _throttle(self, host: str, interval: float) -> None:
        if self.rate_store is not None:
            # Reserve a time slot atomically across both worker queues.
            delay = self.rate_store.eval(
                "local t=redis.call('TIME'); local now=t[1]*1000+math.floor(t[2]/1000); "
                "local next=math.max(now,tonumber(redis.call('GET',KEYS[1]) or '0')); "
                "redis.call('SET',KEYS[1],next+ARGV[1],'PX',math.max(60000,next-now+ARGV[1])); "
                "return next-now",
                1,
                f"medguide:rate:{host}",
                int(interval * 1000),
            )
            self.sleep(float(delay) / 1000)  # type: ignore[arg-type]
        else:
            delay = interval - (time.monotonic() - self.last_request.get(host, 0))
            if delay > 0:
                self.sleep(delay)
            self.last_request[host] = time.monotonic()

    def _robots_allowed(self, url: str) -> float:
        parsed = urlsplit(url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in self.robots:
            parser = RobotFileParser()
            try:
                resource = self.get(origin + "/robots.txt", check_robots=False)
                parser.parse(resource.data.decode("utf-8", errors="replace").splitlines())
            except PipelineError as exc:
                if exc.code == "HTTP_404":
                    parser.parse([])
                else:
                    raise
            self.robots[origin] = parser
        parser = self.robots[origin]
        if not parser.can_fetch(self.settings.user_agent, url):
            raise PipelineError("ROBOTS_DISALLOWED")
        return max(
            self.settings.request_interval, float(parser.crawl_delay(self.settings.user_agent) or 0)
        )

    def get(self, url: str, *, check_robots: bool = True) -> Resource:
        for _ in range(self.settings.max_redirects + 1):
            host, addresses = self.validate_url(url)
            interval = self._robots_allowed(url) if check_robots else self.settings.request_interval
            for attempt in range(self.settings.http_attempts):
                self._throttle(host, interval)
                try:
                    # Pin the validated address to prevent a second, rebound DNS lookup.
                    pinned = httpx.URL(url).copy_with(host=addresses[0])
                    with self.client.stream(
                        "GET",
                        pinned,
                        headers={
                            "Host": host,
                            "User-Agent": self.settings.user_agent,
                            "Accept": "application/pdf,text/html;q=0.9,*/*;q=0.1",
                        },
                        extensions={"sni_hostname": host.encode("ascii")},
                    ) as response:
                        if response.status_code in (301, 302, 303, 307, 308):
                            location = response.headers.get("location")
                            if not location:
                                raise PipelineError("INVALID_REDIRECT")
                            url = urljoin(url, location)
                            break
                        if response.status_code in (429, 502, 503, 504):
                            delay = self._retry_after(response.headers.get("retry-after"), attempt)
                            if attempt + 1 == self.settings.http_attempts:
                                raise PipelineError(f"HTTP_{response.status_code}", transient=True)
                            self.sleep(delay)
                            continue
                        if response.status_code != 200:
                            raise PipelineError(f"HTTP_{response.status_code}")
                        length = response.headers.get("content-length", "")
                        if length.isdigit() and int(length) > self.settings.max_download_bytes:
                            raise PipelineError("DOWNLOAD_TOO_LARGE")
                        chunks: list[bytes] = []
                        size = 0
                        for chunk in response.iter_bytes(chunk_size=65536):
                            size += len(chunk)
                            if size > self.settings.max_download_bytes:
                                raise PipelineError("DOWNLOAD_TOO_LARGE")
                            chunks.append(chunk)
                        return Resource(
                            url,
                            b"".join(chunks),
                            response.headers.get("content-type", "").split(";")[0],
                            dict(response.headers),
                        )
                except (
                    httpx.TimeoutException,
                    httpx.NetworkError,
                    httpx.RemoteProtocolError,
                ) as exc:
                    if attempt + 1 == self.settings.http_attempts:
                        raise PipelineError("NETWORK_FAILURE", transient=True) from exc
                    self.sleep(self._retry_after(None, attempt))
            else:
                raise PipelineError("HTTP_RETRIES_EXHAUSTED", transient=True)
        raise PipelineError("TOO_MANY_REDIRECTS")

    @staticmethod
    def _retry_after(value: str | None, attempt: int) -> float:
        if value:
            try:
                seconds = float(value)
            except ValueError:
                try:
                    seconds = (parsedate_to_datetime(value) - datetime.now(UTC)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    seconds = 0
            if seconds > 300:
                # Defer to the durable task retry instead of retrying before the server permits.
                raise PipelineError("RETRY_AFTER_DEFERRED", transient=True)
            return max(0, seconds)
        return (2**attempt) + random.uniform(0, 0.5)
