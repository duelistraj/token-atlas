"""Canonical Token Atlas PKF contract values.

Keep this module dependency-free. Tooling, tests, and docs drift guards import
these values instead of copying threshold and schema literals.
"""

from __future__ import annotations


REQUIRED_FRONT_MATTER = {"type", "title", "description", "resource", "tags", "timestamp", "pkf"}

TOKEN_THRESHOLDS = {
    "startup": 2500,
    "leaf": 1500,
    "task": 4000,
}
ESTIMATOR_FORMULA = "ceil(character_count / 4)"

RETRIEVAL_BUDGET = {
    "module_indexes": 1,
    "leaf_docs": 2,
}

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
LEAF_MODULE_DOCS = tuple(doc for doc in REQUIRED_MODULE_DOCS if doc != "INDEX.md")
LEAF_SOURCE_SYMBOLS_FIELD = "source_symbols"
EMPTY_LEAF_MARKER = "- TODO: No source-backed facts."
EDIT_MAP_HEADING = "## Edit Map"
EDIT_MAP_COLUMNS = ("Behavior", "Source symbols", "Tests", "Styles/tokens", "Locator")

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
