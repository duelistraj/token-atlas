#!/usr/bin/env python3
"""Deterministic mechanical validator for Token Atlas PKF trees."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pkf_contract import (  # noqa: E402
    CLOSEOUT_MODES,
    CLOSEOUT_PROTOCOL_HEADING,
    EDIT_MAP_COLUMNS,
    EDIT_MAP_HEADING,
    EMPTY_LEAF_MARKER,
    EXIT_CODES,
    GENERIC_EDIT_MAP_BEHAVIORS,
    LEAF_MODULE_DOCS,
    LEAF_SOURCE_SYMBOLS_FIELD,
    REQUIRED_FRONT_MATTER,
    REQUIRED_MODULE_DOCS,
    REQUIRED_RUNTIME_DOCS,
    RETRIEVAL_BUDGET,
    RUNTIME_VERSION,
    RUNTIME_VERSION_FIELD,
    SHARED_DOCS,
    TOKEN_THRESHOLDS,
    VALIDATION_STRICTNESS,
    PROTOCOL_REQUIREMENTS,
)
from pkf_lib import PkfParseError, listify, markdown_body, read_front_matter, rel  # noqa: E402
from pkf_tokens import count_tokens  # noqa: E402


ALLOWED_FORMATS = ("text", "json")
RETRIEVAL_PROTOCOL_HEADING = "## Retrieval Protocol (MANDATORY)"
BOOTSTRAP_FILE = "AGENTS.md"
BOOTSTRAP_REFERENCE = ".ai/PKF.md"
BOOTSTRAP_CLOSEOUT_REFERENCE = "Closeout Protocol"


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
        report = validate_pkf(
            args.path,
            args.strictness,
            args.model,
            changed_paths=args.changed_path,
        )
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
    parser.add_argument(
        "--model",
        default=None,
        help="Optional tokenizer model name. Without it, validation uses the portable approximate estimator.",
    )
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        metavar="PATH",
        help="Repository-relative changed path to validate as an affected slice. Repeat for multiple paths.",
    )
    return parser.parse_args()


class UsageError(Exception):
    """Invalid validator invocation."""


def validate_pkf(
    path: Path,
    strictness: str = "advisory",
    model: str | None = None,
    *,
    changed_paths: Sequence[str] = (),
) -> ValidationReport:
    if strictness not in VALIDATION_STRICTNESS:
        raise UsageError(f"invalid strictness: {strictness}")

    ai_dir = resolve_ai_dir(path)
    repo_root = ai_dir.parent
    report = ValidationReport(path=str(ai_dir), strictness=strictness)
    normalized_changed_paths = normalize_changed_paths(changed_paths)

    if not ai_dir.exists():
        error(report, ".ai", "missing PKF runtime directory")
        add_token_impact(report, ai_dir, model)
        return report
    if not ai_dir.is_dir():
        error(report, rel(ai_dir, repo_root), "PKF path is not a directory")
        return report

    check_required_docs(ai_dir, repo_root, report)
    check_runtime_protocols(ai_dir, repo_root, report)
    check_neutral_bootstrap(repo_root, report)
    check_flat_module_layout(ai_dir, repo_root, report)
    modules = discover_modules(ai_dir)
    check_module_docs(ai_dir, repo_root, modules, report)
    front_matter = check_front_matter(ai_dir, repo_root, report)
    check_runtime_config(ai_dir, repo_root, front_matter, report)
    affected_modules, mapped_changed_paths = check_leaf_contracts(
        ai_dir,
        repo_root,
        modules,
        front_matter,
        report,
        normalized_changed_paths,
    )
    for changed_path in sorted(set(normalized_changed_paths) - mapped_changed_paths):
        warn(report, changed_path, "changed path has no matching implementation leaf source_symbols entry")
    check_references(repo_root, front_matter, report)
    check_reachability(ai_dir, repo_root, modules, front_matter, report)
    check_unrelated_loads(repo_root, front_matter, report)
    add_token_impact(
        report,
        ai_dir,
        model,
        modules=affected_modules if normalized_changed_paths else None,
    )
    return report


def normalize_changed_paths(changed_paths: Sequence[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw_path in changed_paths:
        token = Path(raw_path)
        if token.is_absolute() or ".." in token.parts:
            raise UsageError(f"changed path must be repository-relative without '..': {raw_path}")
        value = token.as_posix().removeprefix("./")
        if not value or value == ".":
            raise UsageError("changed path must not be empty")
        normalized.append(value)
    return tuple(dict.fromkeys(normalized))


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


def check_runtime_protocols(ai_dir: Path, repo_root: Path, report: ValidationReport) -> None:
    pkf = ai_dir / "PKF.md"
    if not pkf.is_file():
        return
    text = pkf.read_text(encoding="utf-8")
    normalized_text = " ".join(text.split())
    headings = {line.strip() for line in text.splitlines()}
    for heading, label in (
        (RETRIEVAL_PROTOCOL_HEADING, "Retrieval Protocol"),
        (CLOSEOUT_PROTOCOL_HEADING, "Closeout Protocol"),
    ):
        if heading in headings:
            passed(report, f"PKF.md embeds the {label} heading")
        else:
            error(report, rel(pkf, repo_root), f"missing required heading: {heading}")
    for protocol, requirements in PROTOCOL_REQUIREMENTS.items():
        for requirement in requirements:
            if " ".join(requirement.split()) in normalized_text:
                passed(report, f"PKF.md embeds {protocol} protocol clause: {requirement}")
            else:
                error(report, rel(pkf, repo_root), f"missing required {protocol} protocol clause: {requirement}")


def check_neutral_bootstrap(repo_root: Path, report: ValidationReport) -> None:
    bootstrap = repo_root / BOOTSTRAP_FILE
    if not bootstrap.is_file():
        error(report, BOOTSTRAP_FILE, f"missing root bootstrap referencing {BOOTSTRAP_REFERENCE}")
        return
    text = bootstrap.read_text(encoding="utf-8")
    if BOOTSTRAP_REFERENCE in text:
        passed(report, f"root bootstrap references {BOOTSTRAP_REFERENCE}")
    else:
        error(report, BOOTSTRAP_FILE, f"missing reference to {BOOTSTRAP_REFERENCE}")
    if BOOTSTRAP_CLOSEOUT_REFERENCE in text:
        passed(report, f"root bootstrap references {BOOTSTRAP_CLOSEOUT_REFERENCE}")
    else:
        error(report, BOOTSTRAP_FILE, f"missing reference to {BOOTSTRAP_CLOSEOUT_REFERENCE}")


def check_runtime_config(
    ai_dir: Path,
    repo_root: Path,
    metadata: dict[Path, dict[str, Any]],
    report: ValidationReport,
) -> None:
    pkf_path = ai_dir / "PKF.md"
    if not pkf_path.is_file() or pkf_path not in metadata:
        return
    runtime = metadata[pkf_path].get("pkf")
    if not isinstance(runtime, dict):
        return
    version = runtime.get(RUNTIME_VERSION_FIELD)
    if version != RUNTIME_VERSION:
        if isinstance(version, int) and version > RUNTIME_VERSION:
            issue = f"pkf.{RUNTIME_VERSION_FIELD} {version} is newer than supported version {RUNTIME_VERSION}"
        elif version is None:
            issue = f"missing pkf.{RUNTIME_VERSION_FIELD}; migrate runtime to version {RUNTIME_VERSION}"
        else:
            issue = f"pkf.{RUNTIME_VERSION_FIELD} must be {RUNTIME_VERSION}; found {version!r}"
        error(report, rel(pkf_path, repo_root), issue)
    else:
        passed(report, f"PKF runtime version is current: {RUNTIME_VERSION}")

    mode = runtime.get("closeout")
    if mode not in CLOSEOUT_MODES:
        allowed = ", ".join(CLOSEOUT_MODES)
        error(report, rel(pkf_path, repo_root), f"pkf.closeout must be one of: {allowed}")
        return
    passed(report, f"PKF closeout mode is valid: {mode}")


def discover_modules(ai_dir: Path) -> list[str]:
    knowledge = ai_dir / "knowledge"
    if not knowledge.is_dir():
        return []
    return sorted(item.name for item in knowledge.iterdir() if item.is_dir() and item.name != "retrieval")


def check_flat_module_layout(ai_dir: Path, repo_root: Path, report: ValidationReport) -> None:
    knowledge = ai_dir / "knowledge"
    if not knowledge.is_dir():
        return
    nested_indexes = [
        path
        for path in sorted(knowledge.rglob("INDEX.md"))
        if len(path.relative_to(knowledge).parts) > 2
    ]
    if not nested_indexes:
        passed(report, "module indexes use a flat knowledge layout")
        return
    for path in nested_indexes:
        error(
            report,
            rel(path, repo_root),
            "nested module index is unsupported; use a flat module directory directly under .ai/knowledge",
        )


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


def check_leaf_contracts(
    ai_dir: Path,
    repo_root: Path,
    modules: list[str],
    metadata: dict[Path, dict[str, Any]],
    report: ValidationReport,
    changed_paths: Sequence[str] = (),
) -> tuple[set[str], set[str]]:
    affected_modules: set[str] = set()
    mapped_changed_paths: set[str] = set()
    for module in modules:
        for doc in LEAF_MODULE_DOCS:
            leaf = ai_dir / "knowledge" / module / doc
            if not leaf.is_file():
                continue
            display = rel(leaf, repo_root)
            meta = metadata.get(leaf, {})
            if LEAF_SOURCE_SYMBOLS_FIELD not in meta:
                error(report, display, f"missing leaf front matter field: {LEAF_SOURCE_SYMBOLS_FIELD}")
                continue
            source_symbols = meta.get(LEAF_SOURCE_SYMBOLS_FIELD)
            if not isinstance(source_symbols, dict):
                error(report, display, f"{LEAF_SOURCE_SYMBOLS_FIELD} must be a mapping of source paths to symbol lists")
                continue
            if not source_symbols:
                if EMPTY_LEAF_MARKER in markdown_body(leaf):
                    passed(report, f"standard empty leaf: {display}")
                else:
                    error(report, display, f"empty {LEAF_SOURCE_SYMBOLS_FIELD} requires marker: {EMPTY_LEAF_MARKER}")
                continue

            matched_paths = matching_changed_paths(leaf, repo_root, source_symbols, changed_paths)
            if changed_paths and not matched_paths:
                continue
            affected_modules.add(module)
            mapped_changed_paths.update(matched_paths)

            validate_source_symbols(leaf, repo_root, source_symbols, report)
            validate_edit_map(leaf, repo_root, source_symbols, report)
    return affected_modules, mapped_changed_paths


def matching_changed_paths(
    leaf: Path,
    repo_root: Path,
    source_symbols: dict[Any, Any],
    changed_paths: Sequence[str],
) -> set[str]:
    if not changed_paths:
        return set()
    leaf_ref = rel(leaf, repo_root)
    source_refs = {str(path).strip() for path in source_symbols}
    return {
        changed_path
        for changed_path in changed_paths
        if changed_path == leaf_ref
        or any(
            changed_path == source_ref
            or changed_path.startswith(f"{source_ref}/")
            or source_ref.startswith(f"{changed_path}/")
            for source_ref in source_refs
        )
    }


def validate_source_symbols(
    leaf: Path,
    repo_root: Path,
    source_symbols: dict[Any, Any],
    report: ValidationReport,
) -> None:
    display = rel(leaf, repo_root)
    for raw_path, raw_symbols in source_symbols.items():
        if not isinstance(raw_path, str) or not raw_path.strip():
            error(report, display, "source_symbols contains an empty or non-string path")
            continue
        source_ref = raw_path.strip()
        source_token = Path(source_ref)
        if source_token.is_absolute() or ".." in source_token.parts:
            error(report, display, f"source_symbols path must be repository-relative without '..': {source_ref}")
            continue
        source = repo_root / source_ref
        try:
            resolved = source.resolve()
            resolved.relative_to(repo_root.resolve())
        except (OSError, ValueError):
            error(report, display, f"source_symbols path escapes repository: {source_ref}")
            continue
        if not source.is_file():
            error(
                report,
                display,
                f"stale reference to deleted evidence; source_symbols path does not resolve: {source_ref}",
            )
            continue
        if not isinstance(raw_symbols, list) or not raw_symbols:
            error(report, display, f"source_symbols entry must be a non-empty list: {source_ref}")
            continue
        source_text = source.read_text(encoding="utf-8", errors="replace")
        for raw_symbol in raw_symbols:
            if not isinstance(raw_symbol, str) or not raw_symbol.strip():
                error(report, display, f"source_symbols contains an empty or non-string symbol: {source_ref}")
                continue
            symbol = raw_symbol.strip()
            if symbol not in source_text:
                error(report, display, f"source symbol does not resolve: {source_ref}:{symbol}")
            else:
                passed(report, f"source symbol resolves: {source_ref}:{symbol}")


def validate_edit_map(
    leaf: Path,
    repo_root: Path,
    source_symbols: dict[Any, Any],
    report: ValidationReport,
) -> None:
    display = rel(leaf, repo_root)
    body = markdown_body(leaf)
    lines = body.splitlines()
    heading_index = next((index for index, line in enumerate(lines) if line.strip() == EDIT_MAP_HEADING), None)
    if heading_index is None:
        error(report, display, f"missing required heading: {EDIT_MAP_HEADING}")
        return
    table_lines = []
    for line in lines[heading_index + 1 :]:
        if line.lstrip().startswith("|"):
            table_lines.append(line)
        elif table_lines:
            break
    header = table_lines[0] if table_lines else ""
    header_cells = split_markdown_row(header)
    missing = [column for column in EDIT_MAP_COLUMNS if column.lower() not in {cell.lower() for cell in header_cells}]
    if missing:
        error(report, display, f"Edit Map header missing columns: {', '.join(missing)}")
        return
    passed(report, f"Edit Map columns: {display}")
    rows = [split_markdown_row(line) for line in table_lines[2:]]
    rows = [row for row in rows if len(row) == len(header_cells)]
    if not rows:
        error(report, display, "Edit Map has no behavior rows")
        return

    column_by_name = {name.lower(): index for index, name in enumerate(header_cells)}
    behavior_index = column_by_name["behavior"]
    symbols_index = column_by_name["source symbols"]
    locator_index = column_by_name["locator"]
    known_symbols = {
        str(symbol).strip()
        for symbols in source_symbols.values()
        if isinstance(symbols, list)
        for symbol in symbols
        if isinstance(symbol, str) and symbol.strip()
    }
    mentioned_symbols: set[str] = set()

    for row in rows:
        behavior = row[behavior_index].strip().strip("`").lower()
        if behavior in GENERIC_EDIT_MAP_BEHAVIORS or behavior.startswith("todo"):
            error(report, display, f"Edit Map behavior is generic or placeholder text: {row[behavior_index].strip()}")
        source_cell = row[symbols_index]
        locator = row[locator_index]
        row_symbols = {symbol for symbol in known_symbols if symbol in source_cell or symbol in locator}
        mentioned_symbols.update(row_symbols)
        if "rg -n -F --" not in locator and "sg --pattern" not in locator:
            error(
                report,
                display,
                f"Edit Map row has no targeted rg or ast-grep locator command: {row[behavior_index].strip()}",
            )
        elif not row_symbols:
            error(report, display, f"Edit Map locator does not target a declared source symbol: {row[behavior_index].strip()}")

    missing_symbols = sorted(known_symbols - mentioned_symbols)
    if missing_symbols:
        error(report, display, f"Edit Map omits declared source symbols: {', '.join(missing_symbols)}")
    else:
        passed(report, f"Edit Map source symbols and locators agree: {display}")


def split_markdown_row(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def check_references(repo_root: Path, metadata: dict[Path, dict[str, Any]], report: ValidationReport) -> None:
    for md, meta in metadata.items():
        display = rel(md, repo_root)
        resource = str(meta.get("resource", ""))
        if resource.upper() == "TODO" or resource.startswith("TODO"):
            passed(report, f"resource marked TODO: {display}")
        elif not resource:
            error(report, display, "resource is empty")
        elif not resolve_resource_reference(md, repo_root, resource):
            error(report, display, f"resource path does not resolve: {resource}")
        else:
            passed(report, f"resource resolves: {display}")

        pkf = meta.get("pkf")
        if not isinstance(pkf, dict):
            continue
        for key in ("loads", "related"):
            for target in listify(pkf.get(key)):
                target_path = resolve_doc_reference(md, repo_root, str(target))
                if target_path is not None and target_path.is_file():
                    passed(report, f"{key} resolves: {target}")
                else:
                    error(report, display, f"broken pkf.{key}: {target}")


def resolve_doc_reference(md: Path, repo_root: Path, target: str) -> Path | None:
    token = Path(target)
    if token.is_absolute():
        return None
    candidate = repo_root / token if token.parts and token.parts[0] == ".ai" else md.parent / token
    try:
        resolved = candidate.resolve()
        resolved.relative_to(repo_root.resolve())
    except (OSError, ValueError):
        return None
    return resolved


def resolve_resource_reference(md: Path, repo_root: Path, resource: str) -> Path | None:
    token = Path(resource)
    if token.is_absolute():
        return None
    candidates = [repo_root / token, md.parent / token]
    knowledge_root = repo_root / ".ai" / "knowledge"
    try:
        md.resolve().relative_to(knowledge_root.resolve())
    except (OSError, ValueError):
        pass
    else:
        candidates.append(knowledge_root / token)

    for candidate in candidates:
        try:
            resolved = candidate.resolve()
            resolved.relative_to(repo_root.resolve())
        except (OSError, ValueError):
            continue
        if resolved.exists():
            return resolved
    return None


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
        if (
            module_path in root_text
            or module_path in root_edges
            or f"knowledge/{module}/INDEX.md" in root_text
            or f"{module}/INDEX.md" in root_text
        ):
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
        if md.name == "INDEX.md":
            leaf_loads = [
                str(target)
                for target in listify(pkf.get("loads"))
                if module_for_token(str(target)) == source_module and Path(str(target)).name in LEAF_MODULE_DOCS
            ]
            if len(leaf_loads) > RETRIEVAL_BUDGET["leaf_docs"]:
                error(
                    report,
                    rel(md, repo_root),
                    f"normal retrieval budget exceeded: {len(leaf_loads)} automatic leaves; maximum is {RETRIEVAL_BUDGET['leaf_docs']}",
                )


def add_token_impact(
    report: ValidationReport,
    ai_dir: Path,
    model: str | None,
    *,
    modules: set[str] | None = None,
) -> None:
    startup_files = [ai_dir / doc for doc in REQUIRED_RUNTIME_DOCS]
    add_route_tokens(report, "startup", startup_files, TOKEN_THRESHOLDS["startup"], model)

    selected_modules = discover_modules(ai_dir) if modules is None else sorted(modules)
    for module in selected_modules:
        module_index = ai_dir / "knowledge" / module / "INDEX.md"
        leaves = [ai_dir / "knowledge" / module / doc for doc in LEAF_MODULE_DOCS]
        for leaf in leaves:
            add_route_tokens(
                report,
                f"leaf:{module}/{leaf.name}",
                [leaf],
                TOKEN_THRESHOLDS["leaf"],
                model,
            )

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
        largest_leaves = sorted(
            (leaf for leaf in leaves if leaf.is_file()),
            key=lambda path: path.stat().st_size,
            reverse=True,
        )[:2]
        route_files.extend(largest_leaves)
        add_route_tokens(report, f"task:{module}", deduplicate_paths(route_files), TOKEN_THRESHOLDS["task"], model)


def add_route_tokens(
    report: ValidationReport,
    route: str,
    files: list[Path],
    threshold: int,
    model: str | None,
) -> None:
    existing = [path for path in files if path.is_file()]
    text = "\n".join(path.read_text(encoding="utf-8") for path in existing)
    tokens, estimator = count_tokens(text, model)
    status = "error" if tokens > threshold and report.strictness == "ci" else "warning" if tokens > threshold else "passed"
    report.token_impact.append(TokenEntry(route=route, tokens=tokens, estimator=estimator, threshold=threshold, status=status))
    if status in {"warning", "error"}:
        message = f"token count {tokens} exceeds threshold {threshold}"
        if status == "error":
            error(report, route, message)
        else:
            warn(report, route, message)


def deduplicate_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    result: list[Path] = []
    for path in paths:
        normalized = path.resolve()
        if normalized not in seen:
            seen.add(normalized)
            result.append(path)
    return result


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
