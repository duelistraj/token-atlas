import re
import unittest
from pathlib import Path

import sys


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from pkf_contract import ESTIMATOR_FORMULA, REQUIRED_FRONT_MATTER, TOKEN_THRESHOLDS


class ContractConsistencyTests(unittest.TestCase):
    def test_contract_values_appear_in_docs_and_fixtures(self):
        corpus = self.read_corpus()

        self.assertIn(f"{TOKEN_THRESHOLDS['startup']:,}", corpus)
        self.assertIn(f"{TOKEN_THRESHOLDS['module']:,}", corpus)
        self.assertIn(ESTIMATOR_FORMULA, corpus)
        for field in REQUIRED_FRONT_MATTER:
            self.assertRegex(corpus, rf"\b{re.escape(field)}\b")

    def test_no_known_contradicting_thresholds(self):
        corpus = self.read_corpus()

        self.assertNotRegex(corpus, r"\b(4500|4,500|5000|5,000)\b")

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


if __name__ == "__main__":
    unittest.main()
