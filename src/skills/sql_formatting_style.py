import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

from src.contracts import HarnessResult


HOST_SQL_FORMATTING_SKILL = Path.home() / ".codex" / "skills" / "sql-formatting" / "SKILL.md"
POWERBUILDER_SQL_KEYWORD_PATTERN = re.compile(r"\b(SELECT|UPDATE|DELETE|INSERT)\b", re.IGNORECASE)


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


def verify_sql_formatting_style(
    original_sql: str,
    formatted_sql: str,
    *,
    style_contract_path: str | os.PathLike[str] | None = None,
    cte_temp_table_reason: str | None = None,
) -> HarnessResult:
    """Verify SQL formatting output against the host-local sql-formatting contract."""
    original = str(original_sql or "")
    formatted = str(formatted_sql or "")
    preservation_issues = _check_preservation(original, formatted)
    style_issues = _check_style(original, formatted, cte_temp_table_reason=cte_temp_table_reason)
    issues = preservation_issues + style_issues
    mechanical_passed = not any(issue.severity == "error" for issue in issues)
    metadata = {
        "harness": "sql-formatting-style-harness",
        "style_contract_source": resolve_style_contract_source(style_contract_path),
        "mechanical_checks": {
            "status": "passed" if mechanical_passed else "blocked",
            "preservation_issues": [issue.to_dict() for issue in preservation_issues],
            "style_issues": [issue.to_dict() for issue in style_issues],
        },
        "semantic_checks": {
            "status": "not_proven",
            "reason": (
                "Regex checks cannot prove DB execution-plan, rowset, transaction, trigger, "
                "collation, or stored procedure side-effect equivalence."
            ),
            "requires": [
                "database-backed execution comparison",
                "review of schema-dependent rewrites",
                "STATISTICS IO/TIME or result-set diff when performance or semantics matter",
            ],
        },
        "token_optimizer_status": "passthrough",
        "token_optimizer_status_reason": (
            "Token optimizer not used because SQL/stored procedure text is contract-sensitive and was not compressed."
        ),
        "not_used_reason": (
            "Token optimizer not used because SQL/stored procedure text is contract-sensitive and was not compressed."
        ),
        "cte_temp_table_reason": cte_temp_table_reason or "",
    }
    return HarnessResult(
        success=mechanical_passed,
        stdout=json.dumps(
            {
                "status": "passed" if mechanical_passed else "blocked",
                "issue_count": len(issues),
                "error_count": sum(1 for issue in issues if issue.severity == "error"),
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
        stderr="" if mechanical_passed else "SQL formatting verification blocked by mechanical issues.",
        exit_code=0 if mechanical_passed else 1,
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
        line = lines[index]
        match = POWERBUILDER_SQL_KEYWORD_PATTERN.search(line)
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
        fragment_id = f"{Path(source_name).name or 'powerbuilder'}:{start + 1}:{match.group(1).upper()}"
        fragments.append(
            {
                "fragment_id": fragment_id,
                "source_name": source_name,
                "keyword": match.group(1).upper(),
                "start_line": start + 1,
                "end_line": end + 1,
                "sql_text": sql_text,
                "token_optimizer_status": "passthrough",
                "token_optimizer_status_reason": (
                    "Token optimizer not used because SQL/stored procedure text is contract-sensitive and was not compressed."
                ),
            }
        )
        index = end + 1
    return fragments


def build_powerbuilder_sql_validation_plan(
    *,
    pbl_root: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    pblscripter_path: str | os.PathLike[str] = r"C:\PblScripter\Export-PBL.ps1",
) -> Dict[str, Any]:
    """Return a bounded no-write-to-source validation plan for PB-exported SQL fragments."""
    export_dir = Path(output_dir) / "powerbuilder_export"
    fragments_dir = Path(output_dir) / "sql_fragments"
    guard = validate_powerbuilder_output_dir(source_root=pbl_root, output_dir=output_dir)
    return {
        "status": "planned" if guard["allowed"] else "blocked",
        "pbl_root": str(pbl_root),
        "pblscripter_path": str(pblscripter_path),
        "output_dir": str(output_dir),
        "output_guard": guard,
        "write_boundary": {
            "allowed": [str(export_dir), str(fragments_dir)],
            "forbidden": [str(pbl_root), r"C:\GWERP"],
            "policy": "Do not write to C:\\GWERP or the source PBL tree; exports and fragments go under output_dir only.",
        },
        "steps": [
            "Confirm PblScripter invocation syntax with its local help or existing wrapper usage.",
            "Export PBL objects from pbl_root into output_dir/powerbuilder_export.",
            "Scan exported .srw/.sru/.srd/.txt files for SELECT/UPDATE/DELETE/INSERT fragments.",
            "Keep extracted SQL fragments as passthrough text under output_dir/sql_fragments.",
            "Format each fragment with host-local sql-formatting.",
            "Run verify_sql_formatting_style(original_fragment, formatted_fragment) for each pair.",
            "Report blocked fragments with source file and line span; do not claim DB semantics without DB-backed checks.",
        ],
        "current_pass_scope": "bounded hook and fixture tests only; broad C:\\GWERP sweep is follow-up unless explicitly run.",
    }


def validate_powerbuilder_output_dir(
    *,
    source_root: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
) -> Dict[str, Any]:
    """Validate that PB probe output will not be written under source-controlled PB roots."""
    source = Path(source_root).expanduser().resolve()
    output = Path(output_dir).expanduser().resolve()
    forbidden_roots = [source, Path(r"C:\GWERP").resolve()]
    violations = []
    for root in forbidden_roots:
        if _path_is_relative_to(output, root):
            violations.append(str(root))
    return {
        "allowed": not violations,
        "source_root": str(source),
        "output_dir": str(output),
        "forbidden_roots": [str(root) for root in forbidden_roots],
        "violations": violations,
        "policy": "output_dir must be outside source_root and outside C:\\GWERP before any mkdir or artifact write",
    }


def resolve_style_contract_source(
    style_contract_path: str | os.PathLike[str] | None = None,
) -> Dict[str, Any]:
    candidates = []
    if style_contract_path:
        candidates.append(Path(style_contract_path).expanduser())
    candidates.append(Path(os.environ.get("CODEX_HOME", str(Path.home() / ".codex"))) / "skills" / "sql-formatting" / "SKILL.md")
    candidates.append(HOST_SQL_FORMATTING_SKILL)
    candidates.append(Path(__file__).resolve().parents[2] / "skills" / "sql_formatting_style_harness" / "references" / "usage.md")

    seen = set()
    for path in candidates:
        key = str(path).lower()
        if key in seen:
            continue
        seen.add(key)
        if path.is_file():
            return {
                "kind": "host-local-sql-formatting-skill" if "sql-formatting" in path.as_posix() else "packaged-fallback-reference",
                "path": str(path),
                "sha256": _sha256(path),
                "available": True,
            }
    fallback = candidates[-1]
    return {
        "kind": "packaged-fallback-reference",
        "path": str(fallback),
        "sha256": "",
        "available": False,
    }


def _check_preservation(original: str, formatted: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    localized_damage = _localized_text_damage_issue(original, formatted)
    if localized_damage:
        issues.append(
            SqlFormattingIssue(
                code="localized_text_damaged",
                severity="error",
                message="Localized business text from the original SQL appears to be damaged or replaced.",
                evidence=localized_damage,
            )
        )

    original_literals = _extract_string_literals(original)
    formatted_literals = _extract_string_literals(formatted)
    if re.search(r"\bDBO\.F_BA011T_FIND_SUBNM\s*\(", original, flags=re.IGNORECASE):
        formatted_literals = _without_allowed_ba011t_empty_literal(original_literals, formatted_literals)
    if sorted(original_literals) != sorted(formatted_literals):
        issues.append(
            SqlFormattingIssue(
                code="string_literals_changed",
                severity="error",
                message="String literal multiset changed; localized and business values must be preserved exactly.",
                evidence=_diff_sample(original_literals, formatted_literals),
            )
        )

    original_localized = [value for value in original_literals if _contains_localized_text(value)]
    formatted_localized = [value for value in formatted_literals if _contains_localized_text(value)]
    if sorted(original_localized) != sorted(formatted_localized):
        issues.append(
            SqlFormattingIssue(
                code="localized_literals_changed",
                severity="error",
                message="Localized string literals changed.",
                evidence=_diff_sample(original_localized, formatted_localized),
            )
        )

    comment_issue = _comment_preservation_issue(original, formatted)
    if comment_issue is not None:
        issues.append(
            SqlFormattingIssue(
                code="comments_changed",
                severity="error",
                message="Comments changed, were removed, or were uncommented.",
                evidence=comment_issue,
            )
        )

    for code, label, extractor in [
        ("predicates_changed", "WHERE/HAVING predicates", _extract_predicates),
        ("join_conditions_changed", "JOIN conditions", _extract_join_conditions),
        ("calculations_changed", "calculation expressions", _extract_calculations),
    ]:
        original_items = extractor(original)
        formatted_items = extractor(formatted)
        if sorted(original_items) != sorted(formatted_items):
            issues.append(
                SqlFormattingIssue(
                    code=code,
                    severity="error",
                    message=f"{label} changed or were lost.",
                    evidence=_diff_sample(original_items, formatted_items),
                )
            )

    if _else_count(original) < _else_count(formatted):
        issues.append(
            SqlFormattingIssue(
                code="arbitrary_else_added",
                severity="error",
                message="Formatted SQL contains more ELSE tokens than the original.",
                evidence=[f"original_else={_else_count(original)}", f"formatted_else={_else_count(formatted)}"],
            )
        )
    return issues


def _check_style(original: str, formatted: str, *, cte_temp_table_reason: str | None = None) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    unprotected = _strip_literals_and_comments(formatted)

    if _has_unterminated_string_literal(formatted):
        issues.append(
            SqlFormattingIssue(
                code="unterminated_string_literal",
                severity="error",
                message="Formatted SQL appears to contain an unterminated string literal.",
                evidence=["single-quoted string did not close before the end of SQL text"],
                check_kind="style",
            )
        )

    lowercase_tokens = _lowercase_sql_tokens(unprotected)
    if lowercase_tokens:
        issues.append(
            SqlFormattingIssue(
                code="identifiers_not_uppercase",
                severity="error",
                message="SQL identifiers/keywords outside literals and comments must be uppercase.",
                evidence=lowercase_tokens[:10],
            )
        )

    issues.extend(_check_alias_rules(formatted))
    issues.extend(_check_procedure_parameter_layout(formatted))
    issues.extend(_check_select_leading_commas(formatted))
    issues.extend(_check_insert_select_layout(formatted))
    issues.extend(_check_cte_temp_table_introduction(original, formatted, cte_temp_table_reason=cte_temp_table_reason))
    issues.extend(_check_if_exists_where_subquery(formatted))
    issues.extend(_check_join_indentation(formatted))
    issues.extend(_check_case_parentheses(formatted))
    issues.extend(_check_ba011t_conversion(original, formatted))
    return issues


def _extract_string_literals(sql: str) -> List[str]:
    return re.findall(r"'(?:''|[^'])*'", sql, flags=re.DOTALL)


def _has_unterminated_string_literal(sql: str) -> bool:
    in_string = False
    in_line_comment = False
    in_block_comment = False
    index = 0
    while index < len(sql):
        char = sql[index]
        next_char = sql[index + 1] if index + 1 < len(sql) else ""

        if in_line_comment:
            if char in "\r\n":
                in_line_comment = False
            index += 1
            continue

        if in_block_comment:
            if char == "*" and next_char == "/":
                in_block_comment = False
                index += 2
            else:
                index += 1
            continue

        if not in_string and char == "-" and next_char == "-":
            in_line_comment = True
            index += 2
            continue

        if not in_string and char == "/" and next_char == "*":
            in_block_comment = True
            index += 2
            continue

        if char == "'":
            if in_string and next_char == "'":
                index += 2
                continue
            in_string = not in_string

        index += 1
    return in_string


def _extract_comments(sql: str) -> List[str]:
    return re.findall(r"--[^\r\n]*|/\*.*?\*/", sql, flags=re.DOTALL)


def _extract_comment_records(sql: str) -> List[Dict[str, str]]:
    records = []
    for match in re.finditer(r"--[^\r\n]*|/\*.*?\*/", sql, flags=re.DOTALL):
        text = match.group(0)
        records.append(
            {
                "shape": "--" if text.startswith("--") else "/* */",
                "text": text,
            }
        )
    return records


def _comment_preservation_issue(original: str, formatted: str) -> List[str] | None:
    original_comments = _extract_comment_records(original)
    formatted_comments = _extract_comment_records(formatted)
    if len(original_comments) != len(formatted_comments):
        return [
            f"comment_count: original={len(original_comments)}, formatted={len(formatted_comments)}",
            *_diff_sample(
                [item["text"] for item in original_comments],
                [item["text"] for item in formatted_comments],
            ),
        ]

    evidence = []
    for index, (before, after) in enumerate(zip(original_comments, formatted_comments), start=1):
        if before["shape"] != after["shape"]:
            evidence.append(f"comment_{index}_shape: original={before['shape']}, formatted={after['shape']}")
            continue
        if _normalized_comment_for_preservation(before["text"]) != _normalized_comment_for_preservation(after["text"]):
            evidence.append(f"comment_{index}: original={before['text']!r}, formatted={after['text']!r}")
    return evidence or None


def _normalized_comment_for_preservation(comment: str) -> str:
    if comment.startswith("--"):
        body = comment[2:].strip()
        prefix = "--"
    else:
        body = comment[2:-2].strip()
        prefix = "/* */"
    if not _looks_like_commented_sql(body):
        return f"{prefix}{body}"

    literals: List[str] = []

    def preserve_literal(match: re.Match[str]) -> str:
        literals.append(match.group(0))
        return f"__SQL_LITERAL_{len(literals) - 1}__"

    normalized = re.sub(r"'(?:''|[^'])*'", preserve_literal, body, flags=re.DOTALL)
    normalized = re.sub(
        r"\b[A-Za-z_][A-Za-z0-9_@$#]*\s*\.",
        "ALIAS.",
        normalized,
    )
    normalized = re.sub(r"\s*(=|<>|!=|<=|>=)\s*", r"\1", normalized)
    normalized = re.sub(r"\s+", " ", normalized.strip()).upper()
    for index, literal in enumerate(literals):
        normalized = normalized.replace(f"__SQL_LITERAL_{index}__", literal)
    return f"{prefix}{normalized}"


def _looks_like_commented_sql(body: str) -> bool:
    if not body:
        return False
    return bool(
        re.match(r"^(AND|OR|WHERE|HAVING|ON|JOIN|SELECT|UPDATE|DELETE|INSERT|FROM)\b", body.strip(), flags=re.IGNORECASE)
        and re.search(r"(=|<>|!=|<=|>=|\bLIKE\b|\bBETWEEN\b|\bIN\s*\()", body, flags=re.IGNORECASE)
    )


def _strip_literals_and_comments(sql: str) -> str:
    stripped = re.sub(r"'(?:''|[^'])*'", "''", sql, flags=re.DOTALL)
    return re.sub(r"--[^\r\n]*|/\*.*?\*/", "", stripped, flags=re.DOTALL)


def _strip_comments(sql: str) -> str:
    return re.sub(r"--[^\r\n]*|/\*.*?\*/", "", sql, flags=re.DOTALL)


def _normalized_contract_line(line: str, *, preserve_literals: bool = False) -> str:
    without_comments = re.sub(r"--.*$", "", line)
    without_literals = without_comments if preserve_literals else re.sub(r"'(?:''|[^'])*'", "?", without_comments)
    collapsed = re.sub(r"\s+", " ", without_literals.strip())
    collapsed = re.sub(r"\s*(=|<>|!=|<=|>=)\s*", r"\1", collapsed)
    return re.sub(r"\s+;", ";", collapsed).upper()


def _extract_predicates(sql: str) -> List[str]:
    lines = _strip_comments(sql).splitlines()
    result = []
    in_predicate_block = False
    predicate_operator = re.compile(r"(=|<>|!=|<=|>=|\bLIKE\b|\bBETWEEN\b|\bIN\s*\()", re.IGNORECASE)
    for line in lines:
        stripped = line.strip()
        upper = stripped.upper()
        if re.match(r"^(WHERE|HAVING)\b", upper):
            in_predicate_block = True
        elif re.match(r"^(GROUP BY|ORDER BY|UNION|SELECT|FROM|JOIN|LEFT OUTER JOIN|INNER JOIN|ON)\b", upper):
            in_predicate_block = False
        if in_predicate_block and re.match(r"^(WHERE|AND|OR|HAVING)\b", upper) and predicate_operator.search(line):
            result.append(_normalized_contract_line(line, preserve_literals=True))
    return result


def _extract_join_conditions(sql: str) -> List[str]:
    lines = _strip_literals_and_comments(sql).splitlines()
    result = []
    in_join = False
    current_join_is_ba011t = False
    for line in lines:
        upper = line.upper()
        if re.search(r"\bJOIN\b", upper):
            in_join = True
            current_join_is_ba011t = "BA011T" in upper
            if not current_join_is_ba011t:
                result.extend(_extract_inline_join_conditions(line))
            continue
        if in_join and re.match(r"^\s*(WHERE|GROUP BY|ORDER BY|HAVING|UNION|SELECT|FROM)\b", upper):
            in_join = False
            current_join_is_ba011t = False
        if in_join and not current_join_is_ba011t and re.match(r"^\s*(ON|AND|OR)\b", upper) and "=" in line:
            result.append(_normalized_contract_line(line))
    return result


def _extract_inline_join_conditions(line: str) -> List[str]:
    if not re.search(r"\bON\b", line, flags=re.IGNORECASE):
        return []
    after_on = re.split(r"\bON\b", line, maxsplit=1, flags=re.IGNORECASE)[1]
    pieces = re.split(r"\b(AND|OR)\b", after_on, flags=re.IGNORECASE)
    conditions: List[str] = []
    first = pieces[0].strip()
    if first and "=" in first:
        conditions.append(_normalized_contract_line(f"ON {first}"))
    for index in range(1, len(pieces), 2):
        operator = pieces[index].upper()
        condition = pieces[index + 1].strip() if index + 1 < len(pieces) else ""
        if condition and "=" in condition:
            conditions.append(_normalized_contract_line(f"{operator} {condition}"))
    return conditions


def _extract_calculations(sql: str) -> List[str]:
    result = []
    for line in _strip_literals_and_comments(sql).splitlines():
        if re.search(r"[A-Z0-9_@\]\)]\s*[\+\-\*/]\s*[A-Z0-9_@\[\(]", line, flags=re.IGNORECASE):
            result.append(_normalized_contract_line(line).lstrip(", "))
    return result


def _else_count(sql: str) -> int:
    return len(re.findall(r"\bELSE\b", _strip_literals_and_comments(sql), flags=re.IGNORECASE))


def _contains_localized_text(value: str) -> bool:
    return bool(re.search(r"[^\x00-\x7F]", value))


def _localized_text_damage_issue(original: str, formatted: str) -> List[str]:
    original_fragments = _extract_localized_fragments(original)
    if not original_fragments:
        return []
    formatted_fragments = _extract_localized_fragments(formatted)
    original_text = " ".join(original_fragments)
    formatted_text = " ".join(formatted_fragments)
    evidence = []
    if original_fragments and not formatted_fragments and _has_replacement_damage_markers(formatted):
        evidence.append("original contains localized text but formatted output contains no localized text and has replacement markers")
    for fragment in original_fragments[:12]:
        if fragment not in formatted_text:
            evidence.append(f"missing_localized_fragment={fragment}")
        if len(evidence) >= 6:
            break
    if _contains_localized_text(original_text) and "\ufffd" in formatted:
        evidence.append("formatted output contains Unicode replacement character")
    return evidence[:8]


def _extract_localized_fragments(sql: str) -> List[str]:
    return re.findall(r"[^\x00-\x7F]{2,}", sql)


def _has_replacement_damage_markers(value: str) -> bool:
    return "\ufffd" in value or bool(re.search(r"\?{2,}", value))


def _check_alias_rules(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    unprotected = _strip_literals_and_comments(sql)
    outer_aliases = _extract_outer_table_aliases(unprotected)
    invalid_outer = [
        alias
        for alias in outer_aliases
        if _is_derived_internal_alias(alias) or not _is_allowed_outer_alias(alias)
    ]
    if invalid_outer:
        code = (
            "outer_query_uses_derived_table_internal_alias"
            if any(_is_derived_internal_alias(alias) for alias in invalid_outer)
            else "ad_hoc_outer_alias"
        )
        issues.append(
            SqlFormattingIssue(
                code=code,
                severity="error",
                message=(
                    "Outer query table aliases must follow the host SQL formatting contract "
                    "(A/A1, B/B1, C, D...); T/T1/TA1 are reserved for derived-table internals."
                ),
                evidence=invalid_outer[:8],
            )
        )
    table_qualifiers = _raw_table_qualifiers_after_aliasing(unprotected)
    if table_qualifiers:
        issues.append(
            SqlFormattingIssue(
                code="raw_table_qualifier_after_aliasing",
                severity="error",
                message="After a table has an alias, column references should use the alias rather than the raw table name.",
                evidence=table_qualifiers[:8],
            )
        )
    return issues


def _extract_outer_table_aliases(unprotected_sql: str) -> List[str]:
    aliases: List[str] = []
    depth = 0
    pending_derived_table = False
    for line in unprotected_sql.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        starts_derived = bool(
            re.match(
                r"^(?:FROM|(?:LEFT\s+OUTER|RIGHT\s+OUTER|FULL\s+OUTER|INNER|CROSS)?\s*JOIN)\s*\(",
                stripped,
                flags=re.IGNORECASE,
            )
        )
        if depth <= 0 and starts_derived:
            pending_derived_table = True

        depth += stripped.count("(") - stripped.count(")")
        if pending_derived_table:
            if depth <= 0:
                alias = _derived_table_alias_from_line(stripped)
                if alias:
                    aliases.append(alias)
                pending_derived_table = False
            continue

        if depth <= 0:
            match = re.match(
                r"^(?:FROM|(?:LEFT\s+OUTER|RIGHT\s+OUTER|FULL\s+OUTER|INNER|CROSS)?\s*JOIN)\s+"
                r"(?:\[?DBO\]?\.)?\[?[A-Z_][A-Z0-9_@$#]*\]?\s+(?:AS\s+)?([A-Z][A-Z0-9_]*)\b",
                stripped,
                flags=re.IGNORECASE,
            )
            if match:
                aliases.append(match.group(1).upper())
    return aliases


def _derived_table_alias_from_line(line: str) -> str:
    close_index = line.rfind(")")
    if close_index < 0:
        return ""
    tail = line[close_index + 1 :].strip()
    match = re.match(r"(?:AS\s+)?([A-Z][A-Z0-9_]*)\b", tail, flags=re.IGNORECASE)
    return match.group(1).upper() if match else ""


def _is_derived_internal_alias(alias: str) -> bool:
    return bool(re.fullmatch(r"T\d*|T[A-Z]\d+", alias.upper()))


def _is_allowed_outer_alias(alias: str) -> bool:
    upper = alias.upper()
    return bool(re.fullmatch(r"[A-SU-Z]\d*", upper))


def _raw_table_qualifiers_after_aliasing(unprotected_sql: str) -> List[str]:
    evidence = []
    for statement in _split_top_level_semicolons(unprotected_sql):
        table_names = []
        for match in re.finditer(
            r"\b(?:FROM|JOIN)[ \t]+(?:\[?DBO\]?\.)?\[?([A-Z_][A-Z0-9_@$#]*)\]?[ \t]+(?:AS[ \t]+)?([A-Z][A-Z0-9_]*)\b",
            statement,
            flags=re.IGNORECASE,
        ):
            table, alias = match.group(1).upper(), match.group(2).upper()
            if table != alias and not _is_sql_clause_keyword(alias):
                table_names.append(table)
        for table in sorted(set(table_names)):
            if re.search(rf"\b{re.escape(table)}\s*\.", statement, flags=re.IGNORECASE):
                evidence.append(f"{table}.")
    return evidence


def _is_sql_clause_keyword(token: str) -> bool:
    return token.upper() in {
        "WHERE",
        "JOIN",
        "LEFT",
        "RIGHT",
        "FULL",
        "INNER",
        "CROSS",
        "ON",
        "GROUP",
        "ORDER",
        "HAVING",
        "UNION",
        "EXCEPT",
        "INTERSECT",
    }


def _split_top_level_semicolons(sql: str) -> List[str]:
    statements: List[str] = []
    current: List[str] = []
    depth = 0
    for char in sql:
        if char == "(":
            depth += 1
        elif char == ")" and depth > 0:
            depth -= 1
        if char == ";" and depth == 0:
            statement = "".join(current).strip()
            if statement:
                statements.append(statement)
            current = []
            continue
        current.append(char)
    tail = "".join(current).strip()
    if tail:
        statements.append(tail)
    return statements


def _lowercase_sql_tokens(unprotected_sql: str) -> List[str]:
    tokens = []
    for match in re.finditer(r"(?<![A-Za-z0-9_@#])(@?[A-Za-z_][A-Za-z0-9_@$#]*)(?![A-Za-z0-9_])", unprotected_sql):
        token = match.group(1)
        if match.start(1) > 0 and unprotected_sql[match.start(1) - 1] == ":":
            continue
        if token.startswith("@@"):
            continue
        if any("a" <= char <= "z" for char in token):
            tokens.append(token)
    return sorted(set(tokens))


def _check_procedure_parameter_layout(sql: str) -> List[SqlFormattingIssue]:
    if not re.search(r"\bCREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\b", sql, flags=re.IGNORECASE):
        return []
    lines = sql.splitlines()
    issues: List[SqlFormattingIssue] = []
    proc_index = next(
        (index for index, line in enumerate(lines) if re.search(r"\bCREATE\s+(?:OR\s+ALTER\s+)?PROCEDURE\b", line, re.IGNORECASE)),
        -1,
    )
    if proc_index < 0:
        return []
    if "@" in lines[proc_index]:
        issues.append(
            SqlFormattingIssue(
                code="procedure_first_parameter_same_line",
                severity="error",
                message="First stored procedure parameter must be on the line after the procedure name.",
                evidence=[lines[proc_index].strip()],
            )
        )
    parameter_lines = []
    for line in lines[proc_index + 1 :]:
        if re.match(r"^\s*AS\b", line, flags=re.IGNORECASE):
            break
        if "@" in line and re.search(r"@\w+", line):
            parameter_lines.append(line)
    for index, line in enumerate(parameter_lines):
        stripped = line.lstrip()
        if index == 0:
            if stripped.startswith(","):
                issues.append(
                    SqlFormattingIssue(
                        code="procedure_first_parameter_leading_comma",
                        severity="error",
                        message="First stored procedure parameter must not use a leading comma.",
                        evidence=[line],
                    )
                )
        elif not stripped.startswith(","):
            issues.append(
                SqlFormattingIssue(
                    code="procedure_parameter_missing_leading_comma",
                    severity="error",
                    message="Stored procedure parameters after the first must use leading commas.",
                    evidence=[line],
                )
            )
    return issues


def _check_select_leading_commas(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    lines = sql.splitlines()
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
            if not stripped or stripped.startswith("--"):
                index += 1
                continue
            if re.match(r"^(INTO|FROM|WHERE|GROUP BY|ORDER BY|HAVING|UNION|END|ELSE)\b", stripped, flags=re.IGNORECASE):
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
                        evidence=[candidate],
                    )
                )
                break
            column_seen = True
            index += 1
    return issues


def _looks_like_select_continuation_line(line: str) -> bool:
    stripped = line.strip()
    if not stripped:
        return False
    if stripped.startswith(","):
        return False
    if re.match(r"^(AND|OR|WHEN|ELSE|END|INTO|FROM|WHERE|GROUP BY|ORDER BY|HAVING|UNION)\b", stripped, flags=re.IGNORECASE):
        return False
    if stripped.startswith(("+", "-", "*", "/", ")", ".")):
        return True
    if re.match(r"^(PARTITION\s+BY|ORDER\s+BY)\b", stripped, flags=re.IGNORECASE):
        return True
    if stripped == ")":
        return True
    return False


def _check_insert_select_layout(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    for block in _extract_insert_column_blocks(sql):
        lines = _meaningful_insert_lines(block)
        if len(lines) < 8:
            continue
        single_column_lines = [line for line in lines if _looks_like_single_insert_column_line(line)]
        if len(single_column_lines) >= max(8, int(len(lines) * 0.8)):
            issues.append(
                SqlFormattingIssue(
                    code="insert_select_single_column_per_line",
                    severity="error",
                    message=(
                        "Wide INSERT INTO ... SELECT mappings should use the existing grouped horizontal "
                        "stored-procedure layout, with long CASE/ROW_NUMBER/ISNULL expressions wrapped only "
                        "for that mapping instead of making the entire insert one target column per line."
                    ),
                    evidence=single_column_lines[:6],
                )
            )
    issues.extend(_check_insert_select_value_layout(sql))
    return issues


def _check_insert_select_value_layout(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    for statement in _extract_insert_select_statements(sql):
        target_block = statement["target_block"]
        select_block = statement["select_block"]
        target_lines = _meaningful_insert_lines(target_block)
        if _count_insert_target_columns(target_block) < 8:
            continue
        if _target_columns_are_vertical(target_lines):
            continue
        select_value_lines = _meaningful_select_value_lines(select_block)
        if len(select_value_lines) < 8:
            continue
        single_value_lines = [line for line in select_value_lines if _looks_like_single_select_value_line(line)]
        if len(single_value_lines) >= max(8, int(len(select_value_lines) * 0.8)):
            issues.append(
                SqlFormattingIssue(
                    code="insert_select_value_list_verticalized",
                    severity="error",
                    message=(
                        "Wide INSERT INTO ... SELECT mappings should keep target columns and SELECT values "
                        "in comparable grouped horizontal rows unless an individual long expression needs wrapping."
                    ),
                    evidence=single_value_lines[:6],
                )
            )
    return issues


def _check_cte_temp_table_introduction(
    original: str,
    formatted: str,
    *,
    cte_temp_table_reason: str | None = None,
) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    original_unprotected = _strip_literals_and_comments(original)
    formatted_unprotected = _strip_literals_and_comments(formatted)
    exception_allowed = _has_cte_temp_table_exception_reason(cte_temp_table_reason)

    introduced_ctes = sorted(_extract_statement_cte_names(formatted_unprotected) - _extract_statement_cte_names(original_unprotected))
    if introduced_ctes:
        if exception_allowed:
            issues.append(
                SqlFormattingIssue(
                    code="cte_exception_reason_recorded",
                    severity="warning",
                    message="A CTE was introduced with a recorded exception reason.",
                    evidence=[cte_temp_table_reason or "", *introduced_ctes[:4]],
                    check_kind="style",
                )
            )
        else:
            issues.append(
                SqlFormattingIssue(
                    code="cte_introduced_without_reason",
                    severity="error",
                    message=(
                        "Do not introduce a CTE in SQL recommendations or formatting by default. "
                        "Use the existing join/derived-table style unless recursion, repeated logic, an explicit request, "
                        "or another concrete reason is recorded."
                    ),
                    evidence=introduced_ctes[:8],
                )
            )

    introduced_temp_tables = sorted(
        _extract_temp_table_names(formatted_unprotected) - _extract_temp_table_names(original_unprotected)
    )
    if introduced_temp_tables:
        if exception_allowed:
            issues.append(
                SqlFormattingIssue(
                    code="temp_table_exception_reason_recorded",
                    severity="warning",
                    message="# temporary tables were introduced with a recorded exception reason.",
                    evidence=[cte_temp_table_reason or "", *introduced_temp_tables[:4]],
                    check_kind="style",
                )
            )
        else:
            issues.append(
                SqlFormattingIssue(
                    code="temp_table_introduced_without_reason",
                    severity="error",
                    message=(
                        "Do not introduce # temporary tables in SQL recommendations or formatting by default. "
                        "Use direct joins, derived tables, or aggregate subqueries unless repeated reuse, indexing/statistics, "
                        "procedural staging, measured performance evidence, or an explicit request justifies a temp table."
                    ),
                    evidence=introduced_temp_tables[:8],
                )
            )
    return issues


def _extract_statement_cte_names(unprotected_sql: str) -> set[str]:
    cte_name = r"([A-Z_][A-Z0-9_@$#]*)\s*(?:\([^)]*\)\s*)?AS\s*\("
    first_pattern = rf"(?:^|;|\bBEGIN(?:\s+TRY|\s+CATCH)?\b)\s*WITH\s+{cte_name}"
    extra_pattern = rf",\s*{cte_name}"
    names = {
        match.group(1).upper()
        for match in re.finditer(first_pattern, unprotected_sql, flags=re.IGNORECASE | re.DOTALL)
    }
    names.update(
        match.group(1).upper()
        for match in re.finditer(extra_pattern, unprotected_sql, flags=re.IGNORECASE | re.DOTALL)
    )
    return names


def _has_cte_temp_table_exception_reason(reason: str | None) -> bool:
    normalized = re.sub(r"\s+", " ", str(reason or "").strip()).lower()
    if len(normalized) < 12:
        return False
    negated_exception = (
        r"\b(?:not|no|without)\s+"
        r"(?:explicit|user\s+request|reason|evidence|recursive|recursion|reuse|repeated|"
        r"multiple\s+statements?|multi-?statement|index(?:ing|es)?|statistics|large\s+intermediate|"
        r"procedural\s+staging|measured\s+performance|performance\s+evidence)\b"
    )
    if re.search(negated_exception, normalized):
        return False
    exception_patterns = [
        r"\bexplicit\s+user\s+request\b",
        r"\buser\s+(?:asked|requested|requires?)\b",
        r"\brecurs(?:ive|ion)\b",
        r"\brepeated\s+reuse\b",
        r"\breuse\s+across\s+multiple\s+statements?\b",
        r"\bmulti-?statement\b",
        r"\bmultiple\s+statements?\b",
        r"\bneeds?\s+index(?:ing|es)?\b",
        r"\bindex(?:ing|ed)?\s*/?\s*statistics\b",
        r"\bstatistics\b",
        r"\blarge\s+intermediate\b",
        r"\bprocedural\s+staging\b",
        r"\bmeasured\s+performance\b",
        r"\bperformance\s+evidence\b",
        r"\bstatistics\s+io\b",
    ]
    return any(re.search(pattern, normalized) for pattern in exception_patterns)


def _check_if_exists_where_subquery(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    unprotected = _strip_literals_and_comments(sql)
    for block in _extract_if_exists_blocks(unprotected):
        if _contains_where_subquery(block):
            issues.append(
                SqlFormattingIssue(
                    code="if_exists_where_subquery",
                    severity="error",
                    message=(
                        "Do not put a nested subquery under WHERE inside IF EXISTS guards by default. "
                        "Use direct JOIN/derived-table style or record explicit source evidence."
                    ),
                    evidence=[_single_line_sample(block)],
                    check_kind="style",
                )
            )
    return issues


def _extract_if_exists_blocks(unprotected_sql: str) -> List[str]:
    blocks: List[str] = []
    pattern = re.compile(r"\bIF\s+EXISTS\s*\(", flags=re.IGNORECASE)
    for match in pattern.finditer(unprotected_sql):
        open_index = unprotected_sql.find("(", match.start())
        if open_index < 0:
            continue
        close_index = _find_matching_parenthesis(unprotected_sql, open_index)
        if close_index > open_index:
            blocks.append(unprotected_sql[open_index + 1 : close_index])
    return blocks


def _contains_where_subquery(block: str) -> bool:
    upper = block.upper()
    where_index = _find_top_level_keyword(upper, 0, "WHERE")
    if where_index < 0:
        return False
    where_text = upper[where_index:]
    subquery_patterns = [
        r"\b(?:NOT\s+)?EXISTS\s*\(\s*SELECT\b",
        r"\b(?:NOT\s+)?IN\s*\(\s*SELECT\b",
        r"(?:=|<>|!=|<=|>=|<|>)\s*\(\s*SELECT\b",
    ]
    return any(re.search(pattern, where_text, flags=re.IGNORECASE | re.DOTALL) for pattern in subquery_patterns)


def _single_line_sample(text: str, *, limit: int = 240) -> str:
    sample = re.sub(r"\s+", " ", text.strip())
    return sample[:limit]


def _extract_temp_table_names(unprotected_sql: str) -> set[str]:
    return {
        match.group(1).upper()
        for match in re.finditer(
            r"(?<![A-Z0-9_#])((?:##|#)[A-Z_][A-Z0-9_]*)\b",
            unprotected_sql,
            flags=re.IGNORECASE,
        )
    }


def _extract_insert_column_blocks(sql: str) -> List[str]:
    blocks: List[str] = []
    for match in re.finditer(r"\bINSERT\s+INTO\b", sql, flags=re.IGNORECASE):
        open_index = sql.find("(", match.end())
        if open_index < 0:
            continue
        close_index = _find_matching_parenthesis(sql, open_index)
        if close_index < 0:
            continue
        remainder = sql[close_index + 1 : close_index + 2500]
        if not re.search(r"\bSELECT\b", remainder, flags=re.IGNORECASE):
            continue
        blocks.append(sql[open_index + 1 : close_index])
    return blocks


def _extract_insert_select_statements(sql: str) -> List[Dict[str, str]]:
    statements: List[Dict[str, str]] = []
    for match in re.finditer(r"\bINSERT\s+INTO\b", sql, flags=re.IGNORECASE):
        open_index = sql.find("(", match.end())
        if open_index < 0:
            continue
        close_index = _find_matching_parenthesis(sql, open_index)
        if close_index < 0:
            continue
        select_match = re.search(r"\bSELECT\b", sql[close_index + 1 :], flags=re.IGNORECASE)
        if not select_match:
            continue
        select_start = close_index + 1 + select_match.start()
        from_index = _find_top_level_keyword(sql, select_start, "FROM")
        if from_index < 0:
            continue
        statements.append(
            {
                "target_block": sql[open_index + 1 : close_index],
                "select_block": sql[select_start:from_index],
            }
        )
    return statements


def _find_top_level_keyword(sql: str, start: int, keyword: str) -> int:
    depth = 0
    in_string = False
    keyword_re = re.compile(rf"\b{re.escape(keyword)}\b", flags=re.IGNORECASE)
    index = start
    while index < len(sql):
        char = sql[index]
        if char == "'":
            if in_string and index + 1 < len(sql) and sql[index + 1] == "'":
                index += 2
                continue
            in_string = not in_string
        elif not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            elif depth == 0:
                match = keyword_re.match(sql, index)
                if match:
                    return index
        index += 1
    return -1


def _find_matching_parenthesis(sql: str, open_index: int) -> int:
    depth = 0
    index = open_index
    in_string = False
    while index < len(sql):
        char = sql[index]
        if char == "'":
            if in_string and index + 1 < len(sql) and sql[index + 1] == "'":
                index += 2
                continue
            in_string = not in_string
        elif not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return index
        index += 1
    return -1


def _meaningful_insert_lines(block: str) -> List[str]:
    lines = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if stripped in {"(", ")"}:
            continue
        lines.append(stripped.rstrip(","))
    return lines


def _count_insert_target_columns(block: str) -> int:
    return len(_split_top_level_commas(block))


def _split_top_level_commas(value: str) -> List[str]:
    items: List[str] = []
    depth = 0
    in_string = False
    start = 0
    index = 0
    while index < len(value):
        char = value[index]
        if char == "'":
            if in_string and index + 1 < len(value) and value[index + 1] == "'":
                index += 2
                continue
            in_string = not in_string
        elif not in_string:
            if char == "(":
                depth += 1
            elif char == ")":
                depth = max(0, depth - 1)
            elif char == "," and depth == 0:
                item = value[start:index].strip()
                if item:
                    items.append(item)
                start = index + 1
        index += 1
    tail = value[start:].strip()
    if tail:
        items.append(tail)
    return items


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
    single_column_lines = [line for line in lines if _looks_like_single_insert_column_line(line)]
    return len(single_column_lines) >= max(8, int(len(lines) * 0.8))


def _looks_like_single_insert_column_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("--"):
        stripped = stripped[2:].strip()
    if stripped.startswith(","):
        stripped = stripped[1:].strip()
    stripped = re.sub(r"/\*.*?\*/", "", stripped).strip()
    return bool(re.fullmatch(r"(?:\[[A-Z_][A-Z0-9_@$#]*\]|[A-Z_][A-Z0-9_@$#]*)(?:\s+AS\s+\w+)?", stripped, flags=re.IGNORECASE))


def _looks_like_single_select_value_line(line: str) -> bool:
    stripped = line.strip()
    if stripped.startswith("--"):
        return False
    if stripped.startswith(","):
        stripped = stripped[1:].strip()
    if not stripped:
        return False
    upper = stripped.upper()
    if stripped.startswith(("+", "-", "*", "/", ")")):
        return False
    if re.match(r"^(PARTITION\s+BY|ORDER\s+BY|WHEN|ELSE|END)\b", upper):
        return False
    if "," in stripped:
        return False
    if re.search(r"\b(OVER|CASE)\b", stripped, flags=re.IGNORECASE) and not re.search(r"\bEND\b", stripped, flags=re.IGNORECASE):
        return False
    return bool(re.search(r"^(@|:|'|[A-Z_][A-Z0-9_@$#]*\.|[A-Z_][A-Z0-9_@$#]*\()", stripped, flags=re.IGNORECASE))


def _check_join_indentation(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    in_join = False
    current_join_indent = -1
    current_condition_indent = -1
    for line in sql.splitlines():
        stripped = line.lstrip(" ")
        if re.match(r"(LEFT\s+OUTER\s+JOIN|INNER\s+JOIN|JOIN)\b", stripped, flags=re.IGNORECASE):
            in_join = True
            current_condition_indent = -1
            leading = len(line) - len(stripped)
            current_join_indent = leading
            if leading % 4 != 0 or leading < 8:
                issues.append(
                    SqlFormattingIssue(
                        code="join_indentation",
                        severity="error",
                        message="JOIN lines should be indented to the SQL formatting join style.",
                        evidence=[line],
                    )
                )
            continue
        if in_join and re.match(r"(WHERE|GROUP BY|ORDER BY|HAVING|UNION|SELECT|FROM)\b", stripped, flags=re.IGNORECASE):
            in_join = False
            current_join_indent = -1
            current_condition_indent = -1
        if in_join and re.match(r"(ON|AND)\b", stripped, flags=re.IGNORECASE) and "=" in stripped:
            leading = len(line) - len(stripped)
            if leading < 10 or (current_join_indent >= 0 and leading < current_join_indent + 13):
                issues.append(
                    SqlFormattingIssue(
                        code="join_condition_indentation",
                        severity="error",
                        message="JOIN ON/AND conditions should be indented under the JOIN.",
                        evidence=[line],
                    )
                )
            if current_condition_indent < 0:
                current_condition_indent = leading
            elif leading != current_condition_indent:
                issues.append(
                    SqlFormattingIssue(
                        code="join_condition_alignment",
                        severity="error",
                        message="JOIN ON/AND conditions for the same JOIN should start in the same column.",
                        evidence=[line],
                    )
                )
    return issues


def _check_case_parentheses(sql: str) -> List[SqlFormattingIssue]:
    issues = []
    for line in _strip_literals_and_comments(sql).splitlines():
        if re.search(r"\bCASE\b", line, flags=re.IGNORECASE) and not re.search(r"\(\s*CASE\b", line, flags=re.IGNORECASE):
            issues.append(
                SqlFormattingIssue(
                    code="case_not_parenthesized",
                    severity="error",
                    message="CASE expressions must be wrapped as (CASE ... END).",
                    evidence=[line.strip()],
                )
            )
    return issues


def _check_ba011t_conversion(original: str, formatted: str) -> List[SqlFormattingIssue]:
    if not re.search(r"\bDBO\.F_BA011T_FIND_SUBNM\s*\(", original, flags=re.IGNORECASE):
        return []
    issues: List[SqlFormattingIssue] = []
    if re.search(r"\bDBO\.F_BA011T_FIND_SUBNM\s*\(", formatted, flags=re.IGNORECASE):
        issues.append(
            SqlFormattingIssue(
                code="ba011t_scalar_lookup_retained",
                severity="error",
                message="Verified BA011T scalar lookup should be converted to a BA011T join unless a concrete safety exception is recorded.",
                evidence=["DBO.F_BA011T_FIND_SUBNM"],
            )
        )
    if not re.search(r"\bJOIN\s+(?:\[?DBO\]?\.)?\[?BA011T\]?\b|\bFROM\s+(?:\[?DBO\]?\.)?\[?BA011T\]?\b", formatted, flags=re.IGNORECASE):
        issues.append(
            SqlFormattingIssue(
                code="ba011t_join_missing",
                severity="error",
                message="Formatted SQL should include a BA011T join or derived-table lookup for BA011T scalar conversion.",
                evidence=["BA011T"],
            )
        )
    if not re.search(r"\bISNULL\s*\([^)]*\.SUBNM\s*,\s*''\s*\)", formatted, flags=re.IGNORECASE):
        issues.append(
            SqlFormattingIssue(
                code="ba011t_subnm_projection_missing",
                severity="error",
                message="BA011T lookup projection should select ISNULL(alias.SUBNM, '').",
                evidence=["ISNULL(alias.SUBNM, '')"],
            )
        )
    return issues


def _diff_sample(original: Sequence[str], formatted: Sequence[str], limit: int = 6) -> List[str]:
    original_counts = _counts(original)
    formatted_counts = _counts(formatted)
    evidence = []
    for value in sorted(set(original_counts) | set(formatted_counts)):
        before = original_counts.get(value, 0)
        after = formatted_counts.get(value, 0)
        if before != after:
            evidence.append(f"{value!r}: original={before}, formatted={after}")
        if len(evidence) >= limit:
            break
    return evidence


def _without_allowed_ba011t_empty_literal(original: Sequence[str], formatted: Sequence[str]) -> List[str]:
    remaining = list(formatted)
    empty_additions = max(0, remaining.count("''") - list(original).count("''"))
    for _ in range(empty_additions):
        remaining.remove("''")
    return remaining


def _counts(items: Iterable[str]) -> Dict[str, int]:
    counts: Dict[str, int] = {}
    for item in items:
        counts[item] = counts.get(item, 0) + 1
    return counts


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
    parser.add_argument("--original", required=True, help="Path to original SQL text.")
    parser.add_argument("--formatted", required=True, help="Path to formatted SQL text.")
    parser.add_argument("--style-contract", default="", help="Optional host-local sql-formatting SKILL.md path.")
    args = parser.parse_args()

    result = verify_sql_formatting_style(
        Path(args.original).read_text(encoding="utf-8"),
        Path(args.formatted).read_text(encoding="utf-8"),
        style_contract_path=args.style_contract or None,
    )
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2, sort_keys=True))
    return result.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
