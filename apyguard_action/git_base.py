"""A checkout of the pull request's base commit beside the workspace, as a git worktree."""
from __future__ import annotations

import subprocess
from contextlib import contextmanager
from pathlib import Path
from typing import Callable, Iterator


class GitError(RuntimeError):
    """The base commit could not be fetched or checked out."""


def head_commit(workspace: Path, run: Callable[..., subprocess.CompletedProcess] = subprocess.run) -> str:
    result = run(["git", "-C", str(workspace), "rev-parse", "HEAD"], capture_output=True, text=True, check=False)
    if result.returncode != 0:
        raise GitError(f"Could not read the checked-out commit in {workspace}: {result.stderr.strip()}")
    return result.stdout.strip()


@contextmanager
def checkout_base(
    workspace: Path,
    base_sha: str,
    scratch: Path,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
) -> Iterator[Path]:
    def git(*arguments: str) -> subprocess.CompletedProcess:
        return run(["git", "-C", str(workspace), *arguments], capture_output=True, text=True, check=False)

    # actions/checkout fetches one commit by default, so the base is usually missing.
    if git("cat-file", "-e", f"{base_sha}^{{commit}}").returncode != 0:
        fetched = git("fetch", "--no-tags", "--depth=1", "origin", base_sha)
        if fetched.returncode != 0:
            raise GitError(
                f"Could not fetch the pull request's base commit {base_sha}: {fetched.stderr.strip()}. "
                "Check out the repository with actions/checkout and keep persist-credentials on "
                "(its default) so the action can fetch the base."
            )

    target = scratch / "base"
    added = git("worktree", "add", "--detach", str(target), base_sha)
    if added.returncode != 0:
        raise GitError(f"Could not check out the base commit {base_sha}: {added.stderr.strip()}")
    try:
        yield target
    finally:
        removed = git("worktree", "remove", "--force", str(target))
        if removed.returncode != 0:
            # The runner discards its temp folder after the job; the run's result does not depend on this.
            print(f"::warning::Could not remove the base checkout at {target}: {removed.stderr.strip()}")
