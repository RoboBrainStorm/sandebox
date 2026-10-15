"""Introspect a model's input contract from its own repo — never hardcoded.

Statically (AST — no code execution, no model deps) parses the model's schemas.py
for its Pydantic input classes and reads its example_payload.json. Runs at build
time against the cloned repo; the result is stored on Model.input_schema and drives
the run-card field mapping.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def extract_model_document(repo_path: str, model_md_path: str | None = None) -> str:
    """Read a model card from inside the cloned repository.

    Leading slashes are treated as repository-relative for compatibility with
    older registration forms that used `/model.md`.
    """
    root = Path(repo_path).resolve()
    configured = (model_md_path or "./model.md").strip()
    relative = configured.lstrip("/")
    if not relative:
        raise ValueError("model_md_path must point to a Markdown file")

    candidate = (root / relative).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("model_md_path must stay inside the model repository") from exc

    if not candidate.is_file():
        raise ValueError(f"Required model documentation not found: {configured}")

    try:
        content = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise ValueError(f"Could not read model documentation: {configured}") from exc

    if not content.strip():
        raise ValueError(f"Model documentation is empty: {configured}")
    return content


def _is_pydantic_model(node: ast.ClassDef) -> bool:
    for base in node.bases:
        name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
        if name in ("BaseModel", "Schema"):
            return True
    return False


def _field(node: ast.AnnAssign) -> dict[str, Any] | None:
    if not isinstance(node.target, ast.Name):
        return None
    try:
        type_str = ast.unparse(node.annotation)
    except Exception:
        type_str = "Any"
    required = node.value is None or (
        isinstance(node.value, ast.Call)
        and any(
            isinstance(a, ast.Constant) and a.value is Ellipsis for a in node.value.args
        )
        or (isinstance(node.value, ast.Constant) and node.value.value is Ellipsis)
    )
    optional = type_str.startswith("Optional") or "| None" in type_str
    out: dict[str, Any] = {
        "name": node.target.id,
        "type": type_str,
        "required": bool(required) and not optional,
    }

    # Pull bounds/default/description from a Field(...) call so the run-card can
    # render a proper slider + question text (from the model's own constraints).
    if isinstance(node.value, ast.Call):
        for kw in node.value.keywords:
            val = kw.value.value if isinstance(kw.value, ast.Constant) else None
            if kw.arg in ("ge", "gt") and val is not None:
                out["min"] = val
            elif kw.arg in ("le", "lt") and val is not None:
                out["max"] = val
            elif kw.arg == "description" and isinstance(val, str):
                out["description"] = val
            elif kw.arg == "default" and val is not None:
                out["default"] = val
            elif kw.arg == "default_factory":
                factory_name = getattr(kw.value, "id", None) or getattr(
                    kw.value, "attr", None
                )
                if factory_name == "list":
                    out["default"] = []
                elif factory_name == "dict":
                    out["default"] = {}
                elif factory_name == "set":
                    out["default"] = []
    return out


def _parse_schemas(schemas_path: Path) -> dict[str, list[dict[str, Any]]]:
    try:
        tree = ast.parse(schemas_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("introspect.schemas_parse_failed", error=str(exc))
        return {}
    out: dict[str, list[dict[str, Any]]] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and _is_pydantic_model(node):
            fields = [
                f
                for stmt in node.body
                if isinstance(stmt, ast.AnnAssign) and (f := _field(stmt)) is not None
            ]
            if fields:
                out[node.name] = fields
    return out


def extract_input_schema(repo_path: str) -> dict[str, Any] | None:
    """Build the model's input contract from its repo files. None if nothing found."""
    root = Path(repo_path)
    result: dict[str, Any] = {}

    schemas = root / "schemas.py"
    if schemas.exists():
        models = _parse_schemas(schemas)
        if models:
            result["models"] = models
            # Heuristic: the *Input class is the input contract (prefer one literally
            # named with "Input"; else the first model).
            input_name = next(
                (n for n in models if n.lower().endswith("input")), next(iter(models))
            )
            result["input"] = {"name": input_name, "fields": models[input_name]}

    example = root / "example_payload.json"
    if example.exists():
        try:
            result["example"] = json.loads(example.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            pass

    # The dataset contract — required columns the model's data must have. Declared
    # in config.yaml so it's explicit and language-agnostic (the engine reads rows
    # positionally; this is what lets the platform validate a dataset fits).
    cfg = root / "config.yaml"
    if cfg.exists():
        try:
            import yaml

            data = yaml.safe_load(cfg.read_text(encoding="utf-8")) or {}
            if isinstance(data.get("dataset"), dict) and data["dataset"].get("columns"):
                result["dataset"] = data["dataset"]
        except Exception:  # noqa: BLE001
            pass

    return result or None


def validate_input_schema(schema: dict[str, Any] | None) -> list[str]:
    """Validate an introspected input contract. Returns problems (empty = OK).

    Only the **shape** is enforced as hard errors here (so registration fails fast
    on a malformed `dataset:` block); example↔contract mismatches are surfaced by
    `rb validate` locally. No `dataset` declared → nothing to validate.
    """
    if not schema:
        return []
    ds = schema.get("dataset")
    if ds is None:
        return []
    problems: list[str] = []
    if not isinstance(ds, dict):
        return ["config.yaml: `dataset` must be a mapping"]
    cols = ds.get("columns")
    if not isinstance(cols, list) or not cols:
        problems.append("config.yaml: `dataset.columns` must be a non-empty list")
        return problems
    for i, c in enumerate(cols):
        if not isinstance(c, dict) or not c.get("name"):
            problems.append(f"config.yaml: dataset.columns[{i}] needs a `name`")
    mr = ds.get("min_rows")
    if mr is not None and (not isinstance(mr, int) or mr < 1):
        problems.append("config.yaml: `dataset.min_rows` must be a positive integer")
    return problems


def example_satisfies_contract(schema: dict[str, Any] | None) -> list[str]:
    """Check the model's own example_payload.json against its dataset contract."""
    if not schema or not schema.get("dataset"):
        return []
    cols = (schema.get("example") or {}).get("data", {}).get("columns")
    if cols is None:
        return [
            "example_payload.json has no data.columns to check against the contract"
        ]
    have = {str(c).strip().lower() for c in cols}
    missing = [
        c["name"]
        for c in schema["dataset"]["columns"]
        if c.get("required", True) and str(c["name"]).strip().lower() not in have
    ]
    return [f"example_payload.json is missing required column '{m}'" for m in missing]
