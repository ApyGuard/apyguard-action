"""The pull request comment that carries the report: one per pull request, updated on each run."""
from __future__ import annotations

from typing import Callable, Literal

from apyguard_action.http import HttpError, request_json
from apyguard_action.report import COMMENT_MARKER

PAGE_SIZE = 100
# What a token without write access gets back, as on a pull request from a fork.
FORBIDDEN_STATUSES = (403, 404)


def upsert_pr_comment(
    api_url: str,
    repository: str,
    pr_number: int,
    token: str,
    body: str,
    request: Callable[..., object] = request_json,
) -> Literal["created", "updated", "forbidden"]:
    base = api_url.rstrip("/")
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }

    existing_id = None
    page = 1
    while existing_id is None:
        comments = request(
            "GET",
            f"{base}/repos/{repository}/issues/{pr_number}/comments?per_page={PAGE_SIZE}&page={page}",
            headers,
        )
        existing_id = next(
            (comment["id"] for comment in comments if str(comment.get("body", "")).startswith(COMMENT_MARKER)),
            None,
        )
        if len(comments) < PAGE_SIZE:
            break
        page += 1

    try:
        if existing_id is None:
            request("POST", f"{base}/repos/{repository}/issues/{pr_number}/comments", headers, {"body": body})
            return "created"
        request("PATCH", f"{base}/repos/{repository}/issues/comments/{existing_id}", headers, {"body": body})
        return "updated"
    except HttpError as error:
        if error.status in FORBIDDEN_STATUSES:
            return "forbidden"
        raise
