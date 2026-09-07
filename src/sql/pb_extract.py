"""Retained sql syntax and domain mechanics from KH; no host orchestration."""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple


POWERBUILDER_SQL_KEYWORD_PATTERN = re.compile(
    r"\b(SELECT|UPDATE|DELETE|INSERT|MERGE)\b",
    re.IGNORECASE,
)


def extract_powerbuilder_sql_fragments(
    source_text: str,
    *,
    source_name: str = "",
    max_lines_per_fragment: int = 80,
    token_optimizer_selected: bool = False,
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
        fragment = {
            "fragment_id": f"{Path(source_name).name or 'powerbuilder'}:{start + 1}:{match.group(1).upper()}",
            "source_name": source_name,
            "keyword": match.group(1).upper(),
            "start_line": start + 1,
            "end_line": end + 1,
            "sql_text": sql_text,
        }
        if token_optimizer_selected:
            fragment.update(
                {
                    "token_optimizer_status": "passthrough",
                    "token_optimizer_status_reason": "SQL source text was not compressed.",
                }
            )
        fragments.append(fragment)
        index = end + 1
    return fragments
