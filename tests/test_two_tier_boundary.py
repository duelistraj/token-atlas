import subprocess
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SCRIPT_NAMES = (
    "pkf_contract.py",
    "pkf_lib.py",
    "pkf_tokens.py",
    "pkf_validate.py",
)


class TwoTierBoundaryTests(unittest.TestCase):
    def test_public_package_has_activation_light_shape(self):
        public = ROOT / "skills" / "token-atlas"
        actual = {path.relative_to(public).as_posix() for path in public.rglob("*") if path.is_file()}
        expected = {
            "SKILL.md",
            "agents/openai.yaml",
            "references/export.md",
            "references/extract.md",
            "references/initialize.md",
            "references/closeout.md",
            "references/maintenance.md",
            "references/optimize.md",
            "references/simulate.md",
            "references/tooling.md",
            "references/validation.md",
            "scripts/pkf_contract.py",
            "scripts/pkf_lib.py",
            "scripts/pkf_route.py",
            "scripts/pkf_scaffold.py",
            "scripts/pkf_tokens.py",
            "scripts/pkf_validate.py",
            "templates/bootstrap.md",
            "templates/protocols.md",
        }

        self.assertEqual(actual, expected)

    def test_public_package_has_no_internal_surface_tokens(self):
        public = ROOT / "skills" / "token-atlas"
        text = "\n".join(path.read_text(encoding="utf-8").lower() for path in public.rglob("*") if path.is_file())

        for token in ("codex", "bench", "benchmark", "gpt-5", "pkf.ps1"):
            self.assertNotIn(token, text)

    def test_public_validator_modules_match_canonical_scripts(self):
        public = ROOT / "skills" / "token-atlas" / "scripts"
        canonical = ROOT / "scripts"

        for name in PUBLIC_SCRIPT_NAMES:
            self.assertEqual(
                (public / name).read_bytes(),
                (canonical / name).read_bytes(),
                name,
            )

    def test_public_validator_runs_without_site_packages(self):
        validator = ROOT / "skills" / "token-atlas" / "scripts" / "pkf_validate.py"
        fixture = ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures" / "schema-change" / "repo"

        completed = subprocess.run(
            [sys.executable, "-S", str(validator), "--path", str(fixture), "--strictness", "ci", "--format", "json"],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn('"status": "passed"', completed.stdout)

    def test_internal_tier_carries_benchmark_surface_and_shared_policy(self):
        internal = ROOT / ".agents" / "skills" / "token-atlas"
        files = {path.relative_to(internal).as_posix() for path in internal.rglob("*") if path.is_file()}

        self.assertIn("references/benchmark.md", files)
        self.assertTrue(any(path.startswith("benchmarks/fixtures/") for path in files))
        self.assertIn("agents/openai.yaml", files)
        self.assertIn("allow_implicit_invocation: true", (internal / "agents" / "openai.yaml").read_text(encoding="utf-8"))

        front_matter = (internal / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
        self.assertIn("name: token-atlas", front_matter)
        self.assertIn("description:", front_matter)
        self.assertNotIn("interface:", front_matter)
        self.assertNotIn("policy:", front_matter)


if __name__ == "__main__":
    unittest.main()
