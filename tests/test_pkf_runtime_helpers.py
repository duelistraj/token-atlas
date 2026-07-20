import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "skills" / "token-atlas"
SCAFFOLD = PUBLIC / "scripts" / "pkf_scaffold.py"
ROUTE = PUBLIC / "scripts" / "pkf_route.py"


class PkfRuntimeHelperTests(unittest.TestCase):
    def run_helper(self, script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            (sys.executable, "-S", str(script), *args),
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )

    def prepare_repo(self, root: Path) -> None:
        source = root / "src/notes/service.py"
        source.parent.mkdir(parents=True)
        source.write_text("def list_notes():\n    return []\n", encoding="utf-8")
        tests = root / "tests"
        tests.mkdir()
        (tests / "test_notes.py").write_text("def test_notes():\n    pass\n", encoding="utf-8")
        (root / "pyproject.toml").write_text("[project]\nname = 'fixture'\n", encoding="utf-8")
        (root / "AGENTS.md").write_text("# AGENTS\n\nKeep this instruction.\n", encoding="utf-8")

    def initialize_runtime(self, root: Path) -> None:
        inspected = self.run_helper(SCAFFOLD, "inspect", "--path", ".", cwd=root)
        self.assertEqual(inspected.returncode, 0, inspected.stderr)
        spec_path = root / ".ai/.pkf-init.json"
        spec = json.loads(spec_path.read_text(encoding="utf-8"))
        spec["capabilities"] = [
            {"id": "notes", "title": "Notes", "source_roots": ["src/notes"]}
        ]
        spec_path.write_text(json.dumps(spec), encoding="utf-8")
        created = self.run_helper(SCAFFOLD, "create", "--path", ".", "--strictness", "ci", cwd=root)
        self.assertEqual(created.returncode, 0, created.stdout + created.stderr)

    def test_scaffold_inspects_bounded_structure_and_creates_valid_fresh_runtime(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            root = Path(raw_temp)
            self.prepare_repo(root)
            self.initialize_runtime(root)

            self.assertFalse((root / ".ai/.pkf-init.json").exists())
            self.assertTrue((root / ".ai/PKF.md").is_file())
            self.assertTrue((root / ".ai/tools/pkf_route.py").is_file())
            self.assertTrue((root / ".ai/tools/pkf_validate.py").is_file())
            self.assertTrue((root / ".ai/knowledge/notes/ui.md").is_file())
            self.assertIn("Pending source extraction", (root / ".ai/knowledge/notes/api.md").read_text(encoding="utf-8"))
            root_index = (root / ".ai/knowledge/INDEX.md").read_text(encoding="utf-8")
            module_index = (root / ".ai/knowledge/notes/INDEX.md").read_text(encoding="utf-8")
            architecture = (root / ".ai/ARCHITECTURE.md").read_text(encoding="utf-8")
            self.assertIn("  routes: {}", root_index)
            self.assertIn("  related: []", root_index)
            self.assertIn("  related: []", module_index)
            self.assertIn("  related: []", architecture)
            bootstrap = (root / "AGENTS.md").read_text(encoding="utf-8")
            self.assertIn("Keep this instruction.", bootstrap)
            self.assertEqual(bootstrap.count("token-atlas:bootstrap:start"), 1)
            self.assertIn("python -S .ai/tools/pkf_route.py", bootstrap)
            self.assertIn("python -S .ai/tools/pkf_validate.py", bootstrap)

            validator = PUBLIC / "scripts/pkf_validate.py"
            validated = self.run_helper(
                validator,
                "--path", ".", "--strictness", "ci", "--format", "json",
                cwd=root,
            )
            self.assertEqual(validated.returncode, 0, validated.stdout + validated.stderr)

    def test_scaffold_refuses_overwrite_and_paths_outside_repository(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            root = Path(raw_temp)
            self.prepare_repo(root)
            self.initialize_runtime(root)

            repeated = self.run_helper(SCAFFOLD, "inspect", "--path", ".", cwd=root)
            escaped = self.run_helper(
                SCAFFOLD, "inspect", "--path", ".", "--spec", "../outside.json", cwd=root
            )

            self.assertEqual(repeated.returncode, 2)
            self.assertIn("already exists", repeated.stderr)
            self.assertEqual(escaped.returncode, 2)
            self.assertIn("escapes repository", escaped.stderr)

    def test_scaffold_refuses_partial_existing_ai_content(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            root = Path(raw_temp)
            self.prepare_repo(root)
            partial = root / ".ai/MEMORY.md"
            partial.parent.mkdir()
            partial.write_text("manual knowledge\n", encoding="utf-8")

            inspected = self.run_helper(SCAFFOLD, "inspect", "--path", ".", cwd=root)

            self.assertEqual(inspected.returncode, 2)
            self.assertIn("already contains runtime content", inspected.stderr)

    def test_route_maps_source_and_leaf_paths_and_reports_unmapped_paths(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            root = Path(raw_temp)
            self.prepare_repo(root)
            self.initialize_runtime(root)
            leaf = root / ".ai/knowledge/notes/business_rules.md"
            leaf.write_text(
                """---
type: knowledge
title: Notes Business Rules
description: Note listing behavior.
resource: TODO
tags: [pkf]
timestamp: TODO
source_symbols:
  src/notes/service.py:
    - list_notes
pkf:
  materialization: complete
  loads: []
  related: []
---
# Business Rules

- Notes are returned by `list_notes`.

## Edit Map

| Behavior | Source symbols | Tests | Styles/tokens | Locator |
| --- | --- | --- | --- | --- |
| List notes | `list_notes` | `tests/test_notes.py` | none | `rg -n -F -- 'list_notes' 'src/notes/service.py'` |
""",
                encoding="utf-8",
            )

            routed = self.run_helper(
                ROUTE,
                "--path", ".",
                "--changed-path", "src/notes/service.py",
                "--changed-path", "src/unknown.py",
                "--format", "json",
                cwd=root,
            )
            self.assertEqual(routed.returncode, 0, routed.stderr)
            value = json.loads(routed.stdout)
            self.assertEqual(value["schema_version"], 2)
            self.assertEqual(value["status"], "partial")
            self.assertEqual(value["affected_leaves"][0]["path"], ".ai/knowledge/notes/business_rules.md")
            self.assertEqual(value["unmatched_paths"], ["src/unknown.py"])
            self.assertEqual(value["index_fallback"], [".ai/knowledge/INDEX.md"])
            self.assertEqual(value["validation_scope"], "affected")

    def test_route_reports_module_owned_unmapped_path_without_root_fallback(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            root = Path(raw_temp)
            self.prepare_repo(root)
            self.initialize_runtime(root)

            routed = self.run_helper(
                root / ".ai/tools/pkf_route.py",
                "--path", ".",
                "--changed-path", "src/notes/newState.py",
                "--format", "json",
                cwd=root,
            )
            value = json.loads(routed.stdout)

            self.assertEqual(routed.returncode, 0, routed.stderr)
            self.assertEqual(value["status"], "unmapped")
            self.assertTrue(value["routing_coverage_defect"])
            self.assertEqual(value["index_fallback"], [".ai/knowledge/notes/INDEX.md"])
            self.assertEqual(value["fallback_routes"][0]["kind"], "module")
            self.assertEqual(value["fallback_routes"][0]["changed_paths"], ["src/notes/newState.py"])

    def test_route_requests_full_validation_for_index_change(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            root = Path(raw_temp)
            self.prepare_repo(root)
            self.initialize_runtime(root)

            routed = self.run_helper(
                ROUTE,
                "--path", ".",
                "--changed-path", ".ai/knowledge/notes/INDEX.md",
                "--format", "json",
                cwd=root,
            )
            value = json.loads(routed.stdout)
            self.assertEqual(routed.returncode, 0, routed.stderr)
            self.assertEqual(value["status"], "mapped")
            self.assertEqual(value["validation_scope"], "full")

            shared = self.run_helper(
                ROUTE,
                "--path", ".",
                "--changed-path", ".ai/knowledge/dependencies.md",
                "--format", "json",
                cwd=root,
            )
            shared_value = json.loads(shared.stdout)
            self.assertEqual(shared.returncode, 0, shared.stderr)
            self.assertEqual(shared_value["status"], "mapped")
            self.assertEqual(shared_value["validation_scope"], "full")


if __name__ == "__main__":
    unittest.main()
