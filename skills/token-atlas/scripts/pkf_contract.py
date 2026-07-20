"""Canonical Token Atlas PKF contract values.

Keep this module dependency-free. Tooling, tests, and docs drift guards import
these values instead of copying threshold and schema literals.
"""

from __future__ import annotations


REQUIRED_FRONT_MATTER = {"type", "title", "description", "resource", "tags", "timestamp", "pkf"}

RUNTIME_VERSION_FIELD = "runtime_version"
RUNTIME_VERSION = 4

RETRIEVAL_MODE_FIELD = "retrieval"
RETRIEVAL_DEFAULT = "adaptive"
RETRIEVAL_MODES = ("adaptive", "mandatory")

TOKEN_THRESHOLDS = {
    "startup": 2500,
    "leaf": 1500,
}
ESTIMATOR_FORMULA = "ceil(character_count / 4)"

CLOSEOUT_DEFAULT = "adaptive"
CLOSEOUT_MODES = ("adaptive", "off")
CLOSEOUT_PROTOCOL_HEADING = "## Closeout Protocol (MANDATORY)"
LEGACY_CLOSEOUT_PHRASES = ("every user turn", "every final response")
PROTOCOL_REQUIREMENTS = {
    "retrieval": (
        "### Adaptive retrieval gate",
        "cheap local probe",
        "### PKF activation",
        "### Fallback and verification",
        "### Keep the knowledge base in sync",
    ),
    "closeout": (
        "### Adaptive gate",
        "If the current turn made no intentional repository content mutation",
        "stop silently",
        "Keep the acknowledgement in session context",
        "### Knowledge-impact gate",
        "durable facts, evidence, or routing",
        "### Incremental synchronization",
        "### Safety and recursion",
        "Never invoke closeout again",
        "PKF closeout:",
    ),
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
MODULE_OWNERSHIP_ROOTS_FIELD = "ownership_roots"
CROSS_ROUTES_FIELD = "routes"
CROSS_ROUTE_REQUIRED_FIELDS = ("intent", "triggers", "modules", "loads")
CROSS_ROUTE_REQUIREMENTS_FIELD = "requirements"
CROSS_ROUTE_LOAD_COVERAGE_FIELD = "load_coverage"
LEAF_MATERIALIZATION_FIELD = "materialization"
LEAF_MATERIALIZATION_MODES = ("complete", "pending")
EMPTY_LEAF_MARKER = "- TODO: No source-backed facts."
PENDING_LEAF_MARKER = "- TODO: Pending source extraction."
EDIT_MAP_HEADING = "## Edit Map"
EDIT_MAP_COLUMNS = ("Behavior", "Source symbols", "Tests", "Styles/tokens", "Locator")
GENERIC_EDIT_MAP_BEHAVIORS = frozenset(
    {
        "behavior",
        "documented behavior",
        "documented capability behavior",
        "implementation behavior",
        "none",
        "n/a",
        "todo",
    }
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
