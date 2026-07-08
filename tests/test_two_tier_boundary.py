import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


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
            "references/maintenance.md",
            "references/optimize.md",
            "references/simulate.md",
            "references/tooling.md",
            "references/validation.md",
        }

        self.assertEqual(actual, expected)

    def test_public_package_has_no_internal_surface_tokens(self):
        public = ROOT / "skills" / "token-atlas"
        text = "\n".join(path.read_text(encoding="utf-8").lower() for path in public.rglob("*") if path.is_file())

        for token in ("codex", "bench", "benchmark", "gpt-5", "pkf.ps1"):
            self.assertNotIn(token, text)

    def test_internal_tier_carries_benchmark_surface_and_shared_policy(self):
        internal = ROOT / ".agents" / "skills" / "token-atlas"
        files = {path.relative_to(internal).as_posix() for path in internal.rglob("*") if path.is_file()}

        self.assertIn("references/benchmark.md", files)
        self.assertTrue(any(path.startswith("benchmarks/fixtures/") for path in files))
        self.assertIn("agents/openai.yaml", files)
        self.assertIn("allow_implicit_invocation: false", (internal / "agents" / "openai.yaml").read_text(encoding="utf-8"))

        front_matter = (internal / "SKILL.md").read_text(encoding="utf-8").split("---", 2)[1]
        self.assertIn("name: token-atlas", front_matter)
        self.assertIn("description:", front_matter)
        self.assertNotIn("interface:", front_matter)
        self.assertNotIn("policy:", front_matter)


if __name__ == "__main__":
    unittest.main()
