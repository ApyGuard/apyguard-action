"""What a pull request changed in the API, and the APIScout findings on those endpoints."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apyguard_action.inputs import SEVERITY_LEVELS

COMMENT_MARKER = "<!-- apyguard-api-changes -->"
# GitHub refuses a comment body longer than this many characters.
GITHUB_COMMENT_LIMIT = 65536
SENSITIVITY_TO_SEVERITY = {"high": "High", "medium": "Medium", "low": "Low"}

Endpoint = tuple[str, str]  # (METHOD, path)


@dataclass(frozen=True)
class ChangeReport:
    added: list[Endpoint]
    changed: list[Endpoint]
    removed: list[Endpoint]
    kinds: dict[Endpoint, list[str]] = field(default_factory=dict)
    findings: list[dict[str, Any]] = field(default_factory=list)


def build_report(comparison: dict[str, Any], head_document: dict[str, Any]) -> ChangeReport:
    added: set[Endpoint] = set()
    removed: set[Endpoint] = set()
    kinds: dict[Endpoint, list[str]] = {}
    for item in comparison.get("changes", []):
        endpoint = (str(item["method"]).upper(), str(item["path"]))
        if item["kind"] == "endpointAdded":
            added.add(endpoint)
        elif item["kind"] == "endpointRemoved":
            removed.add(endpoint)
        elif item["kind"] not in kinds.setdefault(endpoint, []):
            kinds[endpoint].append(item["kind"])
    changed = set(kinds) - added

    touched = added | changed
    touched_paths = {path for _, path in touched}
    analysis = head_document.get("x-apyguard-analysis") or {}
    findings = [
        finding
        for finding in analysis.get("findings", [])
        if (
            (str(finding["method"]).upper(), finding["path"]) in touched
            if finding.get("method")
            else finding.get("path") in touched_paths
        )
    ]

    def ordered(endpoints: set[Endpoint]) -> list[Endpoint]:
        return sorted(endpoints, key=lambda endpoint: (endpoint[1], endpoint[0]))

    return ChangeReport(
        added=ordered(added),
        changed=ordered(changed),
        removed=ordered(removed),
        kinds={endpoint: kinds[endpoint] for endpoint in ordered(changed)},
        findings=findings,
    )


def severity_of(finding: dict[str, Any]) -> str:
    return SENSITIVITY_TO_SEVERITY.get(str(finding.get("sensitivityLevel")), "Informational")


def failing_findings(report: ChangeReport, threshold: str) -> list[dict[str, Any]]:
    floor = SEVERITY_LEVELS[threshold]
    return [finding for finding in report.findings if SEVERITY_LEVELS[severity_of(finding)] >= floor]


def render_markdown(report: ChangeReport, threshold: str) -> str:
    lines = [COMMENT_MARKER, "### ApyGuard API changes", ""]
    if not (report.added or report.changed or report.removed):
        lines.append("No API changes in this pull request.")
        return "\n".join(lines) + "\n"

    lines += [
        f"{len(report.added)} added · {len(report.changed)} changed · {len(report.removed)} removed endpoints",
        "",
        "| Method | Path | Change |",
        "| --- | --- | --- |",
    ]
    rows = (
        [(endpoint, "added") for endpoint in report.added]
        + [(endpoint, ", ".join(report.kinds[endpoint])) for endpoint in report.changed]
        + [(endpoint, "removed") for endpoint in report.removed]
    )
    lines += [f"| `{method}` | `{path}` | {change} |" for (method, path), change in rows]

    if report.findings:
        lines += ["", f"#### Findings on these endpoints ({len(report.findings)})", ""]
        for finding in report.findings:
            place = f"{finding['method'].upper()} {finding['path']}" if finding.get("method") else finding["path"]
            source = f" ({finding['filePath']})" if finding.get("filePath") else ""
            lines.append(f"- **{severity_of(finding)}** {finding['title']} — `{place}`{source}")

    failing = failing_findings(report, threshold)
    if failing:
        lines += ["", f"Failing: {len(failing)} finding(s) at {threshold} or above."]
    return "\n".join(lines) + "\n"


def fit_comment(markdown: str, limit: int = GITHUB_COMMENT_LIMIT) -> str:
    """The report cut at a line to fit a pull request comment; the job summary keeps all of it."""
    if len(markdown) <= limit:
        return markdown
    lines = markdown.splitlines()
    # Room for the closing note, whose count runs to a few digits.
    budget = limit - 200
    kept: list[str] = []
    size = 0
    for line in lines:
        if size + len(line) + 1 > budget:
            break
        kept.append(line)
        size += len(line) + 1
    note = f"…and {len(lines) - len(kept)} more lines; the full report is in the job summary."
    return "\n".join(kept) + f"\n\n{note}\n"
