from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from apyguard_action.engine import EngineError, compare_documents, export_openapi
from tests.fakes import FakeRun, completed


class EngineTest(unittest.TestCase):
    def test_export_reads_the_written_document(self) -> None:
        def write_document(command: list[str]):
            Path(command[command.index("--output") + 1]).write_text(json.dumps({"paths": {"/a": {}}}))
            return completed(command)

        run = FakeRun(write_document)
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir, "head.json")

            document = export_openapi(Path("/repo/api"), output, run=run)

        self.assertEqual(document, {"paths": {"/a": {}}})
        self.assertEqual(
            run.commands,
            [["apyguard-engine", "export", "/repo/api", "--output", str(output), "--format", "json"]],
        )

    def test_engine_failure_reports_stderr_tail(self) -> None:
        stderr = "\n".join(f"line {number}" for number in range(30))
        run = FakeRun(lambda command: completed(command, 1, stderr=stderr))

        with self.assertRaises(EngineError) as raised:
            export_openapi(Path("/repo"), Path("/tmp/out.json"), run=run)

        message = str(raised.exception)
        self.assertIn("export", message)
        self.assertIn("line 29", message)
        self.assertNotIn("line 5\n", message)

    def test_engine_runs_with_ai_inference_off(self) -> None:
        # Job-level APYGUARD_AI_* variables would otherwise send the project's code to an AI provider.
        run = FakeRun(lambda command: completed(command, stdout="{}"))

        with mock.patch.dict(os.environ, {"APYGUARD_AI_ENABLED": "true", "PATH": "/usr/bin"}):
            compare_documents(Path("base.json"), Path("head.json"), run=run)

        environment = run.options[0]["env"]
        self.assertEqual(environment["APYGUARD_AI_ENABLED"], "false")
        self.assertEqual(environment["PATH"], "/usr/bin")

    def test_compare_parses_stdout(self) -> None:
        run = FakeRun(lambda command: completed(command, stdout='{"changes": [], "added_endpoint_count": 0}'))

        result = compare_documents(Path("base.json"), Path("head.json"), run=run)

        self.assertEqual(result, {"changes": [], "added_endpoint_count": 0})
        self.assertEqual(run.commands, [["apyguard-engine", "compare", "base.json", "head.json"]])


if __name__ == "__main__":
    unittest.main()
