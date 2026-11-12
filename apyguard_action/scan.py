"""Scan mode: start the CI/CD scan task, wait for it, and count what reaches the threshold."""
from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Callable, Mapping

from apyguard_action.http import HttpError, request_json
from apyguard_action.inputs import SEVERITY_LEVELS, ActionInputs

START_PATH = "api/api_security/github_actions/start_scan"
STATUS_PATH = "api/api_security/integrations/get_scan_status"
RESULTS_PATH = "api/api_security/integrations/get_scan_results"
# The statuses a scan ends in without results.
ENDED_WITHOUT_RESULTS = ("Failed", "Stopped", "Cancelled")
MAX_STATUS_FAILURES = 3


class ScanError(RuntimeError):
    """The scan could not be started, ended without results, or did not finish in time."""


@dataclass(frozen=True)
class ScanOutcome:
    apiscan_id: str
    vulnerabilities: dict[str, int]
    failing_count: int


def count_at_or_above(vulnerabilities: Mapping[str, int] | None, threshold: str) -> int:
    floor = SEVERITY_LEVELS[threshold]
    return sum(
        int(count)
        for severity, count in (vulnerabilities or {}).items()
        if SEVERITY_LEVELS.get(severity, -1) >= floor
    )


def run_scan(
    inputs: ActionInputs,
    request: Callable[..., object] = request_json,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
    poll_seconds: float = 5,
) -> ScanOutcome:
    base = inputs.api_url.rstrip("/")
    headers = {"X-APYGUARD-TOKEN": inputs.api_key or ""}

    def post(path: str, body: dict[str, str]) -> dict:
        return request("POST", f"{base}/{path}", headers, body)

    started = post(START_PATH, {"scan_task_id": inputs.task_id or ""})
    apiscan_id = str(started["apiscan_id"])
    print(f"ApyGuard scan {apiscan_id} started.")

    deadline = clock() + inputs.timeout_minutes * 60
    failures = 0
    while True:
        if clock() > deadline:
            raise ScanError(
                f"Scan {apiscan_id} did not finish within {inputs.timeout_minutes} minutes."
            )
        try:
            status = post(STATUS_PATH, {"apiscan_id": apiscan_id})
        except HttpError as error:
            failures += 1
            if failures >= MAX_STATUS_FAILURES:
                raise ScanError(
                    f"Could not read the status of scan {apiscan_id} {failures} times in a row: {error}"
                ) from error
            sleep(poll_seconds * failures)
            continue
        failures = 0
        state = status.get("status")
        if state == "Completed":
            break
        if state in ENDED_WITHOUT_RESULTS:
            reason = status.get("error") or "no reason given"
            raise ScanError(f"Scan {apiscan_id} ended as {state}: {reason}")
        sleep(poll_seconds)

    results = post(RESULTS_PATH, {"apiscan_id": apiscan_id})
    vulnerabilities = {
        severity: int(count) for severity, count in (results.get("vulnerabilities") or {}).items()
    }
    return ScanOutcome(
        apiscan_id=apiscan_id,
        vulnerabilities=vulnerabilities,
        failing_count=count_at_or_above(vulnerabilities, inputs.severity_threshold),
    )
