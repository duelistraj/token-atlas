#!/usr/bin/env python3
"""Hybrid benchmark runner for Token Atlas fixtures.

The PowerShell wrapper remains a thin workflow selector. This script is the
executable harness for local fixture contract checks and optional Codex-backed
skill evaluation.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pkf_contract import REQUIRED_FRONT_MATTER  # noqa: E402
from pkf_lib import PkfParseError, listify, parse_yaml_block, read_front_matter, rel  # noqa: E402
from pkf_validate import validate_pkf  # noqa: E402

DEFAULT_FIXTURES = ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "fixtures"
DEFAULT_SCHEMA = ROOT / ".agents" / "skills" / "token-atlas" / "benchmarks" / "schemas" / "codex_fixture_report.schema.json"
SKILL_DIR = ROOT / ".agents" / "skills" / "token-atlas"
DEFAULT_MODEL = "gpt-5.5"
DEFAULT_MODEL_REASONING_EFFORT = "medium"
ALLOWED_SUITES = {"quick", "core", "full"}
ALLOWED_MODES = {"local", "codex", "both"}
ALLOWED_FORMATS = {"text", "json"}
ALLOWED_REASONING_EFFORTS = {"minimal", "low", "medium", "high"}
REQUIRED_MANIFEST_KEYS = {
    "name",
    "suites",
    "goal",
    "repo_root",
    "workflow",
    "source_shape",
    "expected_modules",
    "expected_required_docs",
    "forbidden_loads",
    "expected_warnings",
    "expected_errors",
    "token_thresholds",
    "exit_behavior",
}


class BenchmarkError(Exception):
    """Invalid benchmark setup or runner usage."""


class ManifestError(BenchmarkError):
    """Invalid fixture manifest."""


def main() -> int:
    args = parse_args()
    started = time.time()
    started_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()

    try:
        fixtures_dir = args.fixtures_dir.resolve()
        manifests = load_selected_manifests(fixtures_dir, args.suite)
        codex_available = shutil.which("codex") is not None
        if args.mode in {"codex", "both"} and not codex_available:
            raise BenchmarkError("codex executable is required for codex benchmark mode")

        fixture_reports = []
        for fixture_dir, manifest in manifests:
            fixture_reports.append(run_fixture(fixture_dir, manifest, args))

        aggregate = aggregate_reports(fixture_reports)
        report = {
            "suite": args.suite,
            "mode": args.mode,
            "model": resolved_model_config(args),
            "started_at": started_at,
            "duration_ms": int((time.time() - started) * 1000),
            "fixtures": fixture_reports,
            "aggregate": aggregate,
        }

        output_report(report, args)
        return 1 if aggregate["failed"] else 0
    except BenchmarkError as exc:
        print(f"pkf_bench: {exc}", file=sys.stderr)
        return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Token Atlas benchmark fixtures.")
    parser.add_argument("--suite", choices=sorted(ALLOWED_SUITES), default="quick")
    parser.add_argument("--mode", choices=sorted(ALLOWED_MODES), default="local")
    parser.add_argument("--format", choices=sorted(ALLOWED_FORMATS), default="text")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--timeout-seconds", type=int, default=1200)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--model-reasoning-effort", choices=sorted(ALLOWED_REASONING_EFFORTS), default=DEFAULT_MODEL_REASONING_EFFORT)
    parser.add_argument("--keep-workspaces", action="store_true")
    parser.add_argument("--fixtures-dir", type=Path, default=DEFAULT_FIXTURES)
    args = parser.parse_args()
    if args.timeout_seconds < 1:
        raise BenchmarkError("--timeout-seconds must be at least 1")
    args.model_source = "cli" if "--model" in sys.argv else "runner-default"
    args.model_reasoning_effort_source = "cli" if "--model-reasoning-effort" in sys.argv else "runner-default"
    return args


def resolved_model_config(args: argparse.Namespace) -> dict[str, str]:
    return {
        "name": getattr(args, "model", DEFAULT_MODEL),
        "source": getattr(args, "model_source", "runner-default"),
        "reasoning_effort": getattr(args, "model_reasoning_effort", DEFAULT_MODEL_REASONING_EFFORT),
        "reasoning_effort_source": getattr(args, "model_reasoning_effort_source", "runner-default"),
    }


def load_selected_manifests(fixtures_dir: Path, suite: str) -> list[tuple[Path, dict[str, Any]]]:
    if not fixtures_dir.is_dir():
        raise BenchmarkError(f"fixtures directory does not exist: {fixtures_dir}")

    selected: list[tuple[Path, dict[str, Any]]] = []
    for manifest_path in sorted(fixtures_dir.glob("*/fixture.yaml")):
        manifest = parse_manifest(manifest_path)
        suites = require_list(manifest, "suites", manifest_path)
        if suite in suites:
            selected.append((manifest_path.parent, manifest))

    if not selected:
        raise BenchmarkError(f"no fixtures found for suite '{suite}' in {fixtures_dir}")
    return selected


def parse_manifest(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    lines = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        lines.append(line)
    try:
        value, index = parse_yaml_block(lines, 0, 0, path)
    except PkfParseError as exc:
        raise ManifestError(str(exc)) from exc
    if index != len(lines):
        raise ManifestError(f"{path}: unsupported YAML near line {index + 1}")
    if not isinstance(value, dict):
        raise ManifestError(f"{path}: manifest root must be a mapping")
    missing = sorted(REQUIRED_MANIFEST_KEYS - set(value))
    if missing:
        raise ManifestError(f"{path}: missing required keys: {', '.join(missing)}")
    return value


def run_fixture(fixture_dir: Path, manifest: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    name = str(manifest["name"])
    started = time.time()
    report: dict[str, Any] = {
        "name": name,
        "overall_status": "passed",
        "checks": {"passed": 0, "total": 0},
        "model": resolved_model_config(args),
        "warnings": [],
        "errors": [],
        "token_impact": {},
        "evidence": [],
    }

    try:
        local_result = run_local_mode(fixture_dir, manifest, args) if args.mode in {"local", "both"} else None
        codex_result = run_codex_mode(fixture_dir, manifest, args) if args.mode in {"codex", "both"} else None
        if local_result is not None:
            report["local"] = local_result
        if codex_result is not None:
            report["codex"] = codex_result

        mode_results = [item for item in (local_result, codex_result) if item is not None]
        report["checks"] = combine_checks(mode_results)
        report["warnings"] = flatten_values(mode_results, "warnings")
        report["errors"] = flatten_values(mode_results, "errors")
        report["token_impact"] = merge_token_impact(mode_results)
        report["evidence"] = flatten_values(mode_results, "evidence")
        report["overall_status"] = combine_statuses([item["status"] for item in mode_results])
    except BenchmarkError as exc:
        report["overall_status"] = "failed"
        report["checks"] = {"passed": 0, "total": 1}
        report["errors"] = [str(exc)]

    report["duration_ms"] = int((time.time() - started) * 1000)
    return report


def run_local_mode(fixture_dir: Path, manifest: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    result = empty_mode_result("local")
    result["model"] = resolved_model_config(args)
    workspace_root, cleanup = make_workspace(args.keep_workspaces)
    try:
        readme = fixture_dir / "README.md"
        repo_src = fixture_dir / str(manifest["repo_root"])
        add_check(result, readme.is_file(), "fixture README exists", f"missing {readme}")
        add_check(result, repo_src.is_dir(), "fixture repo exists", f"missing {repo_src}")
        if not repo_src.is_dir():
            raise BenchmarkError(f"{manifest['name']}: fixture repo is missing")

        repo = workspace_root / str(manifest["name"])
        shutil.copytree(repo_src, repo)
        result["workspace"] = str(repo)
        result["selected_modules"] = [str(item) for item in require_list(manifest, "expected_modules", Path(manifest["name"]))]
        result["evidence"].append(f"copied repo to {repo}")
        verify_expected_modules(manifest, result)

        initialize_git(repo, result)
        patch_name = manifest.get("patch")
        if patch_name:
            apply_patch_file(repo, fixture_dir / str(patch_name), result)
        verify_git_state(repo, manifest, result, bool(patch_name))
        verify_runtime_state(repo, manifest, result)
        apply_expected_ai_overlay(fixture_dir, repo, manifest, result)
        verify_expected_docs(repo, manifest, result)
        verify_front_matter(repo, manifest, result)
        verify_pkf_references(repo, result)
        verify_expected_defects(repo, manifest, result)
        verify_exports_static(repo, manifest, result)
        verify_validator_result(repo, manifest, result)
    finally:
        if cleanup is not None:
            cleanup.cleanup()

    finish_mode_status(result)
    return result


def make_workspace(keep: bool) -> tuple[Path, tempfile.TemporaryDirectory[str] | None]:
    if keep:
        return Path(tempfile.mkdtemp(prefix="token-atlas-bench-")), None
    temp = tempfile.TemporaryDirectory(prefix="token-atlas-bench-")
    return Path(temp.name), temp


def initialize_git(repo: Path, result: dict[str, Any]) -> None:
    run_command(["git", "init"], repo)
    run_command(["git", "config", "user.email", "bench@example.test"], repo)
    run_command(["git", "config", "user.name", "Token Atlas Bench"], repo)
    run_command(["git", "add", "."], repo)
    run_command(["git", "commit", "-m", "fixture baseline"], repo)
    add_check(result, True, "git baseline initialized")


def apply_patch_file(repo: Path, patch_path: Path, result: dict[str, Any]) -> None:
    add_check(result, patch_path.is_file(), f"patch exists: {patch_path.name}", f"missing patch {patch_path}")
    if not patch_path.is_file():
        raise BenchmarkError(f"missing patch file: {patch_path}")
    run_command(["git", "apply", "--check", str(patch_path)], repo)
    run_command(["git", "apply", str(patch_path)], repo)
    add_check(result, True, f"patch applied: {patch_path.name}")


def verify_git_state(repo: Path, manifest: dict[str, Any], result: dict[str, Any], has_patch: bool) -> None:
    expected_changed = set(require_list(manifest, "changed_paths", Path(manifest["name"])))
    expected_deleted = set(require_list(manifest, "deleted_paths", Path(manifest["name"])))
    if not has_patch:
        for path in expected_changed:
            add_check(result, (repo / path).exists(), f"changed path exists: {path}", f"changed path does not exist: {path}")
        for path in expected_deleted:
            add_check(result, not (repo / path).exists(), f"deleted path absent: {path}", f"deleted path unexpectedly exists: {path}")
        return

    diff = run_command(["git", "diff", "--name-status"], repo).stdout.splitlines()
    actual_changed: set[str] = set()
    actual_deleted: set[str] = set()
    for line in diff:
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        status, path = parts[0], parts[-1].replace("\\", "/")
        if status.startswith("D"):
            actual_deleted.add(path)
        elif status.startswith(("A", "M", "R")):
            actual_changed.add(path)
    add_check(
        result,
        expected_changed <= actual_changed,
        "changed paths match manifest",
        f"missing changed paths: {sorted(expected_changed - actual_changed)}",
    )
    add_check(
        result,
        expected_deleted <= actual_deleted,
        "deleted paths match manifest",
        f"missing deleted paths: {sorted(expected_deleted - actual_deleted)}",
    )
    result["evidence"].append(f"git diff --name-status: {diff or 'clean'}")


def verify_runtime_state(repo: Path, manifest: dict[str, Any], result: dict[str, Any]) -> None:
    expected = manifest.get("source_shape", {}).get("pkf_runtime")
    pkf = repo / ".ai" / "PKF.md"
    if expected == "present":
        add_check(result, pkf.is_file(), "PKF runtime is present", "missing .ai/PKF.md")
    elif expected == "missing":
        add_check(result, not pkf.exists(), "PKF runtime is missing before recovery", ".ai/PKF.md should be absent")


def apply_expected_ai_overlay(fixture_dir: Path, repo: Path, manifest: dict[str, Any], result: dict[str, Any]) -> None:
    if manifest.get("source_shape", {}).get("pkf_runtime") != "missing":
        return
    overlay = fixture_dir / "expected_ai" / ".ai"
    add_check(result, overlay.is_dir(), "expected .ai overlay exists", f"missing expected .ai overlay: {overlay}")
    if not overlay.is_dir():
        raise BenchmarkError(f"{manifest['name']}: expected .ai overlay is missing")
    shutil.copytree(overlay, repo / ".ai")
    result["evidence"].append(f"copied expected .ai overlay from {overlay}")


def verify_expected_modules(manifest: dict[str, Any], result: dict[str, Any]) -> None:
    source_modules = manifest.get("source_shape", {}).get("modules", [])
    if not isinstance(source_modules, list):
        add_check(result, False, "source modules list exists", "source_shape.modules must be a list")
        return
    for module in require_list(manifest, "expected_modules", Path(manifest["name"])):
        add_check(result, module in source_modules, f"expected module declared: {module}", f"expected module missing from source_shape.modules: {module}")


def verify_expected_docs(repo: Path, manifest: dict[str, Any], result: dict[str, Any]) -> None:
    docs = flatten_expected_docs(manifest.get("expected_required_docs", []))
    pkf_present = (repo / ".ai" / "PKF.md").is_file()
    if not pkf_present:
        result["evidence"].append("required docs are expected to be generated by workflow")
        return
    for doc in docs:
        add_check(result, (repo / doc).is_file(), f"required doc exists: {doc}", f"missing required doc: {doc}")
        if doc.endswith(".md"):
            result["required_docs"].append(doc)


def verify_front_matter(repo: Path, manifest: dict[str, Any], result: dict[str, Any]) -> None:
    if not (repo / ".ai" / "PKF.md").is_file():
        return
    ai_dir = repo / ".ai"
    for md in sorted(ai_dir.rglob("*.md")):
        meta = read_front_matter(md)
        missing = REQUIRED_FRONT_MATTER - set(meta)
        add_check(result, not missing, f"front matter fields: {rel(md, repo)}", f"{rel(md, repo)} missing {sorted(missing)}")
        pkf = meta.get("pkf", {})
        add_check(result, isinstance(pkf.get("loads", []), list), f"pkf.loads list: {rel(md, repo)}")
        add_check(result, isinstance(pkf.get("related", []), list), f"pkf.related list: {rel(md, repo)}")


def verify_pkf_references(repo: Path, result: dict[str, Any]) -> None:
    ai_dir = repo / ".ai"
    if not ai_dir.is_dir():
        return
    for md in sorted(ai_dir.rglob("*.md")):
        meta = read_front_matter(md)
        pkf = meta.get("pkf", {})
        for key in ("loads", "related"):
            for target in pkf.get(key, []):
                target_path = repo / str(target)
                add_check(result, target_path.is_file(), f"{key} resolves: {target}", f"{rel(md, repo)} has broken {key}: {target}")


def verify_expected_defects(repo: Path, manifest: dict[str, Any], result: dict[str, Any]) -> None:
    expected_errors = flatten_strings(manifest.get("expected_errors", []))
    deleted_paths = require_list(manifest, "deleted_paths", Path(manifest["name"]))
    if deleted_paths:
        text = read_all_ai_text(repo)
        for path in deleted_paths:
            add_check(
                result,
                path in text,
                f"expected stale evidence is present: {path}",
                f"expected stale evidence not found: {path}",
            )
        if expected_errors:
            result["errors"].extend(expected_errors)

    broad_error = any("Unrelated module loaded automatically" in item for item in expected_errors)
    if broad_error:
        broad_load_found = find_broad_load(repo, manifest)
        add_check(result, broad_load_found, "expected broad pkf.loads defect is present", "expected broad pkf.loads defect not found")
        result["errors"].extend(expected_errors)


def verify_validator_result(repo: Path, manifest: dict[str, Any], result: dict[str, Any]) -> None:
    ai_dir = repo / ".ai"
    if not ai_dir.is_dir():
        result["evidence"].append("pkf_validate skipped because .ai is absent")
        return
    report = validate_pkf(ai_dir, strictness="ci")
    result["token_impact"]["validator"] = [entry.__dict__ for entry in report.token_impact]
    expected_errors = flatten_strings(manifest.get("expected_errors", []))
    unexpected = []
    for finding in report.errors:
        issue = f"{finding.file}: {finding.issue}"
        if matches_any_expected(issue, expected_errors):
            add_check(result, True, f"validator reported expected error: {finding.issue}")
        else:
            unexpected.append(issue)
    add_check(result, not unexpected, "pkf_validate structural checks passed", f"pkf_validate unexpected errors: {unexpected}")
    result["warnings"].extend(f"pkf_validate: {finding.file}: {finding.issue}" for finding in report.warnings)


def verify_exports_static(repo: Path, manifest: dict[str, Any], result: dict[str, Any]) -> None:
    expected_exports = manifest.get("expected_export_files")
    if not isinstance(expected_exports, dict):
        return
    retrieval = repo / ".ai" / "retrieval"
    off_files = expected_exports.get("off", [])
    add_check(result, not retrieval.exists() or not off_files, "retrieval exports are not source truth")
    result["token_impact"]["exports_do_not_change_startup_cost_when_off"] = bool(
        manifest.get("token_thresholds", {}).get("exports_do_not_change_startup_cost_when_off")
    )


def run_codex_mode(fixture_dir: Path, manifest: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    result = empty_mode_result("codex")
    model_config = resolved_model_config(args)
    result["model"] = model_config
    workspace_root, cleanup = make_workspace(args.keep_workspaces)
    started = time.time()
    try:
        repo_src = fixture_dir / str(manifest["repo_root"])
        repo = workspace_root / str(manifest["name"])
        skill_copy = workspace_root / "token-atlas-skill"
        shutil.copytree(repo_src, repo)
        shutil.copytree(SKILL_DIR, skill_copy, ignore=shutil.ignore_patterns("benchmarks"))
        metadata_dir = repo / ".benchmark"
        metadata_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(fixture_dir / "fixture.yaml", metadata_dir / "fixture.yaml")
        if (fixture_dir / "README.md").is_file():
            shutil.copy2(fixture_dir / "README.md", metadata_dir / "README.md")
        result["workspace"] = str(repo)
        result["evidence"].append(f"copied repo to {repo}")
        initialize_git(repo, result)
        if manifest.get("patch"):
            apply_patch_file(repo, fixture_dir / str(manifest["patch"]), result)

        output_path = workspace_root / f"{manifest['name']}-codex-report.json"
        prompt = build_codex_prompt(manifest, skill_copy, metadata_dir)
        command = [
            "codex",
            "--ask-for-approval",
            "never",
            "--model",
            model_config["name"],
            "--config",
            f'model_reasoning_effort="{model_config["reasoning_effort"]}"',
            "exec",
            "--sandbox",
            "workspace-write",
            "--ephemeral",
            "--output-schema",
            str(DEFAULT_SCHEMA),
            "-o",
            str(output_path),
            "-C",
            str(repo),
            "--add-dir",
            str(skill_copy),
            prompt,
        ]
        try:
            completed = subprocess.run(
                command,
                cwd=str(repo),
                text=True,
                capture_output=True,
                timeout=args.timeout_seconds,
                check=False,
            )
        except subprocess.TimeoutExpired:
            result["status"] = "timeout"
            result["errors"].append(f"codex exec timed out after {args.timeout_seconds} seconds")
            result["duration_ms"] = int((time.time() - started) * 1000)
            return result

        result["exit_behavior"] = {"actual": completed.returncode}
        result["evidence"].append(f"codex exit code: {completed.returncode}")
        if completed.stderr.strip():
            result["evidence"].append(f"codex stderr: {completed.stderr.strip()[-1000:]}")
        if not output_path.is_file():
            add_check(result, False, "codex report file exists", "codex did not write final report")
            finish_mode_status(result)
            return result

        codex_report = parse_codex_report(output_path)
        result["evidence"].append(f"codex report: {output_path}")
        score_codex_report(manifest, codex_report, result)
    finally:
        if cleanup is not None:
            cleanup.cleanup()

    result["duration_ms"] = int((time.time() - started) * 1000)
    finish_mode_status(result)
    return result


def build_codex_prompt(manifest: dict[str, Any], skill_copy: Path, metadata_dir: Path) -> str:
    return (
        "Run the Token Atlas benchmark fixture in this isolated repository.\n"
        f"Fixture name: {manifest['name']}\n"
        f"Use the copied skill docs at: {skill_copy}\n"
        f"Use the fixture manifest at: {metadata_dir / 'fixture.yaml'}\n"
        f"Use the fixture README contract at: {metadata_dir / 'README.md'}\n"
        "Do not analyze or modify the token-atlas skill-maintenance repository.\n"
        "Execute only the workflow named in fixture.yaml for this fixture.\n"
        "Apply the Token Atlas skill instructions from the copied skill docs.\n"
        "Return a JSON object matching the provided output schema. Include selected modules, "
        "required docs, forbidden automatic loads status, warnings, errors, token impact, exit "
        "behavior, and compact evidence. Expected benchmark defects should be reported as errors "
        "in the report rather than hidden.\n"
    )


def parse_codex_report(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8").strip()
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, flags=re.S)
        if not match:
            raise BenchmarkError(f"malformed Codex report: {path}")
        value = json.loads(match.group(0))
    if not isinstance(value, dict):
        raise BenchmarkError(f"Codex report must be a JSON object: {path}")
    return value


def score_codex_report(manifest: dict[str, Any], report: dict[str, Any], result: dict[str, Any]) -> None:
    reported_status = str(report.get("status", ""))
    add_check(
        result,
        reported_status in {"passed", "warning", "failed"},
        "Codex report status is valid",
        f"invalid Codex report status: {reported_status or '<missing>'}",
    )
    expected_modules = require_list(manifest, "expected_modules", Path(manifest["name"]))
    selected = listify(report.get("selected_modules", []))
    result["selected_modules"] = selected
    for module in expected_modules:
        add_check(result, module in selected, f"Codex selected module: {module}", f"missing selected module: {module}")

    required_docs = listify(report.get("required_docs", []))
    result["required_docs"] = required_docs
    for doc in flatten_expected_docs(manifest.get("expected_required_docs", [])):
        add_check(result, doc in required_docs, f"Codex required doc: {doc}", f"missing required doc in Codex report: {doc}")

    expected_errors = expected_errors_for_scoring(manifest)
    allowed_errors = allowed_errors_for_scoring(manifest)
    actual_errors = listify(report.get("errors", []))
    result["errors"].extend(actual_errors)
    if expected_errors:
        joined = "\n".join(actual_errors)
        for expected in expected_errors:
            add_check(result, fuzzy_contains(joined, expected), f"Codex reported expected error: {expected}", f"missing expected error: {expected}")
    else:
        unexpected = [error for error in actual_errors if not matches_any_expected(str(error), allowed_errors)]
        add_check(result, not unexpected, "Codex reported no unexpected errors", f"unexpected Codex errors: {unexpected}")
        add_check(
            result,
            reported_status != "failed" or (actual_errors and not unexpected),
            "Codex report status is compatible with expected errors",
            "Codex report status failed unexpectedly",
        )

    expected_warnings = flatten_strings(manifest.get("expected_warnings", []))
    actual_warnings = listify(report.get("warnings", []))
    result["warnings"].extend(actual_warnings)
    if expected_warnings:
        result["warnings"].extend(expected_warnings)

    result["forbidden_loads"] = report.get("forbidden_loads", [])
    result["token_impact"] = report.get("token_impact", {})
    result["exit_behavior"] = report.get("exit_behavior", result.get("exit_behavior", {}))
    evidence = listify(report.get("evidence", []))
    result["evidence"].extend(evidence)


def fuzzy_contains(haystack: str, needle: str) -> bool:
    haystack_lower = haystack.lower()
    needle_lower = needle.lower()
    if needle_lower in haystack_lower:
        return True
    words = [word for word in re.split(r"[^A-Za-z0-9_./-]+", needle_lower) if len(word) > 3]
    return all(word in haystack_lower for word in words[:4])


def expected_errors_for_scoring(manifest: dict[str, Any]) -> list[str]:
    value = manifest.get("expected_errors", [])
    if isinstance(value, dict):
        if "after_recovery" in value:
            return flatten_strings(value["after_recovery"])
        if "default" in value:
            return flatten_strings(value["default"])
    return flatten_strings(value)


def allowed_errors_for_scoring(manifest: dict[str, Any]) -> list[str]:
    return flatten_strings(manifest.get("expected_errors", []))


def matches_any_expected(error: str, expected_errors: list[str]) -> bool:
    return any(fuzzy_contains(error, expected) for expected in expected_errors)


def empty_mode_result(mode: str) -> dict[str, Any]:
    return {
        "mode": mode,
        "status": "passed",
        "checks": {"passed": 0, "total": 0},
        "model": {},
        "selected_modules": [],
        "required_docs": [],
        "forbidden_loads": [],
        "warnings": [],
        "errors": [],
        "token_impact": {},
        "exit_behavior": {},
        "evidence": [],
    }


def add_check(result: dict[str, Any], ok: bool, passed: str, failed: str | None = None) -> None:
    result["checks"]["total"] += 1
    if ok:
        result["checks"]["passed"] += 1
        result["evidence"].append(passed)
    else:
        result["errors"].append(failed or passed)


def finish_mode_status(result: dict[str, Any]) -> None:
    if result.get("status") == "timeout":
        return
    checks = result["checks"]
    if checks["passed"] < checks["total"]:
        result["status"] = "failed"
    elif result["warnings"]:
        result["status"] = "warning"
    else:
        result["status"] = "passed"


def combine_statuses(statuses: list[str]) -> str:
    if any(status in {"failed", "timeout"} for status in statuses):
        return "failed"
    if any(status == "warning" for status in statuses):
        return "warning"
    return "passed"


def combine_checks(results: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "passed": sum(item["checks"]["passed"] for item in results),
        "total": sum(item["checks"]["total"] for item in results),
    }


def flatten_values(results: list[dict[str, Any]], key: str) -> list[Any]:
    values: list[Any] = []
    for item in results:
        values.extend(listify(item.get(key, [])))
    return values


def merge_token_impact(results: list[dict[str, Any]]) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in results:
        impact = item.get("token_impact")
        if isinstance(impact, dict):
            merged[item["mode"]] = impact
    return merged


def aggregate_reports(fixtures: list[dict[str, Any]]) -> dict[str, Any]:
    passed = sum(1 for item in fixtures if item["overall_status"] == "passed")
    warning = sum(1 for item in fixtures if item["overall_status"] == "warning")
    failed = sum(1 for item in fixtures if item["overall_status"] == "failed")
    return {
        "total": len(fixtures),
        "passed": passed,
        "warning": warning,
        "failed": failed,
        "skipped": 0,
        "failing_fixtures": [item["name"] for item in fixtures if item["overall_status"] == "failed"],
        "checks": {
            "passed": sum(item["checks"]["passed"] for item in fixtures),
            "total": sum(item["checks"]["total"] for item in fixtures),
        },
    }


def output_report(report: dict[str, Any], args: argparse.Namespace) -> None:
    if args.format == "json":
        content = json.dumps(report, indent=2, sort_keys=True)
    else:
        content = render_text_report(report)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        try:
            args.report.write_text(content + "\n", encoding="utf-8")
        except OSError as exc:
            raise BenchmarkError(f"could not write report to {args.report}: {exc}") from exc
    print(content)


def render_text_report(report: dict[str, Any]) -> str:
    lines = [
        "Token Atlas Benchmark",
        f"Suite: {report['suite']}",
        f"Mode: {report['mode']}",
        f"Model: {report['model']['name']} ({report['model']['source']})",
        f"Reasoning Effort: {report['model']['reasoning_effort']} ({report['model']['reasoning_effort_source']})",
        f"Duration: {report['duration_ms']} ms",
        "",
    ]
    for fixture in report["fixtures"]:
        checks = fixture["checks"]
        lines.extend(
            [
                f"Fixture: {fixture['name']}",
                f"Status: {fixture['overall_status']}",
                f"Score: {checks['passed']}/{checks['total']}",
            ]
        )
        for mode in ("local", "codex"):
            if mode in fixture:
                mode_checks = fixture[mode]["checks"]
                lines.append(f"  {mode}: {fixture[mode]['status']} ({mode_checks['passed']}/{mode_checks['total']})")
        if fixture["errors"]:
            label = "Expected Errors" if fixture["overall_status"] == "passed" else "Errors"
            lines.append(f"  {label}:")
            lines.extend(f"    - {item}" for item in fixture["errors"])
        if fixture["warnings"]:
            lines.append("  Warnings:")
            lines.extend(f"    - {item}" for item in fixture["warnings"])
        lines.append("")
    aggregate = report["aggregate"]
    lines.extend(
        [
            "Aggregate:",
            f"  total: {aggregate['total']}",
            f"  passed: {aggregate['passed']}",
            f"  warning: {aggregate['warning']}",
            f"  failed: {aggregate['failed']}",
            f"  score: {aggregate['checks']['passed']}/{aggregate['checks']['total']}",
        ]
    )
    if aggregate["failing_fixtures"]:
        lines.append(f"  failing_fixtures: {', '.join(aggregate['failing_fixtures'])}")
    return "\n".join(lines)


def flatten_expected_docs(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        docs: list[str] = []
        for nested in value.values():
            docs.extend(flatten_expected_docs(nested))
        return docs
    return []


def flatten_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, dict):
        items: list[str] = []
        for nested in value.values():
            items.extend(flatten_strings(nested))
        return items
    if value in (None, ""):
        return []
    return [str(value)]


def require_list(mapping: dict[str, Any], key: str, source: Path) -> list[Any]:
    value = mapping.get(key)
    if not isinstance(value, list):
        raise ManifestError(f"{source}: '{key}' must be a list")
    return value


def run_command(command: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(command, cwd=str(cwd), text=True, capture_output=True, check=False)
    if completed.returncode != 0:
        joined = " ".join(command)
        raise BenchmarkError(f"command failed in {cwd}: {joined}\n{completed.stderr.strip()}")
    return completed


def read_all_ai_text(repo: Path) -> str:
    ai_dir = repo / ".ai"
    if not ai_dir.is_dir():
        return ""
    return "\n".join(path.read_text(encoding="utf-8") for path in ai_dir.rglob("*.md"))


def find_broad_load(repo: Path, manifest: dict[str, Any]) -> bool:
    forbidden = [str(item) for item in require_list(manifest, "forbidden_loads", Path(manifest["name"]))]
    ai_dir = repo / ".ai"
    if not ai_dir.is_dir():
        return False
    for md in ai_dir.rglob("*.md"):
        meta = read_front_matter(md)
        loads = [str(item) for item in meta.get("pkf", {}).get("loads", [])]
        for load in loads:
            if any(item.endswith("/") and item in load for item in forbidden):
                return True
            if load in forbidden:
                return True
    return False



if __name__ == '__main__':
    raise SystemExit(main())
