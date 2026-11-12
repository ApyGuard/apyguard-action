from __future__ import annotations

import unittest
from typing import Any

from apyguard_action.http import HttpError
from apyguard_action.inputs import read_inputs
from apyguard_action.scan import ScanError, run_scan


def scan_inputs(**overrides: str):
    env = {"INPUT_MODE": "scan", "INPUT_API_KEY": "key", "INPUT_TASK_ID": "task-1"}
    env.update({f"INPUT_{name.upper()}": value for name, value in overrides.items()})
    return read_inputs(env)


class FakeBackend:
    """Answers the three scan endpoints; status replies are taken in order."""

    def __init__(self, statuses: list[Any], vulnerabilities: Any = None) -> None:
        self.calls: list[tuple[str, str, dict[str, str], Any]] = []
        self.statuses = list(statuses)
        self.vulnerabilities = vulnerabilities

    def __call__(self, method: str, url: str, headers: Any, body: Any = None, timeout: float = 30) -> Any:
        self.calls.append((method, url, dict(headers), body))
        if url.endswith("/github_actions/start_scan"):
            return {"status": "success", "apiscan_id": "scan-1"}
        if url.endswith("/integrations/get_scan_status"):
            reply = self.statuses.pop(0)
            if isinstance(reply, Exception):
                raise reply
            return reply
        if url.endswith("/integrations/get_scan_results"):
            return {"status": "success", "vulnerabilities": self.vulnerabilities}
        raise AssertionError(f"unexpected call to {url}")


class Clock:
    def __init__(self, step_seconds: float = 0) -> None:
        self.now = 0.0
        self.step_seconds = step_seconds

    def __call__(self) -> float:
        self.now += self.step_seconds
        return self.now


def run(backend: FakeBackend, clock: Clock | None = None, **overrides: str):
    return run_scan(
        scan_inputs(**overrides),
        request=backend,
        sleep=lambda seconds: None,
        clock=clock or Clock(),
    )


class RunScanTest(unittest.TestCase):
    def test_joins_api_url_without_double_slashes(self) -> None:
        backend = FakeBackend([{"status": "Completed"}], {})

        run(backend, api_url="https://api.apyguard.com/")

        method, url, headers, body = backend.calls[0]
        self.assertEqual(method, "POST")
        self.assertEqual(url, "https://api.apyguard.com/api/api_security/github_actions/start_scan")
        self.assertEqual(headers["X-APYGUARD-TOKEN"], "key")
        self.assertEqual(body, {"scan_task_id": "task-1"})

    def test_returns_counts_when_scan_completes(self) -> None:
        backend = FakeBackend([{"status": "Running"}, {"status": "Completed"}], {"High": 2, "Low": 3})

        outcome = run(backend, severity_threshold="Medium")

        self.assertEqual(outcome.apiscan_id, "scan-1")
        self.assertEqual(outcome.vulnerabilities, {"High": 2, "Low": 3})
        self.assertEqual(outcome.failing_count, 2)
        self.assertEqual(backend.calls[-1][3], {"apiscan_id": "scan-1"})

    def test_fails_with_backend_error_when_scan_failed(self) -> None:
        backend = FakeBackend([{"status": "Failed", "error": "target unreachable"}])

        with self.assertRaises(ScanError) as raised:
            run(backend)

        self.assertIn("target unreachable", str(raised.exception))

    def test_fails_when_scan_stopped_or_cancelled(self) -> None:
        for status in ("Stopped", "Cancelled"):
            with self.subTest(status=status), self.assertRaises(ScanError) as raised:
                run(FakeBackend([{"status": status}]))
            self.assertIn(status, str(raised.exception))

    def test_treats_null_vulnerabilities_as_none_found(self) -> None:
        outcome = run(FakeBackend([{"status": "Completed"}], None))

        self.assertEqual(outcome.vulnerabilities, {})
        self.assertEqual(outcome.failing_count, 0)

    def test_gives_up_after_timeout(self) -> None:
        backend = FakeBackend([{"status": "Running"}] * 5)

        with self.assertRaises(ScanError) as raised:
            run(backend, clock=Clock(step_seconds=61 * 60), timeout_minutes="60")

        self.assertIn("60 minutes", str(raised.exception))

    def test_retries_status_three_times_then_fails(self) -> None:
        backend = FakeBackend([HttpError(502, "Bad Gateway")] * 3)

        with self.assertRaises(ScanError) as raised:
            run(backend)

        self.assertIn("502", str(raised.exception))

    def test_recovers_after_two_failed_status_checks(self) -> None:
        backend = FakeBackend(
            [HttpError(502, "Bad Gateway"), HttpError(503, "Unavailable"), {"status": "Completed"}],
            {"Critical": 1},
        )

        outcome = run(backend)

        self.assertEqual(outcome.failing_count, 1)


if __name__ == "__main__":
    unittest.main()
