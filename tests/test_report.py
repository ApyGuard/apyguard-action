from __future__ import annotations

import unittest
from typing import Any

from apyguard_action.report import (
    COMMENT_MARKER,
    build_report,
    failing_findings,
    fit_comment,
    render_markdown,
)


def change(kind: str, method: str, path: str) -> dict[str, str]:
    return {"kind": kind, "method": method, "path": path}


def finding(sensitivity: str, method: str | None, path: str, title: str = "Finding") -> dict[str, Any]:
    return {
        "categories": ["authentication"],
        "sensitivityLevel": sensitivity,
        "title": title,
        "description": "",
        "path": path,
        "method": method,
        "filePath": "app/routes.py",
        "functionName": "handler",
        "evidence": [],
    }


def head(*findings: dict[str, Any]) -> dict[str, Any]:
    return {"paths": {}, "x-apyguard-analysis": {"findings": list(findings)}}


COMPARISON = {
    "changes": [
        change("endpointAdded", "POST", "/orders"),
        change("parameterAdded", "GET", "/users"),
        change("bodyPropertyAdded", "GET", "/users"),
        change("endpointRemoved", "DELETE", "/old"),
    ]
}


class BuildReportTest(unittest.TestCase):
    def test_classifies_added_changed_removed(self) -> None:
        report = build_report(COMPARISON, head())

        self.assertEqual(report.added, [("POST", "/orders")])
        self.assertEqual(report.changed, [("GET", "/users")])
        self.assertEqual(report.removed, [("DELETE", "/old")])
        self.assertEqual(report.kinds[("GET", "/users")], ["parameterAdded", "bodyPropertyAdded"])

    def test_keeps_findings_only_on_added_or_changed_endpoints(self) -> None:
        on_new = finding("high", "POST", "/orders")
        on_changed = finding("low", "GET", "/users")
        untouched = finding("high", "GET", "/health")

        report = build_report(COMPARISON, head(on_new, on_changed, untouched))

        self.assertEqual(report.findings, [on_new, on_changed])

    def test_matches_method_less_findings_by_path(self) -> None:
        on_changed_path = finding("medium", None, "/users")
        elsewhere = finding("medium", None, "/health")

        report = build_report(COMPARISON, head(on_changed_path, elsewhere))

        self.assertEqual(report.findings, [on_changed_path])

    def test_failing_findings_respects_threshold(self) -> None:
        report = build_report(COMPARISON, head(finding("high", "POST", "/orders"), finding("low", "GET", "/users")))

        self.assertEqual(len(failing_findings(report, "Medium")), 1)
        self.assertEqual(len(failing_findings(report, "Critical")), 0)
        self.assertEqual(len(failing_findings(report, "Informational")), 2)


class FitCommentTest(unittest.TestCase):
    def test_fit_comment_keeps_comments_under_githubs_limit(self) -> None:
        many = {"changes": [change("endpointAdded", "GET", f"/resources/{number}/items") for number in range(5000)]}
        body = render_markdown(build_report(many, head()), "Medium")
        self.assertGreater(len(body), 65536)

        fitted = fit_comment(body)

        self.assertLessEqual(len(fitted), 65536)
        self.assertTrue(fitted.startswith(COMMENT_MARKER))
        self.assertIn("full report is in the job summary", fitted)

    def test_fit_comment_leaves_short_comments_alone(self) -> None:
        body = render_markdown(build_report(COMPARISON, head()), "Medium")

        self.assertEqual(fit_comment(body), body)


class RenderMarkdownTest(unittest.TestCase):
    def test_markdown_without_changes(self) -> None:
        body = render_markdown(build_report({"changes": []}, head()), "Medium")

        self.assertTrue(body.startswith(COMMENT_MARKER))
        self.assertIn("No API changes in this pull request.", body)

    def test_markdown_lists_counts_and_findings(self) -> None:
        report = build_report(
            {"changes": [change("endpointAdded", "POST", "/orders"), change("parameterAdded", "GET", "/users")]},
            head(finding("high", "POST", "/orders", title="Admin route without authentication")),
        )

        body = render_markdown(report, "Medium")

        self.assertIn("1 added · 1 changed · 0 removed endpoints", body)
        self.assertIn("| `POST` | `/orders` | added |", body)
        self.assertIn("| `GET` | `/users` | parameterAdded |", body)
        self.assertIn("**High** Admin route without authentication — `POST /orders` (app/routes.py)", body)
        self.assertIn("Failing: 1 finding(s) at Medium or above.", body)


if __name__ == "__main__":
    unittest.main()
