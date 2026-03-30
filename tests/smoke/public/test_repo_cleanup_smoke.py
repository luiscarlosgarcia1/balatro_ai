from __future__ import annotations

from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[3]


class Phase5RepoCleanupSmokeTests(unittest.TestCase):
    def test_tracked_legacy_workflow_files_are_removed(self) -> None:
        self.assertFalse((REPO_ROOT / "obs_test.py").exists())
        self.assertFalse((REPO_ROOT / "clean_obs.ps1").exists())

    def test_repo_docs_no_longer_teach_legacy_observer_workflows(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        mod_readme = (REPO_ROOT / "mods" / "live_state_exporter" / "README.md").read_text(
            encoding="utf-8"
        )
        workflow = (REPO_ROOT / "WORKFLOW.md").read_text(encoding="utf-8")

        self.assertNotIn("obs_test.py", readme)
        self.assertNotIn("clean_obs.ps1", readme)
        self.assertNotIn("save-first", readme)
        self.assertNotIn("save-file", readme)
        self.assertNotIn("screenshot", readme.lower())

        self.assertNotIn("obs_test.py", mod_readme)
        self.assertNotIn("screenshot", mod_readme.lower())

        self.assertNotIn("save.jkr", workflow)
        self.assertNotIn("screenshot", workflow.lower())


if __name__ == "__main__":
    unittest.main()
