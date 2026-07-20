import shutil
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pkf_contract import PENDING_LEAF_MARKER, RUNTIME_VERSION
from pkf_validate import UsageError, report_to_dict, validate_pkf
from pkf_lib import parse_yaml_block, read_front_matter


GOOD_AI = ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures" / "schema-change" / "repo" / ".ai"
GOOD_REPO = GOOD_AI.parent
PUBLIC_INITIALIZE = ROOT / "skills" / "token-atlas" / "references" / "initialize.md"
INTERNAL_INITIALIZE = ROOT / ".agents" / "skills" / "token-atlas" / "references" / "initialize.md"
INTERNAL_SKILL = ROOT / ".agents" / "skills" / "token-atlas" / "SKILL.md"
FIXTURES = ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures"
TWO_MODULE_REPO = FIXTURES / "broad-loads" / "repo"


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

    def test_document_relative_pkf_references_resolve(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(pkf.read_text(encoding="utf-8").replace(".ai/MEMORY.md", "MEMORY.md"), encoding="utf-8")
            index = ai / "knowledge" / "backend" / "INDEX.md"
            index.write_text(index.read_text(encoding="utf-8").replace(".ai/knowledge/backend/api.md", "api.md"), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertFalse(any("broken pkf" in finding.issue for finding in report.errors))

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

    def test_root_index_relative_module_route_is_reachable(self):
        with self.copy_ai() as ai:
            root_index = ai / "knowledge" / "INDEX.md"
            root_index.write_text(
                root_index.read_text(encoding="utf-8").replace(".ai/knowledge/backend/INDEX.md", "backend/INDEX.md"),
                encoding="utf-8",
            )
            report = validate_pkf(ai, strictness="ci")

        self.assertFalse(any("module not reachable" in finding.issue for finding in report.errors))

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

    def test_missing_retrieval_mode_is_ci_blocking(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(pkf.read_text(encoding="utf-8").replace("  retrieval: adaptive\n", ""), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("pkf.retrieval must be one of" in finding.issue for finding in report.errors))

    def test_missing_runtime_version_requires_migration(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(pkf.read_text(encoding="utf-8").replace("  runtime_version: 4\n", ""), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("missing pkf.runtime_version" in finding.issue for finding in report.errors))

    def test_future_runtime_version_is_not_downgraded(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(pkf.read_text(encoding="utf-8").replace("runtime_version: 4", "runtime_version: 5"), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("newer than supported" in finding.issue for finding in report.errors))

    def test_runtime_version_one_requires_mutation_gate_migration(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(pkf.read_text(encoding="utf-8").replace("runtime_version: 4", "runtime_version: 3"), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("must be 4; found 3" in finding.issue for finding in report.errors))

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

    def test_missing_required_protocol_clause_is_ci_blocking(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(pkf.read_text(encoding="utf-8").replace("### Safety and recursion", "### Safety"), encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("missing required closeout protocol clause" in finding.issue for finding in report.errors))

    def test_legacy_every_turn_closeout_protocol_is_ci_blocking(self):
        with self.copy_ai() as ai:
            pkf = ai / "PKF.md"
            pkf.write_text(
                pkf.read_text(encoding="utf-8")
                + "\nRun closeout before every final response.\n",
                encoding="utf-8",
            )
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("legacy every-turn closeout wording" in finding.issue for finding in report.errors))

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

    def test_bootstrap_must_mutation_gate_closeout(self):
        with self.copy_ai() as ai:
            bootstrap = ai.parent / "AGENTS.md"
            bootstrap.write_text(
                bootstrap.read_text(encoding="utf-8").replace("intentional repository mutation", "ordinary turn"),
                encoding="utf-8",
            )
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("gated by a repository mutation" in finding.issue for finding in report.errors))

    def test_bootstrap_must_silently_bypass_read_only_turns(self):
        with self.copy_ai() as ai:
            bootstrap = ai.parent / "AGENTS.md"
            bootstrap.write_text(
                bootstrap.read_text(encoding="utf-8").replace(
                    "Read-only turns bypass closeout silently",
                    "Read-only turns run closeout",
                ),
                encoding="utf-8",
            )
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("silently bypass read-only turns" in finding.issue for finding in report.errors))

    def test_bootstrap_mutation_gate_allows_markdown_line_wrapping(self):
        with self.copy_ai() as ai:
            bootstrap = ai.parent / "AGENTS.md"
            bootstrap.write_text(
                bootstrap.read_text(encoding="utf-8").replace(
                    "Read-only turns bypass closeout silently",
                    "Read-only turns bypass\ncloseout silently",
                ),
                encoding="utf-8",
            )
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 0)

    def test_bootstrap_rejects_legacy_every_turn_wording(self):
        with self.copy_ai() as ai:
            bootstrap = ai.parent / "AGENTS.md"
            bootstrap.write_text(
                bootstrap.read_text(encoding="utf-8")
                + "\nBefore every final response, run closeout.\n",
                encoding="utf-8",
            )
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 1)
        self.assertTrue(any("legacy every-turn closeout wording" in finding.issue for finding in report.errors))

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

    def test_edit_map_rejects_generic_behavior(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "schema.md"
            text = leaf.read_text(encoding="utf-8").replace("| Schema |", "| Documented capability behavior |")
            leaf.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("generic or placeholder" in finding.issue for finding in report.errors))

    def test_edit_map_must_cover_declared_symbols(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "schema.md"
            text = leaf.read_text(encoding="utf-8").replace("CustomerRecord", "UnlistedRecord")
            leaf.write_text(text, encoding="utf-8")
            source = ai.parent / "src" / "backend" / "models" / "customer.ts"
            source.write_text(source.read_text(encoding="utf-8") + "\nconst UnlistedRecord = true;\n", encoding="utf-8")
            text = leaf.read_text(encoding="utf-8").replace(
                "`src/backend/models/customer.ts:UnlistedRecord`",
                "schema declaration",
            ).replace("'UnlistedRecord'", "'OtherRecord'")
            leaf.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("omits declared source symbols" in finding.issue for finding in report.errors))

    def test_edit_map_test_evidence_must_be_routable(self):
        with self.copy_ai() as ai:
            test_path = ai.parent / "src" / "backend" / "models" / "customer.test.ts"
            test_path.write_text("export const customerSchemaTest = true;\n", encoding="utf-8")
            leaf = ai / "knowledge" / "backend" / "schema.md"
            leaf.write_text(
                leaf.read_text(encoding="utf-8").replace(
                    "| Not documented |",
                    "| `src/backend/models/customer.test.ts:customerSchemaTest` |",
                ),
                encoding="utf-8",
            )
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("test evidence is missing from source_symbols" in finding.issue for finding in report.errors))

    def test_module_index_requires_machine_readable_ownership_roots(self):
        with self.copy_ai() as ai:
            index = ai / "knowledge" / "backend" / "INDEX.md"
            index.write_text(
                index.read_text(encoding="utf-8").replace(
                    '  ownership_roots:\n    - "src/backend"\n',
                    "",
                ),
                encoding="utf-8",
            )
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("pkf.ownership_roots must be a non-empty list" in finding.issue for finding in report.errors))

    def test_empty_leaf_requires_standard_marker(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "ui.md"
            text = leaf.read_text(encoding="utf-8").replace("- TODO: No source-backed facts.", "- No UI.")
            leaf.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("empty source_symbols requires marker" in finding.issue for finding in report.errors))

    def test_pending_leaf_is_valid_without_edit_map(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "ui.md"
            text = leaf.read_text(encoding="utf-8")
            text = text.replace("pkf:\n  loads: []", "pkf:\n  materialization: pending\n  loads: []")
            text = text.replace("- TODO: No source-backed facts.", PENDING_LEAF_MARKER)
            leaf.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertEqual(report.exit_code, 0)
        self.assertTrue(any("explicitly unmaterialized" in item for item in report.passed))

    def test_pending_leaf_rejects_declared_source_symbols(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "api.md"
            text = leaf.read_text(encoding="utf-8")
            text = text.replace("pkf:\n  loads: []", "pkf:\n  materialization: pending\n  loads: []")
            leaf.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("pending leaf must not declare source_symbols" in finding.issue for finding in report.errors))

    def test_leaf_token_gate_warns_locally_and_fails_ci(self):
        with self.copy_ai() as ai:
            leaf = ai / "knowledge" / "backend" / "schema.md"
            leaf.write_text(leaf.read_text(encoding="utf-8") + ("context " * 3000), encoding="utf-8")
            advisory = validate_pkf(ai, strictness="advisory")
            ci = validate_pkf(ai, strictness="ci")

        self.assertTrue(any(finding.file == "leaf:backend/schema.md" for finding in advisory.warnings))
        self.assertTrue(any(finding.file == "leaf:backend/schema.md" for finding in ci.errors))
        self.assertEqual(next(entry.status for entry in ci.token_impact if entry.route == "leaf:backend/schema.md"), "error")

    def test_task_route_size_is_measured_without_a_numeric_gate(self):
        with self.copy_ai() as ai:
            index = ai / "knowledge" / "backend" / "INDEX.md"
            text = index.read_text(encoding="utf-8").replace(
                "  loads: []",
                "  loads:\n    - .ai/knowledge/backend/api.md\n    - .ai/knowledge/backend/schema.md\n    - .ai/knowledge/backend/ui.md",
            )
            index.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertFalse(any("retrieval budget" in finding.issue for finding in report.errors))
        task_entry = next(entry for entry in report.token_impact if entry.route == "task:backend")
        self.assertIsNone(task_entry.threshold)
        self.assertEqual(task_entry.status, "measured")
        self.assertEqual(task_entry.document_count, 4)
        self.assertEqual(task_entry.leaf_count, 3)

    def test_changed_path_limits_leaf_contract_validation(self):
        with self.copy_ai() as ai:
            schema = ai / "knowledge" / "backend" / "schema.md"
            schema.write_text(schema.read_text(encoding="utf-8").replace("CustomerRecord", "MissingRecord"), encoding="utf-8")
            report = validate_pkf(
                ai,
                strictness="ci",
                changed_paths=("src/backend/routes/customers.ts",),
                scope="affected",
            )

        self.assertFalse(any("MissingRecord" in finding.issue for finding in report.errors))
        self.assertTrue(any("listCustomersRoute" in item for item in report.passed))
        self.assertEqual(report.scope, "affected")
        self.assertEqual(
            report.checked_docs,
            [".ai/knowledge/backend/INDEX.md", ".ai/knowledge/backend/api.md"],
        )
        self.assertFalse(any(entry.route == "startup" for entry in report.token_impact))

    def test_affected_scope_requires_changed_path(self):
        with self.copy_ai() as ai:
            with self.assertRaises(UsageError):
                validate_pkf(ai, scope="affected")

    def test_affected_scope_escalates_for_routing_changes(self):
        with self.copy_ai() as ai:
            report = validate_pkf(
                ai,
                strictness="ci",
                changed_paths=(".ai/knowledge/INDEX.md",),
                scope="affected",
            )

        self.assertEqual(report.scope, "full")
        self.assertIn(".ai/PKF.md", report.checked_docs)

    def test_affected_scope_escalates_for_shared_knowledge(self):
        with self.copy_ai() as ai:
            report = validate_pkf(
                ai,
                strictness="ci",
                changed_paths=(".ai/knowledge/dependencies.md",),
                scope="affected",
            )

        self.assertEqual(report.scope, "full")
        self.assertIn(".ai/knowledge/dependencies.md", report.checked_docs)

    def test_summary_report_omits_pass_inventory(self):
        with self.copy_ai() as ai:
            report = validate_pkf(
                ai,
                changed_paths=("src/backend/routes/customers.ts",),
                scope="affected",
            )

        payload = report_to_dict(report, detail="summary")
        self.assertNotIn("passed", payload)
        self.assertNotIn("checked_docs", payload)
        self.assertEqual(payload["checked_doc_count"], len(report.checked_docs))
        self.assertGreater(payload["passed_count"], 0)
        self.assertEqual(payload["token_impact_count"], len(report.token_impact))
        self.assertTrue(all(entry["status"] != "passed" for entry in payload["token_impact"]))

    def test_fallback_yaml_parser_handles_keyed_cross_routes(self):
        lines = [
            "pkf:",
            "  routes:",
            "    note-task-links:",
            '      intent: "Note/task relationship"',
            "      triggers: [note-task links, linked notes]",
            "      modules: [notes, boards]",
            "      loads: [.ai/knowledge/notes/business_rules.md, .ai/knowledge/boards/business_rules.md]",
            "  loads: []",
            "  related: []",
        ]

        metadata, index = parse_yaml_block(lines, 0, 0, Path("index.md"))

        self.assertEqual(index, len(lines))
        route = metadata["pkf"]["routes"]["note-task-links"]
        self.assertEqual(route["modules"], ["notes", "boards"])
        self.assertEqual(len(route["loads"]), 2)

    def test_root_cross_routes_require_known_modules_and_complete_leaf_loads(self):
        with self.copy_ai() as ai:
            root_index = ai / "knowledge" / "INDEX.md"
            text = root_index.read_text(encoding="utf-8")
            text = text.replace(
                "  routes: {}",
                "  routes:\n"
                "    invalid-route:\n"
                '      intent: "Cross capability"\n'
                "      triggers: [cross]\n"
                "      modules: [backend, missing]\n"
                "      requirements: [api-contract, schema-contract, business-policy, ui-contract]\n"
                "      loads: [.ai/knowledge/backend/api.md, .ai/knowledge/backend/schema.md, .ai/knowledge/backend/business_rules.md, .ai/knowledge/backend/ui.md]\n"
                "      load_coverage:\n"
                "        .ai/knowledge/backend/api.md: [api-contract]\n"
                "        .ai/knowledge/backend/schema.md: [schema-contract]\n"
                "        .ai/knowledge/backend/business_rules.md: [business-policy]\n"
                "        .ai/knowledge/backend/ui.md: [ui-contract]",
            )
            root_index.write_text(text, encoding="utf-8")
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("unknown modules" in finding.issue for finding in report.errors))
        self.assertFalse(any("leaf" in finding.issue and "maximum" in finding.issue for finding in report.errors))

    def test_atomic_routes_compose_beyond_three_unique_task_leaves(self):
        with self.copy_two_module_ai() as ai:
            self.set_cross_routes(
                ai,
                "    relationship-visibility:\n"
                '      intent: "Relationship visibility"\n'
                "      triggers: [relationship visibility]\n"
                "      modules: [backend, frontend]\n"
                "      requirements: [backend-interface, frontend-visibility]\n"
                "      loads: [.ai/knowledge/backend/api.md, .ai/knowledge/frontend/ui.md]\n"
                "      load_coverage:\n"
                "        .ai/knowledge/backend/api.md: [backend-interface]\n"
                "        .ai/knowledge/frontend/ui.md: [frontend-visibility]\n"
                "    relationship-policy:\n"
                '      intent: "Relationship policy"\n'
                "      triggers: [relationship policy]\n"
                "      modules: [backend, frontend]\n"
                "      requirements: [backend-policy, frontend-policy]\n"
                "      loads: [.ai/knowledge/backend/business_rules.md, .ai/knowledge/frontend/business_rules.md]\n"
                "      load_coverage:\n"
                "        .ai/knowledge/backend/business_rules.md: [backend-policy]\n"
                "        .ai/knowledge/frontend/business_rules.md: [frontend-policy]",
            )
            report = validate_pkf(ai, strictness="ci")

        route_errors = [finding for finding in report.errors if "pkf.routes" in finding.file]
        self.assertEqual(route_errors, [])
        route_entries = [entry for entry in report.token_impact if entry.route.startswith("cross:")]
        self.assertEqual({entry.route for entry in route_entries}, {"cross:relationship-policy", "cross:relationship-visibility"})
        self.assertTrue(all(entry.threshold is None and entry.status == "measured" for entry in route_entries))

    def test_one_leaf_can_cover_a_multi_module_route(self):
        with self.copy_two_module_ai() as ai:
            self.set_cross_routes(
                ai,
                "    shared-contract:\n"
                '      intent: "Shared relationship contract"\n'
                "      triggers: [shared relationship]\n"
                "      modules: [backend, frontend]\n"
                "      requirements: [relationship-policy]\n"
                "      loads: [.ai/knowledge/backend/business_rules.md]\n"
                "      load_coverage:\n"
                "        .ai/knowledge/backend/business_rules.md: [relationship-policy]",
            )
            report = validate_pkf(ai, strictness="ci")

        route_errors = [finding for finding in report.errors if "pkf.routes.shared-contract" in finding.file]
        self.assertEqual(route_errors, [])
        coverage = next(item for item in report.route_coverage if item.route == "shared-contract")
        self.assertEqual(coverage.leaf_count, 1)
        self.assertEqual(coverage.minimality_status, "minimal")

    def test_seven_uniquely_required_leaves_have_no_exception_ceiling(self):
        with self.copy_two_module_ai() as ai:
            loads = (
                ".ai/knowledge/backend/api.md",
                ".ai/knowledge/backend/schema.md",
                ".ai/knowledge/backend/business_rules.md",
                ".ai/knowledge/backend/ui.md",
                ".ai/knowledge/frontend/api.md",
                ".ai/knowledge/frontend/schema.md",
                ".ai/knowledge/frontend/business_rules.md",
            )
            route = (
                "    seven-part-contract:\n"
                '      intent: "Seven independently owned requirements"\n'
                "      triggers: [seven part contract]\n"
                "      modules: [backend, frontend]\n"
                f"      requirements: [{', '.join(f'requirement-{index}' for index in range(1, 8))}]\n"
                f"      loads: [{', '.join(loads)}]\n"
                "      load_coverage:\n"
                + "".join(
                    f"        {load}: [requirement-{index}]\n"
                    for index, load in enumerate(loads, start=1)
                ).rstrip()
            )
            self.set_cross_routes(ai, route)
            report = validate_pkf(ai, strictness="ci")

        route_errors = [finding for finding in report.errors if "pkf.routes.seven-part-contract" in finding.file]
        self.assertEqual(route_errors, [])
        coverage = next(item for item in report.route_coverage if item.route == "seven-part-contract")
        self.assertEqual(coverage.leaf_count, 7)
        self.assertEqual(coverage.minimality_status, "minimal")

    def test_redundant_route_leaf_is_rejected(self):
        with self.copy_two_module_ai() as ai:
            self.set_cross_routes(
                ai,
                "    redundant-contract:\n"
                '      intent: "Redundant relationship contract"\n'
                "      triggers: [redundant relationship]\n"
                "      modules: [backend, frontend]\n"
                "      requirements: [relationship-policy]\n"
                "      loads: [.ai/knowledge/backend/business_rules.md, .ai/knowledge/frontend/business_rules.md]\n"
                "      load_coverage:\n"
                "        .ai/knowledge/backend/business_rules.md: [relationship-policy]\n"
                "        .ai/knowledge/frontend/business_rules.md: [relationship-policy]",
            )
            report = validate_pkf(ai, strictness="ci")

        self.assertTrue(any("redundant loads" in finding.issue for finding in report.errors))
        coverage = next(item for item in report.route_coverage if item.route == "redundant-contract")
        self.assertEqual(coverage.minimality_status, "redundant")

    def test_route_coverage_rejects_unknown_and_uncovered_requirements(self):
        with self.copy_two_module_ai() as ai:
            self.set_cross_routes(
                ai,
                "    incomplete-contract:\n"
                '      intent: "Incomplete relationship contract"\n'
                "      triggers: [incomplete relationship]\n"
                "      modules: [backend, frontend]\n"
                "      requirements: [relationship-policy, relationship-lifecycle]\n"
                "      loads: [.ai/knowledge/backend/business_rules.md]\n"
                "      load_coverage:\n"
                "        .ai/knowledge/backend/business_rules.md: [relationship-policy, invented-requirement]",
            )
            report = validate_pkf(ai, strictness="ci")

        issues = [finding.issue for finding in report.errors]
        self.assertTrue(any("unknown requirements: invented-requirement" in issue for issue in issues))
        self.assertTrue(any("uncovered requirements: relationship-lifecycle" in issue for issue in issues))
        coverage = next(item for item in report.route_coverage if item.route == "incomplete-contract")
        self.assertEqual(coverage.coverage_status, "incomplete")
        self.assertEqual(coverage.minimality_status, "invalid")

    def test_legacy_route_remains_readable_with_unknown_minimality(self):
        with self.copy_two_module_ai() as ai:
            self.set_cross_routes(
                ai,
                "    legacy-contract:\n"
                '      intent: "Legacy contract"\n'
                "      triggers: [legacy relationship]\n"
                "      modules: [backend, frontend]\n"
                "      loads: [.ai/knowledge/backend/api.md]",
            )
            report = validate_pkf(ai, strictness="ci")

        self.assertFalse(report.errors)
        self.assertTrue(any("minimality is unknown" in finding.issue for finding in report.warnings))
        coverage = next(item for item in report.route_coverage if item.route == "legacy-contract")
        self.assertEqual(coverage.coverage_status, "unknown")

    def test_unmapped_changed_path_warns(self):
        with self.copy_ai() as ai:
            report = validate_pkf(ai, changed_paths=("docs/unknown.md",))

        self.assertTrue(any(finding.file == "docs/unknown.md" for finding in report.warnings))

    def test_changed_path_must_be_repository_relative(self):
        with self.copy_ai() as ai:
            with self.assertRaises(UsageError):
                validate_pkf(ai, changed_paths=("../outside.py",))

    def test_internal_initialize_uses_public_protocol_templates(self):
        public = PUBLIC_INITIALIZE.read_text(encoding="utf-8")
        internal = INTERNAL_INITIALIZE.read_text(encoding="utf-8")
        protocols = (PUBLIC_INITIALIZE.parent.parent / "templates" / "protocols.md").read_text(encoding="utf-8")
        bootstrap = (PUBLIC_INITIALIZE.parent.parent / "templates" / "bootstrap.md").read_text(encoding="utf-8")

        self.assertEqual(public, internal)
        self.assertIn("pkf_scaffold.py inspect", public)
        self.assertIn("## Retrieval Protocol (MANDATORY)", protocols)
        self.assertIn("## Closeout Protocol (MANDATORY)", protocols)
        self.assertIn("token-atlas:bootstrap:start", bootstrap)
        skill = INTERNAL_SKILL.read_text(encoding="utf-8")
        self.assertIn("embed the Retrieval and Closeout Protocols", skill)
        self.assertIn("neutral bootstrap", skill)

    def test_seeded_fixture_runtimes_include_bootstrap_contract(self):
        for pkf in sorted(FIXTURES.rglob("PKF.md")):
            if ".ai" not in pkf.parts:
                continue
            self.assertIn("## Retrieval Protocol (MANDATORY)", pkf.read_text(encoding="utf-8"), pkf)
            self.assertIn("## Closeout Protocol (MANDATORY)", pkf.read_text(encoding="utf-8"), pkf)
            self.assertEqual(read_front_matter(pkf)["pkf"]["runtime_version"], RUNTIME_VERSION, pkf)
            self.assertEqual(read_front_matter(pkf)["pkf"]["retrieval"], "adaptive", pkf)
            self.assertEqual(read_front_matter(pkf)["pkf"]["closeout"], "adaptive", pkf)
            bootstrap = pkf.parent.parent / "AGENTS.md"
            self.assertTrue(bootstrap.is_file(), f"missing bootstrap for {pkf}")
            self.assertIn(".ai/PKF.md", bootstrap.read_text(encoding="utf-8"), bootstrap)
            self.assertIn("Closeout Protocol", bootstrap.read_text(encoding="utf-8"), bootstrap)
            self.assertIn("repository mutation", bootstrap.read_text(encoding="utf-8").lower(), bootstrap)

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

    def copy_two_module_ai(self):
        temp = tempfile.TemporaryDirectory()
        root = Path(temp.name)
        shutil.copytree(TWO_MODULE_REPO, root, dirs_exist_ok=True)
        target = root / ".ai"
        backend_index = target / "knowledge" / "backend" / "INDEX.md"
        backend_index.write_text(
            backend_index.read_text(encoding="utf-8").replace(
                "  loads:\n    - .ai/knowledge/backend/api.md\n    - .ai/knowledge/frontend/ui.md",
                "  loads: []",
            ),
            encoding="utf-8",
        )

        class Context:
            def __enter__(self):
                return target

            def __exit__(self, exc_type, exc, tb):
                temp.cleanup()

        return Context()

    @staticmethod
    def set_cross_routes(ai: Path, route_block: str) -> None:
        root_index = ai / "knowledge" / "INDEX.md"
        root_index.write_text(
            root_index.read_text(encoding="utf-8").replace(
                "  routes: {}",
                f"  routes:\n{route_block}",
            ),
            encoding="utf-8",
        )

    @staticmethod
    def template_block(text: str, heading: str) -> str:
        start = text.index(heading)
        fence_start = text.index("````markdown\n", start)
        fence_end = text.index("\n````", fence_start) + len("\n````")
        return text[fence_start:fence_end]


if __name__ == "__main__":
    unittest.main()
