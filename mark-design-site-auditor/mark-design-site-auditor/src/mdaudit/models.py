from __future__ import annotations

from dataclasses import dataclass, field

PASS, WARN, FAIL, INFO = "pass", "warn", "fail", "info"
CATEGORIES = ("SEO", "Mobile", "Security", "Performance")


@dataclass
class Finding:
    id: str
    category: str
    status: str  # pass | warn | fail | info
    title: str
    detail: str = ""
    fix: str = ""
    weight: int = 1


@dataclass
class AuditResult:
    url: str
    final_url: str
    audited_at: str
    platform: list[str] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def score(self) -> int:
        scored = [f for f in self.findings if f.status != INFO]
        total = sum(f.weight for f in scored)
        if not total:
            return 0
        earned = sum(f.weight * {PASS: 1.0, WARN: 0.5, FAIL: 0.0}[f.status] for f in scored)
        return round(100 * earned / total)

    @property
    def grade(self) -> str:
        s = self.score
        for cutoff, letter in ((90, "A"), (80, "B"), (65, "C"), (50, "D")):
            if s >= cutoff:
                return letter
        return "F"

    def by_category(self) -> dict[str, list[Finding]]:
        out: dict[str, list[Finding]] = {}
        for f in self.findings:
            out.setdefault(f.category, []).append(f)
        return out

    def counts(self) -> dict[str, int]:
        c = {PASS: 0, WARN: 0, FAIL: 0, INFO: 0}
        for f in self.findings:
            c[f.status] += 1
        return c

    def to_dict(self) -> dict:
        return {
            "url": self.url,
            "final_url": self.final_url,
            "audited_at": self.audited_at,
            "platform": self.platform,
            "score": self.score,
            "grade": self.grade,
            "counts": self.counts(),
            "findings": [f.__dict__ for f in self.findings],
        }
