"""Bounded cumulative directives and write-intent checks for PB migration.

Directive text is opaque. State is derived only from explicit identifiers,
supersession edges, satisfaction evidence, and observed action kinds. The
module is intentionally in-memory and has no clock, filesystem, environment,
process, network, subagent, or memory-provider dependency.
"""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
import json
from typing import Any, Iterable, Mapping, Tuple


CONTRACT_ID = "pb-migration-cumulative-directives"
SCHEMA_VERSION = 1

MODE_IMPLEMENTATION = "implementation"
MODE_ANALYSIS_ONLY = "analysis-only"
MODE_READ_ONLY = "read-only"

ACTION_READ = "read"
ACTION_REPORT = "report"
ACTION_WRITE = "write"
ACTION_MUTATION = "mutation"
ACTION_SUBAGENT_IMPLEMENTATION = "subagent_implementation"

ISSUE_EMPTY_DIRECTIVE_ID = "pb_directive_id_empty"
ISSUE_DUPLICATE_DIRECTIVE_ID = "pb_directive_id_duplicate"
ISSUE_UNKNOWN_SUPERSESSION = "pb_directive_supersession_unknown"
ISSUE_UNDECLARED_SUPERSESSION_CONFLICT = (
    "pb_directive_supersession_conflict_not_declared"
)
ISSUE_INACTIVE_SUPERSESSION = "pb_directive_supersession_target_inactive"
ISSUE_AMBIGUOUS_SUPERSESSION = "pb_directive_supersession_target_ambiguous"
ISSUE_UNKNOWN_CONFLICT = "pb_directive_conflict_unknown"
ISSUE_ACTIVE_CONFLICT = "pb_directive_conflict_active"
ISSUE_UNKNOWN_SATISFIED_ID = "pb_directive_satisfied_id_unknown"
ISSUE_ACTIVE_UNRESOLVED = "pb_directive_active_unresolved"
ISSUE_WRITE_INTENT_MODE_INVALID = "pb_write_intent_mode_invalid"
ISSUE_ACTION_KIND_UNKNOWN = "pb_write_intent_action_kind_unknown"
ISSUE_ANALYSIS_ONLY_WRITE = "pb_write_intent_analysis_only_write_observed"
ISSUE_ANALYSIS_ONLY_MUTATION = (
    "pb_write_intent_analysis_only_mutation_observed"
)
ISSUE_ANALYSIS_ONLY_SUBAGENT_IMPLEMENTATION = (
    "pb_write_intent_analysis_only_subagent_implementation_observed"
)
ISSUE_PREMATURE_COMPLETION = "pb_directive_completion_premature"

_MODES = {MODE_IMPLEMENTATION, MODE_ANALYSIS_ONLY, MODE_READ_ONLY}
_ACTION_KINDS = {
    ACTION_READ,
    ACTION_REPORT,
    ACTION_WRITE,
    ACTION_MUTATION,
    ACTION_SUBAGENT_IMPLEMENTATION,
}
_READ_ONLY_MODES = {MODE_ANALYSIS_ONLY, MODE_READ_ONLY}
_FORBIDDEN_ACTION_ISSUES = {
    ACTION_WRITE: ISSUE_ANALYSIS_ONLY_WRITE,
    ACTION_MUTATION: ISSUE_ANALYSIS_ONLY_MUTATION,
    ACTION_SUBAGENT_IMPLEMENTATION: (
        ISSUE_ANALYSIS_ONLY_SUBAGENT_IMPLEMENTATION
    ),
}


def _normalized_ids(values: Iterable[Any] | Any) -> Tuple[str, ...]:
    if values is None:
        return ()
    if isinstance(values, str):
        values = (values,)
    return tuple(sorted({str(value).strip() for value in values}))


@dataclass(frozen=True)
class Directive:
    """One immutable entry in an append-only directive stream."""

    directive_id: str
    text: str
    conflicts_with: Tuple[str, ...] = ()
    supersedes: Tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "directive_id", str(self.directive_id).strip())
        object.__setattr__(self, "text", str(self.text))
        object.__setattr__(
            self,
            "conflicts_with",
            _normalized_ids(self.conflicts_with),
        )
        object.__setattr__(
            self,
            "supersedes",
            _normalized_ids(self.supersedes),
        )

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "Directive":
        return cls(
            directive_id=value.get("directive_id", ""),
            text=value.get("text", ""),
            conflicts_with=value.get("conflicts_with", ()),
            supersedes=value.get("supersedes", ()),
        )


@dataclass(frozen=True)
class ObservedAction:
    """A caller-observed operation checked against the declared mode."""

    action_id: str
    kind: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "action_id", str(self.action_id).strip())
        object.__setattr__(self, "kind", str(self.kind).strip())

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any]) -> "ObservedAction":
        return cls(
            action_id=value.get("action_id", ""),
            kind=value.get("kind", ""),
        )


@dataclass(frozen=True)
class DirectiveReceipt:
    """Deterministic evaluation result suitable for harness metadata."""

    completion_authorized: bool
    issues: Tuple[Mapping[str, Any], ...]
    metadata: Mapping[str, Any]

    @property
    def success(self) -> bool:
        return self.completion_authorized

    @property
    def issue_codes(self) -> Tuple[str, ...]:
        return tuple(str(issue["code"]) for issue in self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "completion_authorized": self.completion_authorized,
            "issue_codes": list(self.issue_codes),
            "issues": [dict(issue) for issue in self.issues],
            "metadata": dict(self.metadata),
        }


class AppendOnlyDirectiveLedger:
    """In-memory ledger exposing append and evaluation, but no rewrite API."""

    __slots__ = ("_directives",)

    def __init__(self, directives: Iterable[Directive] = ()) -> None:
        self._directives = tuple(_coerce_directive(item) for item in directives)

    @property
    def directives(self) -> Tuple[Directive, ...]:
        return self._directives

    def append(self, directive: Directive | Mapping[str, Any]) -> int:
        self._directives = self._directives + (_coerce_directive(directive),)
        return len(self._directives) - 1

    def evaluate(
        self,
        *,
        satisfied_ids: Iterable[str] = (),
        write_intent: str = MODE_IMPLEMENTATION,
        observed_actions: Iterable[ObservedAction | Mapping[str, Any]] = (),
        completion_requested: bool = False,
    ) -> DirectiveReceipt:
        return evaluate_pb_migration_directives(
            self._directives,
            satisfied_ids=satisfied_ids,
            write_intent=write_intent,
            observed_actions=observed_actions,
            completion_requested=completion_requested,
        )


def evaluate_pb_migration_directives(
    directives: Iterable[Directive | Mapping[str, Any]],
    *,
    satisfied_ids: Iterable[str] = (),
    write_intent: str = MODE_IMPLEMENTATION,
    observed_actions: Iterable[ObservedAction | Mapping[str, Any]] = (),
    completion_requested: bool = False,
) -> DirectiveReceipt:
    """Evaluate cumulative directives and return a fail-closed receipt."""

    entries = tuple(_coerce_directive(item) for item in directives)
    actions = tuple(_coerce_action(item) for item in observed_actions)
    satisfied = _normalized_ids(satisfied_ids)
    mode = str(write_intent).strip()

    issues: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    invalid_sequences: set[int] = set()
    indices_by_id: dict[str, list[int]] = {}
    for sequence, directive in enumerate(entries):
        indices_by_id.setdefault(directive.directive_id, []).append(sequence)

    for sequence, directive in enumerate(entries):
        if not directive.directive_id:
            invalid_sequences.add(sequence)
            issues.append(
                _issue(ISSUE_EMPTY_DIRECTIVE_ID, directive_sequence=sequence)
            )

    for directive_id, sequences in sorted(indices_by_id.items()):
        if directive_id and len(sequences) > 1:
            invalid_sequences.update(sequences)
            issues.append(
                _issue(
                    ISSUE_DUPLICATE_DIRECTIVE_ID,
                    directive_id=directive_id,
                    directive_sequences=sequences,
                )
            )

    active_sequences = set(range(len(entries)))
    for sequence, directive in enumerate(entries):
        declared_conflicts = set(directive.conflicts_with)
        declared_supersessions = set(directive.supersedes)

        for target_id in sorted(declared_supersessions - declared_conflicts):
            invalid_sequences.add(sequence)
            issues.append(
                _issue(
                    ISSUE_UNDECLARED_SUPERSESSION_CONFLICT,
                    directive_id=directive.directive_id,
                    directive_sequence=sequence,
                    target_id=target_id,
                )
            )
            conflicts.append(
                _conflict_record(
                    directive,
                    sequence,
                    target_id,
                    status="invalid",
                    supersession_requested=True,
                )
            )

        for target_id in directive.conflicts_with:
            prior = [
                index
                for index in indices_by_id.get(target_id, ())
                if index < sequence
            ]
            supersession_requested = target_id in declared_supersessions
            if not prior:
                invalid_sequences.add(sequence)
                code = (
                    ISSUE_UNKNOWN_SUPERSESSION
                    if supersession_requested
                    else ISSUE_UNKNOWN_CONFLICT
                )
                issues.append(
                    _issue(
                        code,
                        directive_id=directive.directive_id,
                        directive_sequence=sequence,
                        target_id=target_id,
                    )
                )
                conflicts.append(
                    _conflict_record(
                        directive,
                        sequence,
                        target_id,
                        status="unknown",
                        supersession_requested=supersession_requested,
                    )
                )
                continue
            if len(prior) > 1:
                invalid_sequences.add(sequence)
                invalid_sequences.update(prior)
                issues.append(
                    _issue(
                        ISSUE_AMBIGUOUS_SUPERSESSION,
                        directive_id=directive.directive_id,
                        directive_sequence=sequence,
                        target_id=target_id,
                        target_sequences=prior,
                    )
                )
                conflicts.append(
                    _conflict_record(
                        directive,
                        sequence,
                        target_id,
                        status="ambiguous",
                        supersession_requested=supersession_requested,
                    )
                )
                continue

            target_sequence = prior[0]
            if supersession_requested:
                if target_sequence not in active_sequences:
                    invalid_sequences.add(sequence)
                    issues.append(
                        _issue(
                            ISSUE_INACTIVE_SUPERSESSION,
                            directive_id=directive.directive_id,
                            directive_sequence=sequence,
                            target_id=target_id,
                            target_sequence=target_sequence,
                        )
                    )
                    status = "inactive"
                else:
                    active_sequences.remove(target_sequence)
                    superseded.append(
                        {
                            "directive_id": target_id,
                            "directive_sequence": target_sequence,
                            "superseded_by": directive.directive_id,
                            "superseded_by_sequence": sequence,
                        }
                    )
                    status = "superseded"
            else:
                status = (
                    "active" if target_sequence in active_sequences else "inactive"
                )
                if status == "active":
                    invalid_sequences.update((sequence, target_sequence))
                    issues.append(
                        _issue(
                            ISSUE_ACTIVE_CONFLICT,
                            directive_id=directive.directive_id,
                            directive_sequence=sequence,
                            target_id=target_id,
                            target_sequence=target_sequence,
                        )
                    )
            conflicts.append(
                _conflict_record(
                    directive,
                    sequence,
                    target_id,
                    status=status,
                    supersession_requested=supersession_requested,
                    target_sequence=target_sequence,
                )
            )

        for target_id in sorted(declared_supersessions - declared_conflicts):
            if not [
                index
                for index in indices_by_id.get(target_id, ())
                if index < sequence
            ]:
                issues.append(
                    _issue(
                        ISSUE_UNKNOWN_SUPERSESSION,
                        directive_id=directive.directive_id,
                        directive_sequence=sequence,
                        target_id=target_id,
                    )
                )

    known_ids = set(indices_by_id)
    for directive_id in sorted(set(satisfied) - known_ids):
        issues.append(
            _issue(ISSUE_UNKNOWN_SATISFIED_ID, directive_id=directive_id)
        )

    if mode not in _MODES:
        issues.append(_issue(ISSUE_WRITE_INTENT_MODE_INVALID, mode=mode))

    action_payloads: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []
    for sequence, action in enumerate(actions):
        payload = {
            "action_id": action.action_id,
            "action_sequence": sequence,
            "kind": action.kind,
        }
        action_payloads.append(payload)
        if action.kind not in _ACTION_KINDS:
            issue = _issue(ISSUE_ACTION_KIND_UNKNOWN, **payload)
            issues.append(issue)
            violations.append(issue)
        elif mode in _READ_ONLY_MODES and action.kind in _FORBIDDEN_ACTION_ISSUES:
            issue = _issue(_FORBIDDEN_ACTION_ISSUES[action.kind], **payload)
            issues.append(issue)
            violations.append(issue)

    active = [
        _directive_record(entries[sequence], sequence)
        for sequence in sorted(active_sequences)
    ]
    unresolved: list[dict[str, Any]] = []
    for sequence in sorted(active_sequences):
        directive = entries[sequence]
        reasons = []
        if directive.directive_id not in satisfied:
            reasons.append("not_satisfied")
        if sequence in invalid_sequences:
            reasons.append("invalid_directive_state")
        if reasons:
            unresolved.append(
                {
                    **_directive_record(directive, sequence),
                    "reasons": reasons,
                }
            )
            issues.append(
                _issue(
                    ISSUE_ACTIVE_UNRESOLVED,
                    directive_id=directive.directive_id,
                    directive_sequence=sequence,
                    reasons=reasons,
                )
            )

    issues = sorted(issues, key=_issue_sort_key)
    completion_authorized = not issues and not unresolved
    if completion_requested and not completion_authorized:
        issues.append(
            _issue(
                ISSUE_PREMATURE_COMPLETION,
                blocking_issue_codes=sorted(
                    {str(issue["code"]) for issue in issues}
                ),
            )
        )
        issues = sorted(issues, key=_issue_sort_key)

    payload: dict[str, Any] = {
        "contract_id": CONTRACT_ID,
        "schema_version": SCHEMA_VERSION,
        "directive_count": len(entries),
        "completion_requested": bool(completion_requested),
        "completion_authorized": completion_authorized,
        "active": active,
        "superseded": superseded,
        "conflict": conflicts,
        "unresolved": unresolved,
        "write_intent": {
            "mode": mode,
            "writes_permitted": mode == MODE_IMPLEMENTATION,
            "observed_actions": action_payloads,
            "observed_write_count": sum(
                action.kind == ACTION_WRITE for action in actions
            ),
            "observed_mutation_count": sum(
                action.kind == ACTION_MUTATION for action in actions
            ),
            "observed_subagent_implementation_count": sum(
                action.kind == ACTION_SUBAGENT_IMPLEMENTATION
                for action in actions
            ),
            "violations": violations,
        },
        "issue_codes": [str(issue["code"]) for issue in issues],
        "issues": issues,
    }
    payload["receipt_sha256"] = _payload_sha256(payload)
    return DirectiveReceipt(
        completion_authorized=completion_authorized,
        issues=tuple(issues),
        metadata=payload,
    )


def _coerce_directive(value: Directive | Mapping[str, Any]) -> Directive:
    if isinstance(value, Directive):
        return value
    if isinstance(value, Mapping):
        return Directive.from_mapping(value)
    raise TypeError("directive must be Directive or a mapping")


def _coerce_action(
    value: ObservedAction | Mapping[str, Any],
) -> ObservedAction:
    if isinstance(value, ObservedAction):
        return value
    if isinstance(value, Mapping):
        return ObservedAction.from_mapping(value)
    raise TypeError("observed action must be ObservedAction or a mapping")


def _directive_record(directive: Directive, sequence: int) -> dict[str, Any]:
    return {
        "directive_id": directive.directive_id,
        "directive_sequence": sequence,
        "text": directive.text,
    }


def _conflict_record(
    directive: Directive,
    sequence: int,
    target_id: str,
    *,
    status: str,
    supersession_requested: bool,
    target_sequence: int | None = None,
) -> dict[str, Any]:
    return {
        "directive_id": directive.directive_id,
        "directive_sequence": sequence,
        "target_id": target_id,
        "target_sequence": target_sequence,
        "supersession_requested": supersession_requested,
        "status": status,
    }


def _issue(code: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "severity": "error", **details}


def _issue_sort_key(issue: Mapping[str, Any]) -> tuple[Any, ...]:
    return (
        str(issue.get("code", "")),
        int(issue.get("directive_sequence", -1)),
        str(issue.get("directive_id", "")),
        str(issue.get("target_id", "")),
        int(issue.get("action_sequence", -1)),
        str(issue.get("action_id", "")),
    )


def _payload_sha256(payload: Mapping[str, Any]) -> str:
    canonical = json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return "sha256:" + sha256(canonical.encode("utf-8")).hexdigest()
