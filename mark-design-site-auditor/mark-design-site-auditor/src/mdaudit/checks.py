"""Pure check functions: they take a Context and return Findings (easy to unit-test)."""
from __future__ import annotations

from dataclasses import dataclass

from .fetcher import FetchResult
from .models import FAIL, INFO, PASS, WARN, Finding
from .parser import PageParser


@dataclass
class Context:
    page: FetchResult
    parsed: PageParser
    http_redirects_to_https: bool | None = None  # None = could not be determined
    cert_days_left: int | None = None
    cert_error: str = ""
    robots: FetchResult | None = None
    sitemap_found: bool = False


def _f(id_, cat, status, title, detail="", fix="", weight=1) -> Finding:
    return Finding(id_, cat, status, title, detail, fix, weight)


def robots_blocks_all(text: str) -> bool:
    applies = False
    for raw in text.splitlines():
        line = raw.split("#", 1)[0].strip().lower()
        if line.startswith("user-agent:"):
            applies = line.split(":", 1)[1].strip() == "*"
        elif applies and line.replace(" ", "") == "disallow:/":
            return True
    return False


def detect_platform(html: str, meta: dict[str, str]) -> list[str]:
    low = html.lower()
    found = []
    if "wp-content" in low or "wordpress" in meta.get("generator", "").lower():
        found.append("WordPress")
        if "fusion-" in low or "avada" in low:
            found.append("Avada theme")
        if "woocommerce" in low:
            found.append("WooCommerce")
    if "cdn.shopify.com" in low:
        found.append("Shopify")
    if "wixstatic.com" in low:
        found.append("Wix")
    return found


# ---------------------------------------------------------------- SEO
def seo_checks(ctx: Context) -> list[Finding]:
    p, out = ctx.parsed, []

    title = p.title.strip()
    if not title:
        out.append(_f("seo-title", "SEO", FAIL, "Page title is missing",
                      fix="Add a unique <title> of 30-60 characters containing the main keyword.", weight=3))
    elif 30 <= len(title) <= 60:
        out.append(_f("seo-title", "SEO", PASS, "Page title length is good", f"{len(title)} characters.", weight=3))
    else:
        out.append(_f("seo-title", "SEO", WARN, "Page title length is off",
                      f"{len(title)} characters (ideal 30-60); long titles get truncated in results.",
                      "Rewrite the title to 30-60 characters.", weight=3))

    desc = p.meta.get("description", "").strip()
    if not desc:
        out.append(_f("seo-desc", "SEO", FAIL, "Meta description is missing",
                      fix="Add a compelling 70-160 character meta description.", weight=2))
    elif 70 <= len(desc) <= 160:
        out.append(_f("seo-desc", "SEO", PASS, "Meta description length is good", f"{len(desc)} characters.", weight=2))
    else:
        out.append(_f("seo-desc", "SEO", WARN, "Meta description length is off",
                      f"{len(desc)} characters (ideal 70-160).", "Tighten or expand the description.", weight=2))

    if p.h1_count == 1:
        out.append(_f("seo-h1", "SEO", PASS, "Exactly one H1 heading", weight=2))
    elif p.h1_count == 0:
        out.append(_f("seo-h1", "SEO", FAIL, "No H1 heading found",
                      fix="Add one H1 that describes the page topic.", weight=2))
    else:
        out.append(_f("seo-h1", "SEO", WARN, "Multiple H1 headings",
                      f"{p.h1_count} H1 tags found.", "Keep a single H1 and demote the rest to H2/H3.", weight=2))

    if p.canonical:
        out.append(_f("seo-canonical", "SEO", PASS, "Canonical URL is set", p.canonical))
    else:
        out.append(_f("seo-canonical", "SEO", WARN, "No canonical URL",
                      fix='Add <link rel="canonical" href="..."> to avoid duplicate-content issues.'))

    if p.lang:
        out.append(_f("seo-lang", "SEO", PASS, "Language attribute is set", f'lang="{p.lang}"'))
    else:
        out.append(_f("seo-lang", "SEO", WARN, "<html> has no lang attribute",
                      fix='Add lang="en" (or the right language) to the <html> tag.'))

    missing_og = [k for k in ("og:title", "og:description", "og:image") if not p.meta.get(k)]
    if not missing_og:
        out.append(_f("seo-og", "SEO", PASS, "Open Graph tags present"))
    else:
        out.append(_f("seo-og", "SEO", WARN, "Open Graph tags incomplete",
                      "Missing: " + ", ".join(missing_og),
                      "Add the missing tags so links look right on WhatsApp, LinkedIn and Facebook."))

    if p.jsonld_blocks:
        out.append(_f("seo-schema", "SEO", PASS, "Structured data (JSON-LD) found", f"{p.jsonld_blocks} block(s)."))
    else:
        out.append(_f("seo-schema", "SEO", WARN, "No structured data found",
                      fix="Add Organization / LocalBusiness JSON-LD to qualify for rich results."))

    if p.img_total:
        covered = 1 - p.img_missing_alt / p.img_total
        detail = f"{p.img_total - p.img_missing_alt}/{p.img_total} images have an alt attribute."
        if covered >= 0.9:
            out.append(_f("seo-alt", "SEO", PASS, "Images have alt text", detail))
        elif covered >= 0.6:
            out.append(_f("seo-alt", "SEO", WARN, "Some images lack alt text", detail,
                          "Describe each meaningful image in its alt attribute."))
        else:
            out.append(_f("seo-alt", "SEO", FAIL, "Most images lack alt text", detail,
                          "Describe each meaningful image in its alt attribute."))

    rb = ctx.robots
    if rb is None or not rb.ok or not rb.body.strip():
        out.append(_f("seo-robots", "SEO", WARN, "robots.txt not found",
                      fix="Publish a robots.txt that points to your sitemap."))
    elif robots_blocks_all(rb.text):
        out.append(_f("seo-robots", "SEO", FAIL, "robots.txt blocks all crawlers",
                      "A 'Disallow: /' rule applies to every bot.",
                      "Remove the blanket disallow (common leftover from staging) so Google can index the site.", weight=3))
    else:
        out.append(_f("seo-robots", "SEO", PASS, "robots.txt is present"))

    if ctx.sitemap_found:
        out.append(_f("seo-sitemap", "SEO", PASS, "XML sitemap found", weight=2))
    else:
        out.append(_f("seo-sitemap", "SEO", WARN, "No XML sitemap found",
                      "Checked robots.txt, /sitemap.xml, /sitemap_index.xml and /wp-sitemap.xml.",
                      "Generate a sitemap and submit it in Google Search Console.", weight=2))
    return out


# ------------------------------------------------------------- Mobile
def mobile_checks(ctx: Context) -> list[Finding]:
    vp = ctx.parsed.meta.get("viewport", "")
    if "width=device-width" in vp.replace(" ", ""):
        return [_f("mob-viewport", "Mobile", PASS, "Responsive viewport tag present", weight=3)]
    if vp:
        return [_f("mob-viewport", "Mobile", WARN, "Viewport tag is not responsive", vp,
                   "Use content=\"width=device-width, initial-scale=1\".", weight=3)]
    return [_f("mob-viewport", "Mobile", FAIL, "No viewport meta tag",
               "Without it, phones render the page as a shrunken desktop site.",
               'Add <meta name="viewport" content="width=device-width, initial-scale=1">.', weight=3)]


# ----------------------------------------------------------- Security
SECURITY_HEADERS = (
    ("strict-transport-security", "HSTS (Strict-Transport-Security)", 2,
     "Send 'Strict-Transport-Security: max-age=31536000; includeSubDomains'."),
    ("x-content-type-options", "X-Content-Type-Options", 1, "Send 'X-Content-Type-Options: nosniff'."),
    ("referrer-policy", "Referrer-Policy", 1, "Send 'Referrer-Policy: strict-origin-when-cross-origin'."),
    ("content-security-policy", "Content-Security-Policy", 1,
     "Start with a report-only CSP and tighten it over time."),
)


def security_checks(ctx: Context) -> list[Finding]:
    out, page = [], ctx.page
    https = page.final_url.startswith("https://")

    if https:
        out.append(_f("sec-https", "Security", PASS, "Site is served over HTTPS", weight=3))
    else:
        out.append(_f("sec-https", "Security", FAIL, "Site is not served over HTTPS",
                      fix="Install an SSL certificate and redirect all traffic to https://.", weight=3))

    if ctx.http_redirects_to_https is True:
        out.append(_f("sec-redirect", "Security", PASS, "HTTP redirects to HTTPS", weight=2))
    elif ctx.http_redirects_to_https is False:
        out.append(_f("sec-redirect", "Security", FAIL, "HTTP does not redirect to HTTPS",
                      fix="Add a 301 redirect from http:// to https:// at server level.", weight=2))

    if https:
        if ctx.cert_error:
            out.append(_f("sec-cert", "Security", FAIL, "TLS certificate problem", ctx.cert_error,
                          "Reissue or fix the certificate chain.", weight=3))
        elif ctx.cert_days_left is not None:
            d = ctx.cert_days_left
            if d < 0:
                out.append(_f("sec-cert", "Security", FAIL, "TLS certificate has expired", f"{-d} days ago.",
                              "Renew the certificate immediately.", weight=3))
            elif d < 14:
                out.append(_f("sec-cert", "Security", WARN, "TLS certificate expires very soon", f"{d} days left.",
                              "Renew now and enable auto-renewal.", weight=3))
            else:
                out.append(_f("sec-cert", "Security", PASS, "TLS certificate is valid", f"{d} days left.", weight=3))

    for key, label, weight, fix in SECURITY_HEADERS:
        if key in page.headers:
            out.append(_f(f"sec-{key}", "Security", PASS, f"{label} header present", weight=weight))
        else:
            out.append(_f(f"sec-{key}", "Security", WARN, f"{label} header missing", fix=fix, weight=weight))

    csp = page.headers.get("content-security-policy", "").lower()
    if "x-frame-options" in page.headers or "frame-ancestors" in csp:
        out.append(_f("sec-frame", "Security", PASS, "Clickjacking protection present"))
    else:
        out.append(_f("sec-frame", "Security", WARN, "No clickjacking protection",
                      fix="Send 'X-Frame-Options: SAMEORIGIN' or a CSP frame-ancestors rule."))

    gen = ctx.parsed.meta.get("generator", "")
    if any(ch.isdigit() for ch in gen):
        out.append(_f("sec-generator", "Security", WARN, "Software version is publicly exposed", gen,
                      "Remove the generator meta tag so attackers cannot target known versions."))

    if https and ctx.parsed.http_resources:
        n = len(ctx.parsed.http_resources)
        out.append(_f("sec-mixed", "Security", FAIL, "Mixed content detected",
                      f"{n} resource(s) load over plain HTTP, e.g. {ctx.parsed.http_resources[0]}",
                      "Update those URLs to https:// (a search-and-replace in the database usually does it).", weight=2))
    return out


# -------------------------------------------------------- Performance
def performance_checks(ctx: Context) -> list[Finding]:
    out, page = [], ctx.page

    t = page.elapsed
    if t < 1.0:
        out.append(_f("perf-time", "Performance", PASS, "Fast page response", f"{t:.2f}s to download the HTML.", weight=3))
    elif t < 2.5:
        out.append(_f("perf-time", "Performance", WARN, "Page response is slowish", f"{t:.2f}s to download the HTML.",
                      "Enable page caching, upgrade hosting, or add a CDN.", weight=3))
    else:
        out.append(_f("perf-time", "Performance", FAIL, "Page response is slow", f"{t:.2f}s to download the HTML.",
                      "Enable page caching, upgrade hosting, or add a CDN.", weight=3))

    kb = len(page.body) / 1024
    if kb < 200:
        out.append(_f("perf-size", "Performance", PASS, "HTML size is lean", f"{kb:.0f} KB."))
    elif kb < 500:
        out.append(_f("perf-size", "Performance", WARN, "HTML is heavy", f"{kb:.0f} KB.",
                      "Trim inline CSS/JS and unused page-builder markup."))
    else:
        out.append(_f("perf-size", "Performance", FAIL, "HTML is very heavy", f"{kb:.0f} KB.",
                      "Trim inline CSS/JS and unused page-builder markup."))

    if kb > 5:
        enc = page.headers.get("content-encoding", "").lower()
        if enc in ("gzip", "br", "deflate", "zstd"):
            out.append(_f("perf-compress", "Performance", PASS, "Text compression enabled", enc, weight=2))
        else:
            out.append(_f("perf-compress", "Performance", WARN, "Text compression not detected",
                          fix="Enable gzip or Brotli on the server.", weight=2))

    if any(h in page.headers for h in ("cache-control", "expires", "etag", "last-modified")):
        out.append(_f("perf-cache", "Performance", PASS, "Caching headers present"))
    else:
        out.append(_f("perf-cache", "Performance", WARN, "No caching headers",
                      fix="Send Cache-Control headers for static assets and pages."))

    b = ctx.parsed.blocking_scripts
    if b <= 3:
        out.append(_f("perf-blocking", "Performance", PASS, "Few render-blocking scripts", f"{b} in <head>."))
    elif b <= 8:
        out.append(_f("perf-blocking", "Performance", WARN, "Several render-blocking scripts", f"{b} in <head>.",
                      "Add defer/async or move scripts to the footer."))
    else:
        out.append(_f("perf-blocking", "Performance", FAIL, "Many render-blocking scripts", f"{b} in <head>.",
                      "Add defer/async or move scripts to the footer."))

    out.append(_f("info-scripts", "Performance", INFO, "Script tags on page", str(ctx.parsed.script_count)))
    return out


def run_checks(ctx: Context) -> list[Finding]:
    findings: list[Finding] = []
    for fn in (seo_checks, mobile_checks, security_checks, performance_checks):
        findings.extend(fn(ctx))
    return findings
