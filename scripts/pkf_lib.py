"""Shared helpers for Token Atlas PKF tooling."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class PkfParseError(ValueError):
    """Invalid front matter or lightweight YAML."""


def read_front_matter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    body = parts[1]
    if not body.strip():
        return {}

    try:
        import yaml  # type: ignore
    except ImportError:
        lines = [line.rstrip() for line in body.splitlines() if line.strip()]
        value, _ = parse_yaml_block(lines, 0, 0, path)
    else:
        try:
            value = yaml.safe_load(body)
        except Exception as exc:  # pragma: no cover - exact PyYAML exceptions vary
            raise PkfParseError(f"{path}: invalid YAML front matter: {exc}") from exc

    if value is None:
        return {}
    if not isinstance(value, dict):
        raise PkfParseError(f"{path}: front matter root must be a mapping")
    return value


def parse_yaml_block(lines: list[str], index: int, indent: int, path: Path) -> tuple[Any, int]:
    if index >= len(lines):
        return {}, index
    current_indent = count_indent(lines[index])
    if current_indent < indent:
        return {}, index
    if lines[index].lstrip().startswith("- "):
        return parse_yaml_list(lines, index, current_indent, path)
    return parse_yaml_map(lines, index, current_indent, path)


def parse_yaml_map(lines: list[str], index: int, indent: int, path: Path) -> tuple[dict[str, Any], int]:
    result: dict[str, Any] = {}
    while index < len(lines):
        line = lines[index]
        current_indent = count_indent(line)
        if current_indent < indent:
            break
        if current_indent > indent:
            raise PkfParseError(f"{path}: unexpected indentation near '{line.strip()}'")
        stripped = line.strip()
        if stripped.startswith("- "):
            break
        if ":" not in stripped:
            raise PkfParseError(f"{path}: expected key/value line near '{stripped}'")
        key, raw_value = stripped.split(":", 1)
        key = key.strip()
        raw_value = raw_value.strip()
        if not key:
            raise PkfParseError(f"{path}: empty YAML key")
        if raw_value:
            result[key] = parse_yaml_scalar(raw_value)
            index += 1
        else:
            child, index = parse_yaml_block(lines, index + 1, indent + 2, path)
            result[key] = child
    return result, index


def parse_yaml_list(lines: list[str], index: int, indent: int, path: Path) -> tuple[list[Any], int]:
    result: list[Any] = []
    while index < len(lines):
        line = lines[index]
        current_indent = count_indent(line)
        if current_indent < indent:
            break
        if current_indent > indent:
            raise PkfParseError(f"{path}: unexpected indentation near '{line.strip()}'")
        stripped = line.strip()
        if not stripped.startswith("- "):
            break
        raw_value = stripped[2:].strip()
        if raw_value:
            result.append(parse_yaml_scalar(raw_value))
            index += 1
        else:
            child, index = parse_yaml_block(lines, index + 1, indent + 2, path)
            result.append(child)
    return result, index


def parse_yaml_scalar(value: str) -> Any:
    if value == "[]":
        return []
    if value == "{}":
        return {}
    if value in {"true", "false"}:
        return value == "true"
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [parse_yaml_scalar(item.strip()) for item in inner.split(",")]
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
        return value[1:-1]
    return value


def count_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def listify(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def markdown_body(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return text
    return parts[2]
