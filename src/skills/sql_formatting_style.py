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
) -> HarnessResult:
    """Verify SQL formatting output against the host-local sql-formatting contract."""
    original = str(original_sql or "")
    formatted = str(formatted_sql or "")
    preservation_issues = _check_preservation(original, formatted)
    style_issues = _check_style(original, formatted)
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
        "token_optimizer_reason": "SQL/stored procedure text is contract-sensitive and was not compressed.",
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
    original_literals = _extract_string_literals(original)
    formatted_literals = _extract_string_literals(formatted)
    if re.search(r"\bDBO\.F_BA011T_FIND_SUBNM\s*\(", original, flags=re.IGNORECASE):
        formatted_literals = _without_allowed_ba011t_empty_literal(original_literals, formatted_literals)
    if sorted(original_literals) != sorted(formatted_literals):
        issues.append(
            SqlFormattingIssue(
                code="string_literals_changed",
                severity="error",
                message="String literal multiset changed; Korean and business values must be preserved exactly.",
                evidence=_diff_sample(original_literals, formatted_literals),
            )
        )

    original_korean = [value for value in original_literals if _contains_korean(value)]
    formatted_korean = [value for value in formatted_literals if _contains_korean(value)]
    if sorted(original_korean) != sorted(formatted_korean):
        issues.append(
            SqlFormattingIssue(
                code="korean_literals_changed",
                severity="error",
                message="Korean string literals changed.",
                evidence=_diff_sample(original_korean, formatted_korean),
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


def _check_style(original: str, formatted: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    unprotected = _strip_literals_and_comments(formatted)

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

    issues.extend(_check_procedure_parameter_layout(formatted))
    issues.extend(_check_select_leading_commas(formatted))
    issues.extend(_check_join_indentation(formatted))
    issues.extend(_check_case_parentheses(formatted))
    issues.extend(_check_ba011t_conversion(original, formatted))
    return issues


def _extract_string_literals(sql: str) -> List[str]:
    return re.findall(r"'(?:''|[^'])*'", sql, flags=re.DOTALL)


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


def _contains_korean(value: str) -> bool:
    return bool(re.search(r"[\uac00-\ud7a3]", value))


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
            if re.match(r"^(FROM|WHERE|GROUP BY|ORDER BY|HAVING|UNION|END|ELSE)\b", stripped, flags=re.IGNORECASE):
                break
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


def _check_join_indentation(sql: str) -> List[SqlFormattingIssue]:
    issues: List[SqlFormattingIssue] = []
    in_join = False
    for line in sql.splitlines():
        stripped = line.lstrip(" ")
        if re.match(r"(LEFT\s+OUTER\s+JOIN|INNER\s+JOIN|JOIN)\b", stripped, flags=re.IGNORECASE):
            in_join = True
            leading = len(line) - len(stripped)
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
        if in_join and re.match(r"(ON|AND)\b", stripped, flags=re.IGNORECASE) and "=" in stripped:
            leading = len(line) - len(stripped)
            if leading < 10:
                issues.append(
                    SqlFormattingIssue(
                        code="join_condition_indentation",
                        severity="error",
                        message="JOIN ON/AND conditions should be indented under the JOIN.",
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
