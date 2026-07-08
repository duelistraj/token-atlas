import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pkf_validate import validate_pkf


GOOD_AI = ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures" / "schema-change" / "repo" / ".ai"


class PkfValidateTests(unittest.TestCase):
    def test_good_tree_exits_zero(self):
        with self.copy_ai() as ai:
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 0)
        self.assertFalse(report.errors)

    def test_broken_load_exits_one_in_ci(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(
                pkf.read_text(encoding="utf-8").replace("  related: []", "  related:\n    - .ai/knowledge/missing.md"),
                encoding="utf-8",
            )
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("broken pkf.related" in finding.issue for finding in report.errors))

    def test_missing_module_doc_exits_one_in_ci(self):
        with self.copy_ai() as ai:
            (ai / "knowledge" / "backend" / "api.md").unlink()
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("missing required file" in finding.issue for finding in report.errors))

    def test_missing_pkf_is_ci_blocking(self):
        with self.copy_ai() as ai:
            (ai / "PKF.md").unlink()
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("PKF.md" in finding.file for finding in report.errors))

    def test_malformed_front_matter_exits_one_in_ci(self):
        with self.copy_ai() as ai:
            path = ai / "MEMORY.md"
            path.write_text("---\n:\n---\n\n# Broken\n", encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(report.errors)

    def test_advisory_reports_errors_but_exits_zero(self):
        with self.copy_ai() as ai:
            (ai / "knowledge" / "backend" / "api.md").unlink()
            report = validate_pkf(ai, strictness="advisory")

        self.assertEqual(report.exit_code, 0)
        self.assertTrue(report.errors)

    def copy_ai(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        target = root / ".ai"
        shutil.copytree(GOOD_AI, target)

        class Context:
            def __enter__(self):
                return target

            def __exit__(self, exc_type, exc, tb):
                temp.cleanup()

        return Context()


if __name__ == "__main__":
    unittest.main()
