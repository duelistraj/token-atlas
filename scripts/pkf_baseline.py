#!/usr/bin/env python3
"""Create and validate an immutable, repository-specific PKF benchmark baseline."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_SKILL = ROOT / "skills" / "token-atlas"
DEFAULT_BASELINES_ROOT = ROOT / "benchmarks" / "baselines"
BASELINE_SCHEMA_VERSION = 1
MANAGED_START = "<!-- token-atlas:bootstrap:start -->"
MANAGED_END = "<!-- token-atlas:bootstrap:end -->"
EXCLUDED_PREFIXES = (
    ".ai",
    ".pkf-init.json",
    ".token-atlas",
    ".agents/skills/token-atlas",
    ".claude/skills/token-atlas",
    ".codex/skills/token-atlas",
)
RUN_ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")


class BaselineError(RuntimeError):
    """The baseline could not be prepared, validated, or sealed."""


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    create = subparsers.add_parser("create", help="Create or resume a one-time sealed baseline.")
    validate = subparsers.add_parser("validate", help="Validate an existing sealed baseline without model calls.")
    for command in (create, validate):
        command.add_argument("--target-repo", type=Path, required=True)
        command.add_argument("--target-commit", default="HEAD")
        command.add_argument("--baselines-root", type=Path, default=DEFAULT_BASELINES_ROOT)
        command.add_argument("--baseline", type=Path)
    create.add_argument("--model")
    create.add_argument("--model-reasoning-effort")
    create.add_argument("--timeout-seconds", type=int, default=3600)
    create.add_argument("--executor", choices=("codex",), default="codex")
    create.add_argument("--prepare-only", action="store_true")
    args = parser.parse_args(argv)
    if getattr(args, "timeout_seconds", 1) < 1:
        parser.error("--timeout-seconds must be positive")
    if args.command == "create" and not args.prepare_only:
        if not args.model or not args.model_reasoning_effort:
            parser.error("baseline generation requires --model and --model-reasoning-effort")
    return args


def run(
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


def target_identity(target_repo: Path, target_commit: str) -> dict[str, str]:
    repo = target_repo.resolve()
    if not (repo / ".git").exists():
        raise BaselineError(f"target is not a Git repository: {repo}")
    try:
        commit = run(("git", "rev-parse", f"{target_commit}^{{commit}}"), cwd=repo).stdout.strip()
        tree = run(("git", "rev-parse", f"{commit}^{{tree}}"), cwd=repo).stdout.strip()
    except subprocess.CalledProcessError as exc:
        raise BaselineError(f"target commit is unavailable: {target_commit}") from exc
    repository_id = re.sub(r"[^a-z0-9._-]+", "-", repo.name.lower()).strip("-.") or "repository"
    return {"repository_id": repository_id, "commit": commit, "tree": tree}


def baseline_path(args: argparse.Namespace, identity: dict[str, str]) -> Path:
    if args.baseline is not None:
        return args.baseline.resolve()
    return (args.baselines_root / identity["repository_id"] / identity["tree"]).resolve()


def excluded_archive_member(name: str) -> bool:
    normalized = PurePosixPath(name).as_posix().removeprefix("./")
    return any(normalized == prefix or normalized.startswith(f"{prefix}/") for prefix in EXCLUDED_PREFIXES)


def export_filtered(target_repo: Path, commit: str, destination: Path) -> list[str]:
    destination.mkdir(parents=True, exist_ok=False)
    excluded: list[str] = []
    with tempfile.TemporaryDirectory(prefix="pkf-export-") as raw_temp:
        archive_path = Path(raw_temp) / "target.tar"
        run(("git", "archive", "--format=tar", f"--output={archive_path}", commit), cwd=target_repo)
        with tarfile.open(archive_path, "r") as archive:
            for member in archive.getmembers():
                if excluded_archive_member(member.name):
                    excluded.append(member.name)
                    continue
                archive.extract(member, destination, filter="data")
    sanitize_agents(destination / "AGENTS.md")
    return sorted(excluded)


def sanitize_agents(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    text = unmanaged_agents_text(text)
    if re.search(r"(?i)(\.ai/PKF\.md|Token Atlas)", text):
        raise BaselineError(
            "target AGENTS.md contains unmanaged PKF instructions; isolate them in Token Atlas managed markers"
        )
    remaining = text.strip()
    if remaining:
        path.write_text(remaining + "\n", encoding="utf-8")
    else:
        path.unlink()


def unmanaged_agents_text(text: str) -> str:
    if MANAGED_START in text or MANAGED_END in text:
        if text.count(MANAGED_START) != 1 or text.count(MANAGED_END) != 1:
            raise BaselineError("target AGENTS.md has malformed Token Atlas managed markers")
        start = text.index(MANAGED_START)
        end = text.index(MANAGED_END, start) + len(MANAGED_END)
        text = text[:start] + text[end:]
    return text.strip() + ("\n" if text.strip() else "")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_digest(repo: Path) -> str:
    digest = hashlib.sha256()
    ignored = {".git", ".ai", ".token-atlas"}
    for path in sorted(item for item in repo.rglob("*") if item.is_file() or item.is_symlink()):
        relative = path.relative_to(repo)
        value = relative.as_posix()
        if (
            any(part in ignored for part in relative.parts)
            or value == ".pkf-init.json"
            or value.startswith(".codex/skills/token-atlas/")
        ):
            continue
        if value == "AGENTS.md" and path.is_file():
            content = unmanaged_agents_text(path.read_text(encoding="utf-8")).encode("utf-8")
            if not content:
                continue
        else:
            content = path.read_bytes() if path.is_file() else os.readlink(path).encode("utf-8")
        digest.update(value.encode("utf-8"))
        digest.update(b"\0")
        digest.update(content)
        digest.update(b"\0")
    return digest.hexdigest()


def runtime_digest(runtime: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in runtime.rglob("*") if item.is_file()):
        digest.update(path.relative_to(runtime).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def initialization_prompt() -> str:
    return (
        "Use the installed Token Atlas skill to initialize this repository completely. "
        "Derive capability names and boundaries only from repository evidence. Inspect the entire relevant "
        "source surface, use symbol-scoped ownership where independently routable capabilities share files, "
        "and generate only applicable evidence-backed leaves. Every emitted leaf must be complete. The final "
        "runtime must contain no TODO, pending materialization, placeholder, unresolved source symbol, missing "
        "route coverage, or invalid metadata. Run deterministic validation, repair every finding, and revalidate "
        "until strict validation passes. Do not modify application source, tests, configuration, or unrelated "
        "repository instructions. Finish only after .ai/PKF.md and the managed bootstrap are complete."
    )


def completeness_review_prompt() -> str:
    return (
        "Audit the newly generated Token Atlas .ai knowledge base against this repository before it is sealed. "
        "This is an independent completeness and capability-boundary review, not a benchmark task. Inventory the "
        "repository's implemented public behaviors, important mutation entrypoints, tests, and cross-capability "
        "contracts; then compare that inventory with .ai ownership, leaves, source_symbols, Edit Maps, and root "
        "routes. Repair every omission, coarse task-shaped capability, ownership conflict, unresolved symbol, "
        "placeholder, TODO, pending leaf, incomplete route, or unsupported fact. Shared source files may belong to "
        "separate capabilities only through disjoint symbol ownership. Keep names and facts derived only from source, "
        "tests, configuration, and existing repository documentation. Do not read or infer any external evaluation "
        "tasks. Do not modify application source, tests, configuration, or unrelated instructions. Finish by running "
        "strict deterministic validation and repairing findings until it passes."
    )


def install_skill(repo: Path) -> None:
    destination = repo / ".codex" / "skills" / "token-atlas"
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise BaselineError("filtered draft unexpectedly contains Token Atlas skill")
    shutil.copytree(PUBLIC_SKILL, destination)


def run_agent_pass(
    args: argparse.Namespace,
    repo: Path,
    trace_path: Path,
    *,
    role: str,
    prompt: str,
) -> dict[str, Any]:
    command = (
        "codex",
        "exec",
        "--json",
        "--ephemeral",
        "--ignore-user-config",
        "--sandbox",
        "workspace-write",
        "--model",
        args.model,
        "--config",
        f'model_reasoning_effort="{args.model_reasoning_effort}"',
        prompt,
    )
    started = dt.datetime.now(dt.timezone.utc)
    completed = run(command, cwd=repo, check=False, timeout=args.timeout_seconds)
    trace_path.parent.mkdir(parents=True, exist_ok=True)
    trace_path.parent.chmod(0o700)
    trace_path.write_text(completed.stdout, encoding="utf-8")
    trace_path.chmod(0o600)
    stderr_path = trace_path.parent / "stderr.txt"
    stderr_path.write_text(completed.stderr, encoding="utf-8")
    stderr_path.chmod(0o600)
    return {
        "executor": args.executor,
        "role": role,
        "model": args.model,
        "reasoning_effort": args.model_reasoning_effort,
        "returncode": completed.returncode,
        "duration_ms": int((dt.datetime.now(dt.timezone.utc) - started).total_seconds() * 1000),
    }


def run_generator(args: argparse.Namespace, repo: Path, trace_path: Path) -> dict[str, Any]:
    return run_agent_pass(
        args,
        repo,
        trace_path,
        role="initialization",
        prompt=initialization_prompt(),
    )


def run_completeness_review(args: argparse.Namespace, repo: Path, trace_path: Path) -> dict[str, Any]:
    return run_agent_pass(
        args,
        repo,
        trace_path,
        role="completeness_review",
        prompt=completeness_review_prompt(),
    )


def validate_runtime(repo: Path) -> dict[str, Any]:
    validator = repo / ".ai" / "tools" / "pkf_validate.py"
    if not validator.is_file():
        raise BaselineError("generated runtime is missing .ai/tools/pkf_validate.py")
    completed = run(
        (
            sys.executable,
            "-S",
            str(validator),
            "--path",
            ".",
            "--strictness",
            "ci",
            "--format",
            "json",
            "--detail",
            "summary",
        ),
        cwd=repo,
        check=False,
    )
    try:
        result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise BaselineError(f"validator returned invalid JSON: {completed.stdout[-1000:]}") from exc
    if completed.returncode != 0 or result.get("status") == "failed":
        raise BaselineError("generated runtime failed strict validation")
    violations: list[str] = []
    for path in sorted((repo / ".ai").rglob("*.md")):
        text = path.read_text(encoding="utf-8", errors="replace")
        relative = path.relative_to(repo).as_posix()
        if re.search(r"\bTODO\b", text, re.IGNORECASE):
            violations.append(f"{relative}: TODO")
        if re.search(r"(?m)^\s*materialization:\s*(pending|unknown)\s*$", text):
            violations.append(f"{relative}: incomplete materialization")
    if violations:
        raise BaselineError("generated runtime is incomplete: " + "; ".join(violations[:20]))
    return result


def runtime_inventory(repo: Path) -> dict[str, Any]:
    knowledge = repo / ".ai" / "knowledge"
    modules = sorted(
        path.name
        for path in knowledge.iterdir()
        if path.is_dir() and (path / "INDEX.md").is_file()
    )
    leaves = sorted(
        path.relative_to(repo).as_posix()
        for module in modules
        for path in (knowledge / module).glob("*.md")
        if path.name != "INDEX.md"
    )
    return {
        "module_ids": modules,
        "module_count": len(modules),
        "leaf_paths": leaves,
        "leaf_count": len(leaves),
    }


def read_manifest(path: Path) -> dict[str, Any]:
    try:
        value = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BaselineError(f"baseline manifest is unreadable: {path}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != BASELINE_SCHEMA_VERSION:
        raise BaselineError("unsupported baseline manifest schema")
    return value


def write_json_atomic(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def read_progress(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {"schema_version": 1, "passes": {}}
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise BaselineError(f"baseline draft progress is unreadable: {path}") from exc
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise BaselineError("unsupported baseline draft progress schema")
    if not isinstance(value.get("passes", {}), dict):
        raise BaselineError("baseline draft progress has invalid passes")
    return value


def completed_pass(progress: Mapping[str, Any], role: str) -> bool:
    value = progress.get("passes", {}).get(role, {})
    return isinstance(value, dict) and value.get("returncode") == 0


def run_and_record_pass(
    args: argparse.Namespace,
    repository: Path,
    draft: Path,
    progress_path: Path,
    progress: dict[str, Any],
    *,
    role: str,
) -> dict[str, Any]:
    previous = progress.get("passes", {}).get(role, {})
    attempt = int(previous.get("attempt", 0)) + 1 if isinstance(previous, dict) else 1
    trace = draft / "generation" / role / f"attempt-{attempt}" / "trace.jsonl"
    result = (
        run_generator(args, repository, trace)
        if role == "initialization"
        else run_completeness_review(args, repository, trace)
    )
    result["attempt"] = attempt
    progress.setdefault("passes", {})[role] = result
    write_json_atomic(progress_path, progress)
    return result


def validate_sealed(path: Path, identity: dict[str, str]) -> dict[str, Any]:
    manifest = read_manifest(path)
    target = manifest.get("target", {})
    if target.get("commit") != identity["commit"] or target.get("tree") != identity["tree"]:
        raise BaselineError("baseline target identity does not match the requested target")
    runtime = path / "runtime"
    if not (runtime / ".ai" / "PKF.md").is_file():
        raise BaselineError("sealed baseline runtime is incomplete")
    actual_digest = runtime_digest(runtime)
    if actual_digest != manifest.get("runtime_sha256"):
        raise BaselineError("sealed baseline digest does not match its manifest")
    if manifest.get("validation_status") != "passed":
        raise BaselineError("sealed baseline does not record successful strict validation")
    generation = manifest.get("generation", {})
    if any(
        not isinstance(generation.get(role), dict)
        or generation[role].get("returncode") != 0
        for role in ("initialization", "completeness_review")
    ):
        raise BaselineError("sealed baseline does not record both successful generation passes")
    acceptance = manifest.get("semantic_acceptance", {})
    if not isinstance(acceptance, dict) or acceptance.get("status") != "model_review_completed":
        raise BaselineError("sealed baseline does not record the completeness review")
    inventory = manifest.get("runtime_inventory", {})
    leaf_paths = inventory.get("leaf_paths", []) if isinstance(inventory, dict) else []
    if not isinstance(leaf_paths, list) or not leaf_paths:
        raise BaselineError("sealed baseline records no evidence-backed leaves")
    if any(not isinstance(value, str) or not (runtime / value).is_file() for value in leaf_paths):
        raise BaselineError("sealed baseline inventory references a missing leaf")
    incomplete = []
    for markdown in sorted((runtime / ".ai").rglob("*.md")):
        text = markdown.read_text(encoding="utf-8", errors="replace")
        relative = markdown.relative_to(runtime).as_posix()
        if re.search(r"\bTODO\b", text, re.IGNORECASE):
            incomplete.append(f"{relative}: TODO")
        if re.search(r"(?m)^\s*materialization:\s*(pending|unknown)\s*$", text):
            incomplete.append(f"{relative}: incomplete materialization")
    if incomplete:
        raise BaselineError("sealed baseline contains incomplete knowledge: " + "; ".join(incomplete[:20]))
    return manifest


def create_baseline(args: argparse.Namespace, identity: dict[str, str], final: Path) -> dict[str, Any]:
    if final.exists():
        manifest = validate_sealed(final, identity)
        return {"status": "reused", "baseline": str(final), "manifest": manifest}
    draft = final.with_name(f"{final.name}.draft")
    repository = draft / "repository"
    draft.mkdir(parents=True, exist_ok=True)
    draft.chmod(0o700)
    metadata_path = draft / "draft.json"
    if not repository.exists():
        excluded = export_filtered(args.target_repo.resolve(), identity["commit"], repository)
        install_skill(repository)
        metadata_path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "target": identity,
                    "excluded_archive_members": excluded,
                    "source_sha256": source_digest(repository),
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    draft_metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    if draft_metadata.get("target", {}).get("tree") != identity["tree"]:
        raise BaselineError("existing draft belongs to a different target tree")
    if source_digest(repository) != draft_metadata.get("source_sha256"):
        raise BaselineError("existing draft source changed; inspect the draft instead of regenerating it")
    if args.prepare_only:
        return {"status": "prepared", "draft": str(draft), "repository": str(repository)}

    before = source_digest(repository)
    progress_path = draft / "progress.json"
    progress = read_progress(progress_path)
    if completed_pass(progress, "initialization") and progress.get("initialization_validation") == "passed":
        initialization = progress["passes"]["initialization"]
        if not (repository / ".ai" / "PKF.md").is_file():
            raise BaselineError("draft says initialization completed but .ai/PKF.md is missing")
    else:
        initialization = run_and_record_pass(
            args, repository, draft, progress_path, progress, role="initialization"
        )
    if initialization["returncode"] != 0:
        raise BaselineError(
            f"initializer exited with {initialization['returncode']}; resumable draft retained at {draft}"
        )
    if not (repository / ".ai" / "PKF.md").is_file():
        initialization["returncode"] = 3
        initialization["error"] = "initializer returned success without .ai/PKF.md"
        progress["passes"]["initialization"] = initialization
        progress["initialization_validation"] = "failed"
        write_json_atomic(progress_path, progress)
        raise BaselineError(f"initializer did not produce .ai/PKF.md; resumable draft retained at {draft}")
    if source_digest(repository) != before:
        raise BaselineError(f"initializer modified repository content outside .ai/AGENTS.md; draft retained at {draft}")
    if progress.get("initialization_validation") != "passed":
        try:
            initialization_validation = validate_runtime(repository)
        except BaselineError:
            progress["initialization_validation"] = "failed"
            write_json_atomic(progress_path, progress)
            raise
        progress["initialization_validation"] = "passed"
        write_json_atomic(progress_path, progress)
        write_json_atomic(draft / "generation" / "initialization" / "validation.json", initialization_validation)

    review_validated = progress.get("review_validation") == "passed"
    if completed_pass(progress, "completeness_review") and review_validated:
        review = progress["passes"]["completeness_review"]
    else:
        review = run_and_record_pass(
            args, repository, draft, progress_path, progress, role="completeness_review"
        )
    if review["returncode"] != 0:
        raise BaselineError(
            f"completeness review exited with {review['returncode']}; resumable draft retained at {draft}"
        )
    if source_digest(repository) != before:
        raise BaselineError(f"review modified repository content outside .ai/AGENTS.md; draft retained at {draft}")
    try:
        validation = validate_runtime(repository)
    except BaselineError:
        progress["review_validation"] = "failed"
        write_json_atomic(progress_path, progress)
        raise
    progress["review_validation"] = "passed"
    write_json_atomic(progress_path, progress)
    after = source_digest(repository)
    if before != after:
        raise BaselineError(f"initializer modified repository content outside .ai/AGENTS.md; draft retained at {draft}")

    seal = final.with_name(f"{final.name}.sealing")
    if seal.exists():
        raise BaselineError(f"stale sealing directory requires manual inspection: {seal}")
    runtime = seal / "runtime"
    (runtime / ".ai").parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(repository / ".ai", runtime / ".ai")
    if (repository / "AGENTS.md").is_file():
        shutil.copy2(repository / "AGENTS.md", runtime / "AGENTS.md")
    (seal / "validation.json").write_text(json.dumps(validation, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {
        "schema_version": BASELINE_SCHEMA_VERSION,
        "created_at": dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
        "target": identity,
        "runtime_sha256": runtime_digest(runtime),
        "source_sha256": before,
        "generation": {"initialization": initialization, "completeness_review": review},
        "skill_sha256": runtime_digest(PUBLIC_SKILL),
        "validation_status": validation.get("status"),
        "runtime_inventory": runtime_inventory(repository),
        "semantic_acceptance": {
            "status": "model_review_completed",
            "scope": "repository-derived completeness and capability-boundary audit",
            "task_relevance_proven": False,
        },
    }
    (seal / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    final.parent.mkdir(parents=True, exist_ok=True)
    os.replace(seal, final)
    final.chmod(0o700)
    return {"status": "created", "baseline": str(final), "manifest": manifest, "draft": str(draft)}


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        identity = target_identity(args.target_repo, args.target_commit)
        final = baseline_path(args, identity)
        result = (
            create_baseline(args, identity, final)
            if args.command == "create"
            else {"status": "valid", "baseline": str(final), "manifest": validate_sealed(final, identity)}
        )
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0
    except (BaselineError, OSError, subprocess.SubprocessError) as exc:
        print(f"pkf_baseline: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
