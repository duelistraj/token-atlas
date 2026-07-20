import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from argparse import Namespace
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "pkf_baseline.py"
SPEC = importlib.util.spec_from_file_location("pkf_baseline", SCRIPT)
pkf_baseline = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = pkf_baseline
SPEC.loader.exec_module(pkf_baseline)


class PkfBaselineTests(unittest.TestCase):
    def initialize_repo(self, root: Path) -> str:
        subprocess.run(("git", "init", "--quiet"), cwd=root, check=True)
        subprocess.run(("git", "config", "user.name", "Baseline Test"), cwd=root, check=True)
        subprocess.run(("git", "config", "user.email", "baseline@example.invalid"), cwd=root, check=True)
        subprocess.run(("git", "add", "."), cwd=root, check=True)
        subprocess.run(("git", "commit", "--quiet", "-m", "fixture"), cwd=root, check=True)
        return subprocess.run(
            ("git", "rev-parse", "HEAD"), cwd=root, check=True, capture_output=True, text=True
        ).stdout.strip()

    def test_prepare_only_cli_does_not_require_model_configuration(self):
        args = pkf_baseline.parse_args(
            ("create", "--target-repo", "/tmp/target", "--prepare-only")
        )

        self.assertTrue(args.prepare_only)
        self.assertIsNone(args.model)
        self.assertIsNone(args.model_reasoning_effort)

    def test_baseline_manifest_schema_is_explicit(self):
        schema = json.loads(
            (ROOT / "benchmarks" / "schemas" / "pkf-baseline-manifest.schema.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(schema["properties"]["schema_version"]["const"], 1)
        self.assertIn("completeness_review", schema["properties"]["generation"]["required"])
        self.assertEqual(
            schema["properties"]["semantic_acceptance"]["properties"]["task_relevance_proven"]["const"],
            False,
        )

    def test_filtered_export_never_extracts_existing_pkf_or_installed_skill(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            source = temp / "source"
            source.mkdir()
            (source / "src").mkdir()
            (source / "src" / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
            (source / ".ai").mkdir()
            (source / ".ai" / "POISON.md").write_text("must not be read\n", encoding="utf-8")
            (source / ".pkf-init.json").write_text('{"poison": true}\n', encoding="utf-8")
            (source / ".token-atlas").mkdir()
            (source / ".token-atlas" / "draft.txt").write_text("old draft\n", encoding="utf-8")
            installed = source / ".codex" / "skills" / "token-atlas"
            installed.mkdir(parents=True)
            (installed / "SKILL.md").write_text("old skill\n", encoding="utf-8")
            (source / "AGENTS.md").write_text(
                "Keep this.\n<!-- token-atlas:bootstrap:start -->\nold PKF\n<!-- token-atlas:bootstrap:end -->\n",
                encoding="utf-8",
            )
            commit = self.initialize_repo(source)
            destination = temp / "exported"

            excluded = pkf_baseline.export_filtered(source, commit, destination)

            self.assertFalse((destination / ".ai").exists())
            self.assertFalse((destination / ".pkf-init.json").exists())
            self.assertFalse((destination / ".token-atlas").exists())
            self.assertFalse((destination / ".codex" / "skills" / "token-atlas").exists())
            self.assertTrue((destination / "src" / "app.py").is_file())
            self.assertIn("Keep this.", (destination / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertNotIn("old PKF", (destination / "AGENTS.md").read_text(encoding="utf-8"))
            self.assertTrue(any(path.startswith(".ai/") for path in excluded))

    def test_prepare_only_creates_persistent_resumable_draft(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            source = temp / "source"
            source.mkdir()
            (source / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            commit = self.initialize_repo(source)
            identity = pkf_baseline.target_identity(source, commit)
            final = temp / "baselines" / identity["tree"]
            args = Namespace(
                target_repo=source,
                target_commit=commit,
                model="model",
                model_reasoning_effort="high",
                timeout_seconds=10,
                executor="codex",
                prepare_only=True,
            )

            first = pkf_baseline.create_baseline(args, identity, final)
            second = pkf_baseline.create_baseline(args, identity, final)

            self.assertEqual(first["status"], "prepared")
            self.assertEqual(second["status"], "prepared")
            draft = Path(first["draft"])
            self.assertTrue((draft / "repository" / "source.py").is_file())
            self.assertTrue((draft / "draft.json").is_file())

    def test_unmanaged_pkf_bootstrap_fails_clean_export(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            source = temp / "source"
            source.mkdir()
            (source / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            (source / "AGENTS.md").write_text("Always read .ai/PKF.md.\n", encoding="utf-8")
            commit = self.initialize_repo(source)

            with self.assertRaises(pkf_baseline.BaselineError):
                pkf_baseline.export_filtered(source, commit, temp / "exported")

    def test_source_digest_ignores_only_the_managed_bootstrap(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            repo = Path(raw_temp)
            (repo / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            agents = repo / "AGENTS.md"
            agents.write_text("Preserve this.\n", encoding="utf-8")
            original = pkf_baseline.source_digest(repo)

            agents.write_text(
                "Preserve this.\n\n"
                "<!-- token-atlas:bootstrap:start -->\ngenerated\n"
                "<!-- token-atlas:bootstrap:end -->\n",
                encoding="utf-8",
            )
            self.assertEqual(pkf_baseline.source_digest(repo), original)

            agents.write_text(
                "Changed instruction.\n\n"
                "<!-- token-atlas:bootstrap:start -->\ngenerated\n"
                "<!-- token-atlas:bootstrap:end -->\n",
                encoding="utf-8",
            )
            self.assertNotEqual(pkf_baseline.source_digest(repo), original)

    def test_sealed_baseline_is_identity_and_digest_checked(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            root = Path(raw_temp)
            runtime = root / "runtime"
            (runtime / ".ai" / "knowledge" / "capability").mkdir(parents=True)
            (runtime / ".ai" / "PKF.md").write_text("runtime\n", encoding="utf-8")
            leaf = runtime / ".ai" / "knowledge" / "capability" / "api.md"
            leaf.write_text("complete leaf\n", encoding="utf-8")
            identity = {"repository_id": "repo", "commit": "a" * 40, "tree": "b" * 40}
            manifest = {
                "schema_version": 1,
                "target": identity,
                "runtime_sha256": pkf_baseline.runtime_digest(runtime),
                "validation_status": "passed",
                "generation": {
                    "initialization": {"returncode": 0},
                    "completeness_review": {"returncode": 0},
                },
                "semantic_acceptance": {"status": "model_review_completed"},
                "runtime_inventory": {
                    "leaf_paths": [".ai/knowledge/capability/api.md"],
                    "leaf_count": 1,
                },
            }
            (root / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")

            self.assertEqual(pkf_baseline.validate_sealed(root, identity), manifest)
            (runtime / ".ai" / "PKF.md").write_text("changed\n", encoding="utf-8")
            with self.assertRaises(pkf_baseline.BaselineError):
                pkf_baseline.validate_sealed(root, identity)

    def test_failed_review_resumes_without_rerunning_initialization(self):
        with tempfile.TemporaryDirectory() as raw_temp:
            temp = Path(raw_temp)
            source = temp / "source"
            source.mkdir()
            (source / "source.py").write_text("VALUE = 1\n", encoding="utf-8")
            commit = self.initialize_repo(source)
            identity = pkf_baseline.target_identity(source, commit)
            final = temp / "baselines" / identity["tree"]
            args = Namespace(
                target_repo=source,
                target_commit=commit,
                model="model",
                model_reasoning_effort="high",
                timeout_seconds=10,
                executor="codex",
                prepare_only=True,
            )
            prepared = pkf_baseline.create_baseline(args, identity, final)
            repository = Path(prepared["repository"])
            args.prepare_only = False

            def initialize(_args, repo, _trace):
                (repo / ".ai" / "knowledge" / "capability").mkdir(parents=True)
                (repo / ".ai" / "PKF.md").write_text("runtime\n", encoding="utf-8")
                (repo / ".ai" / "knowledge" / "capability" / "INDEX.md").write_text(
                    "index\n", encoding="utf-8"
                )
                (repo / ".ai" / "knowledge" / "capability" / "api.md").write_text(
                    "leaf\n", encoding="utf-8"
                )
                return {"returncode": 0, "role": "initialization"}

            review_results = (
                {"returncode": 1, "role": "completeness_review"},
                {"returncode": 0, "role": "completeness_review"},
            )
            with (
                mock.patch.object(pkf_baseline, "run_generator", side_effect=initialize) as generator,
                mock.patch.object(
                    pkf_baseline, "run_completeness_review", side_effect=review_results
                ) as reviewer,
                mock.patch.object(pkf_baseline, "validate_runtime", return_value={"status": "passed"}),
            ):
                with self.assertRaises(pkf_baseline.BaselineError):
                    pkf_baseline.create_baseline(args, identity, final)
                result = pkf_baseline.create_baseline(args, identity, final)

            self.assertEqual(result["status"], "created")
            self.assertEqual(generator.call_count, 1)
            self.assertEqual(reviewer.call_count, 2)
            self.assertTrue((final / "runtime" / ".ai" / "PKF.md").is_file())
            self.assertTrue((repository / ".ai" / "PKF.md").is_file())


if __name__ == "__main__":
    unittest.main()
