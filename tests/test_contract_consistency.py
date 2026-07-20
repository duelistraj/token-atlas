import re
import unittest
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pkf_contract import (
    CLOSEOUT_DEFAULT,
    CLOSEOUT_MODES,
    CLOSEOUT_PROTOCOL_HEADING,
    ESTIMATOR_FORMULA,
    LEAF_MATERIALIZATION_FIELD,
    LEAF_MATERIALIZATION_MODES,
    LEAF_SOURCE_SYMBOLS_FIELD,
    LEGACY_CLOSEOUT_PHRASES,
    REQUIRED_FRONT_MATTER,
    RETRIEVAL_BUDGET,
    RETRIEVAL_DEFAULT,
    RETRIEVAL_MODE_FIELD,
    RETRIEVAL_MODES,
    RUNTIME_VERSION,
    RUNTIME_VERSION_FIELD,
    TOKEN_THRESHOLDS,
)


class ContractConsistencyTests(unittest.TestCase):
    def test_contract_values_appear_in_docs_and_fixtures(self):
        corpus = self.read_corpus()

        for threshold in TOKEN_THRESHOLDS.values():
            self.assertIn(f"{threshold:,}", corpus)
        self.assertIn(ESTIMATOR_FORMULA, corpus)
        self.assertIn(LEAF_SOURCE_SYMBOLS_FIELD, corpus)
        self.assertIn(CLOSEOUT_PROTOCOL_HEADING, corpus)
        self.assertIn(f"closeout: {CLOSEOUT_DEFAULT}", corpus)
        self.assertIn(f"{RUNTIME_VERSION_FIELD}: {RUNTIME_VERSION}", corpus)
        self.assertIn(f"{RETRIEVAL_MODE_FIELD}: {RETRIEVAL_DEFAULT}", corpus)
        self.assertIn(LEAF_MATERIALIZATION_FIELD, corpus)
        self.assertEqual(CLOSEOUT_MODES, ("adaptive", "off"))
        self.assertEqual(RETRIEVAL_MODES, ("adaptive", "mandatory"))
        self.assertEqual(LEAF_MATERIALIZATION_MODES, ("complete", "pending"))
        self.assertEqual(LEGACY_CLOSEOUT_PHRASES, ("every user turn", "every final response"))
        self.assertIn(f"one or two leaf", corpus.lower())
        self.assertEqual(
            RETRIEVAL_BUDGET,
            {"module_indexes": 1, "leaf_docs": 2, "cross_leaf_docs": 3},
        )
        for field in REQUIRED_FRONT_MATTER:
            self.assertRegex(corpus, rf"\b{re.escape(field)}\b")

    def test_no_known_contradicting_thresholds(self):
        corpus = self.read_corpus()

        self.assertNotRegex(corpus, r"\b(4500|4,500|5000|5,000|8000|8,000)\b")

    def test_public_and_internal_module_boundary_contracts_match(self):
        public = (ROOT / "skills" / "token-atlas" / "references" / "initialize.md").read_text(encoding="utf-8")
        internal = (ROOT / ".agents" / "skills" / "token-atlas" / "references" / "initialize.md").read_text(encoding="utf-8")

        public_contract = self.section(public, "## Module Boundary Contract")
        internal_contract = self.section(internal, "## Module Boundary Contract")
        self.assertEqual(public_contract, internal_contract)
        self.assertIn("target repository", public_contract)
        self.assertIn("`<module>`", public_contract)
        self.assertIn("`<capability>`", public_contract)
        self.assertRegex(public_contract, r"never prescribe target-repo\s+module names")

    def test_public_and_internal_closeout_workflows_match(self):
        public = (ROOT / "skills" / "token-atlas" / "references" / "closeout.md").read_text(encoding="utf-8")
        internal = (ROOT / ".agents" / "skills" / "token-atlas" / "references" / "closeout.md").read_text(encoding="utf-8")

        self.assertEqual(public, internal)
        self.assertIn("Do not persist a change-set ledger", public)
        self.assertIn("Do not invoke closeout again", public)
        normalized = re.sub(r"\s+", " ", public)
        self.assertIn("apply the knowledge-impact gate exactly once before the final response", normalized)
        self.assertIn("If the current turn made no intentional repository content mutation, stop silently", normalized)
        self.assertIn("Return `no-op` without reading PKF, loading Token Atlas, inspecting Git, or validating when the change is knowledge-neutral", normalized)
        self.assertIn("Do not load this reference", normalized)
        self.assertIn("Emit nothing for a read-only bypass", normalized)
        self.assertIn("Before the first task mutation in a session, capture a baseline snapshot", normalized)
        self.assertIn("both endpoints of renames", normalized)
        self.assertIn("content identity for untracked files", normalized)
        self.assertIn("identity must change when the same path is edited again", normalized)
        self.assertIn("Never acknowledge a failed or\nambiguous snapshot", public)
        self.assertIn("Update only leaves whose durable facts changed", public)
        self.assertIn("only `.ai/` changed", public)
        self.assertNotIn("every user turn", public.lower())
        self.assertNotIn("every final response", public.lower())

    def test_skill_packages_allow_implicit_closeout_invocation(self):
        for package in (ROOT / "skills" / "token-atlas", ROOT / ".agents" / "skills" / "token-atlas"):
            metadata = (package / "agents" / "openai.yaml").read_text(encoding="utf-8")
            self.assertIn("allow_implicit_invocation: true", metadata)

    def read_corpus(self) -> str:
        roots = [
            ROOT / "README.md",
            ROOT / "skills" / "token-atlas",
            ROOT / ".agents" / "skills" / "token-atlas",
        ]
        parts = []
        for root in roots:
            if root.is_file():
                parts.append(root.read_text(encoding="utf-8"))
                continue
            for path in sorted(root.rglob("*")):
                if path.is_file() and path.suffix in {".md", ".yaml", ".yml"}:
                    parts.append(path.read_text(encoding="utf-8"))
        return "\n".join(parts)

    @staticmethod
    def section(text: str, heading: str) -> str:
        start = text.index(heading)
        end = text.index("\n---\n", start)
        return text[start:end]


if __name__ == "__main__":
    unittest.main()
