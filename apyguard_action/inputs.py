"""The action's inputs, read from the INPUT_* variables the composite step passes."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Mapping

SEVERITY_LEVELS: dict[str, int] = {
    "Critical": 4,
    "High": 3,
    "Medium": 2,
    "Low": 1,
    "Informational": 0,
}
MODES = ("scan", "pr")


class InputError(ValueError):
    """An input the action cannot run with; the message names the input."""


@dataclass(frozen=True)
class ActionInputs:
    mode: Literal["scan", "pr"]
    api_key: str | None
    task_id: str | None
    api_url: str
    severity_threshold: str
    project_path: str
    github_token: str | None
    timeout_minutes: int


def read_inputs(env: Mapping[str, str]) -> ActionInputs:
    def value(name: str, default: str | None = None) -> str | None:
        # The composite step passes an input that was not set as an empty string.
        raw = env.get(f"INPUT_{name}", "").strip()
        return raw or default

    mode = value("MODE", "scan")
    if mode not in MODES:
        raise InputError(f"mode must be one of {', '.join(MODES)}, not {mode!r}.")

    threshold = value("SEVERITY_THRESHOLD", "Medium")
    if threshold not in SEVERITY_LEVELS:
        raise InputError(
            f"severity_threshold must be one of {', '.join(SEVERITY_LEVELS)}, not {threshold!r}."
        )

    raw_timeout = value("TIMEOUT_MINUTES", "120")
    try:
        timeout_minutes = int(raw_timeout)
    except ValueError as error:
        raise InputError(f"timeout_minutes must be a whole number, not {raw_timeout!r}.") from error
    if timeout_minutes <= 0:
        raise InputError(f"timeout_minutes must be greater than 0, not {timeout_minutes}.")

    api_key = value("API_KEY")
    task_id = value("TASK_ID")
    if mode == "scan":
        if api_key is None:
            raise InputError("api_key is required in scan mode.")
        if task_id is None:
            raise InputError("task_id is required in scan mode.")

    return ActionInputs(
        mode=mode,
        api_key=api_key,
        task_id=task_id,
        api_url=value("API_URL", "https://api.apyguard.com"),
        severity_threshold=threshold,
        project_path=value("PROJECT_PATH", "."),
        github_token=value("GITHUB_TOKEN"),
        timeout_minutes=timeout_minutes,
    )
