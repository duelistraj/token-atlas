import importlib.util
import subprocess
import sys
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pkf_bench.py"
spec = importlib.util.spec_from_file_location("pkf_bench", SCRIPT)
pkf_bench = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(pkf_bench)


class PkfBenchTests(unittest.TestCase):
    def test_parse_args_pins_model_defaults(self):
        with mock.patch.object(sys, "argv", ["pkf_bench.py"]):
            args = pkf_bench.parse_args()

        self.assertEqual(args.model, pkf_bench.DEFAULT_MODEL)
        self.assertEqual(args.model_reasoning_effort, pkf_bench.DEFAULT_MODEL_REASONING_EFFORT)
        self.assertEqual(args.model_source, "runner-default")
        self.assertEqual(args.model_reasoning_effort_source, "runner-default")

    def test_parse_manifest_subset(self):
        manifest = pkf_bench.parse_manifest(
            ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures" / "missing-runtime" / "fixture.yaml"
        )

        self.assertEqual(manifest["name"], "missing-runtime")
        self.assertIn("quick", manifest["suites"])
        self.assertEqual(manifest["source_shape"]["pkf_runtime"], "missing")
        self.assertIn(".ai/PKF.md", manifest["expected_required_docs"]["generated"])

    def test_local_quick_suite_passes(self):
        args = Namespace(mode="local", keep_workspaces=False)
        manifests = pkf_bench.load_selected_manifests(pkf_bench.DEFAULT_FIXTURES, "quick")
        reports = [pkf_bench.run_fixture(fixture_dir, manifest, args) for fixture_dir, manifest in manifests]
        aggregate = pkf_bench.aggregate_reports(reports)

        self.assertEqual(aggregate["total"], 2)
        self.assertEqual(aggregate["failed"], 0)
        self.assertGreater(aggregate["checks"]["passed"], 0)

    def test_codex_report_scoring_uses_expected_errors(self):
        manifest = pkf_bench.parse_manifest(
            ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures" / "deleted-evidence" / "fixture.yaml"
        )
        result = pkf_bench.empty_mode_result("codex")
        codex_report = {
            "status": "failed",
            "selected_modules": ["backend"],
            "required_docs": pkf_bench.flatten_expected_docs(manifest["expected_required_docs"]),
            "warnings": [],
            "errors": [
                "Stale reference to deleted evidence path src/backend/routes/legacyOrders.ts.",
                "Removed route getLegacyOrderRoute still cited as current.",
            ],
            "forbidden_loads": [],
            "token_impact": {"reported": True},
            "exit_behavior": {"actual": 1},
            "evidence": ["validation found stale evidence"],
        }

        pkf_bench.score_codex_report(manifest, codex_report, result)
        pkf_bench.finish_mode_status(result)

        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["checks"]["passed"], result["checks"]["total"])

    def test_combine_statuses_treats_timeout_as_failure(self):
        self.assertEqual(pkf_bench.combine_statuses(["passed", "timeout"]), "failed")
        self.assertEqual(pkf_bench.combine_statuses(["passed", "warning"]), "warning")
        self.assertEqual(pkf_bench.combine_statuses(["passed"]), "passed")

    def test_codex_timeout_result(self):
        fixture_dir = ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures" / "simple-api"
        manifest = pkf_bench.parse_manifest(fixture_dir / "fixture.yaml")
        args = Namespace(keep_workspaces=False, timeout_seconds=1)
        real_run = subprocess.run
        captured = {}

        def fake_run(command, *args, **kwargs):
            if command and command[0] == "codex":
                captured["command"] = command
                raise subprocess.TimeoutExpired(command, timeout=1)
            return real_run(command, *args, **kwargs)

        with mock.patch.object(pkf_bench.subprocess, "run", side_effect=fake_run):
            result = pkf_bench.run_codex_mode(fixture_dir, manifest, args)

        self.assertEqual(result["status"], "timeout")
        self.assertTrue(result["errors"])
        self.assertIn("--model", captured["command"])
        self.assertIn(pkf_bench.DEFAULT_MODEL, captured["command"])
        self.assertIn(f'model_reasoning_effort="{pkf_bench.DEFAULT_MODEL_REASONING_EFFORT}"', captured["command"])


if __name__ == "__main__":
    unittest.main()
