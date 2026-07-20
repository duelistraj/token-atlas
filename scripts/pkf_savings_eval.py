#!/usr/bin/env python3
"""Compare Token Atlas PKF lifecycle cost with a source-only repository baseline."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import tarfile
import tempfile
import time
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pkf_lib import PkfParseError, listify, read_front_matter  # noqa: E402
from pkf_tokens import count_tokens  # noqa: E402

PUBLIC_SKILL = ROOT / "skills" / "token-atlas"
DEFAULT_TARGET_COMMIT = "5c458df3c737f0af2a2193186d98af90c45163f0"
DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_REPETITIONS = 3
DEFAULT_TIMEOUT_SECONDS = 1_800
DEFAULT_ARTIFACTS_ROOT = ROOT / "benchmarks" / "artifacts"
ALLOWED_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")
EVALUATION_SUITES = ("retrieval", "lifecycle", "closeout", "regression", "all")
ARTIFACT_MODES = ("full", "public", "off")
TARGET_NAME = "tether-brain"
ISOLATED_CLOSEOUT_PATCH = ROOT / "benchmarks" / "patches" / "favorite-visibility.patch"
MUTATION_PATHS = (
    "frontend/src/notes/noteSectionState.ts",
    "frontend/src/notes/noteSectionState.test.ts",
)
ARM_DEFINITIONS = {
    "source_only": "No PKF and no adaptive local-probe instructions; generic source discovery only.",
    "probe_only": "Adaptive bounded local probe, with no PKF installed or available.",
    "pkf": "PKF installed with adaptive retrieval and repository-local semantic closeout; an individual task may bypass retrieval.",
}
RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
PKF_ROUTE_MARKER_PATTERN = re.compile(
    r"^PKF route: (?P<routes>[a-z0-9][a-z0-9-]*(?: \+ [a-z0-9][a-z0-9-]*)*); "
    r"(?P<leaves>[1-9][0-9]*) unique leaves; fallback=(?P<fallback>yes|no)$"
)

SOURCE_ONLY_AGENTS = """# AGENTS

## Code Search

- Prefer `rg` (ripgrep) for text search and file discovery.
- Prefer `sg` (ast-grep) for syntax-aware searches and refactoring.
- Avoid `grep -r` unless `rg` is unavailable.

## Best Practices

- Read and follow `.codex/best-practices/PYTHON-BEST-PRACTICES.md` for Python work.
- Read and follow `.codex/best-practices/REACT-BEST-PRACTICES.md` for React work.
"""

PROBE_ONLY_AGENTS = """# AGENTS

## Adaptive local discovery

For a likely single-capability task, use a cheap local probe of at most two
targeted `rg`/`sg` searches and three source files. If that resolves a known path
or symbol, continue locally. For cross-capability, architecture, ownership, or
repository-wide work, use source-only discovery because no PKF is installed.

## Code Search

- Prefer `rg` (ripgrep) for text search and file discovery.
- Prefer `sg` (ast-grep) for syntax-aware searches and refactoring.
- Avoid `grep -r` unless `rg` is unavailable.

## Best Practices

- Read and follow `.codex/best-practices/PYTHON-BEST-PRACTICES.md` for Python work.
- Read and follow `.codex/best-practices/REACT-BEST-PRACTICES.md` for React work.
"""

INITIALIZE_PROMPT = (
    "Use the token-atlas skill and initialize through the installed checkout-local helper at "
    ".codex/skills/token-atlas/scripts/pkf_scaffold.py. Treat helper scripts as opaque "
    "executables: do not read their source unless an invocation fails because the helper itself "
    "is broken. "
    "PKF with hybrid extraction: review capability boundaries, materialize shared "
    "architecture and bounded routing. Materialize every verified public behavior, important "
    "mutation entrypoint, and cross-capability contract needed for direct source-backed "
    "retrieval; do not impose a fixed leaf count per capability. Record narrow atomic "
    "cross-capability routes under pkf.routes in .ai/knowledge/INDEX.md and compose multiple "
    "routes for broader intents. Give every route requirement IDs and a load_coverage mapping; "
    "every leaf must uniquely cover at least one requirement. Include capability-local public behavior state/helpers and "
    "their focused tests in materialized leaf source_symbols; leave unrelated implementation leaves "
    "pending. Use profile=core, retrieval_exports=off, "
    "simulation=changed, token_budget=summary, and validation_strictness=ci. "
    "Run exactly one explicit post-extraction validation. Do not change application source or tests."
)

CLOSEOUT_CONTROL_PROMPT = """A benchmark harness already applied and tested this
repository mutation: favorited notes remain visible in All, remain excluded from
their home category, and retain archive/favorite mutual exclusion. The turn-owned
paths are frontend/src/notes/noteSectionState.ts and
frontend/src/notes/noteSectionState.test.ts. Do not change application source or
tests. This checkout has no PKF; return a compact acknowledgement that no knowledge
synchronization surface exists without reading repository source.
"""

CLOSEOUT_PKF_PROMPT = """A benchmark harness already applied and tested this
repository mutation: favorited notes remain visible in All, remain excluded from
their home category, and retain archive/favorite mutual exclusion. The turn-owned
paths are frontend/src/notes/noteSectionState.ts and
frontend/src/notes/noteSectionState.test.ts. Do not change application source or
tests. Follow the repository bootstrap for routine mapped closeout: begin with
the exact repository-local route helper, do not activate or read Token Atlas
before the route result, reconcile both changed files with the returned leaf's
source_symbols and Edit Map before validation, and emit the exact final
`PKF closeout:` status line. Do not replay repository startup or rediscover the
mutation.
"""

MUTATION_PROMPT = """In this disposable benchmark checkout, change note visibility so a
favorited note remains visible in All while staying excluded from its home category.
Preserve current Archive behavior and favorite/archive mutual exclusion. Update the
focused noteSectionState tests and run them. Follow all repository instructions and
keep repository knowledge synchronized when required.
"""


@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    prompt: str
    expected_answers: Mapping[str, bool]


READ_ONLY_TASKS = (
    TaskSpec(
        task_id="boards_add_task",
        prompt=(
            "Answer this repository behavior question without changing files: when the "
            "global Boards Add task action is used, how is its target list chosen and what "
            "happens when no eligible list exists? Return the requested structured answer "
            "with concise source evidence."
        ),
        expected_answers={
            "targets_first_non_final_by_position": True,
            "can_target_final_list": False,
            "shows_error_when_none": True,
            "mutates_board_when_none": False,
        },
    ),
    TaskSpec(
        task_id="note_task_links",
        prompt=(
            "Answer this cross-capability repository question without changing files: who "
            "may read or modify note-task links, are completed tasks linkable, and what does "
            "trashing then restoring a linked task, list, or board do to the relationship? "
            "Return the requested structured answer with concise source evidence. If PKF "
            "retrieval activates, include exactly one evidence string in this form: `PKF "
            "route: <route-id> + <route-id>; <N> unique leaves; fallback=<yes|no>`. List only "
            "the selected keyed route IDs, deduplicate their combined leaves, and omit the "
            "marker when PKF is unavailable or bypassed."
        ),
        expected_answers={
            "owners_can_modify": True,
            "editors_can_modify": True,
            "viewers_can_modify": False,
            "viewers_can_read": True,
            "completed_tasks_linkable": True,
            "trash_deletes_relationship": False,
            "restore_reveals_relationship": True,
        },
    ),
)

POST_MUTATION_TASK = TaskSpec(
    task_id="favorite_visibility_after_change",
    prompt=(
        "Answer from the current repository state without changing files: where does a "
        "favorited note appear, is it still shown in its home category, and what happens "
        "when that note is archived? Return the requested structured answer with concise "
        "source evidence."
    ),
    expected_answers={
        "favorite_appears_in_favorite": True,
        "favorite_appears_in_all": True,
        "favorite_appears_in_home": False,
        "archiving_clears_favorite": True,
        "archived_appears_in_all": True,
    },
)


@dataclass(frozen=True)
class Usage:
    input_tokens: int
    cached_input_tokens: int
    output_tokens: int

    @property
    def non_cached_input_tokens(self) -> int:
        return max(0, self.input_tokens - self.cached_input_tokens)


@dataclass(frozen=True)
class TraceMetrics:
    tool_call_count: int
    read_or_search_command_count: int
    tool_input_chars: int
    tool_output_chars: int
    explicit_read_path_count: int
    explicit_ai_read_path_count: int
    explicit_skill_read_path_count: int
    searched_root_count: int
    ai_read_or_search_command_count: int
    routed_document_count: int
    fallback_invocation_count: int
    fallback_search: bool


@dataclass(frozen=True)
class CodexResult:
    repetition: int
    arm: str
    task_id: str
    phase: str
    returncode: int
    duration_ms: int
    usage: Usage | None
    answer: Mapping[str, Any] | None
    answer_correct: bool | None
    accessed_skill: bool
    accessed_closeout: bool
    used_route_helper: bool
    emitted_closeout: bool
    retrieval_decision: str
    fallback_search: bool
    mentioned_path_count: int
    mentioned_ai_path_count: int
    tool_call_count: int
    read_or_search_command_count: int
    tool_input_chars: int
    tool_output_chars: int
    explicit_read_path_count: int
    explicit_ai_read_path_count: int
    explicit_skill_read_path_count: int
    searched_root_count: int
    ai_read_or_search_command_count: int
    routed_document_count: int
    fallback_invocation_count: int
    changed_path_count: int
    changed_expected_paths: bool | None
    focused_test_passed: bool | None
    pkf_validation_passed: bool | None
    error: str
    initial_route_status: str = "not_run"
    final_route_status: str = "not_run"
    route_attempt_count: int = 0
    routing_coverage_defect: bool = False
    route_attempts: tuple[Mapping[str, Any], ...] = ()
    trace_segments: Mapping[str, Mapping[str, Any]] | None = None
    implementation_explicit_ai_read_path_count: int = 0
    implementation_explicit_skill_read_path_count: int = 0
    implementation_fallback_search: bool = False
    closeout_accessed_skill: bool = False
    closeout_accessed_closeout: bool = False
    closeout_fallback_search: bool = False
    closeout_unexpected_read_path_count: int = 0
    closeout_unexpected_read_paths: tuple[str, ...] = ()
    closeout_validation_call_count: int = 0
    initialization_validation_call_count: int = 0
    initialization_helper_source_read_count: int = 0
    initialization_helper_source_read_paths: tuple[str, ...] = ()
    initialization_route_status: str = "not_applicable"
    initialization_unmatched_paths: tuple[str, ...] = ()
    route_marker_emitted: bool = False
    cross_route_marker_status: str = "not_applicable"
    cross_route_ids: tuple[str, ...] = ()
    cross_route_unique_leaf_count: int = 0
    cross_route_fallback: bool | None = None
    cross_configured_document_paths: tuple[str, ...] = ()
    cross_observed_document_paths: tuple[str, ...] = ()
    cross_missing_route_ids: tuple[str, ...] = ()
    cross_missing_document_paths: tuple[str, ...] = ()
    cross_unexpected_document_paths: tuple[str, ...] = ()
    cross_requirement_count: int = 0
    cross_covered_requirement_count: int = 0
    cross_coverage_status: str = "not_applicable"
    cross_minimality_status: str = "not_applicable"
    cross_redundant_document_paths: tuple[str, ...] = ()
    cross_estimated_tokens: int = 0
    cross_token_estimator: str = "not_applicable"


class EvaluationError(Exception):
    """Invalid evaluation setup or runner usage."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-repo", type=Path, required=True)
    parser.add_argument("--target-commit", default=DEFAULT_TARGET_COMMIT)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--model-reasoning-effort",
        choices=ALLOWED_REASONING_EFFORTS,
        default=DEFAULT_REASONING_EFFORT,
    )
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    parser.add_argument("--suite", choices=EVALUATION_SUITES, default="lifecycle")
    parser.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument("--runtime-root", type=Path, default=ROOT)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--report-json", type=Path)
    parser.add_argument("--report-markdown", type=Path)
    parser.add_argument("--artifacts-root", type=Path, default=DEFAULT_ARTIFACTS_ROOT)
    parser.add_argument("--artifact-mode", choices=ARTIFACT_MODES, default="full")
    parser.add_argument("--run-id")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be at least 1")
    if args.run_id is not None and not RUN_ID_PATTERN.fullmatch(args.run_id):
        parser.error("--run-id must be 1-128 lowercase letters, digits, dots, underscores, or hyphens")
    return args


def run_command(
    command: Sequence[str],
    *,
    cwd: Path,
    check: bool = True,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        tuple(command),
        cwd=cwd,
        text=True,
        capture_output=True,
        check=check,
        timeout=timeout,
    )


def verify_target(target_repo: Path, target_commit: str) -> dict[str, str]:
    target_repo = target_repo.resolve()
    if not (target_repo / ".git").exists():
        raise EvaluationError(f"target is not a Git repository: {target_repo}")
    try:
        commit = run_command(
            ("git", "rev-parse", f"{target_commit}^{{commit}}"),
            cwd=target_repo,
        ).stdout.strip()
        tree = run_command(
            ("git", "rev-parse", f"{commit}^{{tree}}"),
            cwd=target_repo,
        ).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise EvaluationError(f"target commit is unavailable: {target_commit}") from exc
    return {"commit": commit, "tree": tree}


def sha256_tree(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def export_target(target_repo: Path, target_commit: str, destination: Path) -> None:
    destination.mkdir(parents=True)
    archive_path = destination.parent / f"{destination.name}.tar"
    run_command(
        (
            "git",
            "archive",
            "--format=tar",
            f"--output={archive_path}",
            target_commit,
        ),
        cwd=target_repo,
    )
    with tarfile.open(archive_path, mode="r") as archive:
        archive.extractall(destination, filter="data")
    archive_path.unlink()


def strip_pkf(repo: Path, agents_text: str = SOURCE_ONLY_AGENTS) -> None:
    ai_dir = repo / ".ai"
    if ai_dir.exists():
        shutil.rmtree(ai_dir)
    installed_skill = repo / ".codex" / "skills" / "token-atlas"
    if installed_skill.exists():
        shutil.rmtree(installed_skill)
    (repo / "AGENTS.md").write_text(agents_text, encoding="utf-8")


def install_public_skill(repo: Path) -> None:
    destination = repo / ".codex" / "skills" / "token-atlas"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PUBLIC_SKILL, destination)


def link_local_dependencies(repo: Path, target_repo: Path) -> None:
    source = target_repo / "frontend" / "node_modules"
    destination = repo / "frontend" / "node_modules"
    if source.is_dir() and not destination.exists():
        destination.symlink_to(source, target_is_directory=True)


def initialize_git(repo: Path, message: str) -> None:
    commands = (
        ("git", "init", "--quiet"),
        ("git", "config", "user.name", "Token Atlas Savings Eval"),
        ("git", "config", "user.email", "savings-eval@example.invalid"),
        ("git", "add", "."),
        ("git", "commit", "--quiet", "-m", message),
    )
    for command in commands:
        run_command(command, cwd=repo)


def commit_generated_pkf(repo: Path) -> None:
    run_command(("git", "add", "AGENTS.md", ".ai"), cwd=repo)
    run_command(("git", "commit", "--quiet", "-m", "Initialize PKF"), cwd=repo)


def prepare_arms(
    workspace: Path,
    *,
    target_repo: Path,
    target_commit: str,
) -> dict[str, Path]:
    exported = workspace / "exported"
    export_target(target_repo, target_commit, exported)
    strip_pkf(exported)
    arms: dict[str, Path] = {}
    for arm in ("source_only", "probe_only", "pkf"):
        repo = workspace / arm
        shutil.copytree(exported, repo, symlinks=True)
        if arm == "pkf":
            install_public_skill(repo)
        elif arm == "probe_only":
            (repo / "AGENTS.md").write_text(PROBE_ONLY_AGENTS, encoding="utf-8")
        link_local_dependencies(repo, target_repo)
        initialize_git(repo, "Benchmark source baseline")
        arms[arm] = repo
    return arms


def answer_schema(task: TaskSpec) -> dict[str, Any]:
    answer_properties = {
        key: {"type": "boolean"} for key in task.expected_answers
    }
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "type": "object",
        "properties": {
            "task_id": {"type": "string"},
            "answers": {
                "type": "object",
                "properties": answer_properties,
                "required": list(answer_properties),
                "additionalProperties": False,
            },
            "evidence": {"type": "array", "items": {"type": "string"}},
        },
        "required": ["task_id", "answers", "evidence"],
        "additionalProperties": False,
    }


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, Mapping):
        return [item for nested in value.values() for item in flatten_strings(nested)]
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [item for nested in value for item in flatten_strings(nested)]
    return []


TOOL_INPUT_FIELDS = frozenset(
    {"command", "args", "arguments", "path", "paths", "query", "pattern", "input"}
)
TOOL_OUTPUT_FIELDS = frozenset(
    {"output", "stdout", "stderr", "result", "content", "aggregated_output", "error"}
)
READ_OR_SEARCH_COMMANDS = frozenset(
    {
        "awk",
        "cat",
        "egrep",
        "fd",
        "fgrep",
        "find",
        "grep",
        "head",
        "jq",
        "less",
        "more",
        "nl",
        "rg",
        "sed",
        "sg",
        "tail",
        "tree",
    }
)
SHELL_COMMANDS = frozenset({"bash", "dash", "fish", "sh", "zsh"})
SHELL_CONTROL_TOKENS = frozenset({";", "&&", "||", "|", "&"})
SHELL_RESERVED_PREFIXES = frozenset({"do", "else", "elif", "if", "then", "while", "until", "!"})
PYTHON_COMMANDS = frozenset({"python", "python3"})
HELPER_SOURCE_ROOTS = (".ai/tools", ".codex/skills/token-atlas/scripts")


def named_field_strings(value: Any, names: frozenset[str]) -> list[str]:
    if not isinstance(value, Mapping):
        return []
    strings: list[str] = []
    for key, nested in value.items():
        if str(key).lower() in names:
            strings.extend(flatten_strings(nested))
        elif isinstance(nested, Mapping):
            strings.extend(named_field_strings(nested, names))
        elif isinstance(nested, Sequence) and not isinstance(nested, (str, bytes)):
            for item in nested:
                strings.extend(named_field_strings(item, names))
    return strings


def tokenize_shell(value: str) -> list[str]:
    """Tokenize a command without executing it, preserving shell separators."""

    try:
        lexer = shlex.shlex(value, posix=True, punctuation_chars=";&|")
        lexer.whitespace_split = True
        lexer.commenters = ""
        return list(lexer)
    except ValueError:
        return value.split()


def unwrap_shell_command(value: str) -> list[str]:
    """Return the inner script tokens for common `<shell> -c <script>` wrappers."""

    try:
        outer = shlex.split(value)
    except ValueError:
        outer = value.split()
    if outer and Path(outer[0]).name in SHELL_COMMANDS:
        for index, token in enumerate(outer[:-1]):
            if token == "-c" or (token.startswith("-") and "c" in token[1:]):
                return tokenize_shell(outer[index + 1])
    return tokenize_shell(value)


def command_invocations(value: str) -> list[tuple[str, ...]]:
    """Split a shell input into command-position argv groups.

    This is intentionally a conservative trace parser, not a shell evaluator.
    It recognizes command boundaries well enough to distinguish `tail` from
    `--detail` and an invoked validator from a search mentioning its filename.
    """

    tokens = unwrap_shell_command(value)
    segments: list[list[str]] = [[]]
    for token in tokens:
        if token in SHELL_CONTROL_TOKENS or set(token) <= {";", "&", "|"}:
            if segments[-1]:
                segments.append([])
            continue
        segments[-1].append(token)

    invocations: list[tuple[str, ...]] = []
    for raw_segment in segments:
        segment = list(raw_segment)
        while segment and (
            segment[0] in SHELL_RESERVED_PREFIXES
            or re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", segment[0])
        ):
            segment.pop(0)
        if segment and segment[0] == "for":
            continue
        if segment:
            invocations.append(tuple(segment))
    return invocations


def invocation_name(invocation: Sequence[str]) -> str:
    return Path(invocation[0]).name.lower() if invocation else ""


def unwrap_env_invocation(invocation: Sequence[str]) -> tuple[str, ...]:
    if invocation_name(invocation) != "env":
        return tuple(invocation)
    args = list(invocation[1:])
    index = 0
    options_with_values = {"-C", "-S", "-u", "--chdir", "--split-string", "--unset"}
    while index < len(args):
        token = args[index]
        if token == "--":
            return tuple(args[index + 1 :])
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token):
            index += 1
            continue
        if token in options_with_values:
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return tuple(args[index:])
    return ()


def is_read_or_search_invocation(invocation: Sequence[str]) -> bool:
    invocation = unwrap_env_invocation(invocation)
    name = invocation_name(invocation)
    if name in READ_OR_SEARCH_COMMANDS:
        return True
    if name == "git":
        return next((token for token in invocation[1:] if not token.startswith("-")), "") == "show"
    return False


def is_fallback_invocation(invocation: Sequence[str]) -> bool:
    invocation = unwrap_env_invocation(invocation)
    name = invocation_name(invocation)
    args = tuple(invocation[1:])
    if name == "rg":
        return "--files" in args
    if name == "git":
        return next((token for token in args if not token.startswith("-")), "") == "ls-files"
    if name == "find":
        return bool(args and args[0] in {".", "./"})
    if name in {"grep", "egrep", "fgrep"}:
        return any(token == "-r" or (token.startswith("-") and "r" in token[1:]) for token in args)
    return False


def invoked_script_count(item: Mapping[str, Any], script_name: str) -> int:
    count = 0
    for value in named_field_strings(item, TOOL_INPUT_FIELDS):
        for raw_invocation in command_invocations(value):
            invocation = unwrap_env_invocation(raw_invocation)
            name = invocation_name(invocation)
            if name == script_name:
                count += 1
                continue
            if name not in PYTHON_COMMANDS and not re.fullmatch(r"python\d+(?:\.\d+)*", name):
                continue
            script = next(
                (
                    token
                    for token in invocation[1:]
                    if not token.startswith("-") and token not in {"-m", "-c"}
                ),
                "",
            )
            if Path(script).name == script_name:
                count += 1
    return count


def item_is_read_like(item: Mapping[str, Any]) -> bool:
    input_strings = named_field_strings(item, TOOL_INPUT_FIELDS)
    if any(
        is_read_or_search_invocation(invocation)
        for value in input_strings
        for invocation in command_invocations(value)
    ):
        return True
    item_type = str(item.get("type", "")).lower()
    return item_type != "command_execution" and any(
        token in item_type for token in ("read", "search", "query")
    )


def helper_source_read_paths(events: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """Return helper files or directories passed to an actual read/search command."""

    paths: set[str] = set()
    for item in events:
        if not item_is_read_like(item):
            continue
        for value in named_field_strings(item, TOOL_INPUT_FIELDS):
            for invocation in command_invocations(value):
                if not is_read_or_search_invocation(invocation):
                    continue
                for token in invocation[1:]:
                    normalized = token.strip("'\" ,:").removeprefix("./")
                    for root in HELPER_SOURCE_ROOTS:
                        marker = f"/{root}"
                        if marker in normalized:
                            normalized = normalized[normalized.index(marker) + 1 :]
                        if normalized == root or normalized.startswith(f"{root}/"):
                            paths.add(normalized)
    return tuple(sorted(paths))


def completed_tool_events(output: str) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for raw_line in output.splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        item = event.get("item")
        if event.get("type") != "item.completed" or not isinstance(item, dict):
            continue
        if str(item.get("type", "")) in {"agent_message", "reasoning"}:
            continue
        events.append(item)
    return events


def parse_jsonl(output: str) -> tuple[Usage | None, tuple[str, ...], str]:
    usage: Usage | None = None
    messages: list[str] = []
    normalized_events: list[str] = []
    for raw_line in output.splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        normalized_events.append(json.dumps(event, sort_keys=True))
        if event.get("type") == "turn.completed" and isinstance(event.get("usage"), dict):
            raw_usage = event["usage"]
            usage = Usage(
                input_tokens=int(raw_usage.get("input_tokens", 0)),
                cached_input_tokens=int(raw_usage.get("cached_input_tokens", 0)),
                output_tokens=int(raw_usage.get("output_tokens", 0)),
            )
        item = event.get("item")
        if (
            event.get("type") == "item.completed"
            and isinstance(item, dict)
            and item.get("type") == "agent_message"
            and isinstance(item.get("text"), str)
        ):
            messages.append(item["text"])
    return usage, tuple(messages), "\n".join(normalized_events)


def parse_structured_answer(messages: Sequence[str]) -> Mapping[str, Any] | None:
    for message in reversed(messages):
        try:
            parsed = json.loads(message)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict) and isinstance(parsed.get("answers"), dict):
            return parsed
    return None


def inspect_jsonl_trace(
    output: str,
    *,
    known_paths: Sequence[str] = (),
    known_directories: Sequence[str] = (),
) -> TraceMetrics:
    return inspect_tool_events(
        completed_tool_events(output),
        known_paths=known_paths,
        known_directories=known_directories,
    )


def inspect_tool_events(
    events: Sequence[Mapping[str, Any]],
    *,
    known_paths: Sequence[str] = (),
    known_directories: Sequence[str] = (),
) -> TraceMetrics:
    tool_calls = 0
    read_or_search_commands = 0
    tool_input_chars = 0
    tool_output_chars = 0
    explicit_paths: set[str] = set()
    searched_roots: set[str] = set()
    ai_read_or_search_commands = 0
    fallback_search = False
    fallback_invocations = 0
    normalized_paths = tuple(sorted(set(known_paths), key=len, reverse=True))
    normalized_directories = set(known_directories)
    for item in events:
        tool_calls += 1
        input_strings = named_field_strings(item, TOOL_INPUT_FIELDS)
        output_strings = named_field_strings(item, TOOL_OUTPUT_FIELDS)
        tool_input_chars += sum(len(value) for value in input_strings)
        tool_output_chars += sum(len(value) for value in output_strings)
        input_text = " ".join(input_strings)
        lowered = input_text.lower()
        read_like = item_is_read_like(item)
        if read_like:
            read_or_search_commands += 1
            if ".ai/" in lowered or " .ai" in lowered:
                ai_read_or_search_commands += 1
            for path in normalized_paths:
                if path in input_text:
                    explicit_paths.add(path)
            for value in input_strings:
                try:
                    tokens = shlex.split(value)
                except ValueError:
                    tokens = value.split()
                for token in tokens:
                    clean = token.strip("'\"").removeprefix("./")
                    if token in {".", "./"}:
                        searched_roots.add(".")
                    elif clean in normalized_directories:
                        searched_roots.add(clean)
        item_fallback_invocations = sum(
            is_fallback_invocation(invocation)
            for value in named_field_strings(item, TOOL_INPUT_FIELDS)
            for invocation in command_invocations(value)
        )
        if item_fallback_invocations:
            fallback_search = True
            fallback_invocations += item_fallback_invocations
    explicit_ai = {path for path in explicit_paths if path.startswith(".ai/")}
    explicit_skill = {
        path for path in explicit_paths if "/skills/token-atlas/" in f"/{path}" or path.startswith(".codex/skills/token-atlas/")
    }
    routed_documents = {
        path
        for path in explicit_paths
        if path.startswith(".ai/knowledge/") and not path.endswith("/INDEX.md")
    }
    return TraceMetrics(
        tool_call_count=tool_calls,
        read_or_search_command_count=read_or_search_commands,
        tool_input_chars=tool_input_chars,
        tool_output_chars=tool_output_chars,
        explicit_read_path_count=len(explicit_paths),
        explicit_ai_read_path_count=len(explicit_ai),
        explicit_skill_read_path_count=len(explicit_skill),
        searched_root_count=len(searched_roots),
        ai_read_or_search_command_count=ai_read_or_search_commands,
        routed_document_count=len(routed_documents),
        fallback_invocation_count=fallback_invocations,
        fallback_search=fallback_search,
    )


def explicit_read_paths_for_events(
    events: Sequence[Mapping[str, Any]],
    known_paths: Sequence[str],
) -> set[str]:
    paths: set[str] = set()
    normalized_paths = tuple(sorted(set(known_paths), key=len, reverse=True))
    for item in events:
        input_strings = named_field_strings(item, TOOL_INPUT_FIELDS)
        input_text = " ".join(input_strings)
        if not item_is_read_like(item):
            continue
        for path in normalized_paths:
            if path in input_text:
                paths.add(path)
    return paths


def parse_pkf_route_marker(structured: Mapping[str, Any] | None) -> dict[str, Any]:
    empty = {
        "status": "missing",
        "route_ids": (),
        "unique_leaf_count": 0,
        "fallback": None,
    }
    if not isinstance(structured, Mapping):
        return empty
    evidence = structured.get("evidence")
    if not isinstance(evidence, list):
        return empty
    candidates = [
        value for value in evidence if isinstance(value, str) and value.startswith("PKF route:")
    ]
    if not candidates:
        return empty
    if len(candidates) != 1:
        return {**empty, "status": "multiple"}
    match = PKF_ROUTE_MARKER_PATTERN.fullmatch(candidates[0])
    if match is None:
        return {**empty, "status": "malformed"}
    route_ids = tuple(match.group("routes").split(" + "))
    if len(set(route_ids)) != len(route_ids):
        return {**empty, "status": "duplicate_routes"}
    return {
        "status": "valid",
        "route_ids": route_ids,
        "unique_leaf_count": int(match.group("leaves")),
        "fallback": match.group("fallback") == "yes",
    }


def configured_cross_routes(
    repo: Path,
    route_ids: Sequence[str],
) -> dict[str, Any]:
    empty = {
        "loads": (),
        "missing_route_ids": tuple(route_ids),
        "requirement_count": 0,
        "covered_requirement_count": 0,
        "coverage_status": "incomplete" if route_ids else "unknown",
        "minimality_status": "unknown",
        "redundant_loads": (),
        "estimated_tokens": 0,
        "token_estimator": "approximate",
    }
    index = repo / ".ai" / "knowledge" / "INDEX.md"
    if not index.is_file():
        return empty
    try:
        metadata = read_front_matter(index)
    except PkfParseError:
        return empty
    pkf = metadata.get("pkf")
    routes = pkf.get("routes") if isinstance(pkf, Mapping) else None
    if not isinstance(routes, Mapping):
        return empty
    loads: set[str] = set()
    missing: list[str] = []
    requirements: set[str] = set()
    coverage_by_load: dict[str, set[str]] = {}
    metadata_known = True
    metadata_valid = True
    for route_id in route_ids:
        route = routes.get(route_id)
        if not isinstance(route, Mapping):
            missing.append(route_id)
            metadata_valid = False
            continue
        route_loads = {str(value) for value in listify(route.get("loads")) if str(value)}
        loads.update(route_loads)
        route_requirements = route.get("requirements")
        load_coverage = route.get("load_coverage")
        if route_requirements is None and load_coverage is None:
            metadata_known = False
            continue
        if (
            not isinstance(route_requirements, list)
            or not route_requirements
            or not isinstance(load_coverage, Mapping)
            or {str(value) for value in load_coverage} != route_loads
        ):
            metadata_valid = False
            continue
        scoped_requirements = {
            f"{route_id}:{value}" for value in route_requirements if isinstance(value, str) and value
        }
        if len(scoped_requirements) != len(route_requirements):
            metadata_valid = False
        requirements.update(scoped_requirements)
        for load, raw_coverage in load_coverage.items():
            if not isinstance(raw_coverage, list) or not raw_coverage:
                metadata_valid = False
                continue
            scoped_coverage = {
                f"{route_id}:{value}" for value in raw_coverage if isinstance(value, str) and value
            }
            if not scoped_coverage <= scoped_requirements:
                metadata_valid = False
            coverage_by_load.setdefault(str(load), set()).update(scoped_coverage & scoped_requirements)

    covered = set().union(*coverage_by_load.values()) if coverage_by_load else set()
    provider_counts = {
        requirement: sum(requirement in values for values in coverage_by_load.values())
        for requirement in requirements
    }
    redundant = tuple(
        sorted(
            load
            for load in loads
            if metadata_known
            and not any(provider_counts.get(requirement) == 1 for requirement in coverage_by_load.get(load, set()))
        )
    )
    if not metadata_known:
        coverage_status = "unknown"
        minimality_status = "unknown"
    elif metadata_valid and not missing and requirements == covered:
        coverage_status = "complete"
        minimality_status = "minimal" if not redundant else "redundant"
    else:
        coverage_status = "incomplete"
        minimality_status = "redundant" if redundant else "invalid"

    load_files = [repo / load for load in sorted(loads) if (repo / load).is_file()]
    text = "\n".join(path.read_text(encoding="utf-8") for path in load_files)
    estimated_tokens, estimator = count_tokens(text, None)
    return {
        "loads": tuple(sorted(loads)),
        "missing_route_ids": tuple(missing),
        "requirement_count": len(requirements),
        "covered_requirement_count": len(covered),
        "coverage_status": coverage_status,
        "minimality_status": minimality_status,
        "redundant_loads": redundant,
        "estimated_tokens": estimated_tokens,
        "token_estimator": estimator,
    }


def parse_route_attempts(events: Sequence[Mapping[str, Any]]) -> tuple[dict[str, Any], ...]:
    attempts: list[dict[str, Any]] = []
    for event_index, item in enumerate(events):
        if invoked_script_count(item, "pkf_route.py") == 0:
            continue
        parsed: Mapping[str, Any] | None = None
        for raw_output in named_field_strings(item, TOOL_OUTPUT_FIELDS):
            try:
                candidate = json.loads(raw_output)
            except json.JSONDecodeError:
                continue
            if isinstance(candidate, Mapping) and candidate.get("status") in {"mapped", "partial", "unmapped"}:
                parsed = candidate
                break
        if parsed is None:
            continue
        affected = [
            str(value.get("path"))
            for value in parsed.get("affected_leaves", [])
            if isinstance(value, Mapping) and isinstance(value.get("path"), str)
        ]
        fallbacks = [
            str(value.get("index"))
            for value in parsed.get("fallback_routes", [])
            if isinstance(value, Mapping) and isinstance(value.get("index"), str)
        ]
        if not fallbacks:
            fallbacks = [str(value) for value in parsed.get("index_fallback", []) if isinstance(value, str)]
        attempts.append(
            {
                "event_index": event_index,
                "schema_version": int(parsed.get("schema_version", 1)),
                "status": str(parsed["status"]),
                "affected_leaves": sorted(set(affected)),
                "fallback_indexes": sorted(set(fallbacks)),
                "unmatched_paths": sorted(
                    str(value) for value in parsed.get("unmatched_paths", []) if isinstance(value, str)
                ),
                "routing_coverage_defect": bool(
                    parsed.get("routing_coverage_defect", parsed.get("unmatched_paths"))
                ),
                "validation_scope": str(parsed.get("validation_scope", "affected")),
            }
        )
    return tuple(attempts)


def segmented_trace(
    events: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    *,
    known_paths: Sequence[str],
    known_directories: Sequence[str],
) -> tuple[dict[str, TraceMetrics], dict[str, Sequence[Mapping[str, Any]]]]:
    if attempts:
        boundary = int(attempts[0]["event_index"])
        event_segments: dict[str, Sequence[Mapping[str, Any]]] = {
            "implementation": events[:boundary],
            "routing": events[boundary : boundary + 1],
            "closeout": events[boundary + 1 :],
        }
    else:
        event_segments = {"implementation": events, "routing": (), "closeout": ()}
    metrics = {
        name: inspect_tool_events(
            selected,
            known_paths=known_paths,
            known_directories=known_directories,
        )
        for name, selected in event_segments.items()
    }
    return metrics, event_segments


def changed_paths(repo: Path) -> tuple[str, ...]:
    status = run_command(("git", "status", "--porcelain"), cwd=repo).stdout
    return tuple(line[3:].strip() for line in status.splitlines() if len(line) > 3)


def tracked_paths(repo: Path) -> tuple[str, ...]:
    output = run_command(
        ("git", "ls-files", "--cached", "--others", "--exclude-standard"),
        cwd=repo,
    ).stdout
    return tuple(sorted({line for line in output.splitlines() if line}))


def tracked_directories(paths: Sequence[str]) -> tuple[str, ...]:
    directories = {
        parent.as_posix()
        for value in paths
        for parent in Path(value).parents
        if parent.as_posix() not in {"", "."}
    }
    return tuple(sorted(directories))


def detect_accessed_paths(event_text: str, paths: Sequence[str]) -> tuple[str, ...]:
    return tuple(path for path in paths if path in event_text)


def sanitized_error(text: str, sensitive_roots: Sequence[Path]) -> str:
    sanitized = text[-1_500:]
    for root in sensitive_roots:
        sanitized = sanitized.replace(str(root.resolve()), f"<{root.name or 'workspace'}>")
    sanitized = re.sub(r"/home/[^/]+/", "<home>/", sanitized)
    return sanitized.strip()


def slug(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9._-]+", "-", value.lower()).strip("-.")
    return normalized or "run"


def make_run_id(args: argparse.Namespace) -> str:
    if args.run_id:
        return args.run_id
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    value = "-".join(
        (
            "token-atlas",
            slug(args.model),
            slug(args.model_reasoning_effort),
            slug(args.suite),
            slug(run_class(args.repetitions)),
            timestamp,
        )
    )
    return value[:128].rstrip("-.")


def repository_diff(repo: Path, *, pkf_only: bool) -> str:
    paths = (".ai", "AGENTS.md") if pkf_only else (".", ":(exclude).ai/**", ":(exclude)AGENTS.md")
    completed = run_command(("git", "diff", "--binary", "--", *paths), cwd=repo, check=False)
    return completed.stdout


def route_trace_excerpt(output: str) -> str:
    attempts = parse_route_attempts(completed_tool_events(output))
    return "\n".join(json.dumps(value, sort_keys=True) for value in attempts)


class ArtifactStore:
    """Incrementally retain sanitized public results and local-only exact PKF evidence."""

    def __init__(self, *, root: Path, run_id: str, mode: str) -> None:
        self.mode = mode
        self.run_id = run_id
        self.root = root.resolve() / run_id
        self.public_dir = self.root / "public"
        self.private_dir = self.root / "private"
        self.calls: list[dict[str, Any]] = []
        self.created_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
        self._counter = 0
        if mode == "off":
            return
        if self.root.exists() and any(self.root.iterdir()):
            raise EvaluationError(f"artifact run already exists: {self.root}")
        self.public_dir.mkdir(parents=True, exist_ok=True)
        if mode == "full":
            self.private_dir.mkdir(parents=True, exist_ok=True)
            self.private_dir.chmod(0o700)
        self.write_manifest("running")

    @property
    def manifest_path(self) -> Path | None:
        return None if self.mode == "off" else self.root / "manifest.json"

    def _write_private(self, path: Path, text: str) -> None:
        if self.mode != "full":
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        parent = path.parent
        while parent == self.private_dir or self.private_dir in parent.parents:
            parent.chmod(0o700)
            if parent == self.private_dir:
                break
            parent = parent.parent
        path.write_text(text, encoding="utf-8")
        path.chmod(0o600)

    def record_call(
        self,
        *,
        result: CodexResult,
        stdout: str,
        stderr: str,
        schema_path: Path | None,
        repo: Path,
        workspace: Path,
    ) -> None:
        if self.mode == "off":
            return
        self._counter += 1
        call_id = (
            f"{self._counter:03d}-r{result.repetition}-{slug(result.arm)}-"
            f"{slug(result.task_id)}"
        )
        self.calls.append(
            {
                "call_id": call_id,
                "repetition": result.repetition,
                "arm": result.arm,
                "task_id": result.task_id,
                "phase": result.phase,
                "returncode": result.returncode,
            }
        )
        if self.mode == "full":
            call_dir = self.private_dir / "calls" / call_id
            sanitized_trace = stdout
            sanitized_stderr = stderr
            for sensitive in (repo, workspace, ROOT):
                replacement = f"<{sensitive.name or 'workspace'}>"
                sanitized_trace = sanitized_trace.replace(str(sensitive.resolve()), replacement)
                sanitized_stderr = sanitized_stderr.replace(str(sensitive.resolve()), replacement)
            sanitized_trace = re.sub(r"/home/[^/]+/", "<home>/", sanitized_trace)
            sanitized_stderr = re.sub(r"/home/[^/]+/", "<home>/", sanitized_stderr)
            self._write_private(call_dir / "trace.jsonl", sanitized_trace)
            self._write_private(call_dir / "stderr.txt", sanitized_stderr)
            self._write_private(
                call_dir / "result.json",
                json.dumps(asdict(result), indent=2, sort_keys=True) + "\n",
            )
            if schema_path is not None and schema_path.is_file():
                self._write_private(call_dir / "schema.json", schema_path.read_text(encoding="utf-8"))
            if result.answer is not None:
                self._write_private(
                    call_dir / "answer.json",
                    json.dumps(result.answer, indent=2, sort_keys=True) + "\n",
                )
            self._write_private(call_dir / "source.diff", repository_diff(repo, pkf_only=False))
            self._write_private(call_dir / "pkf.diff", repository_diff(repo, pkf_only=True))
            route_output = route_trace_excerpt(stdout)
            if route_output:
                self._write_private(call_dir / "route-output.jsonl", route_output + "\n")
        self.write_manifest("running")

    def snapshot_pkf(self, label: str, repo: Path) -> None:
        if self.mode != "full":
            return
        destination = self.private_dir / "pkf-snapshots" / slug(label)
        destination.mkdir(parents=True, exist_ok=True)
        ai_dir = repo / ".ai"
        if ai_dir.is_dir():
            shutil.copytree(ai_dir, destination / ".ai", dirs_exist_ok=True)
        agents = repo / "AGENTS.md"
        if agents.is_file():
            shutil.copy2(agents, destination / "AGENTS.md")
        for path in destination.rglob("*"):
            path.chmod(0o700 if path.is_dir() else 0o600)
        self.write_manifest("running")

    def record_validation(self, label: str, *, passed: bool, output: str) -> None:
        if self.mode == "full":
            self._write_private(
                self.private_dir / "validation" / f"{slug(label)}.json",
                json.dumps({"passed": passed, "output": output}, indent=2, sort_keys=True) + "\n",
            )
        if self.mode != "off":
            self.write_manifest("running")

    def _file_records(self) -> list[dict[str, Any]]:
        if self.mode == "off" or not self.root.exists():
            return []
        records = []
        for path in sorted(item for item in self.root.rglob("*") if item.is_file()):
            if path == self.manifest_path:
                continue
            records.append(
                {
                    "path": path.relative_to(self.root).as_posix(),
                    "sha256": sha256_file(path),
                    "visibility": "private" if self.private_dir in path.parents else "public",
                }
            )
        return records

    def write_manifest(self, status: str, *, error: str = "") -> None:
        if self.mode == "off":
            return
        manifest = {
            "schema_version": 1,
            "run_id": self.run_id,
            "status": status,
            "artifact_mode": self.mode,
            "created_at": self.created_at,
            "arm_definitions": ARM_DEFINITIONS,
            "calls": self.calls,
            "artifacts": self._file_records(),
            "private_artifacts_local_only": self.mode == "full",
            "error": error,
        }
        assert self.manifest_path is not None
        self.manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    def write_public(self, report: Mapping[str, Any]) -> None:
        if self.mode == "off":
            return
        report_path = self.public_dir / "report.json"
        markdown_path = self.public_dir / "report.md"
        report_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        markdown_path.write_text(
            render_markdown(report, raw_result_link="report.json"),
            encoding="utf-8",
        )
        self.write_manifest("failed" if report.get("status") == "failed" else "completed")

    def fail(self, error: str) -> None:
        self.write_manifest("failed", error=error)


def classify_retrieval_decision(*, arm: str, phase: str, trace: TraceMetrics) -> str:
    if arm != "pkf" or phase not in {"retrieval", "post_mutation"}:
        return "not_applicable"
    if trace.explicit_ai_read_path_count or trace.explicit_skill_read_path_count:
        return "activated"
    return "bypassed"


def run_codex(
    *,
    repetition: int,
    arm: str,
    task_id: str,
    phase: str,
    prompt: str,
    repo: Path,
    model: str,
    reasoning_effort: str,
    timeout_seconds: int,
    workspace: Path,
    sandbox: str,
    task: TaskSpec | None = None,
    artifacts: ArtifactStore | None = None,
) -> tuple[CodexResult, str]:
    source_codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    eval_codex_home = workspace / "codex-homes" / f"{arm}-{task_id}"
    eval_codex_home.mkdir(parents=True)
    auth_file = source_codex_home / "auth.json"
    if auth_file.is_file():
        shutil.copy2(auth_file, eval_codex_home / "auth.json")
    process_environment = os.environ.copy()
    process_environment["CODEX_HOME"] = str(eval_codex_home)

    schema_path: Path | None = None
    command = [
        "codex",
        "--ask-for-approval",
        "never",
        "--model",
        model,
        "--config",
        f'model_reasoning_effort="{reasoning_effort}"',
        "exec",
        "--sandbox",
        sandbox,
        "--ephemeral",
        "--ignore-user-config",
        "--json",
    ]
    if task is not None:
        schema_path = workspace / "schemas" / f"{task_id}.schema.json"
        schema_path.parent.mkdir(parents=True, exist_ok=True)
        schema_path.write_text(json.dumps(answer_schema(task)), encoding="utf-8")
        command.extend(("--output-schema", str(schema_path)))
    command.extend(("-C", str(repo), prompt))

    started = time.monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=repo,
            text=True,
            capture_output=True,
            env=process_environment,
            timeout=timeout_seconds,
            check=False,
        )
        returncode = completed.returncode
        stdout = completed.stdout
        stderr = completed.stderr
    except subprocess.TimeoutExpired as exc:
        returncode = 124
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = f"timed out after {timeout_seconds} seconds"
    duration_ms = int((time.monotonic() - started) * 1_000)

    usage, messages, event_text = parse_jsonl(stdout)
    repo_paths = tracked_paths(repo)
    tool_events = completed_tool_events(stdout)
    trace = inspect_tool_events(
        tool_events,
        known_paths=repo_paths,
        known_directories=tracked_directories(repo_paths),
    )
    route_attempts = parse_route_attempts(tool_events)
    segment_metrics, segment_events = segmented_trace(
        tool_events,
        route_attempts,
        known_paths=repo_paths,
        known_directories=tracked_directories(repo_paths),
    )
    structured = parse_structured_answer(messages) if task is not None else None
    route_marker = parse_pkf_route_marker(structured)
    answer = structured.get("answers") if isinstance(structured, dict) else None
    answer_correct = (
        dict(answer) == dict(task.expected_answers)
        if task is not None and isinstance(answer, Mapping)
        else (False if task is not None else None)
    )
    accessed = detect_accessed_paths(event_text, repo_paths)
    implementation_metrics = segment_metrics["implementation"]
    closeout_metrics = segment_metrics["closeout"]
    all_read_paths = explicit_read_paths_for_events(tool_events, repo_paths)
    closeout_read_paths = explicit_read_paths_for_events(segment_events["closeout"], repo_paths)
    allowed_closeout_reads: set[str] = set()
    if route_attempts:
        allowed_closeout_reads.update(route_attempts[0]["affected_leaves"])
        if route_attempts[0]["status"] in {"partial", "unmapped"}:
            allowed_closeout_reads.update(route_attempts[0]["fallback_indexes"])
    unexpected_closeout_reads = {
        path
        for path in closeout_read_paths
        if path not in allowed_closeout_reads
    }
    closeout_validation_calls = sum(
        invoked_script_count(item, "pkf_validate.py")
        for item in segment_events["closeout"]
    )
    initialization_validation_calls = sum(
        invoked_script_count(item, "pkf_validate.py") for item in tool_events
    ) if task_id == "initialize" else 0
    initialization_helper_reads = (
        helper_source_read_paths(tool_events) if task_id == "initialize" else ()
    )
    cross_route_marker_status = "not_applicable"
    cross_route_ids: tuple[str, ...] = ()
    cross_route_unique_leaf_count = 0
    cross_route_fallback: bool | None = None
    cross_configured_documents: tuple[str, ...] = ()
    cross_observed_documents: tuple[str, ...] = ()
    cross_missing_route_ids: tuple[str, ...] = ()
    cross_missing_documents: tuple[str, ...] = ()
    cross_unexpected_documents: tuple[str, ...] = ()
    cross_requirement_count = 0
    cross_covered_requirement_count = 0
    cross_coverage_status = "not_applicable"
    cross_minimality_status = "not_applicable"
    cross_redundant_documents: tuple[str, ...] = ()
    cross_estimated_tokens = 0
    cross_token_estimator = "not_applicable"
    if task_id == "note_task_links" and arm == "pkf":
        cross_route_marker_status = str(route_marker["status"])
        cross_route_ids = tuple(route_marker["route_ids"])
        cross_route_unique_leaf_count = int(route_marker["unique_leaf_count"])
        cross_route_fallback = route_marker["fallback"]
        configured = configured_cross_routes(
            repo,
            cross_route_ids,
        )
        cross_configured_documents = tuple(configured["loads"])
        cross_missing_route_ids = tuple(configured["missing_route_ids"])
        cross_requirement_count = int(configured["requirement_count"])
        cross_covered_requirement_count = int(configured["covered_requirement_count"])
        cross_coverage_status = str(configured["coverage_status"])
        cross_minimality_status = str(configured["minimality_status"])
        cross_redundant_documents = tuple(configured["redundant_loads"])
        cross_estimated_tokens = int(configured["estimated_tokens"])
        cross_token_estimator = str(configured["token_estimator"])
        leaf_reads = {
            path
            for path in all_read_paths
            if path.startswith(".ai/knowledge/") and not path.endswith("/INDEX.md")
        }
        cross_observed_documents = tuple(sorted(leaf_reads))
        cross_missing_documents = tuple(
            sorted(set(cross_configured_documents) - leaf_reads)
        )
        cross_unexpected_documents = tuple(
            sorted(leaf_reads - set(cross_configured_documents))
        )
    changes = changed_paths(repo)
    result = CodexResult(
        repetition=repetition,
        arm=arm,
        task_id=task_id,
        phase=phase,
        returncode=returncode,
        duration_ms=duration_ms,
        usage=usage,
        answer=answer,
        answer_correct=answer_correct,
        accessed_skill=bool(trace.explicit_skill_read_path_count),
        accessed_closeout=any(path.endswith("token-atlas/references/closeout.md") for path in all_read_paths),
        used_route_helper=bool(route_attempts),
        emitted_closeout="pkf closeout:" in "\n".join(messages).lower(),
        retrieval_decision=classify_retrieval_decision(arm=arm, phase=phase, trace=trace),
        fallback_search=trace.fallback_search,
        mentioned_path_count=len(accessed),
        mentioned_ai_path_count=sum(path.startswith(".ai/") for path in accessed),
        tool_call_count=trace.tool_call_count,
        read_or_search_command_count=trace.read_or_search_command_count,
        tool_input_chars=trace.tool_input_chars,
        tool_output_chars=trace.tool_output_chars,
        explicit_read_path_count=trace.explicit_read_path_count,
        explicit_ai_read_path_count=trace.explicit_ai_read_path_count,
        explicit_skill_read_path_count=trace.explicit_skill_read_path_count,
        searched_root_count=trace.searched_root_count,
        ai_read_or_search_command_count=trace.ai_read_or_search_command_count,
        routed_document_count=trace.routed_document_count,
        fallback_invocation_count=trace.fallback_invocation_count,
        changed_path_count=len(changes),
        changed_expected_paths=None,
        focused_test_passed=None,
        pkf_validation_passed=None,
        error=sanitized_error(stderr, (repo, workspace, ROOT)) if returncode else "",
        initial_route_status=str(route_attempts[0]["status"]) if route_attempts else "not_run",
        final_route_status=str(route_attempts[-1]["status"]) if route_attempts else "not_run",
        route_attempt_count=len(route_attempts),
        routing_coverage_defect=bool(route_attempts and route_attempts[0]["routing_coverage_defect"]),
        route_attempts=route_attempts,
        trace_segments={name: asdict(value) for name, value in segment_metrics.items()},
        implementation_explicit_ai_read_path_count=implementation_metrics.explicit_ai_read_path_count,
        implementation_explicit_skill_read_path_count=implementation_metrics.explicit_skill_read_path_count,
        implementation_fallback_search=implementation_metrics.fallback_search,
        closeout_accessed_skill=any(
            "/skills/token-atlas/" in f"/{path}" and path.endswith("/SKILL.md")
            for path in closeout_read_paths
        ),
        closeout_accessed_closeout=any(
            path.endswith("token-atlas/references/closeout.md") for path in closeout_read_paths
        ),
        closeout_fallback_search=closeout_metrics.fallback_search,
        closeout_unexpected_read_path_count=len(unexpected_closeout_reads),
        closeout_unexpected_read_paths=tuple(sorted(unexpected_closeout_reads)),
        closeout_validation_call_count=closeout_validation_calls,
        initialization_validation_call_count=initialization_validation_calls,
        initialization_helper_source_read_count=len(initialization_helper_reads),
        initialization_helper_source_read_paths=initialization_helper_reads,
        route_marker_emitted=route_marker["status"] != "missing",
        cross_route_marker_status=cross_route_marker_status,
        cross_route_ids=cross_route_ids,
        cross_route_unique_leaf_count=cross_route_unique_leaf_count,
        cross_route_fallback=cross_route_fallback,
        cross_configured_document_paths=cross_configured_documents,
        cross_observed_document_paths=cross_observed_documents,
        cross_missing_route_ids=cross_missing_route_ids,
        cross_missing_document_paths=cross_missing_documents,
        cross_unexpected_document_paths=cross_unexpected_documents,
        cross_requirement_count=cross_requirement_count,
        cross_covered_requirement_count=cross_covered_requirement_count,
        cross_coverage_status=cross_coverage_status,
        cross_minimality_status=cross_minimality_status,
        cross_redundant_document_paths=cross_redundant_documents,
        cross_estimated_tokens=cross_estimated_tokens,
        cross_token_estimator=cross_token_estimator,
    )
    if artifacts is not None:
        artifacts.record_call(
            result=result,
            stdout=stdout,
            stderr=stderr,
            schema_path=schema_path,
            repo=repo,
            workspace=workspace,
        )
    return result, event_text


def replace_result(result: CodexResult, **updates: Any) -> CodexResult:
    values = asdict(result)
    values.update(updates)
    if isinstance(values.get("usage"), dict):
        values["usage"] = Usage(**values["usage"])
    return CodexResult(**values)


def validate_pkf(repo: Path) -> tuple[bool, str]:
    validator = repo / ".ai" / "tools" / "pkf_validate.py"
    if not validator.is_file():
        return False, "repository-local validator is missing"
    completed = run_command(
        (
            sys.executable,
            "-S",
            str(validator),
            "--path",
            ".ai",
            "--strictness",
            "ci",
            "--format",
            "json",
        ),
        cwd=repo,
        check=False,
    )
    output = "\n".join(value for value in (completed.stdout.strip(), completed.stderr.strip()) if value)
    return completed.returncode == 0, output[-10_000:]


def probe_route_coverage(repo: Path, paths: Sequence[str]) -> tuple[str, tuple[str, ...], str]:
    helper = repo / ".ai" / "tools" / "pkf_route.py"
    if not helper.is_file():
        return "invalid", tuple(paths), "repository-local route helper is missing"
    command = [sys.executable, "-S", str(helper), "--path", "."]
    for path in paths:
        command.extend(("--changed-path", path))
    command.extend(("--format", "json"))
    completed = run_command(command, cwd=repo, check=False)
    if completed.returncode != 0:
        return "invalid", tuple(paths), completed.stdout + completed.stderr
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return "invalid", tuple(paths), completed.stdout
    return (
        str(result.get("status", "invalid")),
        tuple(str(value) for value in result.get("unmatched_paths", []) if isinstance(value, str)),
        completed.stdout,
    )


def pkf_materialization_inventory(repo: Path) -> dict[str, int]:
    inventory = {"materialized_leaf_count": 0, "pending_leaf_count": 0, "unknown_leaf_count": 0}
    knowledge = repo / ".ai" / "knowledge"
    if not knowledge.is_dir():
        return inventory
    for path in knowledge.rglob("*.md"):
        if path.name == "INDEX.md":
            continue
        header = path.read_text(encoding="utf-8", errors="replace")[:8_192]
        match = re.search(r"(?m)^\s*materialization:\s*(complete|pending)\s*$", header)
        if match is None:
            inventory["unknown_leaf_count"] += 1
        elif match.group(1) == "complete":
            inventory["materialized_leaf_count"] += 1
        else:
            inventory["pending_leaf_count"] += 1
    return inventory


def run_focused_test(repo: Path) -> bool:
    completed = run_command(
        ("npm", "run", "test", "--prefix", "frontend", "--", "noteSectionState.test.ts"),
        cwd=repo,
        check=False,
        timeout=600,
    )
    return completed.returncode == 0


def prepare_closeout_arms(workspace: Path, arms: Mapping[str, Path]) -> dict[str, Path]:
    prepared: dict[str, Path] = {}
    for arm in ("probe_only", "pkf"):
        destination = workspace / f"{arm}-isolated-closeout"
        shutil.copytree(arms[arm], destination, symlinks=True)
        completed = run_command(
            ("git", "apply", str(ISOLATED_CLOSEOUT_PATCH)),
            cwd=destination,
            check=False,
        )
        if completed.returncode != 0:
            raise EvaluationError(f"isolated closeout patch did not apply to {arm}: {completed.stderr.strip()}")
        if not run_focused_test(destination):
            raise EvaluationError(f"isolated closeout patch failed focused test in {arm}")
        prepared[arm] = destination
    return prepared


def score_closeout(
    result: CodexResult,
    repo: Path,
    arm: str,
    artifacts: ArtifactStore | None = None,
) -> CodexResult:
    changes = changed_paths(repo)
    expected = {
        "frontend/src/notes/noteSectionState.ts",
        "frontend/src/notes/noteSectionState.test.ts",
    }
    valid: bool | None = None
    if arm == "pkf":
        valid, validation_output = validate_pkf(repo)
        if artifacts is not None:
            label = f"r{result.repetition}-{result.task_id}"
            artifacts.record_validation(label, passed=valid, output=validation_output)
            artifacts.snapshot_pkf(label, repo)
    return replace_result(
        result,
        changed_path_count=len(changes),
        changed_expected_paths=expected.issubset(changes),
        focused_test_passed=True,
        pkf_validation_passed=valid,
    )


def score_mutation(
    result: CodexResult,
    repo: Path,
    arm: str,
    artifacts: ArtifactStore | None = None,
) -> CodexResult:
    changes = changed_paths(repo)
    expected_source = "frontend/src/notes/noteSectionState.ts" in changes
    expected_test = "frontend/src/notes/noteSectionState.test.ts" in changes
    focused_test_passed = run_focused_test(repo)
    pkf_validation_passed: bool | None = None
    if arm == "pkf":
        pkf_validation_passed, validation_output = validate_pkf(repo)
        if artifacts is not None:
            label = f"r{result.repetition}-{result.task_id}"
            artifacts.record_validation(
                label,
                passed=pkf_validation_passed,
                output=validation_output,
            )
            artifacts.snapshot_pkf(label, repo)
    return replace_result(
        result,
        changed_path_count=len(changes),
        changed_expected_paths=expected_source and expected_test,
        focused_test_passed=focused_test_passed,
        pkf_validation_passed=pkf_validation_passed,
    )


def three_arm_order(repetition: int) -> tuple[str, ...]:
    orders = (
        ("source_only", "probe_only", "pkf"),
        ("probe_only", "pkf", "source_only"),
        ("pkf", "source_only", "probe_only"),
    )
    return orders[(repetition - 1) % len(orders)]


def two_arm_order(repetition: int) -> tuple[str, ...]:
    return ("probe_only", "pkf") if repetition % 2 else ("pkf", "probe_only")


def build_schedule(repetitions: int, suite: str = "lifecycle") -> list[dict[str, Any]]:
    if suite not in EVALUATION_SUITES:
        raise EvaluationError(f"unknown evaluation suite: {suite}")
    schedule: list[dict[str, Any]] = []
    for repetition in range(1, repetitions + 1):
        schedule.append({"repetition": repetition, "arm": "pkf", "task_id": "initialize", "phase": "setup"})
        if suite in {"retrieval", "all"}:
            for task in READ_ONLY_TASKS:
                for arm in three_arm_order(repetition):
                    schedule.append({"repetition": repetition, "arm": arm, "task_id": task.task_id, "phase": "retrieval"})
        if suite == "regression":
            cross_task = next(task for task in READ_ONLY_TASKS if task.task_id == "note_task_links")
            for arm in two_arm_order(repetition):
                schedule.append(
                    {
                        "repetition": repetition,
                        "arm": arm,
                        "task_id": cross_task.task_id,
                        "phase": "retrieval",
                    }
                )
        if suite in {"lifecycle", "all"}:
            for arm in two_arm_order(repetition):
                schedule.append({"repetition": repetition, "arm": arm, "task_id": "favorite_visibility_mutation", "phase": "mutation"})
            for arm in two_arm_order(repetition):
                schedule.append({"repetition": repetition, "arm": arm, "task_id": POST_MUTATION_TASK.task_id, "phase": "post_mutation"})
        if suite in {"closeout", "regression", "all"}:
            for arm in two_arm_order(repetition):
                schedule.append({"repetition": repetition, "arm": arm, "task_id": "isolated_closeout", "phase": "closeout"})
    return schedule


def median(values: Sequence[int | float]) -> float:
    return float(statistics.median(values)) if values else 0.0


def run_class(repetitions: int) -> str:
    if repetitions == 1:
        return "one_pass_preflight"
    if repetitions >= 3:
        return "replicated"
    return "diagnostic"


def usage_value(result: CodexResult, metric: str) -> int | None:
    if result.usage is None:
        return None
    return int(getattr(result.usage, metric))


def aggregate_metrics(results: Sequence[CodexResult]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[CodexResult]] = {}
    for result in results:
        groups.setdefault((result.task_id, result.arm), []).append(result)
    by_task: dict[str, Any] = {}
    usage_metrics = (
        "input_tokens",
        "cached_input_tokens",
        "non_cached_input_tokens",
        "output_tokens",
    )
    trace_metrics = (
        "tool_call_count",
        "read_or_search_command_count",
        "tool_input_chars",
        "tool_output_chars",
        "explicit_read_path_count",
        "explicit_ai_read_path_count",
        "explicit_skill_read_path_count",
        "searched_root_count",
        "ai_read_or_search_command_count",
        "routed_document_count",
        "fallback_invocation_count",
        "mentioned_path_count",
        "mentioned_ai_path_count",
    )
    attribution_metrics = (
        "closeout_unexpected_read_path_count",
        "closeout_validation_call_count",
        "initialization_validation_call_count",
        "initialization_helper_source_read_count",
    )
    for (task_id, arm), grouped in sorted(groups.items()):
        entry = {
            metric: median(
                [value for result in grouped if (value := usage_value(result, metric)) is not None]
            )
            for metric in usage_metrics
        }
        entry["duration_ms"] = median([result.duration_ms for result in grouped])
        for trace_metric in trace_metrics:
            entry[trace_metric] = median(
                [getattr(result, trace_metric) for result in grouped]
            )
        for attribution_metric in attribution_metrics:
            entry[attribution_metric] = median(
                [getattr(result, attribution_metric) for result in grouped]
            )
        scored = [result for result in grouped if result.answer_correct is not None]
        entry["correctness_rate"] = (
            sum(result.answer_correct is True for result in scored) / len(scored)
            if scored
            else None
        )
        entry["retrieval_decisions"] = {
            decision: sum(result.retrieval_decision == decision for result in grouped)
            for decision in ("activated", "bypassed", "not_applicable")
        }
        entry["initial_route_statuses"] = {
            status: sum(result.initial_route_status == status for result in grouped)
            for status in ("mapped", "partial", "unmapped", "not_run", "invalid")
        }
        if task_id == "note_task_links" and arm == "pkf":
            entry["cross_route_count"] = median(
                [len(result.cross_route_ids) for result in grouped]
            )
            entry["cross_unique_leaf_count"] = median(
                [result.cross_route_unique_leaf_count for result in grouped]
            )
            entry["cross_requirement_count"] = median(
                [result.cross_requirement_count for result in grouped]
            )
            entry["cross_covered_requirement_count"] = median(
                [result.cross_covered_requirement_count for result in grouped]
            )
            entry["cross_redundant_leaf_count"] = median(
                [len(result.cross_redundant_document_paths) for result in grouped]
            )
            entry["cross_estimated_tokens"] = median(
                [result.cross_estimated_tokens for result in grouped]
            )
            entry["cross_coverage_statuses"] = {
                status: sum(result.cross_coverage_status == status for result in grouped)
                for status in ("complete", "incomplete", "unknown")
            }
            entry["cross_minimality_statuses"] = {
                status: sum(result.cross_minimality_status == status for result in grouped)
                for status in ("minimal", "redundant", "invalid", "unknown")
            }
            entry["cross_fallback_rate"] = (
                sum(result.cross_route_fallback is True for result in grouped) / len(grouped)
            )
        segmented = [result.trace_segments for result in grouped if result.trace_segments]
        if segmented:
            entry["trace_segments"] = {
                segment: {
                    metric: median(
                        [
                            float(value[segment][metric])
                            for value in segmented
                            if segment in value and metric in value[segment]
                        ]
                    )
                    for metric in (
                        "tool_call_count",
                        "read_or_search_command_count",
                        "explicit_read_path_count",
                        "explicit_ai_read_path_count",
                        "explicit_skill_read_path_count",
                        "routed_document_count",
                        "fallback_invocation_count",
                    )
                } | {
                    "fallback_rate": (
                        sum(bool(value[segment].get("fallback_search")) for value in segmented if segment in value)
                        / sum(segment in value for value in segmented)
                    )
                }
                for segment in ("implementation", "routing", "closeout")
            }
        by_task.setdefault(task_id, {})[arm] = entry

    sum_metrics = (*usage_metrics, "duration_ms", *trace_metrics, *attribution_metrics)
    operational_by_repetition: list[dict[str, Any]] = []
    for repetition in sorted({result.repetition for result in results}):
        repeated = [result for result in results if result.repetition == repetition]
        has_integrated_mutation = any(
            result.task_id == "favorite_visibility_mutation" for result in repeated
        )
        entry: dict[str, Any] = {"repetition": repetition}
        for arm in ("source_only", "probe_only", "pkf"):
            arm_results = [
                result
                for result in repeated
                if result.arm == arm
                and result.phase != "setup"
                and not (has_integrated_mutation and result.phase == "closeout")
            ]
            entry[arm] = {
                metric: sum(
                    (
                        usage_value(result, metric)
                        if metric in usage_metrics
                        else getattr(result, metric)
                    )
                    or 0
                    for result in arm_results
                )
                for metric in sum_metrics
            }
        operational_by_repetition.append(entry)

    lifecycle_phase_costs: list[dict[str, Any]] = []
    phase_cost_metrics = (*usage_metrics, "duration_ms", *trace_metrics)
    for repetition in sorted({result.repetition for result in results}):
        by_key = {
            (result.task_id, result.arm): result
            for result in results
            if result.repetition == repetition
        }
        required = {
            ("favorite_visibility_mutation", "probe_only"),
            ("favorite_visibility_mutation", "pkf"),
            ("isolated_closeout", "probe_only"),
            ("isolated_closeout", "pkf"),
        }
        if not required.issubset(by_key):
            continue
        implementation = by_key[("favorite_visibility_mutation", "probe_only")]
        integrated = by_key[("favorite_visibility_mutation", "pkf")]
        closeout_control = by_key[("isolated_closeout", "probe_only")]
        closeout = by_key[("isolated_closeout", "pkf")]

        def metric_value(result: CodexResult, metric: str) -> int:
            if metric in usage_metrics:
                return usage_value(result, metric) or 0
            return int(getattr(result, metric))

        lifecycle_phase_costs.append(
            {
                "repetition": repetition,
                "implementation": {
                    metric: metric_value(implementation, metric) for metric in phase_cost_metrics
                },
                "closeout": {metric: metric_value(closeout, metric) for metric in phase_cost_metrics},
                "closeout_control": {
                    metric: metric_value(closeout_control, metric) for metric in phase_cost_metrics
                },
                "closeout_incremental": {
                    metric: metric_value(closeout, metric) - metric_value(closeout_control, metric)
                    for metric in phase_cost_metrics
                },
                "composed_probe_plus_closeout": {
                    metric: metric_value(implementation, metric) + metric_value(closeout, metric)
                    for metric in phase_cost_metrics
                },
                "integrated_observed": {
                    metric: metric_value(integrated, metric) for metric in phase_cost_metrics
                },
            }
        )

    lifecycle_phase_summary = {
        phase: {
            metric: median([entry[phase][metric] for entry in lifecycle_phase_costs])
            for metric in phase_cost_metrics
        }
        for phase in (
            "implementation",
            "closeout",
            "closeout_control",
            "closeout_incremental",
            "composed_probe_plus_closeout",
            "integrated_observed",
        )
    } if lifecycle_phase_costs else {}

    activated_savings: dict[str, list[float]] = {metric: [] for metric in usage_metrics}
    bypassed_deltas: dict[str, dict[str, list[float]]] = {}
    for repetition in sorted({result.repetition for result in results}):
        for task_id in {task.task_id for task in (*READ_ONLY_TASKS, POST_MUTATION_TASK)}:
            result_by_arm = {
                result.arm: result
                for result in results
                if result.repetition == repetition and result.task_id == task_id
            }
            if not {"probe_only", "pkf"}.issubset(result_by_arm):
                continue
            decision = result_by_arm["pkf"].retrieval_decision
            for metric in usage_metrics:
                baseline = usage_value(result_by_arm["probe_only"], metric)
                candidate = usage_value(result_by_arm["pkf"], metric)
                if baseline is not None and candidate is not None:
                    if decision == "activated":
                        activated_savings[metric].append(float(baseline - candidate))
                    elif decision == "bypassed":
                        bypassed_deltas.setdefault(task_id, {}).setdefault(metric, []).append(
                            float(candidate - baseline)
                        )

    comparisons: dict[str, Any] = {}
    for task_id, arm_values in by_task.items():
        task_comparisons: dict[str, Any] = {}
        for label, baseline_arm, candidate_arm in (
            ("source_vs_probe", "source_only", "probe_only"),
            ("probe_vs_pkf", "probe_only", "pkf"),
        ):
            if baseline_arm not in arm_values or candidate_arm not in arm_values:
                continue
            comparison: dict[str, Any] = {}
            for metric in (*usage_metrics, "duration_ms", *trace_metrics):
                baseline = float(arm_values[baseline_arm][metric])
                candidate = float(arm_values[candidate_arm][metric])
                comparison[metric] = {
                    "baseline": baseline,
                    "candidate": candidate,
                    "delta": candidate - baseline,
                    "percent": ((candidate - baseline) / baseline * 100.0) if baseline else None,
                }
            task_comparisons[label] = comparison
        comparisons[task_id] = task_comparisons

    break_even: dict[str, int | None] = {}
    for metric in ("input_tokens", "non_cached_input_tokens"):
        per_read_saving = median(activated_savings[metric])
        init_cost = median(
            [
                value
                for result in results
                if result.arm == "pkf"
                and result.task_id == "initialize"
                and (value := usage_value(result, metric)) is not None
            ]
        )
        closeout = comparisons.get("isolated_closeout", {}).get("probe_vs_pkf", {}).get(metric, {})
        mutation_premium = max(0.0, float(closeout.get("delta", 0.0)))
        break_even[metric] = (
            math.ceil((init_cost + mutation_premium) / per_read_saving)
            if per_read_saving > 0
            else None
        )

    return {
        "by_task": by_task,
        "comparisons": comparisons,
        "operational_by_repetition": operational_by_repetition,
        "lifecycle_phase_costs_by_repetition": lifecycle_phase_costs,
        "lifecycle_phase_cost_summary": lifecycle_phase_summary,
        "activated_pkf_knowledge_savings": {
            "paired_count": len(activated_savings["input_tokens"]),
            **{metric: median(values) for metric, values in activated_savings.items()},
        },
        "bypassed_pkf_environment_deltas": {
            task_id: {
                "paired_count": len(metric_values.get("input_tokens", [])),
                **{metric: median(values) for metric, values in metric_values.items()},
            }
            for task_id, metric_values in sorted(bypassed_deltas.items())
        },
        "break_even_activated_tasks": break_even,
    }


def performance_advisories(metrics: Mapping[str, Any], repetitions: int) -> dict[str, Any]:
    comparisons = metrics.get("comparisons", {})
    phases: dict[str, dict[str, Any]] = {
        "local_bypass": {
            "purpose": "PKF-inactive local work should remain near probe-only cost.",
            "checks": [],
            "measurements": {},
        },
        "cross_retrieval": {
            "purpose": "Activated PKF should replace broad cross-capability discovery.",
            "checks": [],
            "measurements": {},
        },
        "mutation_implementation": {
            "purpose": "Implementation stays source-first; closeout cost is attributed separately.",
            "checks": [],
            "measurements": {},
        },
        "closeout": {
            "purpose": "Required knowledge maintenance is measured as a maintenance premium.",
            "checks": [],
            "measurements": {},
        },
        "initialization": {
            "purpose": "One-time setup is reported for coverage and runaway detection, not historical cost parity.",
            "checks": [],
            "measurements": {},
        },
        "amortization": {
            "purpose": "Break-even estimates relate setup and maintenance premiums to activated retrieval savings.",
            "checks": [],
            "measurements": {},
        },
    }

    def add_check(
        phase: str,
        name: str,
        value: float | None,
        target: str,
        met: bool | None,
    ) -> None:
        phases[phase]["checks"].append(
            {"phase": phase, "name": name, "value": value, "target": target, "met": met}
        )

    for task_id in ("boards_add_task", POST_MUTATION_TASK.task_id):
        local = comparisons.get(task_id, {}).get("probe_vs_pkf", {})
        if not local:
            continue
        for metric in ("non_cached_input_tokens", "duration_ms", "tool_call_count"):
            value = local.get(metric, {}).get("percent")
            add_check(
                "local_bypass",
                f"{task_id}_{metric}_overhead",
                value,
                "<= 5%",
                value is not None and value <= 5.0,
            )
        phases["local_bypass"]["measurements"][task_id] = {
            metric: local.get(metric, {})
            for metric in ("input_tokens", "non_cached_input_tokens", "duration_ms", "tool_call_count")
        }
    cross = comparisons.get("note_task_links", {}).get("probe_vs_pkf", {})
    if cross:
        non_cached_delta = cross.get("non_cached_input_tokens", {}).get("delta")
        add_check(
            "cross_retrieval",
            "cross_capability_non_cached_input_tokens_delta",
            non_cached_delta,
            "< 0",
            non_cached_delta is not None and non_cached_delta < 0,
        )
        tool_delta = cross.get("tool_call_count", {}).get("delta")
        add_check(
            "cross_retrieval",
            "cross_capability_tool_call_delta",
            tool_delta,
            "< 0",
            tool_delta is not None and tool_delta < 0,
        )
        pkf_cross = metrics.get("by_task", {}).get("note_task_links", {}).get("pkf", {})
        phases["cross_retrieval"]["measurements"] = {
            "input_tokens": cross.get("input_tokens", {}),
            "non_cached_input_tokens": cross.get("non_cached_input_tokens", {}),
            "output_tokens": cross.get("output_tokens", {}),
            "duration_ms": cross.get("duration_ms", {}),
            "tool_call_count": cross.get("tool_call_count", {}),
            "routed_document_count": float(pkf_cross.get("routed_document_count", 0)),
            "route_count": float(pkf_cross.get("cross_route_count", 0)),
            "unique_leaf_count": float(pkf_cross.get("cross_unique_leaf_count", 0)),
            "requirement_count": float(pkf_cross.get("cross_requirement_count", 0)),
            "covered_requirement_count": float(pkf_cross.get("cross_covered_requirement_count", 0)),
            "redundant_leaf_count": float(pkf_cross.get("cross_redundant_leaf_count", 0)),
            "estimated_route_tokens": float(pkf_cross.get("cross_estimated_tokens", 0)),
            "fallback_rate": float(pkf_cross.get("cross_fallback_rate", 0)),
        }
    initialized = metrics.get("by_task", {}).get("initialize", {}).get("pkf", {})
    if initialized:
        phases["initialization"]["measurements"] = {
            metric: float(initialized.get(metric, 0))
            for metric in (
                "input_tokens",
                "non_cached_input_tokens",
                "output_tokens",
                "duration_ms",
                "tool_call_count",
                "initialization_validation_call_count",
                "initialization_helper_source_read_count",
                "fallback_invocation_count",
            )
        }
    isolated_closeout = metrics.get("by_task", {}).get("isolated_closeout", {}).get("pkf", {})
    if isolated_closeout:
        tool_calls = float(isolated_closeout.get("tool_call_count", 0))
        mapped_count = isolated_closeout.get("initial_route_statuses", {}).get("mapped", 0)
        if mapped_count:
            add_check(
                "closeout",
                "mapped_closeout_tool_calls",
                tool_calls,
                "<= 6",
                tool_calls <= 6,
            )
    phase_costs = metrics.get("lifecycle_phase_cost_summary", {})
    if phase_costs:
        phases["mutation_implementation"]["measurements"] = {
            "implementation": phase_costs["implementation"],
            "integrated_observed": phase_costs["integrated_observed"],
        }
        phases["closeout"]["measurements"] = {
            "closeout": phase_costs["closeout"],
            "closeout_control": phase_costs["closeout_control"],
            "closeout_incremental": phase_costs["closeout_incremental"],
            "composed_probe_plus_closeout": phase_costs["composed_probe_plus_closeout"],
        }
    phases["amortization"]["measurements"] = {
        "break_even_activated_tasks": metrics.get("break_even_activated_tasks", {})
    }

    checks = [check for phase in phases.values() for check in phase["checks"]]
    for phase in phases.values():
        phase_checks = phase["checks"]
        if phase_checks:
            base = "met" if all(check["met"] for check in phase_checks) else "missed"
            phase["status"] = f"directional_{base}" if repetitions < 3 else f"replicated_{base}"
        elif phase["measurements"]:
            phase["status"] = "measured"
        else:
            phase["status"] = "not_measured"
    return {
        "status": "preliminary" if repetitions < 3 else "reported",
        "evidence_strength": "replicated" if repetitions >= 3 else "directional",
        "phases": phases,
        "checks": checks,
    }


def public_result(result: CodexResult) -> dict[str, Any]:
    value = asdict(result)
    value.pop("answer", None)
    return value


def evaluation_errors(results: Sequence[CodexResult], expected_count: int) -> list[str]:
    errors: list[str] = []
    if len(results) != expected_count:
        errors.append(f"expected {expected_count} calls but recorded {len(results)}")
    for result in results:
        label = f"repetition {result.repetition} {result.arm}/{result.task_id}"
        if result.returncode != 0:
            errors.append(f"{label}: Codex exit {result.returncode}")
        if result.usage is None:
            errors.append(f"{label}: missing token usage")
        if result.answer_correct is False:
            errors.append(f"{label}: incorrect structured answer")
        if result.task_id == "initialize" and result.pkf_validation_passed is not True:
            errors.append(f"{label}: initialized PKF failed strict validation")
        if result.task_id == "initialize" and result.initialization_validation_call_count != 1:
            errors.append(
                f"{label}: initialization must run exactly one explicit post-extraction validation "
                f"(observed {result.initialization_validation_call_count})"
            )
        if result.task_id == "initialize" and result.initialization_helper_source_read_count:
            paths = ", ".join(result.initialization_helper_source_read_paths)
            errors.append(f"{label}: initialization read opaque helper source: {paths}")
        if result.task_id == "initialize" and result.fallback_invocation_count > 1:
            errors.append(
                f"{label}: initialization repeated broad repository scans "
                f"({result.fallback_invocation_count} fallback-style invocations)"
            )
        if result.task_id == "initialize" and result.initialization_route_status != "mapped":
            unmatched = ", ".join(result.initialization_unmatched_paths) or "unknown paths"
            errors.append(
                f"{label}: initialization routing-coverage defect; public mutation paths were "
                f"{result.initialization_route_status}: {unmatched}"
            )
        if result.task_id in {"boards_add_task", POST_MUTATION_TASK.task_id}:
            if result.explicit_ai_read_path_count or result.explicit_skill_read_path_count:
                errors.append(f"{label}: local task explicitly read PKF or Token Atlas paths")
            if result.arm == "pkf" and result.retrieval_decision != "bypassed":
                errors.append(f"{label}: local PKF task was not classified as bypassed")
            if result.route_marker_emitted:
                errors.append(f"{label}: bypassed local task emitted a PKF route marker")
        if result.arm != "pkf" and result.route_marker_emitted:
            errors.append(f"{label}: non-PKF arm emitted a PKF route marker")
        if result.task_id == "note_task_links" and result.arm == "pkf":
            if result.explicit_ai_read_path_count < 1:
                errors.append(f"{label}: cross-capability task did not activate PKF retrieval")
            if result.retrieval_decision != "activated":
                errors.append(f"{label}: cross-capability PKF task was not classified as activated")
            if result.explicit_skill_read_path_count:
                errors.append(f"{label}: cross-capability retrieval loaded Token Atlas workflow instructions")
            if result.cross_route_marker_status != "valid":
                errors.append(
                    f"{label}: cross-capability retrieval route marker was "
                    f"{result.cross_route_marker_status}"
                )
            if not result.cross_route_ids:
                errors.append(f"{label}: cross-capability retrieval selected no keyed routes")
            if result.cross_missing_route_ids:
                route_ids = ", ".join(result.cross_missing_route_ids)
                errors.append(f"{label}: route marker named undefined routes: {route_ids}")
            if result.cross_coverage_status != "complete":
                errors.append(
                    f"{label}: configured route requirement coverage is {result.cross_coverage_status}"
                )
            if result.cross_minimality_status != "minimal":
                errors.append(
                    f"{label}: configured route minimality is {result.cross_minimality_status}"
                )
            if result.cross_redundant_document_paths:
                paths = ", ".join(result.cross_redundant_document_paths)
                errors.append(f"{label}: configured route contains redundant leaves: {paths}")
            if not result.cross_configured_document_paths:
                errors.append(f"{label}: selected routes configured no leaf documents")
            if result.cross_route_unique_leaf_count != len(result.cross_configured_document_paths):
                errors.append(
                    f"{label}: route marker reported {result.cross_route_unique_leaf_count} unique leaves "
                    f"but configuration resolves {len(result.cross_configured_document_paths)}"
                )
            if result.cross_route_fallback is not False or result.fallback_search:
                errors.append(f"{label}: configured cross-capability retrieval used fallback discovery")
            if result.cross_missing_document_paths:
                paths = ", ".join(result.cross_missing_document_paths)
                errors.append(f"{label}: cross-capability retrieval skipped configured leaves: {paths}")
            if result.cross_unexpected_document_paths:
                paths = ", ".join(result.cross_unexpected_document_paths)
                errors.append(f"{label}: cross-capability retrieval read outside its explicit route: {paths}")
        if result.task_id == "favorite_visibility_mutation":
            if result.changed_expected_paths is not True:
                errors.append(f"{label}: mutation did not make the expected source/test change")
            if result.focused_test_passed is not True:
                errors.append(f"{label}: focused frontend test failed")
            if result.arm == "pkf":
                if result.implementation_explicit_ai_read_path_count or result.implementation_explicit_skill_read_path_count:
                    errors.append(f"{label}: implementation phase activated PKF or Token Atlas before routing")
                if result.pkf_validation_passed is not True:
                    errors.append(f"{label}: PKF failed validation after mutation")
                if not result.emitted_closeout:
                    errors.append(f"{label}: mutation did not emit PKF closeout status")
                if not result.used_route_helper:
                    errors.append(f"{label}: mutation closeout did not use the changed-path route helper")
                if result.initial_route_status == "mapped":
                    if result.route_attempt_count != 1:
                        errors.append(f"{label}: mapped mutation closeout must route exactly once")
                    if result.closeout_accessed_skill or result.closeout_accessed_closeout:
                        errors.append(f"{label}: mapped mutation closeout loaded Token Atlas workflow instructions")
                    if result.closeout_fallback_search:
                        errors.append(f"{label}: mapped mutation closeout used fallback discovery")
                    if result.closeout_unexpected_read_path_count:
                        paths = ", ".join(result.closeout_unexpected_read_paths)
                        errors.append(
                            f"{label}: mapped mutation closeout read paths outside returned leaves: {paths}"
                        )
                    if result.closeout_validation_call_count != 1:
                        errors.append(f"{label}: mapped mutation closeout must run exactly one validation")
                elif result.initial_route_status in {"partial", "unmapped"}:
                    errors.append(
                        f"{label}: mutation routing-coverage defect; initial route was {result.initial_route_status}"
                    )
        if result.task_id == "isolated_closeout":
            if result.arm == "pkf":
                if result.implementation_explicit_ai_read_path_count or result.implementation_explicit_skill_read_path_count:
                    errors.append(f"{label}: isolated closeout loaded PKF or Token Atlas before routing")
                if result.pkf_validation_passed is not True:
                    errors.append(f"{label}: isolated closeout left PKF invalid")
                if not result.emitted_closeout:
                    errors.append(f"{label}: isolated closeout did not emit status")
                if not result.used_route_helper:
                    errors.append(f"{label}: isolated closeout did not use the changed-path route helper")
                if result.initial_route_status == "mapped":
                    if result.route_attempt_count != 1:
                        errors.append(f"{label}: mapped isolated closeout must route exactly once")
                    if result.closeout_accessed_skill or result.closeout_accessed_closeout:
                        errors.append(f"{label}: mapped isolated closeout loaded Token Atlas workflow instructions")
                    if result.closeout_fallback_search:
                        errors.append(f"{label}: mapped isolated closeout used fallback discovery")
                    if result.closeout_unexpected_read_path_count:
                        paths = ", ".join(result.closeout_unexpected_read_paths)
                        errors.append(
                            f"{label}: mapped isolated closeout read paths outside returned leaves: {paths}"
                        )
                    if result.closeout_validation_call_count != 1:
                        errors.append(f"{label}: mapped isolated closeout must run exactly one validation")
                elif result.initial_route_status in {"partial", "unmapped"}:
                    errors.append(
                        f"{label}: isolated closeout routing-coverage defect; initial route was {result.initial_route_status}"
                    )
            elif result.explicit_ai_read_path_count or result.explicit_skill_read_path_count:
                errors.append(f"{label}: closeout control accessed PKF or Token Atlas paths")
    return errors


def execute(
    args: argparse.Namespace,
    target: Mapping[str, str],
    artifacts: ArtifactStore,
) -> dict[str, Any]:
    runtime_root = args.runtime_root.resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    results: list[CodexResult] = []
    initialization_inventories: list[dict[str, int]] = []
    for repetition in range(1, args.repetitions + 1):
        with tempfile.TemporaryDirectory(
            prefix=f".pkf-savings-{repetition}-",
            dir=runtime_root,
        ) as raw_workspace:
            workspace = Path(raw_workspace)
            arms = prepare_arms(
                workspace,
                target_repo=args.target_repo.resolve(),
                target_commit=target["commit"],
            )

            print(
                f"[{repetition}/{args.repetitions}] pkf initialize",
                file=sys.stderr,
                flush=True,
            )
            init_result, _ = run_codex(
                repetition=repetition,
                arm="pkf",
                task_id="initialize",
                phase="setup",
                prompt=INITIALIZE_PROMPT,
                repo=arms["pkf"],
                model=args.model,
                reasoning_effort=args.model_reasoning_effort,
                timeout_seconds=args.timeout_seconds,
                workspace=workspace,
                sandbox="workspace-write",
                artifacts=artifacts,
            )
            init_valid, validation_error = validate_pkf(arms["pkf"])
            route_status, unmatched_paths, route_output = probe_route_coverage(
                arms["pkf"], MUTATION_PATHS
            )
            init_result = replace_result(
                init_result,
                pkf_validation_passed=init_valid,
                initialization_route_status=route_status,
                initialization_unmatched_paths=unmatched_paths,
                error=init_result.error or sanitized_error(
                    validation_error,
                    (arms["pkf"], workspace, ROOT),
                ),
            )
            results.append(init_result)
            inventory = pkf_materialization_inventory(arms["pkf"])
            initialization_inventories.append({"repetition": repetition, **inventory})
            artifacts.record_validation(
                f"r{repetition}-initialize",
                passed=init_valid,
                output=validation_error,
            )
            artifacts.record_validation(
                f"r{repetition}-initialize-route-coverage",
                passed=route_status == "mapped",
                output=route_output,
            )
            artifacts.snapshot_pkf(f"r{repetition}-initialize", arms["pkf"])
            if init_result.returncode == 0 and init_valid:
                commit_generated_pkf(arms["pkf"])

            closeout_arms = (
                prepare_closeout_arms(workspace, arms)
                if args.suite in {"closeout", "regression", "all"}
                else {}
            )

            if args.suite in {"retrieval", "all"}:
                for task in READ_ONLY_TASKS:
                    for arm in three_arm_order(repetition):
                        print(f"[{repetition}/{args.repetitions}] {arm} {task.task_id}", file=sys.stderr, flush=True)
                        result, _ = run_codex(
                            repetition=repetition,
                            arm=arm,
                            task_id=task.task_id,
                            phase="retrieval",
                            prompt=task.prompt,
                            repo=arms[arm],
                            model=args.model,
                            reasoning_effort=args.model_reasoning_effort,
                            timeout_seconds=args.timeout_seconds,
                            workspace=workspace,
                            sandbox="read-only",
                            task=task,
                            artifacts=artifacts,
                        )
                        results.append(result)

            if args.suite == "regression":
                task = next(task for task in READ_ONLY_TASKS if task.task_id == "note_task_links")
                for arm in two_arm_order(repetition):
                    print(
                        f"[{repetition}/{args.repetitions}] {arm} {task.task_id}",
                        file=sys.stderr,
                        flush=True,
                    )
                    result, _ = run_codex(
                        repetition=repetition,
                        arm=arm,
                        task_id=task.task_id,
                        phase="retrieval",
                        prompt=task.prompt,
                        repo=arms[arm],
                        model=args.model,
                        reasoning_effort=args.model_reasoning_effort,
                        timeout_seconds=args.timeout_seconds,
                        workspace=workspace,
                        sandbox="read-only",
                        task=task,
                        artifacts=artifacts,
                    )
                    results.append(result)

            if args.suite in {"lifecycle", "all"}:
                for arm in two_arm_order(repetition):
                    print(f"[{repetition}/{args.repetitions}] {arm} favorite_visibility_mutation", file=sys.stderr, flush=True)
                    result, _ = run_codex(
                        repetition=repetition,
                        arm=arm,
                        task_id="favorite_visibility_mutation",
                        phase="mutation",
                        prompt=MUTATION_PROMPT,
                        repo=arms[arm],
                        model=args.model,
                        reasoning_effort=args.model_reasoning_effort,
                        timeout_seconds=args.timeout_seconds,
                        workspace=workspace,
                        sandbox="workspace-write",
                        artifacts=artifacts,
                    )
                    results.append(score_mutation(result, arms[arm], arm, artifacts))

                for arm in two_arm_order(repetition):
                    print(f"[{repetition}/{args.repetitions}] {arm} {POST_MUTATION_TASK.task_id}", file=sys.stderr, flush=True)
                    result, _ = run_codex(
                        repetition=repetition,
                        arm=arm,
                        task_id=POST_MUTATION_TASK.task_id,
                        phase="post_mutation",
                        prompt=POST_MUTATION_TASK.prompt,
                        repo=arms[arm],
                        model=args.model,
                        reasoning_effort=args.model_reasoning_effort,
                        timeout_seconds=args.timeout_seconds,
                        workspace=workspace,
                        sandbox="read-only",
                        task=POST_MUTATION_TASK,
                        artifacts=artifacts,
                    )
                    results.append(result)

            if args.suite in {"closeout", "regression", "all"}:
                for arm in two_arm_order(repetition):
                    print(f"[{repetition}/{args.repetitions}] {arm} isolated_closeout", file=sys.stderr, flush=True)
                    result, _ = run_codex(
                        repetition=repetition,
                        arm=arm,
                        task_id="isolated_closeout",
                        phase="closeout",
                        prompt=CLOSEOUT_PKF_PROMPT if arm == "pkf" else CLOSEOUT_CONTROL_PROMPT,
                        repo=closeout_arms[arm],
                        model=args.model,
                        reasoning_effort=args.model_reasoning_effort,
                        timeout_seconds=args.timeout_seconds,
                        workspace=workspace,
                        sandbox="workspace-write" if arm == "pkf" else "read-only",
                        artifacts=artifacts,
                    )
                    results.append(score_closeout(result, closeout_arms[arm], arm, artifacts))

    expected_count = len(build_schedule(args.repetitions, args.suite))
    errors = evaluation_errors(results, expected_count)
    token_atlas_commit = run_command(("git", "rev-parse", "HEAD"), cwd=ROOT).stdout.strip()
    codex_version = run_command(("codex", "--version"), cwd=ROOT).stdout.strip()
    metrics = aggregate_metrics(results)
    performance = performance_advisories(metrics, args.repetitions)
    report = {
        "schema_version": 7,
        "run_id": artifacts.run_id,
        "artifact_manifest_path": "../manifest.json" if artifacts.mode != "off" else None,
        "benchmark": "token-atlas-adaptive-attribution",
        "evaluation_kind": "real_repository_performance",
        "arm_definitions": ARM_DEFINITIONS,
        "suite": args.suite,
        "run_class": run_class(args.repetitions),
        "replicated": args.repetitions >= 3,
        "status": "failed" if errors else ("preliminary" if args.repetitions < 3 else "completed"),
        "quality_status": "failed" if errors else "passed",
        "performance": performance,
        "recorded_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "target": {
            "name": TARGET_NAME,
            "repository": "duelistraj/tether-brain",
            "commit": target["commit"],
            "tree": target["tree"],
            "visibility_at_measurement": "private",
        },
        "token_atlas": {
            "commit": token_atlas_commit,
            "public_skill_sha256": sha256_tree(PUBLIC_SKILL),
            "harness_sha256": sha256_file(Path(__file__).resolve()),
        },
        "environment": {
            "model": args.model,
            "reasoning_effort": args.model_reasoning_effort,
            "repetitions": args.repetitions,
            "codex_version": codex_version,
            "scheduled_calls": expected_count,
        },
        "methodology": {
            "arms": ["source_only", "probe_only", "pkf"],
            "arm_definitions": ARM_DEFINITIONS,
            "task_ids": sorted({item["task_id"] for item in build_schedule(1, args.suite)}),
            "arm_order": "three-arm Latin square and alternating two-arm phases",
            "trace_accounting": (
                "ordered tool events segmented into implementation, first valid route call, and post-route closeout; "
                "token and duration usage remain call-level"
            ),
            "phase_cost_accounting": (
                "probe-only mutation measures implementation, isolated PKF closeout measures closeout, "
                "and integrated PKF mutation remains the observed combined total"
            ),
            "initialization_objective": (
                "maximize verified public-behavior and routing coverage while enforcing one final "
                "validation, opaque helpers, and bounded atomic routes; no historical cost target"
            ),
            "performance_interpretation": (
                "phase-specific advisory targets remain separate from blocking quality gates; "
                "closeout is reported as a required maintenance premium"
            ),
            "ambient_user_config": "ignored; authentication copied only",
            "raw_traces_published": False,
        },
        "pkf_inventory": {
            "materialized_leaf_count": median(
                [entry["materialized_leaf_count"] for entry in initialization_inventories]
            ),
            "pending_leaf_count": median(
                [entry["pending_leaf_count"] for entry in initialization_inventories]
            ),
            "unknown_leaf_count": median(
                [entry["unknown_leaf_count"] for entry in initialization_inventories]
            ),
            "by_repetition": initialization_inventories,
        },
        "metrics": metrics,
        "runs": [public_result(result) for result in results],
        "errors": errors,
    }
    return report


def render_markdown(
    report: Mapping[str, Any],
    *,
    raw_result_link: str | None = None,
) -> str:
    target = report["target"]
    environment = report["environment"]
    metrics = report["metrics"]
    one_pass = report.get("run_class") == "one_pass_preflight"
    run_label = "one-pass preflight" if one_pass else str(report.get("run_class", "benchmark"))
    usage_heading = "Single-pass usage by task" if one_pass else "Median usage by task"
    lines = [
        "# Token Atlas Benchmarks",
        "",
        f"## Adaptive attribution benchmark — {report['suite']} — {run_label}",
        "",
        (
            "This benchmark separates generic source discovery, the adaptive local-probe "
            "policy, and PKF knowledge on Tether Brain at commit "
            f"`{target['commit']}`. The repository was private when measured; no source, "
            "credentials, local paths, or raw traces are published."
        ),
        "",
        f"Publication class: **{run_label}**<br>",
        f"Replicated: **{'yes' if report.get('replicated') else 'no'}**<br>",
        f"Status: **{report['status']}**<br>",
        f"Quality: **{report['quality_status']}**<br>",
        f"Performance: **{report['performance']['status']}**<br>",
        f"Recorded: `{report['recorded_at']}`<br>",
        f"Model: `{environment['model']}` at `{environment['reasoning_effort']}` reasoning<br>",
        f"Repetitions: `{environment['repetitions']}` (`{environment['scheduled_calls']}` calls)",
        "",
    ]
    if raw_result_link:
        result_name = Path(raw_result_link).name
        lines.extend((f"Raw sanitized result: [`{result_name}`]({raw_result_link})", ""))
    if report.get("artifact_manifest_path"):
        lines.extend(
            (
                f"Artifact manifest: [`manifest.json`]({report['artifact_manifest_path']})",
                "",
            )
        )
    lines.extend(
        (
            "### Method",
            "",
            "`source_only` has no PKF or probe policy, `probe_only` isolates the bounded "
            "local-probe policy without PKF, and `pkf` installs adaptive retrieval and "
            "semantic closeout but may bypass PKF for an individual task. Token counts come "
            "from Codex JSONL; total and non-cached input are "
            "reported separately and are not pricing estimates. Tool input and output are "
            "parsed separately. Explicit read targets are distinct from unverified path mentions.",
            "",
            f"### {usage_heading}",
            "",
            "| Task | Phase | Arm | Retrieval | Initial route | Input | Non-cached | Output | Duration ms | Tools | Routed docs | Correct |",
            "| --- | --- | --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        )
    )
    phase_by_task = {
        run["task_id"]: run["phase"] for run in report["runs"]
    }
    for task_id, arms in sorted(metrics["by_task"].items()):
        for arm, values in sorted(arms.items()):
            correct = "n/a" if values["correctness_rate"] is None else f"{values['correctness_rate'] * 100:.0f}%"
            decisions = values.get("retrieval_decisions", {})
            decision = ", ".join(
                f"{name}:{count}" for name, count in decisions.items() if count
            ) or "n/a"
            route_statuses = values.get("initial_route_statuses", {})
            route_status = ", ".join(
                f"{name}:{count}" for name, count in route_statuses.items() if count and name != "not_run"
            ) or "n/a"
            lines.append(
                f"| {task_id} | {phase_by_task.get(task_id, 'unknown')} | `{arm}` | `{decision}` | `{route_status}` | "
                f"{values['input_tokens']:.0f} | {values['non_cached_input_tokens']:.0f} | "
                f"{values['output_tokens']:.0f} | {values['duration_ms']:.0f} | "
                f"{values['tool_call_count']:.0f} | {values['routed_document_count']:.0f} | {correct} |"
            )
    lines.extend(("", "### Routing and validation evidence", ""))
    for run in report["runs"]:
        if run["task_id"] == "initialize":
            helper_paths = ", ".join(run.get("initialization_helper_source_read_paths", [])) or "none"
            lines.append(
                f"- Initialization: {run.get('initialization_validation_call_count', 0)} explicit "
                f"validation(s); opaque helper source reads: {helper_paths}; fallback-style broad "
                f"scan invocations: {run.get('fallback_invocation_count', 0)}."
            )
        elif run["task_id"] == "note_task_links" and run["arm"] == "pkf":
            route_ids = " + ".join(run.get("cross_route_ids", [])) or "none"
            configured = ", ".join(run.get("cross_configured_document_paths", [])) or "none"
            observed = ", ".join(run.get("cross_observed_document_paths", [])) or "none"
            missing = ", ".join(run.get("cross_missing_document_paths", [])) or "none"
            unexpected = ", ".join(run.get("cross_unexpected_document_paths", [])) or "none"
            lines.append(
                f"- Cross routes `{route_ids}` ({run.get('cross_route_marker_status', 'missing')} marker, "
                f"{run.get('cross_route_unique_leaf_count', 0)} reported unique leaves, "
                f"coverage={run.get('cross_coverage_status', 'unknown')}, "
                f"minimality={run.get('cross_minimality_status', 'unknown')}, "
                f"requirements={run.get('cross_covered_requirement_count', 0)}/"
                f"{run.get('cross_requirement_count', 0)}, "
                f"estimated tokens={run.get('cross_estimated_tokens', 0)}): configured {configured}; "
                f"observed {observed}; missing {missing}; unexpected {unexpected}."
            )
        elif run["task_id"] in {"favorite_visibility_mutation", "isolated_closeout"} and run["arm"] == "pkf":
            unexpected = ", ".join(run.get("closeout_unexpected_read_paths", [])) or "none"
            lines.append(
                f"- `{run['task_id']}` closeout: {run.get('closeout_validation_call_count', 0)} "
                f"validation(s); unexpected reads {unexpected}."
            )
    phase_costs = metrics.get("lifecycle_phase_cost_summary", {})
    lines.extend(("", "### Mutation phase attribution", ""))
    if phase_costs:
        lines.extend(
            (
                "Implementation and isolated closeout are separate calls; the integrated row is the directly observed combined mutation. The composed row is their explicit sum.",
                "",
                "| Evidence | Input | Non-cached | Output | Duration ms | Tools |",
                "| --- | ---: | ---: | ---: | ---: | ---: |",
            )
        )
        for phase in (
            "implementation",
            "closeout",
            "closeout_control",
            "closeout_incremental",
            "composed_probe_plus_closeout",
            "integrated_observed",
        ):
            values = phase_costs[phase]
            lines.append(
                f"| {phase} | {values['input_tokens']:.0f} | {values['non_cached_input_tokens']:.0f} | "
                f"{values['output_tokens']:.0f} | {values['duration_ms']:.0f} | {values['tool_call_count']:.0f} |"
            )
        integrated_segments = (
            metrics.get("by_task", {})
            .get("favorite_visibility_mutation", {})
            .get("pkf", {})
            .get("trace_segments", {})
        )
        if integrated_segments:
            lines.extend(("", "Integrated mutation tool segments:", ""))
            for segment in ("implementation", "routing", "closeout"):
                values = integrated_segments[segment]
                lines.append(
                    f"- `{segment}`: {values['tool_call_count']:.0f} tools, "
                    f"{values['read_or_search_command_count']:.0f} reads/searches, "
                    f"fallback rate {values['fallback_rate'] * 100:.0f}%."
                )
    else:
        lines.append("- Requires both lifecycle and isolated-closeout evidence; use the `all` suite.")
    knowledge_savings = metrics.get("activated_pkf_knowledge_savings", {})
    lines.extend(("", "### PKF knowledge savings", ""))
    lines.append(
        "Only paired tasks whose PKF arm actually activated retrieval contribute to "
        "this figure; bypassed tasks are excluded."
    )
    lines.append("")
    lines.append(
        f"Activated pairs: `{knowledge_savings.get('paired_count', 0)}`; median input "
        f"saving: `{knowledge_savings.get('input_tokens', 0):.0f}`; median non-cached "
        f"input saving: `{knowledge_savings.get('non_cached_input_tokens', 0):.0f}`."
    )
    break_even = metrics.get("break_even_activated_tasks", {})
    lines.append(
        f"Estimated break-even activated tasks: input "
        f"`{break_even.get('input_tokens') if break_even.get('input_tokens') is not None else 'not reached'}`, "
        f"non-cached input "
        f"`{break_even.get('non_cached_input_tokens') if break_even.get('non_cached_input_tokens') is not None else 'not reached'}`."
    )
    lines.extend(("", "### Bypassed environment deltas", ""))
    bypassed = metrics.get("bypassed_pkf_environment_deltas", {})
    if bypassed:
        for task_id, values in sorted(bypassed.items()):
            lines.append(
                f"- `{task_id}` ({values['paired_count']} pair(s)): input "
                f"{values.get('input_tokens', 0):+.0f}, non-cached "
                f"{values.get('non_cached_input_tokens', 0):+.0f}."
            )
    else:
        lines.append("- No PKF-arm task bypassed retrieval in this suite.")
    lines.extend(("", "### Attribution deltas", ""))
    for task_id, comparisons in sorted(metrics["comparisons"].items()):
        for label, values in sorted(comparisons.items()):
            input_delta = values["input_tokens"]["delta"]
            non_cached_delta = values["non_cached_input_tokens"]["delta"]
            duration_delta = values["duration_ms"]["delta"]
            lines.append(
                f"- `{task_id}` {label}: input {input_delta:+.0f}, non-cached "
                f"{non_cached_delta:+.0f}, duration {duration_delta:+.0f} ms."
            )
    lines.extend(("", "### Phase performance scorecard", ""))
    lines.append(
        f"Evidence strength: **{report['performance'].get('evidence_strength', 'unknown')}**. "
        "These targets are advisory and do not change the quality verdict."
    )
    for phase_name, phase in report["performance"].get("phases", {}).items():
        lines.extend(("", f"- `{phase_name}` — **{phase['status']}**: {phase['purpose']}"))
        for check in phase.get("checks", []):
            state = "met" if check["met"] else "missed"
            value = "n/a" if check["value"] is None else f"{check['value']:.2f}"
            lines.append(
                f"  - {check['name']}: {state} (`{value}`, target {check['target']})."
            )
    lines.extend(("", "### Limitations", ""))
    lines.extend(
        (
            "- One application repository, one pinned commit, one model, and one reasoning setting.",
            f"- {environment['repetitions']} repetition(s) describe this controlled run but are not a population-wide estimate.",
            "- Provider prompt caching can change total-input composition; interpret cached and non-cached input separately.",
        )
    )
    if one_pass:
        lines.append(
            "- This published one-pass preflight is directional and cannot replace a fresh three-repetition result for replicated claims."
        )
    if report["errors"]:
        lines.extend(("", "### Evaluation errors", ""))
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


def write_report(
    report: Mapping[str, Any],
    args: argparse.Namespace,
    artifacts: ArtifactStore,
) -> None:
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
    artifacts.write_public(report)
    if args.report_json:
        args.report_json.parent.mkdir(parents=True, exist_ok=True)
        args.report_json.write_text(json_text, encoding="utf-8")
    if args.report_markdown:
        args.report_markdown.parent.mkdir(parents=True, exist_ok=True)
        raw_result_link = None
        if args.report_json:
            raw_result_link = Path(
                os.path.relpath(
                    args.report_json.resolve(),
                    start=args.report_markdown.parent.resolve(),
                )
            ).as_posix()
        args.report_markdown.write_text(
            render_markdown(report, raw_result_link=raw_result_link),
            encoding="utf-8",
        )
    if args.format == "json":
        print(json_text, end="")
    else:
        savings = report["metrics"]["activated_pkf_knowledge_savings"]
        savings_label = "Activated-task paired" if report.get("run_class") == "one_pass_preflight" else "Median activated-task paired"
        print(f"PKF savings eval: {report['status']}")
        print(f"Run class: {report['run_class']}")
        print(f"Suite: {report['suite']}")
        print(f"Calls: {len(report['runs'])}/{report['environment']['scheduled_calls']}")
        print(f"{savings_label} read-only input saving: {savings['input_tokens']:.0f}")
        print(f"Performance: {report['performance']['status']}")
        print(f"Errors: {len(report['errors'])}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts: ArtifactStore | None = None
    try:
        target = verify_target(args.target_repo, args.target_commit)
        schedule = build_schedule(args.repetitions, args.suite)
        if args.dry_run:
            output = {
                "dry_run": True,
                "target": {"name": TARGET_NAME, **target},
                "model": args.model,
                "reasoning_effort": args.model_reasoning_effort,
                "suite": args.suite,
                "run_class": run_class(args.repetitions),
                "replicated": args.repetitions >= 3,
                "scheduled_calls": len(schedule),
                "schedule": schedule,
            }
            print(json.dumps(output, indent=2, sort_keys=True))
            return 0
        artifacts = ArtifactStore(
            root=args.artifacts_root,
            run_id=make_run_id(args),
            mode=args.artifact_mode,
        )
        report = execute(args, target, artifacts)
        write_report(report, args, artifacts)
        return 1 if report["status"] == "failed" else 0
    except (EvaluationError, OSError, subprocess.SubprocessError) as exc:
        if artifacts is not None:
            artifacts.fail(sanitized_error(str(exc), (ROOT, args.target_repo)))
        print(f"pkf_savings_eval: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        if artifacts is not None:
            artifacts.fail(sanitized_error(str(exc), (ROOT, args.target_repo)))
        raise


if __name__ == "__main__":
    raise SystemExit(main())
