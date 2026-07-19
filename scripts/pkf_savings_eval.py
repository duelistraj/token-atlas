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
PUBLIC_SKILL = ROOT / "skills" / "token-atlas"
DEFAULT_TARGET_COMMIT = "5c458df3c737f0af2a2193186d98af90c45163f0"
DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_REASONING_EFFORT = "high"
DEFAULT_REPETITIONS = 3
DEFAULT_TIMEOUT_SECONDS = 1_800
ALLOWED_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")
EVALUATION_SUITES = ("retrieval", "lifecycle", "closeout", "all")
TARGET_NAME = "tether-brain"
ISOLATED_CLOSEOUT_PATCH = ROOT / "benchmarks" / "patches" / "favorite-visibility.patch"
INITIALIZATION_REFERENCE = {
    "non_cached_input_tokens": 99_720,
    "duration_ms": 516_944,
}

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
    "Use the token-atlas skill and its deterministic scaffold helper to initialize "
    "PKF with hybrid extraction: review capability boundaries, materialize shared "
    "architecture, routing, and bounded public entry points, and leave other leaves "
    "pending. Use profile=core, retrieval_exports=off, "
    "simulation=changed, token_budget=summary, and validation_strictness=ci. "
    "Do not change application source or tests."
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
tests. Perform only the required PKF semantic closeout using the provided
implementation context and changed paths; do not replay repository startup or
rediscover the mutation.
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
            "Return the requested structured answer with concise source evidence."
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
    emitted_closeout: bool
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
    changed_path_count: int
    changed_expected_paths: bool | None
    focused_test_passed: bool | None
    pkf_validation_passed: bool | None
    error: str


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
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be at least 1")
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
READ_OR_SEARCH_TOKENS = ("rg ", "sg ", "sed ", "cat ", "head ", "tail ", "find ", "git show")
FALLBACK_PATTERNS = ("rg --files", "git ls-files", "find . ", "find ./", "grep -r")


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


def trace_tool_inputs(output: str) -> str:
    values: list[str] = []
    for raw_line in output.splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        item = event.get("item")
        if event.get("type") == "item.completed" and isinstance(item, dict):
            values.extend(named_field_strings(item, TOOL_INPUT_FIELDS))
    return "\n".join(values)


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
    tool_calls = 0
    read_or_search_commands = 0
    tool_input_chars = 0
    tool_output_chars = 0
    explicit_paths: set[str] = set()
    searched_roots: set[str] = set()
    ai_read_or_search_commands = 0
    fallback_search = False
    normalized_paths = tuple(sorted(set(known_paths), key=len, reverse=True))
    normalized_directories = set(known_directories)
    for raw_line in output.splitlines():
        try:
            event = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        item = event.get("item")
        if event.get("type") != "item.completed" or not isinstance(item, dict):
            continue
        item_type = str(item.get("type", ""))
        if item_type in {"agent_message", "reasoning"}:
            continue
        tool_calls += 1
        input_strings = named_field_strings(item, TOOL_INPUT_FIELDS)
        output_strings = named_field_strings(item, TOOL_OUTPUT_FIELDS)
        tool_input_chars += sum(len(value) for value in input_strings)
        tool_output_chars += sum(len(value) for value in output_strings)
        input_text = " ".join(input_strings)
        lowered = input_text.lower()
        read_like = any(token in f"{lowered} " for token in READ_OR_SEARCH_TOKENS) or any(
            token in item_type.lower() for token in ("read", "search", "query")
        )
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
        if any(pattern in lowered for pattern in FALLBACK_PATTERNS):
            fallback_search = True
    explicit_ai = {path for path in explicit_paths if path.startswith(".ai/")}
    explicit_skill = {
        path for path in explicit_paths if "/skills/token-atlas/" in f"/{path}" or path.startswith(".codex/skills/token-atlas/")
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
        fallback_search=fallback_search,
    )


def changed_paths(repo: Path) -> tuple[str, ...]:
    status = run_command(("git", "status", "--porcelain"), cwd=repo).stdout
    return tuple(line[3:].strip() for line in status.splitlines() if len(line) > 3)


def tracked_paths(repo: Path) -> tuple[str, ...]:
    output = run_command(("git", "ls-files"), cwd=repo).stdout
    return tuple(line for line in output.splitlines() if line)


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
    trace = inspect_jsonl_trace(
        stdout,
        known_paths=repo_paths,
        known_directories=tracked_directories(repo_paths),
    )
    structured = parse_structured_answer(messages) if task is not None else None
    answer = structured.get("answers") if isinstance(structured, dict) else None
    answer_correct = (
        dict(answer) == dict(task.expected_answers)
        if task is not None and isinstance(answer, Mapping)
        else (False if task is not None else None)
    )
    accessed = detect_accessed_paths(event_text, repo_paths)
    tool_inputs = trace_tool_inputs(stdout).lower()
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
        accessed_skill="token-atlas/skill.md" in tool_inputs,
        accessed_closeout="token-atlas/references/closeout.md" in tool_inputs,
        emitted_closeout="pkf closeout:" in "\n".join(messages).lower(),
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
        changed_path_count=len(changes),
        changed_expected_paths=None,
        focused_test_passed=None,
        pkf_validation_passed=None,
        error=sanitized_error(stderr, (repo, workspace, ROOT)) if returncode else "",
    )
    return result, event_text


def replace_result(result: CodexResult, **updates: Any) -> CodexResult:
    values = asdict(result)
    values.update(updates)
    if isinstance(values.get("usage"), dict):
        values["usage"] = Usage(**values["usage"])
    return CodexResult(**values)


def validate_pkf(repo: Path) -> tuple[bool, str]:
    validator = repo / ".codex" / "skills" / "token-atlas" / "scripts" / "pkf_validate.py"
    if not validator.is_file():
        return False, "public validator is missing"
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
    return completed.returncode == 0, completed.stderr.strip()[-1_000:]


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


def score_closeout(result: CodexResult, repo: Path, arm: str) -> CodexResult:
    changes = changed_paths(repo)
    expected = {
        "frontend/src/notes/noteSectionState.ts",
        "frontend/src/notes/noteSectionState.test.ts",
    }
    valid: bool | None = None
    if arm == "pkf":
        valid, _ = validate_pkf(repo)
    return replace_result(
        result,
        changed_path_count=len(changes),
        changed_expected_paths=expected.issubset(changes),
        focused_test_passed=True,
        pkf_validation_passed=valid,
    )


def score_mutation(result: CodexResult, repo: Path, arm: str) -> CodexResult:
    changes = changed_paths(repo)
    expected_source = "frontend/src/notes/noteSectionState.ts" in changes
    expected_test = "frontend/src/notes/noteSectionState.test.ts" in changes
    focused_test_passed = run_focused_test(repo)
    pkf_validation_passed: bool | None = None
    if arm == "pkf":
        pkf_validation_passed, _ = validate_pkf(repo)
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
        if suite in {"lifecycle", "all"}:
            for arm in two_arm_order(repetition):
                schedule.append({"repetition": repetition, "arm": arm, "task_id": "favorite_visibility_mutation", "phase": "mutation"})
            for arm in two_arm_order(repetition):
                schedule.append({"repetition": repetition, "arm": arm, "task_id": POST_MUTATION_TASK.task_id, "phase": "post_mutation"})
        if suite in {"closeout", "all"}:
            for arm in two_arm_order(repetition):
                schedule.append({"repetition": repetition, "arm": arm, "task_id": "isolated_closeout", "phase": "closeout"})
    return schedule


def median(values: Sequence[int | float]) -> float:
    return float(statistics.median(values)) if values else 0.0


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
        "mentioned_path_count",
        "mentioned_ai_path_count",
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
        scored = [result for result in grouped if result.answer_correct is not None]
        entry["correctness_rate"] = (
            sum(result.answer_correct is True for result in scored) / len(scored)
            if scored
            else None
        )
        by_task.setdefault(task_id, {})[arm] = entry

    sum_metrics = (*usage_metrics, "duration_ms", *trace_metrics)
    operational_by_repetition: list[dict[str, Any]] = []
    for repetition in sorted({result.repetition for result in results}):
        repeated = [result for result in results if result.repetition == repetition]
        entry: dict[str, Any] = {"repetition": repetition}
        for arm in ("source_only", "probe_only", "pkf"):
            arm_results = [result for result in repeated if result.arm == arm and result.phase != "setup"]
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

    paired_savings: dict[str, list[float]] = {metric: [] for metric in usage_metrics}
    for repetition in sorted({result.repetition for result in results}):
        for task_id in {task.task_id for task in READ_ONLY_TASKS}:
            result_by_arm = {
                result.arm: result
                for result in results
                if result.repetition == repetition and result.task_id == task_id
            }
            if not {"probe_only", "pkf"}.issubset(result_by_arm):
                continue
            for metric in usage_metrics:
                baseline = usage_value(result_by_arm["probe_only"], metric)
                candidate = usage_value(result_by_arm["pkf"], metric)
                if baseline is not None and candidate is not None:
                    paired_savings[metric].append(float(baseline - candidate))

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
        per_read_saving = median(paired_savings[metric])
        init_cost = median(
            [
                value
                for result in results
                if result.arm == "pkf"
                and result.task_id == "initialize"
                and (value := usage_value(result, metric)) is not None
            ]
        )
        mutation = comparisons.get("favorite_visibility_mutation", {}).get("probe_vs_pkf", {}).get(metric, {})
        mutation_premium = max(0.0, float(mutation.get("delta", 0.0)))
        break_even[metric] = (
            math.ceil((init_cost + mutation_premium) / per_read_saving)
            if per_read_saving > 0
            else None
        )

    return {
        "by_task": by_task,
        "comparisons": comparisons,
        "operational_by_repetition": operational_by_repetition,
        "median_paired_pkf_read_only_savings": {
            metric: median(values) for metric, values in paired_savings.items()
        },
        "break_even_read_only_tasks": break_even,
    }


def performance_advisories(metrics: Mapping[str, Any], repetitions: int) -> dict[str, Any]:
    if repetitions < 3:
        return {"status": "preliminary", "checks": []}
    comparisons = metrics.get("comparisons", {})
    checks: list[dict[str, Any]] = []

    def add_check(name: str, value: float | None, target: str, met: bool | None) -> None:
        checks.append({"name": name, "value": value, "target": target, "met": met})

    local = comparisons.get("boards_add_task", {}).get("probe_vs_pkf", {})
    if local:
        for metric in ("input_tokens", "non_cached_input_tokens", "duration_ms"):
            value = local.get(metric, {}).get("percent")
            add_check(f"local_{metric}_overhead", value, "<= 5%", value is not None and value <= 5.0)
    cross = comparisons.get("note_task_links", {}).get("probe_vs_pkf", {})
    if cross:
        for metric in ("non_cached_input_tokens", "tool_call_count"):
            value = cross.get(metric, {}).get("delta")
            add_check(f"cross_capability_{metric}_delta", value, "< 0", value is not None and value < 0)
    initialized = metrics.get("by_task", {}).get("initialize", {}).get("pkf", {})
    for metric, reference in INITIALIZATION_REFERENCE.items():
        if metric in initialized:
            value = float(initialized[metric]) - reference
            add_check(f"initialization_{metric}_delta", value, "< 0 versus runtime-v3 one-pass", value < 0)
    operational = metrics.get("operational_by_repetition", [])
    for metric in ("input_tokens", "non_cached_input_tokens", "duration_ms"):
        probe = median([entry["probe_only"][metric] for entry in operational])
        pkf = median([entry["pkf"][metric] for entry in operational])
        if probe:
            value = (pkf - probe) / probe * 100.0
            add_check(f"operational_{metric}_overhead", value, "<= 5%", value <= 5.0)
    return {
        "status": "advisory_met" if checks and all(check["met"] for check in checks) else "advisory_missed",
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
        if result.task_id in {"boards_add_task", POST_MUTATION_TASK.task_id}:
            if result.explicit_ai_read_path_count or result.explicit_skill_read_path_count:
                errors.append(f"{label}: local task explicitly read PKF or Token Atlas paths")
        if result.task_id == "note_task_links" and result.arm == "pkf":
            if result.explicit_ai_read_path_count < 1:
                errors.append(f"{label}: cross-capability task did not activate PKF retrieval")
        if result.task_id == "favorite_visibility_mutation":
            if result.changed_expected_paths is not True:
                errors.append(f"{label}: mutation did not make the expected source/test change")
            if result.focused_test_passed is not True:
                errors.append(f"{label}: focused frontend test failed")
            if result.arm == "pkf":
                if result.pkf_validation_passed is not True:
                    errors.append(f"{label}: PKF failed validation after mutation")
                if not result.emitted_closeout:
                    errors.append(f"{label}: mutation did not emit PKF closeout status")
        if result.task_id == "isolated_closeout":
            if result.arm == "pkf":
                if result.pkf_validation_passed is not True:
                    errors.append(f"{label}: isolated closeout left PKF invalid")
                if not result.emitted_closeout:
                    errors.append(f"{label}: isolated closeout did not emit status")
            elif result.explicit_ai_read_path_count or result.explicit_skill_read_path_count:
                errors.append(f"{label}: closeout control accessed PKF or Token Atlas paths")
    return errors


def execute(args: argparse.Namespace, target: Mapping[str, str]) -> dict[str, Any]:
    runtime_root = args.runtime_root.resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    results: list[CodexResult] = []
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
            )
            init_valid, validation_error = validate_pkf(arms["pkf"])
            init_result = replace_result(
                init_result,
                pkf_validation_passed=init_valid,
                error=init_result.error or sanitized_error(
                    validation_error,
                    (arms["pkf"], workspace, ROOT),
                ),
            )
            results.append(init_result)
            if init_result.returncode == 0 and init_valid:
                commit_generated_pkf(arms["pkf"])

            closeout_arms = (
                prepare_closeout_arms(workspace, arms)
                if args.suite in {"closeout", "all"}
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
                    )
                    results.append(score_mutation(result, arms[arm], arm))

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
                    )
                    results.append(result)

            if args.suite in {"closeout", "all"}:
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
                    )
                    results.append(score_closeout(result, closeout_arms[arm], arm))

    expected_count = len(build_schedule(args.repetitions, args.suite))
    errors = evaluation_errors(results, expected_count)
    token_atlas_commit = run_command(("git", "rev-parse", "HEAD"), cwd=ROOT).stdout.strip()
    codex_version = run_command(("codex", "--version"), cwd=ROOT).stdout.strip()
    metrics = aggregate_metrics(results)
    performance = performance_advisories(metrics, args.repetitions)
    report = {
        "schema_version": 2,
        "benchmark": "token-atlas-adaptive-attribution",
        "suite": args.suite,
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
        },
        "environment": {
            "model": args.model,
            "reasoning_effort": args.model_reasoning_effort,
            "repetitions": args.repetitions,
            "codex_version": codex_version,
            "scheduled_calls": expected_count,
            "publishable": args.repetitions >= 3,
        },
        "methodology": {
            "arms": ["source_only", "probe_only", "pkf"],
            "task_ids": sorted({item["task_id"] for item in build_schedule(1, args.suite)}),
            "arm_order": "three-arm Latin square and alternating two-arm phases",
            "trace_accounting": "tool inputs and outputs parsed separately; path mentions remain unverified",
            "initialization_reference": INITIALIZATION_REFERENCE,
            "ambient_user_config": "ignored; authentication copied only",
            "raw_traces_published": False,
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
    lines = [
        "# Token Atlas Benchmarks",
        "",
        f"## Adaptive attribution benchmark — {report['suite']}",
        "",
        (
            "This benchmark separates generic source discovery, the adaptive local-probe "
            "policy, and PKF knowledge on Tether Brain at commit "
            f"`{target['commit']}`. The repository was private when measured; no source, "
            "credentials, local paths, or raw traces are published."
        ),
        "",
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
    lines.extend(
        (
            "### Method",
            "",
            "`source_only` measures generic discovery, `probe_only` isolates the bounded "
            "local-probe policy, and `pkf` adds adaptive knowledge retrieval and semantic "
            "closeout. Token counts come from Codex JSONL; total and non-cached input are "
            "reported separately and are not pricing estimates. Tool input and output are "
            "parsed separately. Explicit read targets are distinct from unverified path mentions.",
            "",
            "### Median usage by task",
            "",
            "| Task | Phase | Arm | Input | Non-cached | Output | Duration ms | Tools | Explicit .ai reads | Correct |",
            "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        )
    )
    phase_by_task = {
        run["task_id"]: run["phase"] for run in report["runs"]
    }
    for task_id, arms in sorted(metrics["by_task"].items()):
        for arm, values in sorted(arms.items()):
            correct = "n/a" if values["correctness_rate"] is None else f"{values['correctness_rate'] * 100:.0f}%"
            lines.append(
                f"| {task_id} | {phase_by_task.get(task_id, 'unknown')} | `{arm}` | "
                f"{values['input_tokens']:.0f} | {values['non_cached_input_tokens']:.0f} | "
                f"{values['output_tokens']:.0f} | {values['duration_ms']:.0f} | "
                f"{values['tool_call_count']:.0f} | {values['explicit_ai_read_path_count']:.0f} | {correct} |"
            )
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
    lines.extend(("", "### Performance advisories", ""))
    if report["performance"]["checks"]:
        for check in report["performance"]["checks"]:
            state = "met" if check["met"] else "missed"
            value = "n/a" if check["value"] is None else f"{check['value']:.2f}"
            lines.append(f"- {check['name']}: {state} (`{value}`, target {check['target']}).")
    else:
        lines.append("- Preliminary run: performance targets require at least three repetitions.")
    lines.extend(("", "### Limitations", ""))
    lines.extend(
        (
            "- One application repository, one pinned commit, one model, and one reasoning setting.",
            f"- {environment['repetitions']} repetition(s) describe this controlled run but are not a population-wide estimate.",
            "- Provider prompt caching can change total-input composition; interpret cached and non-cached input separately.",
            "- A one-pass run is diagnostic only and cannot replace headline replicated results.",
        )
    )
    if report["errors"]:
        lines.extend(("", "### Evaluation errors", ""))
        lines.extend(f"- {error}" for error in report["errors"])
    return "\n".join(lines) + "\n"


def write_report(report: Mapping[str, Any], args: argparse.Namespace) -> None:
    json_text = json.dumps(report, indent=2, sort_keys=True) + "\n"
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
        savings = report["metrics"]["median_paired_pkf_read_only_savings"]
        print(f"PKF savings eval: {report['status']}")
        print(f"Suite: {report['suite']}")
        print(f"Calls: {len(report['runs'])}/{report['environment']['scheduled_calls']}")
        print(f"Median paired read-only input saving: {savings['input_tokens']:.0f}")
        print(f"Performance: {report['performance']['status']}")
        print(f"Errors: {len(report['errors'])}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
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
                "publishable": args.repetitions >= 3,
                "scheduled_calls": len(schedule),
                "schedule": schedule,
            }
            print(json.dumps(output, indent=2, sort_keys=True))
            return 0
        report = execute(args, target)
        write_report(report, args)
        return 1 if report["status"] == "failed" else 0
    except (EvaluationError, OSError, subprocess.SubprocessError) as exc:
        print(f"pkf_savings_eval: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
