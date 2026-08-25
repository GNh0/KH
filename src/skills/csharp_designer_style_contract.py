"""PB-independent fixed style verification for C# WinForms/DevExpress artifacts.

The verifier intentionally reads only the two caller-supplied artifact receipts and
the packaged contract next to this module.  It does not search a project root,
source control, history, sibling projects, or author metadata.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


_REPO_ROOT = Path(__file__).resolve().parents[2]
PACKAGED_CONTRACT_PATH = (
    _REPO_ROOT / "skills" / "csharp_designer_style_harness" / "references" / "style-contract.json"
)

try:
    from src.contracts import HarnessResult
except ModuleNotFoundError:  # pragma: no cover - exercised by direct CLI invocation
    sys.path.insert(0, str(_REPO_ROOT))
    from src.contracts import HarnessResult


def _sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _sha256_label(value: str) -> str:
    text = str(value or "").strip().lower()
    return text if text.startswith("sha256:") else f"sha256:{text}"


def _valid_sha256(value: Any) -> bool:
    return bool(re.fullmatch(r"(?:sha256:)?[0-9a-fA-F]{64}", str(value or "").strip()))


def _json_safe(value: Any) -> Any:
    """Return a deterministic JSON-safe representation for evidence binding."""

    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if isinstance(value, (set, frozenset)):
        normalized = [_json_safe(item) for item in value]
        return sorted(
            normalized,
            key=lambda item: json.dumps(item, ensure_ascii=True, sort_keys=True, separators=(",", ":")),
        )
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return {"type": type(value).__qualname__, "value": str(value)}


def _stable_digest(value: Any) -> str:
    encoded = json.dumps(
        _json_safe(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256:{_sha256_bytes(encoded)}"


def _canonical_absolute_path(value: Any) -> tuple[Path | None, str]:
    if not isinstance(value, (str, Path)) or not str(value).strip():
        return None, "missing"
    supplied = Path(str(value).strip())
    if not supplied.is_absolute():
        return None, "relative"
    try:
        resolved = supplied.resolve(strict=False)
    except OSError:
        return None, "unresolvable"
    absolute = Path(os.path.abspath(str(supplied)))
    if os.path.normcase(str(absolute)) != os.path.normcase(str(resolved)):
        return None, "noncanonical"
    return resolved, "ok"


def load_packaged_style_contract() -> dict[str, Any]:
    """Load the one fixed contract shipped with this skill."""

    raw = PACKAGED_CONTRACT_PATH.read_bytes()
    return json.loads(raw.decode("utf-8"))


def packaged_style_contract_receipt() -> dict[str, str]:
    raw = PACKAGED_CONTRACT_PATH.read_bytes()
    return {
        "path": str(PACKAGED_CONTRACT_PATH.resolve()),
        "sha256": f"sha256:{_sha256_bytes(raw)}",
    }


def _issue(code: str, artifact: str, message: str, *, line: int | None = None, **extra: Any) -> dict[str, Any]:
    item: dict[str, Any] = {
        "code": code,
        "severity": "error",
        "artifact": artifact,
        "message": message,
    }
    if line is not None:
        item["line"] = line
    item.update(extra)
    return item


def _line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _mask_range(chars: list[str], text: str, start: int, end: int) -> None:
    for index in range(start, min(end, len(chars))):
        if text[index] not in "\r\n":
            chars[index] = " "


def _find_interpolation_close(
    text: str,
    start: int,
    limit: int,
    *,
    brace_count: int,
) -> int:
    """Find the first balanced interpolation close outside nested literals."""

    opening = "{" * brace_count
    closing = "}" * brace_count
    depth = 1
    index = start
    while index < limit:
        if text.startswith("//", index):
            newline = text.find("\n", index + 2, limit)
            index = limit if newline < 0 else newline + 1
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2, limit)
            index = limit if end < 0 else end + 2
            continue
        nested = _consume_csharp_literal(text, index)
        if nested is not None:
            index = nested[0]
            continue
        if text.startswith(opening, index):
            depth += 1
            index += brace_count
            continue
        if text.startswith(closing, index):
            depth -= 1
            if depth == 0:
                return index
            index += brace_count
            continue
        index += 1
    return limit


def _consume_csharp_literal(
    text: str,
    start: int,
) -> tuple[int, str, list[tuple[int, int]], bool] | None:
    """Return literal end/value and executable interpolation expression ranges."""

    length = len(text)
    index = start
    dollar_count = 0
    verbatim = False
    while index < length and text[index] in {"$", "@"}:
        if text[index] == "$":
            dollar_count += 1
        else:
            if verbatim:
                return None
            verbatim = True
        index += 1
    if index >= length or text[index] not in {'"', "'"}:
        return None
    quote = text[index]
    if quote == "'" and (dollar_count or verbatim):
        return None
    quote_start = index
    quote_count = 1
    while quote == '"' and index + quote_count < length and text[index + quote_count] == quote:
        quote_count += 1
    raw = quote == '"' and quote_count >= 3
    content_start = quote_start + (quote_count if raw else 1)
    delimiter = quote * (quote_count if raw else 1)
    index = content_start
    expressions: list[tuple[int, int]] = []
    literal_parts: list[str] = []
    literal_start = content_start
    brace_count = max(1, dollar_count) if raw else 1
    while index < length:
        if raw and text.startswith(delimiter, index):
            literal_parts.append(text[literal_start:index])
            return index + len(delimiter), "".join(literal_parts), expressions, bool(dollar_count)
        if not raw and verbatim and quote == '"' and text[index] == '"':
            if index + 1 < length and text[index + 1] == '"':
                index += 2
                continue
            literal_parts.append(text[literal_start:index])
            return index + 1, "".join(literal_parts), expressions, bool(dollar_count)
        if not raw and not verbatim and text[index] == "\\":
            index = min(index + 2, length)
            continue
        if not raw and not verbatim and text[index] == quote:
            literal_parts.append(text[literal_start:index])
            return index + 1, "".join(literal_parts), expressions, bool(dollar_count)
        opening = "{" * brace_count
        if dollar_count and text.startswith(opening, index):
            if not raw and text.startswith("{{", index):
                index += 2
                continue
            expression_start = index + brace_count
            expression_end = _find_interpolation_close(
                text,
                expression_start,
                length,
                brace_count=brace_count,
            )
            literal_parts.append(text[literal_start:index])
            expressions.append((expression_start, expression_end))
            index = min(length, expression_end + brace_count)
            literal_start = index
            continue
        if not raw and dollar_count and text.startswith("}}", index):
            index += 2
            continue
        index += 1
    literal_parts.append(text[literal_start:])
    return length, "".join(literal_parts), expressions, bool(dollar_count)


def _scan_csharp(text: str) -> tuple[str, list[tuple[str, str, int, int]]]:
    """Lex comments and literals without allowing their contents to act as code."""

    chars = list(text)
    tokens: list[tuple[str, str, int, int]] = []
    index = 0
    length = len(text)
    while index < length:
        if text.startswith("//", index):
            end = index + 2
            while end < length and text[end] not in "\r\n":
                end += 1
            _mask_range(chars, text, index, end)
            index = end
            continue
        if text.startswith("/*", index):
            end = text.find("*/", index + 2)
            end = length if end < 0 else end + 2
            _mask_range(chars, text, index, end)
            index = end
            continue
        literal = _consume_csharp_literal(text, index)
        if literal is not None:
            end, value, expressions, interpolated = literal
            tokens.append(("interpolated_string" if interpolated else "string", value, index, end))
            _mask_range(chars, text, index, end)
            for expression_start, expression_end in expressions:
                nested_code, nested_tokens = _scan_csharp(text[expression_start:expression_end])
                chars[expression_start:expression_end] = list(nested_code)
                tokens.extend(
                    (kind, value, start + expression_start, finish + expression_start)
                    for kind, value, start, finish in nested_tokens
                )
            index = end
            continue
        if text[index].isalpha() or text[index] == "_":
            end = index + 1
            while end < length and (text[end].isalnum() or text[end] == "_"):
                end += 1
            tokens.append(("identifier", text[index:end], index, end))
            index = end
            continue
        if not text[index].isspace():
            operator = next((candidate for candidate in ("+=", "-=", "=>", "?.", "??", "==", "!=", "<=", ">=") if text.startswith(candidate, index)), text[index])
            tokens.append(("symbol", operator, index, index + len(operator)))
            index += len(operator)
            continue
        index += 1
    tokens.sort(key=lambda item: (item[2], item[3]))
    return "".join(chars), tokens


def _strip_comments(text: str) -> str:
    return _scan_csharp(text)[0]


def _identifier_tokens(text: str) -> set[str]:
    return {value for kind, value, _, _ in _scan_csharp(text)[1] if kind == "identifier"}


def _normalized_identifier(value: str) -> str:
    return str(value or "").strip().removeprefix("@")


def _balanced_close(code: str, opening: int, open_char: str = "(", close_char: str = ")") -> int:
    depth = 0
    for index in range(opening, len(code)):
        if code[index] == open_char:
            depth += 1
        elif code[index] == close_char:
            depth -= 1
            if depth == 0:
                return index
    return -1


def _split_arguments(code: str) -> list[str]:
    parts: list[str] = []
    start = 0
    depth = 0
    masked = _strip_comments(code)
    for index, char in enumerate(masked):
        if char in "([{":
            depth += 1
        elif char in ")]}":
            depth = max(0, depth - 1)
        elif char == "," and depth == 0:
            parts.append(code[start:index].strip())
            start = index + 1
    tail = code[start:].strip()
    if tail or parts:
        parts.append(tail)
    return parts


def _method_declarations(text: str, name: str) -> list[re.Match[str]]:
    code = _strip_comments(text)
    modifiers = r"(?:public|private|protected|internal|static|async|virtual|override|sealed|new|unsafe|extern|partial|abstract)"
    return list(
        re.finditer(
            rf"(?m)^\s*(?:(?:{modifiers})\s+)+[A-Za-z_][A-Za-z0-9_.,<>\[\]?]*\s+@?{re.escape(name)}\s*\(",
            code,
        )
    )


def _method_calls(text: str, name: str) -> list[re.Match[str]]:
    code = _strip_comments(text)
    declarations = [(match.start(), match.end()) for match in _method_declarations(text, name)]
    calls: list[re.Match[str]] = []
    for match in re.finditer(rf"(?<![A-Za-z0-9_])(?:@?[A-Za-z_][A-Za-z0-9_]*\.)*@?{re.escape(name)}\s*\(", code):
        if not any(start <= match.start() < end for start, end in declarations):
            calls.append(match)
    return calls


def _called_string_arguments(text: str, method_names: Iterable[str]) -> set[str]:
    names = set(method_names)
    _, tokens = _scan_csharp(text)
    values: set[str] = set()
    for index, (_, value, _, _) in enumerate(tokens):
        if value not in names or index + 1 >= len(tokens) or tokens[index + 1][1] != "(":
            continue
        depth = 0
        arguments: list[list[tuple[str, str, int, int]]] = [[]]
        for token in tokens[index + 2 :]:
            if token[1] == "(":
                depth += 1
            elif token[1] == ")":
                if depth == 0:
                    break
                depth -= 1
            elif token[1] == "," and depth == 0:
                arguments.append([])
                continue
            arguments[-1].append(token)
        if arguments and len(arguments[0]) == 1 and arguments[0][0][0] == "string":
            values.add(arguments[0][0][1])
    return values


def _parameter_constructor_calls(text: str) -> list[tuple[str, str, int]]:
    """Return real DbParameter/SqlParameter constructor call sites."""

    _, tokens = _scan_csharp(text)
    calls: list[tuple[str, str, int]] = []
    for index, token in enumerate(tokens):
        if token[0] != "identifier" or token[1] != "new":
            continue
        cursor = index + 1
        type_name = ""
        while cursor < len(tokens) and tokens[cursor][0] == "identifier":
            type_name = tokens[cursor][1]
            cursor += 1
            if cursor < len(tokens) and tokens[cursor][1] == ".":
                cursor += 1
                continue
            break
        if type_name not in {"DbParameter", "SqlParameter"}:
            continue
        if cursor + 1 >= len(tokens) or tokens[cursor][1] != "(" or tokens[cursor + 1][0] != "string":
            continue
        calls.append((type_name, tokens[cursor + 1][1], token[2]))
    return calls


def _receipt(
    value: Any,
    supplied_sha256: str,
    role: str,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    if isinstance(value, Mapping):
        path_value = value.get("path") if "path" in value else value.get("artifact_path")
        path = str(path_value).strip() if isinstance(path_value, (str, Path)) else ""
        if path_value is not None and not isinstance(path_value, (str, Path)):
            issues.append(_issue("artifact_receipt_path_invalid", role, "Artifact receipt paths must be strings or Path values."))
        expected_value = next(
            (value[key] for key in ("sha256", "byte_sha256", "expected_sha256") if key in value),
            supplied_sha256,
        )
        expected = str(expected_value).strip() if isinstance(expected_value, (str, Path)) else ""
        if expected_value is not None and not isinstance(expected_value, (str, Path)):
            issues.append(_issue("artifact_receipt_sha256_invalid", role, "Artifact receipts must carry a string byte SHA-256."))
        provenance = value.get("provenance")
    else:
        path = str(value or "").strip()
        expected = str(supplied_sha256 or "").strip()
        provenance = None
    receipt = {
        "role": role,
        "path": path,
        "expected_sha256": _sha256_label(expected) if expected else "",
        "provenance": provenance,
    }
    if not path:
        issues.append(_issue("artifact_receipt_path_missing", role, "An exact artifact path is required."))
    else:
        canonical, path_status = _canonical_absolute_path(path)
        if canonical is None:
            code = "artifact_receipt_path_not_absolute" if path_status == "relative" else "artifact_receipt_path_not_canonical"
            issues.append(_issue(code, role, "Artifact receipt paths must be canonical absolute paths.", path=path, reason=path_status))
        else:
            receipt["path"] = str(canonical)
            if not canonical.is_file():
                issues.append(_issue("artifact_receipt_path_missing", role, "The exact artifact path is not an existing file.", path=str(canonical)))
    if not expected:
        issues.append(_issue("artifact_receipt_sha256_missing", role, "An exact byte SHA-256 receipt is required."))
    elif not _valid_sha256(expected):
        issues.append(_issue("artifact_receipt_sha256_invalid", role, "Artifact receipts must carry a valid byte SHA-256."))
    if provenance is not None:
        issues.append(
            _issue(
                "standalone_provenance_not_authoritative",
                role,
                "Standalone verification does not accept caller-supplied provenance or authentication material.",
            )
        )
    return receipt, issues


def _read_receipt(receipt: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    path = Path(receipt["path"]) if receipt.get("path") else Path(".")
    role = str(receipt.get("role") or "artifact")
    canonical, path_status = _canonical_absolute_path(path)
    if canonical is None:
        code = "artifact_receipt_path_not_absolute" if path_status == "relative" else "artifact_receipt_path_not_canonical"
        issues.append(_issue(code, role, "Artifact receipt paths must be canonical absolute paths.", path=str(path), reason=path_status))
        return "", issues
    path = canonical
    receipt["path"] = str(path)
    if not path.is_file():
        issues.append(_issue("artifact_missing", role, "The exact receipt path is not a file.", path=str(path)))
        return "", issues
    try:
        raw = path.read_bytes()
    except OSError as exc:
        issues.append(_issue("artifact_read_failed", role, f"The exact receipt path could not be read: {exc}"))
        return "", issues
    actual = f"sha256:{_sha256_bytes(raw)}"
    receipt["actual_sha256"] = actual
    receipt["byte_length"] = len(raw)
    if actual != receipt.get("expected_sha256"):
        issues.append(
            _issue(
                "artifact_sha256_mismatch",
                role,
                "The artifact bytes do not match the supplied SHA-256 receipt.",
                expected_sha256=receipt.get("expected_sha256"),
                actual_sha256=actual,
            )
        )
    try:
        return raw.decode("utf-8-sig"), issues
    except UnicodeDecodeError as exc:
        issues.append(_issue("artifact_utf8_decode_failed", role, f"The artifact is not UTF-8: {exc}"))
        return "", issues


def _allow_map(
    exceptions: Sequence[Mapping[str, Any]] | None,
) -> tuple[set[tuple[str, str]], list[dict[str, Any]]]:
    issues: list[dict[str, Any]] = []
    for item in exceptions or ():
        issues.append(
            _issue(
                "identity_exception_not_supported_standalone",
                "contract",
                "The standalone public verifier never authorizes identity exceptions.",
                exception=dict(item) if isinstance(item, Mapping) else str(item),
            )
        )
    return set(), issues


def _is_allowed(allowed: set[tuple[str, str]], scope: str, identity: str) -> bool:
    return (scope, identity) in allowed


def _matching_method_body(text: str, name: str) -> str:
    code = _strip_comments(text)
    for match in _method_declarations(text, name):
        opening = code.find("{", match.end())
        if opening < 0:
            continue
        closing = _balanced_close(code, opening, "{", "}")
        return text[opening : closing + 1 if closing >= 0 else len(text)]
    return ""


def _catch_bodies(text: str) -> list[str]:
    code = _strip_comments(text)
    bodies: list[str] = []
    for match in re.finditer(r"\bcatch\s*(?:\([^)]*\))?\s*\{", code):
        opening = code.find("{", match.start(), match.end())
        closing = _balanced_close(code, opening, "{", "}")
        bodies.append(text[opening : closing + 1 if closing >= 0 else len(text)])
    return bodies


def _property_assignments(text: str) -> dict[str, dict[str, tuple[str, int]]]:
    values: dict[str, dict[str, tuple[str, int]]] = {}
    code = _strip_comments(text)
    pattern = re.compile(
        r"\b(?:this\.)?(?P<member>[A-Za-z_][A-Za-z0-9_]*)\.(?P<property>BindingField|FieldName|DataPropertyName|TabIndex|VisibleIndex|Name)\s*=\s*(?P<value>\"[^\"]*\"|[-]?\d+)"
    )
    for match in pattern.finditer(text):
        if not any(char != " " for char in code[match.start() : match.end()] if char not in "\r\n"):
            continue
        value = match.group("value").strip('"')
        values.setdefault(match.group("member"), {})[match.group("property")] = (
            value,
            _line_number(text, match.start()),
        )
    return values


def _field_declarations(designer: str) -> dict[str, str]:
    code = _strip_comments(designer)
    pattern = re.compile(
        r"(?m)^\s*(?:(?:private|protected|internal|public|static|readonly|const)\s+)+(?P<type>[A-Za-z_][A-Za-z0-9_.<>,\[\]?]*)\s+@?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*(?:=\s*[^;]*)?;"
    )
    return {m.group("name"): m.group("type") for m in pattern.finditer(code)}


def _class_bases(text: str) -> dict[str, set[str]]:
    code = _strip_comments(text)
    result: dict[str, set[str]] = {}
    pattern = re.compile(r"\b(?:partial\s+)?class\s+@?(?P<class>[A-Za-z_][A-Za-z0-9_]*)\s*(?::\s*(?P<bases>[^\{]+))?")
    for match in pattern.finditer(code):
        raw_bases = match.group("bases") or ""
        bases = {part.strip().split(" where ", 1)[0].strip() for part in raw_bases.split(",") if part.strip()}
        result.setdefault(match.group("class"), set()).update(bases)
    return result


def _base_name(value: str) -> str:
    return _normalized_identifier(value.split("<", 1)[0].strip())


def _partial_class_names(text: str) -> set[str]:
    return {
        match.group("name")
        for match in re.finditer(
            r"\bpartial\s+class\s+@?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
            _strip_comments(text),
        )
    }


def _declared_class_names(text: str) -> set[str]:
    return set(_class_bases(text))


def _direct_declared_base(text: str, class_name: str) -> str:
    match = re.search(
        rf"\bpartial\s+class\s+@?{re.escape(class_name)}\s*(?::\s*(?P<bases>[^{{]+))?\{{",
        _strip_comments(text),
    )
    if not match or not match.group("bases"):
        return ""
    return _base_name(match.group("bases").split(",", 1)[0].strip())


def _using_aliases(text: str) -> set[str]:
    code = _strip_comments(text)
    return {
        _normalized_identifier(match.group("alias"))
        for match in re.finditer(
            r"(?m)^\s*(?:global\s+)?using\s+@?(?P<alias>[A-Za-z_][A-Za-z0-9_]*)\s*=",
            code,
        )
    }


def _type_chain_from_evidence(
    evidence: Any,
    issues: list[dict[str, Any]],
) -> dict[str, set[str]]:
    if evidence is None:
        return {}
    issues.append(
        _issue(
            "type_chain_evidence_not_supported_standalone",
            "contract",
            "The standalone public verifier does not trust caller-supplied type-chain evidence.",
        )
    )
    return {}


def _check_form_and_type_chain(
    source: str,
    designer: str,
    contract: Mapping[str, Any],
    allowed: set[tuple[str, str]],
    issues: list[dict[str, Any]],
    type_chain_evidence: Any = None,
) -> str:
    source_partials = _partial_class_names(source)
    designer_partials = _partial_class_names(designer)
    common = source_partials & designer_partials
    if len(common) != 1 or source_partials != designer_partials:
        issues.append(
            _issue(
                "partial_class_set_ambiguous",
                "contract",
                "Source and Designer must contain one identical partial surface class; decoy or unmatched partial classes are rejected.",
                source_classes=sorted(source_partials),
                designer_classes=sorted(designer_partials),
            )
        )
    if not common:
        issues.append(_issue("base_type_chain_missing", "source", "The partial form declaration must provide explicit base-type evidence."))
        return ""
    form_class = sorted(common)[0]
    source_base = _direct_declared_base(source, form_class)
    designer_base = _direct_declared_base(designer, form_class)
    if designer_base and source_base != designer_base:
        issues.append(
            _issue(
                "partial_base_type_mismatch",
                "contract",
                "Source and Designer cannot declare different direct base types.",
                source_base=source_base,
                designer_base=designer_base,
            )
        )
    accepted = set(contract.get("base_types", []))
    packaged_aliases = accepted & (_using_aliases(source) | _using_aliases(designer))
    for alias in sorted(packaged_aliases):
        issues.append(
            _issue(
                "packaged_base_type_aliased",
                "source",
                "A packaged base type name cannot be redefined through a using alias in supplied artifacts.",
                base_type=alias,
            )
        )
    binary_chains = _type_chain_from_evidence(type_chain_evidence, issues)
    def trusted_chain_reaches_packaged(type_name: str, seen: set[str] | None = None) -> bool:
        seen = set() if seen is None else seen
        if type_name in seen:
            return False
        seen.add(type_name)
        for base in binary_chains.get(type_name, set()):
            normalized = _base_name(base)
            if normalized in accepted:
                return True
            if normalized in binary_chains:
                if trusted_chain_reaches_packaged(normalized, seen):
                    return True
        return False

    local_classes = _declared_class_names(source) | _declared_class_names(designer)
    locally_shadowed = bool(source_base and source_base in local_classes and source_base != form_class)
    direct_packaged = source_base in accepted and not locally_shadowed and source_base not in packaged_aliases
    externally_proven = trusted_chain_reaches_packaged(source_base) if source_base else False
    if locally_shadowed:
        issues.append(
            _issue(
                "packaged_base_type_locally_shadowed",
                "source",
                "A local class declaration cannot establish packaged base-type authority.",
                base_type=source_base,
            )
        )
    if not source_base or not direct_packaged and not externally_proven:
        issues.append(_issue("base_type_not_packaged", "source", "The form base type is outside the packaged WinForms/KoneLib type chain.", observed=[source_base] if source_base else [], allowed=sorted(accepted)))
    if "InitializeComponent(" not in _strip_comments(source):
        issues.append(_issue("initialize_component_call_missing", "source", "Code-behind must call InitializeComponent()."))
    if not re.search(r"\b(?:void\s+)?InitializeComponent\s*\(", _strip_comments(designer)):
        issues.append(_issue("designer_initialize_component_missing", "designer", "Designer.cs must own InitializeComponent()."))
    return form_class


def _check_names(designer: str, declarations: Mapping[str, str], contract: Mapping[str, Any], allowed: set[tuple[str, str]], issues: list[dict[str, Any]]) -> None:
    forbidden = re.compile(r"\b(?:gridControl\d*|gridView\d*|gridColumn\d*|repositoryItem\w*|AddGridColumn|ConfigureColumn)\b")
    code = _strip_comments(designer)
    for match in forbidden.finditer(code):
        identity = match.group(0)
        if identity.startswith("col") and _is_allowed(allowed, "designer", identity):
            continue
        if identity in {"AddGridColumn", "ConfigureColumn"} or re.match(r"(?:gridControl|gridView|gridColumn|repositoryItem)", identity) or re.match(r"col[A-Za-z0-9]+$", identity):
            issues.append(_issue("noncanonical_designer_identity", "designer", "Static DevExpress members must use the packaged semantic naming grammar.", line=_line_number(designer, match.start()), identity=identity))
    for name, type_name in declarations.items():
        if name.startswith(("grd", "gvw")):
            prefix = "grid" if name.startswith("grd") else "view"
            if not re.fullmatch(r"(?:grd|gvw)[A-Z][A-Za-z0-9]*", name):
                issues.append(_issue("grid_view_name_noncanonical", "designer", "GridControl/GridView names must use grd<Role>/gvw<Role>.", identity=name))
        if "GridColumn" in type_name or name.startswith("col"):
            if not re.fullmatch(r"col[A-Z][A-Za-z0-9]*_[A-Z][A-Za-z0-9_]*", name) and not _is_allowed(allowed, "designer", name):
                issues.append(_issue("grid_column_name_noncanonical", "designer", "Grid columns must use col<Role>_<FIELD>.", identity=name))
        if "RepositoryItem" in type_name or name.startswith("rps"):
            if not re.fullmatch(r"rps(?:Spin|cbo|btn|chk)[A-Z][A-Za-z0-9_]*", name) and not _is_allowed(allowed, "designer", name):
                issues.append(_issue("repository_name_noncanonical", "designer", "Repository items must use a semantic rpsSpin/rpscbo/rpsbtn/rpschk identity.", identity=name))
        if name.startswith("grid") or name.startswith("repositoryItem"):
            issues.append(_issue("generic_control_identity_rejected", "designer", "Generic generated control identities are not accepted.", identity=name))


def _looks_designer_owned_type(type_name: str) -> bool:
    normalized = str(type_name or "").replace("global::", "").rstrip("?")
    short = normalized.rsplit(".", 1)[-1].split("<", 1)[0]
    if normalized.startswith(("DevExpress.", "System.Windows.Forms.")):
        return True
    if short in {
        "Component",
        "IComponent",
        "Control",
        "IContainer",
        "Container",
        "BackgroundWorker",
        "BindingSource",
        "ContextMenuStrip",
        "ErrorProvider",
        "FileSystemWatcher",
        "HelpProvider",
        "ImageList",
        "ToolTip",
        "Timer",
    }:
        return True
    return bool(
        re.search(
            r"(?:Control|View|Column|RepositoryItem|Edit|Button|Label|Panel|RadioGroup|CheckBox|ComboBox|ListBox|TreeList|PivotGrid|Chart|BarManager|LayoutControl|BindingSource|ImageList|Timer)$",
            short,
        )
    )


def _static_designer_property_chain(chain: str) -> bool:
    parts = [part for part in chain.split(".") if part]
    if not parts:
        return False
    direct = {
        "Name",
        "TabIndex",
        "Location",
        "Size",
        "Dock",
        "Anchor",
        "BindingField",
        "DataPropertyName",
        "FieldName",
        "VisibleIndex",
        "Caption",
        "Text",
        "MainView",
        "ColumnEdit",
        "Width",
        "MinWidth",
        "MaxWidth",
        "DisplayFormat",
        "EditFormat",
        "Mask",
        "NullText",
    }
    nested_prefixes = (
        "Appearance",
        "OptionsColumn",
        "OptionsView",
        "OptionsBehavior",
        "OptionsSelection",
        "OptionsFilter",
        "TextOptions",
        "Layout",
    )
    return parts[-1] in direct or any(part.startswith(nested_prefixes) for part in parts)


def _check_designer_contract(source: str, designer: str, declarations: Mapping[str, str], contract: Mapping[str, Any], allowed: set[tuple[str, str]], issues: list[dict[str, Any]]) -> None:
    source_code = _strip_comments(source)
    designer_code = _strip_comments(designer)
    for name, type_name in _field_declarations(source).items():
        if _looks_designer_owned_type(type_name):
            match = re.search(rf"\b{re.escape(name)}\b", source_code)
            issues.append(_issue("control_declaration_in_codebehind", "source", "Static control, column, or repository declarations must be Designer-owned.", line=_line_number(source, match.start()) if match else None, identity=name, type=type_name))
    static_source_patterns = {
        "control_creation_in_codebehind": r"\bthis\.[A-Za-z_][A-Za-z0-9_]*\s*=\s*new\s+[A-Za-z_][A-Za-z0-9_.<>]*\s*\(",
        "static_ui_assignment_in_codebehind": r"\bthis\.[A-Za-z_][A-Za-z0-9_]*\.(?:Name|TabIndex|Location|Size|Dock|Anchor|BindingField|FieldName|VisibleIndex|Caption|Text)\s*=",
        "grid_registration_in_codebehind": r"\.(?:Columns|RepositoryItems)\s*\.\s*Add(?:Range)?\s*\(",
        "column_edit_in_codebehind": r"\.ColumnEdit\s*=",
        "dynamic_ui_helper": r"\b(?:AddGridColumn|ConfigureColumn|ConfigureHiddenColumn|SetDetailGridColumns|CreateLabel|CreateCell|InitializeDetailTabs)\s*\(",
    }
    for code, pattern in static_source_patterns.items():
        match = re.search(pattern, source_code)
        if match:
            issues.append(_issue(code, "source", "Static controls, columns, repositories, and their properties belong in Designer.cs.", line=_line_number(source, match.start()), evidence=match.group(0)))
    for match in re.finditer(r"\bnew\s+(?P<type>[A-Za-z_][A-Za-z0-9_.<>]*)\s*\(", source_code):
        if _looks_designer_owned_type(match.group("type")):
            issues.append(_issue("grid_runtime_creation_in_codebehind", "source", "Designer-owned UI/component instances must be created in Designer.cs.", line=_line_number(source, match.start()), type=match.group("type")))
    reported_assignments: set[tuple[str, str, int]] = set()
    for match in re.finditer(
        r"\b(?:this\.)?(?P<member>[A-Za-z_][A-Za-z0-9_]*)(?P<chain>(?:\.[A-Za-z_][A-Za-z0-9_]*)+)\s*=",
        source_code,
    ):
        member = match.group("member")
        chain = match.group("chain").lstrip(".")
        if member in declarations and _looks_designer_owned_type(declarations[member]) and _static_designer_property_chain(chain):
            key = (member, chain, match.start())
            if key not in reported_assignments:
                reported_assignments.add(key)
                issues.append(_issue("static_ui_assignment_in_codebehind", "source", "Static control, column, repository, appearance, and layout properties must be Designer-owned.", line=_line_number(source, match.start()), identity=member, property=chain))
    for event_match in re.finditer(
        r"\b(?P<receiver>this|[A-Za-z_][A-Za-z0-9_]*)\.(?P<event>[A-Za-z_][A-Za-z0-9_]*)\s*\+=",
        source_code,
    ):
        receiver = event_match.group("receiver")
        designer_owned = receiver == "this" or (
            receiver in declarations and _looks_designer_owned_type(declarations[receiver])
        )
        if designer_owned:
            issues.append(_issue("codebehind_event_subscription", "source", "Events on Designer-owned controls/components must be wired in Designer.cs; non-UI worker events may remain in code-behind.", line=_line_number(source, event_match.start()), receiver=receiver, event=event_match.group("event")))
    assignments = _property_assignments(designer)
    input_names = tuple(contract.get("input_prefixes", []))
    input_tab_values: list[int] = []
    for name in declarations:
        if name.startswith(input_names):
            tab = assignments.get(name, {}).get("TabIndex")
            if not tab:
                issues.append(_issue("designer_tab_index_missing", "designer", "Every input control requires an explicit Designer TabIndex.", identity=name))
            else:
                input_tab_values.append(int(tab[0]))
            if name.startswith(("txt", "cbo", "Spin", "ymd", "Chk", "memo")) and not any(
                key in assignments.get(name, {}) for key in ("BindingField", "DataPropertyName")
            ):
                issues.append(_issue("designer_binding_missing", "designer", "Mapped input controls require an explicit BindingField or DataPropertyName.", identity=name))
    if input_tab_values and sorted(input_tab_values) != list(range(min(input_tab_values), max(input_tab_values) + 1)):
        issues.append(_issue("designer_tab_index_noncontiguous", "designer", "Input TabIndex values must be unique and contiguous within the supplied form." , values=sorted(input_tab_values)))
    for member, props in assignments.items():
        binding = next((props.get(k) for k in ("BindingField", "FieldName", "DataPropertyName") if props.get(k)), None)
        if not binding or not binding[0].strip():
            continue
        field = binding[0]
        if member.startswith("col") and "_" in member:
            expected = member.rsplit("_", 1)[1]
            if field.upper() != expected.upper() and not _is_allowed(allowed, "designer", member):
                issues.append(_issue("designer_field_name_mismatch", "designer", "GridColumn FieldName must match the semantic column identity.", line=binding[1], identity=member, field_name=field, expected=expected))
    columns = [name for name, type_name in declarations.items() if "GridColumn" in type_name or name.startswith("col")]
    for name in columns:
        props = assignments.get(name, {})
        if not any(key in props for key in ("FieldName", "BindingField", "DataPropertyName")):
            issues.append(_issue("designer_column_fieldname_missing", "designer", "Every static grid column requires an explicit FieldName assignment.", identity=name))
        if "VisibleIndex" not in props:
            issues.append(_issue("designer_column_visible_index_missing", "designer", "Every static grid column requires an explicit VisibleIndex assignment.", identity=name))
    if columns and not re.search(r"\.Columns\.AddRange\s*\(", designer_code):
        issues.append(_issue("designer_columns_addrange_missing", "designer", "Static grid columns must be registered by Designer Columns.AddRange."))
    if re.search(r"\b(?:grd[A-Z][A-Za-z0-9]*)\.MainView\s*=\s*(?:this\.)?gvw[A-Z][A-Za-z0-9]*", designer_code) is None and re.search(r"\.MainView\s*=", designer_code) is None:
        issues.append(_issue("designer_grid_view_wiring_missing", "designer", "Designer must wire each GridControl to its semantic GridView."))
    if re.search(r"\.RepositoryItems\.AddRange\s*\(", designer_code) and re.search(r"\.ColumnEdit\s*=", designer_code):
        if designer_code.find(".RepositoryItems.AddRange") > designer_code.find(".ColumnEdit ="):
            issues.append(_issue("designer_repository_order_invalid", "designer", "RepositoryItems must be registered before a column receives ColumnEdit."))


def _constructor_arguments(source: str, type_name: str) -> list[tuple[int, list[str]]]:
    _, tokens = _scan_csharp(source)
    results: list[tuple[int, list[str]]] = []
    for index, token in enumerate(tokens):
        if token[0] != "identifier" or token[1] != type_name:
            continue
        cursor = index - 1
        while cursor >= 1 and tokens[cursor][1] == "." and tokens[cursor - 1][0] == "identifier":
            cursor -= 2
        if cursor < 0 or tokens[cursor][1] != "new":
            continue
        if index + 1 >= len(tokens) or tokens[index + 1][1] != "(":
            continue
        depth = 0
        argument_tokens: list[list[tuple[str, str, int, int]]] = [[]]
        for token_index, current in enumerate(tokens[index + 1 :], start=index + 1):
            if token_index == index + 1:
                continue
            if current[1] == "(":
                depth += 1
                argument_tokens[-1].append(current)
                continue
            if current[1] == ")":
                if depth == 0:
                    break
                depth -= 1
                argument_tokens[-1].append(current)
                continue
            if current[1] == "," and depth == 0:
                argument_tokens.append([])
                continue
            argument_tokens[-1].append(current)
        values = [part[0][1] if len(part) == 1 and part[0][0] == "string" else "" for part in argument_tokens if part]
        results.append((token[2], values))
    return results


def _check_parameters(source: str, issues: list[dict[str, Any]]) -> None:
    for type_name in ("DbParameter", "SqlParameter"):
        for offset, arguments in _constructor_arguments(source, type_name):
            parameter = arguments[0] if arguments else ""
            line = _line_number(source, offset)
            issue_prefix = "db_parameter" if type_name == "DbParameter" else "sql_parameter"
            if not re.fullmatch(r"@[A-Z][A-Z0-9_]*", parameter):
                issues.append(_issue(f"{issue_prefix}_name_invalid", "source", f"{type_name} names must be literal uppercase @ identifiers.", line=line, parameter=parameter))
            if len(arguments) < 2:
                issues.append(_issue(f"{issue_prefix}_shape_invalid", "source", f"{type_name} construction must include a value or type argument after the parameter name.", line=line, parameter=parameter))
    code = _strip_comments(source)
    for match in re.finditer(r"\bParameterName\s*=\s*", code):
        literal = re.match(r"\s*(?:\$?@?\"([^\"]*)\"|'([^']*)')", source[match.end() :])
        parameter = (literal.group(1) if literal and literal.group(1) is not None else literal.group(2) if literal else "")
        if not re.fullmatch(r"@[A-Z][A-Z0-9_]*", parameter):
            issues.append(_issue("sql_parameter_name_invalid", "source", "ParameterName assignments must use literal uppercase @ identifiers.", line=_line_number(source, match.start()), parameter=parameter))


_SP_INVOCATION_METHODS = (
    "GetDataSetFromSP",
    "ExecSP",
    "ExecSPTrn",
    "ExecuteStoredProcedure",
    "ExecuteNonQuery",
    "CallStoredProcedure",
)
_APPROVED_DB_RECEIVERS = {"dbClient"}
_APPROVED_ERROR_RECEIVERS = {"logger", "_logger", "Log", "Trace", "MessageBox", "XtraMessageBox"}
_APPROVED_INHERITED_REPORTERS = {"ShowExcetion", "ShowException", "ShowMessageError", "LogError", "WriteError"}


def _locally_declared_names(text: str, candidates: Iterable[str]) -> set[str]:
    """Find normalized C# declarations that shadow authority-bearing names."""

    approved = {_normalized_identifier(name) for name in candidates}
    if not approved:
        return set()
    declared = set(_field_declarations(text)) & approved
    code = _strip_comments(text)
    names = "|".join(re.escape(name) for name in sorted(approved, key=len, reverse=True))
    modifiers = r"(?:public|private|protected|internal|static|readonly|const|sealed|abstract|partial|virtual|override|new|async|unsafe|extern)"
    type_name = r"(?:var|[A-Za-z_][A-Za-z0-9_.<>,\[\]?]*)"
    patterns = (
        rf"(?m)^\s*(?:(?:{modifiers})\s+)*(?!return\b|throw\b|new\b|await\b){type_name}\s+@?(?P<name>{names})\s*(?==|;|\{{|,|\))",
        rf"(?m)^\s*(?:(?:{modifiers})\s+)*(?!return\b|throw\b|new\b|await\b){type_name}\s+@?(?P<name>{names})\s*\(",
        rf"(?m)^\s*(?:(?:{modifiers})\s+)*delegate\s+{type_name}\s+@?(?P<name>{names})\s*\(",
        rf"\([^)]*\b{type_name}\s+@?(?P<name>{names})\s*(?=,|\))",
        rf"(?m)^\s*(?:global\s+)?using\s+@?(?P<name>{names})\s*=",
    )
    for pattern in patterns:
        declared.update(_normalized_identifier(match.group("name")) for match in re.finditer(pattern, code))
    return declared


def _locally_declared_approved_receivers(text: str) -> set[str]:
    return _locally_declared_names(text, _APPROVED_DB_RECEIVERS | _APPROVED_ERROR_RECEIVERS)


def _stored_procedure_invocations(text: str) -> list[tuple[str, str, int, int]]:
    """Return qualified runtime SP calls and their exact token spans."""

    _, tokens = _scan_csharp(text)
    shadowed = _locally_declared_approved_receivers(text)
    invocations: list[tuple[str, str, int, int]] = []
    for index, token in enumerate(tokens):
        if token[0] != "identifier" or token[1] not in _SP_INVOCATION_METHODS:
            continue
        if index < 2 or tokens[index - 1][1] != "." or tokens[index - 2][0] != "identifier":
            continue
        receiver = tokens[index - 2][1]
        if receiver not in _APPROVED_DB_RECEIVERS or receiver in shadowed:
            continue
        if index >= 4 and tokens[index - 3][1] == "." and tokens[index - 4][0] == "identifier":
            if tokens[index - 4][1] != "this":
                continue
        if index + 2 >= len(tokens) or tokens[index + 1][1] != "(" or tokens[index + 2][0] != "string":
            continue
        depth = 0
        end = token[3]
        for current in tokens[index + 1 :]:
            if current[1] == "(":
                depth += 1
            elif current[1] == ")":
                depth -= 1
                if depth == 0:
                    end = current[3]
                    break
        invocations.append((token[1], tokens[index + 2][1], token[2], end))
    return invocations


def _invocation_arguments(text: str, start: int, end: int) -> list[str]:
    code = _strip_comments(text)
    opening = code.find("(", start, end)
    if opening < 0:
        return []
    closing = _balanced_close(code, opening)
    if closing < 0 or closing > end:
        return []
    return _split_arguments(text[opening + 1 : closing])


def _parameter_variables_bound_to_invocation(
    method_body: str,
    invocation_start: int,
    invocation_end: int,
) -> set[str]:
    """Resolve variables whose last assignment before the exact call constructs a parameter."""

    arguments = _invocation_arguments(method_body, invocation_start, invocation_end)
    argument_names = {
        argument.strip()
        for argument in arguments[1:]
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", argument.strip())
    }
    if not argument_names:
        return set()
    before_call = _strip_comments(method_body[:invocation_start])
    bound: set[str] = set()
    for name in argument_names:
        assignments = list(
            re.finditer(
                rf"(?<![A-Za-z0-9_.])(?:(?:DbParameter|SqlParameter|var)\s+)?{re.escape(name)}\s*=\s*(?P<value>[^;]+);",
                before_call,
            )
        )
        if not assignments:
            continue
        last_value = assignments[-1].group("value").strip()
        if re.match(r"^new\s+(?:DbParameter|SqlParameter)\s*\(", last_value):
            bound.add(name)
    return bound


def _catch_reports_error(catch_body: str, source: str) -> bool:
    code = _strip_comments(catch_body)
    shadowed = _locally_declared_approved_receivers(source)
    shadowed_reporters = _locally_declared_names(source, _APPROVED_INHERITED_REPORTERS)
    if re.search(r"\bthrow\s*(?:;|[A-Za-z_(])", code):
        return True
    for reporter in sorted(_APPROVED_INHERITED_REPORTERS):
        if reporter in shadowed_reporters:
            continue
        if re.search(rf"(?<![A-Za-z0-9_.@])@?{re.escape(reporter)}\s*\(", code):
            return True
        if re.search(rf"\b(?:this|base)\.@?{re.escape(reporter)}\s*\(", code):
            return True
    for receiver in ("MessageBox", "XtraMessageBox"):
        if receiver not in shadowed and re.search(rf"\b{re.escape(receiver)}\.Show\s*\(", code):
            return True
    for receiver in ("logger", "_logger", "Log", "Trace"):
        if receiver not in shadowed and re.search(
            rf"\b{re.escape(receiver)}\.(?:Error|Fatal|LogError|WriteLine)\s*\(",
            code,
        ):
            return True
    return False


def _check_method_and_db_contract(source: str, contract: Mapping[str, Any], allowed: set[tuple[str, str]], issues: list[dict[str, Any]], applicable_operations: Iterable[str] | None = None) -> None:
    code = _strip_comments(source)
    shadowed_receivers = _locally_declared_approved_receivers(source)
    for receiver in sorted(shadowed_receivers):
        issues.append(
            _issue(
                "approved_receiver_locally_shadowed",
                "source",
                "A supplied source declaration cannot establish authority for an approved runtime receiver name.",
                identity=receiver,
            )
        )
    for reporter in sorted(_locally_declared_names(source, _APPROVED_INHERITED_REPORTERS)):
        issues.append(
            _issue(
                "approved_error_reporter_locally_shadowed",
                "source",
                "A local method, function, delegate, variable, or alias cannot establish inherited error-reporter authority.",
                identity=reporter,
            )
        )
    canonical_query = str(contract.get("query_method") or "CallSelectProcedure")
    canonical_save = str(contract.get("save_method") or "CallSaveProcedure")
    supplied_operations = None if applicable_operations is None else [str(item).strip().lower() for item in applicable_operations]
    operations = {"query", "save"} if supplied_operations is None else set(supplied_operations)
    invalid_operations = sorted(operation for operation in operations if operation not in {"query", "save"})
    if not operations or invalid_operations:
        issues.append(
            _issue(
                "applicable_operations_invalid",
                "contract",
                "Applicable operations must be a non-empty subset of query/save.",
                observed=sorted(operations),
                invalid=invalid_operations,
            )
        )
        operations &= {"query", "save"}
    for forbidden in contract.get("forbidden_methods", []):
        if (_method_declarations(source, str(forbidden)) or _method_calls(source, str(forbidden))) and not _is_allowed(allowed, "source", str(forbidden)):
            issues.append(_issue("noncanonical_method_family", "source", "Query/save calls must use the packaged canonical method family.", identity=str(forbidden), expected=[canonical_query, canonical_save]))
    required_methods = []
    if "query" in operations:
        required_methods.append((canonical_query, "query"))
    if "save" in operations:
        required_methods.append((canonical_save, "save"))
    for method, code_name in required_methods:
        declarations = _method_declarations(source, method)
        calls = _method_calls(source, method)
        if not declarations:
            issues.append(_issue("canonical_method_missing", "source", f"The applicable {code_name} method family is missing.", expected=method))
            continue
        if not calls:
            issues.append(_issue("canonical_method_call_missing", "source", f"The applicable {code_name} method must have an actual parsed call site.", expected=method))
        body = _matching_method_body(source, method)
        catches = _catch_bodies(body)
        if not re.search(r"\btry\b", _strip_comments(body)) or not catches:
            issues.append(_issue("exception_handling_missing", "source", f"{method} must contain explicit try/catch handling.", method=method))
        elif any(not _catch_reports_error(catch, source) for catch in catches):
            issues.append(_issue("catch_error_reporting_missing", "source", f"{method} catch blocks must call an approved error reporter or rethrow.", method=method))
        invocations = (
            []
            if shadowed_receivers & _APPROVED_DB_RECEIVERS
            else _stored_procedure_invocations(body)
        )
        procedures = {procedure for _call, procedure, _start, _end in invocations}
        if not procedures:
            issues.append(_issue("stored_procedure_invocation_missing", "source", f"{method} must contain an actual stored-procedure invocation with a literal procedure identity.", method=method))
        elif code_name == "query" and not any(re.search(r"_SELECT$", procedure, re.IGNORECASE) for procedure in procedures):
            issues.append(_issue("query_procedure_invocation_missing", "source", "The query wrapper must invoke an actual _SELECT procedure.", method=method, observed=sorted(procedures)))
        elif code_name == "save" and not any(re.search(r"_SAVE$", procedure, re.IGNORECASE) for procedure in procedures):
            issues.append(_issue("save_procedure_invocation_missing", "source", "The save wrapper must invoke an actual _SAVE procedure.", method=method, observed=sorted(procedures)))
        parameter_offsets = [
            offset
            for type_name in ("DbParameter", "SqlParameter")
            for offset, _arguments in _constructor_arguments(body, type_name)
        ]
        inline_parameters = any(
            start < offset < end
            for _call, _procedure, start, end in invocations
            for offset in parameter_offsets
        )
        variable_parameters = any(
            _parameter_variables_bound_to_invocation(body, start, end)
            for _call, _procedure, start, end in invocations
        )
        if not inline_parameters and not variable_parameters:
            issues.append(_issue("db_parameter_callsite_missing", "source", f"{method} must contain a real DbParameter or SqlParameter constructor call site.", method=method))
    if "query" in operations and not re.search(rf"\b{re.escape(canonical_query)}\s*\(\s*SelectType\.[A-Za-z_][A-Za-z0-9_]*", code):
        issues.append(_issue("query_call_shape_noncanonical", "source", "Query calls must pass a SelectType member through CallSelectProcedure."))
    if "save" in operations and not re.search(rf"\b{re.escape(canonical_save)}\s*\(\s*\)", code):
        issues.append(_issue("save_call_shape_noncanonical", "source", "The normal save path must use parameterless CallSaveProcedure()."))
    for _call, procedure, _start, _end in _stored_procedure_invocations(source):
        if not re.search(r"(?:_SELECT|_SAVE)$", procedure, re.IGNORECASE) and not _is_allowed(allowed, "source", procedure):
            issues.append(_issue("procedure_identity_noncanonical", "source", "Database procedure identities must end in _SELECT or _SAVE unless explicitly scoped with provenance.", identity=procedure))
    _check_parameters(source, issues)
    if re.search(r"\b(?:class\s+\w*(?:Dto|DTO|Request|Criteria|Wrapper)|\w+Wrapper\b|\b(?:Build|Create|Configure|SetDefault|ValidateSearch|GetEntityCodeLike)\w*\s*\()", code):
        issues.append(_issue("invented_helper_or_dto", "source", "Do not invent DTO, wrapper, generic helper, or runtime UI-builder styles outside the packaged contract."))
    for helper in contract.get("native_helpers", []):
        if re.search(rf"\b{re.escape(str(helper))}\s*\(", code) is None:
            continue
    if re.search(r"\b(?:DataRowToPanel|GridToPanel|dtMasterToDataTable|MasterToDataTable|Usr_ControlsProtect|InitControl)\s*\(", code):
        return


def _check_native_helpers(
    source: str,
    contract: Mapping[str, Any],
    available: Iterable[Any] | None,
    issues: list[dict[str, Any]],
) -> None:
    """Accept packaged helpers or local wrappers that call an unshadowed packaged helper."""

    packaged = {str(item).strip() for item in contract.get("native_helpers", []) if str(item).strip()}
    declarations = {match.group(1) for match in re.finditer(r"(?m)^\s*(?:public|private|protected|internal)\s+(?:static\s+)?[A-Za-z_][A-Za-z0-9_.<>\[\]?]*\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(", _strip_comments(source))}
    for item in available or ():
        if isinstance(item, Mapping):
            name = str(item.get("name") or "").strip()
            if item.get("provenance") is not None or item.get("authority") not in (None, "", "packaged"):
                issues.append(
                    _issue(
                        "native_helper_provenance_not_supported_standalone",
                        "source",
                        "Standalone verification does not accept caller-provided helper authority or provenance.",
                        identity=name,
                    )
                )
        else:
            name = str(item).strip()
        if not name:
            issues.append(_issue("native_helper_authority_missing", "source", "Native helper entries require an exact name and packaged/project authority."))
            continue
        delegates_to_packaged = False
        if name in declarations:
            body = _matching_method_body(source, name)
            delegates_to_packaged = any(
                packaged_name not in declarations and _method_calls(body, packaged_name)
                for packaged_name in packaged
            )
            if not delegates_to_packaged:
                issues.append(_issue("native_helper_self_declared", "source", "A code-behind declaration cannot establish native helper authority.", identity=name))
                continue
        if name not in packaged and not delegates_to_packaged:
            issues.append(_issue("native_helper_authority_missing", "source", "Clear/refresh helpers must be packaged or locally delegate to an unshadowed packaged helper.", identity=name))
            continue
        calls = [] if name in packaged and name in declarations else _method_calls(source, name)
        if not calls:
            issues.append(_issue("native_helper_not_reused", "source", "The authoritative clear/refresh helper must be called by the supplied source.", identity=name))


def _check_identity_expectations(source: str, designer: str, expected: Mapping[str, Any] | None, allowed: set[tuple[str, str]], issues: list[dict[str, Any]]) -> None:
    if not expected:
        return
    designer_fields = set(_field_declarations(designer))
    source_fields = set(_field_declarations(source))
    method_pattern = re.compile(
        r"(?m)^\s*(?:(?:public|private|protected|internal|static|async|virtual|override|sealed|new|unsafe|extern|partial|abstract)\s+)+"
        r"[A-Za-z_][A-Za-z0-9_.,<>\[\]?]*\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*\("
    )
    source_methods = {match.group("name") for match in method_pattern.finditer(_strip_comments(source))}
    procedure_calls = {
        procedure
        for _call, procedure, _start, _end in _stored_procedure_invocations(source)
    }
    for identity in expected.get("procedures", []):
        expected_identity = str(identity)
        if expected_identity not in procedure_calls and not _is_allowed(allowed, "source", expected_identity):
            issues.append(_issue("stale_or_missing_procedure_identity", "source", "Expected procedure identity is absent or stale.", identity=str(identity)))
    for identity in expected.get("controls", []):
        expected_identity = str(identity)
        if expected_identity not in designer_fields and not _is_allowed(allowed, "designer", expected_identity):
            issues.append(_issue("stale_or_missing_control_identity", "designer", "Expected control identity is absent or stale.", identity=str(identity)))
    for identity in expected.get("fields", []):
        expected_identity = str(identity)
        if expected_identity not in source_fields | designer_fields and not _is_allowed(allowed, "source", expected_identity):
            issues.append(_issue("stale_or_missing_field_identity", "source", "Expected field identity is not a real field declaration.", identity=expected_identity))
    for identity in expected.get("methods", []):
        expected_identity = str(identity)
        if expected_identity not in source_methods and not _is_allowed(allowed, "source", expected_identity):
            issues.append(_issue("stale_or_missing_method_identity", "source", "Expected method identity is not a real method declaration.", identity=expected_identity))


def _verify_csharp_designer_style(
    source_artifact: str | Path | Mapping[str, Any],
    designer_artifact: str | Path | Mapping[str, Any],
    *,
    source_sha256: str = "",
    designer_sha256: str = "",
    identity_exceptions: Sequence[Mapping[str, Any]] | None = None,
    expected_identities: Mapping[str, Any] | None = None,
    target_identities: Mapping[str, Any] | None = None,
    native_helpers: Iterable[Any] | None = None,
    applicable_operations: Iterable[str] | None = None,
    type_chain_evidence: Any = None,
    analysis_only: bool = True,
) -> HarnessResult:
    """Verify one exact source/Designer pair in fail-closed standalone mode."""

    issues: list[dict[str, Any]] = []
    contract: dict[str, Any] = {}
    normalized_operation_input = (
        None
        if applicable_operations is None
        else tuple(str(item).strip().lower() for item in applicable_operations)
    )
    identity_exception_values = tuple(identity_exceptions or ())
    if isinstance(native_helpers, (str, bytes)):
        native_helper_values: tuple[Any, ...] = (native_helpers,)
    else:
        native_helper_values = tuple(native_helpers or ())
    try:
        contract = load_packaged_style_contract()
        contract_receipt = packaged_style_contract_receipt()
    except (OSError, ValueError, TypeError) as exc:
        contract_receipt = {"path": str(PACKAGED_CONTRACT_PATH), "sha256": ""}
        issues.append(_issue("packaged_contract_load_failed", "contract", f"The packaged fixed contract could not be loaded: {exc}"))
    source, source_issues_receipt = _receipt(
        source_artifact,
        source_sha256,
        "source",
    )
    designer, designer_issues_receipt = _receipt(
        designer_artifact,
        designer_sha256,
        "designer",
    )
    issues.extend(source_issues_receipt)
    issues.extend(designer_issues_receipt)
    if source["path"] and designer["path"] and Path(source["path"]).resolve() == Path(designer["path"]).resolve():
        issues.append(_issue("artifact_paths_not_distinct", "contract", "Source and Designer receipts must identify distinct files."))
    source_text, source_read_issues = _read_receipt(source)
    designer_text, designer_read_issues = _read_receipt(designer)
    issues.extend(source_read_issues)
    issues.extend(designer_read_issues)
    allowed, exception_issues = _allow_map(identity_exception_values)
    issues.extend(exception_issues)
    if source_text and designer_text and not source_read_issues and not designer_read_issues:
        style = contract.get("style", {})
        form_class = _check_form_and_type_chain(
            source_text,
            designer_text,
            style,
            allowed,
            issues,
            type_chain_evidence,
        )
        declarations = _field_declarations(_strip_comments(designer_text))
        _check_names(designer_text, declarations, style, allowed, issues)
        _check_designer_contract(source_text, designer_text, declarations, style, allowed, issues)
        _check_method_and_db_contract(source_text, style, allowed, issues, normalized_operation_input)
        _check_native_helpers(
            source_text,
            style,
            native_helper_values,
            issues,
        )
        _check_identity_expectations(source_text, designer_text, target_identities or expected_identities, allowed, issues)
        if form_class and target_identities and target_identities.get("form_class"):
            expected_form = str(target_identities["form_class"])
            if form_class != expected_form and not _is_allowed(allowed, "source", expected_form):
                issues.append(_issue("form_identity_mismatch", "source", "The target form identity must be preserved exactly or explicitly scoped with provenance.", actual=form_class, expected=expected_form))
    source_hash = str(source.get("actual_sha256") or "")
    designer_hash = str(designer.get("actual_sha256") or "")
    contract_hash = str(contract_receipt.get("sha256") or "")
    operation_values = (
        ["query", "save"]
        if normalized_operation_input is None
        else sorted(set(normalized_operation_input))
    )
    status = "passed" if not issues else "blocked"
    success = not issues
    verification_binding = {
        "source_sha256": source_hash,
        "designer_sha256": designer_hash,
        "contract_sha256": contract_hash,
        "source_receipt_digest": _stable_digest(source),
        "designer_receipt_digest": _stable_digest(designer),
        "contract_receipt_digest": _stable_digest(contract_receipt),
        "applicable_operations_input": _json_safe(normalized_operation_input),
        "applicable_operations": operation_values,
        "expected_identities_digest": _stable_digest(expected_identities),
        "target_identities_digest": _stable_digest(target_identities),
        "native_helpers_digest": _stable_digest(native_helper_values),
        "type_chain_evidence_digest": _stable_digest(type_chain_evidence),
        "identity_exceptions_digest": _stable_digest(identity_exception_values),
        "analysis_only": bool(analysis_only),
        "success": success,
        "status": status,
        "issues_digest": _stable_digest(issues),
    }
    verification_id_payload = json.dumps(
        verification_binding,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    metadata = {
        "status": status,
        "verification_id": f"csharp-style-{_sha256_bytes(verification_id_payload)[:32]}",
        "verification_binding": verification_binding,
        "contract_id": contract.get("contract_id", ""),
        "contract_version": contract.get("contract_version", ""),
        "contract_sha256": contract_hash,
        "contract_receipt": contract_receipt,
        "source_receipt": source,
        "designer_receipt": designer,
        "issues": issues,
        "analysis_only": bool(analysis_only),
        "writes_performed": False,
        "discovery": {"root_search": False, "history_search": False, "author_discovery": False, "sibling_scan": False},
        "evidence_scope": "exact_source_and_designer_receipts_plus_packaged_contract",
        "applicable_operations": operation_values,
        "identity_exception_authority": "unsupported_standalone",
    }
    payload = {"status": metadata["status"], "issue_count": len(issues), "issues": issues}
    return HarnessResult(
        success=success,
        stdout=json.dumps(payload, ensure_ascii=False, sort_keys=True),
        stderr="" if success else "C# Designer style contract verification blocked.",
        exit_code=0 if success else 1,
        metadata=metadata,
    )


def verify_csharp_designer_style(
    source_artifact: str | Path | Mapping[str, Any],
    designer_artifact: str | Path | Mapping[str, Any],
    *,
    source_sha256: str = "",
    designer_sha256: str = "",
    identity_exceptions: Sequence[Mapping[str, Any]] | None = None,
    expected_identities: Mapping[str, Any] | None = None,
    target_identities: Mapping[str, Any] | None = None,
    native_helpers: Iterable[Any] | None = None,
    applicable_operations: Iterable[str] | None = None,
    type_chain_evidence: Any = None,
    analysis_only: bool = True,
) -> HarnessResult:
    """Strict public verifier with no caller-controlled authentication surface."""

    return _verify_csharp_designer_style(
        source_artifact,
        designer_artifact,
        source_sha256=source_sha256,
        designer_sha256=designer_sha256,
        identity_exceptions=identity_exceptions,
        expected_identities=expected_identities,
        target_identities=target_identities,
        native_helpers=native_helpers,
        applicable_operations=applicable_operations,
        type_chain_evidence=type_chain_evidence,
        analysis_only=analysis_only,
    )


def _main() -> int:
    parser = argparse.ArgumentParser(description="Verify a C# code-behind and Designer pair against the fixed packaged style contract.")
    parser.add_argument("--source", required=True)
    parser.add_argument("--designer", required=True)
    parser.add_argument("--source-sha256", required=True)
    parser.add_argument("--designer-sha256", required=True)
    parser.add_argument("--analysis-only", action="store_true", default=True)
    args = parser.parse_args()
    result = verify_csharp_designer_style(
        args.source,
        args.designer,
        source_sha256=args.source_sha256,
        designer_sha256=args.designer_sha256,
        analysis_only=args.analysis_only,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return result.exit_code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_main())
