"""The runner's side channels: workflow commands on stdout, and the output and summary files."""
from __future__ import annotations

from pathlib import Path
from typing import Mapping


def _escape(message: str) -> str:
    # A workflow command ends at the line break, so the message's own breaks are encoded.
    return message.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def error(message: str) -> None:
    print(f"::error::{_escape(message)}")


def warning(message: str) -> None:
    print(f"::warning::{_escape(message)}")


def set_output(env: Mapping[str, str], name: str, value: str) -> None:
    path = env.get("GITHUB_OUTPUT")
    if path:
        with Path(path).open("a", encoding="utf-8") as output:
            output.write(f"{name}={value}\n")


def append_step_summary(env: Mapping[str, str], markdown: str) -> None:
    path = env.get("GITHUB_STEP_SUMMARY")
    if path:
        with Path(path).open("a", encoding="utf-8") as summary:
            summary.write(markdown)
