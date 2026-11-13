from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from typing import Any

from apyguard_action.__main__ import main
from apyguard_action.github_env import error


def scan_backend(vulnerabilities: dict[str, int]):
    def request(method: str, url: str, headers: Any, body: Any = None, timeout: float = 30) -> Any:
        if url.endswith("/start_scan"):
            return {"apiscan_id": "scan-1"}
        if url.endswith("/get_scan_status"):
            return {"status": "Completed"}
        return {"vulnerabilities": vulnerabilities}

    return request


def run_main(env: dict[str, str], **boundaries: Any) -> tuple[int, str]:
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        code = main(env, sleep=lambda seconds: None, **boundaries)
    return code, stdout.getvalue()


class MainTest(unittest.TestCase):
    def test_scan_mode_exit_code_follows_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir, "output.txt")
            env = {
                "INPUT_MODE": "scan",
                "INPUT_API_KEY": "key",
                "INPUT_TASK_ID": "task-1",
                "GITHUB_OUTPUT": str(output),
            }

            failing, _ = run_main(env, request=scan_backend({"High": 1}))
            passing, _ = run_main(env, request=scan_backend({"Low": 4}))

            self.assertEqual((failing, passing), (1, 0))
            self.assertIn('results={"High": 1}', output.read_text().splitlines())

    def test_known_errors_become_workflow_errors(self) -> None:
        code, stdout = run_main({"INPUT_MODE": "deploy"})

        self.assertEqual(code, 1)
        self.assertIn("::error::mode must be one of scan, pr", stdout)

    def test_workflow_messages_keep_multiline_text_on_one_command(self) -> None:
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            error("engine failed:\nline 1\n100% broken")

        self.assertEqual(stdout.getvalue(), "::error::engine failed:%0Aline 1%0A100%25 broken\n")


if __name__ == "__main__":
    unittest.main()
