from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List

from src.orchestration.skill_application import (
    LargeWorkOrchestrationBundle,
    SkillApplicationStatus,
)


TERMINAL_COMPOUND_STATUSES = {
    "ready_for_system_update",
    "no_reusable_learning",
    "completed",
}
COMPOUND_FOLLOWUP_SKILLS = {
    "workflow-skill-distiller",
    "memory-state-harness",
    "scenario-evaluation-harness",
    "context-state-harness",
}
COMPOUND_FOLLOWUP_EVIDENCE_KEYS = {
    "workflow-skill-distiller": {
        "workflow_skill_distiller_applied",
        "workflow_distillation_review",
        "skill_distillation_status",
    },
    "memory-state-harness": {
        "memory_candidates_recorded",
        "memory_state_applied",
        "memory_recorded",
    },
    "scenario-evaluation-harness": {
        "scenario_evaluation_applied",
        "scenario_evaluation_result",
        "scenario_regression_review",
    },
    "context-state-harness": {
        "context_state_applied",
        "resume_handoff",
        "context_state_saved",
    },
}


@dataclass(frozen=True)
class SkillTransitionIssue:
    rule: str
    source_skill: str
    required_skill: str
    reason: str

    def to_dict(self) -> Dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class SkillTransitionHandoff:
    phase: str
    required_next_skills: List[str] = field(default_factory=list)
    issues: List[SkillTransitionIssue] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase,
            "required_next_skills": list(self.required_next_skills),
            "issues": [issue.to_dict() for issue in self.issues],
            "evidence": list(self.evidence),
            "valid": not self.issues,
        }


def build_skill_transition_handoff(
    bundle: LargeWorkOrchestrationBundle,
    phase: str = "final",
) -> SkillTransitionHandoff:
    issues: List[SkillTransitionIssue] = []
    required_next_skills: List[str] = []
    statuses = bundle.skill_statuses

    _require_token_gate(bundle, statuses, issues, required_next_skills)
    _require_subagent_token_decision(bundle, statuses, issues, required_next_skills)
    _require_memory_skill_for_candidates(bundle, statuses, issues, required_next_skills)
    _require_parallel_skill_for_parallel_decision(bundle, statuses, issues, required_next_skills)
    _require_role_audit_after_subagent_or_role_claim(statuses, issues, required_next_skills)
    _require_verification_before_completion(bundle, statuses, phase, issues, required_next_skills)
    _require_compound_closure(bundle, statuses, phase, issues, required_next_skills)
    _require_compound_followup_consistency(bundle, statuses, issues, required_next_skills)

    required_next_skills = _dedupe(required_next_skills)
    evidence = [
        "skill_transition_handoff",
        "required_next_skills",
        "large_work_orchestration_bundle",
    ]
    if not issues:
        evidence.append("skill_transition_policy_passed")
    return SkillTransitionHandoff(
        phase=phase,
        required_next_skills=required_next_skills,
        issues=issues,
        evidence=evidence,
    )


def validate_skill_transitions(
    bundle: LargeWorkOrchestrationBundle,
    phase: str = "final",
) -> Dict[str, Any]:
    handoff = build_skill_transition_handoff(bundle, phase=phase)
    return handoff.to_dict()


def _require_token_gate(
    bundle: LargeWorkOrchestrationBundle,
    statuses: Dict[str, SkillApplicationStatus],
    issues: List[SkillTransitionIssue],
    required_next_skills: List[str],
) -> None:
    token_status = statuses.get("token-optimizer")
    if not bundle.token_optimizer_status.strip() or token_status is None:
        issues.append(SkillTransitionIssue(
            rule="large_work_requires_token_optimizer_status",
            source_skill="development-lifecycle-harness",
            required_skill="token-optimizer",
            reason="large work must record token_optimizer_status before broad reads, logs, or subagent transcripts",
        ))
        required_next_skills.append("token-optimizer")
        return
    if not bundle.token_optimizer_status_reason.strip():
        issues.append(SkillTransitionIssue(
            rule="large_work_requires_token_optimizer_status_reason",
            source_skill="development-lifecycle-harness",
            required_skill="token-optimizer",
            reason="large work must record why token optimizer was used, skipped, passed through, or blocked",
        ))
        required_next_skills.append("token-optimizer")
    if token_status.status == "considered_not_needed" and bundle.token_optimizer_status == "used":
        issues.append(SkillTransitionIssue(
            rule="token_status_mismatch",
            source_skill="large_work_orchestration_bundle",
            required_skill="token-optimizer",
            reason="bundle says token optimizer was not needed but workflow token_optimizer_status says it was used",
        ))
        required_next_skills.append("token-optimizer")


def _require_subagent_token_decision(
    bundle: LargeWorkOrchestrationBundle,
    statuses: Dict[str, SkillApplicationStatus],
    issues: List[SkillTransitionIssue],
    required_next_skills: List[str],
) -> None:
    subagent_status = statuses.get("subagent-review-pipeline")
    if subagent_status is None or subagent_status.status != "applied":
        return
    token_status = statuses.get("token-optimizer")
    if token_status is None or token_status.status == "considered_not_needed":
        issues.append(SkillTransitionIssue(
            rule="subagent_review_requires_token_optimizer_decision",
            source_skill="subagent-review-pipeline",
            required_skill="token-optimizer",
            reason="subagent task packets, transcripts, and reviewer outputs require an explicit token optimizer decision before aggregation",
        ))
        required_next_skills.append("token-optimizer")
        return
    if not bundle.token_optimizer_status.strip():
        issues.append(SkillTransitionIssue(
            rule="subagent_review_requires_token_optimizer_status",
            source_skill="subagent-review-pipeline",
            required_skill="token-optimizer",
            reason="subagents were applied, so token_optimizer_status must record used, considered_not_needed, passthrough, or blocked",
        ))
        required_next_skills.append("token-optimizer")


def _require_memory_skill_for_candidates(
    bundle: LargeWorkOrchestrationBundle,
    statuses: Dict[str, SkillApplicationStatus],
    issues: List[SkillTransitionIssue],
    required_next_skills: List[str],
) -> None:
    if not bundle.memory_candidates:
        return
    memory_status = statuses.get("memory-state-harness")
    if memory_status is None or memory_status.status == "considered_not_needed":
        issues.append(SkillTransitionIssue(
            rule="memory_candidates_require_memory_state",
            source_skill="compound-engineering-harness",
            required_skill="memory-state-harness",
            reason="memory candidates exist, so memory-state-harness must be applied or explicitly blocked",
        ))
        required_next_skills.append("memory-state-harness")


def _require_parallel_skill_for_parallel_decision(
    bundle: LargeWorkOrchestrationBundle,
    statuses: Dict[str, SkillApplicationStatus],
    issues: List[SkillTransitionIssue],
    required_next_skills: List[str],
) -> None:
    if "parallel" not in bundle.parallel_strategy_decision.lower():
        return
    parallel_status = statuses.get("parallel-orchestration-harness")
    if parallel_status is None or parallel_status.status == "considered_not_needed":
        issues.append(SkillTransitionIssue(
            rule="parallel_decision_requires_parallel_harness",
            source_skill="development-lifecycle-harness",
            required_skill="parallel-orchestration-harness",
            reason="parallel execution was selected, so parallel-orchestration-harness cannot remain considered_not_needed",
        ))
        required_next_skills.append("parallel-orchestration-harness")


def _require_role_audit_after_subagent_or_role_claim(
    statuses: Dict[str, SkillApplicationStatus],
    issues: List[SkillTransitionIssue],
    required_next_skills: List[str],
) -> None:
    subagent_status = statuses.get("subagent-review-pipeline")
    role_audit_status = statuses.get("role-execution-audit-harness")
    if subagent_status is None:
        return
    if subagent_status.status != "applied":
        return
    if role_audit_status is None or role_audit_status.status == "considered_not_needed":
        issues.append(SkillTransitionIssue(
            rule="subagent_review_requires_role_audit_decision",
            source_skill="subagent-review-pipeline",
            required_skill="role-execution-audit-harness",
            reason="subagent review was applied, so role execution audit must inspect results or be explicitly blocked",
        ))
        required_next_skills.append("role-execution-audit-harness")


def _require_verification_before_completion(
    bundle: LargeWorkOrchestrationBundle,
    statuses: Dict[str, SkillApplicationStatus],
    phase: str,
    issues: List[SkillTransitionIssue],
    required_next_skills: List[str],
) -> None:
    if phase != "final":
        return
    verification_status = statuses.get("verification-before-completion-harness")
    if verification_status is None or verification_status.status != "applied":
        issues.append(SkillTransitionIssue(
            rule="final_requires_verification_before_completion",
            source_skill="development-lifecycle-harness",
            required_skill="verification-before-completion-harness",
            reason="final completion, commit, push, PR, release, or handoff claims require fresh verification evidence",
        ))
        required_next_skills.append("verification-before-completion-harness")
        return
    if not _has_fresh_verification_evidence(verification_status):
        issues.append(SkillTransitionIssue(
            rule="verification_before_completion_requires_fresh_evidence",
            source_skill="verification-before-completion-harness",
            required_skill="verification-before-completion-harness",
            reason="verification-before-completion cannot pass on generic status keys; attach command/result/report evidence",
        ))
        required_next_skills.append("verification-before-completion-harness")


def _has_fresh_verification_evidence(status: SkillApplicationStatus) -> bool:
    evidence_keys = set(status.evidence_keys)
    if not evidence_keys & {
        "fresh_verification",
        "verification_command",
        "verification_result",
        "test_evidence",
        "release_gate",
    }:
        return False
    metadata = dict(status.metadata or {})
    return _has_passed_verification_result(metadata)


def _has_passed_verification_result(metadata: Dict[str, Any]) -> bool:
    command_output = metadata.get("command_output")
    if isinstance(command_output, dict) and _command_output_passed(command_output):
        return True

    has_concrete_source = _has_concrete_verification_source(metadata)
    if has_concrete_source and _value_is_passed(metadata.get("verification_result")):
        return True
    if has_concrete_source and _value_is_passed(metadata.get("test_result")):
        return True
    if has_concrete_source and _value_is_passed(metadata.get("release_gate")):
        return True

    results = metadata.get("verification_results") or metadata.get("test_results")
    if has_concrete_source and isinstance(results, list) and any(_value_is_passed(item) for item in results):
        return True

    return False


def _has_concrete_verification_source(metadata: Dict[str, Any]) -> bool:
    concrete_keys = {
        "verification_command",
        "verification_commands",
        "test_command",
        "test_commands",
        "report_path",
        "report_paths",
        "evidence_artifacts",
    }
    return any(key in metadata and metadata.get(key) for key in concrete_keys)


def _command_output_passed(command_output: Dict[str, Any]) -> bool:
    command = str(command_output.get("command") or command_output.get("cmd") or "").strip()
    if not command:
        return False
    try:
        return int(command_output.get("exit_code")) == 0
    except (TypeError, ValueError):
        return False


def _value_is_passed(value: Any) -> bool:
    if isinstance(value, dict):
        status = value.get("status") or value.get("result") or value.get("outcome")
        if status is not None:
            return _value_is_passed(status)
        if "exit_code" in value:
            try:
                return int(value.get("exit_code")) == 0
            except (TypeError, ValueError):
                return False
        return False
    if isinstance(value, bool):
        return value
    normalized = str(value or "").strip().lower()
    return normalized in {"pass", "passed", "success", "successful", "ok", "green", "0"}


def _require_compound_closure(
    bundle: LargeWorkOrchestrationBundle,
    statuses: Dict[str, SkillApplicationStatus],
    phase: str,
    issues: List[SkillTransitionIssue],
    required_next_skills: List[str],
) -> None:
    compound_status = statuses.get("compound-engineering-harness")
    compound_handoff = dict(bundle.compound_handoff or {})
    handoff_status = str(compound_handoff.get("status", "")).strip()
    no_learning = str(compound_handoff.get("no_reusable_learning_rationale", "")).strip()

    if phase not in {"post_review", "final"}:
        return
    if compound_status is None or compound_status.status == "considered_not_needed":
        issues.append(SkillTransitionIssue(
            rule="post_review_requires_compound_decision",
            source_skill="development-lifecycle-harness",
            required_skill="compound-engineering-harness",
            reason="after review, compound-engineering-harness must capture learning or record no reusable learning",
        ))
        required_next_skills.append("compound-engineering-harness")
        return
    if compound_status.status != "applied":
        issues.append(SkillTransitionIssue(
            rule="compound_harness_must_be_applied_before_completion",
            source_skill="compound-engineering-harness",
            required_skill="compound-engineering-harness",
            reason=(
                "compound-engineering-harness must be applied before post-review or final completion; "
                f"current status is {compound_status.status!r}"
            ),
        ))
        required_next_skills.append("compound-engineering-harness")
        return
    if handoff_status not in TERMINAL_COMPOUND_STATUSES and not no_learning:
        issues.append(SkillTransitionIssue(
            rule="compound_handoff_must_close",
            source_skill="compound-engineering-harness",
            required_skill="workflow-skill-distiller",
            reason="compound_handoff is still pending and lacks an explicit no_reusable_learning_rationale",
        ))
        required_next_skills.append("compound-engineering-harness")


def _require_compound_followup_consistency(
    bundle: LargeWorkOrchestrationBundle,
    statuses: Dict[str, SkillApplicationStatus],
    issues: List[SkillTransitionIssue],
    required_next_skills: List[str],
) -> None:
    compound_handoff = dict(bundle.compound_handoff or {})
    next_skills = {str(item) for item in compound_handoff.get("next_skills", [])}
    for next_skill in sorted(next_skills & COMPOUND_FOLLOWUP_SKILLS):
        followup_status = statuses.get(next_skill)
        if followup_status is None or followup_status.status == "considered_not_needed":
            issues.append(SkillTransitionIssue(
                rule="compound_next_skill_requires_followup_status",
                source_skill="compound-engineering-harness",
                required_skill=next_skill,
                reason=f"compound handoff routes to {next_skill}, so it cannot be silently omitted",
            ))
            required_next_skills.append(next_skill)
            continue
        if followup_status.status == "blocked" and followup_status.blocked_reason.strip():
            continue
        allowed_evidence = COMPOUND_FOLLOWUP_EVIDENCE_KEYS.get(next_skill, set())
        evidence_keys = set(followup_status.evidence_keys)
        if evidence_keys & allowed_evidence and _has_followup_runtime_evidence(followup_status):
            continue
        issues.append(SkillTransitionIssue(
            rule="compound_next_skill_requires_followup_evidence",
            source_skill="compound-engineering-harness",
            required_skill=next_skill,
            reason=(
                f"compound handoff routes to {next_skill}, so metadata status must include "
                "follow-up-specific evidence instead of a generic applied marker"
            ),
        ))
        required_next_skills.append(next_skill)


def _has_followup_runtime_evidence(status: SkillApplicationStatus) -> bool:
    if status.application_mode == "runtime":
        return True
    metadata = dict(status.metadata or {})
    concrete_keys = {
        "artifact_path",
        "artifact_paths",
        "output_path",
        "output_paths",
        "result_path",
        "result_paths",
        "report_path",
        "report_paths",
        "runtime_path",
        "generated_skill_path",
        "scenario_report_path",
        "verification_command",
        "verification_result",
        "record_ids",
        "candidate_ids",
    }
    if any(key in metadata and metadata.get(key) for key in concrete_keys):
        return True
    evidence_artifacts = metadata.get("evidence_artifacts")
    return isinstance(evidence_artifacts, list) and any(str(item).strip() for item in evidence_artifacts)


def _dedupe(items: List[str]) -> List[str]:
    seen = set()
    unique = []
    for item in items:
        if item in seen:
            continue
        seen.add(item)
        unique.append(item)
    return unique
