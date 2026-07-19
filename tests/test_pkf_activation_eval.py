import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pkf_activation_eval.py"
SPEC = importlib.util.spec_from_file_location("pkf_activation_eval", SCRIPT)
activation_eval = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = activation_eval
SPEC.loader.exec_module(activation_eval)


class ActivationEvalTests(unittest.TestCase):
    def result(self, **overrides):
        values = {
            "variant": "v3",
            "prompt_kind": "read-only",
            "returncode": 0,
            "usage": activation_eval.Usage(1_000, 100, 50),
            "accessed_pkf": False,
            "accessed_skill": False,
            "accessed_closeout": False,
            "emitted_closeout": False,
            "changed_paths": (),
            "source_synchronized": False,
            "knowledge_synchronized": False,
            "event_tail": "",
            "stderr_tail": "",
        }
        values.update(overrides)
        return activation_eval.RunResult(**values)

    def test_parse_jsonl_extracts_usage_and_final_message(self):
        output = "\n".join(
            (
                json.dumps(
                    {
                        "type": "item.completed",
                        "item": {"type": "agent_message", "text": "PKF closeout: no-op"},
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

        usage, messages, normalized = activation_eval.parse_jsonl(output)

        self.assertEqual(usage, activation_eval.Usage(1_200, 200, 80))
        self.assertEqual(messages, ("PKF closeout: no-op",))
        self.assertIn("turn.completed", normalized)

    def test_cli_defaults_use_luna_high(self):
        args = activation_eval.parse_args(())

        self.assertEqual(args.model, "gpt-5.6-luna")
        self.assertEqual(args.model_reasoning_effort, "high")

    def test_prepare_v3_repo_applies_activation_overlay(self):
        with tempfile.TemporaryDirectory() as raw_workspace:
            repo = activation_eval.prepare_repo(Path(raw_workspace), "v3")

            source = (repo / "src/backend/routes/customers.ts").read_text(encoding="utf-8")
            knowledge = (repo / ".ai/knowledge/backend/api.md").read_text(encoding="utf-8")
            skill_exists = (repo / ".codex/skills/token-atlas/SKILL.md").is_file()

        self.assertIn('path: "/customers"', source)
        self.assertIn("Customer list path is `/customers`", knowledge)
        self.assertTrue(skill_exists)

    def test_evaluate_accepts_silent_read_only_and_synchronized_mutation(self):
        legacy = [
            self.result(
                variant="v1",
                usage=activation_eval.Usage(2_000, 0, 50),
                accessed_skill=True,
                emitted_closeout=True,
            )
        ]
        optimized = [self.result(usage=activation_eval.Usage(1_000, 0, 40))]
        mutation = self.result(
            prompt_kind="mutation",
            accessed_closeout=True,
            emitted_closeout=True,
            changed_paths=("src/backend/routes/customers.ts",),
            source_synchronized=True,
            knowledge_synchronized=True,
        )

        neutral = self.result(
            prompt_kind="knowledge-neutral-mutation",
            emitted_closeout=True,
            changed_paths=("src/backend/routes/customers.ts",),
        )

        errors, metrics = activation_eval.evaluate(legacy, optimized, neutral, mutation)

        self.assertEqual(errors, [])
        self.assertEqual(metrics["median_input_token_savings"], 1_000)
        self.assertEqual(metrics["knowledge_neutral_mutation_usage"]["input_tokens"], 1_000)

    def test_evaluate_rejects_read_only_activation(self):
        legacy = [
            self.result(
                variant="v1",
                usage=activation_eval.Usage(2_000, 0, 50),
                accessed_skill=True,
                emitted_closeout=True,
            )
        ]
        optimized = [
            self.result(
                usage=activation_eval.Usage(1_000, 0, 40),
                accessed_skill=True,
                emitted_closeout=True,
            )
        ]
        mutation = self.result(
            prompt_kind="mutation",
            accessed_closeout=True,
            emitted_closeout=True,
            source_synchronized=True,
            knowledge_synchronized=True,
        )

        neutral = self.result(
            prompt_kind="knowledge-neutral-mutation",
            emitted_closeout=True,
            changed_paths=("src/backend/routes/customers.ts",),
        )

        errors, _ = activation_eval.evaluate(legacy, optimized, neutral, mutation)

        self.assertTrue(any("read-only" in error for error in errors))

    def test_evaluate_rejects_local_read_only_pkf_access(self):
        legacy = [
            self.result(
                variant="v1",
                usage=activation_eval.Usage(2_000, 0, 50),
                accessed_skill=True,
                emitted_closeout=True,
            )
        ]
        optimized = [self.result(accessed_pkf=True)]
        mutation = self.result(
            prompt_kind="mutation",
            accessed_closeout=True,
            emitted_closeout=True,
            source_synchronized=True,
            knowledge_synchronized=True,
        )

        neutral = self.result(
            prompt_kind="knowledge-neutral-mutation",
            emitted_closeout=True,
            changed_paths=("src/backend/routes/customers.ts",),
        )

        errors, _ = activation_eval.evaluate(legacy, optimized, neutral, mutation)

        self.assertTrue(any("local read-only" in error for error in errors))

    def test_evaluate_rejects_token_atlas_on_knowledge_neutral_mutation(self):
        legacy = [
            self.result(
                variant="v1",
                usage=activation_eval.Usage(2_000, 0, 50),
                accessed_skill=True,
                emitted_closeout=True,
            )
        ]
        optimized = [self.result(usage=activation_eval.Usage(1_000, 0, 40))]
        neutral = self.result(
            prompt_kind="knowledge-neutral-mutation",
            accessed_skill=True,
            emitted_closeout=True,
            changed_paths=("src/backend/routes/customers.ts",),
        )
        mutation = self.result(
            prompt_kind="mutation",
            accessed_closeout=True,
            emitted_closeout=True,
            source_synchronized=True,
            knowledge_synchronized=True,
        )

        errors, _ = activation_eval.evaluate(legacy, optimized, neutral, mutation)

        self.assertTrue(any("knowledge-neutral" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
