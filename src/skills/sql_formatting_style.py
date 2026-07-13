import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Sequence, Tuple

from src.contracts import HarnessResult


CONTRACT_VERSION = "2.0"
HOST_SQL_FORMATTING_SKILL = Path.home() / ".codex" / "skills" / "sql-formatting" / "SKILL.md"
POWERBUILDER_SQL_KEYWORD_PATTERN = re.compile(
    r"\b(SELECT|UPDATE|DELETE|INSERT|MERGE)\b",
    re.IGNORECASE,
)
_CLAUSE_WORDS = {
    "APPLY",
    "CROSS",
    "EXCEPT",
    "FULL",
    "GROUP",
    "HAVING",
    "INNER",
    "INTERSECT",
    "JOIN",
    "LEFT",
    "ON",
    "OPTION",
    "ORDER",
    "OUTER",
    "RIGHT",
    "UNION",
    "WHERE",
    "WHEN",
    "WITH",
}
_HASH_PATTERN = re.compile(r"^[0-9a-f]{64}$", re.IGNORECASE)


@dataclass(frozen=True)
class SqlFormattingIssue:
    code: str
    severity: str
    message: str
    evidence: List[str] = field(default_factory=list)
    check_kind: str = "mechanical"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "severity": self.severity,
            "message": self.message,
            "evidence": list(self.evidence),
            "check_kind": self.check_kind,
        }


@dataclass(frozen=True)
class _SqlInput:
    text: str
    evidence: Dict[str, Any]
    issues: List[SqlFormattingIssue]


@dataclass(frozen=True)
class _SqlToken:
    index: int
    kind: str
    text: str
    start: int
    end: int
    depth: int

    @property
    def normalized(self) -> str:
        if self.kind in {"string", "line_comment", "block_comment"}:
            return self.text
        if self.kind == "unicode_string":
            return "N" + self.text[1:]
        if self.kind == "batch_separator":
            return "<GO_BATCH>"
        if self.kind == "bracket_identifier":
            return "[" + self.text[1:-1].replace("]]", "]").upper() + "]"
        if self.kind == "quoted_identifier":
            return '"' + self.text[1:-1].replace('""', '"').upper() + '"'
        if self.kind == "word":
            return self.text.upper()
        return self.text


@dataclass(frozen=True)
class _SourceDeclaration:
    scope_id: str
    source: str
    base_source: str
    effective_alias: str
    source_start: int
    source_name_end: int
    source_end: int
    alias_start: int | None
    alias_end: int | None
    order: int


@dataclass(frozen=True)
class _SqlScope:
    scope_id: str
    start: int
    end: int
    depth: int
    declarations: Tuple[_SourceDeclaration, ...]


@dataclass(frozen=True)
class _AliasChange:
    scope_id: str
    source: str
    original_alias: str
    formatted_alias: str
    original: _SourceDeclaration
    formatted: _SourceDeclaration


def verify_sql_formatting_style(
    original_sql: str | bytes | os.PathLike[str],
    formatted_sql: str | bytes | os.PathLike[str],
    *,
    style_contract_path: str | os.PathLike[str] | None = None,
    cte_temp_table_reason: str | None = None,
    alias_role_plan: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None = None,
    scalar_function_refactor: Mapping[str, Any] | None = None,
    operation: str = "formatting",
) -> HarnessResult:
    """Return deterministic formatting evidence without inferring SQL semantics."""
    operation_name = str(operation or "formatting").strip().lower()
    operation_issues: List[SqlFormattingIssue] = []
    if operation_name not in {"formatting", "generation", "refactor"}:
        operation_issues.append(
            SqlFormattingIssue(
                code="invalid_operation",
                severity="error",
                message="operation must be 'formatting', 'generation', or 'refactor'.",
                evidence=[operation_name],
                check_kind="input",
            )
        )
        operation_name = "formatting"

    original_input = _load_sql_input(original_sql, "original")
    formatted_input = _load_sql_input(formatted_sql, "formatted")
    original = original_input.text
    formatted = formatted_input.text
    original_sha256 = _sha256_text(original)
    formatted_sha256 = _sha256_text(formatted)
    style_source = resolve_style_contract_source(style_contract_path)

    original_tokens, original_integrity = _analyze_sql_integrity(
        original,
        check_kind="input_integrity",
    )
    formatted_tokens, formatted_integrity = _analyze_sql_integrity(
        formatted,
        check_kind="formatter_output_integrity",
    )
    input_issues = [*original_input.issues, *original_integrity]
    output_issues = [*formatted_input.issues, *formatted_integrity]
    source_valid = not _has_errors(input_issues)
    output_valid = source_valid and not _has_errors(output_issues)

    original_scopes = _build_sql_scopes(original_tokens) if source_valid else []
    formatted_scopes = _build_sql_scopes(formatted_tokens) if output_valid else []
    alias_changes = _find_alias_changes(original_scopes, formatted_scopes)
    alias_metadata, alias_issues, alias_plan_valid = _validate_alias_role_plan(
        original_scopes,
        formatted_scopes,
        alias_changes,
        alias_role_plan,
    )

    preservation_issues: List[SqlFormattingIssue] = []
    preservation_metadata: Dict[str, Any] = {
        "status": "not_evaluated",
        "reason": "source_or_output_integrity_blocked",
        "token_count": {"original": len(original_tokens), "formatted": len(formatted_tokens)},
        "lexical_summary": _lexical_summary(original_tokens, formatted_tokens),
        "first_difference": {},
        "alias_substitutions": [],
        "scalar_refactor_boundary": {
            "status": "not_evaluated",
            "reason": "operation_is_not_a_convert_refactor",
        },
    }
    preservation_required = operation_name in {"formatting", "refactor"}
    if source_valid and output_valid and preservation_required:
        approved_changes = alias_changes if alias_plan_valid else []
        original_stream = _canonical_token_stream(original_tokens, original_scopes, approved_changes, "original")
        formatted_stream = _canonical_token_stream(formatted_tokens, formatted_scopes, approved_changes, "formatted")
        boundary_requested = (
            operation_name == "refactor"
            and isinstance(scalar_function_refactor, Mapping)
            and str(scalar_function_refactor.get("decision", "")).strip().lower() == "convert"
        )
        boundary_valid = False
        if boundary_requested:
            boundary_metadata, boundary_issues, boundary_original, boundary_formatted = (
                _validate_scalar_refactor_boundary(
                    original_tokens,
                    formatted_tokens,
                    original_scopes,
                    formatted_scopes,
                    approved_changes,
                    scalar_function_refactor,
                )
            )
            preservation_metadata["scalar_refactor_boundary"] = boundary_metadata
            preservation_issues.extend(boundary_issues)
            boundary_valid = boundary_metadata["status"] == "verified"
            if boundary_valid:
                original_stream = boundary_original
                formatted_stream = boundary_formatted

        if original_stream == formatted_stream and (not boundary_requested or boundary_valid):
            preservation_metadata.update(
                {
                    "status": "verified",
                    "reason": (
                        "parsed_scalar_refactor_boundary_match"
                        if boundary_valid
                        else "complete_token_stream_match"
                    ),
                    "alias_substitutions": [_alias_change_dict(item) for item in approved_changes],
                }
            )
        else:
            first_difference = _first_token_difference(original_stream, formatted_stream)
            preservation_metadata.update(
                {
                    "status": "changed",
                    "reason": "complete_token_stream_changed",
                    "first_difference": first_difference,
                    "alias_substitutions": [_alias_change_dict(item) for item in approved_changes],
                }
            )
            preservation_issues.append(
                SqlFormattingIssue(
                    code="token_stream_changed",
                    severity="error",
                    message=(
                        "The complete T-SQL token stream changed outside whitespace, safe case normalization, "
                        "or a verified alias substitution plan."
                    ),
                    evidence=_difference_evidence(first_difference),
                    check_kind="formatting_preservation",
                )
            )
            preservation_issues.extend(
                _preservation_diagnostics(
                    original_tokens,
                    formatted_tokens,
                    original_stream,
                    formatted_stream,
                    operation=operation_name,
                )
            )
    elif source_valid and output_valid:
        preservation_metadata.update(
            {
                "status": "not_evaluated",
                "reason": "generation_has_no_original_token_preservation_contract",
            }
        )

    style_issues = (
        _style_lint(
            original,
            formatted,
            formatted_tokens,
            operation=operation_name,
            cte_temp_table_reason=cte_temp_table_reason,
        )
        if source_valid and output_valid
        else []
    )
    style_metadata = {
        "status": "blocked" if _has_errors(style_issues) else "passed",
        "issues": [item.to_dict() for item in style_issues],
        "contract_source": style_source,
    }

    refactor_metadata, refactor_issues = _validate_scalar_function_refactor(
        scalar_function_refactor,
        operation=operation_name,
        original_sha256=original_sha256,
        formatted_sha256=formatted_sha256,
    )
    semantic_status = refactor_metadata["scalar_function_refactor"].get(
        "semantic_status",
        "not_proven",
    )

    effective_output_issues = output_issues if source_valid else []
    all_issues = [
        *operation_issues,
        *input_issues,
        *effective_output_issues,
        *preservation_issues,
        *style_issues,
        *alias_issues,
        *refactor_issues,
    ]
    mechanical_passed = not _has_errors(all_issues)
    refactor_state = refactor_metadata["scalar_function_refactor"]
    refactor_release_ready = (
        semantic_status == "proven"
        and refactor_state.get("execution_authentication") == "authenticated"
    )
    release_ready = mechanical_passed and (
        operation_name != "refactor" or refactor_release_ready
    )
    pending = mechanical_passed and operation_name == "refactor" and not release_ready
    result_status = "passed" if release_ready else ("pending" if pending else "blocked")
    verification_id = _verification_id(
        original_sha256=original_sha256,
        formatted_sha256=formatted_sha256,
        style_contract_sha256=style_source["sha256"],
        operation=operation_name,
        alias_role_plan=alias_role_plan,
        scalar_function_refactor=scalar_function_refactor,
        cte_temp_table_reason=cte_temp_table_reason,
    )

    metadata = {
        "harness": "sql-formatting-style-harness",
        "contract_version": CONTRACT_VERSION,
        "operation": operation_name,
        "original_sha256": original_sha256,
        "formatted_sha256": formatted_sha256,
        "style_contract_sha256": style_source["sha256"],
        "style_contract_source": style_source,
        "verification_id": verification_id,
        "encoding_evidence": {
            "original": original_input.evidence,
            "formatted": formatted_input.evidence,
        },
        "input_integrity": {
            "status": "valid" if source_valid else "source_invalid",
            "issues": [item.to_dict() for item in input_issues],
        },
        "formatter_output_integrity": {
            "status": "not_evaluated" if not source_valid else ("valid" if output_valid else "damaged"),
            "formatter_caused": bool(source_valid and _has_errors(output_issues)),
            "issues": [item.to_dict() for item in effective_output_issues],
            "reason": "source SQL must be valid first" if not source_valid else "",
        },
        "formatting_preservation": preservation_metadata,
        "style_lint": style_metadata,
        "alias_role_plan_validation": alias_metadata,
        "semantic_refactor_evidence": refactor_metadata,
        "semantic_checks": {
            "status": semantic_status,
            "reason": "Python validates evidence shape and correlation only; database semantics are not proven.",
            "requires": [
                "authoritative scalar-function definition",
                "pure deterministic lookup analysis",
                "cardinality and unmatched-row proof",
                "trusted execution authenticated outside caller-supplied metadata",
            ],
        },
        "release_readiness": {
            "status": "ready" if release_ready else ("pending" if pending else "blocked"),
            "reason": (
                "formatting_verification_completed"
                if release_ready and operation_name != "refactor"
                else (
                    "authenticated_runtime_semantic_execution_required"
                    if pending
                    else "mechanical_or_evidence_gate_blocked"
                )
            ),
            "requires": (
                []
                if operation_name != "refactor"
                else [
                    "semantic_checks.status=proven",
                    "execution_authentication=authenticated",
                ]
            ),
        },
        "mechanical_checks": {
            "status": "passed" if mechanical_passed else "blocked",
            "input_issues": [item.to_dict() for item in input_issues],
            "output_integrity_issues": [item.to_dict() for item in effective_output_issues],
            "preservation_issues": [item.to_dict() for item in preservation_issues],
            "style_issues": [item.to_dict() for item in [*style_issues, *alias_issues, *refactor_issues]],
            "structural_preservation": preservation_metadata,
            "proof_status": (
                "mechanically_proven"
                if mechanical_passed and operation_name == "formatting"
                else "not_proven"
            ),
        },
        "mechanical_equivalence": {
            "status": (
                "verified"
                if mechanical_passed
                and operation_name == "formatting"
                and preservation_metadata["status"] == "verified"
                else "not_proven"
            ),
            "scope": "Complete lexer token stream with verified per-scope alias substitutions only.",
            "does_not_prove": "database semantic equivalence",
        },
        "alias_role_verification": alias_metadata,
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": (
            "SQL, literals, comments, and evidence were preserved without lossy compression."
        ),
        "not_used_reason": "Contract-sensitive SQL evidence requires passthrough.",
        "cte_temp_table_reason": cte_temp_table_reason or "",
    }
    return HarnessResult(
        success=release_ready,
        stdout=json.dumps(
            {
                "status": result_status,
                "mechanical_status": (
                    "mechanically_valid" if mechanical_passed else "blocked"
                ),
                "issue_count": len(all_issues),
                "error_count": sum(item.severity == "error" for item in all_issues),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        stderr=(
            ""
            if release_ready
            else (
                "SQL refactor verification remains pending authenticated runtime semantic execution."
                if pending
                else "SQL formatting verification blocked by deterministic evidence gates."
            )
        ),
        exit_code=0 if release_ready else 1,
        metadata=metadata,
    )


def extract_powerbuilder_sql_fragments(
    source_text: str,
    *,
    source_name: str = "",
    max_lines_per_fragment: int = 80,
) -> List[Dict[str, Any]]:
    """Extract bounded SQL-looking fragments from exported PowerBuilder source text."""
    lines = str(source_text or "").splitlines()
    fragments: List[Dict[str, Any]] = []
    index = 0
    while index < len(lines):
        match = POWERBUILDER_SQL_KEYWORD_PATTERN.search(lines[index])
        if not match:
            index += 1
            continue
        start = index
        end = min(len(lines) - 1, start + max_lines_per_fragment - 1)
        for cursor in range(start, end + 1):
            if ";" in lines[cursor]:
                end = cursor
                break
            if cursor > start and not lines[cursor].strip():
                end = cursor - 1
                break
        sql_text = "\n".join(lines[start : end + 1]).strip()
        fragments.append(
            {
                "fragment_id": f"{Path(source_name).name or 'powerbuilder'}:{start + 1}:{match.group(1).upper()}",
                "source_name": source_name,
                "keyword": match.group(1).upper(),
                "start_line": start + 1,
                "end_line": end + 1,
                "sql_text": sql_text,
                "token_optimizer_status": "passthrough",
                "token_optimizer_status_reason": "SQL source text was not compressed.",
            }
        )
        index = end + 1
    return fragments


def build_powerbuilder_sql_validation_plan(
    *,
    pbl_root: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    pblscripter_path: str | os.PathLike[str] | None = None,
) -> Dict[str, Any]:
    """Return a bounded no-write-to-source validation plan for PB-exported SQL."""
    export_dir = Path(output_dir) / "powerbuilder_export"
    fragments_dir = Path(output_dir) / "sql_fragments"
    guard = validate_powerbuilder_output_dir(source_root=pbl_root, output_dir=output_dir)
    export_tool = str(pblscripter_path or "").strip()
    export_provider = "caller_supplied" if export_tool else "standalone"
    export_step = (
        "Export approved objects with the caller-supplied tool under output_dir/powerbuilder_export."
        if export_tool
        else "Use PB migration harness extraction or already-exported PB source; no local export tool is assumed."
    )
    return {
        "status": "planned" if guard["allowed"] else "blocked",
        "pbl_root": str(pbl_root),
        "pblscripter_path": export_tool,
        "export_provider": export_provider,
        "output_dir": str(output_dir),
        "output_guard": guard,
        "write_boundary": {
            "allowed": [str(export_dir), str(fragments_dir)],
            "forbidden": [str(pbl_root)],
            "policy": "Exports and fragments go under output_dir only.",
        },
        "steps": [
            "Resolve PB extraction paths from caller configuration or the PB migration harness.",
            export_step,
            "Extract bounded SQL fragments under output_dir/sql_fragments.",
            "Format each fragment with the selected host contract.",
            "Verify each exact original/formatted pair with verify_sql_formatting_style.",
            "Report blocked fragments; do not claim DB semantics from deterministic checks.",
        ],
        "current_pass_scope": "bounded hook and fixture tests only",
    }


def validate_powerbuilder_output_dir(
    *,
    source_root: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
) -> Dict[str, Any]:
    source = Path(source_root).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    forbidden_roots = [source]
    violations = [str(root) for root in forbidden_roots if _path_is_relative_to(output, root)]
    return {
        "allowed": not violations,
        "source_root": str(source),
        "output_dir": str(output),
        "forbidden_roots": [str(root) for root in forbidden_roots],
        "violations": violations,
        "policy": "output_dir must be outside source_root before writes",
    }


def resolve_style_contract_source(
    style_contract_path: str | os.PathLike[str] | None = None,
) -> Dict[str, Any]:
    candidates: List[Tuple[str, Path]] = []
    if style_contract_path:
        candidates.append(("explicit-style-contract", Path(style_contract_path).expanduser()))
    candidates.append(
        (
            "host-local-sql-formatting-skill",
            Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex")))
            / "skills"
            / "sql-formatting"
            / "SKILL.md",
        )
    )
    candidates.append(("host-local-sql-formatting-skill", HOST_SQL_FORMATTING_SKILL))
    candidates.append(
        (
            "packaged-fallback-reference",
            Path(__file__).resolve().parents[2]
            / "skills"
            / "sql_formatting_style_harness"
            / "references"
            / "style-contract.md",
        )
    )
    seen = set()
    for kind, path in candidates:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            return {
                "kind": kind,
                "path": str(path),
                "sha256": _sha256(path),
                "available": True,
                "contract_role": "provenance_only",
                "enforcement_profile": "built_in_python_checks",
            }
    kind, path = candidates[-1]
    return {
        "kind": kind,
        "path": str(path),
        "sha256": "",
        "available": False,
        "contract_role": "provenance_only",
        "enforcement_profile": "built_in_python_checks",
    }


def _load_sql_input(value: str | bytes | os.PathLike[str], label: str) -> _SqlInput:
    source_kind = "string"
    path_value = ""
    raw: bytes | None = None
    if isinstance(value, (bytes, bytearray)):
        source_kind = "bytes"
        raw = bytes(value)
    elif isinstance(value, os.PathLike):
        source_kind = "path"
        path = Path(value)
        path_value = str(path)
        try:
            raw = path.read_bytes()
        except OSError as exc:
            issue = SqlFormattingIssue(
                code="sql_input_read_failed",
                severity="error",
                message=f"Could not read {label} SQL path.",
                evidence=[path_value, str(exc)],
                check_kind="encoding",
            )
            return _SqlInput(
                text="",
                evidence={
                    "status": "unverified",
                    "source_kind": source_kind,
                    "path": path_value,
                    "encoding": "utf-8",
                    "raw_sha256": "",
                },
                issues=[issue],
            )
    else:
        text = str(value or "")
        return _SqlInput(
            text=text,
            evidence={
                "status": "encoding_unverified",
                "source_kind": source_kind,
                "path": "",
                "encoding": "",
                "raw_sha256": "",
                "text_sha256": _sha256_text(text),
                "reason": "Python str does not retain source-file encoding evidence.",
            },
            issues=[],
        )

    assert raw is not None
    try:
        text = raw.decode("utf-8-sig", errors="strict")
        issues: List[SqlFormattingIssue] = []
        status = "verified"
    except UnicodeDecodeError as exc:
        text = raw.decode("utf-8", errors="replace")
        issues = [
            SqlFormattingIssue(
                code="invalid_utf8",
                severity="error",
                message=f"{label} SQL bytes are not valid UTF-8.",
                evidence=[f"offset={exc.start}", source_kind, path_value],
                check_kind="encoding",
            )
        ]
        status = "invalid"
    return _SqlInput(
        text=text,
        evidence={
            "status": status,
            "source_kind": source_kind,
            "path": path_value,
            "encoding": "utf-8",
            "raw_sha256": hashlib.sha256(raw).hexdigest(),
            "text_sha256": _sha256_text(text),
        },
        issues=issues,
    )


def _scan_sql_tokens(sql: str) -> Tuple[List[_SqlToken], List[Tuple[str, str, str]]]:
    tokens: List[_SqlToken] = []
    issues: List[Tuple[str, str, str]] = []
    index = 0
    depth = 0
    open_parentheses: List[int] = []

    def emit(kind: str, text: str, start: int, end: int, token_depth: int | None = None) -> None:
        tokens.append(
            _SqlToken(
                index=len(tokens),
                kind=kind,
                text=text,
                start=start,
                end=end,
                depth=depth if token_depth is None else token_depth,
            )
        )

    while index < len(sql):
        char = sql[index]
        pair = sql[index : index + 2]
        if char.isspace():
            index += 1
            continue
        if pair == "--":
            start = index
            newline = sql.find("\n", index + 2)
            index = len(sql) if newline < 0 else newline
            emit("line_comment", sql[start:index], start, index)
            continue
        if pair == "/*":
            start = index
            nesting = 1
            index += 2
            while index < len(sql) and nesting:
                current = sql[index : index + 2]
                if current == "/*":
                    nesting += 1
                    index += 2
                elif current == "*/":
                    nesting -= 1
                    index += 2
                else:
                    index += 1
            emit("block_comment", sql[start:index], start, index)
            if nesting:
                issues.append(
                    (
                        "unclosed_block_comment",
                        "SQL contains a block comment without a closing */ marker.",
                        f"offset={start}",
                    )
                )
            continue
        if char in "Nn" and index + 1 < len(sql) and sql[index + 1] == "'":
            start = index
            index += 2
            closed = False
            while index < len(sql):
                if sql[index] == "'":
                    if index + 1 < len(sql) and sql[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    closed = True
                    break
                index += 1
            emit("unicode_string", sql[start:index], start, index)
            if not closed:
                issues.append(
                    (
                        "unclosed_string_literal",
                        "SQL contains a string literal without a closing quote.",
                        f"offset={start}",
                    )
                )
            continue
        if char == "'":
            start = index
            index += 1
            closed = False
            while index < len(sql):
                if sql[index] == "'":
                    if index + 1 < len(sql) and sql[index + 1] == "'":
                        index += 2
                        continue
                    index += 1
                    closed = True
                    break
                index += 1
            emit("string", sql[start:index], start, index)
            if not closed:
                issues.append(
                    (
                        "unclosed_string_literal",
                        "SQL contains a string literal without a closing quote.",
                        f"offset={start}",
                    )
                )
            continue
        if char == "[":
            start = index
            index += 1
            closed = False
            while index < len(sql):
                if sql[index] == "]":
                    if index + 1 < len(sql) and sql[index + 1] == "]":
                        index += 2
                        continue
                    index += 1
                    closed = True
                    break
                index += 1
            emit("bracket_identifier", sql[start:index], start, index)
            if not closed:
                issues.append(
                    (
                        "unclosed_bracket_identifier",
                        "SQL contains a bracketed identifier without a closing ].",
                        f"offset={start}",
                    )
                )
            continue
        if char == '"':
            start = index
            index += 1
            closed = False
            while index < len(sql):
                if sql[index] == '"':
                    if index + 1 < len(sql) and sql[index + 1] == '"':
                        index += 2
                        continue
                    index += 1
                    closed = True
                    break
                index += 1
            emit("quoted_identifier", sql[start:index], start, index)
            if not closed:
                issues.append(
                    (
                        "unclosed_quoted_identifier",
                        "SQL contains a quoted identifier without a closing quote.",
                        f"offset={start}",
                    )
                )
            continue
        if char == "(":
            emit("symbol", char, index, index + 1)
            open_parentheses.append(index)
            depth += 1
            index += 1
            continue
        if char == ")":
            if open_parentheses:
                open_parentheses.pop()
                depth -= 1
                emit("symbol", char, index, index + 1, depth)
            else:
                emit("symbol", char, index, index + 1, 0)
                issues.append(
                    (
                        "unbalanced_parentheses",
                        "SQL contains an unmatched closing parenthesis.",
                        f"offset={index}",
                    )
                )
            index += 1
            continue
        if char.isalpha() or char in "_@#$" or ord(char) > 127:
            start = index
            index += 1
            while index < len(sql) and (
                sql[index].isalnum() or sql[index] in "_@#$" or ord(sql[index]) > 127
            ):
                index += 1
            text = sql[start:index]
            line_start = sql.rfind("\n", 0, start) + 1
            line_end = sql.find("\n", index)
            if line_end < 0:
                line_end = len(sql)
            line = sql[line_start:line_end]
            kind = (
                "batch_separator"
                if text.upper() == "GO"
                and re.fullmatch(r"\s*GO(?:\s+\d+)?(?:\s*--[^\r\n]*)?\s*", line, re.IGNORECASE)
                else "word"
            )
            emit(kind, text, start, index)
            continue
        if char.isdigit():
            start = index
            index += 1
            while index < len(sql) and (sql[index].isalnum() or sql[index] in "._"):
                index += 1
            emit("number", sql[start:index], start, index)
            continue
        if pair in {"<=", ">=", "<>", "!=", "!<", "!>", "+=", "-=", "*=", "/=", "%=", "::"}:
            emit("symbol", pair, index, index + 2)
            index += 2
            continue
        emit("symbol", char, index, index + 1)
        index += 1

    if open_parentheses:
        issues.append(
            (
                "unbalanced_parentheses",
                "SQL contains one or more unclosed opening parentheses.",
                "offsets=" + ",".join(str(value) for value in open_parentheses[:8]),
            )
        )
    return tokens, issues


def _analyze_sql_integrity(
    sql: str,
    *,
    check_kind: str,
) -> Tuple[List[_SqlToken], List[SqlFormattingIssue]]:
    tokens, records = _scan_sql_tokens(sql)
    issues = []
    for code, message, evidence in records:
        output_code = (
            "unterminated_string_literal"
            if check_kind == "formatter_output_integrity" and code == "unclosed_string_literal"
            else code
        )
        issues.append(
            SqlFormattingIssue(
                code=output_code,
                severity="error",
                message=message,
                evidence=[evidence],
                check_kind=check_kind,
            )
        )
    if not records:
        code_tokens = [item for item in tokens if item.kind not in {"line_comment", "block_comment"}]
        for position, token in enumerate(code_tokens):
            if token.normalized != "SELECT":
                continue
            for cursor in range(position + 1, len(code_tokens)):
                candidate = code_tokens[cursor]
                if candidate.depth < token.depth:
                    break
                if candidate.depth == token.depth and candidate.normalized in {";", "UNION", "EXCEPT", "INTERSECT", "END"}:
                    break
                if candidate.depth == token.depth and candidate.normalized == "FROM":
                    previous = code_tokens[cursor - 1] if cursor > position + 1 else None
                    if previous and previous.text == ",":
                        issues.append(
                            SqlFormattingIssue(
                                code="dangling_select_comma",
                                severity="error",
                                message="SELECT projection has a dangling comma before FROM.",
                                evidence=[f"offset={previous.start}"],
                                check_kind=check_kind,
                            )
                        )
                    break
    return tokens, issues


def _build_sql_scopes(tokens: Sequence[_SqlToken]) -> List[_SqlScope]:
    code_indices = [
        item.index
        for item in tokens
        if item.kind not in {"line_comment", "block_comment"} and item.normalized == "SELECT"
    ]
    scopes: List[_SqlScope] = []
    for ordinal, start in enumerate(code_indices, start=1):
        depth = tokens[start].depth
        end = len(tokens)
        for cursor in range(start + 1, len(tokens)):
            token = tokens[cursor]
            if token.depth < depth:
                end = cursor
                break
            if token.depth == depth and token.normalized == ";":
                end = cursor + 1
                break
            if token.depth == depth and token.normalized == "SELECT" and cursor in code_indices:
                end = cursor
                break
        scope_id = f"scope_{ordinal}"
        declarations = _parse_scope_declarations(tokens, scope_id, start, end, depth)
        scopes.append(
            _SqlScope(
                scope_id=scope_id,
                start=start,
                end=end,
                depth=depth,
                declarations=tuple(declarations),
            )
        )
    return scopes


def _parse_scope_declarations(
    tokens: Sequence[_SqlToken],
    scope_id: str,
    start: int,
    end: int,
    depth: int,
) -> List[_SourceDeclaration]:
    declarations: List[_SourceDeclaration] = []
    cursor = start + 1
    while cursor < end:
        token = tokens[cursor]
        if token.kind in {"line_comment", "block_comment"}:
            cursor += 1
            continue
        if token.depth != depth or token.normalized not in {"FROM", "JOIN", "APPLY"}:
            cursor += 1
            continue
        value_index = _next_code_token(tokens, cursor + 1, end)
        if value_index is None:
            break
        if tokens[value_index].text == "(":
            close = _matching_parenthesis_token(tokens, value_index, end)
            if close is None:
                cursor += 1
                continue
            source = "(DERIVED)"
            source_start = value_index
            source_name_end = close
            source_end = close
            alias_probe = _next_code_token(tokens, close + 1, end)
        else:
            source_start = value_index
            source_end = value_index
            parts = [tokens[value_index].normalized]
            probe = value_index + 1
            while probe + 1 < end:
                dot = _next_code_token(tokens, probe, end)
                if dot is None or tokens[dot].text != ".":
                    break
                name = _next_code_token(tokens, dot + 1, end)
                if name is None or not _is_identifier_token(tokens[name]):
                    break
                parts.extend([".", tokens[name].normalized])
                source_end = name
                probe = name + 1
            source = "".join(parts)
            source_name_end = source_end
            alias_probe = _next_code_token(tokens, source_end + 1, end)
            if alias_probe is not None and tokens[alias_probe].text == "(":
                close = _matching_parenthesis_token(tokens, alias_probe, end)
                if close is None:
                    cursor += 1
                    continue
                source_end = close
                alias_probe = _next_code_token(tokens, close + 1, end)

        alias_start: int | None = None
        alias_end: int | None = None
        alias = _base_source(source)
        if alias_probe is not None and tokens[alias_probe].normalized == "AS":
            alias_value = _next_code_token(tokens, alias_probe + 1, end)
            if alias_value is not None and _is_identifier_token(tokens[alias_value]):
                alias_start, alias_end = alias_probe, alias_value
                alias = _identifier_value(tokens[alias_value])
        elif (
            alias_probe is not None
            and _is_identifier_token(tokens[alias_probe])
            and tokens[alias_probe].normalized not in _CLAUSE_WORDS
        ):
            alias_start = alias_end = alias_probe
            alias = _identifier_value(tokens[alias_probe])

        declarations.append(
            _SourceDeclaration(
                scope_id=scope_id,
                source=_normalize_source(source),
                base_source=_base_source(source),
                effective_alias=alias.upper(),
                source_start=source_start,
                source_name_end=source_name_end,
                source_end=source_end,
                alias_start=alias_start,
                alias_end=alias_end,
                order=len(declarations) + 1,
            )
        )
        cursor = max(cursor + 1, source_end + 1)
    return declarations


def _find_alias_changes(
    original_scopes: Sequence[_SqlScope],
    formatted_scopes: Sequence[_SqlScope],
) -> List[_AliasChange]:
    changes: List[_AliasChange] = []
    for original_scope, formatted_scope in zip(original_scopes, formatted_scopes):
        for original_decl, formatted_decl in zip(
            original_scope.declarations,
            formatted_scope.declarations,
        ):
            if original_decl.source != formatted_decl.source:
                continue
            if original_decl.effective_alias == formatted_decl.effective_alias:
                continue
            changes.append(
                _AliasChange(
                    scope_id=formatted_scope.scope_id,
                    source=formatted_decl.source,
                    original_alias=original_decl.effective_alias,
                    formatted_alias=formatted_decl.effective_alias,
                    original=original_decl,
                    formatted=formatted_decl,
                )
            )
    return changes


def _validate_alias_role_plan(
    original_scopes: Sequence[_SqlScope],
    formatted_scopes: Sequence[_SqlScope],
    changes: Sequence[_AliasChange],
    plan: Mapping[str, Any] | Sequence[Mapping[str, Any]] | None,
) -> Tuple[Dict[str, Any], List[SqlFormattingIssue], bool]:
    if not changes:
        return (
            {
                "status": "not_needed",
                "reason": "no_alias_changed",
                "plan_provided": plan is not None,
                "verified_scopes": [],
                "conflicts": [],
            },
            [],
            True,
        )
    if plan is None:
        issue = SqlFormattingIssue(
            code="alias_role_plan_required",
            severity="error",
            message="Alias changes require a complete explicit per-scope role plan.",
            evidence=[f"{item.scope_id}:{item.original_alias}->{item.formatted_alias}" for item in changes],
            check_kind="alias_role_plan",
        )
        return (
            {
                "status": "required",
                "reason": "alias_changed_without_plan",
                "plan_provided": False,
                "verified_scopes": [],
                "conflicts": issue.evidence,
            },
            [issue],
            False,
        )

    raw_scopes: Any
    if isinstance(plan, Mapping):
        raw_scopes = plan.get("scopes")
    else:
        raw_scopes = plan
    conflicts: List[str] = []
    issue_codes: set[str] = set()
    if not isinstance(raw_scopes, Sequence) or isinstance(raw_scopes, (str, bytes)):
        raw_scopes = []
        conflicts.append("alias_role_plan.scopes must be a sequence")
        issue_codes.add("alias_plan_incomplete")

    original_by_id = {item.scope_id: item for item in original_scopes}
    formatted_by_id = {item.scope_id: item for item in formatted_scopes}
    changed_scope_ids = {item.scope_id for item in changes}
    plan_scope_ids: set[str] = set()
    verified_scopes: List[str] = []
    all_expected = _expected_alias_members(original_scopes, formatted_scopes, changed_scope_ids)

    for raw_scope in raw_scopes:
        if not isinstance(raw_scope, Mapping):
            conflicts.append("scope entry must be an object")
            issue_codes.add("alias_plan_incomplete")
            continue
        scope_id = str(raw_scope.get("scope_id", "")).strip()
        if not scope_id or scope_id in plan_scope_ids:
            conflicts.append(f"invalid or duplicate scope_id {scope_id!r}")
            issue_codes.add("alias_plan_incomplete")
            continue
        plan_scope_ids.add(scope_id)
        if scope_id not in changed_scope_ids:
            conflicts.append(f"scope {scope_id!r} has no alias changes")
            issue_codes.add("alias_plan_incomplete")
            continue
        basis = raw_scope.get("basis_references", [])
        if not _has_concrete_basis_references(basis):
            conflicts.append(f"scope {scope_id!r} needs non-empty concrete basis_references")
            issue_codes.add("alias_basis_required")

        roles = raw_scope.get("roles", [])
        if not isinstance(roles, Sequence) or isinstance(roles, (str, bytes)) or not roles:
            conflicts.append(f"scope {scope_id!r} needs roles")
            issue_codes.add("alias_plan_incomplete")
            continue
        members: List[Tuple[str, str, str]] = []
        next_role_letter = ord("B")
        for role_index, role in enumerate(roles):
            if not isinstance(role, Mapping):
                conflicts.append(f"scope {scope_id!r} role {role_index + 1} is not an object")
                issue_codes.add("alias_plan_incomplete")
                continue
            role_members = role.get("members", [])
            if not isinstance(role_members, Sequence) or isinstance(role_members, (str, bytes)) or not role_members:
                conflicts.append(f"scope {scope_id!r} role {role_index + 1} has no members")
                issue_codes.add("alias_plan_incomplete")
                continue
            normalized_members = []
            for member in role_members:
                if not isinstance(member, Mapping):
                    continue
                normalized_members.append(
                    (
                        _normalize_source(str(member.get("source", ""))),
                        str(member.get("original_alias", "")).strip().upper(),
                        str(member.get("alias", "")).strip().upper(),
                    )
                )
            if len(normalized_members) != len(role_members) or any(not all(item) for item in normalized_members):
                conflicts.append(f"scope {scope_id!r} role {role_index + 1} has incomplete members")
                issue_codes.add("alias_plan_incomplete")
            members.extend(normalized_members)

            kind = str(role.get("kind", "support")).strip().lower()
            aliases = [item[2] for item in normalized_members]
            if kind == "main":
                expected = ["A", *[f"A{index}" for index in range(1, len(aliases))]]
                if role_index != 0 or aliases != expected:
                    conflicts.append(f"scope {scope_id!r} main role aliases {aliases} must be {expected}")
                    issue_codes.add("alias_main_role_invalid")
            else:
                family = chr(next_role_letter)
                expected = [family] if len(aliases) == 1 else [f"{family}{i}" for i in range(1, len(aliases) + 1)]
                if aliases != expected:
                    conflicts.append(f"scope {scope_id!r} role aliases {aliases} must be sequential {expected}")
                    issue_codes.add("alias_role_letters_not_sequential")
                next_role_letter += 1

        expected_members = all_expected.get(scope_id, set())
        actual_members = set(members)
        for member in actual_members - expected_members:
            other_scope = next(
                (
                    candidate
                    for candidate, values in all_expected.items()
                    if candidate != scope_id and member in values
                ),
                "",
            )
            if other_scope:
                conflicts.append(f"member {member!r} belongs to {other_scope}, not {scope_id}")
                issue_codes.add("alias_cross_scope_mixing")
        if actual_members != expected_members:
            conflicts.append(
                f"scope {scope_id!r} plan members do not cover every declaration: "
                f"missing={sorted(expected_members - actual_members)!r}, extra={sorted(actual_members - expected_members)!r}"
            )
            issue_codes.add("alias_plan_incomplete")
        if not any(f"scope {scope_id!r}" in value for value in conflicts):
            verified_scopes.append(scope_id)

    if plan_scope_ids != changed_scope_ids:
        conflicts.append(
            f"plan scopes must exactly cover changed scopes: missing={sorted(changed_scope_ids - plan_scope_ids)!r}, "
            f"extra={sorted(plan_scope_ids - changed_scope_ids)!r}"
        )
        issue_codes.add("alias_plan_incomplete")

    issues = [
        SqlFormattingIssue(
            code=code,
            severity="error",
            message="Alias-role plan validation failed.",
            evidence=conflicts[:16],
            check_kind="alias_role_plan",
        )
        for code in sorted(issue_codes)
    ]
    status = "conflict" if issues else "verified"
    return (
        {
            "status": status,
            "reason": "complete_per_scope_plan_matched" if not issues else "plan_conflicts_with_sql",
            "plan_provided": True,
            "verified_scopes": verified_scopes,
            "conflicts": conflicts,
        },
        issues,
        not issues,
    )


def _expected_alias_members(
    original_scopes: Sequence[_SqlScope],
    formatted_scopes: Sequence[_SqlScope],
    changed_scope_ids: set[str],
) -> Dict[str, set[Tuple[str, str, str]]]:
    result: Dict[str, set[Tuple[str, str, str]]] = {}
    for original_scope, formatted_scope in zip(original_scopes, formatted_scopes):
        if formatted_scope.scope_id not in changed_scope_ids:
            continue
        values = set()
        for original_decl, formatted_decl in zip(original_scope.declarations, formatted_scope.declarations):
            if original_decl.source == formatted_decl.source:
                values.add(
                    (
                        formatted_decl.source,
                        original_decl.effective_alias,
                        formatted_decl.effective_alias,
                    )
                )
        result[formatted_scope.scope_id] = values
    return result


def _canonical_token_stream(
    tokens: Sequence[_SqlToken],
    scopes: Sequence[_SqlScope],
    changes: Sequence[_AliasChange],
    side: str,
    range_replacements: Sequence[Tuple[int, int, str]] = (),
) -> List[str]:
    skip: set[int] = set()
    insert_after: Dict[int, str] = {}
    replacement: Dict[int, str] = {}
    range_markers: Dict[int, str] = {}
    for start, end, marker in range_replacements:
        skip.update(range(start, end + 1))
        if marker:
            range_markers[start] = marker
    scopes_by_id = {item.scope_id: item for item in scopes}
    for ordinal, change in enumerate(changes, start=1):
        declaration = change.original if side == "original" else change.formatted
        alias = change.original_alias if side == "original" else change.formatted_alias
        marker = f"<ALIAS:{change.scope_id}:{ordinal}>"
        if declaration.alias_start is not None and declaration.alias_end is not None:
            skip.update(range(declaration.alias_start, declaration.alias_end + 1))
        insert_after[declaration.source_end] = marker
        scope = scopes_by_id.get(change.scope_id)
        if scope is None:
            continue
        for index in range(scope.start, min(scope.end, len(tokens))):
            if any(
                item.source_start <= index <= item.source_name_end
                for item in scope.declarations
            ):
                continue
            token = tokens[index]
            if _identifier_value(token) != alias:
                continue
            if _is_bound_alias_reference(tokens, index, scope, alias):
                replacement[index] = marker

    values: List[str] = []
    for token in tokens:
        if token.index in range_markers:
            values.append(range_markers[token.index])
        if token.index in skip:
            continue
        values.append(replacement.get(token.index, _canonical_token_value(token)))
        if token.index in insert_after:
            values.append(insert_after[token.index])
    return values


def _is_bound_alias_reference(
    tokens: Sequence[_SqlToken],
    index: int,
    scope: _SqlScope,
    alias: str,
) -> bool:
    if _identifier_value(tokens[index]) != alias:
        return False
    if sum(item.effective_alias == alias for item in scope.declarations) != 1:
        return False
    dot = _next_code_token(tokens, index + 1, scope.end)
    if dot is None or tokens[dot].text != ".":
        return False
    member = _next_code_token(tokens, dot + 1, scope.end)
    if member is None or not (_is_identifier_token(tokens[member]) or tokens[member].text == "*"):
        return False
    following = _next_code_token(tokens, member + 1, scope.end)
    return following is None or tokens[following].text != "."


def _validate_scalar_refactor_boundary(
    original_tokens: Sequence[_SqlToken],
    formatted_tokens: Sequence[_SqlToken],
    original_scopes: Sequence[_SqlScope],
    formatted_scopes: Sequence[_SqlScope],
    alias_changes: Sequence[_AliasChange],
    evidence: Mapping[str, Any],
) -> Tuple[Dict[str, Any], List[SqlFormattingIssue], List[str], List[str]]:
    original_stream = _canonical_token_stream(
        original_tokens,
        original_scopes,
        alias_changes,
        "original",
    )
    formatted_stream = _canonical_token_stream(
        formatted_tokens,
        formatted_scopes,
        alias_changes,
        "formatted",
    )
    errors: List[str] = []
    function = evidence.get("function") if isinstance(evidence.get("function"), Mapping) else {}
    analysis = evidence.get("analysis") if isinstance(evidence.get("analysis"), Mapping) else {}
    function_name = str(function.get("name", "")).strip()
    function_parts = _normalized_identifier_path(function_name)
    if not function_parts:
        errors.append("function.name must be a multipart identifier")

    original_calls = _find_scalar_function_calls(original_tokens, function_parts)
    formatted_calls = _find_scalar_function_calls(formatted_tokens, function_parts)
    if len(original_calls) != 1:
        errors.append(f"expected exactly one original scalar call, found {len(original_calls)}")
    if formatted_calls:
        errors.append(f"formatted SQL still contains {len(formatted_calls)} matching scalar call(s)")

    source_table = _normalize_source(str(analysis.get("source_table", "")))
    formatted_sources = [
        (scope, declaration)
        for scope in formatted_scopes
        for declaration in scope.declarations
        if _matches_refactor_source(declaration.source, source_table)
    ]
    original_source_count = sum(
        _matches_refactor_source(declaration.source, source_table)
        for scope in original_scopes
        for declaration in scope.declarations
    )
    if not source_table:
        errors.append("analysis.source_table is required")
    elif original_source_count:
        errors.append("source_table already exists in the original scope")
    if len(formatted_sources) != 1:
        errors.append(
            f"expected exactly one formatted source_table declaration, found {len(formatted_sources)}"
        )

    if errors or len(original_calls) != 1 or len(formatted_sources) != 1:
        return _scalar_boundary_failure(errors, original_stream, formatted_stream)

    call_start, call_open, call_end = original_calls[0]
    original_scope = _scope_containing_token(original_scopes, call_start)
    formatted_scope, formatted_declaration = formatted_sources[0]
    if original_scope is None or original_scope.scope_id != formatted_scope.scope_id:
        errors.append("scalar call and replacement source must belong to the same parsed scope")
    if formatted_declaration.alias_start is None:
        errors.append("replacement source_table must have an explicit alias")

    join_boundary = _left_outer_join_boundary(
        formatted_tokens,
        formatted_scope,
        formatted_declaration,
    )
    if join_boundary is None:
        errors.append("source_table must be introduced by one parsed LEFT OUTER JOIN ... ON clause")

    return_tokens, _ = _scan_sql_tokens(str(analysis.get("return_expression", "")))
    return_code = [item for item in return_tokens if item.kind not in {"line_comment", "block_comment"}]
    if len(return_code) != 1 or not _is_identifier_token(return_code[0]):
        errors.append("analysis.return_expression must identify one returned source column")

    replacement_ranges: List[Tuple[int, int]] = []
    if not errors and join_boundary is not None:
        return_name = _identifier_value(return_code[0])
        join_start, join_end, on_index = join_boundary
        for index in range(formatted_scope.start, min(formatted_scope.end, len(formatted_tokens))):
            if join_start <= index <= join_end:
                continue
            if not _is_bound_alias_reference(
                formatted_tokens,
                index,
                formatted_scope,
                formatted_declaration.effective_alias,
            ):
                continue
            dot = _next_code_token(formatted_tokens, index + 1, formatted_scope.end)
            member = (
                _next_code_token(formatted_tokens, dot + 1, formatted_scope.end)
                if dot is not None
                else None
            )
            if member is not None and _identifier_value(formatted_tokens[member]) == return_name:
                replacement_ranges.append((index, member))
        if len(replacement_ranges) != 1:
            errors.append(
                "formatted SQL must contain exactly one alias-qualified return_expression replacement"
            )

        mappings = analysis.get("key_mappings")
        mapping_values = (
            list(mappings)
            if isinstance(mappings, Sequence) and not isinstance(mappings, (str, bytes))
            else []
        )
        expected_arguments = [
            _canonical_sql_fragment(str(item.get("call_argument", "")))
            for item in mapping_values
            if isinstance(item, Mapping)
        ]
        actual_arguments = _split_call_arguments(original_tokens, call_open, call_end)
        if not expected_arguments or actual_arguments != expected_arguments:
            errors.append("parsed scalar call arguments do not match analysis.key_mappings")

        predicate_fragments = [
            str(item.get("join_expression", ""))
            for item in mapping_values
            if isinstance(item, Mapping)
        ]
        filters = analysis.get("filters")
        if isinstance(filters, Sequence) and not isinstance(filters, (str, bytes)):
            predicate_fragments.extend(str(item) for item in filters)
        expected_predicate: List[str] = []
        for fragment in predicate_fragments:
            values = _canonical_sql_fragment(fragment)
            if expected_predicate:
                expected_predicate.append("AND")
            expected_predicate.extend(values)
        actual_predicate = [
            _canonical_token_value(item)
            for item in formatted_tokens[on_index + 1 : join_end + 1]
        ]
        if not expected_predicate or actual_predicate != expected_predicate:
            errors.append("parsed LEFT OUTER JOIN predicate does not match declared mappings and filters")

    if errors or join_boundary is None or len(replacement_ranges) != 1:
        return _scalar_boundary_failure(errors, original_stream, formatted_stream)

    join_start, join_end, _ = join_boundary
    replacement_start, replacement_end = replacement_ranges[0]
    marker = "<SCALAR_FUNCTION_REFACTOR:1>"
    bounded_original = _canonical_token_stream(
        original_tokens,
        original_scopes,
        alias_changes,
        "original",
        [(call_start, call_end, marker)],
    )
    bounded_formatted = _canonical_token_stream(
        formatted_tokens,
        formatted_scopes,
        alias_changes,
        "formatted",
        [
            (replacement_start, replacement_end, marker),
            (join_start, join_end, ""),
        ],
    )
    if bounded_original != bounded_formatted:
        difference = _first_token_difference(bounded_original, bounded_formatted)
        errors.extend(_difference_evidence(difference))
        return _scalar_boundary_failure(errors, bounded_original, bounded_formatted)

    return (
        {
            "status": "verified",
            "reason": "parsed_call_replacement_and_left_join_only",
            "function": function_name,
            "source_table": source_table,
            "formatted_source": formatted_declaration.source,
            "original_call_tokens": [call_start, call_end],
            "formatted_replacement_tokens": [replacement_start, replacement_end],
            "formatted_join_tokens": [join_start, join_end],
        },
        [],
        bounded_original,
        bounded_formatted,
    )


def _matches_refactor_source(parsed_source: str, declared_source: str) -> bool:
    return parsed_source == declared_source


def _scalar_boundary_failure(
    errors: Sequence[str],
    original_stream: List[str],
    formatted_stream: List[str],
) -> Tuple[Dict[str, Any], List[SqlFormattingIssue], List[str], List[str]]:
    evidence = list(errors)[:16] or ["parsed scalar refactor boundary was not proven"]
    issue = SqlFormattingIssue(
        code="scalar_refactor_boundary_violation",
        severity="error",
        message="Refactor changes escaped the parsed scalar-function replacement boundary.",
        evidence=evidence,
        check_kind="formatting_preservation",
    )
    return (
        {
            "status": "blocked",
            "reason": "parsed_boundary_not_proven",
            "errors": evidence,
        },
        [issue],
        original_stream,
        formatted_stream,
    )


def _normalized_identifier_path(value: str) -> List[str]:
    tokens, issues = _scan_sql_tokens(value)
    if issues:
        return []
    code = [item for item in tokens if item.kind not in {"line_comment", "block_comment"}]
    if not code or len(code) % 2 == 0:
        return []
    parts: List[str] = []
    for index, token in enumerate(code):
        if index % 2 == 0:
            if not _is_identifier_token(token):
                return []
            parts.append(_identifier_value(token))
        elif token.text != ".":
            return []
    return parts


def _find_scalar_function_calls(
    tokens: Sequence[_SqlToken],
    function_parts: Sequence[str],
) -> List[Tuple[int, int, int]]:
    if not function_parts:
        return []
    calls: List[Tuple[int, int, int]] = []
    for start, token in enumerate(tokens):
        if _identifier_value(token) != function_parts[0]:
            continue
        cursor = start
        matched = True
        for part in function_parts[1:]:
            dot = _next_code_token(tokens, cursor + 1, len(tokens))
            name = _next_code_token(tokens, dot + 1, len(tokens)) if dot is not None else None
            if (
                dot is None
                or tokens[dot].text != "."
                or name is None
                or _identifier_value(tokens[name]) != part
            ):
                matched = False
                break
            cursor = name
        if not matched:
            continue
        open_index = _next_code_token(tokens, cursor + 1, len(tokens))
        if open_index is None or tokens[open_index].text != "(":
            continue
        close_index = _matching_parenthesis_token(tokens, open_index, len(tokens))
        if close_index is not None:
            calls.append((start, open_index, close_index))
    return calls


def _scope_containing_token(
    scopes: Sequence[_SqlScope],
    token_index: int,
) -> _SqlScope | None:
    return next((item for item in scopes if item.start <= token_index < item.end), None)


def _left_outer_join_boundary(
    tokens: Sequence[_SqlToken],
    scope: _SqlScope,
    declaration: _SourceDeclaration,
) -> Tuple[int, int, int] | None:
    join_index = _previous_code_token(tokens, declaration.source_start - 1, scope.start)
    if join_index is None or tokens[join_index].normalized != "JOIN":
        return None
    previous = _previous_code_token(tokens, join_index - 1, scope.start)
    if previous is not None and tokens[previous].normalized == "OUTER":
        left_index = _previous_code_token(tokens, previous - 1, scope.start)
    else:
        left_index = previous
    if left_index is None or tokens[left_index].normalized != "LEFT":
        return None

    declaration_end = declaration.alias_end or declaration.source_end
    on_index = _next_code_token(tokens, declaration_end + 1, scope.end)
    if on_index is None or tokens[on_index].normalized != "ON":
        return None
    end = scope.end - 1
    boundary_words = {
        "LEFT",
        "RIGHT",
        "FULL",
        "INNER",
        "CROSS",
        "JOIN",
        "APPLY",
        "WHERE",
        "GROUP",
        "HAVING",
        "ORDER",
        "UNION",
        "EXCEPT",
        "INTERSECT",
        "OPTION",
        ";",
        "<GO_BATCH>",
    }
    for index in range(on_index + 1, min(scope.end, len(tokens))):
        token = tokens[index]
        if token.depth == scope.depth and token.normalized in boundary_words:
            end = index - 1
            break
    if end <= on_index:
        return None
    return left_index, end, on_index


def _previous_code_token(
    tokens: Sequence[_SqlToken],
    start: int,
    lower_bound: int,
) -> int | None:
    for index in range(start, lower_bound - 1, -1):
        if tokens[index].kind not in {"line_comment", "block_comment"}:
            return index
    return None


def _canonical_sql_fragment(value: str) -> List[str]:
    tokens, issues = _scan_sql_tokens(value)
    if issues:
        return []
    return [_canonical_token_value(item) for item in tokens]


def _split_call_arguments(
    tokens: Sequence[_SqlToken],
    open_index: int,
    close_index: int,
) -> List[List[str]]:
    if close_index == open_index + 1:
        return []
    arguments: List[List[str]] = []
    start = open_index + 1
    argument_depth = tokens[open_index].depth + 1
    for index in range(start, close_index):
        if tokens[index].text == "," and tokens[index].depth == argument_depth:
            arguments.append([_canonical_token_value(item) for item in tokens[start:index]])
            start = index + 1
    arguments.append([_canonical_token_value(item) for item in tokens[start:close_index]])
    return arguments


def _validate_scalar_function_refactor(
    evidence: Mapping[str, Any] | None,
    *,
    operation: str,
    original_sha256: str,
    formatted_sha256: str,
) -> Tuple[Dict[str, Any], List[SqlFormattingIssue]]:
    base = {
        "status": "not_requested",
        "evidence_status": "not_provided",
        "semantic_status": "not_proven",
        "reason": "formatting_preserves_all_scalar_functions",
        "missing_fields": [],
        "disqualifiers": [],
        "external_correlation": "not_provided",
        "execution_authentication": "not_authenticated",
    }
    if evidence is None:
        if operation == "refactor":
            issue = _scalar_refactor_issue(
                "scalar_refactor_evidence_required",
                ["A refactor operation requires structured scalar_function_refactor evidence."],
            )
            return (
                {
                    "scalar_function_refactor": {
                        **base,
                        "status": "blocked",
                        "reason": "structured_evidence_required",
                    }
                },
                [issue],
            )
        return {"scalar_function_refactor": base}, []
    if not isinstance(evidence, Mapping):
        issue = _scalar_refactor_issue("scalar_refactor_evidence_incomplete", ["evidence must be an object"])
        return {
            "scalar_function_refactor": {
                **base,
                "status": "blocked",
                "evidence_status": "invalid",
                "reason": "invalid_evidence",
            }
        }, [issue]

    decision = str(evidence.get("decision", "")).strip().lower()
    if operation != "refactor":
        issue = _scalar_refactor_issue(
            "scalar_refactor_requires_separate_operation",
            ["set operation='refactor' for a separately requested conversion"],
        )
        incomplete = _scalar_refactor_missing_fields(evidence)
        issues = [issue]
        if incomplete:
            issues.append(_scalar_refactor_issue("scalar_refactor_evidence_incomplete", incomplete))
        return (
            {
                "scalar_function_refactor": {
                    **base,
                    "status": "blocked",
                    "evidence_status": "incomplete" if incomplete else "not_evaluated",
                    "reason": "separate_refactor_operation_required",
                    "missing_fields": incomplete,
                }
            },
            issues,
        )
    if decision in {"retain", "blocked"}:
        reason = str(evidence.get("reason", "")).strip() or "conversion_not_proven"
        issue = _scalar_refactor_issue("scalar_refactor_conversion_blocked", [reason])
        return (
            {
                "scalar_function_refactor": {
                    **base,
                    "status": "blocked",
                    "reason": reason,
                }
            },
            [issue],
        )

    missing = _scalar_refactor_missing_fields(evidence)
    analysis = evidence.get("analysis") if isinstance(evidence.get("analysis"), Mapping) else {}
    disqualifiers = [str(item) for item in analysis.get("disqualifiers", []) if str(item).strip()]
    classification = str(analysis.get("classification", "")).strip().lower()
    if classification and classification != "pure_deterministic_lookup":
        disqualifiers.append(classification)
    if disqualifiers:
        issue = _scalar_refactor_issue("scalar_refactor_conversion_blocked", disqualifiers)
        return (
            {
                "scalar_function_refactor": {
                    **base,
                    "status": "blocked",
                    "evidence_status": "rejected",
                    "reason": "disqualifying_function_behavior",
                    "missing_fields": missing,
                    "disqualifiers": sorted(set(disqualifiers)),
                }
            },
            [issue],
        )
    if missing:
        issue = _scalar_refactor_issue("scalar_refactor_evidence_incomplete", missing)
        return (
            {
                "scalar_function_refactor": {
                    **base,
                    "status": "blocked",
                    "evidence_status": "incomplete",
                    "reason": "structured_evidence_incomplete",
                    "missing_fields": missing,
                }
            },
            [issue],
        )

    external = evidence.get("trusted_external_verification")
    correlation_errors = _external_refactor_correlation_errors(
        external,
        original_sha256,
        formatted_sha256,
    )
    if correlation_errors:
        issue = _scalar_refactor_issue("scalar_refactor_semantics_not_proven", correlation_errors)
        return (
            {
                "scalar_function_refactor": {
                    **base,
                    "status": "not_proven",
                    "evidence_status": "complete",
                    "reason": "trusted_external_result_comparison_required",
                    "external_correlation": "not_proven",
                }
            },
            [issue],
        )

    return (
        {
            "scalar_function_refactor": {
                **base,
                "status": "mechanically_valid",
                "evidence_status": "complete",
                "semantic_status": "not_proven",
                "reason": "external_result_comparison_is_provenance_only",
                "external_correlation": "provenance_correlated",
            }
        },
        [],
    )


def _scalar_refactor_missing_fields(evidence: Mapping[str, Any]) -> List[str]:
    missing: List[str] = []
    if str(evidence.get("decision", "")).strip().lower() != "convert":
        missing.append("decision=convert")
    function = evidence.get("function") if isinstance(evidence.get("function"), Mapping) else {}
    for key in ["name", "definition_source_kind", "definition_source_ref", "definition_sha256"]:
        if not str(function.get(key, "")).strip():
            missing.append(f"function.{key}")
    source_kind = str(function.get("definition_source_kind", "")).strip().lower()
    if source_kind and source_kind not in {"database", "mcp", "project_source"}:
        missing.append("function.definition_source_kind(authoritative)")
    digest = str(function.get("definition_sha256", "")).strip()
    if digest and not _HASH_PATTERN.fullmatch(digest):
        missing.append("function.definition_sha256(valid_sha256)")

    analysis = evidence.get("analysis") if isinstance(evidence.get("analysis"), Mapping) else {}
    for key in [
        "classification",
        "source_table",
        "return_expression",
        "null_behavior",
        "cardinality",
        "unmatched_row_behavior",
        "preferred_reason",
    ]:
        if not str(analysis.get(key, "")).strip():
            missing.append(f"analysis.{key}")
    mappings = analysis.get("key_mappings")
    if not isinstance(mappings, Sequence) or isinstance(mappings, (str, bytes)) or not mappings:
        missing.append("analysis.key_mappings")
    else:
        for index, mapping in enumerate(mappings):
            if not isinstance(mapping, Mapping):
                missing.append(f"analysis.key_mappings[{index}]")
                continue
            for key in ["parameter", "source_column", "call_argument", "join_expression"]:
                if not str(mapping.get(key, "")).strip():
                    missing.append(f"analysis.key_mappings[{index}].{key}")
    filters = analysis.get("filters")
    if not isinstance(filters, Sequence) or isinstance(filters, (str, bytes)):
        missing.append("analysis.filters")
    if "disqualifiers" not in analysis or not isinstance(analysis.get("disqualifiers"), Sequence):
        missing.append("analysis.disqualifiers")
    if str(analysis.get("cardinality", "")).strip().lower() not in {"zero_or_one", "exactly_one"}:
        missing.append("analysis.cardinality(proven_zero_or_one)")

    artifacts = evidence.get("artifacts")
    if not isinstance(artifacts, Sequence) or isinstance(artifacts, (str, bytes)):
        missing.append("artifacts")
    else:
        definition_artifacts = [
            item
            for item in artifacts
            if isinstance(item, Mapping) and str(item.get("kind", "")).strip() == "function_definition"
        ]
        if not definition_artifacts:
            missing.append("artifacts.function_definition")
        for artifact in definition_artifacts:
            if not str(artifact.get("artifact_id", "")).strip():
                missing.append("artifacts.function_definition.artifact_id")
            artifact_digest = str(artifact.get("sha256", "")).strip()
            if not _HASH_PATTERN.fullmatch(artifact_digest):
                missing.append("artifacts.function_definition.sha256")
            elif digest and artifact_digest.lower() != digest.lower():
                missing.append("artifacts.function_definition.sha256(matches_function_definition)")
    return sorted(set(missing))


def _external_refactor_correlation_errors(
    external: Any,
    original_sha256: str,
    formatted_sha256: str,
) -> List[str]:
    if not isinstance(external, Mapping):
        return ["trusted_external_verification is missing"]
    errors = []
    required = ["provider", "artifact_id", "artifact_sha256", "kind", "status"]
    for key in required:
        if not str(external.get(key, "")).strip():
            errors.append(f"trusted_external_verification.{key}")
    if str(external.get("kind", "")).strip().lower() not in {
        "db_result_comparison",
        "result_comparison",
    }:
        errors.append("trusted_external_verification.kind")
    if str(external.get("status", "")).strip().lower() != "matched":
        errors.append("trusted_external_verification.status=matched")
    if not _HASH_PATTERN.fullmatch(str(external.get("artifact_sha256", "")).strip()):
        errors.append("trusted_external_verification.artifact_sha256")
    if str(external.get("original_sha256", "")).strip().lower() != original_sha256:
        errors.append("trusted_external_verification.original_sha256")
    if str(external.get("formatted_sha256", "")).strip().lower() != formatted_sha256:
        errors.append("trusted_external_verification.formatted_sha256")
    return errors


def _scalar_refactor_issue(code: str, evidence: Sequence[str]) -> SqlFormattingIssue:
    return SqlFormattingIssue(
        code=code,
        severity="error",
        message="Scalar-function-to-join refactor evidence did not prove the requested conversion.",
        evidence=list(evidence)[:16],
        check_kind="semantic_refactor_evidence",
    )


def _style_lint(
    original: str,
    formatted: str,
    formatted_tokens: Sequence[_SqlToken],
    *,
    operation: str,
    cte_temp_table_reason: str | None,
) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    lowercase = _lowercase_sql_tokens(formatted_tokens)
    if lowercase:
        issues.append(
            SqlFormattingIssue(
                code="identifiers_not_uppercase",
                severity="error",
                message="SQL identifiers and keywords outside literals/comments must be uppercase.",
                evidence=lowercase[:10],
                check_kind="style",
            )
        )
    issues.extend(_check_alias_style(formatted_tokens))
    issues.extend(_check_procedure_parameter_layout(formatted))
    issues.extend(_check_select_leading_commas(formatted))
    issues.extend(_check_insert_select_layout(formatted))
    issues.extend(
        _check_cte_temp_table_introduction(
            original,
            formatted,
            cte_temp_table_reason=cte_temp_table_reason,
        )
    )
    issues.extend(_check_if_exists_where_subquery(formatted_tokens))
    issues.extend(_check_join_indentation(formatted))
    if operation != "formatting":
        issues.extend(_check_case_parentheses(formatted, formatted_tokens))
    return issues


def _preservation_diagnostics(
    original_tokens: Sequence[_SqlToken],
    formatted_tokens: Sequence[_SqlToken],
    original_stream: Sequence[str],
    formatted_stream: Sequence[str],
    *,
    operation: str,
) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    original_strings = [
        item.text for item in original_tokens if item.kind in {"string", "unicode_string"}
    ]
    formatted_strings = [
        item.text for item in formatted_tokens if item.kind in {"string", "unicode_string"}
    ]
    if original_strings != formatted_strings:
        issues.append(
            SqlFormattingIssue(
                code="string_literals_changed",
                severity="error",
                message="String literal sequence changed.",
                evidence=_sequence_diff(original_strings, formatted_strings),
                check_kind="formatting_preservation",
            )
        )
        if any(_contains_localized_text(value) for value in [*original_strings, *formatted_strings]):
            issues.append(
                SqlFormattingIssue(
                    code="localized_literals_changed",
                    severity="error",
                    message="Localized string literals changed.",
                    evidence=_sequence_diff(original_strings, formatted_strings),
                    check_kind="formatting_preservation",
                )
            )
    original_comments = [item.text for item in original_tokens if item.kind.endswith("comment")]
    formatted_comments = [item.text for item in formatted_tokens if item.kind.endswith("comment")]
    if original_comments != formatted_comments:
        issues.append(
            SqlFormattingIssue(
                code="comments_changed",
                severity="error",
                message="Comment token sequence changed.",
                evidence=_sequence_diff(original_comments, formatted_comments),
                check_kind="formatting_preservation",
            )
        )
    localized_before = [value for value in [*original_strings, *original_comments] if _contains_localized_text(value)]
    localized_after = [value for value in [*formatted_strings, *formatted_comments] if _contains_localized_text(value)]
    if localized_before != localized_after or any(_has_replacement_damage_markers(value) for value in localized_after):
        issues.append(
            SqlFormattingIssue(
                code="localized_text_damaged",
                severity="error",
                message="Localized business text changed or contains replacement markers.",
                evidence=_sequence_diff(localized_before, localized_after),
                check_kind="formatting_preservation",
            )
        )
    original_else = sum(value == "ELSE" for value in original_stream)
    formatted_else = sum(value == "ELSE" for value in formatted_stream)
    if formatted_else > original_else:
        issues.append(
            SqlFormattingIssue(
                code="arbitrary_else_added",
                severity="error",
                message="Formatted SQL contains additional ELSE tokens.",
                evidence=[f"original={original_else}", f"formatted={formatted_else}"],
                check_kind="formatting_preservation",
            )
        )
    if any(value in {"WHERE", "ON", "HAVING"} for value in [*original_stream, *formatted_stream]):
        issues.append(
            SqlFormattingIssue(
                code="predicates_changed",
                severity="error",
                message="Predicate-bearing SQL changed; inspect the token diff.",
                evidence=[],
                check_kind="formatting_preservation",
            )
        )
    if sum(value == "SELECT" for value in original_stream) != sum(value == "SELECT" for value in formatted_stream):
        issues.append(
            SqlFormattingIssue(
                code="select_query_count_changed",
                severity="error",
                message="SELECT query count changed.",
                evidence=[],
                check_kind="formatting_preservation",
            )
        )
    return issues


def _check_alias_style(tokens: Sequence[_SqlToken]) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    scopes = _build_sql_scopes(tokens)
    invalid = []
    for scope in scopes:
        for declaration in scope.declarations:
            if declaration.alias_start is None:
                continue
            alias = declaration.effective_alias
            if scope.depth == 0 and re.fullmatch(r"T\d*|T[A-Z]\d+", alias):
                invalid.append(alias)
            elif scope.depth == 0 and not re.fullmatch(r"[A-SU-Z]\d*", alias):
                invalid.append(alias)
    if invalid:
        code = (
            "outer_query_uses_derived_table_internal_alias"
            if any(re.fullmatch(r"T\d*|T[A-Z]\d+", item) for item in invalid)
            else "ad_hoc_outer_alias"
        )
        issues.append(
            SqlFormattingIssue(
                code=code,
                severity="error",
                message="Outer aliases must use A/A1, B/B1, C...; T families are derived-table internal.",
                evidence=invalid[:8],
                check_kind="style",
            )
        )
    return issues


def _canonical_token_value(token: _SqlToken) -> str:
    if token.kind == "line_comment":
        return "LINE_COMMENT:" + token.text
    if token.kind == "block_comment":
        return "BLOCK_COMMENT:" + token.text
    if token.kind == "string":
        return "STRING:" + token.text
    if token.kind == "unicode_string":
        return "UNICODE_STRING:N" + token.text[1:]
    if token.kind == "bracket_identifier":
        return "BRACKET_IDENTIFIER:" + token.text
    if token.kind == "quoted_identifier":
        return "QUOTED_IDENTIFIER:" + token.text
    return token.normalized


def _lexical_summary(
    original_tokens: Sequence[_SqlToken],
    formatted_tokens: Sequence[_SqlToken],
) -> Dict[str, int]:
    return {
        "original_token_count": len(original_tokens),
        "formatted_token_count": len(formatted_tokens),
        "original_comment_count": sum(item.kind.endswith("comment") for item in original_tokens),
        "formatted_comment_count": sum(item.kind.endswith("comment") for item in formatted_tokens),
        "original_string_count": sum(
            item.kind in {"string", "unicode_string"} for item in original_tokens
        ),
        "formatted_string_count": sum(
            item.kind in {"string", "unicode_string"} for item in formatted_tokens
        ),
    }


def _first_token_difference(original: Sequence[str], formatted: Sequence[str]) -> Dict[str, Any]:
    limit = min(len(original), len(formatted))
    index = next((value for value in range(limit) if original[value] != formatted[value]), limit)
    return {
        "index": index,
        "original": original[index] if index < len(original) else "<END>",
        "formatted": formatted[index] if index < len(formatted) else "<END>",
        "original_context": list(original[max(0, index - 3) : index + 4]),
        "formatted_context": list(formatted[max(0, index - 3) : index + 4]),
    }


def _difference_evidence(value: Mapping[str, Any]) -> List[str]:
    return [
        f"index={value.get('index')}",
        f"original={value.get('original')!r}",
        f"formatted={value.get('formatted')!r}",
    ]


def _alias_change_dict(value: _AliasChange) -> Dict[str, str]:
    return {
        "scope_id": value.scope_id,
        "source": value.source,
        "original_alias": value.original_alias,
        "formatted_alias": value.formatted_alias,
    }


def _has_concrete_basis_references(value: Any) -> bool:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)) or not value:
        return False
    references = [str(item).strip() for item in value]
    if any(not item for item in references):
        return False
    vague = {"reviewed", "same role", "business role", "looks related", "n/a"}
    return all(len(item) >= 8 and item.lower() not in vague for item in references)


def _next_code_token(tokens: Sequence[_SqlToken], start: int, end: int) -> int | None:
    for index in range(start, min(end, len(tokens))):
        if tokens[index].kind not in {"line_comment", "block_comment"}:
            return index
    return None


def _matching_parenthesis_token(
    tokens: Sequence[_SqlToken],
    open_index: int,
    end: int,
) -> int | None:
    target_depth = tokens[open_index].depth
    for index in range(open_index + 1, min(end, len(tokens))):
        if tokens[index].text == ")" and tokens[index].depth == target_depth:
            return index
    return None


def _is_identifier_token(token: _SqlToken) -> bool:
    return token.kind in {"word", "bracket_identifier", "quoted_identifier"}


def _identifier_value(token: _SqlToken) -> str:
    if not _is_identifier_token(token):
        return ""
    if token.kind == "bracket_identifier":
        return token.text[1:-1].replace("]]", "]").upper()
    if token.kind == "quoted_identifier":
        return token.text[1:-1].replace('""', '"').upper()
    return token.text.upper()


def _normalize_source(value: str) -> str:
    return value.replace("[", "").replace("]", "").replace('"', "").strip().upper()


def _base_source(value: str) -> str:
    return _normalize_source(value).rsplit(".", 1)[-1]


def _lowercase_sql_tokens(tokens: Sequence[_SqlToken]) -> List[str]:
    values = []
    for index, token in enumerate(tokens):
        if token.kind != "word" or not any("a" <= char <= "z" for char in token.text):
            continue
        previous = tokens[index - 1] if index else None
        if previous and previous.text == ":":
            continue
        if token.text.startswith("@@"):
            continue
        values.append(token.text)
    return sorted(set(values))


def _masked_sql(sql: str) -> str:
    tokens, _ = _scan_sql_tokens(sql)
    chars = list(sql)
    for token in tokens:
        if token.kind not in {"string", "line_comment", "block_comment"}:
            continue
        for index in range(token.start, token.end):
            if chars[index] not in "\r\n":
                chars[index] = " "
    return "".join(chars)


def _check_procedure_parameter_layout(sql: str) -> List[SqlFormattingIssue]:
    masked = _masked_sql(sql)
    if not re.search(r"\bCREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\b", masked, flags=re.IGNORECASE):
        return []
    lines = masked.splitlines()
    issues: List[SqlFormattingIssue] = []
    proc_index = next(
        (
            index
            for index, line in enumerate(lines)
            if re.search(r"\bCREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\b", line, flags=re.IGNORECASE)
        ),
        -1,
    )
    if proc_index < 0:
        return []
    if "@" in lines[proc_index]:
        issues.append(
            SqlFormattingIssue(
                code="procedure_first_parameter_same_line",
                severity="error",
                message="First stored procedure parameter must follow the procedure-name line.",
                evidence=[sql.splitlines()[proc_index].strip()],
                check_kind="style",
            )
        )
    parameter_lines = []
    for line in lines[proc_index + 1 :]:
        if re.match(r"^\s*AS\b", line, flags=re.IGNORECASE):
            break
        if re.search(r"@\w+", line):
            parameter_lines.append(line)
    for index, line in enumerate(parameter_lines):
        stripped = line.lstrip()
        if index == 0 and stripped.startswith(","):
            issues.append(
                SqlFormattingIssue(
                    code="procedure_first_parameter_leading_comma",
                    severity="error",
                    message="The first procedure parameter must not have a leading comma.",
                    evidence=[line],
                    check_kind="style",
                )
            )
        elif index > 0 and not stripped.startswith(","):
            issues.append(
                SqlFormattingIssue(
                    code="procedure_parameter_missing_leading_comma",
                    severity="error",
                    message="Procedure parameters after the first must have leading commas.",
                    evidence=[line],
                    check_kind="style",
                )
            )
    return issues


def _check_select_leading_commas(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    lines = _masked_sql(sql).splitlines()
    raw_lines = sql.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not re.match(r"^\s*SELECT\b", line, flags=re.IGNORECASE):
            index += 1
            continue
        select_indent = len(line) - len(line.lstrip(" "))
        column_seen = bool(re.search(r"\bSELECT\s+\S+", line, flags=re.IGNORECASE))
        index += 1
        while index < len(lines):
            candidate = lines[index]
            stripped = candidate.strip()
            if not stripped:
                index += 1
                continue
            if re.match(
                r"^(INTO|FROM|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|UNION|END|ELSE)\b",
                stripped,
                flags=re.IGNORECASE,
            ):
                break
            if column_seen and _looks_like_select_continuation_line(candidate):
                index += 1
                continue
            current_indent = len(candidate) - len(candidate.lstrip(" "))
            if current_indent >= select_indent and column_seen and not candidate.lstrip().startswith(","):
                issues.append(
                    SqlFormattingIssue(
                        code="select_column_missing_leading_comma",
                        severity="error",
                        message="SELECT columns after the first must use leading commas.",
                        evidence=[raw_lines[index] if index < len(raw_lines) else candidate],
                        check_kind="style",
                    )
                )
                break
            column_seen = True
            index += 1
    return issues


def _looks_like_select_continuation_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped or stripped.startswith(","):
        return False
    if re.match(
        r"^(AND|OR|WHEN|ELSE|END|INTO|FROM|WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|UNION)\b",
        stripped,
        flags=re.IGNORECASE,
    ):
        return False
    if stripped.startswith(("+", "-", "*", "/", ")", ".")):
        return True
    if re.match(r"^(PARTITION\s+BY|ORDER\s+BY)\b", stripped, flags=re.IGNORECASE):
        return True
    return stripped == ")"


def _check_insert_select_layout(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    for block in _extract_insert_column_blocks(sql):
        lines = _meaningful_insert_lines(block)
        if len(lines) < 8:
            continue
        single_lines = [line for line in lines if _looks_like_single_insert_column_line(line)]
        if len(single_lines) >= max(8, int(len(lines) * 0.8)):
            issues.append(
                SqlFormattingIssue(
                    code="insert_select_single_column_per_line",
                    severity="error",
                    message="Wide INSERT ... SELECT mappings must retain grouped horizontal layout.",
                    evidence=single_lines[:6],
                    check_kind="style",
                )
            )
    issues.extend(_check_insert_select_value_layout(sql))
    return issues


def _check_insert_select_value_layout(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    for statement in _extract_insert_select_statements(sql):
        target_block = statement["target_block"]
        if len(_split_top_level_commas(target_block)) < 8:
            continue
        target_lines = _meaningful_insert_lines(target_block)
        if _target_columns_are_vertical(target_lines):
            continue
        select_lines = _meaningful_select_value_lines(statement["select_block"])
        if len(select_lines) < 8:
            continue
        single_lines = [line for line in select_lines if _looks_like_single_select_value_line(line)]
        if len(single_lines) >= max(8, int(len(select_lines) * 0.8)):
            issues.append(
                SqlFormattingIssue(
                    code="insert_select_value_list_verticalized",
                    severity="error",
                    message="Wide SELECT value lists must retain grouped horizontal mapping rows.",
                    evidence=single_lines[:6],
                    check_kind="style",
                )
            )
    return issues


def _extract_insert_column_blocks(sql: str) -> List[str]:
    masked = _masked_sql(sql)
    blocks = []
    for match in re.finditer(r"\bINSERT\s+INTO\b", masked, flags=re.IGNORECASE):
        open_index = masked.find("(", match.end())
        if open_index < 0:
            continue
        close_index = _find_matching_parenthesis(masked, open_index)
        if close_index < 0:
            continue
        if re.search(r"\bSELECT\b", masked[close_index + 1 : close_index + 2500], flags=re.IGNORECASE):
            blocks.append(sql[open_index + 1 : close_index])
    return blocks


def _extract_insert_select_statements(sql: str) -> List[Dict[str, str]]:
    masked = _masked_sql(sql)
    statements = []
    for match in re.finditer(r"\bINSERT\s+INTO\b", masked, flags=re.IGNORECASE):
        open_index = masked.find("(", match.end())
        if open_index < 0:
            continue
        close_index = _find_matching_parenthesis(masked, open_index)
        if close_index < 0:
            continue
        select_match = re.search(r"\bSELECT\b", masked[close_index + 1 :], flags=re.IGNORECASE)
        if not select_match:
            continue
        select_start = close_index + 1 + select_match.start()
        from_index = _find_top_level_keyword(masked, select_start, "FROM")
        if from_index < 0:
            continue
        statements.append(
            {
                "target_block": sql[open_index + 1 : close_index],
                "select_block": sql[select_start:from_index],
            }
        )
    return statements


def _meaningful_insert_lines(block: str) -> List[str]:
    return [
        line.strip().rstrip(",")
        for line in block.splitlines()
        if line.strip() and line.strip() not in {"(", ")"}
    ]


def _meaningful_select_value_lines(block: str) -> List[str]:
    lines = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped.upper() == "SELECT":
            continue
        if stripped.upper().startswith("SELECT "):
            stripped = stripped[7:].strip()
        lines.append(stripped.rstrip(","))
    return lines


def _target_columns_are_vertical(lines: Sequence[str]) -> bool:
    values = [line for line in lines if _looks_like_single_insert_column_line(line)]
    return len(values) >= max(8, int(len(lines) * 0.8))


def _looks_like_single_insert_column_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith(","):
        stripped = stripped[1:].strip()
    return bool(
        re.fullmatch(
            r"(?:\[[A-Z_][A-Z0-9_@$#]*\]|[A-Z_][A-Z0-9_@$#]*)(?:\s+AS\s+\w+)?",
            stripped,
            flags=re.IGNORECASE,
        )
    )


def _looks_like_single_select_value_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith(","):
        stripped = stripped[1:].strip()
    if not stripped or stripped.startswith(("+", "-", "*", "/", ")")) or "," in stripped:
        return False
    if re.match(r"^(PARTITION\s+BY|ORDER\s+BY|WHEN|ELSE|END)\b", stripped, flags=re.IGNORECASE):
        return False
    if re.search(r"\b(OVER|CASE)\b", stripped, flags=re.IGNORECASE) and not re.search(
        r"\bEND\b",
        stripped,
        flags=re.IGNORECASE,
    ):
        return False
    return bool(
        re.search(
            r"^(@|:|'|[A-Z_][A-Z0-9_@$#]*\.|[A-Z_][A-Z0-9_@$#]*\()",
            stripped,
            flags=re.IGNORECASE,
        )
    )


def _split_top_level_commas(value: str) -> List[str]:
    tokens, _ = _scan_sql_tokens(value)
    items = []
    start = 0
    for token in tokens:
        if token.text == "," and token.depth == 0:
            item = value[start:token.start].strip()
            if item:
                items.append(item)
            start = token.end
    tail = value[start:].strip()
    if tail:
        items.append(tail)
    return items


def _find_top_level_keyword(sql: str, start: int, keyword: str) -> int:
    tokens, _ = _scan_sql_tokens(sql[start:])
    for token in tokens:
        if token.depth == 0 and token.normalized == keyword.upper():
            return start + token.start
    return -1


def _find_matching_parenthesis(sql: str, open_index: int) -> int:
    tokens, _ = _scan_sql_tokens(sql[open_index:])
    for token in tokens:
        if token.text == ")" and token.depth == 0:
            return open_index + token.start
    return -1


def _check_cte_temp_table_introduction(
    original: str,
    formatted: str,
    *,
    cte_temp_table_reason: str | None,
) -> List[SqlFormattingIssue]:
    original_masked = _masked_sql(original)
    formatted_masked = _masked_sql(formatted)
    reason_allowed = _has_cte_temp_table_exception_reason(cte_temp_table_reason)
    issues: List[SqlFormattingIssue] = []
    introduced_ctes = sorted(
        _extract_statement_cte_names(formatted_masked) - _extract_statement_cte_names(original_masked)
    )
    if introduced_ctes:
        issues.append(
            SqlFormattingIssue(
                code="cte_exception_reason_recorded" if reason_allowed else "cte_introduced_without_reason",
                severity="warning" if reason_allowed else "error",
                message="CTE introduction requires a concrete recorded reason and remains a token-stream change.",
                evidence=[cte_temp_table_reason or "", *introduced_ctes[:8]],
                check_kind="style",
            )
        )
    introduced_temp = sorted(
        _extract_temp_table_names(formatted_masked) - _extract_temp_table_names(original_masked)
    )
    if introduced_temp:
        issues.append(
            SqlFormattingIssue(
                code=(
                    "temp_table_exception_reason_recorded"
                    if reason_allowed
                    else "temp_table_introduced_without_reason"
                ),
                severity="warning" if reason_allowed else "error",
                message="Temporary-table introduction requires a concrete reason and remains a token-stream change.",
                evidence=[cte_temp_table_reason or "", *introduced_temp[:8]],
                check_kind="style",
            )
        )
    return issues


def _extract_statement_cte_names(masked_sql: str) -> set[str]:
    name = r"([A-Z_][A-Z0-9_@$#]*)\s*(?:\([^)]*\)\s*)?AS\s*\("
    first = rf"(?:^|;|\bBEGIN(?:\s+TRY|\s+CATCH)?\b)\s*;?\s*WITH\s+{name}"
    names = {
        match.group(1).upper()
        for match in re.finditer(first, masked_sql, flags=re.IGNORECASE | re.DOTALL)
    }
    if names:
        names.update(
            match.group(1).upper()
            for match in re.finditer(rf",\s*{name}", masked_sql, flags=re.IGNORECASE | re.DOTALL)
        )
    return names


def _extract_temp_table_names(masked_sql: str) -> set[str]:
    return {
        match.group(1).upper()
        for match in re.finditer(
            r"(?<![A-Z0-9_#])((?:##|#)[A-Z_][A-Z0-9_]*)\b",
            masked_sql,
            flags=re.IGNORECASE,
        )
    }


def _has_cte_temp_table_exception_reason(reason: str | None) -> bool:
    normalized = re.sub(r"\s+", " ", str(reason or "").strip()).lower()
    if len(normalized) < 12:
        return False
    if re.search(
        r"\b(?:not|no|without)\s+(?:explicit|user\s+request|reason|evidence|recursive|recursion|reuse|"
        r"index(?:ing|es)?|statistics|large\s+intermediate|measured\s+performance|performance\s+evidence)\b",
        normalized,
    ):
        return False
    patterns = [
        r"\bexplicit\s+user\s+request\b",
        r"\buser\s+(?:asked|requested|requires?)\b",
        r"\brecurs(?:ive|ion)\b",
        r"\brepeated\s+reuse\b",
        r"\bmultiple\s+statements?\b",
        r"\bneeds?\s+index(?:ing|es)?\b",
        r"\bstatistics\b",
        r"\blarge\s+intermediate\b",
        r"\bprocedural\s+staging\b",
        r"\bmeasured\s+performance\b",
        r"\bperformance\s+evidence\b",
    ]
    return any(re.search(pattern, normalized) for pattern in patterns)


def _check_if_exists_where_subquery(tokens: Sequence[_SqlToken]) -> List[SqlFormattingIssue]:
    code_tokens = [item for item in tokens if item.kind not in {"line_comment", "block_comment"}]
    issues = []
    for position, token in enumerate(code_tokens):
        if token.normalized != "IF":
            continue
        exists = position + 1
        if exists >= len(code_tokens) or code_tokens[exists].normalized != "EXISTS":
            continue
        open_position = exists + 1
        if open_position >= len(code_tokens) or code_tokens[open_position].text != "(":
            continue
        outer_depth = code_tokens[open_position].depth + 1
        close_position = next(
            (
                index
                for index in range(open_position + 1, len(code_tokens))
                if code_tokens[index].text == ")" and code_tokens[index].depth == outer_depth - 1
            ),
            len(code_tokens),
        )
        where_position = next(
            (
                index
                for index in range(open_position + 1, close_position)
                if code_tokens[index].normalized == "WHERE" and code_tokens[index].depth == outer_depth
            ),
            None,
        )
        if where_position is None:
            continue
        if any(
            item.normalized == "SELECT" and item.depth > outer_depth
            for item in code_tokens[where_position + 1 : close_position]
        ):
            issues.append(
                SqlFormattingIssue(
                    code="if_exists_where_subquery",
                    severity="error",
                    message="Do not nest a subquery under the top-level WHERE of an IF EXISTS guard.",
                    evidence=[f"offset={code_tokens[where_position].start}"],
                    check_kind="style",
                )
            )
    return issues


def _check_join_indentation(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    masked_lines = _masked_sql(sql).splitlines()
    raw_lines = sql.splitlines()
    in_join = False
    join_indent = -1
    condition_indent = -1
    for index, line in enumerate(masked_lines):
        stripped = line.lstrip(" ")
        raw = raw_lines[index] if index < len(raw_lines) else line
        if re.match(r"(LEFT\s+OUTER\s+JOIN|RIGHT\s+OUTER\s+JOIN|FULL\s+OUTER\s+JOIN|INNER\s+JOIN|JOIN)\b", stripped, flags=re.IGNORECASE):
            in_join = True
            condition_indent = -1
            join_indent = len(line) - len(stripped)
            if join_indent % 4 != 0 or join_indent < 8:
                issues.append(
                    SqlFormattingIssue(
                        code="join_indentation",
                        severity="error",
                        message="JOIN lines must use the contract indentation.",
                        evidence=[raw],
                        check_kind="style",
                    )
                )
            continue
        if in_join and re.match(r"(WHERE|GROUP\s+BY|ORDER\s+BY|HAVING|UNION|SELECT|FROM)\b", stripped, flags=re.IGNORECASE):
            in_join = False
        if in_join and re.match(r"(ON|AND)\b", stripped, flags=re.IGNORECASE) and "=" in stripped:
            leading = len(line) - len(stripped)
            if leading < 10 or (join_indent >= 0 and leading < join_indent + 13):
                issues.append(
                    SqlFormattingIssue(
                        code="join_condition_indentation",
                        severity="error",
                        message="JOIN ON/AND conditions must be indented beneath JOIN.",
                        evidence=[raw],
                        check_kind="style",
                    )
                )
            if condition_indent < 0:
                condition_indent = leading
            elif leading != condition_indent:
                issues.append(
                    SqlFormattingIssue(
                        code="join_condition_alignment",
                        severity="error",
                        message="JOIN conditions for one JOIN must align.",
                        evidence=[raw],
                        check_kind="style",
                    )
                )
    return issues


def _check_case_parentheses(sql: str, tokens: Sequence[_SqlToken]) -> List[SqlFormattingIssue]:
    issues = []
    masked_lines = _masked_sql(sql).splitlines()
    for line in masked_lines:
        if re.search(r"\bCASE\b", line, flags=re.IGNORECASE) and not re.search(
            r"\(\s*CASE\b",
            line,
            flags=re.IGNORECASE,
        ):
            issues.append(
                SqlFormattingIssue(
                    code="case_not_parenthesized",
                    severity="error",
                    message="CASE expressions must be wrapped as (CASE ... END).",
                    evidence=[line.strip()],
                    check_kind="style",
                )
            )
    return issues


def _contains_localized_text(value: str) -> bool:
    return any(ord(char) > 127 for char in value)


def _has_replacement_damage_markers(value: str) -> bool:
    return "\ufffd" in value or bool(re.search(r"\?{2,}", value))


def _sequence_diff(original: Sequence[str], formatted: Sequence[str], limit: int = 6) -> List[str]:
    evidence = []
    for index in range(max(len(original), len(formatted))):
        before = original[index] if index < len(original) else "<END>"
        after = formatted[index] if index < len(formatted) else "<END>"
        if before != after:
            evidence.append(f"index={index}: original={before!r}, formatted={after!r}")
        if len(evidence) >= limit:
            break
    return evidence


def _has_errors(issues: Iterable[SqlFormattingIssue]) -> bool:
    return any(item.severity == "error" for item in issues)


def _json_contract_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _json_contract_value(item) for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))}
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return [_json_contract_value(item) for item in value]
    if isinstance(value, os.PathLike):
        return str(value)
    return value


def _verification_id(**values: Any) -> str:
    payload = json.dumps(_json_contract_value(values), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _path_is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Verify SQL formatting preservation and style.")
    parser.add_argument("--original", default="", help="Path to original SQL text.")
    parser.add_argument("--formatted", required=True, help="Path to formatted SQL text.")
    parser.add_argument("--style-contract", default="", help="Optional style-contract path.")
    parser.add_argument(
        "--operation",
        choices=["formatting", "generation", "refactor"],
        default="formatting",
    )
    args = parser.parse_args()
    if args.operation != "generation" and not args.original:
        parser.error("--original is required for formatting and refactor operations")
    result = verify_sql_formatting_style(
        Path(args.original) if args.original else "",
        Path(args.formatted),
        style_contract_path=args.style_contract or None,
        operation=args.operation,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
