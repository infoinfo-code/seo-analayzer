from __future__ import annotations

import json
from html import escape

from .models import FAIL, INFO, PASS, WARN, AuditResult

LABEL = {PASS: "PASS", WARN: "WARN", FAIL: "FAIL", INFO: "INFO"}
ORDER = {FAIL: 0, WARN: 1, PASS: 2, INFO: 3}


def to_json(r: AuditResult) -> str:
    return json.dumps(r.to_dict(), indent=2, ensure_ascii=False)


def to_markdown(r: AuditResult, brand: str = "Mark Design") -> str:
    c = r.counts()
    lines = [
        f"# Website Audit: {r.final_url or r.url}",
        "",
        f"**Prepared by {brand}** | {r.audited_at}",
        "",
        f"**Score: {r.score}/100 (grade {r.grade})** - {c[FAIL]} failed, {c[WARN]} warnings, {c[PASS]} passed",
    ]
    if r.platform:
        lines.append(f"\nDetected: {', '.join(r.platform)}")
    for cat, items in r.by_category().items():
        lines += ["", f"## {cat}", ""]
        for f in sorted(items, key=lambda x: ORDER[x.status]):
            lines.append(f"- **[{LABEL[f.status]}]** {f.title}" + (f" - {f.detail}" if f.detail else ""))
            if f.fix and f.status in (WARN, FAIL):
                lines.append(f"  - Fix: {f.fix}")
    lines.append("")
    return "\n".join(lines)


_CSS = """
:root{--bg:#f6f7f9;--card:#fff;--ink:#1c2430;--muted:#667085;--line:#e4e7ec;
--pass:#12805c;--warn:#b25e09;--fail:#c0262d;--accent:#0b5fff}
@media(prefers-color-scheme:dark){:root{--bg:#10151c;--card:#182029;--ink:#e8edf3;--muted:#98a2b3;--line:#2a3441;
--pass:#3ccf91;--warn:#f0a23b;--fail:#ff6b72;--accent:#6ea4ff}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:16px/1.5 system-ui,-apple-system,"Segoe UI",Roboto,sans-serif}
.wrap{max-width:860px;margin:0 auto;padding:32px 20px 64px}
header{display:flex;gap:24px;align-items:center;flex-wrap:wrap;margin-bottom:28px}
.gauge{--p:0;width:120px;height:120px;border-radius:50%;display:grid;place-items:center;flex:none;
background:conic-gradient(var(--c) calc(var(--p)*1%),var(--line) 0)}
.gauge span{width:92px;height:92px;border-radius:50%;background:var(--card);display:grid;place-items:center;
font-size:30px;font-weight:700}
h1{font-size:22px;margin:0 0 4px;word-break:break-all}.sub{color:var(--muted);font-size:14px}
.chips{display:flex;gap:8px;margin-top:10px;flex-wrap:wrap}
.chip{border:1px solid var(--line);background:var(--card);border-radius:99px;padding:2px 12px;font-size:13px}
section{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:8px 20px;margin-bottom:18px}
h2{font-size:17px;margin:14px 0 6px}
.row{padding:12px 0;border-top:1px solid var(--line)}.row:first-of-type{border-top:0}
.badge{display:inline-block;min-width:48px;text-align:center;font-size:11px;font-weight:700;border-radius:6px;
padding:1px 6px;margin-right:8px;color:#fff}
.pass{background:var(--pass)}.warn{background:var(--warn)}.fail{background:var(--fail)}.info{background:var(--muted)}
.detail{color:var(--muted);font-size:14px;margin:2px 0 0 58px}
.fix{font-size:14px;margin:4px 0 0 58px}.fix b{color:var(--accent)}
footer{color:var(--muted);font-size:13px;text-align:center;margin-top:28px}
@media print{body{background:#fff}section{break-inside:avoid}}
"""


def to_html(r: AuditResult, brand: str = "Mark Design", contact: str = "https://mark-design.net/contact/") -> str:
    c = r.counts()
    colour = "var(--pass)" if r.score >= 80 else "var(--warn)" if r.score >= 55 else "var(--fail)"
    parts = [
        '<!doctype html><html lang="en"><head><meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        f"<title>Website Audit - {escape(r.final_url or r.url)}</title><style>{_CSS}</style></head><body><div class=\"wrap\">",
        f'<header><div class="gauge" style="--p:{r.score};--c:{colour}"><span>{r.score}</span></div><div>',
        f"<h1>{escape(r.final_url or r.url)}</h1>",
        f'<div class="sub">Website health audit by {escape(brand)} &middot; {escape(r.audited_at)} &middot; Grade {r.grade}</div>',
        '<div class="chips">',
        f'<span class="chip">{c[FAIL]} failed</span><span class="chip">{c[WARN]} warnings</span>'
        f'<span class="chip">{c[PASS]} passed</span>',
    ]
    for p in r.platform:
        parts.append(f'<span class="chip">{escape(p)}</span>')
    parts.append("</div></div></header>")

    for cat, items in r.by_category().items():
        parts.append(f"<section><h2>{escape(cat)}</h2>")
        for f in sorted(items, key=lambda x: ORDER[x.status]):
            parts.append(f'<div class="row"><span class="badge {f.status}">{LABEL[f.status]}</span>{escape(f.title)}')
            if f.detail:
                parts.append(f'<div class="detail">{escape(f.detail)}</div>')
            if f.fix and f.status in (WARN, FAIL):
                parts.append(f'<div class="fix"><b>How to fix:</b> {escape(f.fix)}</div>')
            parts.append("</div>")
        parts.append("</section>")

    parts.append(
        f'<footer>Want these fixed? <a href="{escape(contact)}" style="color:var(--accent)">Talk to {escape(brand)}</a>'
        "</footer></div></body></html>"
    )
    return "".join(parts)
