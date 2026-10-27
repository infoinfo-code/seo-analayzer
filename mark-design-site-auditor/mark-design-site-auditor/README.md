# Mark Design Site Auditor

A small, zero-dependency command-line tool that audits any website for the basics that decide whether it ranks, converts and stays safe, then turns the result into a clean report you can send to a client.

Built for the workflow of a web agency: run it before a sales call to show a prospect what is broken, and run it monthly on maintenance clients to prove what you fixed.

## What it checks

| Area | Checks |
|---|---|
| **SEO** | title and meta description length, single H1, canonical, `lang`, Open Graph, JSON-LD, image alt coverage, robots.txt (including accidental `Disallow: /`), XML sitemap |
| **Mobile** | responsive viewport tag |
| **Security** | HTTPS, HTTP-to-HTTPS redirect, TLS certificate expiry, HSTS, CSP, Referrer-Policy, X-Content-Type-Options, clickjacking protection, exposed CMS version, mixed content |
| **Performance** | HTML response time, HTML weight, gzip/Brotli, caching headers, render-blocking scripts in `<head>` |

Every finding is weighted, scored into a 0-100 health score with an A-F grade, and comes with a plain-English "how to fix" line. It also detects WordPress, Avada, WooCommerce, Shopify and Wix.

## Install (Windows, macOS, Linux)

Requires Python 3.9+. There are no third-party packages.

```bash
git clone https://github.com/<your-username>/mark-design-site-auditor.git
cd mark-design-site-auditor
py -m pip install -e .        # on macOS/Linux: python3 -m pip install -e .
```

## Usage

```bash
# Quick look in the terminal
py -m mdaudit https://mark-design.net

# Client-ready HTML report (opens in any browser, prints cleanly to PDF)
py -m mdaudit https://mark-design.net -f html -o mark-design-audit.html

# Audit many sites at once -> one report per site + summary.csv
py -m mdaudit --batch examples/urls.example.txt -f html --out-dir reports

# White-label it for another brand
py -m mdaudit https://example.com -f html -o out.html --brand "Your Agency"

# Machine-readable output, or fail a CI job if the score drops
py -m mdaudit https://example.com -f json
py -m mdaudit https://example.com --fail-under 80
```

After `pip install -e .` the shorter `mdaudit <url>` command also works.

See [`examples/sample-report.html`](examples/sample-report.html) for what a report looks like (generated against a local demo page).

## Project layout

```
src/mdaudit/
  fetcher.py   HTTP + TLS helpers (stdlib only)
  parser.py    HTML signal extraction
  checks.py    pure check functions -> Findings (the part to extend)
  audit.py     orchestrates fetching + checks
  report.py    Markdown / HTML / JSON output
  cli.py       command-line interface
tests/         unit + local-server integration tests
```

## Adding a check

Write a function in `checks.py` that takes a `Context` and returns a list of `Finding` objects, then add it to the tuple in `run_checks`. Add a unit test that builds a `Context` by hand. No network needed.

## Run the tests

```bash
py -m unittest discover -s tests -v
```

## Limits (by design)

It audits one page (the URL you give it) plus `robots.txt` and the sitemap. It is a fast first-pass health check, not a replacement for Lighthouse, Search Console or a manual review. Only audit sites you own or have permission to test.

## License

MIT, see [LICENSE](LICENSE).
