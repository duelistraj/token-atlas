#!/usr/bin/env python3
"""Compare Token Atlas PKF lifecycle cost with an adaptive local-probe baseline."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
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
import threading
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pkf_lib import PkfParseError, listify, read_front_matter  # noqa: E402
from pkf_contract import LEAF_MODULE_DOCS  # noqa: E402
from pkf_tokens import count_tokens  # noqa: E402

PUBLIC_SKILL = ROOT / "skills" / "token-atlas"
DEFAULT_REPETITIONS = 3
DEFAULT_TIMEOUT_SECONDS = 1_800
DEFAULT_ARTIFACTS_ROOT = ROOT / "benchmarks" / "artifacts"
DEFAULT_BASELINES_ROOT = ROOT / "benchmarks" / "baselines"
REPORT_SCHEMA_VERSION = 10
ALLOWED_REASONING_EFFORTS = ("minimal", "low", "medium", "high", "xhigh")
RETRIEVAL_PHASE_MODES = {
    "simple_retrieval": "local",
    "cross_capability_retrieval": "cross_capability",
}
EVALUATION_PHASES = (*RETRIEVAL_PHASE_MODES, "mutation", "post_mutation", "closeout")
RUN_ID_PHASE_LABELS = {
    "simple_retrieval": "simple",
    "cross_capability_retrieval": "cross",
    "mutation": "mutation",
    "post_mutation": "post",
    "closeout": "closeout",
}
ARTIFACT_MODES = ("full", "public", "off")
ARM_DEFINITIONS = {
    "source_only": "No PKF and no adaptive local-probe instructions; generic source discovery only.",
    "probe_only": "Adaptive bounded local probe, with no PKF installed or available.",
    "pkf": "PKF installed with adaptive retrieval and repository-local semantic closeout; an individual task may bypass retrieval.",
}


def evaluation_arms(*, include_source_only: bool) -> tuple[str, ...]:
    return (
        ("source_only", "probe_only", "pkf")
        if include_source_only
        else ("probe_only", "pkf")
    )


RUN_ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
PKF_ROUTE_MARKER_PATTERN = re.compile(
    r"^PKF route: (?P<routes>[a-z0-9][a-z0-9-]*(?: \+ [a-z0-9][a-z0-9-]*)*); "
    r"(?P<leaves>[1-9][0-9]*) unique leaves; fallback=(?P<fallback>yes|no)$"
)

MANAGED_START = "<!-- token-atlas:bootstrap:start -->"
MANAGED_END = "<!-- token-atlas:bootstrap:end -->"
PROBE_START = "<!-- token-atlas-eval:probe:start -->"
PROBE_END = "<!-- token-atlas-eval:probe:end -->"
PROBE_ONLY_AGENTS = """<!-- token-atlas-eval:probe:start -->
## Adaptive local discovery

For a likely single-capability task, use a cheap local probe of at most two
targeted `rg`/`sg` searches and three source files. If that resolves a known path
or symbol, continue locally. For cross-capability, architecture, ownership, or
repository-wide work, use source-only discovery because no PKF is installed.
<!-- token-atlas-eval:probe:end -->
"""

@dataclass(frozen=True)
class TaskSpec:
    task_id: str
    prompt: str
    expected_answers: Mapping[str, bool]
    retrieval_mode: str = "local"


@dataclass(frozen=True)
class MutationSpec:
    task_id: str
    prompt: str
    expected_paths: tuple[str, ...]
    test_command: tuple[str, ...]


@dataclass(frozen=True)
class CloseoutSpec:
    task_id: str
    control_prompt: str
    pkf_prompt: str
    patch: Path
    expected_paths: tuple[str, ...]
    test_command: tuple[str, ...]


@dataclass(frozen=True)
class BenchmarkSpec:
    schema_version: int
    benchmark_id: str
    retrieval_tasks: tuple[TaskSpec, ...]
    mutation: MutationSpec | None
    post_mutation: TaskSpec | None
    closeout: CloseoutSpec | None
    workspace_links: tuple[str, ...]
    digest: str
    path: Path


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
    cross_declared_document_paths: tuple[str, ...] = ()
    cross_expected_document_paths: tuple[str, ...] = ()
    cross_observed_document_paths: tuple[str, ...] = ()
    cross_missing_route_ids: tuple[str, ...] = ()
    cross_missing_document_paths: tuple[str, ...] = ()
    cross_unexpected_document_paths: tuple[str, ...] = ()
    cross_requirement_count: int = 0
    cross_covered_requirement_count: int = 0
    cross_conflicting_requirement_ids: tuple[str, ...] = ()
    cross_uncovered_requirement_ids: tuple[str, ...] = ()
    cross_unresolved_document_paths: tuple[str, ...] = ()
    cross_coverage_status: str = "not_applicable"
    cross_irredundancy_status: str = "not_applicable"
    cross_redundant_document_paths: tuple[str, ...] = ()
    cross_estimated_tokens: int = 0
    cross_token_estimator: str = "not_applicable"


class EvaluationError(Exception):
    """Invalid evaluation setup or runner usage."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-repo", type=Path, required=True)
    parser.add_argument("--target-commit", default="HEAD")
    parser.add_argument("--benchmark-spec", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--baselines-root", type=Path, default=DEFAULT_BASELINES_ROOT)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--model-reasoning-effort",
        choices=ALLOWED_REASONING_EFFORTS,
        required=True,
    )
    parser.add_argument("--repetitions", type=int, default=DEFAULT_REPETITIONS)
    parser.add_argument(
        "--phases",
        required=True,
        help=(
            "Comma-separated explicit phases: simple_retrieval,"
            "cross_capability_retrieval,mutation,post_mutation,closeout."
        ),
    )
    parser.add_argument(
        "--include-source-only",
        action="store_true",
        help="Add source_only to selected retrieval phases as an attribution diagnostic.",
    )
    parser.add_argument("--jobs", type=int, default=0, help="Maximum parallel calls; 0 runs every ready job.")
    parser.add_argument("--state-from", type=Path)
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
    if args.jobs < 0:
        parser.error("--jobs must be zero or positive")
    phases = tuple(dict.fromkeys(value.strip() for value in args.phases.split(",") if value.strip()))
    invalid_phases = sorted(set(phases) - set(EVALUATION_PHASES))
    if not phases or invalid_phases:
        parser.error("--phases must contain only: " + ", ".join(EVALUATION_PHASES))
    if args.state_from is not None and "mutation" in phases:
        parser.error("--state-from cannot be combined with the mutation phase")
    if "post_mutation" in phases and "mutation" not in phases and args.state_from is None:
        parser.error("standalone post_mutation requires --state-from")
    args.phases = phases
    if args.run_id is not None and not RUN_ID_PATTERN.fullmatch(args.run_id):
        parser.error("--run-id must be 1-128 lowercase letters, digits, dots, underscores, or hyphens")
    return args


def load_benchmark_spec(path: Path) -> BenchmarkSpec:
    resolved = path.resolve()
    try:
        raw_text = resolved.read_text(encoding="utf-8")
        value = json.loads(raw_text)
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(f"benchmark spec must be readable JSON: {resolved}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise EvaluationError("benchmark spec schema_version must be 1")
    benchmark_id = value.get("id")
    if not isinstance(benchmark_id, str) or not RUN_ID_PATTERN.fullmatch(benchmark_id):
        raise EvaluationError("benchmark spec id must be a lowercase run identifier")

    def task(raw: Any, *, required_mode: bool = False) -> TaskSpec:
        if not isinstance(raw, dict):
            raise EvaluationError("benchmark task must be an object")
        task_id = raw.get("id")
        prompt = raw.get("prompt")
        expected = raw.get("expected_answers")
        mode = raw.get("retrieval_mode", "local")
        if not isinstance(task_id, str) or not RUN_ID_PATTERN.fullmatch(task_id):
            raise EvaluationError("benchmark task id is invalid")
        if not isinstance(prompt, str) or not prompt.strip():
            raise EvaluationError(f"benchmark task {task_id} requires a prompt")
        if not isinstance(expected, dict) or not expected or not all(
            isinstance(key, str) and isinstance(answer, bool) for key, answer in expected.items()
        ):
            raise EvaluationError(f"benchmark task {task_id} requires boolean expected_answers")
        if required_mode and mode not in {"local", "cross_capability"}:
            raise EvaluationError(f"benchmark task {task_id} has invalid retrieval_mode")
        return TaskSpec(task_id, prompt.strip(), expected, str(mode))

    retrieval_raw = value.get("retrieval", [])
    if not isinstance(retrieval_raw, list):
        raise EvaluationError("benchmark spec retrieval must be a list")
    retrieval = tuple(task(item, required_mode=True) for item in retrieval_raw)

    mutation_raw = value.get("mutation")
    mutation = None
    if mutation_raw is not None:
        if not isinstance(mutation_raw, dict):
            raise EvaluationError("benchmark mutation must be an object")
        command = mutation_raw.get("test_command")
        paths = mutation_raw.get("expected_paths")
        if not isinstance(command, list) or not command or not all(isinstance(item, str) and item for item in command):
            raise EvaluationError("benchmark mutation test_command must be a non-empty string list")
        if not isinstance(paths, list) or not paths or not all(isinstance(item, str) and item for item in paths):
            raise EvaluationError("benchmark mutation expected_paths must be a non-empty string list")
        task_id = mutation_raw.get("id")
        prompt = mutation_raw.get("prompt")
        if not isinstance(task_id, str) or not RUN_ID_PATTERN.fullmatch(task_id) or not isinstance(prompt, str) or not prompt.strip():
            raise EvaluationError("benchmark mutation requires valid id and prompt")
        mutation = MutationSpec(task_id, prompt.strip(), tuple(paths), tuple(command))

    post_raw = value.get("post_mutation")
    post_mutation = task(post_raw) if post_raw is not None else None

    closeout_raw = value.get("closeout")
    closeout = None
    if closeout_raw is not None:
        if not isinstance(closeout_raw, dict):
            raise EvaluationError("benchmark closeout must be an object")
        required = ("id", "control_prompt", "pkf_prompt", "patch", "expected_paths", "test_command")
        if any(field not in closeout_raw for field in required):
            raise EvaluationError("benchmark closeout is missing required fields")
        patch = (resolved.parent / str(closeout_raw["patch"])).resolve()
        if not patch.is_file():
            raise EvaluationError(f"benchmark closeout patch does not exist: {patch}")
        closeout = CloseoutSpec(
            task_id=str(closeout_raw["id"]),
            control_prompt=str(closeout_raw["control_prompt"]).strip(),
            pkf_prompt=str(closeout_raw["pkf_prompt"]).strip(),
            patch=patch,
            expected_paths=tuple(str(item) for item in closeout_raw["expected_paths"]),
            test_command=tuple(str(item) for item in closeout_raw["test_command"]),
        )
        if not RUN_ID_PATTERN.fullmatch(closeout.task_id) or not closeout.control_prompt or not closeout.pkf_prompt:
            raise EvaluationError("benchmark closeout requires valid prompts and id")
        if not closeout.expected_paths or not closeout.test_command:
            raise EvaluationError("benchmark closeout requires expected_paths and test_command")

    links_raw = value.get("workspace_links", [])
    if not isinstance(links_raw, list):
        raise EvaluationError("benchmark spec workspace_links must be a list")
    workspace_links: list[str] = []
    for raw_link in links_raw:
        if not isinstance(raw_link, str) or not raw_link.strip():
            raise EvaluationError("benchmark workspace link must be a non-empty relative path")
        link = Path(raw_link)
        if link.is_absolute() or ".." in link.parts or raw_link.startswith("."):
            raise EvaluationError(f"benchmark workspace link must stay inside the target: {raw_link}")
        workspace_links.append(link.as_posix())

    return BenchmarkSpec(
        schema_version=1,
        benchmark_id=benchmark_id,
        retrieval_tasks=retrieval,
        mutation=mutation,
        post_mutation=post_mutation,
        closeout=closeout,
        workspace_links=tuple(dict.fromkeys(workspace_links)),
        digest=hashlib.sha256(raw_text.encode("utf-8")).hexdigest(),
        path=resolved,
    )


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


def publishable_path(path: Path, label: str) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(ROOT).as_posix()
    except ValueError:
        return f"<{label}>/{resolved.name}"


def excluded_target_member(name: str) -> bool:
    normalized = name.replace("\\", "/").removeprefix("./")
    prefixes = (
        ".ai",
        ".pkf-init.json",
        ".token-atlas",
        ".agents/skills/token-atlas",
        ".claude/skills/token-atlas",
        ".codex/skills/token-atlas",
    )
    return any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in prefixes)


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
        for member in archive.getmembers():
            if not excluded_target_member(member.name):
                archive.extract(member, destination, filter="data")
    archive_path.unlink()


def strip_managed_bootstrap(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if MANAGED_START in text or MANAGED_END in text:
        if text.count(MANAGED_START) != 1 or text.count(MANAGED_END) != 1:
            raise EvaluationError("target AGENTS.md has malformed Token Atlas managed markers")
        start = text.index(MANAGED_START)
        end = text.index(MANAGED_END, start) + len(MANAGED_END)
        text = text[:start] + text[end:]
    if re.search(r"(?i)(\.ai/PKF\.md|Token Atlas)", text):
        raise EvaluationError(
            "target AGENTS.md contains unmanaged PKF instructions; isolate them in Token Atlas managed markers"
        )
    remaining = text.strip()
    if remaining:
        path.write_text(remaining + "\n", encoding="utf-8")
    else:
        path.unlink()


def install_probe_policy(repo: Path) -> None:
    path = repo / "AGENTS.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else "# AGENTS\n"
    if PROBE_START in text or PROBE_END in text:
        raise EvaluationError("target AGENTS.md unexpectedly contains benchmark probe markers")
    path.write_text(text.rstrip() + "\n\n" + PROBE_ONLY_AGENTS.strip() + "\n", encoding="utf-8")


def strip_pkf(repo: Path) -> None:
    ai_dir = repo / ".ai"
    if ai_dir.exists():
        shutil.rmtree(ai_dir)
    installed_skill = repo / ".codex" / "skills" / "token-atlas"
    if installed_skill.exists():
        shutil.rmtree(installed_skill)
    strip_managed_bootstrap(repo / "AGENTS.md")


def install_public_skill(repo: Path) -> None:
    destination = repo / ".codex" / "skills" / "token-atlas"
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PUBLIC_SKILL, destination)


def link_workspace_paths(repo: Path, target_repo: Path, paths: Sequence[str]) -> None:
    for value in paths:
        source = target_repo / value
        destination = repo / value
        if not source.exists():
            raise EvaluationError(f"configured workspace link does not exist in target checkout: {value}")
        if destination.exists() or destination.is_symlink():
            raise EvaluationError(f"configured workspace link collides with exported content: {value}")
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.symlink_to(source, target_is_directory=source.is_dir())


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


def prepare_arms(
    workspace: Path,
    *,
    target_repo: Path,
    target_commit: str,
    baseline: Path,
    workspace_links: Sequence[str] = (),
    include_source_only: bool = False,
) -> dict[str, Path]:
    exported = workspace / "exported"
    export_target(target_repo, target_commit, exported)
    strip_pkf(exported)
    arms: dict[str, Path] = {}
    for arm in evaluation_arms(include_source_only=include_source_only):
        repo = workspace / arm
        shutil.copytree(exported, repo, symlinks=True)
        if arm == "pkf":
            runtime = baseline / "runtime"
            if not (runtime / ".ai" / "PKF.md").is_file():
                raise EvaluationError(f"baseline runtime is incomplete: {baseline}")
            shutil.copytree(runtime / ".ai", repo / ".ai")
            if (runtime / "AGENTS.md").is_file():
                shutil.copy2(runtime / "AGENTS.md", repo / "AGENTS.md")
            install_public_skill(repo)
        elif arm == "probe_only":
            install_probe_policy(repo)
        link_workspace_paths(repo, target_repo, workspace_links)
        initialize_git(repo, "Benchmark source baseline")
        arms[arm] = repo
    return arms


def resolve_baseline(args: argparse.Namespace, target: Mapping[str, str]) -> tuple[Path, dict[str, Any]]:
    repository_id = re.sub(r"[^a-z0-9._-]+", "-", args.target_repo.resolve().name.lower()).strip("-.") or "repository"
    path = (
        args.baseline.resolve()
        if args.baseline is not None
        else (args.baselines_root / repository_id / target["tree"]).resolve()
    )
    manifest_path = path / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvaluationError(
            f"sealed PKF baseline is missing or unreadable: {path}; create it once with scripts/pkf_baseline.py"
        ) from exc
    identity = manifest.get("target", {}) if isinstance(manifest, dict) else {}
    if identity.get("commit") != target["commit"] or identity.get("tree") != target["tree"]:
        raise EvaluationError("baseline target identity does not match --target-commit")
    runtime = path / "runtime"
    if not (runtime / ".ai" / "PKF.md").is_file():
        raise EvaluationError(f"baseline runtime is incomplete: {path}")
    if manifest.get("runtime_sha256") != sha256_tree(runtime):
        raise EvaluationError("baseline runtime digest does not match its manifest")
    if manifest.get("skill_sha256") != sha256_tree(PUBLIC_SKILL):
        raise EvaluationError(
            "baseline was generated with a different public skill; explicitly migrate or approve a new baseline"
        )
    if manifest.get("validation_status") != "passed":
        raise EvaluationError("baseline does not record successful strict validation")
    generation = manifest.get("generation", {})
    if any(
        not isinstance(generation.get(role), Mapping)
        or generation[role].get("returncode") != 0
        for role in ("initialization", "completeness_review")
    ):
        raise EvaluationError("baseline does not record both successful generation passes")
    acceptance = manifest.get("semantic_acceptance", {})
    if not isinstance(acceptance, Mapping) or acceptance.get("status") != "model_review_completed":
        raise EvaluationError("baseline does not record the repository completeness review")
    inventory = manifest.get("runtime_inventory", {})
    leaf_paths = inventory.get("leaf_paths", []) if isinstance(inventory, Mapping) else []
    if not isinstance(leaf_paths, list) or not leaf_paths:
        raise EvaluationError("baseline records no evidence-backed PKF leaves")
    if any(not isinstance(value, str) or not (runtime / value).is_file() for value in leaf_paths):
        raise EvaluationError("baseline inventory references a missing PKF leaf")
    return path, manifest


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
        "declared_loads": (),
        "expected_loads": (),
        "missing_route_ids": tuple(route_ids),
        "requirement_count": 0,
        "covered_requirement_count": 0,
        "conflicting_requirements": (),
        "uncovered_requirements": (),
        "unresolved_loads": (),
        "coverage_status": "incomplete" if route_ids else "unknown",
        "irredundancy_status": "invalid" if route_ids else "unknown",
        "redundant_loads": (),
        "estimated_tokens": 0,
        "token_estimator": "approximate",
    }
    if not route_ids:
        return empty
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
    declared_loads: set[str] = set()
    missing: list[str] = []
    requirements: set[str] = set()
    coverage_by_load: dict[str, set[str]] = {}
    metadata_valid = True
    for route_id in route_ids:
        route = routes.get(route_id)
        if not isinstance(route, Mapping):
            missing.append(route_id)
            metadata_valid = False
            continue
        raw_loads = route.get("loads")
        route_requirements = route.get("requirements")
        load_coverage = route.get("load_coverage")
        if (
            not isinstance(route_requirements, list)
            or not route_requirements
            or not all(
                isinstance(value, str)
                and re.fullmatch(r"[a-z0-9][a-z0-9-]*", value)
                for value in route_requirements
            )
            or len(set(route_requirements)) != len(route_requirements)
            or not isinstance(raw_loads, list)
            or not raw_loads
            or not all(isinstance(value, str) and value for value in raw_loads)
            or len(set(raw_loads)) != len(raw_loads)
            or not isinstance(load_coverage, Mapping)
            or set(map(str, load_coverage)) != set(raw_loads)
        ):
            metadata_valid = False
            continue
        route_loads = set(raw_loads)
        declared_loads.update(route_loads)
        route_requirement_set = set(route_requirements)
        requirements.update(route_requirement_set)
        for load, raw_coverage in load_coverage.items():
            if (
                not isinstance(raw_coverage, list)
                or not all(
                    isinstance(value, str)
                    and re.fullmatch(r"[a-z0-9][a-z0-9-]*", value)
                    for value in raw_coverage
                )
                or len(set(raw_coverage)) != len(raw_coverage)
            ):
                metadata_valid = False
                continue
            covered = set(raw_coverage)
            if not covered <= route_requirement_set:
                metadata_valid = False
            coverage_by_load.setdefault(str(load), set()).update(covered & route_requirement_set)

    covered = set().union(*coverage_by_load.values()) if coverage_by_load else set()
    providers = {
        requirement: {
            load
            for load, covered_requirements in coverage_by_load.items()
            if requirement in covered_requirements
        }
        for requirement in requirements
    }
    conflicts = tuple(sorted(requirement for requirement, loads in providers.items() if len(loads) > 1))
    uncovered = tuple(sorted(requirements - covered))
    expected_loads = {
        next(iter(loads))
        for loads in providers.values()
        if len(loads) == 1
    }
    unresolved = tuple(
        sorted(
            load
            for load in declared_loads
            if not (repo / load).is_file() or (repo / load).name not in LEAF_MODULE_DOCS
        )
    )
    ownership_valid = bool(
        route_ids
        and metadata_valid
        and not missing
        and not conflicts
        and not uncovered
        and not unresolved
        and requirements == covered
    )
    redundant = tuple(sorted(declared_loads - expected_loads)) if ownership_valid else ()
    if ownership_valid:
        coverage_status = "complete"
        irredundancy_status = "irredundant" if not redundant else "redundant"
    else:
        coverage_status = "incomplete"
        irredundancy_status = "invalid"

    load_files = [repo / load for load in sorted(expected_loads) if (repo / load).is_file()]
    text = "\n".join(path.read_text(encoding="utf-8") for path in load_files)
    estimated_tokens, estimator = count_tokens(text, None)
    return {
        "declared_loads": tuple(sorted(declared_loads)),
        "expected_loads": tuple(sorted(expected_loads)),
        "missing_route_ids": tuple(missing),
        "requirement_count": len(requirements),
        "covered_requirement_count": len(covered),
        "conflicting_requirements": conflicts,
        "uncovered_requirements": uncovered,
        "unresolved_loads": unresolved,
        "coverage_status": coverage_status,
        "irredundancy_status": irredundancy_status,
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


def make_run_id(args: argparse.Namespace, spec: BenchmarkSpec | None = None) -> str:
    if args.run_id:
        return args.run_id
    timestamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    phase_label = "-".join(RUN_ID_PHASE_LABELS[phase] for phase in args.phases)
    if args.include_source_only:
        phase_label += "-source-diag"
    prefix = "-".join(
        (
            "token-atlas",
            slug(args.model),
            slug(args.model_reasoning_effort),
            slug(spec.benchmark_id if spec is not None else "benchmark"),
            phase_label,
        )
    )
    suffix = f"-{slug(run_class(args.repetitions))}-{timestamp}"
    available = 128 - len(suffix)
    if len(prefix) > available:
        digest = hashlib.sha256(prefix.encode("utf-8")).hexdigest()[:8]
        prefix = prefix[: available - len(digest) - 1].rstrip("-.") + f"-{digest}"
    return prefix + suffix


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
        self._lock = threading.RLock()
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
        call_id: str | None = None,
    ) -> None:
        if self.mode == "off":
            return
        with self._lock:
            self._counter += 1
            call_id = call_id or (
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
                self._write_private(call_dir / "result.json", json.dumps(asdict(result), indent=2, sort_keys=True) + "\n")
                if schema_path is not None and schema_path.is_file():
                    self._write_private(call_dir / "schema.json", schema_path.read_text(encoding="utf-8"))
                if result.answer is not None:
                    self._write_private(call_dir / "answer.json", json.dumps(result.answer, indent=2, sort_keys=True) + "\n")
                self._write_private(call_dir / "source.diff", repository_diff(repo, pkf_only=False))
                self._write_private(call_dir / "pkf.diff", repository_diff(repo, pkf_only=True))
                route_output = route_trace_excerpt(stdout)
                if route_output:
                    self._write_private(call_dir / "route-output.jsonl", route_output + "\n")
            self.calls.sort(key=lambda item: item["call_id"])
            self.write_manifest("running")

    def snapshot_pkf(self, label: str, repo: Path) -> None:
        if self.mode != "full":
            return
        with self._lock:
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
        if self.mode == "off":
            return
        with self._lock:
            if self.mode == "full":
                self._write_private(
                    self.private_dir / "validation" / f"{slug(label)}.json",
                    json.dumps({"passed": passed, "output": output}, indent=2, sort_keys=True) + "\n",
                )
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
        temporary = self.manifest_path.with_suffix(".json.tmp")
        temporary.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        os.replace(temporary, self.manifest_path)

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
    if arm != "pkf" or phase not in {*RETRIEVAL_PHASE_MODES, "post_mutation"}:
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
    call_id: str | None = None,
) -> tuple[CodexResult, str]:
    source_codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    eval_codex_home = workspace / "codex-homes" / (call_id or f"r{repetition}-{arm}-{task_id}")
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
        schema_path = workspace / "schemas" / f"{call_id or task_id}.schema.json"
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
    cross_declared_documents: tuple[str, ...] = ()
    cross_expected_documents: tuple[str, ...] = ()
    cross_observed_documents: tuple[str, ...] = ()
    cross_missing_route_ids: tuple[str, ...] = ()
    cross_missing_documents: tuple[str, ...] = ()
    cross_unexpected_documents: tuple[str, ...] = ()
    cross_requirement_count = 0
    cross_covered_requirement_count = 0
    cross_conflicting_requirements: tuple[str, ...] = ()
    cross_uncovered_requirements: tuple[str, ...] = ()
    cross_unresolved_documents: tuple[str, ...] = ()
    cross_coverage_status = "not_applicable"
    cross_irredundancy_status = "not_applicable"
    cross_redundant_documents: tuple[str, ...] = ()
    cross_estimated_tokens = 0
    cross_token_estimator = "not_applicable"
    if task is not None and task.retrieval_mode == "cross_capability" and arm == "pkf":
        cross_route_marker_status = str(route_marker["status"])
        cross_route_ids = tuple(route_marker["route_ids"])
        cross_route_unique_leaf_count = int(route_marker["unique_leaf_count"])
        cross_route_fallback = route_marker["fallback"]
        configured = configured_cross_routes(
            repo,
            cross_route_ids,
        )
        cross_declared_documents = tuple(configured["declared_loads"])
        cross_expected_documents = tuple(configured["expected_loads"])
        cross_missing_route_ids = tuple(configured["missing_route_ids"])
        cross_requirement_count = int(configured["requirement_count"])
        cross_covered_requirement_count = int(configured["covered_requirement_count"])
        cross_conflicting_requirements = tuple(configured["conflicting_requirements"])
        cross_uncovered_requirements = tuple(configured["uncovered_requirements"])
        cross_unresolved_documents = tuple(configured["unresolved_loads"])
        cross_coverage_status = str(configured["coverage_status"])
        cross_irredundancy_status = str(configured["irredundancy_status"])
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
            sorted(set(cross_expected_documents) - leaf_reads)
        )
        cross_unexpected_documents = tuple(
            sorted(leaf_reads - set(cross_expected_documents))
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
        cross_declared_document_paths=cross_declared_documents,
        cross_expected_document_paths=cross_expected_documents,
        cross_observed_document_paths=cross_observed_documents,
        cross_missing_route_ids=cross_missing_route_ids,
        cross_missing_document_paths=cross_missing_documents,
        cross_unexpected_document_paths=cross_unexpected_documents,
        cross_requirement_count=cross_requirement_count,
        cross_covered_requirement_count=cross_covered_requirement_count,
        cross_conflicting_requirement_ids=cross_conflicting_requirements,
        cross_uncovered_requirement_ids=cross_uncovered_requirements,
        cross_unresolved_document_paths=cross_unresolved_documents,
        cross_coverage_status=cross_coverage_status,
        cross_irredundancy_status=cross_irredundancy_status,
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
            call_id=call_id,
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
    for path in knowledge.glob("*/*.md"):
        if path.name not in LEAF_MODULE_DOCS:
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


def run_focused_test(repo: Path, command: Sequence[str]) -> bool:
    completed = run_command(
        command,
        cwd=repo,
        check=False,
        timeout=600,
    )
    return completed.returncode == 0


def score_closeout(
    result: CodexResult,
    repo: Path,
    arm: str,
    closeout: CloseoutSpec,
    artifacts: ArtifactStore | None = None,
) -> CodexResult:
    changes = changed_paths(repo)
    expected = set(closeout.expected_paths)
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
    mutation: MutationSpec,
    artifacts: ArtifactStore | None = None,
) -> CodexResult:
    changes = changed_paths(repo)
    expected_changes = set(mutation.expected_paths).issubset(changes)
    focused_test_passed = run_focused_test(repo, mutation.test_command)
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
        changed_expected_paths=expected_changes,
        focused_test_passed=focused_test_passed,
        pkf_validation_passed=pkf_validation_passed,
    )


def retrieval_arm_order(repetition: int, *, include_source_only: bool) -> tuple[str, ...]:
    if not include_source_only:
        return two_arm_order(repetition)
    orders = (
        ("source_only", "probe_only", "pkf"),
        ("probe_only", "pkf", "source_only"),
        ("pkf", "source_only", "probe_only"),
    )
    return orders[(repetition - 1) % len(orders)]


def two_arm_order(repetition: int) -> tuple[str, ...]:
    return ("probe_only", "pkf") if repetition % 2 else ("pkf", "probe_only")


def build_schedule(
    repetitions: int,
    phases: Sequence[str],
    spec: BenchmarkSpec,
    *,
    include_source_only: bool = False,
) -> list[dict[str, Any]]:
    schedule: list[dict[str, Any]] = []
    tasks_by_retrieval_phase = {
        phase: tuple(
            task for task in spec.retrieval_tasks if task.retrieval_mode == retrieval_mode
        )
        for phase, retrieval_mode in RETRIEVAL_PHASE_MODES.items()
    }
    for phase in RETRIEVAL_PHASE_MODES:
        if phase in phases and not tasks_by_retrieval_phase[phase]:
            raise EvaluationError(f"selected {phase} phase has no matching tasks in benchmark spec")
    for repetition in range(1, repetitions + 1):
        for phase in RETRIEVAL_PHASE_MODES:
            if phase not in phases:
                continue
            for task in tasks_by_retrieval_phase[phase]:
                for arm in retrieval_arm_order(
                    repetition, include_source_only=include_source_only
                ):
                    schedule.append(
                        {
                            "repetition": repetition,
                            "arm": arm,
                            "task_id": task.task_id,
                            "phase": phase,
                        }
                    )
        if "mutation" in phases:
            if spec.mutation is None:
                raise EvaluationError("selected mutation phase is absent from benchmark spec")
            for arm in two_arm_order(repetition):
                schedule.append({"repetition": repetition, "arm": arm, "task_id": spec.mutation.task_id, "phase": "mutation"})
        if "post_mutation" in phases:
            if spec.post_mutation is None:
                raise EvaluationError("selected post_mutation phase is absent from benchmark spec")
            for arm in two_arm_order(repetition):
                schedule.append({"repetition": repetition, "arm": arm, "task_id": spec.post_mutation.task_id, "phase": "post_mutation", "depends_on": spec.mutation.task_id if "mutation" in phases and spec.mutation else "state_from"})
        if "closeout" in phases:
            if spec.closeout is None:
                raise EvaluationError("selected closeout phase is absent from benchmark spec")
            for arm in two_arm_order(repetition):
                schedule.append({"repetition": repetition, "arm": arm, "task_id": spec.closeout.task_id, "phase": "closeout"})
    for index, item in enumerate(schedule, 1):
        item["call_id"] = f"{index:03d}-r{item['repetition']}-{slug(item['arm'])}-{slug(item['task_id'])}"
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
        if arm == "pkf" and any(result.cross_coverage_status != "not_applicable" for result in grouped):
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
            entry["cross_conflicting_requirement_count"] = median(
                [len(result.cross_conflicting_requirement_ids) for result in grouped]
            )
            entry["cross_uncovered_requirement_count"] = median(
                [len(result.cross_uncovered_requirement_ids) for result in grouped]
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
            entry["cross_irredundancy_statuses"] = {
                status: sum(result.cross_irredundancy_status == status for result in grouped)
                for status in ("irredundant", "redundant", "invalid", "unknown")
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
    observed_arms = tuple(
        arm
        for arm in ("source_only", "probe_only", "pkf")
        if any(result.arm == arm for result in results)
    )
    for repetition in sorted({result.repetition for result in results}):
        repeated = [result for result in results if result.repetition == repetition]
        has_integrated_mutation = any(result.phase == "mutation" for result in repeated)
        entry: dict[str, Any] = {"repetition": repetition}
        for arm in observed_arms:
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
            (result.phase, result.arm): result
            for result in results
            if result.repetition == repetition
        }
        required = {
            ("mutation", "probe_only"),
            ("mutation", "pkf"),
            ("closeout", "probe_only"),
            ("closeout", "pkf"),
        }
        if not required.issubset(by_key):
            continue
        implementation = by_key[("mutation", "probe_only")]
        integrated = by_key[("mutation", "pkf")]
        closeout_control = by_key[("closeout", "probe_only")]
        closeout = by_key[("closeout", "pkf")]

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
        for task_id in {
            result.task_id
            for result in results
            if result.phase in {*RETRIEVAL_PHASE_MODES, "post_mutation"}
        }:
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
    diagnostic_comparisons: dict[str, Any] = {}
    for task_id, arm_values in by_task.items():
        task_comparisons: dict[str, Any] = {}
        task_diagnostics: dict[str, Any] = {}
        for label, baseline_arm, candidate_arm, destination in (
            ("probe_vs_pkf", "probe_only", "pkf", task_comparisons),
            ("source_vs_probe", "source_only", "probe_only", task_diagnostics),
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
            destination[label] = comparison
        comparisons[task_id] = task_comparisons
        if task_diagnostics:
            diagnostic_comparisons[task_id] = task_diagnostics

    return {
        "by_task": by_task,
        "comparisons": comparisons,
        "diagnostic_comparisons": diagnostic_comparisons,
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
    }


def performance_advisories(
    metrics: Mapping[str, Any],
    repetitions: int,
    spec: BenchmarkSpec,
) -> dict[str, Any]:
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

    local_task_ids = [
        task.task_id for task in spec.retrieval_tasks if task.retrieval_mode == "local"
    ]
    if spec.post_mutation is not None:
        local_task_ids.append(spec.post_mutation.task_id)
    for task_id in local_task_ids:
        local = comparisons.get(task_id, {}).get("probe_vs_pkf", {})
        if not local:
            continue
        value = local.get("non_cached_input_tokens", {}).get("percent")
        add_check(
            "local_bypass",
            f"{task_id}_non_cached_input_tokens_overhead",
            value,
            "<= 5%",
            value is not None and value <= 5.0,
        )
        phases["local_bypass"]["measurements"][task_id] = {
            metric: local.get(metric, {})
            for metric in ("input_tokens", "non_cached_input_tokens", "duration_ms", "tool_call_count")
        }
    for cross_task in (task for task in spec.retrieval_tasks if task.retrieval_mode == "cross_capability"):
        cross = comparisons.get(cross_task.task_id, {}).get("probe_vs_pkf", {})
        if not cross:
            continue
        non_cached_delta = cross.get("non_cached_input_tokens", {}).get("delta")
        add_check(
            "cross_retrieval",
            "cross_capability_non_cached_input_tokens_delta",
            non_cached_delta,
            "< 0",
            non_cached_delta is not None and non_cached_delta < 0,
        )
        pkf_cross = metrics.get("by_task", {}).get(cross_task.task_id, {}).get("pkf", {})
        phases["cross_retrieval"]["measurements"][cross_task.task_id] = {
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
    for key in tuple(value):
        if key.startswith("initialization_"):
            value.pop(key)
    return value


def evaluation_errors(
    results: Sequence[CodexResult],
    expected_count: int,
    spec: BenchmarkSpec,
) -> list[str]:
    errors: list[str] = []
    local_task_ids = {
        task.task_id for task in spec.retrieval_tasks if task.retrieval_mode == "local"
    }
    if spec.post_mutation is not None:
        local_task_ids.add(spec.post_mutation.task_id)
    cross_task_ids = {
        task.task_id for task in spec.retrieval_tasks if task.retrieval_mode == "cross_capability"
    }
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
        if result.task_id in local_task_ids:
            if result.explicit_ai_read_path_count or result.explicit_skill_read_path_count:
                errors.append(f"{label}: local task explicitly read PKF or Token Atlas paths")
            if result.arm == "pkf" and result.retrieval_decision != "bypassed":
                errors.append(f"{label}: local PKF task was not classified as bypassed")
            if result.route_marker_emitted:
                errors.append(f"{label}: bypassed local task emitted a PKF route marker")
        if result.arm != "pkf" and result.route_marker_emitted:
            errors.append(f"{label}: non-PKF arm emitted a PKF route marker")
        if result.task_id in cross_task_ids and result.arm == "pkf":
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
            if result.cross_conflicting_requirement_ids:
                requirement_ids = ", ".join(result.cross_conflicting_requirement_ids)
                errors.append(
                    f"{label}: conflicting authoritative owners for requirements: {requirement_ids}"
                )
            if result.cross_uncovered_requirement_ids:
                requirement_ids = ", ".join(result.cross_uncovered_requirement_ids)
                errors.append(f"{label}: uncovered selected-route requirements: {requirement_ids}")
            if result.cross_unresolved_document_paths:
                paths = ", ".join(result.cross_unresolved_document_paths)
                errors.append(f"{label}: selected routes reference unresolved leaves: {paths}")
            if result.cross_coverage_status != "complete":
                errors.append(
                    f"{label}: configured route requirement coverage is {result.cross_coverage_status}"
                )
            if result.cross_redundant_document_paths:
                paths = ", ".join(result.cross_redundant_document_paths)
                errors.append(
                    f"{label}: redundant route-declared leaf selection: {paths}"
                )
            elif result.cross_irredundancy_status != "irredundant":
                errors.append(
                    f"{label}: selected-route irredundancy is {result.cross_irredundancy_status}"
                )
            if not result.cross_expected_document_paths:
                errors.append(f"{label}: selected routes resolve no authoritative leaf documents")
            if result.cross_route_unique_leaf_count != len(result.cross_expected_document_paths):
                errors.append(
                    f"{label}: route marker reported {result.cross_route_unique_leaf_count} unique leaves "
                    f"but authoritative ownership resolves {len(result.cross_expected_document_paths)}"
                )
            if result.cross_route_fallback is not False or result.fallback_search:
                errors.append(f"{label}: configured cross-capability retrieval used fallback discovery")
            if result.cross_missing_document_paths:
                paths = ", ".join(result.cross_missing_document_paths)
                errors.append(f"{label}: cross-capability retrieval skipped expected leaves: {paths}")
            if result.cross_unexpected_document_paths:
                paths = ", ".join(result.cross_unexpected_document_paths)
                errors.append(f"{label}: cross-capability retrieval read outside its explicit route: {paths}")
        if result.phase == "mutation":
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
        if result.phase == "closeout":
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


def copy_job_repo(source: Path, destination: Path) -> Path:
    shutil.copytree(source, destination, symlinks=True)
    return destination


def state_repository(
    state_from: Path,
    repetition: int,
    arm: str,
    *,
    target: Mapping[str, str],
    baseline_manifest: Mapping[str, Any],
) -> Path:
    root = state_from.resolve()
    candidates = (
        root / f"r{repetition}" / arm / "repository",
        root / "private" / "states" / f"r{repetition}" / arm / "repository",
        root / "states" / f"r{repetition}" / arm / "repository",
    )
    for candidate in candidates:
        if candidate.is_dir():
            manifest_path = candidate.parent / "manifest.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise EvaluationError(f"saved mutation state manifest is unreadable: {manifest_path}") from exc
            if (
                manifest.get("schema_version") != 1
                or manifest.get("repetition") != repetition
                or manifest.get("arm") != arm
                or manifest.get("target", {}).get("commit") != target.get("commit")
                or manifest.get("target", {}).get("tree") != target.get("tree")
                or manifest.get("baseline_runtime_sha256") != baseline_manifest.get("runtime_sha256")
            ):
                raise EvaluationError(f"saved mutation state identity does not match this run: {manifest_path}")
            return candidate
    raise EvaluationError(f"saved mutation state is missing for repetition {repetition} arm {arm}: {root}")


def save_mutation_state(
    artifacts: ArtifactStore,
    repo: Path,
    *,
    repetition: int,
    arm: str,
    target: Mapping[str, str],
    baseline_manifest: Mapping[str, Any],
    workspace_links: Sequence[str] = (),
) -> None:
    if artifacts.mode != "full":
        return
    destination = artifacts.private_dir / "states" / f"r{repetition}" / arm
    with artifacts._lock:
        saved_repository = destination / "repository"
        shutil.copytree(
            repo,
            saved_repository,
            symlinks=True,
            ignore=shutil.ignore_patterns(".git"),
        )
        for value in workspace_links:
            linked = saved_repository / value
            if linked.is_symlink():
                linked.unlink()
        (destination / "manifest.json").write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "repetition": repetition,
                    "arm": arm,
                    "target": dict(target),
                    "baseline_runtime_sha256": baseline_manifest.get("runtime_sha256"),
                    "excluded_workspace_links": list(workspace_links),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        artifacts.write_manifest("running")


def execute(
    args: argparse.Namespace,
    target: Mapping[str, str],
    artifacts: ArtifactStore,
    spec: BenchmarkSpec,
    baseline: Path,
    baseline_manifest: Mapping[str, Any],
) -> dict[str, Any]:
    runtime_root = args.runtime_root.resolve()
    runtime_root.mkdir(parents=True, exist_ok=True)
    schedule = build_schedule(
        args.repetitions,
        args.phases,
        spec,
        include_source_only=args.include_source_only,
    )
    scheduled_arms = tuple(
        arm
        for arm in ("source_only", "probe_only", "pkf")
        if any(item["arm"] == arm for item in schedule)
    )
    source_only_diagnostic = "source_only" in scheduled_arms
    schedule_by_id = {item["call_id"]: item for item in schedule}
    results_by_id: dict[str, CodexResult] = {}
    started = time.monotonic()
    active = 0
    peak_active = 0
    active_lock = threading.Lock()

    with tempfile.TemporaryDirectory(prefix=".pkf-savings-", dir=runtime_root) as raw_workspace:
        workspace = Path(raw_workspace)
        base_arms: dict[int, dict[str, Path]] = {}
        for repetition in range(1, args.repetitions + 1):
            repetition_root = workspace / f"r{repetition}"
            repetition_root.mkdir(parents=True)
            base_arms[repetition] = prepare_arms(
                repetition_root,
                target_repo=args.target_repo.resolve(),
                target_commit=target["commit"],
                baseline=baseline,
                workspace_links=spec.workspace_links,
                include_source_only=source_only_diagnostic,
            )

        retrieval_by_id = {task.task_id: task for task in spec.retrieval_tasks}
        mutation_repos: dict[tuple[int, str], Path] = {}

        def prepare_repo(item: Mapping[str, Any]) -> Path:
            repetition = int(item["repetition"])
            arm = str(item["arm"])
            call_id = str(item["call_id"])
            destination = workspace / "jobs" / call_id / "repository"
            if item["phase"] == "post_mutation":
                if "mutation" in args.phases:
                    source = mutation_repos[(repetition, arm)]
                else:
                    assert args.state_from is not None
                    source = state_repository(
                        args.state_from,
                        repetition,
                        arm,
                        target=target,
                        baseline_manifest=baseline_manifest,
                    )
                return copy_job_repo(source, destination)
            repo = copy_job_repo(base_arms[repetition][arm], destination)
            if item["phase"] == "closeout":
                assert spec.closeout is not None
                completed = run_command(("git", "apply", str(spec.closeout.patch)), cwd=repo, check=False)
                if completed.returncode != 0:
                    raise EvaluationError(f"closeout patch did not apply for {call_id}: {completed.stderr.strip()}")
                if not run_focused_test(repo, spec.closeout.test_command):
                    raise EvaluationError(f"closeout pre-applied mutation failed its focused test for {call_id}")
            return repo

        def run_item(item: Mapping[str, Any], repo: Path) -> CodexResult:
            nonlocal active, peak_active
            repetition = int(item["repetition"])
            arm = str(item["arm"])
            phase = str(item["phase"])
            task_id = str(item["task_id"])
            call_id = str(item["call_id"])
            with active_lock:
                active += 1
                peak_active = max(peak_active, active)
            try:
                print(f"[{call_id}] {phase} {arm}/{task_id}", file=sys.stderr, flush=True)
                if phase in RETRIEVAL_PHASE_MODES:
                    task = retrieval_by_id[task_id]
                    result, _ = run_codex(
                        repetition=repetition, arm=arm, task_id=task_id, phase=phase,
                        prompt=task.prompt, repo=repo, model=args.model,
                        reasoning_effort=args.model_reasoning_effort,
                        timeout_seconds=args.timeout_seconds, workspace=workspace,
                        sandbox="read-only", task=task, artifacts=artifacts, call_id=call_id,
                    )
                    return result
                if phase == "mutation":
                    assert spec.mutation is not None
                    result, _ = run_codex(
                        repetition=repetition, arm=arm, task_id=task_id, phase=phase,
                        prompt=spec.mutation.prompt, repo=repo, model=args.model,
                        reasoning_effort=args.model_reasoning_effort,
                        timeout_seconds=args.timeout_seconds, workspace=workspace,
                        sandbox="workspace-write", artifacts=artifacts, call_id=call_id,
                    )
                    scored = score_mutation(result, repo, arm, spec.mutation, artifacts)
                    mutation_repos[(repetition, arm)] = repo
                    save_mutation_state(
                        artifacts, repo, repetition=repetition, arm=arm,
                        target=target, baseline_manifest=baseline_manifest,
                        workspace_links=spec.workspace_links,
                    )
                    return scored
                if phase == "post_mutation":
                    assert spec.post_mutation is not None
                    result, _ = run_codex(
                        repetition=repetition, arm=arm, task_id=task_id, phase=phase,
                        prompt=spec.post_mutation.prompt, repo=repo, model=args.model,
                        reasoning_effort=args.model_reasoning_effort,
                        timeout_seconds=args.timeout_seconds, workspace=workspace,
                        sandbox="read-only", task=spec.post_mutation,
                        artifacts=artifacts, call_id=call_id,
                    )
                    return result
                assert spec.closeout is not None
                result, _ = run_codex(
                    repetition=repetition, arm=arm, task_id=task_id, phase=phase,
                    prompt=spec.closeout.pkf_prompt if arm == "pkf" else spec.closeout.control_prompt,
                    repo=repo, model=args.model, reasoning_effort=args.model_reasoning_effort,
                    timeout_seconds=args.timeout_seconds, workspace=workspace,
                    sandbox="workspace-write" if arm == "pkf" else "read-only",
                    artifacts=artifacts, call_id=call_id,
                )
                return score_closeout(result, repo, arm, spec.closeout, artifacts)
            finally:
                with active_lock:
                    active -= 1

        independent = [item for item in schedule if item["phase"] != "post_mutation" or "mutation" not in args.phases]
        dependent = {
            (int(item["repetition"]), str(item["arm"])): item
            for item in schedule
            if item["phase"] == "post_mutation" and "mutation" in args.phases
        }
        worker_count = max(1, len(schedule) if args.jobs == 0 else min(args.jobs, len(schedule)))
        with concurrent.futures.ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures: dict[concurrent.futures.Future[CodexResult], tuple[dict[str, Any], Path]] = {}
            for item in independent:
                repo = prepare_repo(item)
                futures[executor.submit(run_item, item, repo)] = (item, repo)
            while futures:
                done, _ = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
                for future in done:
                    item, repo = futures.pop(future)
                    result = future.result()
                    results_by_id[str(item["call_id"])] = result
                    if item["phase"] == "mutation":
                        post = dependent.pop((int(item["repetition"]), str(item["arm"])), None)
                        mutation_ready = (
                            result.returncode == 0
                            and result.changed_expected_paths is True
                            and result.focused_test_passed is True
                        )
                        if post is not None and mutation_ready:
                            post_repo = prepare_repo(post)
                            futures[executor.submit(run_item, post, post_repo)] = (post, post_repo)
            if dependent:
                raise EvaluationError("post-mutation dependencies were not satisfied")

    results = [results_by_id[item["call_id"]] for item in schedule if item["call_id"] in results_by_id]
    errors = evaluation_errors(results, len(schedule), spec)
    metrics = aggregate_metrics(results)
    performance = performance_advisories(metrics, args.repetitions, spec)
    token_atlas_commit = run_command(("git", "rev-parse", "HEAD"), cwd=ROOT).stdout.strip()
    codex_version = run_command(("codex", "--version"), cwd=ROOT).stdout.strip()
    inventory = pkf_materialization_inventory(baseline / "runtime")
    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "run_id": artifacts.run_id,
        "artifact_manifest_path": "../manifest.json" if artifacts.mode != "off" else None,
        "benchmark": spec.benchmark_id,
        "benchmark_spec": {
            "path": publishable_path(spec.path, "external-spec"),
            "sha256": spec.digest,
            "schema_version": spec.schema_version,
        },
        "evaluation_kind": "real_repository_performance",
        "arm_definitions": {
            arm: ARM_DEFINITIONS[arm]
            for arm in scheduled_arms
        },
        "phases_selected": list(args.phases),
        "source_only_diagnostic": source_only_diagnostic,
        "run_class": run_class(args.repetitions),
        "replicated": args.repetitions >= 3,
        "status": "failed" if errors else ("preliminary" if args.repetitions < 3 else "completed"),
        "quality_status": "failed" if errors else "passed",
        "performance": performance,
        "recorded_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "target": {"name": args.target_repo.resolve().name, "commit": target["commit"], "tree": target["tree"]},
        "baseline": {
            "path": publishable_path(baseline, "external-baseline"),
            "runtime_sha256": baseline_manifest.get("runtime_sha256"),
            "created_at": baseline_manifest.get("created_at"),
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
            "scheduled_calls": len(schedule),
            "jobs": args.jobs,
            "peak_parallel_calls": peak_active,
            "makespan_ms": int((time.monotonic() - started) * 1000),
            "state_from": publishable_path(args.state_from, "external-state") if args.state_from is not None else None,
        },
        "methodology": {
            "arms": list(scheduled_arms),
            "task_ids": sorted({item["task_id"] for item in schedule}),
            "schedule": schedule,
            "initialization": "excluded; the immutable one-time baseline is reused",
            "primary_metric": "non_cached_input_tokens",
            "secondary_token_telemetry": ["input_tokens", "cached_input_tokens", "output_tokens"],
        },
        "pkf_inventory": inventory,
        "metrics": metrics,
        "runs": [public_result(result) for result in results],
        "errors": errors,
    }


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
        f"## Adaptive attribution benchmark — {report['benchmark']} — {run_label}",
        "",
        (
            "This benchmark compares the adaptive local-probe policy with PKF knowledge "
            "on the selected repository at commit "
            f"`{target['commit']}`. The target-specific tasks come only from the external "
            "benchmark specification."
        ),
        "",
        f"Publication class: **{run_label}**<br>",
        f"Replicated: **{'yes' if report.get('replicated') else 'no'}**<br>",
        f"Status: **{report['status']}**<br>",
        f"Quality: **{report['quality_status']}**<br>",
        f"Performance: **{report['performance']['status']}**<br>",
        f"Recorded: `{report['recorded_at']}`<br>",
        f"Model: `{environment['model']}` at `{environment['reasoning_effort']}` reasoning<br>",
        f"Repetitions: `{environment['repetitions']}` (`{environment['scheduled_calls']}` calls; "
        f"peak parallelism `{environment.get('peak_parallel_calls', 0)}`)",
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
            "`probe_only` isolates the bounded local-probe policy without PKF, and `pkf` "
            "installs adaptive retrieval and semantic closeout but may bypass PKF for an "
            "individual task. Token counts come "
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
    if report.get("source_only_diagnostic"):
        lines.insert(
            lines.index(f"### {usage_heading}"),
            "`source_only` was enabled as an optional diagnostic control with neither PKF nor the bounded probe policy.",
        )
        lines.insert(lines.index(f"### {usage_heading}"), "")
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
        if run.get("cross_coverage_status") != "not_applicable" and run["arm"] == "pkf":
            route_ids = " + ".join(run.get("cross_route_ids", [])) or "none"
            declared = ", ".join(run.get("cross_declared_document_paths", [])) or "none"
            expected = ", ".join(run.get("cross_expected_document_paths", [])) or "none"
            observed = ", ".join(run.get("cross_observed_document_paths", [])) or "none"
            missing = ", ".join(run.get("cross_missing_document_paths", [])) or "none"
            unexpected = ", ".join(run.get("cross_unexpected_document_paths", [])) or "none"
            conflicts = ", ".join(run.get("cross_conflicting_requirement_ids", [])) or "none"
            uncovered = ", ".join(run.get("cross_uncovered_requirement_ids", [])) or "none"
            unresolved = ", ".join(run.get("cross_unresolved_document_paths", [])) or "none"
            redundant = ", ".join(run.get("cross_redundant_document_paths", [])) or "none"
            lines.append(
                f"- Cross routes `{route_ids}` ({run.get('cross_route_marker_status', 'missing')} marker, "
                f"{run.get('cross_route_unique_leaf_count', 0)} reported unique leaves, "
                f"coverage={run.get('cross_coverage_status', 'unknown')}, "
                f"irredundancy={run.get('cross_irredundancy_status', 'unknown')}, "
                f"requirements={run.get('cross_covered_requirement_count', 0)}/"
                f"{run.get('cross_requirement_count', 0)}, "
                f"conflicts={conflicts}, uncovered={uncovered}, unresolved={unresolved}, "
                f"estimated route-content tokens={run.get('cross_estimated_tokens', 0)} "
                f"({run.get('cross_token_estimator', 'unknown')})): declared {declared}; redundant {redundant}; expected {expected}; "
                f"observed {observed}; missing {missing}; unexpected {unexpected}."
            )
        elif run.get("phase") in {"mutation", "closeout"} and run["arm"] == "pkf":
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
            .get(next((task for task, arms in report["metrics"].get("by_task", {}).items() if "pkf" in arms and any(run.get("task_id") == task and run.get("phase") == "mutation" for run in report.get("runs", []))), ""), {})
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
        lines.append("- Mutation and closeout phase evidence was not selected together.")
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
        lines.append("- No selected PKF-arm task bypassed retrieval.")
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
    diagnostics = metrics.get("diagnostic_comparisons", {})
    if report.get("source_only_diagnostic"):
        lines.extend(("", "### Source-only diagnostic deltas", ""))
        if diagnostics:
            for task_id, comparisons in sorted(diagnostics.items()):
                values = comparisons["source_vs_probe"]
                lines.append(
                    f"- `{task_id}` source_vs_probe: input "
                    f"{values['input_tokens']['delta']:+.0f}, non-cached "
                    f"{values['non_cached_input_tokens']['delta']:+.0f}, duration "
                    f"{values['duration_ms']['delta']:+.0f} ms."
                )
        else:
            lines.append("- No paired source-only diagnostic result was recorded.")
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
        print(f"Phases: {','.join(report['phases_selected'])}")
        print(f"Calls: {len(report['runs'])}/{report['environment']['scheduled_calls']}")
        print(f"{savings_label} read-only input saving: {savings['input_tokens']:.0f}")
        print(f"Performance: {report['performance']['status']}")
        print(f"Errors: {len(report['errors'])}")


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    artifacts: ArtifactStore | None = None
    try:
        target = verify_target(args.target_repo, args.target_commit)
        spec = load_benchmark_spec(args.benchmark_spec)
        baseline, baseline_manifest = resolve_baseline(args, target)
        schedule = build_schedule(
            args.repetitions,
            args.phases,
            spec,
            include_source_only=args.include_source_only,
        )
        scheduled_arms = [
            arm
            for arm in ("source_only", "probe_only", "pkf")
            if any(item["arm"] == arm for item in schedule)
        ]
        if args.dry_run:
            output = {
                "dry_run": True,
                "target": {"name": args.target_repo.resolve().name, **target},
                "baseline": {"path": str(baseline), "runtime_sha256": baseline_manifest.get("runtime_sha256")},
                "benchmark_spec": {"id": spec.benchmark_id, "path": str(spec.path), "sha256": spec.digest},
                "model": args.model,
                "reasoning_effort": args.model_reasoning_effort,
                "phases_selected": list(args.phases),
                "source_only_diagnostic": "source_only" in scheduled_arms,
                "arms": scheduled_arms,
                "jobs": args.jobs,
                "state_from": str(args.state_from.resolve()) if args.state_from is not None else None,
                "run_class": run_class(args.repetitions),
                "replicated": args.repetitions >= 3,
                "scheduled_calls": len(schedule),
                "schedule": schedule,
            }
            print(json.dumps(output, indent=2, sort_keys=True))
            return 0
        artifacts = ArtifactStore(
            root=args.artifacts_root,
            run_id=make_run_id(args, spec),
            mode=args.artifact_mode,
        )
        report = execute(args, target, artifacts, spec, baseline, baseline_manifest)
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
