from __future__ import annotations

import unittest

from apyguard_action.inputs import InputError, read_inputs

SCAN = {"INPUT_MODE": "scan", "INPUT_API_KEY": "key", "INPUT_TASK_ID": "task-1"}


class ReadInputsTest(unittest.TestCase):
    def test_defaults(self) -> None:
        # The composite action passes an unset input as an empty string.
        inputs = read_inputs({**SCAN, "INPUT_API_URL": "", "INPUT_TIMEOUT_MINUTES": ""})

        self.assertEqual(inputs.mode, "scan")
        self.assertEqual(inputs.api_url, "https://api.apyguard.com")
        self.assertEqual(inputs.severity_threshold, "Medium")
        self.assertEqual(inputs.project_path, ".")
        self.assertEqual(inputs.timeout_minutes, 120)

    def test_scan_mode_requires_api_key_and_task_id(self) -> None:
        with self.assertRaises(InputError) as raised:
            read_inputs({"INPUT_MODE": "scan", "INPUT_TASK_ID": "task-1"})
        self.assertIn("api_key", str(raised.exception))

        with self.assertRaises(InputError) as raised:
            read_inputs({"INPUT_MODE": "scan", "INPUT_API_KEY": "key"})
        self.assertIn("task_id", str(raised.exception))

    def test_pr_mode_needs_no_api_key(self) -> None:
        self.assertEqual(read_inputs({"INPUT_MODE": "pr"}).mode, "pr")

    def test_rejects_unknown_mode(self) -> None:
        with self.assertRaises(InputError) as raised:
            read_inputs({**SCAN, "INPUT_MODE": "deploy"})
        self.assertIn("deploy", str(raised.exception))

    def test_rejects_unknown_severity_threshold(self) -> None:
        with self.assertRaises(InputError) as raised:
            read_inputs({**SCAN, "INPUT_SEVERITY_THRESHOLD": "Severe"})
        self.assertIn("Severe", str(raised.exception))

    def test_rejects_non_positive_timeout(self) -> None:
        for value in ("0", "-5", "soon"):
            with self.subTest(value=value), self.assertRaises(InputError):
                read_inputs({**SCAN, "INPUT_TIMEOUT_MINUTES": value})


if __name__ == "__main__":
    unittest.main()
