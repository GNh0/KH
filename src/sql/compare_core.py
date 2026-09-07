"""Retained sql syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple
from .scopes import (
    _AliasChange,
    _SqlScope,
    _is_bound_alias_reference,
)
from .lexer import (
    _SqlToken,
    _canonical_token_value,
    _identifier_value,
)


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
    declarations = [declaration for scope in scopes for declaration in scope.declarations]
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
            # A derived declaration spans its child query; it is not an object-name range.
            if any(
                item.source != "(DERIVED)"
                and item.source_start <= index <= item.source_name_end
                for item in declarations
            ):
                continue
            token = tokens[index]
            if _identifier_value(token) != alias:
                continue
            if _is_bound_alias_reference(tokens, index, scope, alias, scopes):
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
