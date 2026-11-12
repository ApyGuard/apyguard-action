"""Pull request mode: what the pull request changes in the API, reported on the pull request.

Only the GitHub API is called. The project's code and the documents made from it stay on the runner.
"""
from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Callable, Mapping

from apyguard_action import github_env
from apyguard_action.engine import compare_documents, export_openapi
from apyguard_action.git_base import checkout_base, head_commit
from apyguard_action.github_api import upsert_pr_comment
from apyguard_action.http import HttpError, request_json
from apyguard_action.inputs import ActionInputs, InputError
from apyguard_action.report import build_report, failing_findings, fit_comment, render_markdown

EMPTY_DOCUMENT = {"openapi": "3.0.3", "paths": {}}


def run_pr_mode(
    inputs: ActionInputs,
    env: Mapping[str, str],
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    request: Callable[..., object] = request_json,
) -> int:
    if env.get("RUNNER_OS") != "Linux" or env.get("RUNNER_ARCH") != "X64":
        raise InputError(
            "mode: pr runs on Linux X64 runners only (the APIScout engine is built for them); "
            f"this runner is {env.get('RUNNER_OS')} {env.get('RUNNER_ARCH')}."
        )
    event_name = env.get("GITHUB_EVENT_NAME")
    if event_name != "pull_request":
        raise InputError(f"mode: pr runs on pull_request events, not {event_name}.")
    pull_request = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))["pull_request"]
    base_sha = pull_request["base"]["sha"]

    workspace = Path(env["GITHUB_WORKSPACE"])
    # The base is compared with the merge commit actions/checkout takes by default. A checkout of
    # the head commit would be compared with a base tip the branch may never have been on.
    checked_out = head_commit(workspace, run=run)
    merge_commit = env.get("GITHUB_SHA", "")
    if checked_out != merge_commit:
        raise InputError(
            f"mode: pr needs the pull request's merge commit {merge_commit[:12]} checked out, "
            f"not {checked_out[:12]}. Use actions/checkout without ref: on pull_request events."
        )
    head_project = workspace / inputs.project_path
    if not head_project.is_dir():
        raise InputError(f"project_path {inputs.project_path!r} is not a folder in the repository.")

    with tempfile.TemporaryDirectory(dir=env.get("RUNNER_TEMP")) as scratch_name:
        scratch = Path(scratch_name)
        head_file = scratch / "head.json"
        head_document = export_openapi(head_project, head_file, run=run)
        if not head_document.get("paths"):
            raise InputError(
                f"APIScout found no API endpoints in {inputs.project_path}. "
                "Set project_path to the folder of the API project."
            )

        base_file = scratch / "base.json"
        with checkout_base(workspace, base_sha, scratch, run=run) as base_root:
            base_project = base_root / inputs.project_path
            if base_project.is_dir():
                export_openapi(base_project, base_file, run=run)
            else:
                # The pull request adds the API project: everything in it is new.
                base_file.write_text(json.dumps(EMPTY_DOCUMENT), encoding="utf-8")
        comparison = compare_documents(base_file, head_file, run=run)

    report = build_report(comparison, head_document)
    body = render_markdown(report, inputs.severity_threshold)
    # The summary and outputs come first: the comment is the part that can fail.
    github_env.append_step_summary(env, body)
    github_env.set_output(env, "changed_endpoint_count", str(len(report.added) + len(report.changed)))
    github_env.set_output(env, "finding_count", str(len(report.findings)))
    if inputs.github_token:
        try:
            result = upsert_pr_comment(
                env.get("GITHUB_API_URL", "https://api.github.com"),
                env["GITHUB_REPOSITORY"],
                int(pull_request["number"]),
                inputs.github_token,
                fit_comment(body),
                request=request,
            )
        except HttpError as failure:
            github_env.warning(f"Could not comment on the pull request ({failure}). The report is in the job summary.")
        else:
            if result == "forbidden":
                github_env.warning(
                    "The token cannot comment on this pull request (a pull request from a fork has a "
                    "read-only token). The report is in the job summary."
                )
    else:
        github_env.warning("No github_token, so the report is only in the job summary.")

    failing = failing_findings(report, inputs.severity_threshold)
    if failing:
        github_env.error(
            f"{len(failing)} APIScout finding(s) at {inputs.severity_threshold} or above on the "
            "endpoints this pull request adds or changes."
        )
        return 1
    return 0
