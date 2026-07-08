"""Canonical Token Atlas PKF contract values.

Keep this module dependency-free. Tooling, tests, and docs drift guards import
these values instead of copying threshold and schema literals.
"""

from __future__ import annotations


REQUIRED_FRONT_MATTER = {"type", "title", "description", "resource", "tags", "timestamp", "pkf"}

TOKEN_THRESHOLDS = {
    "startup": 4000,
    "module": 8000,
}
ESTIMATOR_FORMULA = "ceil(character_count / 4)"

REQUIRED_RUNTIME_DOCS = (
    "PKF.md",
    "MEMORY.md",
    "ARCHITECTURE.md",
    "knowledge/INDEX.md",
)
SHARED_DOCS = (
    "glossary.md",
    "dependencies.md",
    "decision_log.md",
)
REQUIRED_MODULE_DOCS = (
    "INDEX.md",
    "api.md",
    "schema.md",
    "business_rules.md",
    "ui.md",
)

PROFILES = {
    "core": {
        "retrieval_exports": "off",
        "simulation": "changed",
        "token_budget": "summary",
        "validation_strictness": "advisory",
    },
    "ci": {
        "retrieval_exports": "off",
        "simulation": "required",
        "token_budget": "full",
        "validation_strictness": "ci",
    },
    "retrieval": {
        "retrieval_exports": "off",
        "simulation": "changed",
        "token_budget": "summary",
        "validation_strictness": "advisory",
    },
    "full": {
        "retrieval_exports": "all",
        "simulation": "all",
        "token_budget": "full",
        "validation_strictness": "ci",
    },
}

PROFILE_DEFAULT = "core"
RETRIEVAL_EXPORTS = ("off", "rag", "graph", "all")
SIMULATION_MODES = ("off", "changed", "required", "all")
TOKEN_BUDGETS = ("summary", "full")
VALIDATION_STRICTNESS = ("advisory", "ci")

EXIT_CODES = {
    "ok": 0,
    "ci_blocking": 1,
    "usage": 2,
}

RETRIEVAL_PATH = (
    "PKF.md",
    "MEMORY.md",
    "ARCHITECTURE.md",
    "knowledge/INDEX.md",
    "knowledge/<module>/INDEX.md",
    "required leaf docs",
)
