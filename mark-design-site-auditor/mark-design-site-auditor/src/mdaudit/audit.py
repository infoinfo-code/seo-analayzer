from __future__ import annotations

import re
import ssl
from datetime import datetime, timezone
from urllib.parse import urlparse

from .checks import Context, detect_platform, run_checks
from .fetcher import cert_days_left, fetch, normalize_url, split_host
from .models import FAIL, AuditResult, Finding
from .parser import PageParser

SITEMAP_PATHS = ("/sitemap.xml", "/sitemap_index.xml", "/wp-sitemap.xml")


def run_audit(url: str, timeout: int = 15) -> AuditResult:
    url = normalize_url(url)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    page = fetch(url, timeout)

    if page.error or page.status == 0 or page.status >= 400:
        reason = page.error or f"HTTP {page.status}"
        return AuditResult(
            url, page.final_url or url, now,
            findings=[Finding("net-reach", "Security", FAIL, "Site could not be audited", reason,
                              "Check the URL, DNS and that the server is up.", weight=1)],
        )

    parsed = PageParser()
    parsed.feed(page.text)

    final = urlparse(page.final_url or url)
    base = f"{final.scheme}://{final.netloc}"
    ctx = Context(page=page, parsed=parsed)

    if final.scheme == "https":
        probe = fetch(f"http://{final.netloc}/", timeout)
        if not probe.error:
            ctx.http_redirects_to_https = probe.final_url.startswith("https://")
        host, port = split_host(page.final_url)
        try:
            ctx.cert_days_left = cert_days_left(host, port, timeout)
        except (ssl.SSLError, OSError, KeyError) as exc:
            ctx.cert_error = str(exc)

    ctx.robots = fetch(base + "/robots.txt", timeout)
    robots_text = ctx.robots.text if ctx.robots.ok else ""
    if re.search(r"(?im)^\s*sitemap:\s*\S+", robots_text):
        ctx.sitemap_found = True
    else:
        for path in SITEMAP_PATHS:
            r = fetch(base + path, timeout)
            if r.ok and b"<" in r.body[:200]:
                ctx.sitemap_found = True
                break

    return AuditResult(
        url=url,
        final_url=page.final_url,
        audited_at=now,
        platform=detect_platform(page.text, parsed.meta),
        findings=run_checks(ctx),
    )
