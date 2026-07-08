#!/usr/bin/env python3
"""Deterministic mechanical validator for Token Atlas PKF trees."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pkf_contract import (  # noqa: E402
    EXIT_CODES,
    REQUIRED_FRONT_MATTER,
    REQUIRED_MODULE_DOCS,
    REQUIRED_RUNTIME_DOCS,
    SHARED_DOCS,
    TOKEN_THRESHOLDS,
    VALIDATION_STRICTNESS,
)
from pkf_lib import PkfParseError, listify, read_front_matter, rel  # noqa: E402
from pkf_tokens import count_tokens  # noqa: E402


ALLOWED_FORMATS = ("text", "json")


@dataclass
class ValidationFinding:
    file: str
    issue: str


@dataclass
class TokenEntry:
    route: str
    tokens: int
    estimator: str
    threshold: int
    status: str


@dataclass
class ValidationReport:
    path: str
    strictness: str
    passed: list[str] = field(default_factory=list)
    warnings: list[ValidationFinding] = field(default_factory=list)
    errors: list[ValidationFinding] = field(default_factory=list)
    token_impact: list[TokenEntry] = field(default_factory=list)

    @property
    def status(self) -> str:
        if self.errors:
            return "failed"
        if self.warnings:
            return "warning"
        return "passed"

    @property
    def exit_code(self) -> int:
        if self.strictness == "ci" and self.errors:
            return EXIT_CODES["ci_blocking"]
        return EXIT_CODES["ok"]


def main() -> int:
    try:
        args = parse_args()
        report = validate_pkf(args.path, args.strictness, args.model)
        if args.format == "json":
            print(json.dumps(report_to_dict(report), indent=2, sort_keys=True))
        else:
            print(render_text(report))
        return report.exit_code
    except UsageError as exc:
        print(f"pkf_validate: {exc}", file=sys.stderr)
        return EXIT_CODES["usage"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate the deterministic mechanical subset of a Token Atlas PKF tree.",
        epilog=(
            "Non-goals: source-truth synchronization, invented-fact detection, and "
            "duplicate-authoritative-fact detection remain LLM-guided validation.md responsibilities."
        ),
    )
    parser.add_argument("--path", type=Path, default=Path(".ai"), help="Path to a .ai directory or repository containing .ai.")
    parser.add_argument("--strictness", choices=VALIDATION_STRICTNESS, default="advisory")
    parser.add_argument("--format", choices=ALLOWED_FORMATS, default="text")
    parser.add_argument("--model", default="gpt-5.5", help="Model name for optional exact token counting.")
    return parser.parse_args()


class UsageError(Exception):
    """Invalid validator invocation."""


def validate_pkf(path: Path, strictness: str = "advisory", model: str = "gpt-5.5") -> ValidationReport:
    if strictness not in VALIDATION_STRICTNESS:
        raise UsageError(f"invalid strictness: {strictness}")

    ai_dir = resolve_ai_dir(path)
    repo_root = ai_dir.parent
    report = ValidationReport(path=str(ai_dir), strictness=strictness)

    if not ai_dir.exists():
        error(report, ".ai", "missing PKF runtime directory")
        add_token_impact(report, ai_dir, model)
        return report
    if not ai_dir.is_dir():
        error(report, rel(ai_dir, repo_root), "PKF path is not a directory")
        return report

    check_required_docs(ai_dir, repo_root, report)
    modules = discover_modules(ai_dir)
    check_module_docs(ai_dir, repo_root, modules, report)
    front_matter = check_front_matter(ai_dir, repo_root, report)
    check_references(repo_root, front_matter, report)
    check_reachability(ai_dir, repo_root, modules, front_matter, report)
    check_unrelated_loads(repo_root, front_matter, report)
    add_token_impact(report, ai_dir, model)
    return report


def resolve_ai_dir(path: Path) -> Path:
    candidate = path.resolve()
    if candidate.name == ".ai":
        return candidate
    nested = candidate / ".ai"
    if nested.exists() or not candidate.exists():
        return nested
    return candidate


def check_required_docs(ai_dir: Path, repo_root: Path, report: ValidationReport) -> None:
    for doc in REQUIRED_RUNTIME_DOCS:
        check_file(ai_dir / doc, repo_root, report, f"required runtime doc exists: .ai/{doc}")
    for doc in SHARED_DOCS:
        check_file(ai_dir / "knowledge" / doc, repo_root, report, f"shared doc exists: .ai/knowledge/{doc}")


def discover_modules(ai_dir: Path) -> list[str]:
    knowledge = ai_dir / "knowledge"
    if not knowledge.is_dir():
        return []
    return sorted(item.name for item in knowledge.iterdir() if item.is_dir() and item.name != "retrieval")


def check_module_docs(ai_dir: Path, repo_root: Path, modules: list[str], report: ValidationReport) -> None:
    knowledge = ai_dir / "knowledge"
    if not knowledge.is_dir():
        error(report, ".ai/knowledge", "missing knowledge directory")
        return
    passed(report, "knowledge directory exists")
    for module in modules:
        for doc in REQUIRED_MODULE_DOCS:
            check_file(knowledge / module / doc, repo_root, report, f"module doc exists: .ai/knowledge/{module}/{doc}")


def check_front_matter(ai_dir: Path, repo_root: Path, report: ValidationReport) -> dict[Path, dict[str, Any]]:
    metadata: dict[Path, dict[str, Any]] = {}
    for md in sorted(ai_dir.rglob("*.md")):
        display = rel(md, repo_root)
        try:
            meta = read_front_matter(md)
        except PkfParseError as exc:
            error(report, display, str(exc))
            continue
        metadata[md] = meta
        missing = sorted(REQUIRED_FRONT_MATTER - set(meta))
        if missing:
            error(report, display, f"missing front matter fields: {', '.join(missing)}")
            continue
        pkf = meta.get("pkf")
        if not isinstance(pkf, dict):
            error(report, display, "pkf front matter must be a mapping")
            continue
        for key in ("loads", "related"):
            if not isinstance(pkf.get(key), list):
                error(report, display, f"pkf.{key} must be a list")
            else:
                passed(report, f"pkf.{key} list: {display}")
    return metadata


def check_references(repo_root: Path, metadata: dict[Path, dict[str, Any]], report: ValidationReport) -> None:
    for md, meta in metadata.items():
        display = rel(md, repo_root)
        resource = str(meta.get("resource", ""))
        if resource.upper() == "TODO" or resource.startswith("TODO"):
            passed(report, f"resource marked TODO: {display}")
        elif not resource:
            error(report, display, "resource is empty")
        elif not (repo_root / resource).exists():
            error(report, display, f"resource path does not resolve: {resource}")
        else:
            passed(report, f"resource resolves: {display}")

        pkf = meta.get("pkf")
        if not isinstance(pkf, dict):
            continue
        for key in ("loads", "related"):
            for target in listify(pkf.get(key)):
                target_path = repo_root / str(target)
                if target_path.is_file():
                    passed(report, f"{key} resolves: {target}")
                else:
                    error(report, display, f"broken pkf.{key}: {target}")


def check_reachability(
    ai_dir: Path,
    repo_root: Path,
    modules: list[str],
    metadata: dict[Path, dict[str, Any]],
    report: ValidationReport,
) -> None:
    startup_docs = [ai_dir / doc for doc in REQUIRED_RUNTIME_DOCS]
    if all(path.is_file() for path in startup_docs):
        passed(report, "startup path files exist")
    else:
        error(report, ".ai", "startup path is incomplete")

    root_index = ai_dir / "knowledge" / "INDEX.md"
    root_text = root_index.read_text(encoding="utf-8") if root_index.is_file() else ""
    root_meta = metadata.get(root_index, {})
    root_edges = set(str(item) for item in listify(root_meta.get("pkf", {}).get("loads", [])))
    root_edges.update(str(item) for item in listify(root_meta.get("pkf", {}).get("related", [])))
    for module in modules:
        module_path = f".ai/knowledge/{module}/INDEX.md"
        if module_path in root_text or module_path in root_edges or f"knowledge/{module}/INDEX.md" in root_text:
            passed(report, f"module reachable from knowledge/INDEX.md: {module}")
        else:
            error(report, rel(root_index, repo_root) if root_index.exists() else ".ai/knowledge/INDEX.md", f"module not reachable: {module}")


def check_unrelated_loads(repo_root: Path, metadata: dict[Path, dict[str, Any]], report: ValidationReport) -> None:
    for md, meta in metadata.items():
        source_module = module_for_path(md, repo_root)
        if source_module is None:
            continue
        pkf = meta.get("pkf")
        if not isinstance(pkf, dict):
            continue
        for target in listify(pkf.get("loads")):
            target_module = module_for_token(str(target))
            if target_module is not None and target_module != source_module:
                error(report, rel(md, repo_root), f"unrelated module loaded automatically through pkf.loads: {target}")


def add_token_impact(report: ValidationReport, ai_dir: Path, model: str) -> None:
    startup_files = [ai_dir / doc for doc in REQUIRED_RUNTIME_DOCS]
    add_route_tokens(report, "startup", startup_files, TOKEN_THRESHOLDS["startup"], model)

    for module in discover_modules(ai_dir):
        module_index = ai_dir / "knowledge" / module / "INDEX.md"
        route_files = [module_index]
        if module_index.is_file():
            try:
                meta = read_front_matter(module_index)
            except PkfParseError:
                meta = {}
            pkf = meta.get("pkf") if isinstance(meta, dict) else {}
            if isinstance(pkf, dict):
                for target in listify(pkf.get("loads")):
                    route_files.append(ai_dir.parent / str(target))
        add_route_tokens(report, f"module:{module}", route_files, TOKEN_THRESHOLDS["module"], model)


def add_route_tokens(report: ValidationReport, route: str, files: list[Path], threshold: int, model: str) -> None:
    existing = [path for path in files if path.is_file()]
    text = "\n".join(path.read_text(encoding="utf-8") for path in existing)
    tokens, estimator = count_tokens(text, model)
    status = "warning" if tokens > threshold else "passed"
    report.token_impact.append(TokenEntry(route=route, tokens=tokens, estimator=estimator, threshold=threshold, status=status))
    if status == "warning":
        warn(report, route, f"token count {tokens} exceeds threshold {threshold}")


def module_for_path(path: Path, repo_root: Path) -> str | None:
    parts = rel(path, repo_root).split("/")
    if len(parts) >= 4 and parts[0] == ".ai" and parts[1] == "knowledge":
        module = parts[2]
        if module not in {doc.removesuffix(".md") for doc in SHARED_DOCS} and parts[3]:
            return module
    return None


def module_for_token(token: str) -> str | None:
    parts = token.replace("\\", "/").split("/")
    if len(parts) >= 4 and parts[0] == ".ai" and parts[1] == "knowledge":
        return parts[2]
    return None


def check_file(path: Path, repo_root: Path, report: ValidationReport, message: str) -> None:
    if path.is_file():
        passed(report, message)
    else:
        error(report, rel(path, repo_root) if path.is_absolute() and repo_root in path.parents else path.as_posix(), "missing required file")


def passed(report: ValidationReport, message: str) -> None:
    report.passed.append(message)


def warn(report: ValidationReport, file: str, issue: str) -> None:
    report.warnings.append(ValidationFinding(file=file, issue=issue))


def error(report: ValidationReport, file: str, issue: str) -> None:
    report.errors.append(ValidationFinding(file=file, issue=issue))


def report_to_dict(report: ValidationReport) -> dict[str, Any]:
    return {
        "path": report.path,
        "strictness": report.strictness,
        "status": report.status,
        "exit_code": report.exit_code,
        "passed": report.passed,
        "warnings": [finding.__dict__ for finding in report.warnings],
        "errors": [finding.__dict__ for finding in report.errors],
        "token_impact": [entry.__dict__ for entry in report.token_impact],
    }


def render_text(report: ValidationReport) -> str:
    lines = [
        "PKF Validation",
        f"Path: {report.path}",
        f"Strictness: {report.strictness}",
        f"Status: {report.status}",
        "",
        "Passed:",
    ]
    lines.extend(f"- {item}" for item in report.passed) if report.passed else lines.append("- none")
    lines.append("")
    lines.append("Warnings:")
    lines.extend(f"- {item.file}: {item.issue}" for item in report.warnings) if report.warnings else lines.append("- none")
    lines.append("")
    lines.append("Errors:")
    lines.extend(f"- {item.file}: {item.issue}" for item in report.errors) if report.errors else lines.append("- none")
    lines.append("")
    lines.append("Token Impact:")
    if report.token_impact:
        lines.extend(
            f"- {entry.route}: {entry.tokens} tokens ({entry.estimator}), threshold {entry.threshold}, {entry.status}"
            for entry in report.token_impact
        )
    else:
        lines.append("- none")
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
