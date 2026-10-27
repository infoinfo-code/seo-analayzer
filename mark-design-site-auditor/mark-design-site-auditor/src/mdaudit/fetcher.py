from __future__ import annotations

import gzip
import socket
import ssl
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from urllib.parse import urlparse

USER_AGENT = "MarkDesignSiteAuditor/0.1 (+https://mark-design.net)"
MAX_BYTES = 3_000_000


@dataclass
class FetchResult:
    requested_url: str
    final_url: str = ""
    status: int = 0
    headers: dict = field(default_factory=dict)  # lower-cased keys
    body: bytes = b""  # decompressed
    transfer_size: int = 0  # bytes on the wire (before decompression)
    elapsed: float = 0.0
    error: str = ""

    @property
    def ok(self) -> bool:
        return not self.error and 200 <= self.status < 400

    @property
    def text(self) -> str:
        enc = "utf-8"
        ctype = self.headers.get("content-type", "")
        if "charset=" in ctype:
            enc = ctype.split("charset=")[-1].split(";")[0].strip() or "utf-8"
        try:
            return self.body.decode(enc, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


def normalize_url(url: str) -> str:
    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def fetch(url: str, timeout: int = 15) -> FetchResult:
    result = FetchResult(requested_url=url)
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept-Encoding": "gzip", "Accept": "*/*"}
    )
    start = time.perf_counter()
    try:
        try:
            resp = urllib.request.urlopen(req, timeout=timeout)
        except urllib.error.HTTPError as exc:  # 4xx / 5xx still carry headers + body
            resp = exc
        raw = resp.read(MAX_BYTES)
        result.elapsed = time.perf_counter() - start
        result.status = resp.status if hasattr(resp, "status") else resp.code
        result.final_url = resp.geturl()
        result.headers = {k.lower(): v for k, v in resp.headers.items()}
        result.transfer_size = len(raw)
        if result.headers.get("content-encoding", "").lower() == "gzip":
            try:
                raw = gzip.decompress(raw)
            except OSError:
                pass
        result.body = raw
    except (urllib.error.URLError, socket.timeout, ssl.SSLError, ConnectionError, ValueError) as exc:
        result.elapsed = time.perf_counter() - start
        result.error = str(getattr(exc, "reason", exc))
    return result


def cert_days_left(host: str, port: int = 443, timeout: int = 10) -> int:
    """Days until the TLS certificate expires. Raises ssl.SSLError / OSError on failure."""
    ctx = ssl.create_default_context()
    with socket.create_connection((host, port), timeout=timeout) as sock:
        with ctx.wrap_socket(sock, server_hostname=host) as tls:
            cert = tls.getpeercert()
    expires = ssl.cert_time_to_seconds(cert["notAfter"])
    return int((expires - time.time()) // 86400)


def split_host(url: str) -> tuple[str, int]:
    p = urlparse(url)
    return p.hostname or "", p.port or (443 if p.scheme == "https" else 80)
