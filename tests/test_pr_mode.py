from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from apyguard_action.http import HttpError
from apyguard_action.inputs import InputError, read_inputs
from apyguard_action.pr_mode import run_pr_mode
from apyguard_action.report import COMMENT_MARKER
from tests.fakes import FakeRun, completed

SHA = "b" * 40
MERGE_SHA = "c" * 40
HEAD_PATHS = {"/orders": {"post": {}}, "/users": {"get": {}}}
COMPARISON = {
    "changes": [
        {"kind": "endpointAdded", "method": "POST", "path": "/orders"},
        {"kind": "parameterAdded", "method": "GET", "path": "/users"},
    ]
}


def finding(sensitivity: str) -> dict[str, Any]:
    return {
        "categories": ["authentication"],
        "sensitivityLevel": sensitivity,
        "title": "Route without authentication",
        "path": "/orders",
        "method": "POST",
        "filePath": "app/orders.py",
    }


class Pipeline:
    """A pull request run with the engine, git and GitHub stood in for, inside a temp workspace."""

    def __init__(self, test: unittest.TestCase, head_paths: dict | None = None, findings: list | None = None,
                 project_path: str = ".", runner_os: str = "Linux", event: str = "pull_request",
                 comment_error: HttpError | None = None, threshold: str = "Medium",
                 list_error: HttpError | None = None, checked_out: str = MERGE_SHA) -> None:
        temp = tempfile.TemporaryDirectory()
        test.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.workspace = root / "workspace"
        (self.workspace / project_path).mkdir(parents=True, exist_ok=True)
        (root / "runner").mkdir()
        event_path = root / "event.json"
        event_path.write_text(json.dumps({"pull_request": {"number": 7, "base": {"sha": SHA}}}))
        self.output = root / "output.txt"
        self.summary = root / "summary.md"
        self.env = {
            "GITHUB_WORKSPACE": str(self.workspace),
            "GITHUB_EVENT_NAME": event,
            "GITHUB_SHA": MERGE_SHA,
            "GITHUB_EVENT_PATH": str(event_path),
            "GITHUB_REPOSITORY": "acme/shop",
            "GITHUB_API_URL": "https://api.github.com",
            "GITHUB_OUTPUT": str(self.output),
            "GITHUB_STEP_SUMMARY": str(self.summary),
            "RUNNER_OS": runner_os,
            "RUNNER_ARCH": "X64",
            "RUNNER_TEMP": str(root / "runner"),
        }
        self.inputs = read_inputs({
            "INPUT_MODE": "pr",
            "INPUT_GITHUB_TOKEN": "token-1",
            "INPUT_PROJECT_PATH": project_path,
            "INPUT_SEVERITY_THRESHOLD": threshold,
        })
        self.head_document = {
            "paths": HEAD_PATHS if head_paths is None else head_paths,
            "x-apyguard-analysis": {"findings": findings or []},
        }
        self.base_project_exists = True
        self.compared_base: dict | None = None
        self.comment_error = comment_error
        self.list_error = list_error
        self.checked_out = checked_out
        self.comments: list[dict] = []
        self.run = FakeRun(self.git, self.engine)

    def git(self, command: list[str]):
        if "rev-parse" in command:
            return completed(command, stdout=f"{self.checked_out}\n")
        if "worktree" in command and "add" in command:
            base_root = Path(command[command.index("--detach") + 1])
            base_root.mkdir(parents=True)
            if self.base_project_exists:
                (base_root / self.inputs.project_path).mkdir(parents=True, exist_ok=True)
        return completed(command) if command[0] == "git" else None

    def engine(self, command: list[str]):
        if command[1] == "export":
            is_base = "base" in Path(command[2]).parts
            document = {"paths": {"/users": {"get": {}}}} if is_base else self.head_document
            Path(command[command.index("--output") + 1]).write_text(json.dumps(document))
            return completed(command)
        if command[1] == "compare":
            self.compared_base = json.loads(Path(command[2]).read_text())
            return completed(command, stdout=json.dumps(COMPARISON))
        return None

    def request(self, method: str, url: str, headers: Any, body: Any = None, timeout: float = 30) -> Any:
        if method == "GET":
            if self.list_error is not None:
                raise self.list_error
            return []
        if self.comment_error is not None:
            raise self.comment_error
        self.comments.append(body)
        return {"id": 1}

    def start(self) -> tuple[int, str]:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            code = run_pr_mode(self.inputs, self.env, run=self.run, request=self.request)
        return code, stdout.getvalue()


class RunPrModeTest(unittest.TestCase):
    def test_comments_and_passes_when_findings_are_below_threshold(self) -> None:
        pipeline = Pipeline(self, findings=[finding("low")])

        code, _ = pipeline.start()

        self.assertEqual(code, 0)
        self.assertTrue(pipeline.comments[0]["body"].startswith(COMMENT_MARKER))
        self.assertIn("ApyGuard API changes", pipeline.summary.read_text())
        outputs = pipeline.output.read_text().splitlines()
        self.assertIn("changed_endpoint_count=2", outputs)
        self.assertIn("finding_count=1", outputs)

    def test_fails_when_a_finding_reaches_threshold(self) -> None:
        code, stdout = Pipeline(self, findings=[finding("high")]).start()

        self.assertEqual(code, 1)
        self.assertIn("::error::", stdout)

    def test_new_project_folder_counts_every_endpoint_as_added(self) -> None:
        pipeline = Pipeline(self, project_path="services/api")
        pipeline.base_project_exists = False

        pipeline.start()

        self.assertEqual(pipeline.compared_base, {"openapi": "3.0.3", "paths": {}})
        self.assertEqual(sum(command[1] == "export" for command in pipeline.run.commands), 1)

    def test_fails_clearly_when_head_has_no_endpoints(self) -> None:
        with self.assertRaises(InputError) as raised:
            Pipeline(self, head_paths={}).start()

        self.assertIn("project_path", str(raised.exception))

    def test_fork_pr_warns_and_still_writes_summary(self) -> None:
        pipeline = Pipeline(self, comment_error=HttpError(403, "Resource not accessible by integration"))

        code, stdout = pipeline.start()

        self.assertEqual(code, 0)
        self.assertIn("::warning::", stdout)
        self.assertIn("ApyGuard API changes", pipeline.summary.read_text())

    def test_github_api_failure_keeps_summary_and_threshold_exit(self) -> None:
        pipeline = Pipeline(self, list_error=HttpError(502, "Bad Gateway"))

        code, stdout = pipeline.start()

        self.assertEqual(code, 0)
        self.assertIn("::warning::", stdout)
        self.assertIn("ApyGuard API changes", pipeline.summary.read_text())
        self.assertIn("changed_endpoint_count=2", pipeline.output.read_text().splitlines())

    def test_rejects_a_checkout_other_than_the_merge_commit(self) -> None:
        # Checking out the head commit instead would compare against a base the branch never had.
        with self.assertRaises(InputError) as raised:
            Pipeline(self, checked_out="d" * 40).start()

        self.assertIn("actions/checkout", str(raised.exception))

    def test_rejects_non_linux_runner(self) -> None:
        with self.assertRaises(InputError) as raised:
            Pipeline(self, runner_os="macOS").start()

        self.assertIn("Linux", str(raised.exception))

    def test_rejects_push_events(self) -> None:
        with self.assertRaises(InputError) as raised:
            Pipeline(self, event="push").start()

        self.assertIn("pull_request", str(raised.exception))


if __name__ == "__main__":
    unittest.main()
