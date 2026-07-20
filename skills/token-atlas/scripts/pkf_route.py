#!/usr/bin/env python3
"""Map changed repository paths to the smallest affected Token Atlas leaves."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path, PurePosixPath
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pkf_contract import (  # noqa: E402
    LEAF_MATERIALIZATION_FIELD,
    LEAF_MODULE_DOCS,
    LEAF_SOURCE_SYMBOLS_FIELD,
    MODULE_OWNERSHIP_FIELD,
    MODULE_OWNERSHIP_ROOTS_FIELD,
    SHARED_DOCS,
)
from pkf_lib import PkfParseError, read_front_matter  # noqa: E402


class RouteError(ValueError):
    """Invalid route request."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--path", type=Path, default=Path("."), help="Repository root or .ai directory.")
    parser.add_argument("--changed-path", action="append", required=True, metavar="PATH")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    return parser.parse_args()


def resolve_layout(path: Path) -> tuple[Path, Path]:
    candidate = path.resolve()
    ai = candidate if candidate.name == ".ai" else candidate / ".ai"
    repo = ai.parent
    if not (ai / "PKF.md").is_file():
        raise RouteError(f"PKF runtime is missing: {ai / 'PKF.md'}")
    return repo, ai


def normalize_paths(values: list[str]) -> tuple[str, ...]:
    normalized: list[str] = []
    for raw in values:
        token = PurePosixPath(raw.replace("\\", "/").removeprefix("./"))
        if token.is_absolute() or ".." in token.parts or not token.parts:
            raise RouteError(f"changed path must be repository-relative without '..': {raw}")
        value = token.as_posix()
        if value in {"", "."}:
            raise RouteError("changed path must not be empty")
        normalized.append(value)
    return tuple(dict.fromkeys(normalized))


def path_matches(changed: str, source: str) -> bool:
    return changed == source or changed.startswith(f"{source}/") or source.startswith(f"{changed}/")


def module_fallbacks(repo: Path, knowledge: Path, unmatched: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    ownership: list[tuple[str, str, str]] = []
    for module_dir in sorted(path for path in knowledge.iterdir() if path.is_dir()) if knowledge.is_dir() else []:
        index = module_dir / "INDEX.md"
        if not index.is_file():
            continue
        try:
            metadata = read_front_matter(index)
        except PkfParseError as exc:
            raise RouteError(str(exc)) from exc
        pkf = metadata.get("pkf")
        ownership_map = pkf.get(MODULE_OWNERSHIP_FIELD) if isinstance(pkf, dict) else None
        roots = (
            list(ownership_map)
            if isinstance(ownership_map, dict)
            else pkf.get(MODULE_OWNERSHIP_ROOTS_FIELD, [])
            if isinstance(pkf, dict)
            else []
        )
        if not isinstance(roots, list):
            continue
        index_ref = index.relative_to(repo).as_posix()
        for raw_root in roots:
            root = str(raw_root).strip().removeprefix("./").rstrip("/")
            if root:
                ownership.append((root, module_dir.name, index_ref))

    grouped: dict[tuple[str, str], dict[str, Any]] = {}
    unknown: list[str] = []
    for changed in unmatched:
        candidates = [item for item in ownership if path_matches(changed, item[0])]
        if not candidates:
            unknown.append(changed)
            continue
        longest = max(len(root) for root, _, _ in candidates)
        for root, module, index_ref in candidates:
            if len(root) != longest:
                continue
            key = (module, index_ref)
            entry = grouped.setdefault(
                key,
                {
                    "kind": "module",
                    "module": module,
                    "index": index_ref,
                    "ownership_roots": [],
                    "changed_paths": [],
                },
            )
            entry["ownership_roots"].append(root)
            entry["changed_paths"].append(changed)

    routes = []
    for entry in grouped.values():
        entry["ownership_roots"] = sorted(set(entry["ownership_roots"]))
        entry["changed_paths"] = sorted(set(entry["changed_paths"]))
        routes.append(entry)
    if unknown:
        routes.append(
            {
                "kind": "root",
                "module": None,
                "index": ".ai/knowledge/INDEX.md",
                "ownership_roots": [],
                "changed_paths": sorted(unknown),
            }
        )
    return sorted(routes, key=lambda item: (item["kind"], item["index"])), unknown


def route_changes(repo: Path, ai: Path, changed_paths: tuple[str, ...]) -> dict[str, Any]:
    matches: dict[str, dict[str, Any]] = {}
    mapped: set[str] = set()
    full_validation = False
    full_scope_paths = {
        "AGENTS.md",
        ".ai/PKF.md",
        ".ai/MEMORY.md",
        ".ai/ARCHITECTURE.md",
        ".ai/knowledge/INDEX.md",
        *(f".ai/knowledge/{name}" for name in SHARED_DOCS),
    }
    for changed in changed_paths:
        if changed in full_scope_paths or changed.endswith("/INDEX.md"):
            mapped.add(changed)
            full_validation = True

    knowledge = ai / "knowledge"
    for module_dir in sorted(path for path in knowledge.iterdir() if path.is_dir()) if knowledge.is_dir() else []:
        for filename in LEAF_MODULE_DOCS:
            leaf = module_dir / filename
            if not leaf.is_file():
                continue
            try:
                metadata = read_front_matter(leaf)
            except PkfParseError as exc:
                raise RouteError(str(exc)) from exc
            raw_symbols = metadata.get(LEAF_SOURCE_SYMBOLS_FIELD)
            source_symbols = raw_symbols if isinstance(raw_symbols, dict) else {}
            leaf_ref = leaf.relative_to(repo).as_posix()
            matched_by: dict[str, list[str]] = {}
            for changed in changed_paths:
                reasons = []
                if changed == leaf_ref:
                    reasons.append("leaf")
                for source in source_symbols:
                    source_ref = str(source).strip()
                    if source_ref and path_matches(changed, source_ref):
                        reasons.append(source_ref)
                if reasons:
                    mapped.add(changed)
                    matched_by[changed] = sorted(set(reasons))
            if matched_by:
                pkf = metadata.get("pkf")
                materialization = pkf.get(LEAF_MATERIALIZATION_FIELD, "complete") if isinstance(pkf, dict) else "complete"
                matches[leaf_ref] = {
                    "path": leaf_ref,
                    "module": module_dir.name,
                    "materialization": materialization,
                    "matches": matched_by,
                }

    unmatched = sorted(set(changed_paths) - mapped)
    if not unmatched:
        status = "mapped"
    elif mapped:
        status = "partial"
    else:
        status = "unmapped"
    fallback_routes, _ = module_fallbacks(repo, knowledge, unmatched)
    return {
        "schema_version": 2,
        "status": status,
        "changed_paths": list(changed_paths),
        "affected_leaves": [matches[key] for key in sorted(matches)],
        "unmatched_paths": unmatched,
        "index_fallback": [item["index"] for item in fallback_routes],
        "fallback_routes": fallback_routes,
        "routing_coverage_defect": bool(unmatched),
        "validation_scope": "full" if full_validation else "affected",
    }


def render_text(result: dict[str, Any]) -> str:
    leaves = ", ".join(item["path"] for item in result["affected_leaves"]) or "none"
    unmatched = ", ".join(result["unmatched_paths"]) or "none"
    fallbacks = ", ".join(item["index"] for item in result["fallback_routes"]) or "none"
    return "\n".join(
        (
            f"Status: {result['status']}",
            f"Affected leaves: {leaves}",
            f"Unmatched paths: {unmatched}",
            f"Fallback indexes: {fallbacks}",
            f"Validation scope: {result['validation_scope']}",
        )
    )


def main() -> int:
    try:
        args = parse_args()
        repo, ai = resolve_layout(args.path)
        result = route_changes(repo, ai, normalize_paths(args.changed_path))
        print(json.dumps(result, indent=2, sort_keys=True) if args.format == "json" else render_text(result))
        return 0
    except (OSError, RouteError) as exc:
        print(f"pkf_route: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
