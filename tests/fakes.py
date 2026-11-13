"""Stand-ins for the process boundary: a subprocess.run that records commands and answers by rule."""
from __future__ import annotations

import subprocess
from typing import Callable, Sequence

Answer = Callable[[list[str]], "subprocess.CompletedProcess[str] | None"]


def completed(args: Sequence[str], returncode: int = 0, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(list(args), returncode, stdout, stderr)


class FakeRun:
    """Each answer gets the command and returns a result, or None to let the next answer try."""

    def __init__(self, *answers: Answer) -> None:
        self.answers = answers
        self.commands: list[list[str]] = []
        self.options: list[dict[str, object]] = []

    def __call__(self, args: Sequence[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        command = list(args)
        self.commands.append(command)
        self.options.append(kwargs)
        for answer in self.answers:
            result = answer(command)
            if result is not None:
                return result
        return completed(command)

    def ran(self, *words: str) -> bool:
        return any(all(word in command for word in words) for command in self.commands)
