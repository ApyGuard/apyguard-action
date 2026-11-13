from __future__ import annotations

import unittest
from typing import Any

from apyguard_action.github_api import upsert_pr_comment
from apyguard_action.http import HttpError
from apyguard_action.report import COMMENT_MARKER

API = "https://api.github.com"
BODY = f"{COMMENT_MARKER}\n### ApyGuard API changes\n"


class FakeGitHub:
    """Serves the issue's comments in pages of 100; a write either answers or raises."""

    def __init__(self, comments: list[dict[str, Any]], write_error: HttpError | None = None) -> None:
        self.comments = comments
        self.write_error = write_error
        self.calls: list[tuple[str, str, dict[str, str], Any]] = []

    def __call__(self, method: str, url: str, headers: Any, body: Any = None, timeout: float = 30) -> Any:
        self.calls.append((method, url, dict(headers), body))
        if method == "GET":
            page = int(url.rsplit("page=", 1)[1])
            return self.comments[(page - 1) * 100 : page * 100]
        if self.write_error is not None:
            raise self.write_error
        return {"id": 1}


def upsert(github: FakeGitHub) -> str:
    return upsert_pr_comment(API, "acme/shop", 7, "token-1", BODY, request=github)


class UpsertPrCommentTest(unittest.TestCase):
    def test_creates_comment_when_none_has_marker(self) -> None:
        github = FakeGitHub([{"id": 1, "body": "Looks good"}])

        self.assertEqual(upsert(github), "created")

        method, url, headers, body = github.calls[-1]
        self.assertEqual((method, url), ("POST", f"{API}/repos/acme/shop/issues/7/comments"))
        self.assertEqual(body, {"body": BODY})
        self.assertEqual(headers["Authorization"], "Bearer token-1")
        self.assertEqual(headers["Accept"], "application/vnd.github+json")
        self.assertEqual(headers["X-GitHub-Api-Version"], "2022-11-28")

    def test_updates_existing_marker_comment_on_second_page(self) -> None:
        others = [{"id": number, "body": "chatter"} for number in range(100)]
        github = FakeGitHub([*others, {"id": 555, "body": f"{COMMENT_MARKER}\nold report"}])

        self.assertEqual(upsert(github), "updated")

        self.assertEqual(
            [url for method, url, _, _ in github.calls if method == "GET"],
            [
                f"{API}/repos/acme/shop/issues/7/comments?per_page=100&page=1",
                f"{API}/repos/acme/shop/issues/7/comments?per_page=100&page=2",
            ],
        )
        self.assertEqual(github.calls[-1][:2], ("PATCH", f"{API}/repos/acme/shop/issues/comments/555"))

    def test_reports_forbidden_for_fork_tokens(self) -> None:
        github = FakeGitHub([], write_error=HttpError(403, "Resource not accessible by integration"))

        self.assertEqual(upsert(github), "forbidden")

    def test_raises_other_http_errors(self) -> None:
        github = FakeGitHub([], write_error=HttpError(500, "Server Error"))

        with self.assertRaises(HttpError):
            upsert(github)


if __name__ == "__main__":
    unittest.main()
