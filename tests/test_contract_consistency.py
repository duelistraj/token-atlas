import re
import unittest
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pkf_contract import (
    ESTIMATOR_FORMULA,
    LEAF_SOURCE_SYMBOLS_FIELD,
    REQUIRED_FRONT_MATTER,
    RETRIEVAL_BUDGET,
    TOKEN_THRESHOLDS,
)


class ContractConsistencyTests(unittest.TestCase):
    def test_contract_values_appear_in_docs_and_fixtures(self):
        corpus = self.read_corpus()

        for threshold in TOKEN_THRESHOLDS.values():
            self.assertIn(f"{threshold:,}", corpus)
        self.assertIn(ESTIMATOR_FORMULA, corpus)
        self.assertIn(LEAF_SOURCE_SYMBOLS_FIELD, corpus)
        self.assertIn(f"one or two leaf", corpus.lower())
        self.assertEqual(RETRIEVAL_BUDGET, {"module_indexes": 1, "leaf_docs": 2})
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
