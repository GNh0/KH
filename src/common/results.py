"""Findings describe an inspected artifact; they do not authorize host actions."""
from dataclasses import asdict, dataclass, field
import json
from typing import Any, Iterable, Literal

Severity = Literal["error", "warning", "info"]


@dataclass(frozen=True)
class Issue:
    code: str
    severity: Severity
    message: str
    path: str | None = None
    line: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.severity not in {"error", "warning", "info"}:
            raise ValueError(f"invalid severity: {self.severity}")

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in asdict(self).items() if value is not None}


@dataclass
class CheckResult:
    issues: list[Issue] = field(default_factory=list)
    checked: list[str] = field(default_factory=list)
    not_checked: list[str] = field(default_factory=list)
    incomplete: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def status(self) -> str:
        if any(item.severity == "error" for item in self.issues):
            return "failed"
        return "incomplete" if self.incomplete else "passed"

    @property
    def success(self) -> bool:
        return self.status == "passed"

    @property
    def exit_code(self) -> int:
        return {"passed": 0, "failed": 1, "incomplete": 2}[self.status]

    def to_dict(self) -> dict[str, Any]:
        review_keys = ('comparison_baselines', 'review_status', 'project_style_verified', 'designer_preservation')
        review = {key: self.metadata[key] for key in review_keys if key in self.metadata}
        other = {key: value for key, value in self.metadata.items() if key not in review_keys}
        return {"status": self.status, **review, "issues": [i.to_dict() for i in self.issues],
                "checked": self.checked, "not_checked": self.not_checked, **other}

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)


@dataclass
class HarnessResult:
    """Compatibility value for retained domain APIs, without a runtime/ledger."""
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def from_legacy_issues(items: Iterable[dict[str, Any]]) -> list[Issue]:
    return [Issue(str(i["code"]), i.get("severity", "error"), str(i["message"]),
                  path=i.get("path"), line=i.get("line"),
                  details={k: v for k, v in i.items() if k not in {"code", "severity", "message", "path", "line"}})
            for i in items]
