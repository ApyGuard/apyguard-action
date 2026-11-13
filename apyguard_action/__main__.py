"""Entry point: python -m apyguard_action, run by the composite action's step."""
from __future__ import annotations

import json
import os
import subprocess
import time
from typing import Callable, Mapping

from apyguard_action import github_env
from apyguard_action.engine import EngineError
from apyguard_action.git_base import GitError
from apyguard_action.http import HttpError, request_json
from apyguard_action.inputs import InputError, read_inputs
from apyguard_action.pr_mode import run_pr_mode
from apyguard_action.scan import ScanError, run_scan


def main(
    env: Mapping[str, str] = os.environ,
    request: Callable[..., object] = request_json,
    run: Callable[..., subprocess.CompletedProcess] = subprocess.run,
    sleep: Callable[[float], None] = time.sleep,
) -> int:
    try:
        inputs = read_inputs(env)
        if inputs.mode == "pr":
            return run_pr_mode(inputs, env, run=run, request=request)

        outcome = run_scan(inputs, request=request, sleep=sleep)
        github_env.set_output(env, "results", json.dumps(outcome.vulnerabilities))
        if outcome.failing_count:
            github_env.error(
                f"{outcome.failing_count} vulnerabilities at {inputs.severity_threshold} or above "
                f"in scan {outcome.apiscan_id}."
            )
            return 1
        print(f"No vulnerabilities at {inputs.severity_threshold} or above in scan {outcome.apiscan_id}.")
        return 0
    except (InputError, ScanError, EngineError, GitError, HttpError) as failure:
        github_env.error(str(failure))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
