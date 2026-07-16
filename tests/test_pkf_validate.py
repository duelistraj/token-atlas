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
from pkf_lib import parse_yaml_block, read_front_matter


GOOD_AI = ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures" / "schema-change" / "repo" / ".ai"
GOOD_REPO = GOOD_AI.parent
PUBLIC_INITIALIZE = ROOT / "skills" / "token-atlas" / "references" / "initialize.md"
INTERNAL_INITIALIZE = ROOT / ".agents" / "skills" / "token-atlas" / "references" / "initialize.md"
INTERNAL_SKILL = ROOT / ".agents" / "skills" / "token-atlas" / "SKILL.md"
FIXTURES = ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures"


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

    def test_nested_module_index_exits_one_in_ci(self):
        with self.copy_ai() as ai:
            nested = ai / "knowledge" / "module-a" / "capability-a"
            nested.mkdir(parents=True)
            (nested / "INDEX.md").write_text("# Nested module\n", encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("nested module index" in finding.issue for finding in report.errors))

    def test_nested_module_index_is_reported_but_advisory_exits_zero(self):
        with self.copy_ai() as ai:
            nested = ai / "knowledge" / "module-a" / "capability-a"
            nested.mkdir(parents=True)
            (nested / "INDEX.md").write_text("# Nested module\n", encoding="utf-8")
            report = validate_pkf(ai, strictness="advisory")

        self.assertEqual(report.exit_code, 0)
        self.assertTrue(any("nested module index" in finding.issue for finding in report.errors))

    def test_missing_pkf_is_ci_blocking(self):
        with self.copy_ai() as ai:
            (ai / "PKF.md").unlink()
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("PKF.md" in finding.file for finding in report.errors))

    def test_missing_retrieval_protocol_is_ci_blocking(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(pkf.read_text(encoding="utf-8").replace("## Retrieval Protocol (MANDATORY)\n", ""), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("Retrieval Protocol" in finding.issue for finding in report.errors))

    def test_missing_closeout_protocol_is_ci_blocking(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(pkf.read_text(encoding="utf-8").replace("## Closeout Protocol (MANDATORY)\n", ""), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("Closeout Protocol" in finding.issue for finding in report.errors))

    def test_missing_closeout_mode_is_ci_blocking(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(pkf.read_text(encoding="utf-8").replace("  closeout: adaptive\n", ""), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("pkf.closeout must be one of" in finding.issue for finding in report.errors))

    def test_invalid_closeout_mode_is_ci_blocking(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(pkf.read_text(encoding="utf-8").replace("closeout: adaptive", "closeout: always"), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("pkf.closeout must be one of" in finding.issue for finding in report.errors))

    def test_closeout_off_is_valid_opt_out(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(pkf.read_text(encoding="utf-8").replace("closeout: adaptive", 'closeout: "off"'), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 0)
        self.assertTrue(any("PKF closeout mode is valid: off" in item for item in report.passed))

    def test_bootstrap_must_reference_pkf(self):
        with self.copy_ai() as ai:
            bootstrap = ai.parent / "AGENTS.md"
            bootstrap.write_text("# AGENTS\n", encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any(finding.file == "AGENTS.md" and ".ai/PKF.md" in finding.issue for finding in report.errors))

    def test_missing_bootstrap_is_ci_blocking(self):
        with self.copy_ai() as ai:
            (ai.parent / "AGENTS.md").unlink()
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any(finding.file == "AGENTS.md" and "missing root bootstrap" in finding.issue for finding in report.errors))

    def test_bootstrap_must_reference_closeout_protocol(self):
        with self.copy_ai() as ai:
            bootstrap = ai.parent / "AGENTS.md"
            bootstrap.write_text(bootstrap.read_text(encoding="utf-8").replace("Closeout Protocol", "End protocol"), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any(finding.file == "AGENTS.md" and "Closeout Protocol" in finding.issue for finding in report.errors))

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

    def test_nested_source_symbols_mapping_is_parsed(self):
        metadata = read_front_matter(GOOD_AI / "knowledge" / "backend" / "schema.md")

        self.assertEqual(metadata["source_symbols"], {"src/backend/models/customer.ts": ["CustomerRecord"]})

    def test_fallback_yaml_parser_handles_source_symbols_mapping(self):
        lines = [
            "source_symbols:",
            "  src/backend/models/customer.ts:",
            "    - CustomerRecord",
            "pkf:",
            "  loads: []",
            "  related: []",
        ]

        metadata, index = parse_yaml_block(lines, 0, 0, Path("leaf.md"))

        self.assertEqual(index, len(lines))
        self.assertEqual(metadata["source_symbols"], {"src/backend/models/customer.ts": ["CustomerRecord"]})

    def test_missing_source_symbols_is_ci_blocking(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "schema.md"
            text = leaf.read_text(encoding="utf-8")
            leaf.write_text(text.replace("source_symbols:\n  src/backend/models/customer.ts:\n    - CustomerRecord\n", ""), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("missing leaf front matter field: source_symbols" in finding.issue for finding in report.errors))

    def test_missing_source_symbol_path_is_ci_blocking(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "schema.md"
            text = leaf.read_text(encoding="utf-8").replace(
                "src/backend/models/customer.ts", "src/backend/models/missing.ts"
            )
            leaf.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("source_symbols path does not resolve" in finding.issue for finding in report.errors))

    def test_missing_source_symbol_literal_is_ci_blocking(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "schema.md"
            text = leaf.read_text(encoding="utf-8").replace("CustomerRecord", "MissingRecord")
            leaf.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("source symbol does not resolve" in finding.issue for finding in report.errors))

    def test_missing_edit_map_is_ci_blocking(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "schema.md"
            text = leaf.read_text(encoding="utf-8").replace("## Edit Map", "## Source Notes")
            leaf.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("missing required heading: ## Edit Map" in finding.issue for finding in report.errors))

    def test_edit_map_requires_targeted_locator(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "schema.md"
            text = leaf.read_text(encoding="utf-8").replace("rg -n -F --", "search")
            leaf.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("no targeted rg or ast-grep locator" in finding.issue for finding in report.errors))

    def test_empty_leaf_requires_standard_marker(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "ui.md"
            text = leaf.read_text(encoding="utf-8").replace("- TODO: No source-backed facts.", "- No UI.")
            leaf.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("empty source_symbols requires marker" in finding.issue for finding in report.errors))

    def test_leaf_token_gate_warns_locally_and_fails_ci(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "schema.md"
            leaf.write_text(leaf.read_text(encoding="utf-8") + ("context " * 3000), encoding="utf-8")
            advisory = validate_pkf(ai, strictness="advisory")
            ci = validate_pkf(ai, strictness="ci")

        self.assertTrue(any(finding.file == "leaf:backend/schema.md" for finding in advisory.warnings))
        self.assertTrue(any(finding.file == "leaf:backend/schema.md" for finding in ci.errors))
        self.assertEqual(next(entry.status for entry in ci.token_impact if entry.route == "leaf:backend/schema.md"), "error")

    def test_more_than_two_automatic_leaves_is_ci_blocking(self):
        with self.copy_ai() as ai:
            index = ai / "knowledge" / "backend" / "INDEX.md"
            text = index.read_text(encoding="utf-8").replace(
                "  loads: []",
                "  loads:\n    - .ai/knowledge/backend/api.md\n    - .ai/knowledge/backend/schema.md\n    - .ai/knowledge/backend/ui.md",
            )
            index.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("normal retrieval budget exceeded" in finding.issue for finding in report.errors))

    def test_internal_initialize_uses_public_protocol_templates(self):
        public = PUBLIC_INITIALIZE.read_text(encoding="utf-8")
        internal = INTERNAL_INITIALIZE.read_text(encoding="utf-8")

        self.assertEqual(
            self.template_block(public, "## Retrieval Protocol Template"),
            self.template_block(internal, "## Retrieval Protocol Template"),
        )
        self.assertEqual(
            self.template_block(public, "## Bootstrap Template"),
            self.template_block(internal, "## Bootstrap Template"),
        )
        self.assertEqual(
            self.template_block(public, "## Closeout Protocol Template"),
            self.template_block(internal, "## Closeout Protocol Template"),
        )
        skill = INTERNAL_SKILL.read_text(encoding="utf-8")
        self.assertIn("embed the Retrieval and Closeout Protocols", skill)
        self.assertIn("neutral bootstrap", skill)

    def test_seeded_fixture_runtimes_include_bootstrap_contract(self):
        for pkf in sorted(FIXTURES.rglob("PKF.md")):
            if ".ai" not in pkf.parts:
                continue
            self.assertIn("## Retrieval Protocol (MANDATORY)", pkf.read_text(encoding="utf-8"), pkf)
            self.assertIn("## Closeout Protocol (MANDATORY)", pkf.read_text(encoding="utf-8"), pkf)
            self.assertEqual(read_front_matter(pkf)["pkf"]["closeout"], "adaptive", pkf)
            bootstrap = pkf.parent.parent / "AGENTS.md"
            self.assertTrue(bootstrap.is_file(), f"missing bootstrap for {pkf}")
            self.assertIn(".ai/PKF.md", bootstrap.read_text(encoding="utf-8"), bootstrap)
            self.assertIn("Closeout Protocol", bootstrap.read_text(encoding="utf-8"), bootstrap)

    def copy_ai(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        shutil.copytree(GOOD_REPO, root, dirs_exist_ok=True)
        target = root / ".ai"

        class Context:
            def __enter__(self):
                return target

            def __exit__(self, exc_type, exc, tb):
                temp.cleanup()

        return Context()

    @staticmethod
    def template_block(text: str, heading: str) -> str:
        start = text.index(heading)
        fence_start = text.index("````markdown\n", start)
        fence_end = text.index("\n````", fence_start) + len("\n````")
        return text[fence_start:fence_end]


if __name__ == "__main__":
    unittest.main()
