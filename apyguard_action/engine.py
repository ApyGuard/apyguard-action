"""The APIScout engine, run through the apyguard-engine command the vendored wheel installs."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path
from typing import Any, Callable

ENGINE = "apyguard-engine"
STDERR_TAIL_LINES = 20


class EngineError(RuntimeError):
    """The engine could not run, failed, or wrote something that is not JSON."""


def export_openapi(
    project_dir: Path, output: Path, run: Callable[..., subprocess.CompletedProcess] = subprocess.run
) -> dict[str, Any]:
    _run_engine(["export", str(project_dir), "--output", str(output), "--format", "json"], run)
    try:
        return json.loads(output.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise EngineError(f"{ENGINE} export did not write a readable document to {output}: {error}") from error


def compare_documents(
    previous: Path, current: Path, run: Callable[..., subprocess.CompletedProcess] = subprocess.run
) -> dict[str, Any]:
    result = _run_engine(["compare", str(previous), str(current)], run)
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise EngineError(f"{ENGINE} compare printed something that is not JSON: {error}") from error


def _run_engine(arguments: list[str], run: Callable[..., subprocess.CompletedProcess]) -> subprocess.CompletedProcess:
    # AI inference stays off whatever the job sets: it would send the project's code to a provider.
    environment = {**os.environ, "APYGUARD_AI_ENABLED": "false"}
    try:
        result = run([ENGINE, *arguments], capture_output=True, text=True, check=False, env=environment)
    except FileNotFoundError as error:
        raise EngineError(
            f"{ENGINE} is not installed. mode: pr installs it from the action's vendor folder on Linux X64 runners."
        ) from error
    if result.returncode != 0:
        tail = "\n".join((result.stderr or "").splitlines()[-STDERR_TAIL_LINES:])
        raise EngineError(f"{ENGINE} {arguments[0]} exited with {result.returncode}:\n{tail}")
    return result
