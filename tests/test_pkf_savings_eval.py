import importlib.util
import concurrent.futures
import contextlib
import io
import json
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pkf_savings_eval.py"
SPEC = importlib.util.spec_from_file_location("pkf_savings_eval", SCRIPT)
pkf_savings_eval = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = pkf_savings_eval
SPEC.loader.exec_module(pkf_savings_eval)


class PkfSavingsEvalTests(unittest.TestCase):
    def make_result(self, **overrides):
        values = {
            "repetition": 1,
            "arm": "probe_only",
            "task_id": "local-read",
            "phase": "simple_retrieval",
            "returncode": 0,
            "duration_ms": 100,
            "usage": pkf_savings_eval.Usage(1_000, 200, 50),
            "answer": {},
            "answer_correct": True,
            "accessed_skill": False,
            "accessed_closeout": False,
            "used_route_helper": False,
            "emitted_closeout": False,
            "retrieval_decision": "not_applicable",
            "fallback_search": False,
            "mentioned_path_count": 1,
            "mentioned_ai_path_count": 0,
            "tool_call_count": 2,
            "read_or_search_command_count": 1,
            "tool_input_chars": 50,
            "tool_output_chars": 500,
            "explicit_read_path_count": 1,
            "explicit_ai_read_path_count": 0,
            "explicit_skill_read_path_count": 0,
            "searched_root_count": 1,
            "ai_read_or_search_command_count": 0,
            "routed_document_count": 0,
            "fallback_invocation_count": 0,
            "changed_path_count": 0,
            "changed_expected_paths": None,
            "focused_test_passed": None,
            "pkf_validation_passed": None,
            "error": "",
        }
        values.update(overrides)
        return pkf_savings_eval.CodexResult(**values)

    def benchmark_spec(self):
        return pkf_savings_eval.BenchmarkSpec(
            schema_version=1,
            benchmark_id="generic-lifecycle",
            retrieval_tasks=(
                pkf_savings_eval.TaskSpec("local-read", "Local question", {"ok": True}, "local"),
                pkf_savings_eval.TaskSpec("cross-read", "Cross question", {"ok": True}, "cross_capability"),
            ),
            mutation=pkf_savings_eval.MutationSpec(
                "mutation-task", "Change behavior", ("src/state.ts", "tests/state.test.ts"), ("true",)
            ),
            post_mutation=pkf_savings_eval.TaskSpec(
                "post-read", "Read changed behavior", {"ok": True}, "local"
            ),
            closeout=pkf_savings_eval.CloseoutSpec(
                "closeout-task", "Control", "Close out", Path("patch.diff"),
                ("src/state.ts", "tests/state.test.ts"), ("true",)
            ),
            workspace_links=(),
            digest="a" * 64,
            path=Path("benchmark.json"),
        )

    def initialize_repo(self, repo: Path) -> None:
        subprocess.run(("git", "init", "--quiet"), cwd=repo, check=True)
        subprocess.run(("git", "config", "user.name", "Eval Test"), cwd=repo, check=True)
        subprocess.run(
            ("git", "config", "user.email", "eval-test@example.invalid"),
            cwd=repo,
            check=True,
        )
        subprocess.run(("git", "add", "."), cwd=repo, check=True)
        subprocess.run(("git", "commit", "--quiet", "-m", "fixture"), cwd=repo, check=True)

    def test_schedule_splits_explicit_phases_and_counterbalances_arms(self):
        spec = self.benchmark_spec()
        simple = pkf_savings_eval.build_schedule(3, ("simple_retrieval",), spec)
        cross = pkf_savings_eval.build_schedule(3, ("cross_capability_retrieval",), spec)
        diagnostic = pkf_savings_eval.build_schedule(
            3, ("simple_retrieval",), spec, include_source_only=True
        )
        mutation = pkf_savings_eval.build_schedule(3, ("mutation",), spec)
        closeout = pkf_savings_eval.build_schedule(3, ("closeout",), spec)
        all_tasks = pkf_savings_eval.build_schedule(
            3,
            (
                "simple_retrieval",
                "cross_capability_retrieval",
                "mutation",
                "post_mutation",
                "closeout",
            ),
            spec,
        )

        self.assertEqual(len(simple), 6)
        self.assertEqual(len(cross), 6)
        self.assertEqual(len(diagnostic), 9)
        self.assertEqual(len(mutation), 6)
        self.assertEqual(len(closeout), 6)
        self.assertEqual(len(all_tasks), 30)
        self.assertNotIn("initialize", {item["task_id"] for item in all_tasks})
        first_boards = [
            item["arm"]
            for item in diagnostic
            if item["repetition"] == 1 and item["task_id"] == "local-read"
        ]
        second_boards = [
            item["arm"]
            for item in diagnostic
            if item["repetition"] == 2 and item["task_id"] == "local-read"
        ]
        self.assertEqual(first_boards, ["source_only", "probe_only", "pkf"])
        self.assertEqual(second_boards, ["probe_only", "pkf", "source_only"])

    def test_cli_requires_external_spec_model_and_explicit_phases(self):
        args = pkf_savings_eval.parse_args((
            "--target-repo", "/tmp/target",
            "--benchmark-spec", "/tmp/spec.json",
            "--model", "model-id",
            "--model-reasoning-effort", "high",
            "--phases", "simple_retrieval,closeout",
        ))

        self.assertEqual(args.target_commit, "HEAD")
        self.assertEqual(args.model, "model-id")
        self.assertEqual(args.model_reasoning_effort, "high")
        self.assertEqual(args.repetitions, 3)
        self.assertEqual(args.phases, ("simple_retrieval", "closeout"))
        self.assertFalse(args.include_source_only)
        self.assertEqual(args.jobs, 0)
        self.assertEqual(args.artifact_mode, "full")
        self.assertEqual(args.artifacts_root, pkf_savings_eval.DEFAULT_ARTIFACTS_ROOT)
        generated_run_id = pkf_savings_eval.make_run_id(args, self.benchmark_spec())
        self.assertIn("simple-closeout", generated_run_id)
        self.assertRegex(generated_run_id, r"-replicated-\d{8}T\d{6}Z$")
        self.assertLessEqual(len(generated_run_id), 128)

    def test_cli_source_only_is_opt_in_and_legacy_retrieval_is_rejected(self):
        args = pkf_savings_eval.parse_args((
            "--target-repo", "/tmp/target",
            "--benchmark-spec", "/tmp/spec.json",
            "--model", "model-id",
            "--model-reasoning-effort", "high",
            "--phases", "cross_capability_retrieval",
            "--include-source-only",
        ))

        self.assertTrue(args.include_source_only)
        self.assertIn("source-diag", pkf_savings_eval.make_run_id(args, self.benchmark_spec()))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            pkf_savings_eval.parse_args(
                (
                    "--target-repo",
                    "/tmp/target",
                    "--benchmark-spec",
                    "/tmp/spec.json",
                    "--model",
                    "model-id",
                    "--model-reasoning-effort",
                    "high",
                    "--phases",
                    "retrieval",
                )
            )

    def test_external_benchmark_spec_owns_repository_specific_tasks(self):
        spec = pkf_savings_eval.load_benchmark_spec(
            ROOT / "benchmarks" / "targets" / "tether-brain.json"
        )

        self.assertEqual(spec.schema_version, 1)
        self.assertTrue(spec.retrieval_tasks)
        self.assertIsNotNone(spec.mutation)
        self.assertIsNotNone(spec.closeout)
        self.assertEqual(spec.workspace_links, ("frontend/node_modules",))
        self.assertEqual(len(spec.digest), 64)

    def test_schema_ten_and_benchmark_spec_schemas_are_explicit(self):
        report_schema = json.loads(
            (ROOT / "benchmarks" / "schemas" / "pkf-savings-report.schema.json").read_text(encoding="utf-8")
        )
        spec_schema = json.loads(
            (ROOT / "benchmarks" / "schemas" / "benchmark-spec.schema.json").read_text(encoding="utf-8")
        )

        self.assertEqual(report_schema["properties"]["schema_version"]["const"], 10)
        self.assertEqual(spec_schema["properties"]["schema_version"]["const"], 1)
        self.assertNotIn("minimality_status", json.dumps(report_schema))
        self.assertNotIn("retrieval", report_schema["properties"]["phases_selected"]["items"]["enum"])

    def test_parse_jsonl_extracts_usage_and_structured_answer(self):
        answer = {
            "task_id": "local-read",
            "answers": {"ok": True},
            "evidence": ["source"],
        }
        output = "\n".join(
            (
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message", "text": json.dumps(answer)},
                    }
                ),
                json.dumps(
                    {
                        "type": "turn.completed",
                        "usage": {
                            "input_tokens": 1_200,
                            "cached_input_tokens": 200,
                            "output_tokens": 80,
                        },
                    }
                ),
            )
        )

        usage, messages, normalized = pkf_savings_eval.parse_jsonl(output)

        self.assertEqual(usage, pkf_savings_eval.Usage(1_200, 200, 80))
        self.assertEqual(pkf_savings_eval.parse_structured_answer(messages), answer)
        self.assertIn("turn.completed", normalized)

    def test_pkf_route_marker_parses_composed_routes_and_rejects_duplicates(self):
        marker = pkf_savings_eval.parse_pkf_route_marker(
            {
                "evidence": [
                    "PKF route: note-link-policy + note-link-lifecycle; 4 unique leaves; fallback=no"
                ]
            }
        )

        self.assertEqual(marker["status"], "valid")
        self.assertEqual(marker["route_ids"], ("note-link-policy", "note-link-lifecycle"))
        self.assertEqual(marker["unique_leaf_count"], 4)
        self.assertFalse(marker["fallback"])

        duplicate = pkf_savings_eval.parse_pkf_route_marker(
            {"evidence": ["PKF route: note-link-policy + note-link-policy; 2 unique leaves; fallback=no"]}
        )
        self.assertEqual(duplicate["status"], "duplicate_routes")
        malformed = pkf_savings_eval.parse_pkf_route_marker(
            {"evidence": ["PKF route: note-link-policy; fallback=no"]}
        )
        self.assertEqual(malformed["status"], "malformed")

    def test_configured_cross_routes_reports_authoritative_irredundant_composition(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            index = repo / ".ai/knowledge/INDEX.md"
            index.parent.mkdir(parents=True)
            index.write_text(
                "---\n"
                "pkf:\n"
                "  routes:\n"
                "    policy:\n"
                "      requirements: [note-policy, shared-policy]\n"
                "      loads: [.ai/knowledge/notes/api.md, .ai/knowledge/shared/business_rules.md]\n"
                "      load_coverage:\n"
                "        .ai/knowledge/notes/api.md: [note-policy]\n"
                "        .ai/knowledge/shared/business_rules.md: [shared-policy]\n"
                "    lifecycle:\n"
                "      requirements: [board-lifecycle, shared-policy]\n"
                "      loads: [.ai/knowledge/shared/business_rules.md, .ai/knowledge/boards/business_rules.md]\n"
                "      load_coverage:\n"
                "        .ai/knowledge/shared/business_rules.md: [shared-policy]\n"
                "        .ai/knowledge/boards/business_rules.md: [board-lifecycle]\n"
                "---\n",
                encoding="utf-8",
            )
            for relative in (
                ".ai/knowledge/notes/api.md",
                ".ai/knowledge/shared/business_rules.md",
                ".ai/knowledge/boards/business_rules.md",
            ):
                path = repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("source-backed route content\n", encoding="utf-8")

            configured = pkf_savings_eval.configured_cross_routes(
                repo,
                ("policy", "lifecycle", "undefined"),
            )
            complete = pkf_savings_eval.configured_cross_routes(repo, ("policy", "lifecycle"))

        self.assertEqual(
            configured["expected_loads"],
            (
                ".ai/knowledge/boards/business_rules.md",
                ".ai/knowledge/notes/api.md",
                ".ai/knowledge/shared/business_rules.md",
            ),
        )
        self.assertEqual(configured["missing_route_ids"], ("undefined",))
        self.assertEqual(configured["coverage_status"], "incomplete")
        self.assertEqual(configured["requirement_count"], 3)

        self.assertEqual(complete["coverage_status"], "complete")
        self.assertEqual(complete["irredundancy_status"], "irredundant")
        self.assertEqual(complete["redundant_loads"], ())

    def test_configured_cross_routes_distinguishes_conflicts_and_redundancy(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            index = repo / ".ai/knowledge/INDEX.md"
            index.parent.mkdir(parents=True)
            index.write_text(
                "---\n"
                "pkf:\n"
                "  routes:\n"
                "    conflicting:\n"
                "      requirements: [shared-policy]\n"
                "      loads: [.ai/knowledge/notes/api.md, .ai/knowledge/boards/api.md]\n"
                "      load_coverage:\n"
                "        .ai/knowledge/notes/api.md: [shared-policy]\n"
                "        .ai/knowledge/boards/api.md: [shared-policy]\n"
                "    redundant:\n"
                "      requirements: [note-policy]\n"
                "      loads: [.ai/knowledge/notes/api.md, .ai/knowledge/notes/business_rules.md]\n"
                "      load_coverage:\n"
                "        .ai/knowledge/notes/api.md: [note-policy]\n"
                "        .ai/knowledge/notes/business_rules.md: []\n"
                "---\n",
                encoding="utf-8",
            )
            for relative in (
                ".ai/knowledge/notes/api.md",
                ".ai/knowledge/notes/business_rules.md",
                ".ai/knowledge/boards/api.md",
            ):
                path = repo / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("route content\n", encoding="utf-8")

            conflict = pkf_savings_eval.configured_cross_routes(repo, ("conflicting",))
            redundant = pkf_savings_eval.configured_cross_routes(repo, ("redundant",))
            optional = pkf_savings_eval.configured_cross_routes(repo, ())

        self.assertEqual(conflict["conflicting_requirements"], ("shared-policy",))
        self.assertEqual(conflict["irredundancy_status"], "invalid")
        self.assertEqual(conflict["redundant_loads"], ())
        self.assertEqual(redundant["coverage_status"], "complete")
        self.assertEqual(redundant["irredundancy_status"], "redundant")
        self.assertEqual(
            redundant["redundant_loads"],
            (".ai/knowledge/notes/business_rules.md",),
        )
        self.assertEqual(optional["irredundancy_status"], "unknown")

    def test_trace_metrics_separate_tool_input_output_and_explicit_reads(self):
        output = "\n".join(
            (
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "command_execution", "command": "rg -n Widget src", "output": "src/a.py:1"},
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message", "text": "done"},
                    }
                ),
            )
        )

        metrics = pkf_savings_eval.inspect_jsonl_trace(
            output,
            known_paths=("src/a.py",),
            known_directories=("src",),
        )

        self.assertEqual(metrics.tool_call_count, 1)
        self.assertEqual(metrics.read_or_search_command_count, 1)
        self.assertEqual(metrics.tool_input_chars, len("rg -n Widget src"))
        self.assertEqual(metrics.tool_output_chars, len("src/a.py:1"))
        self.assertEqual(metrics.explicit_read_path_count, 0)
        self.assertEqual(metrics.searched_root_count, 1)

    def test_trace_does_not_treat_output_path_mentions_as_reads(self):
        output = json.dumps(
            {
                "type": "item.completed",
                "item": {
                    "type": "command_execution",
                    "command": "rg -n Widget src",
                    "output": ".ai/PKF.md mentions Widget",
                },
            }
        )

        metrics = pkf_savings_eval.inspect_jsonl_trace(
            output,
            known_paths=(".ai/PKF.md",),
            known_directories=("src",),
        )

        self.assertEqual(metrics.explicit_ai_read_path_count, 0)
        self.assertEqual(metrics.ai_read_or_search_command_count, 0)

    def test_trace_classifies_invoked_commands_instead_of_substrings(self):
        events = [
            {
                "type": "command_execution",
                "command": "python -S .ai/tools/pkf_validate.py --detail summary --changed-path src/state.ts",
                "output": "{}",
            },
            {
                "type": "command_execution",
                "command": "rg -n pkf_validate.py .ai/tools/pkf_validate.py",
                "output": "1:def main",
            },
            {
                "type": "command_execution",
                "command": "env PYTHONDONTWRITEBYTECODE=1 python -S .ai/tools/pkf_validate.py --detail summary",
                "output": "{}",
            },
            {
                "type": "command_execution",
                "command": "env SEARCH_MODE=1 rg -n pkf_validate.py .ai/tools/pkf_validate.py",
                "output": "1:def main",
            },
        ]

        metrics = pkf_savings_eval.inspect_tool_events(
            events,
            known_paths=("src/state.ts", ".ai/tools/pkf_validate.py"),
        )

        self.assertEqual(metrics.read_or_search_command_count, 2)
        self.assertEqual(pkf_savings_eval.invoked_script_count(events[0], "pkf_validate.py"), 1)
        self.assertEqual(pkf_savings_eval.invoked_script_count(events[1], "pkf_validate.py"), 0)
        self.assertEqual(pkf_savings_eval.invoked_script_count(events[2], "pkf_validate.py"), 1)
        self.assertEqual(pkf_savings_eval.invoked_script_count(events[3], "pkf_validate.py"), 0)
        self.assertEqual(
            pkf_savings_eval.explicit_read_paths_for_events(events, ("src/state.ts", ".ai/tools/pkf_validate.py")),
            {".ai/tools/pkf_validate.py"},
        )

    def test_helper_source_reads_include_directory_searches_but_not_invocations(self):
        events = [
            {
                "type": "command_execution",
                "command": "rg -n 'def main' .codex/skills/token-atlas/scripts",
                "output": "pkf_scaffold.py:1:def main",
            },
            {
                "type": "command_execution",
                "command": "python -S .ai/tools/pkf_validate.py --detail summary",
                "output": "{}",
            },
        ]

        self.assertEqual(
            pkf_savings_eval.helper_source_read_paths(events),
            (".codex/skills/token-atlas/scripts",),
        )

    def test_route_parser_ignores_searches_that_only_mention_helper_source(self):
        events = [
            {
                "type": "command_execution",
                "command": "rg -n route .ai/tools/pkf_route.py",
                "output": '{"status":"mapped","affected_leaves":[]}',
            }
        ]

        self.assertEqual(pkf_savings_eval.parse_route_attempts(events), ())

    def test_prepare_arms_uses_same_commit_and_removes_pkf_from_baseline(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            target = temp / "target"
            target.mkdir()
            (target / ".ai").mkdir()
            (target / ".ai" / "PKF.md").write_text("runtime", encoding="utf-8")
            skill = target / ".codex" / "skills" / "token-atlas"
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("old", encoding="utf-8")
            best_practices = target / ".codex" / "best-practices"
            best_practices.mkdir(parents=True)
            (best_practices / "PYTHON-BEST-PRACTICES.md").write_text("rules", encoding="utf-8")
            (target / "AGENTS.md").write_text(
                "Preserve this instruction.\n"
                "<!-- token-atlas:bootstrap:start -->\nold PKF instructions\n"
                "<!-- token-atlas:bootstrap:end -->\n",
                encoding="utf-8",
            )
            (target / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            self.initialize_repo(target)
            commit = subprocess.run(
                ("git", "rev-parse", "HEAD"),
                cwd=target,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()
            dependencies = target / "vendor-cache"
            dependencies.mkdir()
            (dependencies / "dependency.txt").write_text("cached\n", encoding="utf-8")

            workspace = temp / "workspace"
            workspace.mkdir()
            baseline = temp / "baseline"
            (baseline / "runtime" / ".ai").mkdir(parents=True)
            (baseline / "runtime" / ".ai" / "PKF.md").write_text("runtime\n", encoding="utf-8")
            (baseline / "runtime" / "AGENTS.md").write_text("baseline instructions\n", encoding="utf-8")
            arms = pkf_savings_eval.prepare_arms(
                workspace,
                target_repo=target,
                target_commit=commit,
                baseline=baseline,
                workspace_links=("vendor-cache",),
                include_source_only=True,
            )

            self.assertFalse((arms["source_only"] / ".ai").exists())
            self.assertFalse(
                (arms["source_only"] / ".codex" / "skills" / "token-atlas").exists()
            )
            self.assertFalse((arms["probe_only"] / ".ai").exists())
            self.assertTrue((arms["pkf"] / ".codex" / "skills" / "token-atlas" / "SKILL.md").is_file())
            self.assertEqual(
                (arms["source_only"] / "AGENTS.md").read_text(encoding="utf-8"),
                "Preserve this instruction.\n",
            )
            self.assertIn("cheap local probe", (arms["probe_only"] / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertTrue((arms["source_only"] / "vendor-cache").is_symlink())
            self.assertEqual(
                subprocess.run(
                    ("git", "status", "--porcelain"),
                    cwd=arms["source_only"],
                    check=True,
                    capture_output=True,
                    text=True,
                ).stdout,
                "",
            )

    def test_trace_path_inventory_includes_untracked_initialized_runtime(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            (repo / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            self.initialize_repo(repo)
            generated = repo / ".ai" / "tools" / "pkf_validate.py"
            generated.parent.mkdir(parents=True)
            generated.write_text("# generated helper\n", encoding="utf-8")

            self.assertIn(
                ".ai/tools/pkf_validate.py",
                pkf_savings_eval.tracked_paths(repo),
            )

    def test_aggregate_excludes_one_time_initialization_from_operational_metrics(self):
        results = [
            self.make_result(arm="probe_only", usage=pkf_savings_eval.Usage(2_000, 0, 20)),
            self.make_result(
                arm="pkf",
                usage=pkf_savings_eval.Usage(1_500, 0, 20),
                retrieval_decision="activated",
            ),
            self.make_result(
                arm="probe_only",
                task_id="mutation-task",
                phase="mutation",
                usage=pkf_savings_eval.Usage(1_000, 0, 20),
                answer_correct=None,
            ),
            self.make_result(
                arm="pkf",
                task_id="mutation-task",
                phase="mutation",
                usage=pkf_savings_eval.Usage(1_500, 0, 20),
                answer_correct=None,
            ),
            self.make_result(
                arm="probe_only",
                task_id="closeout-task",
                phase="closeout",
                usage=pkf_savings_eval.Usage(100, 0, 5),
                answer_correct=None,
            ),
            self.make_result(
                arm="pkf",
                task_id="closeout-task",
                phase="closeout",
                usage=pkf_savings_eval.Usage(600, 0, 5),
                answer_correct=None,
            ),
        ]

        metrics = pkf_savings_eval.aggregate_metrics(results)

        self.assertEqual(metrics["activated_pkf_knowledge_savings"]["input_tokens"], 500)
        self.assertEqual(metrics["activated_pkf_knowledge_savings"]["paired_count"], 1)
        self.assertNotIn("break_even_activated_tasks", metrics)
        phase_costs = metrics["lifecycle_phase_cost_summary"]
        self.assertEqual(phase_costs["implementation"]["input_tokens"], 1_000)
        self.assertEqual(phase_costs["closeout"]["input_tokens"], 600)
        self.assertEqual(phase_costs["composed_probe_plus_closeout"]["input_tokens"], 1_600)
        self.assertEqual(phase_costs["integrated_observed"]["input_tokens"], 1_500)

    def test_bypassed_tasks_are_not_counted_as_pkf_knowledge_savings(self):
        metrics = pkf_savings_eval.aggregate_metrics(
            (
                self.make_result(arm="probe_only", usage=pkf_savings_eval.Usage(1_000, 100, 10)),
                self.make_result(
                    arm="pkf",
                    usage=pkf_savings_eval.Usage(900, 100, 10),
                    retrieval_decision="bypassed",
                ),
            )
        )

        self.assertEqual(metrics["activated_pkf_knowledge_savings"]["paired_count"], 0)
        self.assertEqual(
            metrics["bypassed_pkf_environment_deltas"]["local-read"]["input_tokens"],
            -100,
        )

    def test_retrieval_decision_activates_only_for_pkf_reads(self):
        empty = pkf_savings_eval.TraceMetrics(0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, False)
        activated = pkf_savings_eval.TraceMetrics(1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 0, False)

        self.assertEqual(
            pkf_savings_eval.classify_retrieval_decision(
                arm="pkf", phase="simple_retrieval", trace=empty
            ),
            "bypassed",
        )
        self.assertEqual(
            pkf_savings_eval.classify_retrieval_decision(
                arm="pkf", phase="cross_capability_retrieval", trace=activated
            ),
            "activated",
        )
        self.assertEqual(
            pkf_savings_eval.classify_retrieval_decision(
                arm="probe_only", phase="simple_retrieval", trace=activated
            ),
            "not_applicable",
        )

    def test_one_repetition_reports_directional_performance_checks(self):
        metrics = pkf_savings_eval.aggregate_metrics(
            (
                self.make_result(arm="probe_only"),
                self.make_result(arm="pkf", explicit_ai_read_path_count=0),
            )
        )

        performance = pkf_savings_eval.performance_advisories(metrics, 1, self.benchmark_spec())

        self.assertEqual(performance["evidence_strength"], "directional")
        self.assertEqual(performance["status"], "preliminary")
        self.assertTrue(performance["checks"])
        self.assertEqual(performance["phases"]["local_bypass"]["status"], "directional_met")

    def test_performance_scorecard_does_not_gate_initialization_or_closeout_by_five_percent(self):
        results = (
            self.make_result(
                arm="pkf",
                task_id="initialize",
                phase="setup",
                answer_correct=None,
                pkf_validation_passed=True,
                initialization_validation_call_count=1,
            ),
            self.make_result(arm="probe_only", task_id="mutation-task", phase="mutation"),
            self.make_result(arm="pkf", task_id="mutation-task", phase="mutation"),
            self.make_result(arm="probe_only", task_id="closeout-task", phase="closeout"),
            self.make_result(
                arm="pkf",
                task_id="closeout-task",
                phase="closeout",
                initial_route_status="mapped",
                tool_call_count=5,
            ),
        )
        performance = pkf_savings_eval.performance_advisories(
            pkf_savings_eval.aggregate_metrics(results),
            1,
            self.benchmark_spec(),
        )
        names = {check["name"] for check in performance["checks"]}

        self.assertFalse(any(name.startswith("initialization_") for name in names))
        self.assertFalse(any(name.startswith("composed_mutation_") for name in names))
        self.assertFalse(any(name.startswith("operational_") for name in names))
        self.assertIn("closeout_incremental", performance["phases"]["closeout"]["measurements"])

    def test_cross_quality_accepts_composed_atomic_route_union_over_three_leaves(self):
        leaves = (
            ".ai/knowledge/notes/api.md",
            ".ai/knowledge/notes/business_rules.md",
            ".ai/knowledge/boards/api.md",
            ".ai/knowledge/boards/business_rules.md",
        )
        result = self.make_result(
            arm="pkf",
            task_id="cross-read",
            explicit_ai_read_path_count=5,
            retrieval_decision="activated",
            routed_document_count=4,
            cross_route_marker_status="valid",
            cross_route_ids=("note-link-policy", "note-link-lifecycle"),
            cross_route_unique_leaf_count=4,
            cross_route_fallback=False,
            cross_declared_document_paths=leaves,
            cross_expected_document_paths=leaves,
            cross_observed_document_paths=leaves,
            cross_requirement_count=4,
            cross_covered_requirement_count=4,
            cross_coverage_status="complete",
            cross_irredundancy_status="irredundant",
            cross_estimated_tokens=1200,
        )

        self.assertEqual(pkf_savings_eval.evaluation_errors((result,), 1, self.benchmark_spec()), [])

        errors = pkf_savings_eval.evaluation_errors(
            (self.make_result(arm="pkf", retrieval_decision="bypassed", route_marker_emitted=True),),
            1,
            self.benchmark_spec(),
        )
        self.assertTrue(any("bypassed local task emitted" in error for error in errors))

        redundancy_errors = pkf_savings_eval.evaluation_errors(
            (
                pkf_savings_eval.replace_result(
                    result,
                    cross_irredundancy_status="redundant",
                    cross_redundant_document_paths=(leaves[-1],),
                ),
            ),
            1,
            self.benchmark_spec(),
        )
        self.assertTrue(any("redundant route-declared leaf selection" in error for error in redundancy_errors))

        unexpected_errors = pkf_savings_eval.evaluation_errors(
            (
                pkf_savings_eval.replace_result(
                    result,
                    cross_observed_document_paths=(*leaves, ".ai/knowledge/workspace/api.md"),
                    cross_unexpected_document_paths=(".ai/knowledge/workspace/api.md",),
                ),
            ),
            1,
            self.benchmark_spec(),
        )
        self.assertTrue(any("read outside its explicit route" in error for error in unexpected_errors))
        public = pkf_savings_eval.public_result(result)
        self.assertIn("cross_irredundancy_status", public)
        self.assertNotIn("cross_minimality_status", public)

    def test_run_class_keeps_one_pass_separate_from_replicated_results(self):
        self.assertEqual(pkf_savings_eval.REPORT_SCHEMA_VERSION, 10)
        self.assertEqual(pkf_savings_eval.run_class(1), "one_pass_preflight")
        self.assertEqual(pkf_savings_eval.run_class(2), "diagnostic")
        self.assertEqual(pkf_savings_eval.run_class(3), "replicated")

    def test_initialization_is_not_a_recurring_phase(self):
        schedule = pkf_savings_eval.build_schedule(
            1,
            (
                "simple_retrieval",
                "cross_capability_retrieval",
                "mutation",
                "post_mutation",
                "closeout",
            ),
            self.benchmark_spec(),
        )
        self.assertFalse(any(item["phase"] == "setup" for item in schedule))

    def test_score_mutation_checks_paths_without_coupling_to_test_title(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            source = repo / "src/state.ts"
            test = repo / "tests/state.test.ts"
            source.parent.mkdir(parents=True)
            test.parent.mkdir(parents=True)
            source.write_text("export const before = true;\n", encoding="utf-8")
            test.write_text("it('old title', () => {});\n", encoding="utf-8")
            self.initialize_repo(repo)
            source.write_text("export const after = true;\n", encoding="utf-8")
            test.write_text("it('renamed behavior description', () => {});\n", encoding="utf-8")

            with mock.patch.object(pkf_savings_eval, "run_focused_test", return_value=True):
                scored = pkf_savings_eval.score_mutation(
                    self.make_result(task_id="mutation-task", phase="mutation"),
                    repo,
                    "probe_only",
                    self.benchmark_spec().mutation,
                )

        self.assertTrue(scored.changed_expected_paths)
        self.assertTrue(scored.focused_test_passed)

    def test_public_result_omits_answer_and_markdown_discloses_limitations(self):
        result = self.make_result(answer={"private": "value"})
        public = pkf_savings_eval.public_result(result)
        source = self.make_result(
            arm="source_only",
            task_id="cross-read",
            phase="cross_capability_retrieval",
            usage=pkf_savings_eval.Usage(120, 90, 4),
        )
        probe = self.make_result(
            task_id="cross-read",
            phase="cross_capability_retrieval",
            usage=pkf_savings_eval.Usage(100, 80, 4),
        )
        candidate = self.make_result(
            arm="pkf",
            task_id="cross-read",
            phase="cross_capability_retrieval",
            usage=pkf_savings_eval.Usage(80, 70, 5),
            explicit_ai_read_path_count=1,
            retrieval_decision="activated",
        )
        metrics = pkf_savings_eval.aggregate_metrics((source, probe, candidate))
        self.assertNotIn("source_vs_probe", metrics["comparisons"]["cross-read"])
        self.assertIn(
            "source_vs_probe",
            metrics["diagnostic_comparisons"]["cross-read"],
        )
        report = {
            "benchmark": "generic-lifecycle",
            "phases_selected": ["cross_capability_retrieval"],
            "source_only_diagnostic": True,
            "run_class": "replicated",
            "replicated": True,
            "status": "completed",
            "quality_status": "passed",
            "performance": pkf_savings_eval.performance_advisories(metrics, 3, self.benchmark_spec()),
            "recorded_at": "2026-07-17T00:00:00+00:00",
            "target": {"commit": "abc"},
            "environment": {
                "model": "gpt-5.6-luna",
                "reasoning_effort": "high",
                "repetitions": 3,
                "scheduled_calls": 21,
                "peak_parallel_calls": 3,
            },
            "metrics": metrics,
            "runs": [
                pkf_savings_eval.public_result(source),
                pkf_savings_eval.public_result(probe),
                pkf_savings_eval.public_result(candidate),
            ],
            "errors": [],
        }

        markdown = pkf_savings_eval.render_markdown(
            report,
            raw_result_link=".agents/results/runtime-v3-1pass.json",
        )

        self.assertNotIn("answer", public)
        self.assertNotIn("private", json.dumps(public))
        self.assertIn("external benchmark specification", markdown)
        self.assertIn("- 3 repetition(s) describe", markdown)
        self.assertIn(
            "[`runtime-v3-1pass.json`](.agents/results/runtime-v3-1pass.json)",
            markdown,
        )
        self.assertIn("source_only", markdown)
        self.assertIn("### Source-only diagnostic deltas", markdown)
        self.assertIn("probe_only", markdown)
        self.assertIn("Explicit read targets", markdown)
        self.assertIn("Only paired tasks whose PKF arm actually activated", markdown)

    def test_one_pass_markdown_is_publishable_but_not_replicated(self):
        probe = self.make_result(arm="probe_only")
        candidate = self.make_result(arm="pkf")
        metrics = pkf_savings_eval.aggregate_metrics((probe, candidate))
        report = {
            "benchmark": "generic-lifecycle",
            "phases_selected": ["simple_retrieval"],
            "source_only_diagnostic": False,
            "run_class": "one_pass_preflight",
            "replicated": False,
            "status": "preliminary",
            "quality_status": "passed",
            "performance": pkf_savings_eval.performance_advisories(metrics, 1, self.benchmark_spec()),
            "recorded_at": "2026-07-19T00:00:00+00:00",
            "target": {"commit": "abc"},
            "environment": {
                "model": "gpt-5.6-luna",
                "reasoning_effort": "high",
                "repetitions": 1,
                "scheduled_calls": 7,
                "peak_parallel_calls": 2,
            },
            "metrics": metrics,
            "runs": [pkf_savings_eval.public_result(probe), pkf_savings_eval.public_result(candidate)],
            "errors": [],
        }

        markdown = pkf_savings_eval.render_markdown(report)

        self.assertIn("Publication class: **one-pass preflight**", markdown)
        self.assertIn("Replicated: **no**", markdown)
        self.assertIn("### Single-pass usage by task", markdown)
        self.assertIn("Evidence strength: **directional**", markdown)
        self.assertIn("cannot replace a fresh three-repetition result", markdown)
        self.assertNotIn("Source-only diagnostic deltas", markdown)

    def test_materialization_inventory_counts_complete_pending_and_unknown_leaves(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            knowledge = repo / ".ai" / "knowledge" / "notes"
            knowledge.mkdir(parents=True)
            (knowledge / "INDEX.md").write_text("index", encoding="utf-8")
            (knowledge / "api.md").write_text(
                "---\npkf:\n  materialization: complete\n---\n", encoding="utf-8"
            )
            (knowledge / "schema.md").write_text(
                "---\npkf:\n  materialization: pending\n---\n", encoding="utf-8"
            )
            (knowledge / "ui.md").write_text("# No state\n", encoding="utf-8")

            inventory = pkf_savings_eval.pkf_materialization_inventory(repo)

        self.assertEqual(inventory["materialized_leaf_count"], 1)
        self.assertEqual(inventory["pending_leaf_count"], 1)
        self.assertEqual(inventory["unknown_leaf_count"], 1)

    def test_artifact_store_keeps_private_evidence_out_of_public_report(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            repo = temp / "repo"
            repo.mkdir()
            (repo / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            (repo / ".ai" / "knowledge" / "notes").mkdir(parents=True)
            (repo / ".ai" / "knowledge" / "notes" / "behavior.md").write_text(
                "pkf:\n  materialization: complete\n", encoding="utf-8"
            )
            (repo / "AGENTS.md").write_text("instructions", encoding="utf-8")
            self.initialize_repo(repo)
            store = pkf_savings_eval.ArtifactStore(
                root=temp / "artifacts", run_id="test-run", mode="full"
            )
            result = self.make_result(answer={"secret": True})
            store.record_call(
                result=result,
                stdout='{"type":"turn.completed"}\n',
                stderr="",
                schema_path=None,
                repo=repo,
                workspace=temp,
            )
            store.snapshot_pkf("initialized", repo)

            manifest = json.loads((store.root / "manifest.json").read_text(encoding="utf-8"))

        paths = {item["path"] for item in manifest["artifacts"]}
        self.assertIn("private/calls/001-r1-probe_only-local-read/answer.json", paths)
        self.assertIn("private/pkf-snapshots/initialized/.ai/knowledge/notes/behavior.md", paths)
        self.assertFalse(any("auth.json" in path for path in paths))

    def test_public_artifact_mode_never_creates_private_subtree(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            store = pkf_savings_eval.ArtifactStore(
                root=Path(raw_temp), run_id="public-run", mode="public"
            )
            store.write_manifest("completed")

            self.assertTrue((store.root / "public").is_dir())
            self.assertFalse((store.root / "private").exists())

    def test_saved_mutation_state_excludes_git_and_workspace_links(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            repo = temp / "repo"
            repo.mkdir()
            (repo / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            (repo / ".git").mkdir()
            (repo / ".git" / "config").write_text("private\n", encoding="utf-8")
            dependency = temp / "dependency"
            dependency.mkdir()
            (repo / "vendor-cache").symlink_to(dependency, target_is_directory=True)
            store = pkf_savings_eval.ArtifactStore(
                root=temp / "artifacts", run_id="state-run", mode="full"
            )

            pkf_savings_eval.save_mutation_state(
                store,
                repo,
                repetition=1,
                arm="pkf",
                target={"commit": "a" * 40, "tree": "b" * 40},
                baseline_manifest={"runtime_sha256": "c" * 64},
                workspace_links=("vendor-cache",),
            )

            saved = store.private_dir / "states" / "r1" / "pkf" / "repository"
            self.assertFalse((saved / ".git").exists())
            self.assertFalse((saved / "vendor-cache").exists())
            state_manifest = json.loads((saved.parent / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(state_manifest["excluded_workspace_links"], ["vendor-cache"])

    def test_artifact_manifest_is_consistent_under_parallel_call_completion(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            repo = temp / "repo"
            repo.mkdir()
            store = pkf_savings_eval.ArtifactStore(
                root=temp / "artifacts", run_id="parallel-run", mode="public"
            )
            call_ids = [f"{index:03d}-call" for index in range(12, 0, -1)]

            def record(call_id):
                store.record_call(
                    result=self.make_result(task_id=call_id),
                    stdout="",
                    stderr="",
                    schema_path=None,
                    repo=repo,
                    workspace=temp,
                    call_id=call_id,
                )

            with concurrent.futures.ThreadPoolExecutor(max_workers=6) as executor:
                list(executor.map(record, call_ids))

            manifest = json.loads((store.root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(
                [item["call_id"] for item in manifest["calls"]],
                sorted(call_ids),
            )

    def test_quality_gate_requires_bypass_and_narrow_mapped_closeout(self):
        local = self.make_result(arm="pkf", retrieval_decision="bypassed")
        closeout = self.make_result(
            arm="pkf",
            task_id="closeout-task",
            phase="closeout",
            answer_correct=None,
            used_route_helper=True,
            initial_route_status="mapped",
            final_route_status="mapped",
            route_attempt_count=1,
            emitted_closeout=True,
            pkf_validation_passed=True,
            closeout_validation_call_count=1,
        )

        self.assertEqual(pkf_savings_eval.evaluation_errors((local, closeout), 2, self.benchmark_spec()), [])
        errors = pkf_savings_eval.evaluation_errors(
            (
                pkf_savings_eval.replace_result(local, retrieval_decision="activated"),
                pkf_savings_eval.replace_result(closeout, closeout_accessed_closeout=True),
            ),
            2,
            self.benchmark_spec(),
        )
        self.assertTrue(any("not classified as bypassed" in error for error in errors))
        self.assertTrue(any("loaded Token Atlas workflow" in error for error in errors))

        unmapped_errors = pkf_savings_eval.evaluation_errors(
            (
                local,
                pkf_savings_eval.replace_result(
                    closeout,
                    initial_route_status="unmapped",
                    final_route_status="partial",
                    routing_coverage_defect=True,
                    closeout_accessed_closeout=True,
                    closeout_fallback_search=True,
                ),
            ),
            2,
            self.benchmark_spec(),
        )
        self.assertTrue(any("routing-coverage defect" in error for error in unmapped_errors))
        self.assertFalse(any("mapped isolated closeout" in error for error in unmapped_errors))

    def test_mutation_trace_segments_at_first_valid_route_result(self):
        route_result = {
            "schema_version": 2,
            "status": "mapped",
            "affected_leaves": [{"path": ".ai/knowledge/notes/ui.md"}],
            "fallback_routes": [],
            "unmatched_paths": [],
            "routing_coverage_defect": False,
            "validation_scope": "affected",
        }
        output = "\n".join(
            (
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "command_execution", "command": "rg --files frontend/src/notes", "output": "frontend/src/notes/state.ts"},
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {
                            "type": "command_execution",
                            "command": "python -S .ai/tools/pkf_route.py --path . --changed-path frontend/src/notes/state.ts --format json",
                            "output": json.dumps(route_result),
                        },
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "command_execution", "command": "sed -n '1,80p' .ai/knowledge/notes/ui.md", "output": "leaf"},
                    }
                ),
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "command_execution", "command": "python -S .ai/tools/pkf_validate.py --path .ai --scope affected --changed-path frontend/src/notes/state.ts", "output": "{}"},
                    }
                ),
            )
        )

        events = pkf_savings_eval.completed_tool_events(output)
        attempts = pkf_savings_eval.parse_route_attempts(events)
        metrics, _ = pkf_savings_eval.segmented_trace(
            events,
            attempts,
            known_paths=(".ai/knowledge/notes/ui.md",),
            known_directories=("frontend/src/notes",),
        )

        self.assertEqual(attempts[0]["status"], "mapped")
        self.assertEqual(metrics["implementation"].tool_call_count, 1)
        self.assertTrue(metrics["implementation"].fallback_search)
        self.assertEqual(metrics["routing"].tool_call_count, 1)
        self.assertEqual(metrics["closeout"].tool_call_count, 2)
        self.assertFalse(metrics["closeout"].fallback_search)

    def test_runtime_contract_restores_changed_simulation_and_narrow_closeout(self):
        initialize = (ROOT / "skills/token-atlas/references/initialize.md").read_text(encoding="utf-8")
        closeout = (ROOT / "skills/token-atlas/references/closeout.md").read_text(encoding="utf-8")
        skill = (ROOT / "skills/token-atlas/SKILL.md").read_text(encoding="utf-8")

        self.assertIn("do not impose a fixed per-capability leaf", initialize)
        self.assertIn("`pkf.routes`", initialize)
        self.assertIn("Run `simulation=changed`", initialize)
        self.assertIn("Do not read the skill, this reference", closeout)
        self.assertIn("exactly one affected-slice advisory validation", closeout)
        self.assertIn("Do not trigger for routine mapped closeout", skill)


if __name__ == "__main__":
    unittest.main()
