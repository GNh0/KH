"""Explicit, mechanical alias edits. Business-role selection belongs to Codex."""
import re
from typing import Mapping
from .lexer import _analyze_sql_integrity, _identifier_value
from .scopes import _build_sql_scopes, _is_bound_alias_reference
from .layout import _apply_text_edits
from .compare import compare_sql


def describe_sources(sql: str) -> list[dict]:
    tokens, errors = _analyze_sql_integrity(sql, check_kind="alias_input")
    if any(i.severity == "error" for i in errors):
        raise ValueError("SQL lexical integrity failed")
    return [{"scope_id": scope.scope_id, "depth": scope.depth,
             "sources": [{"source": d.source, "alias": d.effective_alias, "order": d.order} for d in scope.declarations]}
            for scope in _build_sql_scopes(tokens)]


def rename_aliases(sql: str, renames: Mapping[str, Mapping[str, str]]) -> str:
    """Rename {scope_id: {existing_alias: new_alias}} without changing other scopes."""
    tokens, errors = _analyze_sql_integrity(sql, check_kind="alias_input")
    if any(i.severity == "error" for i in errors):
        raise ValueError("SQL lexical integrity failed")
    scopes = _build_sql_scopes(tokens)
    known = {s.scope_id for s in scopes}
    if set(renames) - known:
        raise ValueError("alias mapping contains an unknown SQL scope")
    edits = {}
    for scope in scopes:
        mapping = {a.upper(): b.upper() for a, b in renames.get(scope.scope_id, {}).items()}
        declared = {d.effective_alias for d in scope.declarations}
        if len(declared) != len(scope.declarations) or set(mapping) - declared:
            raise ValueError("alias mapping must identify unique declarations")
        if any(not re.fullmatch(r"[A-Z_][A-Z0-9_]*", alias) for alias in mapping.values()):
            raise ValueError("new aliases must be simple SQL identifiers")
        final = [mapping.get(d.effective_alias, d.effective_alias) for d in scope.declarations]
        if len(final) != len(set(final)):
            raise ValueError("alias mapping introduces a collision")
        for declaration in scope.declarations:
            old = declaration.effective_alias
            if old not in mapping:
                continue
            new = mapping[old]
            if declaration.alias_end is None:
                token = tokens[declaration.source_end]
                edits[token.end, token.end] = " " + new
            else:
                token = tokens[declaration.alias_end]
                edits[token.start, token.end] = new
            for index in range(scope.start, scope.end):
                if any(d.source != "(DERIVED)" and d.source_start <= index <= d.source_name_end
                       for s in scopes for d in s.declarations):
                    continue
                token = tokens[index]
                if _identifier_value(token) == old and _is_bound_alias_reference(tokens, index, scope, old, scopes):
                    edits[token.start, token.end] = new
    candidate = _apply_text_edits(sql, edits)
    check = compare_sql(sql, candidate)
    if not check.success:
        raise ValueError("alias rewrite could not prove preservation: " + check.to_json())
    return candidate


def apply_sql_alias_role_plan(sql: str, alias_role_plan) -> str:
    """Compatibility for explicit role plans; no signed bindings or role-name gates."""
    scopes = alias_role_plan.get("scopes", []) if isinstance(alias_role_plan, Mapping) else alias_role_plan
    mapping = {}
    for scope in scopes:
        scope_id = scope["scope_id"]
        if scope_id in mapping:
            raise ValueError("duplicate scope mapping")
        mapping[scope_id] = {}
        for role in scope.get("roles", []):
            for member in role.get("members", []):
                original = member["original_alias"]
                if original in mapping[scope_id]:
                    raise ValueError("duplicate alias mapping")
                mapping[scope_id][original] = member["alias"]
    return rename_aliases(sql, mapping)
