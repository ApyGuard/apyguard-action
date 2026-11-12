from __future__ import annotations

import unittest
from pathlib import Path

from apyguard_action.git_base import GitError, checkout_base
from tests.fakes import FakeRun, completed

WORKSPACE = Path("/work/repo")
SCRATCH = Path("/tmp/apyguard")
SHA = "a" * 40


def base_commit_present(present: bool):
    return lambda command: completed(command, 0 if present else 1) if "cat-file" in command else None


class CheckoutBaseTest(unittest.TestCase):
    def test_fetches_base_only_when_missing(self) -> None:
        present = FakeRun(base_commit_present(True))
        with checkout_base(WORKSPACE, SHA, SCRATCH, run=present) as base:
            self.assertEqual(base, SCRATCH / "base")
        self.assertFalse(present.ran("fetch"))

        missing = FakeRun(base_commit_present(False))
        with checkout_base(WORKSPACE, SHA, SCRATCH, run=missing):
            pass
        self.assertIn(
            ["git", "-C", str(WORKSPACE), "fetch", "--no-tags", "--depth=1", "origin", SHA],
            missing.commands,
        )
        self.assertTrue(missing.ran("worktree", "add", "--detach", str(SCRATCH / "base"), SHA))

    def test_removes_worktree_even_when_body_raises(self) -> None:
        run = FakeRun(base_commit_present(True))

        with self.assertRaises(ValueError):
            with checkout_base(WORKSPACE, SHA, SCRATCH, run=run):
                raise ValueError("export failed")

        self.assertEqual(
            run.commands[-1],
            ["git", "-C", str(WORKSPACE), "worktree", "remove", "--force", str(SCRATCH / "base")],
        )

    def test_fetch_failure_explains_checkout_settings(self) -> None:
        def fetch_fails(command: list[str]):
            if "fetch" in command:
                return completed(command, 128, stderr="fatal: could not read Username")
            return None

        run = FakeRun(base_commit_present(False), fetch_fails)

        with self.assertRaises(GitError) as raised:
            with checkout_base(WORKSPACE, SHA, SCRATCH, run=run):
                pass

        message = str(raised.exception)
        self.assertIn("actions/checkout", message)
        self.assertIn("persist-credentials", message)
        self.assertIn("could not read Username", message)


if __name__ == "__main__":
    unittest.main()
