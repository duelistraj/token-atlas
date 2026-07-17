#!/usr/bin/env python3
"""Measure Token Atlas runtime-v2 activation behavior with isolated Codex runs."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import statistics
import subprocess
import tempfile
from collections.abc import Sequence
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures" / "activation-gate"
BASE_FIXTURE = ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures" / "schema-change" / "repo"
PUBLIC_SKILL = ROOT / "skills" / "token-atlas"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_REASONING_EFFORT = "low"
MINIMUM_MEDIAN_SAVINGS = 500
READ_ONLY_PROMPT = (
    "Answer only this repository question: which path string does "
    "listCustomersRoute return? Do not modify repository content."
)
MUTATION_PROMPT = (
    "Change the path returned by listCustomersRoute from /customers to /clients. "
    "Keep its test and repository knowledge synchronized as required by the "
    "repository instructions."
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
class RunResult:
    variant: str
    prompt_kind: str
    returncode: int
    usage: Usage | None
    accessed_skill: bool
    accessed_closeout: bool
    emitted_closeout: bool
    changed_paths: tuple[str, ...]
    source_synchronized: bool
    knowledge_synchronized: bool
    event_tail: str
    stderr_tail: str


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument(
        "--model-reasoning-effort",
        choices=("minimal", "low", "medium", "high"),
        default=DEFAULT_REASONING_EFFORT,
    )
    parser.add_argument("--repetitions", type=int, default=3)
    parser.add_argument("--timeout-seconds", type=int, default=1_200)
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument(
        "--runtime-root",
        type=Path,
        default=ROOT,
        help="Parent for ephemeral Codex homes; must not be under the system temporary directory.",
    )
    args = parser.parse_args(argv)
    if args.repetitions < 1:
        parser.error("--repetitions must be at least 1")
    if args.timeout_seconds < 1:
        parser.error("--timeout-seconds must be at least 1")
    return args


def parse_jsonl(output: str) -> tuple[Usage | None, tuple[str, ...], str]:
    usage: Usage | None = None
    agent_messages: list[str] = []
    normalized_events: list[str] = []
    for raw_line in output.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
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
            agent_messages.append(item["text"])
    return usage, tuple(agent_messages), "\n".join(normalized_events)


def initialize_git(repo: Path) -> None:
    commands = (
        ("git", "init", "--quiet"),
        ("git", "config", "user.name", "Token Atlas Activation Eval"),
        ("git", "config", "user.email", "activation-eval@example.invalid"),
        ("git", "add", "."),
        ("git", "commit", "--quiet", "-m", "activation fixture baseline"),
    )
    for command in commands:
        subprocess.run(command, cwd=repo, check=True, capture_output=True, text=True)


def prepare_repo(workspace: Path, variant: str) -> Path:
    repo = workspace / f"activation-{variant}"
    shutil.copytree(BASE_FIXTURE, repo)
    shutil.copytree(FIXTURE / "overlay", repo, dirs_exist_ok=True)
    installed_skill = repo / ".codex" / "skills" / "token-atlas"
    if variant == "v2":
        shutil.copytree(PUBLIC_SKILL, installed_skill)
    elif variant == "v1":
        legacy = FIXTURE / "legacy"
        (installed_skill / "references").mkdir(parents=True)
        shutil.copy2(legacy / "SKILL.md", installed_skill / "SKILL.md")
        shutil.copy2(legacy / "closeout.md", installed_skill / "references" / "closeout.md")
        shutil.copy2(legacy / "AGENTS.md", repo / "AGENTS.md")
        shutil.copy2(legacy / "PKF.md", repo / ".ai" / "PKF.md")
    else:
        raise ValueError(f"unsupported variant: {variant}")
    initialize_git(repo)
    return repo


def run_codex(
    *,
    variant: str,
    prompt_kind: str,
    prompt: str,
    model: str,
    reasoning_effort: str,
    timeout_seconds: int,
    runtime_root: Path,
) -> RunResult:
    runtime_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(
        prefix=".token-atlas-activation-",
        dir=runtime_root,
    ) as raw_workspace:
        workspace = Path(raw_workspace)
        repo = prepare_repo(workspace, variant)
        source_codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
        eval_codex_home = workspace / "codex-home"
        eval_codex_home.mkdir()
        auth_file = source_codex_home / "auth.json"
        if auth_file.is_file():
            shutil.copy2(auth_file, eval_codex_home / "auth.json")
        process_environment = os.environ.copy()
        process_environment["CODEX_HOME"] = str(eval_codex_home)
        command = (
            "codex",
            "--ask-for-approval",
            "never",
            "--model",
            model,
            "--config",
            f'model_reasoning_effort="{reasoning_effort}"',
            "exec",
            "--sandbox",
            "workspace-write",
            "--ephemeral",
            "--ignore-user-config",
            "--json",
            "-C",
            str(repo),
            prompt,
        )
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
        except subprocess.TimeoutExpired as exc:
            return RunResult(
                variant=variant,
                prompt_kind=prompt_kind,
                returncode=124,
                usage=None,
                accessed_skill=False,
                accessed_closeout=False,
                emitted_closeout=False,
                changed_paths=(),
                source_synchronized=False,
                knowledge_synchronized=False,
                event_tail="",
                stderr_tail=str(exc),
            )

        usage, agent_messages, normalized_events = parse_jsonl(completed.stdout)
        event_text = normalized_events.lower()
        final_text = "\n".join(agent_messages)
        status = subprocess.run(
            ("git", "status", "--porcelain"),
            cwd=repo,
            check=True,
            capture_output=True,
            text=True,
        ).stdout
        changed_paths = tuple(
            line[3:].strip() for line in status.splitlines() if len(line) > 3
        )
        source_text = (repo / "src" / "backend" / "routes" / "customers.ts").read_text(encoding="utf-8")
        test_text = (repo / "src" / "backend" / "routes" / "customers.test.ts").read_text(encoding="utf-8")
        knowledge_text = (repo / ".ai" / "knowledge" / "backend" / "api.md").read_text(encoding="utf-8")
        return RunResult(
            variant=variant,
            prompt_kind=prompt_kind,
            returncode=completed.returncode,
            usage=usage,
            accessed_skill="token-atlas/skill.md" in event_text,
            accessed_closeout="token-atlas/references/closeout.md" in event_text,
            emitted_closeout="PKF closeout:" in final_text,
            changed_paths=changed_paths,
            source_synchronized='path: "/clients"' in source_text and '"/clients"' in test_text,
            knowledge_synchronized=(
                "Customer list path is `/clients`" in knowledge_text
                and "`/customers`" not in knowledge_text
            ),
            event_tail=normalized_events[-2_000:] if completed.returncode else "",
            stderr_tail=completed.stderr.strip()[-1_000:],
        )


def median_input_tokens(results: Sequence[RunResult]) -> float:
    values = [result.usage.input_tokens for result in results if result.usage is not None]
    if len(values) != len(results):
        raise ValueError("Codex JSONL did not report token usage for every run")
    return statistics.median(values)


def median_usage_metric(results: Sequence[RunResult], metric: str) -> float:
    values = [
        getattr(result.usage, metric)
        for result in results
        if result.usage is not None
    ]
    if len(values) != len(results):
        raise ValueError("Codex JSONL did not report token usage for every run")
    return statistics.median(values)


def evaluate(
    legacy_results: Sequence[RunResult],
    optimized_results: Sequence[RunResult],
    mutation_result: RunResult,
) -> tuple[list[str], dict[str, Any]]:
    errors: list[str] = []
    if any(result.returncode != 0 for result in (*legacy_results, *optimized_results, mutation_result)):
        errors.append("one or more Codex runs failed")
    if any(result.changed_paths for result in (*legacy_results, *optimized_results)):
        errors.append("a read-only run changed repository content")
    if any(result.accessed_skill or result.accessed_closeout for result in optimized_results):
        errors.append("runtime v2 loaded Token Atlas closeout on a read-only turn")
    if any(result.emitted_closeout for result in optimized_results):
        errors.append("runtime v2 emitted closeout status on a read-only turn")
    if not all(result.accessed_skill or result.accessed_closeout for result in legacy_results):
        errors.append("runtime v1 did not exercise Token Atlas closeout in every read-only run")
    if not all(result.emitted_closeout for result in legacy_results):
        errors.append("runtime v1 did not emit closeout status in every read-only run")

    try:
        legacy_median = median_input_tokens(legacy_results)
        optimized_median = median_input_tokens(optimized_results)
        savings = legacy_median - optimized_median
        legacy_cached = median_usage_metric(legacy_results, "cached_input_tokens")
        optimized_cached = median_usage_metric(optimized_results, "cached_input_tokens")
        legacy_non_cached = median_usage_metric(legacy_results, "non_cached_input_tokens")
        optimized_non_cached = median_usage_metric(optimized_results, "non_cached_input_tokens")
        legacy_output = median_usage_metric(legacy_results, "output_tokens")
        optimized_output = median_usage_metric(optimized_results, "output_tokens")
    except ValueError as exc:
        errors.append(str(exc))
        legacy_median = 0.0
        optimized_median = 0.0
        savings = 0.0
        legacy_cached = optimized_cached = 0.0
        legacy_non_cached = optimized_non_cached = 0.0
        legacy_output = optimized_output = 0.0
    if savings < MINIMUM_MEDIAN_SAVINGS:
        errors.append(
            f"median input-token savings {savings:.0f} is below {MINIMUM_MEDIAN_SAVINGS}"
        )

    if not (mutation_result.accessed_skill or mutation_result.accessed_closeout):
        errors.append("runtime v2 did not activate Token Atlas after a repository mutation")
    if not mutation_result.emitted_closeout:
        errors.append("runtime v2 mutation run did not emit closeout status")
    if not mutation_result.source_synchronized:
        errors.append("runtime v2 mutation run did not synchronize source and test")
    if not mutation_result.knowledge_synchronized:
        errors.append("runtime v2 mutation run did not synchronize PKF knowledge")

    metrics = {
        "legacy_median_input_tokens": legacy_median,
        "optimized_median_input_tokens": optimized_median,
        "median_input_token_savings": savings,
        "median_input_token_savings_percent": (
            (savings / legacy_median) * 100 if legacy_median else 0.0
        ),
        "legacy_median_cached_input_tokens": legacy_cached,
        "optimized_median_cached_input_tokens": optimized_cached,
        "median_cached_input_token_savings": legacy_cached - optimized_cached,
        "legacy_median_non_cached_input_tokens": legacy_non_cached,
        "optimized_median_non_cached_input_tokens": optimized_non_cached,
        "median_non_cached_input_token_savings": legacy_non_cached - optimized_non_cached,
        "legacy_median_output_tokens": legacy_output,
        "optimized_median_output_tokens": optimized_output,
        "median_output_token_savings": legacy_output - optimized_output,
        "minimum_required_savings": MINIMUM_MEDIAN_SAVINGS,
    }
    return errors, metrics


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    legacy_results = [
        run_codex(
            variant="v1",
            prompt_kind="read-only",
            prompt=READ_ONLY_PROMPT,
            model=args.model,
            reasoning_effort=args.model_reasoning_effort,
            timeout_seconds=args.timeout_seconds,
            runtime_root=args.runtime_root,
        )
        for _ in range(args.repetitions)
    ]
    optimized_results = [
        run_codex(
            variant="v2",
            prompt_kind="read-only",
            prompt=READ_ONLY_PROMPT,
            model=args.model,
            reasoning_effort=args.model_reasoning_effort,
            timeout_seconds=args.timeout_seconds,
            runtime_root=args.runtime_root,
        )
        for _ in range(args.repetitions)
    ]
    mutation_result = run_codex(
        variant="v2",
        prompt_kind="mutation",
        prompt=MUTATION_PROMPT,
        model=args.model,
        reasoning_effort=args.model_reasoning_effort,
        timeout_seconds=args.timeout_seconds,
        runtime_root=args.runtime_root,
    )
    errors, metrics = evaluate(legacy_results, optimized_results, mutation_result)
    report = {
        "status": "failed" if errors else "passed",
        "model": args.model,
        "reasoning_effort": args.model_reasoning_effort,
        "repetitions": args.repetitions,
        "metrics": metrics,
        "errors": errors,
        "legacy_read_only": [asdict(result) for result in legacy_results],
        "optimized_read_only": [asdict(result) for result in optimized_results],
        "optimized_mutation": asdict(mutation_result),
    }
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(f"Token Atlas activation eval: {report['status']}")
        print(f"Legacy median input tokens: {metrics['legacy_median_input_tokens']:.0f}")
        print(f"V2 median input tokens: {metrics['optimized_median_input_tokens']:.0f}")
        print(f"Median savings: {metrics['median_input_token_savings']:.0f}")
        for error in errors:
            print(f"ERROR: {error}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
