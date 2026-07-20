#!/usr/bin/env python3
"""Create a deterministic Token Atlas runtime skeleton from a reviewed spec."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from pkf_contract import RUNTIME_VERSION  # noqa: E402

DEFAULT_SPEC = Path(".ai/.pkf-init.json")
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
MODULE_DOCS = ("api.md", "schema.md", "business_rules.md", "ui.md")
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

    create_parser = subparsers.add_parser("create", help="Create a fresh runtime from a reviewed specification.")
    create_parser.add_argument("--path", type=Path, default=Path("."))
    create_parser.add_argument("--spec", type=Path, default=DEFAULT_SPEC)
    create_parser.add_argument("--keep-spec", action="store_true")
    create_parser.add_argument("--strictness", choices=("advisory", "ci"), default="advisory")
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
        "schema_version": 1,
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
    pending: bool = False,
    leaf: bool = False,
    ownership_roots: list[str] | None = None,
) -> str:
    lines = [
        "---",
        f"type: {yaml_value(doc_type)}",
        f"title: {yaml_value(title)}",
        f"description: {yaml_value(description)}",
        "resource: TODO",
        "tags: [pkf]",
        "timestamp: TODO",
    ]
    if leaf:
        lines.append("source_symbols: {}")
    lines.append("pkf:")
    if runtime:
        lines.extend((f"  runtime_version: {RUNTIME_VERSION}", "  retrieval: adaptive", "  closeout: adaptive"))
    if pending:
        lines.append("  materialization: pending")
    if ownership_roots is not None:
        lines.append("  ownership_roots:")
        for item in ownership_roots:
            lines.append(f"    - {yaml_value(item)}")
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


def runtime_doc(project_name: str, protocols: str) -> str:
    return front_matter(
        doc_type="runtime",
        title=f"{project_name} PKF Runtime",
        description="Adaptive repository knowledge routing and closeout contract.",
        loads=[".ai/MEMORY.md", ".ai/ARCHITECTURE.md", ".ai/knowledge/INDEX.md"],
        runtime=True,
    ) + f"# {project_name} Project Knowledge Framework\n\n{protocols.strip()}\n"


def simple_doc(doc_type: str, title: str, description: str, body: str, *, related: list[str] | None = None) -> str:
    return front_matter(
        doc_type=doc_type,
        title=title,
        description=description,
        related=related,
    ) + body.rstrip() + "\n"


def module_index(module: dict[str, Any]) -> str:
    module_id = module["id"]
    title = str(module.get("title") or module_id.replace("-", " ").title())
    roots = ", ".join(f"`{value}`" for value in module["source_roots"])
    return front_matter(
        doc_type="module-index",
        title=f"{title} Knowledge Index",
        description=f"Routes work owned by the {title} capability.",
        related=[f".ai/knowledge/{module_id}/{name}" for name in MODULE_DOCS],
        ownership_roots=list(module["source_roots"]),
    ) + (
        f"# {title}\n\nOwnership roots: {roots}\n\n"
        "| Need | Document |\n| --- | --- |\n"
        "| API or public interface | `api.md` |\n"
        "| Data shape or persistence | `schema.md` |\n"
        "| Behavior and workflows | `business_rules.md` |\n"
        "| User interface | `ui.md` |\n"
    )


def pending_leaf(module: dict[str, Any], filename: str) -> str:
    module_id = module["id"]
    label = filename.removesuffix(".md").replace("_", " ").title()
    return front_matter(
        doc_type="knowledge",
        title=f"{module.get('title') or module_id} {label}",
        description=f"Source-backed {label.lower()} facts for {module_id}.",
        pending=True,
        leaf=True,
    ) + f"# {label}\n\n- TODO: Pending source extraction.\n"


def validate_spec(repo: Path, value: Any) -> tuple[str, list[dict[str, Any]]]:
    if not isinstance(value, dict) or value.get("schema_version") != 1:
        raise ScaffoldError("spec schema_version must be 1")
    project = value.get("project")
    name = project.get("name") if isinstance(project, dict) else None
    if not isinstance(name, str) or not name.strip():
        raise ScaffoldError("spec project.name must be non-empty")
    capabilities = value.get("capabilities")
    if not isinstance(capabilities, list) or not capabilities:
        raise ScaffoldError("reviewed spec must define at least one capability")
    seen_ids: set[str] = set()
    ownership: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for raw in capabilities:
        if not isinstance(raw, dict):
            raise ScaffoldError("each capability must be an object")
        module_id = raw.get("id")
        roots = raw.get("source_roots")
        if not isinstance(module_id, str) or not MODULE_RE.fullmatch(module_id):
            raise ScaffoldError(f"invalid flat capability id: {module_id!r}")
        if module_id in seen_ids:
            raise ScaffoldError(f"duplicate capability id: {module_id}")
        if not isinstance(roots, list) or not roots:
            raise ScaffoldError(f"capability {module_id} requires source_roots")
        normalized_roots = []
        for raw_root in roots:
            if not isinstance(raw_root, str) or not raw_root.strip():
                raise ScaffoldError(f"capability {module_id} has an invalid source root")
            resolved = resolve_inside(repo, Path(raw_root))
            if not resolved.exists():
                raise ScaffoldError(f"capability source root does not exist: {raw_root}")
            root_ref = relative(repo, resolved)
            if root_ref in ownership:
                raise ScaffoldError(f"duplicate capability ownership root: {root_ref}")
            ownership.add(root_ref)
            normalized_roots.append(root_ref)
        seen_ids.add(module_id)
        normalized.append({"id": module_id, "title": raw.get("title") or module_id, "source_roots": normalized_roots})
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


def create_runtime(repo: Path, spec_path: Path, strictness: str, keep_spec: bool) -> dict[str, Any]:
    if (repo / ".ai/PKF.md").exists():
        raise ScaffoldError("fresh scaffold refused: .ai/PKF.md already exists")
    if not spec_path.is_file():
        raise ScaffoldError(f"reviewed specification does not exist: {relative(repo, spec_path)}")
    ai = repo / ".ai"
    existing = [path for path in ai.rglob("*") if path != spec_path] if ai.exists() else []
    if existing:
        raise ScaffoldError("fresh scaffold refused: .ai contains content other than the reviewed specification")
    value = json.loads(spec_path.read_text(encoding="utf-8"))
    project_name, modules = validate_spec(repo, value)
    protocols = (SKILL_DIR / "templates/protocols.md").read_text(encoding="utf-8")
    bootstrap = (SKILL_DIR / "templates/bootstrap.md").read_text(encoding="utf-8")
    knowledge = ai / "knowledge"
    created: list[Path] = []

    def write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path != spec_path:
            raise ScaffoldError(f"fresh scaffold would overwrite existing path: {relative(repo, path)}")
        path.write_text(text, encoding="utf-8")
        created.append(path)

    write(ai / "PKF.md", runtime_doc(project_name, protocols))
    write(ai / "MEMORY.md", simple_doc("memory", f"{project_name} Memory", "Stable repository-wide facts.", "# Memory\n\n- TODO: Add verified repository commands and invariants."))
    module_links = [f".ai/knowledge/{module['id']}/INDEX.md" for module in modules]
    ownership_rows = "\n".join(
        f"| `{module['id']}` | {', '.join(f'`{root}`' for root in module['source_roots'])} |"
        for module in modules
    )
    write(
        ai / "ARCHITECTURE.md",
        simple_doc(
            "architecture", f"{project_name} Architecture", "Structure-backed capability ownership.",
            "# Architecture\n\n| Capability | Ownership roots |\n| --- | --- |\n" + ownership_rows,
            related=module_links,
        ),
    )
    routing_rows = "\n".join(
        f"| `{module['id']}` | {', '.join(f'`{root}`' for root in module['source_roots'])} | `.ai/knowledge/{module['id']}/INDEX.md` |"
        for module in modules
    )
    write(
        knowledge / "INDEX.md",
        simple_doc(
            "knowledge-index", f"{project_name} Knowledge Index", "Routes capabilities to minimal knowledge documents.",
            "# Knowledge Index\n\n| Capability | Ownership roots | Route |\n| --- | --- | --- |\n" + routing_rows,
            related=module_links,
        ),
    )
    for filename, title, description in (
        ("glossary.md", "Glossary", "Repository terminology."),
        ("dependencies.md", "Dependencies", "Repository dependency and command facts."),
        ("decision_log.md", "Decision Log", "Verified architectural decisions."),
    ):
        write(knowledge / filename, simple_doc("shared-knowledge", title, description, f"# {title}\n\n- TODO: Add verified facts."))
    for module in modules:
        module_dir = knowledge / module["id"]
        write(module_dir / "INDEX.md", module_index(module))
        for filename in MODULE_DOCS:
            write(module_dir / filename, pending_leaf(module, filename))
    for filename in RUNTIME_TOOL_FILES:
        write(ai / "tools" / filename, (SCRIPT_DIR / filename).read_text(encoding="utf-8"))
    created.append(merge_bootstrap(repo, bootstrap))

    validator = ai / "tools" / "pkf_validate.py"
    completed = subprocess.run(
        (sys.executable, "-S", str(validator), "--path", str(repo), "--strictness", strictness, "--format", "json", "--detail", "summary"),
        cwd=repo,
        text=True,
        capture_output=True,
        check=False,
    )
    try:
        validation_result = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise ScaffoldError(f"generated runtime validation returned invalid JSON: {completed.stdout[-1000:].strip()}") from exc
    if completed.returncode != 0 or validation_result.get("status") == "failed":
        errors = validation_result.get("errors", [])
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
            summary = create_runtime(repo, spec_path, args.strictness, args.keep_spec)
        print(json.dumps(summary, indent=2, sort_keys=True))
        return 0
    except (OSError, json.JSONDecodeError, ScaffoldError) as exc:
        print(f"pkf_scaffold: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
