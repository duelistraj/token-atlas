import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
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
            "arm": "no_pkf",
            "task_id": "boards_add_task",
            "returncode": 0,
            "duration_ms": 100,
            "usage": pkf_savings_eval.Usage(1_000, 200, 50),
            "answer": {},
            "answer_correct": True,
            "accessed_skill": False,
            "accessed_closeout": False,
            "emitted_closeout": False,
            "fallback_search": False,
            "accessed_path_count": 1,
            "accessed_ai_path_count": 0,
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

    def test_schedule_has_nine_calls_per_repetition_and_counterbalances(self):
        schedule = pkf_savings_eval.build_schedule(3)

        self.assertEqual(len(schedule), 27)
        first_boards = [
            item["arm"]
            for item in schedule
            if item["repetition"] == 1 and item["task_id"] == "boards_add_task"
        ]
        second_boards = [
            item["arm"]
            for item in schedule
            if item["repetition"] == 2 and item["task_id"] == "boards_add_task"
        ]
        self.assertEqual(first_boards, ["no_pkf", "pkf"])
        self.assertEqual(second_boards, ["pkf", "no_pkf"])

    def test_cli_defaults_pin_real_target_model_and_reasoning(self):
        args = pkf_savings_eval.parse_args(("--target-repo", "/tmp/target"))

        self.assertEqual(args.target_commit, pkf_savings_eval.DEFAULT_TARGET_COMMIT)
        self.assertEqual(args.model, "gpt-5.6-luna")
        self.assertEqual(args.model_reasoning_effort, "high")
        self.assertEqual(args.repetitions, 3)

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

            self.assertFalse((arms["no_pkf"] / ".ai").exists())
            self.assertFalse(
                (arms["no_pkf"] / ".codex" / "skills" / "token-atlas").exists()
            )
            self.assertTrue((arms["pkf"] / ".codex" / "skills" / "token-atlas" / "SKILL.md").is_file())
            self.assertIn("Prefer `rg`", (arms["no_pkf"] / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertEqual(
                subprocess.run(
                    ("git", "status", "--porcelain"),
                    cwd=arms["no_pkf"],
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
            self.make_result(arm="no_pkf", usage=pkf_savings_eval.Usage(2_000, 0, 20)),
            self.make_result(arm="pkf", usage=pkf_savings_eval.Usage(1_500, 0, 20)),
            self.make_result(
                arm="no_pkf",
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

        self.assertEqual(metrics["median_paired_read_only_savings"]["input_tokens"], 500)
        self.assertEqual(metrics["break_even_read_only_tasks"]["input_tokens"], 3)

    def test_public_result_omits_answer_and_markdown_discloses_limitations(self):
        result = self.make_result(answer={"private": "value"})
        public = pkf_savings_eval.public_result(result)
        report = {
            "status": "completed",
            "recorded_at": "2026-07-17T00:00:00+00:00",
            "target": {"commit": "abc"},
            "environment": {
                "model": "gpt-5.6-luna",
                "reasoning_effort": "high",
                "repetitions": 3,
                "scheduled_calls": 27,
            },
            "metrics": {
                "by_task": {},
                "lifecycle_by_repetition": [
                    {
                        "repetition": 1,
                        "no_pkf": {
                            "input_tokens": 100,
                            "cached_input_tokens": 80,
                            "non_cached_input_tokens": 20,
                            "output_tokens": 4,
                        },
                        "pkf": {
                            "input_tokens": 120,
                            "cached_input_tokens": 90,
                            "non_cached_input_tokens": 30,
                            "output_tokens": 5,
                        },
                    }
                ],
                "median_paired_read_only_savings": {
                    "input_tokens": 10,
                    "non_cached_input_tokens": 2,
                },
                "break_even_read_only_tasks": {
                    "input_tokens": 4,
                    "non_cached_input_tokens": 5,
                },
            },
            "errors": [],
        }

        report["metrics"]["by_task"] = {
            "note_task_links": {
                "no_pkf": {
                    "input_tokens": 100,
                    "cached_input_tokens": 80,
                    "non_cached_input_tokens": 20,
                    "output_tokens": 4,
                    "correctness_rate": 1.0,
                    "duration_ms": 100,
                },
                "pkf": {
                    "input_tokens": 80,
                    "cached_input_tokens": 70,
                    "non_cached_input_tokens": 10,
                    "output_tokens": 5,
                    "correctness_rate": 1.0,
                    "duration_ms": 110,
                },
            },
            "favorite_visibility_mutation": {
                "no_pkf": {
                    "input_tokens": 100,
                    "cached_input_tokens": 80,
                    "non_cached_input_tokens": 20,
                    "output_tokens": 4,
                    "correctness_rate": None,
                    "duration_ms": 100,
                },
                "pkf": {
                    "input_tokens": 120,
                    "cached_input_tokens": 90,
                    "non_cached_input_tokens": 30,
                    "output_tokens": 5,
                    "correctness_rate": None,
                    "duration_ms": 110,
                },
            },
        }

        markdown = pkf_savings_eval.render_markdown(report)

        self.assertNotIn("answer", public)
        self.assertNotIn("private", json.dumps(public))
        self.assertIn("private when measured", markdown)
        self.assertIn("not pricing estimates", markdown)


if __name__ == "__main__":
    unittest.main()
