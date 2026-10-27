import http.server
import threading
import unittest

from mdaudit.audit import run_audit
from mdaudit.checks import Context, robots_blocks_all, run_checks, detect_platform
from mdaudit.fetcher import FetchResult
from mdaudit.models import FAIL, PASS, WARN, AuditResult, Finding
from mdaudit.parser import PageParser

GOOD = """<!doctype html><html lang="en"><head><title>Custom Website Development in Delhi NCR | Mark</title>
<meta name="description" content="Mark Design builds fast, secure, SEO-friendly websites for businesses across Delhi NCR since 2001.">
<meta name="viewport" content="width=device-width, initial-scale=1"><link rel="canonical" href="https://x.test/">
<meta property="og:title" content="t"><meta property="og:description" content="d"><meta property="og:image" content="i">
<script type="application/ld+json">{}</script></head><body><h1>Hello</h1><img src="a.png" alt="a"></body></html>"""

BAD = """<html><head><script src="a.js"></script><meta name="generator" content="WordPress 6.4.2"></head>
<body><h1>A</h1><h1>B</h1><img src="http://x/a.png"><img src="b.png"></body></html>"""


def ctx_for(html, headers=None, final="https://x.test/", elapsed=0.3):
    parsed = PageParser()
    parsed.feed(html)
    page = FetchResult("https://x.test/", final_url=final, status=200, headers=headers or {},
                       body=html.encode(), elapsed=elapsed)
    return Context(page=page, parsed=parsed, http_redirects_to_https=True, cert_days_left=90,
                   robots=FetchResult("r", status=200, body=b"User-agent: *\nDisallow: /wp-admin/"),
                   sitemap_found=True)


def by_id(findings):
    return {f.id: f for f in findings}


class ParserTests(unittest.TestCase):
    def test_extracts_signals(self):
        p = PageParser()
        p.feed(BAD)
        self.assertEqual(p.h1_count, 2)
        self.assertEqual(p.img_total, 2)
        self.assertEqual(p.img_missing_alt, 2)
        self.assertEqual(p.blocking_scripts, 1)
        self.assertEqual(p.meta["generator"], "WordPress 6.4.2")


class CheckTests(unittest.TestCase):
    def test_good_page_has_no_failures(self):
        f = by_id(run_checks(ctx_for(GOOD, {"content-encoding": "gzip"})))
        self.assertEqual(f["seo-title"].status, PASS)
        self.assertEqual(f["seo-h1"].status, PASS)
        self.assertEqual(f["mob-viewport"].status, PASS)
        self.assertEqual(f["sec-https"].status, PASS)

    def test_bad_page_is_flagged(self):
        f = by_id(run_checks(ctx_for(BAD)))
        self.assertEqual(f["seo-title"].status, FAIL)
        self.assertEqual(f["seo-desc"].status, FAIL)
        self.assertEqual(f["seo-h1"].status, WARN)
        self.assertEqual(f["seo-alt"].status, FAIL)
        self.assertEqual(f["mob-viewport"].status, FAIL)
        self.assertEqual(f["sec-mixed"].status, FAIL)
        self.assertEqual(f["sec-generator"].status, WARN)

    def test_http_site_fails_https_check(self):
        f = by_id(run_checks(ctx_for(GOOD, final="http://x.test/")))
        self.assertEqual(f["sec-https"].status, FAIL)

    def test_expired_cert(self):
        c = ctx_for(GOOD)
        c.cert_days_left = -3
        self.assertEqual(by_id(run_checks(c))["sec-cert"].status, FAIL)

    def test_robots_blocking(self):
        self.assertTrue(robots_blocks_all("User-agent: *\nDisallow: /"))
        self.assertFalse(robots_blocks_all("User-agent: *\nDisallow: /wp-admin/"))
        self.assertFalse(robots_blocks_all("User-agent: Googlebot-Image\nDisallow: /"))

    def test_platform_detection(self):
        self.assertEqual(detect_platform('<link href="/wp-content/themes/Avada/x.css">', {}), ["WordPress", "Avada theme"])

    def test_slow_response(self):
        f = by_id(run_checks(ctx_for(GOOD, elapsed=3.4)))
        self.assertEqual(f["perf-time"].status, FAIL)


class ScoreTests(unittest.TestCase):
    def test_weighted_score_and_grade(self):
        r = AuditResult("u", "u", "now", findings=[
            Finding("a", "SEO", PASS, "a", weight=3),
            Finding("b", "SEO", FAIL, "b", weight=1),
            Finding("c", "SEO", "info", "c"),
        ])
        self.assertEqual(r.score, 75)
        self.assertEqual(r.grade, "C")


class _Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/":
            body, code = GOOD.encode(), 200
        elif self.path == "/robots.txt":
            body, code = b"User-agent: *\nDisallow:\nSitemap: http://localhost/sitemap.xml\n", 200
        else:
            body, code = b"nope", 404
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


class IntegrationTest(unittest.TestCase):
    def test_end_to_end_against_local_server(self):
        srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
        threading.Thread(target=srv.serve_forever, daemon=True).start()
        try:
            res = run_audit(f"http://127.0.0.1:{srv.server_port}/", timeout=5)
        finally:
            srv.shutdown()
            srv.server_close()
        ids = by_id(res.findings)
        self.assertEqual(ids["seo-title"].status, PASS)
        self.assertEqual(ids["sec-https"].status, FAIL)  # plain http test server
        self.assertTrue(ids["seo-sitemap"].status == PASS)
        self.assertGreater(res.score, 0)

    def test_unreachable_site(self):
        res = run_audit("http://127.0.0.1:9/", timeout=2)
        self.assertEqual(res.score, 0)


if __name__ == "__main__":
    unittest.main()
