import importlib.util
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
            "task_id": "boards_add_task",
            "phase": "retrieval",
            "returncode": 0,
            "duration_ms": 100,
            "usage": pkf_savings_eval.Usage(1_000, 200, 50),
            "answer": {},
            "answer_correct": True,
            "accessed_skill": False,
            "accessed_closeout": False,
            "emitted_closeout": False,
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
            "changed_path_count": 0,
            "changed_expected_paths": None,
            "focused_test_passed": None,
            "pkf_validation_passed": None,
            "error": "",
        }
        values.update(overrides)
        return pkf_savings_eval.CodexResult(**values)

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

    def test_schedule_splits_suites_and_counterbalances_arms(self):
        lifecycle = pkf_savings_eval.build_schedule(3, "lifecycle")
        retrieval = pkf_savings_eval.build_schedule(3, "retrieval")
        closeout = pkf_savings_eval.build_schedule(3, "closeout")
        all_tasks = pkf_savings_eval.build_schedule(3, "all")

        self.assertEqual(len(lifecycle), 15)
        self.assertEqual(len(retrieval), 21)
        self.assertEqual(len(closeout), 9)
        self.assertEqual(len(all_tasks), 39)
        first_boards = [
            item["arm"]
            for item in retrieval
            if item["repetition"] == 1 and item["task_id"] == "boards_add_task"
        ]
        second_boards = [
            item["arm"]
            for item in retrieval
            if item["repetition"] == 2 and item["task_id"] == "boards_add_task"
        ]
        self.assertEqual(first_boards, ["source_only", "probe_only", "pkf"])
        self.assertEqual(second_boards, ["probe_only", "pkf", "source_only"])

    def test_cli_defaults_pin_real_target_model_and_reasoning(self):
        args = pkf_savings_eval.parse_args(("--target-repo", "/tmp/target"))

        self.assertEqual(args.target_commit, pkf_savings_eval.DEFAULT_TARGET_COMMIT)
        self.assertEqual(args.model, "gpt-5.6-luna")
        self.assertEqual(args.model_reasoning_effort, "high")
        self.assertEqual(args.repetitions, 3)
        self.assertEqual(args.suite, "lifecycle")

    def test_parse_jsonl_extracts_usage_and_structured_answer(self):
        answer = {
            "task_id": "boards_add_task",
            "answers": {"targets_first_non_final_by_position": True},
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
            (target / "AGENTS.md").write_text("PKF instructions", encoding="utf-8")
            (target / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            self.initialize_repo(target)
            commit = subprocess.run(
                ("git", "rev-parse", "HEAD"),
                cwd=target,
                check=True,
                capture_output=True,
                text=True,
            ).stdout.strip()

            workspace = temp / "workspace"
            workspace.mkdir()
            arms = pkf_savings_eval.prepare_arms(
                workspace,
                target_repo=target,
                target_commit=commit,
            )

            self.assertFalse((arms["source_only"] / ".ai").exists())
            self.assertFalse(
                (arms["source_only"] / ".codex" / "skills" / "token-atlas").exists()
            )
            self.assertFalse((arms["probe_only"] / ".ai").exists())
            self.assertTrue((arms["pkf"] / ".codex" / "skills" / "token-atlas" / "SKILL.md").is_file())
            self.assertIn("Prefer `rg`", (arms["source_only"] / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertIn("cheap local probe", (arms["probe_only"] / "AGENTS.md").read_text(encoding="utf-8"))
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

    def test_aggregate_reports_finite_break_even_for_positive_savings(self):
        results = [
            self.make_result(
                arm="pkf",
                task_id="initialize",
                usage=pkf_savings_eval.Usage(1_000, 0, 10),
                answer_correct=None,
                pkf_validation_passed=True,
            ),
            self.make_result(arm="probe_only", usage=pkf_savings_eval.Usage(2_000, 0, 20)),
            self.make_result(arm="pkf", usage=pkf_savings_eval.Usage(1_500, 0, 20)),
            self.make_result(
                arm="probe_only",
                task_id="favorite_visibility_mutation",
                usage=pkf_savings_eval.Usage(1_000, 0, 20),
                answer_correct=None,
            ),
            self.make_result(
                arm="pkf",
                task_id="favorite_visibility_mutation",
                usage=pkf_savings_eval.Usage(1_500, 0, 20),
                answer_correct=None,
            ),
        ]

        metrics = pkf_savings_eval.aggregate_metrics(results)

        self.assertEqual(metrics["median_paired_pkf_read_only_savings"]["input_tokens"], 500)
        self.assertEqual(metrics["break_even_read_only_tasks"]["input_tokens"], 3)

    def test_one_repetition_is_always_preliminary(self):
        metrics = pkf_savings_eval.aggregate_metrics(
            (
                self.make_result(arm="probe_only"),
                self.make_result(arm="pkf", explicit_ai_read_path_count=0),
            )
        )

        performance = pkf_savings_eval.performance_advisories(metrics, 1)

        self.assertEqual(performance, {"status": "preliminary", "checks": []})

    def test_score_mutation_checks_paths_without_coupling_to_test_title(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            source = repo / "frontend/src/notes/noteSectionState.ts"
            test = repo / "frontend/src/notes/noteSectionState.test.ts"
            source.parent.mkdir(parents=True)
            source.write_text("export const before = true;\n", encoding="utf-8")
            test.write_text("it('old title', () => {});\n", encoding="utf-8")
            self.initialize_repo(repo)
            source.write_text("export const after = true;\n", encoding="utf-8")
            test.write_text("it('renamed behavior description', () => {});\n", encoding="utf-8")

            with mock.patch.object(pkf_savings_eval, "run_focused_test", return_value=True):
                scored = pkf_savings_eval.score_mutation(
                    self.make_result(task_id="favorite_visibility_mutation"),
                    repo,
                    "probe_only",
                )

        self.assertTrue(scored.changed_expected_paths)
        self.assertTrue(scored.focused_test_passed)

    def test_public_result_omits_answer_and_markdown_discloses_limitations(self):
        result = self.make_result(answer={"private": "value"})
        public = pkf_savings_eval.public_result(result)
        probe = self.make_result(task_id="note_task_links", usage=pkf_savings_eval.Usage(100, 80, 4))
        candidate = self.make_result(
            arm="pkf",
            task_id="note_task_links",
            usage=pkf_savings_eval.Usage(80, 70, 5),
            explicit_ai_read_path_count=1,
        )
        metrics = pkf_savings_eval.aggregate_metrics((probe, candidate))
        report = {
            "suite": "retrieval",
            "status": "completed",
            "quality_status": "passed",
            "performance": pkf_savings_eval.performance_advisories(metrics, 3),
            "recorded_at": "2026-07-17T00:00:00+00:00",
            "target": {"commit": "abc"},
            "environment": {
                "model": "gpt-5.6-luna",
                "reasoning_effort": "high",
                "repetitions": 3,
                "scheduled_calls": 21,
            },
            "metrics": metrics,
            "runs": [pkf_savings_eval.public_result(probe), pkf_savings_eval.public_result(candidate)],
            "errors": [],
        }

        markdown = pkf_savings_eval.render_markdown(
            report,
            raw_result_link=".agents/results/runtime-v3-1pass.json",
        )

        self.assertNotIn("answer", public)
        self.assertNotIn("private", json.dumps(public))
        self.assertIn("private when measured", markdown)
        self.assertIn("not pricing estimates", markdown)
        self.assertIn("- 3 repetition(s) describe", markdown)
        self.assertIn(
            "[`runtime-v3-1pass.json`](.agents/results/runtime-v3-1pass.json)",
            markdown,
        )
        self.assertIn("source_only", markdown)
        self.assertIn("probe_only", markdown)
        self.assertIn("Explicit read targets", markdown)


if __name__ == "__main__":
    unittest.main()
