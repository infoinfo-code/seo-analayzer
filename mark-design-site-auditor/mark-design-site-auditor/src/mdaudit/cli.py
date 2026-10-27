from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from . import __version__
from .audit import run_audit
from .report import to_html, to_json, to_markdown

EXT = {"md": "md", "html": "html", "json": "json"}


def render(result, fmt: str, brand: str) -> str:
    if fmt == "html":
        return to_html(result, brand)
    if fmt == "json":
        return to_json(result)
    return to_markdown(result, brand)


def slug(url: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", re.sub(r"^https?://", "", url.lower())).strip("-") or "site"


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="mdaudit", description="Audit a website's SEO, mobile, security and speed basics.")
    p.add_argument("url", nargs="?", help="Site to audit, e.g. https://example.com")
    p.add_argument("--batch", metavar="FILE", help="Text file with one URL per line")
    p.add_argument("-f", "--format", choices=sorted(EXT), default="md", help="Report format (default: md)")
    p.add_argument("-o", "--out", help="Write the report to this file (single URL)")
    p.add_argument("--out-dir", default="reports", help="Folder for batch reports (default: reports)")
    p.add_argument("--brand", default="Mark Design", help="Name shown on the report")
    p.add_argument("--timeout", type=int, default=15, help="Per-request timeout in seconds")
    p.add_argument("--fail-under", type=int, metavar="N", help="Exit with code 1 if any score is below N (for CI)")
    p.add_argument("--version", action="version", version=f"mdaudit {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    args = build_parser().parse_args(argv)
    if not args.url and not args.batch:
        build_parser().error("give a URL or --batch FILE")

    worst = 100
    if args.batch:
        urls = [u.strip() for u in Path(args.batch).read_text(encoding="utf-8").splitlines()
                if u.strip() and not u.startswith("#")]
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        rows = []
        for u in urls:
            print(f"Auditing {u} ...", file=sys.stderr)
            res = run_audit(u, args.timeout)
            (out_dir / f"{slug(res.url)}.{EXT[args.format]}").write_text(render(res, args.format, args.brand), encoding="utf-8")
            c = res.counts()
            rows.append([res.url, res.score, res.grade, c["fail"], c["warn"], c["pass"]])
            worst = min(worst, res.score)
        with open(out_dir / "summary.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(["url", "score", "grade", "failed", "warnings", "passed"])
            w.writerows(rows)
        print(f"Wrote {len(rows)} report(s) and summary.csv to {out_dir}/", file=sys.stderr)
    else:
        res = run_audit(args.url, args.timeout)
        text = render(res, args.format, args.brand)
        if args.out:
            Path(args.out).write_text(text, encoding="utf-8")
            print(f"Score {res.score}/100 (grade {res.grade}) - report saved to {args.out}", file=sys.stderr)
        else:
            print(text)
        worst = res.score

    if args.fail_under is not None and worst < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
