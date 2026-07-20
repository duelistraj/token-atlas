import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "token-atlas-lite" / "scripts" / "lite_validate.py"
SPEC = importlib.util.spec_from_file_location("lite_validate", SCRIPT)
lite_validate = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = lite_validate
previous_bytecode_setting = sys.dont_write_bytecode
sys.dont_write_bytecode = True
try:
    SPEC.loader.exec_module(lite_validate)
finally:
    sys.dont_write_bytecode = previous_bytecode_setting


class TokenAtlasLiteValidationTests(unittest.TestCase):
    def write_valid_runtime(self, root: Path) -> None:
        source = root / "backend" / "app" / "auth.py"
        source.parent.mkdir(parents=True)
        source.write_text(
            "class AuthService:\n    def login(self):\n        return True\n",
            encoding="utf-8",
        )
        dependency = root / "pyproject.toml"
        dependency.write_text('[project]\ndependencies = ["example"]\n', encoding="utf-8")
        ai = root / ".ai"
        ai.mkdir()
        (ai / "token-atlas-lite.json").write_text(
            json.dumps(lite_validate.EXPECTED_MANIFEST, indent=2) + "\n",
            encoding="utf-8",
        )
        (ai / "INDEX.md").write_text(
            """# Token Atlas Lite Index

## Repository Summary

Example service.

## Navigation

Use the authoritative document for the task.

## Inline Update Rules

Update verified durable knowledge while implementing.
""",
            encoding="utf-8",
        )
        (ai / "ARCHITECTURE.md").write_text(
            """# Architecture

### Authentication service

The authentication service owns login behavior.

Evidence:
- `backend/app/auth.py::AuthService.login`
""",
            encoding="utf-8",
        )
        (ai / "DECISIONS.md").write_text(
            """# Decisions

### Keep authentication local

Recorded: 2026-07-20
Status: accepted
Basis: user-confirmed
Confirmed: 2026-07-20
Decision: Keep authentication in the application service.
Rationale: The user confirmed this boundary.
Consequences: Login remains application-owned.
""",
            encoding="utf-8",
        )
        (ai / "GLOSSARY.md").write_text(
            """# Glossary

### Login

The operation that authenticates an application user.

Evidence:
- `backend/app/auth.py::AuthService.login`
""",
            encoding="utf-8",
        )
        (ai / "DEPENDENCIES.md").write_text(
            """# Dependencies

### Example package

The package supplies the example runtime dependency.

Evidence:
- `pyproject.toml::project.dependencies`
""",
            encoding="utf-8",
        )
        (ai / "MEMORY.md").write_text(
            """# Memory

### Authentication locator

Start authentication work at the application service.

Evidence:
- `backend/app/auth.py::AuthService`
""",
            encoding="utf-8",
        )
        (root / "AGENTS.md").write_text(
            "# Repository instructions\n\n" + lite_validate.BOOTSTRAP + "\n",
            encoding="utf-8",
        )

    def validate_fixture(self, mutate=None):
        with tempfile.TemporaryDirectory() as raw_temp:
            root = Path(raw_temp)
            self.write_valid_runtime(root)
            if mutate is not None:
                mutate(root)
            return lite_validate.validate(root)

    def test_valid_lite_runtime_passes(self):
        report = self.validate_fixture()

        self.assertEqual(report["schema_version"], 1)
        self.assertEqual(report["edition"], "lite")
        self.assertEqual(report["status"], "passed")
        self.assertLessEqual(report["memory"]["estimated_tokens"], 1_000)

    def test_manifest_is_exact_and_all_documents_are_required(self):
        def mutate(root: Path) -> None:
            manifest = root / ".ai" / "token-atlas-lite.json"
            value = json.loads(manifest.read_text(encoding="utf-8"))
            value["extra"] = True
            manifest.write_text(json.dumps(value), encoding="utf-8")
            (root / ".ai" / "GLOSSARY.md").unlink()

        report = self.validate_fixture(mutate)

        self.assertEqual(report["status"], "failed")
        issues = "\n".join(item["issue"] for item in report["errors"])
        self.assertIn("manifest must contain exactly", issues)
        self.assertIn("required file is missing", issues)

    def test_placeholder_and_broken_evidence_are_rejected(self):
        def mutate(root: Path) -> None:
            architecture = root / ".ai" / "ARCHITECTURE.md"
            architecture.write_text(
                architecture.read_text(encoding="utf-8")
                + "\n### Future\n\nTODO: determine this.\n\nEvidence:\n- `missing.py::future`\n",
                encoding="utf-8",
            )

        report = self.validate_fixture(mutate)
        issues = "\n".join(item["issue"] for item in report["errors"])

        self.assertIn("incomplete content is forbidden", issues)
        self.assertIn("evidence path does not resolve", issues)

    def test_memory_has_a_hard_one_thousand_token_limit(self):
        def mutate(root: Path) -> None:
            (root / ".ai" / "MEMORY.md").write_text(
                "# Memory\n\n### Oversized\n\n"
                + ("durable operational fact " * 220)
                + "\n\nEvidence:\n- `backend/app/auth.py::AuthService`\n",
                encoding="utf-8",
            )

        report = self.validate_fixture(mutate)

        self.assertGreater(report["memory"]["estimated_tokens"], 1_000)
        self.assertTrue(
            any("memory budget exceeded" in item["issue"] for item in report["errors"])
        )

    def test_decision_basis_controls_evidence_requirements(self):
        def mutate(root: Path) -> None:
            (root / ".ai" / "DECISIONS.md").write_text(
                """# Decisions

### Source-backed choice

Recorded: 2026-07-20
Status: accepted
Basis: source-backed
Decision: Keep authentication local.
Rationale: The implementation owns login.
Consequences: Login remains local.
""",
                encoding="utf-8",
            )

        report = self.validate_fixture(mutate)

        self.assertTrue(
            any("source-backed decision" in item["issue"] for item in report["errors"])
        )

    def test_identical_fact_and_evidence_across_documents_are_rejected(self):
        def mutate(root: Path) -> None:
            architecture = root / ".ai" / "ARCHITECTURE.md"
            architecture.write_text(
                """# Architecture

### Authentication locator

Start authentication work at the application service.

Evidence:
- `backend/app/auth.py::AuthService`
""",
                encoding="utf-8",
            )

        report = self.validate_fixture(mutate)

        duplicates = [
            item for item in report["errors"] if "duplicate durable facts" in item["issue"]
        ]
        self.assertEqual(len(duplicates), 1)
        self.assertIn(".ai/ARCHITECTURE.md, .ai/MEMORY.md", duplicates[0]["file"])

    def test_evidence_bearing_index_fact_participates_in_duplicate_detection(self):
        def mutate(root: Path) -> None:
            index = root / ".ai" / "INDEX.md"
            index.write_text(
                index.read_text(encoding="utf-8")
                + """
### Authentication service

The authentication service owns login behavior.

Evidence:
- `backend/app/auth.py::AuthService.login`
""",
                encoding="utf-8",
            )

        report = self.validate_fixture(mutate)

        self.assertTrue(
            any("duplicate durable facts" in item["issue"] for item in report["errors"])
        )

    def test_high_similarity_fact_with_shared_evidence_is_rejected(self):
        def mutate(root: Path) -> None:
            (root / ".ai" / "ARCHITECTURE.md").write_text(
                """# Architecture

### Authentication ownership

The authentication service owns all current application user login behavior.

Evidence:
- `backend/app/auth.py::AuthService.login`
""",
                encoding="utf-8",
            )
            (root / ".ai" / "MEMORY.md").write_text(
                """# Memory

### Authentication ownership

The authentication service owns all current application user login behavior today.

Evidence:
- `backend/app/auth.py::AuthService.login`
""",
                encoding="utf-8",
            )

        report = self.validate_fixture(mutate)

        self.assertTrue(
            any("duplicate durable facts" in item["issue"] for item in report["errors"])
        )

    def test_different_evidence_or_meaningfully_different_text_is_allowed(self):
        def mutate(root: Path) -> None:
            (root / ".ai" / "MEMORY.md").write_text(
                """# Memory

### Authentication test command

Run the focused authentication test before changing login behavior.

Evidence:
- `pyproject.toml::project.dependencies`
""",
                encoding="utf-8",
            )

        report = self.validate_fixture(mutate)

        self.assertFalse(
            any("duplicate durable facts" in item["issue"] for item in report["errors"])
        )

    def test_bootstrap_forbids_separate_closeout_and_automatic_validation(self):
        self.assertIn("do not perform a post-task repository scan", lite_validate.BOOTSTRAP)
        self.assertIn("start a\nseparate closeout phase", lite_validate.BOOTSTRAP)
        self.assertIn("run Lite validation\nautomatically", lite_validate.BOOTSTRAP)


if __name__ == "__main__":
    unittest.main()
