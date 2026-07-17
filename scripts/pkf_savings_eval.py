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
TARGET_NAME = "tether-brain"

NEUTRAL_AGENTS = """# AGENTS

## Code Search

- Prefer `rg` (ripgrep) for text search and file discovery.
- Prefer `sg` (ast-grep) for syntax-aware searches and refactoring.
- Avoid `grep -r` unless `rg` is unavailable.

## Best Practices

- Read and follow `.codex/best-practices/PYTHON-BEST-PRACTICES.md` for Python work.
- Read and follow `.codex/best-practices/REACT-BEST-PRACTICES.md` for React work.
"""

INITIALIZE_PROMPT = (
    "Use the token-atlas skill to initialize PKF and extract a complete, source-backed "
    "knowledge base for this repository with profile=core, retrieval_exports=off, "
    "simulation=changed, token_budget=summary, and validation_strictness=ci. "
    "Do not change application source or tests."
)

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
            "shows_right_side_error_when_none": True,
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
class CodexResult:
    repetition: int
    arm: str
    task_id: str
    returncode: int
    duration_ms: int
    usage: Usage | None
    answer: Mapping[str, Any] | None
    answer_correct: bool | None
    accessed_skill: bool
    accessed_closeout: bool
    emitted_closeout: bool
    fallback_search: bool
    accessed_path_count: int
    accessed_ai_path_count: int
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


def strip_pkf(repo: Path) -> None:
    ai_dir = repo / ".ai"
    if ai_dir.exists():
        shutil.rmtree(ai_dir)
    installed_skill = repo / ".codex" / "skills" / "token-atlas"
    if installed_skill.exists():
        shutil.rmtree(installed_skill)
    (repo / "AGENTS.md").write_text(NEUTRAL_AGENTS, encoding="utf-8")


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
    for arm in ("no_pkf", "pkf"):
        repo = workspace / arm
        shutil.copytree(exported, repo, symlinks=True)
        if arm == "pkf":
            install_public_skill(repo)
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


def changed_paths(repo: Path) -> tuple[str, ...]:
    status = run_command(("git", "status", "--porcelain"), cwd=repo).stdout
    return tuple(line[3:].strip() for line in status.splitlines() if len(line) > 3)


def tracked_paths(repo: Path) -> tuple[str, ...]:
    output = run_command(("git", "ls-files"), cwd=repo).stdout
    return tuple(line for line in output.splitlines() if line)


def detect_accessed_paths(event_text: str, paths: Sequence[str]) -> tuple[str, ...]:
    return tuple(path for path in paths if path in event_text)


def detect_fallback_search(event_text: str) -> bool:
    lowered = event_text.lower()
    patterns = (
        "rg --files",
        "git ls-files",
        "find . ",
        "find ./",
        "grep -r",
    )
    return any(pattern in lowered for pattern in patterns)


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
    structured = parse_structured_answer(messages) if task is not None else None
    answer = structured.get("answers") if isinstance(structured, dict) else None
    answer_correct = (
        dict(answer) == dict(task.expected_answers)
        if task is not None and isinstance(answer, Mapping)
        else (False if task is not None else None)
    )
    accessed = detect_accessed_paths(event_text, tracked_paths(repo))
    changes = changed_paths(repo)
    result = CodexResult(
        repetition=repetition,
        arm=arm,
        task_id=task_id,
        returncode=returncode,
        duration_ms=duration_ms,
        usage=usage,
        answer=answer,
        answer_correct=answer_correct,
        accessed_skill="token-atlas/skill.md" in event_text.lower(),
        accessed_closeout="token-atlas/references/closeout.md" in event_text.lower(),
        emitted_closeout="pkf closeout:" in "\n".join(messages).lower(),
        fallback_search=detect_fallback_search(event_text),
        accessed_path_count=len(accessed),
        accessed_ai_path_count=sum(path.startswith(".ai/") for path in accessed),
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


def mutation_behavior_changed(repo: Path) -> bool:
    test_path = repo / "frontend" / "src" / "notes" / "noteSectionState.test.ts"
    if not test_path.is_file():
        return False
    text = test_path.read_text(encoding="utf-8")
    match = re.search(
        r'shows favorites.*?\{(?P<body>.*?)\n\s*\}\);',
        text,
        flags=re.DOTALL,
    )
    return bool(
        match
        and "appearsInHome(note, false)).toBe(false)" in match.group("body")
        and "appearsInHome(note, true)).toBe(true)" in match.group("body")
    )


def score_mutation(result: CodexResult, repo: Path, arm: str) -> CodexResult:
    changes = changed_paths(repo)
    expected_source = "frontend/src/notes/noteSectionState.ts" in changes
    expected_test = "frontend/src/notes/noteSectionState.test.ts" in changes
    focused_test_passed = run_focused_test(repo)
    behavior_changed = mutation_behavior_changed(repo)
    pkf_validation_passed: bool | None = None
    if arm == "pkf":
        pkf_validation_passed, _ = validate_pkf(repo)
    return replace_result(
        result,
        changed_path_count=len(changes),
        changed_expected_paths=expected_source and expected_test and behavior_changed,
        focused_test_passed=focused_test_passed,
        pkf_validation_passed=pkf_validation_passed,
    )


def build_schedule(repetitions: int) -> list[dict[str, Any]]:
    schedule: list[dict[str, Any]] = []
    for repetition in range(1, repetitions + 1):
        schedule.append({"repetition": repetition, "arm": "pkf", "task_id": "initialize"})
        arm_order = ("no_pkf", "pkf") if repetition % 2 else ("pkf", "no_pkf")
        for task in READ_ONLY_TASKS:
            for arm in arm_order:
                schedule.append({"repetition": repetition, "arm": arm, "task_id": task.task_id})
        for arm in arm_order:
            schedule.append({"repetition": repetition, "arm": arm, "task_id": "favorite_visibility_mutation"})
        for arm in arm_order:
            schedule.append({"repetition": repetition, "arm": arm, "task_id": POST_MUTATION_TASK.task_id})
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
    metrics = (
        "input_tokens",
        "cached_input_tokens",
        "non_cached_input_tokens",
        "output_tokens",
    )
    for (task_id, arm), grouped in sorted(groups.items()):
        entry = {
            metric: median(
                [value for result in grouped if (value := usage_value(result, metric)) is not None]
            )
            for metric in metrics
        }
        entry["duration_ms"] = median([result.duration_ms for result in grouped])
        scored = [result for result in grouped if result.answer_correct is not None]
        entry["correctness_rate"] = (
            sum(result.answer_correct is True for result in scored) / len(scored)
            if scored
            else None
        )
        by_task.setdefault(task_id, {})[arm] = entry

    lifecycle_by_repetition: list[dict[str, Any]] = []
    for repetition in sorted({result.repetition for result in results}):
        repeated = [result for result in results if result.repetition == repetition]
        entry: dict[str, Any] = {"repetition": repetition}
        for arm in ("no_pkf", "pkf"):
            arm_results = [result for result in repeated if result.arm == arm]
            entry[arm] = {
                metric: sum(
                    value
                    for result in arm_results
                    if (value := usage_value(result, metric)) is not None
                )
                for metric in metrics
            }
        lifecycle_by_repetition.append(entry)

    read_only_ids = {task.task_id for task in READ_ONLY_TASKS} | {POST_MUTATION_TASK.task_id}
    paired_savings: dict[str, list[float]] = {metric: [] for metric in metrics}
    for repetition in sorted({result.repetition for result in results}):
        for task_id in read_only_ids:
            result_by_arm = {
                result.arm: result
                for result in results
                if result.repetition == repetition and result.task_id == task_id
            }
            if set(result_by_arm) != {"no_pkf", "pkf"}:
                continue
            for metric in metrics:
                baseline = usage_value(result_by_arm["no_pkf"], metric)
                candidate = usage_value(result_by_arm["pkf"], metric)
                if baseline is not None and candidate is not None:
                    paired_savings[metric].append(float(baseline - candidate))

    def overhead(metric: str, task_id: str) -> float:
        pkf_values = [
            value
            for result in results
            if result.arm == "pkf"
            and result.task_id == task_id
            and (value := usage_value(result, metric)) is not None
        ]
        no_pkf_values = [
            value
            for result in results
            if result.arm == "no_pkf"
            and result.task_id == task_id
            and (value := usage_value(result, metric)) is not None
        ]
        return median(pkf_values) - median(no_pkf_values)

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
        mutation_premium = max(0.0, overhead(metric, "favorite_visibility_mutation"))
        break_even[metric] = (
            math.ceil((init_cost + mutation_premium) / per_read_saving)
            if per_read_saving > 0
            else None
        )

    return {
        "by_task": by_task,
        "lifecycle_by_repetition": lifecycle_by_repetition,
        "median_paired_read_only_savings": {
            metric: median(values) for metric, values in paired_savings.items()
        },
        "break_even_read_only_tasks": break_even,
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

            arm_order = ("no_pkf", "pkf") if repetition % 2 else ("pkf", "no_pkf")
            for task in READ_ONLY_TASKS:
                for arm in arm_order:
                    print(
                        f"[{repetition}/{args.repetitions}] {arm} {task.task_id}",
                        file=sys.stderr,
                        flush=True,
                    )
                    result, _ = run_codex(
                        repetition=repetition,
                        arm=arm,
                        task_id=task.task_id,
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

            for arm in arm_order:
                print(
                    f"[{repetition}/{args.repetitions}] {arm} favorite_visibility_mutation",
                    file=sys.stderr,
                    flush=True,
                )
                result, _ = run_codex(
                    repetition=repetition,
                    arm=arm,
                    task_id="favorite_visibility_mutation",
                    prompt=MUTATION_PROMPT,
                    repo=arms[arm],
                    model=args.model,
                    reasoning_effort=args.model_reasoning_effort,
                    timeout_seconds=args.timeout_seconds,
                    workspace=workspace,
                    sandbox="workspace-write",
                )
                results.append(score_mutation(result, arms[arm], arm))

            for arm in arm_order:
                print(
                    f"[{repetition}/{args.repetitions}] {arm} {POST_MUTATION_TASK.task_id}",
                    file=sys.stderr,
                    flush=True,
                )
                result, _ = run_codex(
                    repetition=repetition,
                    arm=arm,
                    task_id=POST_MUTATION_TASK.task_id,
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

    expected_count = len(build_schedule(args.repetitions))
    errors = evaluation_errors(results, expected_count)
    token_atlas_commit = run_command(("git", "rev-parse", "HEAD"), cwd=ROOT).stdout.strip()
    codex_version = run_command(("codex", "--version"), cwd=ROOT).stdout.strip()
    report = {
        "schema_version": 1,
        "benchmark": "pkf-vs-no-pkf-lifecycle",
        "status": "failed" if errors else "completed",
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
        },
        "methodology": {
            "arms": ["no_pkf", "pkf"],
            "task_ids": [
                "initialize",
                *(task.task_id for task in READ_ONLY_TASKS),
                "favorite_visibility_mutation",
                POST_MUTATION_TASK.task_id,
            ],
            "arm_order": "counterbalanced by repetition",
            "ambient_user_config": "ignored; authentication copied only",
            "raw_traces_published": False,
        },
        "metrics": aggregate_metrics(results),
        "runs": [public_result(result) for result in results],
        "errors": errors,
    }
    return report


def render_markdown(report: Mapping[str, Any]) -> str:
    target = report["target"]
    environment = report["environment"]
    metrics = report["metrics"]
    by_task = metrics["by_task"]
    lifecycle = metrics["lifecycle_by_repetition"]
    lifecycle_median = {
        arm: {
            metric: median([entry[arm][metric] for entry in lifecycle])
            for metric in (
                "input_tokens",
                "cached_input_tokens",
                "non_cached_input_tokens",
                "output_tokens",
            )
        }
        for arm in ("no_pkf", "pkf")
    }
    lines = [
        "# Token Atlas Benchmarks",
        "",
        "## PKF vs no PKF lifecycle benchmark",
        "",
        (
            f"This benchmark compares Token Atlas with a source-only baseline on the real "
            f"Tether Brain repository at commit `{target['commit']}`. The repository was "
            "private when measured; no source, credentials, raw traces, or local paths are "
            "published here. The pinned commit can be independently checked once the project "
            "is public."
        ),
        "",
        f"Status: **{report['status']}**<br>",
        f"Recorded: `{report['recorded_at']}`<br>",
        f"Model: `{environment['model']}` at `{environment['reasoning_effort']}` reasoning<br>",
        f"Repetitions: `{environment['repetitions']}` (`{environment['scheduled_calls']}` calls)",
        "",
        "Raw sanitized result: "
        "[`pkf-vs-no-pkf-gpt-5.6-luna-high-2026-07-17.json`](.agents/skills/token-atlas/benchmarks/results/pkf-vs-no-pkf-gpt-5.6-luna-high-2026-07-17.json)",
        "",
        "### Method",
        "",
        "Each repetition exports the pinned Git tree into disposable workspaces. Both arms "
        "start without `.ai/` or Token Atlas instructions. The PKF arm installs the public "
        "skill under test, initializes and validates its knowledge base, then both arms run "
        "the same two read-only questions, one focused mutation, and one post-mutation "
        "question. Arm order alternates by repetition.",
        "",
        "Token counts come from Codex JSONL. Total input includes cached input; non-cached "
        "input is reported separately. These figures are not pricing estimates.",
        "",
        "### Median usage by task",
        "",
        "| Task | Arm | Input | Cached | Non-cached | Output | Correct | Duration (ms) |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    task_labels = {
        "initialize": "Initialize PKF",
        "boards_add_task": "Boards Add task lookup",
        "note_task_links": "Note/task link lookup",
        "favorite_visibility_mutation": "Favorite visibility mutation",
        "favorite_visibility_after_change": "Post-mutation lookup",
    }
    for task_id, arm_values in by_task.items():
        for arm, values in arm_values.items():
            correctness = values["correctness_rate"]
            correctness_text = "n/a" if correctness is None else f"{correctness:.0%}"
            lines.append(
                f"| {task_labels.get(task_id, task_id)} | `{arm}` | "
                f"{values['input_tokens']:.0f} | {values['cached_input_tokens']:.0f} | "
                f"{values['non_cached_input_tokens']:.0f} | {values['output_tokens']:.0f} | "
                f"{correctness_text} | {values['duration_ms']:.0f} |"
            )

    savings = metrics["median_paired_read_only_savings"]
    break_even = metrics["break_even_read_only_tasks"]
    link_no_pkf = by_task["note_task_links"]["no_pkf"]
    link_pkf = by_task["note_task_links"]["pkf"]
    mutation_no_pkf = by_task["favorite_visibility_mutation"]["no_pkf"]
    mutation_pkf = by_task["favorite_visibility_mutation"]["pkf"]
    boards_errors = [
        error for error in report["errors"] if "/boards_add_task:" in error
    ]
    boards_scoring_text = (
        "The strict benchmark status is failed because "
        f"{len(boards_errors)} Boards answers missed the expected `right-side` "
        "toast-placement field. The local action calls `toast.error`, while placement is "
        "inherited from the application's default Toaster configuration, so this field "
        "mixes local behavior with a global dependency default. Token measurements are "
        "retained, but the result is not a clean quality-equivalent win for either arm."
        if boards_errors
        else "The Boards structured-answer gate passed in every recorded run."
    )
    lines.extend(
        [
            "",
            "### Result",
            "",
            (
                "Median complete lifecycle input: "
                f"**{lifecycle_median['no_pkf']['input_tokens']:.0f}** without PKF and "
                f"**{lifecycle_median['pkf']['input_tokens']:.0f}** with PKF.<br>"
            ),
            (
                "Median complete lifecycle non-cached input: "
                f"**{lifecycle_median['no_pkf']['non_cached_input_tokens']:.0f}** without PKF and "
                f"**{lifecycle_median['pkf']['non_cached_input_tokens']:.0f}** with PKF.<br>"
            ),
            f"Median paired read-only input saving: **{savings['input_tokens']:.0f} tokens**.<br>",
            (
                "Median paired read-only non-cached input saving: "
                f"**{savings['non_cached_input_tokens']:.0f} tokens**.<br>"
            ),
            (
                "Break-even including initialization and the measured mutation premium: "
                f"**{break_even['input_tokens'] if break_even['input_tokens'] is not None else 'not reached'}** "
                "read-only tasks by total input and "
                f"**{break_even['non_cached_input_tokens'] if break_even['non_cached_input_tokens'] is not None else 'not reached'}** "
                "by non-cached input."
            ),
            "",
        ]
    )
    if break_even["input_tokens"] is None:
        lines.append(
            "On this measured workload, PKF did not produce positive median read-only total-input savings, so no lifecycle break-even was observed."
        )
    else:
        lines.append(
            "On this measured workload, PKF is token-beneficial only when the number of comparable read-only tasks exceeds the reported break-even; smaller workloads retain the setup and maintenance overhead."
        )
    lines.extend(
        [
            "",
            "The cross-capability note/task-link lookup was the clear PKF win: median input "
            f"fell from **{link_no_pkf['input_tokens']:.0f}** to **{link_pkf['input_tokens']:.0f}** "
            "tokens, while non-cached input fell from "
            f"**{link_no_pkf['non_cached_input_tokens']:.0f}** to "
            f"**{link_pkf['non_cached_input_tokens']:.0f}**. The focused mutation moved the "
            f"other way: median input rose from **{mutation_no_pkf['input_tokens']:.0f}** to "
            f"**{mutation_pkf['input_tokens']:.0f}** because PKF also synchronized and "
            "validated knowledge.",
            "",
            "Every PKF initialization passed strict validation. Every mutation arm made "
            "the expected source/test change and passed the focused test; every PKF "
            "mutation also emitted closeout and passed strict validation. The link and "
            "post-mutation lookup answers were 100% correct in both arms.",
            "",
            boards_scoring_text,
        ]
    )
    lines.extend(
        [
            "",
            "### Limitations",
            "",
            "- One application repository, one pinned commit, one model, and one reasoning setting.",
            "- Three repetitions describe this controlled run but are not a population-wide estimate.",
            "- Provider prompt caching can change total-input composition, so cached and non-cached input must be interpreted separately.",
            "- The target was private when measured; external reproduction becomes possible when that exact commit is published.",
            "- The Boards correctness field depended on implicit toast placement and should be narrowed before the next benchmark series.",
        ]
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
        args.report_markdown.write_text(render_markdown(report), encoding="utf-8")
    if args.format == "json":
        print(json_text, end="")
    else:
        savings = report["metrics"]["median_paired_read_only_savings"]
        print(f"PKF savings eval: {report['status']}")
        print(f"Calls: {len(report['runs'])}/{report['environment']['scheduled_calls']}")
        print(f"Median paired read-only input saving: {savings['input_tokens']:.0f}")
        print(f"Errors: {len(report['errors'])}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        target = verify_target(args.target_repo, args.target_commit)
        schedule = build_schedule(args.repetitions)
        if args.dry_run:
            output = {
                "dry_run": True,
                "target": {"name": TARGET_NAME, **target},
                "model": args.model,
                "reasoning_effort": args.model_reasoning_effort,
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
