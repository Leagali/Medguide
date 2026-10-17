import httpx
import pytest

from medguide.infrastructure.errors import PipelineError
from medguide.infrastructure.http import SafeHttpClient


def client(settings, handler):
    return SafeHttpClient(
        settings,
        transport=httpx.MockTransport(handler),
        resolver=lambda host: ["8.8.8.8"],
        sleeper=lambda _: None,
    )


def test_transient_503_retry_after_and_dns_pinning(settings):
    calls, sleeps = [], []

    def handler(request):
        calls.append(request)
        if len(calls) < 3:
            return httpx.Response(503, headers={"retry-after": "2"})
        return httpx.Response(200, content=b"%PDF-test")

    with client(settings, handler) as http:
        http.sleep = sleeps.append
        assert http.get("https://www.gov.br/file", check_robots=False).data == b"%PDF-test"
    assert len(calls) == 3
    assert sleeps == [2, 2]
    assert calls[0].url.host == "8.8.8.8"
    assert calls[0].headers["host"] == "www.gov.br"
    assert calls[0].extensions["sni_hostname"] == b"www.gov.br"


@pytest.mark.parametrize("status", [401, 403, 404])
def test_permanent_status_not_retried(settings, status):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status)

    with client(settings, handler) as http, pytest.raises(PipelineError, match=f"HTTP_{status}"):
        http.get("https://www.gov.br/file", check_robots=False)
    assert len(calls) == 1


def test_timeout_retried_and_limited(settings):
    calls = []

    def handler(request):
        calls.append(request)
        raise httpx.ReadTimeout("timeout")

    with client(settings, handler) as http, pytest.raises(PipelineError, match="NETWORK_FAILURE"):
        http.get("https://www.gov.br/file", check_robots=False)
    assert len(calls) == settings.http_attempts


@pytest.mark.parametrize(
    "url",
    [
        "http://www.gov.br/a",
        "https://localhost/a",
        "https://www.gov.br.evil.test/a",
        "https://www.gov.br:8080/a",
        "https://user:pass@www.gov.br/a",
        "https://169.254.169.254/a",
    ],
)
def test_unapproved_urls(settings, url):
    with client(settings, lambda _: pytest.fail("must not send")) as http:
        with pytest.raises(PipelineError, match="UNAPPROVED_URL"):
            http.get(url)


def test_private_dns_and_redirect_denied(settings):
    with client(
        settings, lambda _: httpx.Response(302, headers={"location": "https://evil.test/"})
    ) as http:
        with pytest.raises(PipelineError, match="UNAPPROVED_URL"):
            http.get("https://www.gov.br/file", check_robots=False)
        http.resolver = lambda _: ["127.0.0.1"]
        with pytest.raises(PipelineError, match="PRIVATE_ADDRESS"):
            http.get("https://www.gov.br/file")


def test_robots_denies_document(settings):
    with client(
        settings, lambda _: httpx.Response(200, text="User-agent: *\nDisallow: /private")
    ) as http:
        with pytest.raises(PipelineError, match="ROBOTS_DISALLOWED"):
            http.get("https://www.gov.br/private/file.pdf")


def test_download_size_limited(settings):
    settings.max_download_bytes = 4
    with client(settings, lambda _: httpx.Response(200, content=b"12345")) as http:
        with pytest.raises(PipelineError, match="DOWNLOAD_TOO_LARGE"):
            http.get("https://www.gov.br/file", check_robots=False)
