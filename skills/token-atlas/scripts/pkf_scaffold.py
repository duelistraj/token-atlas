#!/usr/bin/env python3
"""Create a complete Token Atlas runtime from a reviewed evidence specification."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pkf_contract import LEAF_MODULE_DOCS, RUNTIME_VERSION  # noqa: E402

DEFAULT_SPEC = Path(".pkf-init.json")
SOURCE_EXTENSIONS = {
    ".c", ".cc", ".cpp", ".cs", ".go", ".java", ".js", ".jsx", ".kt",
    ".php", ".py", ".rb", ".rs", ".swift", ".ts", ".tsx", ".vue",
}
IGNORED_PARTS = {
    ".git", ".ai", ".cache", ".next", ".venv", "build", "coverage",
    "dist", "node_modules", "target", "vendor",
}
MANIFEST_NAMES = {
    "Cargo.toml", "Gemfile", "build.gradle", "composer.json", "go.mod",
    "package.json", "pom.xml", "pyproject.toml", "requirements.txt",
}
COMMON_SOURCE_ROOTS = (
    "src", "app", "lib", "server", "backend", "frontend/src", "client/src",
    "packages",
)
RUNTIME_TOOL_FILES = (
    "pkf_contract.py",
    "pkf_lib.py",
    "pkf_route.py",
    "pkf_tokens.py",
    "pkf_validate.py",
)
MODULE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
START_MARKER = "<!-- token-atlas:bootstrap:start -->"
END_MARKER = "<!-- token-atlas:bootstrap:end -->"


class ScaffoldError(ValueError):
    """Invalid request or unsafe scaffold input."""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inspect_parser = subparsers.add_parser("inspect", help="Write a bounded structural specification draft.")
    inspect_parser.add_argument("--path", type=Path, default=Path("."))
    inspect_parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    inspect_parser.add_argument("--root", action="append", default=[])

    create_parser = subparsers.add_parser("create", help="Create and validate a complete runtime from a reviewed specification.")
    create_parser.add_argument("--path", type=Path, default=Path("."))
    create_parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    create_parser.add_argument("--keep-spec", action="store_true")
    create_parser.add_argument(
        "--strictness",
        choices=("ci",),
        default="ci",
        help="Compatibility option; fresh initialization is always strict.",
    )
    return parser.parse_args()


def resolve_repo(path: Path) -> Path:
    repo = path.resolve()
    if not repo.is_dir():
        raise ScaffoldError(f"repository path is not a directory: {path}")
    return repo


def resolve_inside(repo: Path, path: Path) -> Path:
    candidate = path if path.is_absolute() else repo / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(repo)
    except ValueError as exc:
        raise ScaffoldError(f"path escapes repository: {path}") from exc
    return resolved


def relative(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def source_files(root: Path) -> list[Path]:
    if not root.is_dir():
        return []
    return [
        path
        for path in root.rglob("*")
        if path.is_file()
        and path.suffix.lower() in SOURCE_EXTENSIONS
        and not any(part in IGNORED_PARTS for part in path.parts)
    ]


def detected_roots(repo: Path, requested: list[str]) -> list[Path]:
    if requested:
        roots = [resolve_inside(repo, Path(value)) for value in requested]
        missing = [str(path) for path in roots if not path.is_dir()]
        if missing:
            raise ScaffoldError(f"inspection root does not exist: {', '.join(missing)}")
        return roots
    roots = [repo / value for value in COMMON_SOURCE_ROOTS if (repo / value).is_dir()]
    roots = [root for root in roots if source_files(root)]
    return roots or [repo]


def technology_names(files: list[Path], manifests: list[Path]) -> list[str]:
    by_extension = {
        ".go": "Go", ".java": "Java", ".js": "JavaScript", ".jsx": "JavaScript",
        ".php": "PHP", ".py": "Python", ".rb": "Ruby", ".rs": "Rust",
        ".ts": "TypeScript", ".tsx": "TypeScript", ".vue": "Vue",
    }
    values = {by_extension[path.suffix.lower()] for path in files if path.suffix.lower() in by_extension}
    if any(path.name == "Cargo.toml" for path in manifests):
        values.add("Rust")
    if any(path.name == "go.mod" for path in manifests):
        values.add("Go")
    return sorted(values)


def candidate_capabilities(repo: Path, roots: list[Path]) -> tuple[list[dict[str, Any]], bool, int]:
    candidates: list[tuple[int, str, Path, list[Path]]] = []
    for root in roots:
        child_candidates = []
        for child in sorted(root.iterdir()) if root.is_dir() else []:
            if child.is_dir() and child.name not in IGNORED_PARTS:
                files = source_files(child)
                if files:
                    child_candidates.append((child, files))
        if child_candidates:
            for child, files in child_candidates:
                candidates.append((len(files), child.name, child, files))
        else:
            files = source_files(root)
            if files:
                candidates.append((len(files), root.name or repo.name, root, files))

    candidates.sort(key=lambda item: (-item[0], relative(repo, item[2])))
    total = len(candidates)
    selected = candidates[:40]
    result = []
    for count, name, path, files in selected:
        representatives = sorted(files, key=lambda item: relative(repo, item))[:3]
        result.append(
            {
                "suggested_id": slugify(name),
                "source_root": relative(repo, path),
                "source_file_count": count,
                "representative_paths": [relative(repo, item) for item in representatives],
            }
        )
    return result, total > len(selected), total


def slugify(value: str) -> str:
    value = re.sub(r"[^a-z0-9_-]+", "-", value.lower()).strip("-_")
    return value or "repository"


def inspect_repo(repo: Path, spec_path: Path, requested_roots: list[str]) -> dict[str, Any]:
    if (repo / ".ai/PKF.md").exists():
        raise ScaffoldError("fresh inspection refused: .ai/PKF.md already exists")
    ai = repo / ".ai"
    if ai.exists() and any(ai.iterdir()):
        raise ScaffoldError("fresh inspection refused: .ai already contains runtime content")
    roots = detected_roots(repo, requested_roots)
    all_files = [path for root in roots for path in source_files(root)]
    manifests = sorted(
        path for path in repo.rglob("*")
        if path.is_file()
        and path.name in MANIFEST_NAMES
        and not any(part in IGNORED_PARTS for part in path.parts)
    )[:30]
    tests = sorted(
        path for path in repo.rglob("*")
        if path.is_dir()
        and path.name.lower() in {"test", "tests", "__tests__", "spec"}
        and not any(part in IGNORED_PARTS for part in path.parts)
    )[:30]
    candidates, truncated, candidate_count = candidate_capabilities(repo, roots)
    payload = {
        "schema_version": 2,
        "project": {"name": repo.name},
        "technologies": technology_names(all_files, manifests),
        "roots": {
            "source": [relative(repo, path) for path in roots],
            "test": [relative(repo, path) for path in tests],
            "config": [relative(repo, path) for path in manifests],
            "docs": ["docs"] if (repo / "docs").is_dir() else [],
        },
        "commands": {},
        "candidate_capabilities": candidates,
        "capabilities": [],
        "inspection": {
            "candidate_count": candidate_count,
            "candidate_limit": 40,
            "representative_path_limit": 3,
            "truncated": truncated,
        },
    }
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def yaml_value(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def front_matter(
    *,
    doc_type: str,
    title: str,
    description: str,
    loads: list[str] | None = None,
    related: list[str] | None = None,
    runtime: bool = False,
    leaf: bool = False,
    ownership_roots: list[str] | None = None,
    cross_routes: bool = False,
    resource: str = ".",
    timestamp: str | None = None,
    source_symbols: dict[str, list[str]] | None = None,
    ownership: dict[str, list[str]] | None = None,
    routes: dict[str, Any] | None = None,
) -> str:
    lines = [
        "---",
        f"type: {yaml_value(doc_type)}",
        f"title: {yaml_value(title)}",
        f"description: {yaml_value(description)}",
        f"resource: {yaml_value(resource)}",
        "tags: [pkf]",
        f"timestamp: {yaml_value(timestamp or dt.date.today().isoformat())}",
    ]
    if leaf:
        lines.extend(yaml_mapping("source_symbols", source_symbols or {}, 0))
    lines.append("pkf:")
    if runtime:
        lines.extend((f"  runtime_version: {RUNTIME_VERSION}", "  retrieval: adaptive", "  closeout: adaptive"))
    if leaf:
        lines.append("  materialization: complete")
    if ownership_roots is not None:
        lines.append("  ownership_roots:")
        for item in ownership_roots:
            lines.append(f"    - {yaml_value(item)}")
    if ownership is not None:
        lines.extend(yaml_mapping("ownership", ownership, 2))
    if cross_routes:
        lines.extend(yaml_mapping("routes", routes or {}, 2))
    lines.append("  loads:")
    for item in loads or []:
        lines.append(f"    - {yaml_value(item)}")
    if not loads:
        lines[-1] = "  loads: []"
    lines.append("  related:")
    for item in related or []:
        lines.append(f"    - {yaml_value(item)}")
    if not related:
        lines[-1] = "  related: []"
    lines.extend(("---", ""))
    return "\n".join(lines)


def yaml_mapping(key: str, value: dict[str, Any], indent: int) -> list[str]:
    prefix = " " * indent
    if not value:
        return [f"{prefix}{key}: {{}}"]
    lines = [f"{prefix}{key}:"]
    for raw_key, raw_value in value.items():
        rendered_key = str(raw_key)
        if isinstance(raw_value, dict):
            lines.extend(yaml_mapping(rendered_key, raw_value, indent + 2))
        elif isinstance(raw_value, list):
            if raw_value:
                lines.append(f"{' ' * (indent + 2)}{rendered_key}:")
                lines.extend(f"{' ' * (indent + 4)}- {yaml_value(str(item))}" for item in raw_value)
            else:
                lines.append(f"{' ' * (indent + 2)}{rendered_key}: []")
        else:
            lines.append(f"{' ' * (indent + 2)}{rendered_key}: {yaml_value(str(raw_value))}")
    return lines


def runtime_doc(project_name: str, protocols: str) -> str:
    return front_matter(
        doc_type="runtime",
        title=f"{project_name} PKF Runtime",
        description="Adaptive repository knowledge routing and closeout contract.",
        loads=[".ai/MEMORY.md", ".ai/ARCHITECTURE.md", ".ai/knowledge/INDEX.md"],
        runtime=True,
    ) + f"# {project_name} Project Knowledge Framework\n\n{protocols.strip()}\n"


def simple_doc(
    doc_type: str,
    title: str,
    description: str,
    body: str,
    *,
    related: list[str] | None = None,
    cross_routes: bool = False,
    routes: dict[str, Any] | None = None,
    resource: str = ".",
) -> str:
    return front_matter(
        doc_type=doc_type,
        title=title,
        description=description,
        related=related,
        cross_routes=cross_routes,
        routes=routes,
        resource=resource,
    ) + body.rstrip() + "\n"


def module_index(module: dict[str, Any]) -> str:
    module_id = module["id"]
    title = str(module.get("title") or module_id.replace("-", " ").title())
    roots = ", ".join(f"`{value}`" for value in module["ownership"])
    leaf_rows = "\n".join(
        f"| {leaf['title']} | `{leaf['file']}` |" for leaf in module["leaves"]
    )
    return front_matter(
        doc_type="module-index",
        title=f"{title} Knowledge Index",
        description=f"Routes work owned by the {title} capability.",
        related=[],
        ownership_roots=list(module["ownership"]),
        ownership=module["ownership"],
        resource=next(iter(module["ownership"])),
    ) + (
        f"# {title}\n\nOwnership roots: {roots}\n\n"
        "| Need | Document |\n| --- | --- |\n"
        f"{leaf_rows}\n"
    )


def validate_spec(repo: Path, value: Any) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(value, dict) or value.get("schema_version") != 2:
        raise ScaffoldError("spec schema_version must be 2")
    project = value.get("project")
    name = project.get("name") if isinstance(project, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise ScaffoldError("spec project.name must be non-empty")
    capabilities = value.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise ScaffoldError("reviewed spec must define at least one capability")
    seen_ids: set[str] = set()
    ownership: dict[str, set[str] | None] = {}
    normalized: list[dict[str, Any]] = []
    for raw in capabilities:
        if not isinstance(raw, dict):
            raise ScaffoldError("each capability must be an object")
        module_id = raw.get("id")
        raw_ownership = raw.get("ownership")
        leaves = raw.get("leaves")
        if not isinstance(module_id, str) or not MODULE_RE.fullmatch(module_id):
            raise ScaffoldError(f"invalid flat capability id: {module_id!r}")
        if module_id in seen_ids:
            raise ScaffoldError(f"duplicate capability id: {module_id}")
        if not isinstance(raw_ownership, dict) or not raw_ownership:
            raise ScaffoldError(f"capability {module_id} requires ownership")
        normalized_ownership: dict[str, list[str]] = {}
        for raw_path, raw_symbols in raw_ownership.items():
            if not isinstance(raw_path, str) or not raw_path.strip() or ":" in raw_path or "\n" in raw_path:
                raise ScaffoldError(f"capability {module_id} has an invalid ownership path")
            resolved = resolve_inside(repo, Path(raw_path))
            if not resolved.exists():
                raise ScaffoldError(f"capability ownership path does not exist: {raw_path}")
            path_ref = relative(repo, resolved)
            if not isinstance(raw_symbols, list) or not all(
                isinstance(symbol, str) and symbol.strip() for symbol in raw_symbols
            ):
                raise ScaffoldError(f"capability {module_id} ownership symbols must be a string list: {path_ref}")
            symbols = list(dict.fromkeys(symbol.strip() for symbol in raw_symbols))
            claimed = set(symbols) if symbols else None
            previous = ownership.get(path_ref)
            if previous is None and path_ref in ownership:
                raise ScaffoldError(f"exclusive ownership path is already assigned: {path_ref}")
            if claimed is None and path_ref in ownership:
                raise ScaffoldError(f"exclusive ownership path conflicts with another capability: {path_ref}")
            if previous is not None and claimed is not None and previous & claimed:
                conflict = ", ".join(sorted(previous & claimed))
                raise ScaffoldError(f"duplicate capability symbol ownership at {path_ref}: {conflict}")
            ownership[path_ref] = None if claimed is None else (previous or set()) | claimed
            text = resolved.read_text(encoding="utf-8", errors="ignore") if resolved.is_file() else ""
            missing_symbols = [symbol for symbol in symbols if symbol not in text]
            if missing_symbols:
                raise ScaffoldError(
                    f"capability {module_id} ownership symbols do not resolve in {path_ref}: "
                    + ", ".join(missing_symbols)
                )
            normalized_ownership[path_ref] = symbols
        if not isinstance(leaves, list) or not leaves:
            raise ScaffoldError(f"capability {module_id} requires at least one evidence-backed leaf")
        normalized_leaves: list[dict[str, Any]] = []
        seen_leaves: set[str] = set()
        for raw_leaf in leaves:
            if not isinstance(raw_leaf, dict):
                raise ScaffoldError(f"capability {module_id} leaf must be an object")
            filename = raw_leaf.get("file")
            if filename not in LEAF_MODULE_DOCS or filename in seen_leaves:
                raise ScaffoldError(f"capability {module_id} has invalid or duplicate leaf: {filename!r}")
            title = raw_leaf.get("title")
            description = raw_leaf.get("description")
            body = raw_leaf.get("body")
            source_symbols = raw_leaf.get("source_symbols")
            resource = raw_leaf.get("resource")
            if not all(isinstance(item, str) and item.strip() for item in (title, description, body, resource)):
                raise ScaffoldError(f"capability {module_id} leaf {filename} requires title, description, resource, and body")
            if "TODO" in body.upper():
                raise ScaffoldError(f"capability {module_id} leaf {filename} contains TODO")
            resolved_resource = resolve_inside(repo, Path(resource))
            if not resolved_resource.exists():
                raise ScaffoldError(f"capability {module_id} leaf resource does not resolve: {resource}")
            if not isinstance(source_symbols, dict) or not source_symbols:
                raise ScaffoldError(f"capability {module_id} leaf {filename} requires source_symbols")
            normalized_symbols: dict[str, list[str]] = {}
            for raw_source, raw_names in source_symbols.items():
                if not isinstance(raw_source, str) or ":" in raw_source or "\n" in raw_source:
                    raise ScaffoldError(f"capability {module_id} leaf {filename} has invalid source path")
                source = resolve_inside(repo, Path(raw_source))
                if not source.is_file():
                    raise ScaffoldError(f"capability {module_id} leaf source does not resolve: {raw_source}")
                if not isinstance(raw_names, list) or not raw_names or not all(
                    isinstance(symbol, str) and symbol.strip() for symbol in raw_names
                ):
                    raise ScaffoldError(f"capability {module_id} leaf source symbols must be non-empty: {raw_source}")
                names = list(dict.fromkeys(symbol.strip() for symbol in raw_names))
                source_text = source.read_text(encoding="utf-8", errors="ignore")
                missing = [symbol for symbol in names if symbol not in source_text]
                if missing:
                    raise ScaffoldError(
                        f"capability {module_id} leaf symbols do not resolve in {raw_source}: "
                        + ", ".join(missing)
                    )
                normalized_symbols[relative(repo, source)] = names
            normalized_leaves.append(
                {
                    "file": filename,
                    "title": title.strip(),
                    "description": description.strip(),
                    "resource": relative(repo, resolved_resource),
                    "source_symbols": normalized_symbols,
                    "body": body.strip(),
                }
            )
            seen_leaves.add(filename)
        seen_ids.add(module_id)
        normalized.append(
            {
                "id": module_id,
                "title": raw.get("title") or module_id,
                "ownership": normalized_ownership,
                "leaves": normalized_leaves,
            }
        )
    return name.strip(), normalized


def merge_bootstrap(repo: Path, block: str) -> Path:
    path = repo / "AGENTS.md"
    text = path.read_text(encoding="utf-8") if path.is_file() else "# AGENTS\n"
    if START_MARKER in text or END_MARKER in text:
        if text.count(START_MARKER) != 1 or text.count(END_MARKER) != 1:
            raise ScaffoldError("AGENTS.md contains malformed Token Atlas bootstrap markers")
        start = text.index(START_MARKER)
        end = text.index(END_MARKER, start) + len(END_MARKER)
        text = text[:start] + block.strip() + text[end:]
    else:
        text = text.rstrip() + "\n\n" + block.strip() + "\n"
    path.write_text(text, encoding="utf-8")
    return path


def create_runtime(repo: Path, spec_path: Path, keep_spec: bool) -> dict[str, Any]:
    if (repo / ".ai/PKF.md").exists():
        raise ScaffoldError("fresh scaffold refused: .ai/PKF.md already exists")
    if not spec_path.is_file():
        raise ScaffoldError(f"reviewed specification does not exist: {relative(repo, spec_path)}")
    ai = repo / ".ai"
    if ai.exists() and any(ai.iterdir()):
        raise ScaffoldError("fresh scaffold refused: .ai contains content")
    value = json.loads(spec_path.read_text(encoding="utf-8"))
    project_name, modules = validate_spec(repo, value)
    routes = value.get("routes", {})
    if not isinstance(routes, dict):
        raise ScaffoldError("spec routes must be an object")
    protocols = (SKILL_DIR / "templates/protocols.md").read_text(encoding="utf-8")
    bootstrap = (SKILL_DIR / "templates/bootstrap.md").read_text(encoding="utf-8")
    knowledge = ai / "knowledge"
    created: list[Path] = []
    agents_path = repo / "AGENTS.md"
    original_agents = agents_path.read_text(encoding="utf-8") if agents_path.is_file() else None

    def quarantine_runtime() -> Path | None:
        destination = None
        if ai.exists():
            destination = (
                repo
                / ".token-atlas"
                / "drafts"
                / dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            )
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(ai), str(destination))
        if original_agents is None:
            agents_path.unlink(missing_ok=True)
        else:
            agents_path.write_text(original_agents, encoding="utf-8")
        return destination

    def write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path != spec_path:
            raise ScaffoldError(f"fresh scaffold would overwrite existing path: {relative(repo, path)}")
        path.write_text(text, encoding="utf-8")
        created.append(path)

    source_roots = list(value.get("roots", {}).get("source", [])) if isinstance(value.get("roots"), dict) else []
    technologies = [str(item) for item in value.get("technologies", []) if str(item)]
    commands = value.get("commands", {}) if isinstance(value.get("commands"), dict) else {}
    memory_lines = [f"- Project: `{project_name}`."]
    if source_roots:
        memory_lines.append("- Source roots: " + ", ".join(f"`{item}`" for item in source_roots) + ".")
    if technologies:
        memory_lines.append("- Detected technologies: " + ", ".join(technologies) + ".")
    for name, command in sorted(commands.items()):
        if isinstance(name, str) and isinstance(command, str) and name.strip() and command.strip():
            memory_lines.append(f"- `{name}` command: `{command}`.")

    try:
        write(ai / "PKF.md", runtime_doc(project_name, protocols))
        write(
            ai / "MEMORY.md",
            simple_doc(
                "memory",
                f"{project_name} Memory",
                "Verified stable repository-wide facts.",
                "# Memory\n\n" + "\n".join(memory_lines),
                resource=".",
            ),
        )
        ownership_rows = "\n".join(
            f"| `{module['id']}` | {', '.join(f'`{root}`' for root in module['ownership'])} |"
            for module in modules
        )
        write(
            ai / "ARCHITECTURE.md",
            simple_doc(
                "architecture", f"{project_name} Architecture", "Source-backed capability ownership.",
                "# Architecture\n\n| Capability | Ownership evidence |\n| --- | --- |\n" + ownership_rows,
                related=[],
                resource=".",
            ),
        )
        routing_rows = "\n".join(
            f"| `{module['id']}` | {', '.join(f'`{root}`' for root in module['ownership'])} | `.ai/knowledge/{module['id']}/INDEX.md` |"
            for module in modules
        )
        write(
            knowledge / "INDEX.md",
            simple_doc(
                "knowledge-index", f"{project_name} Knowledge Index", "Routes repository-derived capabilities to evidence-backed knowledge.",
                (
                    "# Knowledge Index\n\n| Capability | Ownership evidence | Route |\n| --- | --- | --- |\n"
                    + routing_rows
                    + "\n\n## Cross-capability routes\n\n"
                    "Requirements resolve to one authoritative leaf and composed routes deduplicate shared requirements and leaves.\n"
                ),
                related=[],
                cross_routes=True,
                routes=routes,
                resource=".",
            ),
        )
        if technologies or commands:
            dependency_lines = [f"- Technology: {item}." for item in technologies]
            dependency_lines.extend(
                f"- `{name}`: `{command}`."
                for name, command in sorted(commands.items())
                if isinstance(name, str) and isinstance(command, str) and name.strip() and command.strip()
            )
            write(
                knowledge / "dependencies.md",
                simple_doc(
                    "shared-knowledge",
                    "Dependencies and Commands",
                    "Verified repository technologies and commands.",
                    "# Dependencies and Commands\n\n" + "\n".join(dependency_lines),
                    resource=".",
                ),
            )
        for module in modules:
            module_dir = knowledge / module["id"]
            write(module_dir / "INDEX.md", module_index(module))
            for leaf in module["leaves"]:
                write(
                    module_dir / leaf["file"],
                    front_matter(
                        doc_type="knowledge",
                        title=leaf["title"],
                        description=leaf["description"],
                        leaf=True,
                        resource=leaf["resource"],
                        source_symbols=leaf["source_symbols"],
                    )
                    + leaf["body"].rstrip()
                    + "\n",
                )
        for filename in RUNTIME_TOOL_FILES:
            write(ai / "tools" / filename, (SCRIPT_DIR / filename).read_text(encoding="utf-8"))
        created.append(merge_bootstrap(repo, bootstrap))
    except Exception:
        quarantine_runtime()
        raise

    validator = ai / "tools" / "pkf_validate.py"
    try:
        completed = subprocess.run(
            (sys.executable, "-S", str(validator), "--path", str(repo), "--strictness", "ci", "--format", "json", "--detail", "summary"),
            cwd=repo,
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        quarantine_runtime()
        raise
    try:
        validation_result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        quarantine_runtime()
        raise ScaffoldError(f"generated runtime validation returned invalid JSON: {completed.stdout[-1000:].strip()}") from exc
    if completed.returncode != 0 or validation_result.get("status") == "failed":
        errors = validation_result.get("errors", [])
        quarantine_runtime()
        raise ScaffoldError(f"generated runtime failed validation: {json.dumps(errors, sort_keys=True)}")
    if not keep_spec:
        spec_path.unlink()
    return {
        "status": "created",
        "module_count": len(modules),
        "created_path_count": len(set(created)),
        "validation": validation_result.get("status", "unknown"),
        "spec_consumed": not keep_spec,
    }


def main() -> int:
    try:
        args = parse_args()
        repo = resolve_repo(args.path)
        spec_path = resolve_inside(repo, args.spec)
        if args.command == "inspect":
            result = inspect_repo(repo, spec_path, args.root)
            summary = {
                "status": "inspected",
                "spec": relative(repo, spec_path),
                "candidate_count": result["inspection"]["candidate_count"],
                "truncated": result["inspection"]["truncated"],
            }
        else:
            summary = create_runtime(repo, spec_path, args.keep_spec)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, ScaffoldError) as exc:
        print(f"pkf_scaffold: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
