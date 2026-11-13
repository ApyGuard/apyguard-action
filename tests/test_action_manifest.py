from __future__ import annotations

import re
import unittest
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INPUTS = {
    "mode",
    "api_key",
    "task_id",
    "api_url",
    "severity_threshold",
    "project_path",
    "github_token",
    "timeout_minutes",
}


class ActionManifestTest(unittest.TestCase):
    def setUp(self) -> None:
        self.text = (ROOT / "action.yml").read_text(encoding="utf-8")

    def test_every_input_reaches_the_python_step(self) -> None:
        inputs_block = self.text.split("\ninputs:\n", 1)[1].split("\noutputs:\n", 1)[0]
        names = set(re.findall(r"^  ([a-z_]+):$", inputs_block, re.MULTILINE))

        self.assertEqual(names, INPUTS)
        for name in names:
            self.assertIn(f"INPUT_{name.upper()}: ${{{{ inputs.{name} }}}}", self.text)

    def test_python_steps_ignore_the_workspace_folder(self) -> None:
        # The steps run in the customer's workspace; without -P its packages (email/, json/,
        # apyguard_action/) would shadow the standard library and the action's own code.
        self.assertIn("python -P -m pip install", self.text)
        self.assertIn("python -P -m apyguard_action", self.text)
        self.assertNotRegex(self.text, r"python -m ")

    def test_the_python_step_writes_its_log_as_it_goes(self) -> None:
        # A runner's stdout is a pipe, so Python buffers it: "ApyGuard scan ... started." of a scan
        # that ran for two hours showed up only when the job ended.
        run_step = self.text.split("- id: run", 1)[1]
        self.assertIn("PYTHONUNBUFFERED: '1'", run_step)

    def test_vendored_engine_wheel_is_the_one_the_action_installs(self) -> None:
        wheels = [path.name for path in (ROOT / "vendor").glob("apyguard_engine-*.whl")]

        self.assertEqual(len(wheels), 1)
        self.assertIn(f"$GITHUB_ACTION_PATH/vendor/{wheels[0]}", self.text)

    def test_engine_installs_without_reaching_an_index(self) -> None:
        install = next(line for line in self.text.splitlines() if "-m pip install" in line)

        self.assertIn("--no-index", install)
        self.assertIn('--find-links "$GITHUB_ACTION_PATH/vendor"', install)

    def test_every_engine_dependency_has_a_vendored_wheel(self) -> None:
        # With --no-index, pip can only resolve what vendor/ holds; a new engine
        # dependency without its wheel would fail on every customer's runner.
        engine = next((ROOT / "vendor").glob("apyguard_engine-*.whl"))
        with zipfile.ZipFile(engine) as wheel:
            metadata_name = next(n for n in wheel.namelist() if n.endswith(".dist-info/METADATA"))
            metadata = wheel.read(metadata_name).decode("utf-8")
        required = {
            _normalize(re.match(r"[A-Za-z0-9._-]+", value).group(0))
            for value in re.findall(r"^Requires-Dist: (.+)$", metadata, re.MULTILINE)
            if "extra ==" not in value
        }
        vendored = {_normalize(path.name.split("-", 1)[0]) for path in (ROOT / "vendor").glob("*.whl")}

        self.assertTrue(required)
        self.assertLessEqual(required, vendored)


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "_", name).lower()


if __name__ == "__main__":
    unittest.main()
