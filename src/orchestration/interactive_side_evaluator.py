import argparse
import json
import sys
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Sequence

from src.orchestration.request_classifier import classify_request
from src.skills.token_optimizer import aggregate_token_usage_stats, compare_token_usage
from src.skills.uaf_skill_catalog import collect_packaged_skills


@dataclass(frozen=True)
class InteractiveSideTurn:
    turn_id: str
    user_text: str
    assistant_text: str
    context: Dict[str, Any] = field(default_factory=dict)
    expected_complexity: str = ""
    expected_domain: str = ""
    expected_execution: str = ""


@dataclass(frozen=True)
class InteractiveSideEvaluation:
    turn_id: str
    passed: bool
    expected: Dict[str, Any]
    actual: Dict[str, Any]
    findings: List[Dict[str, str]]
    signals: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class SkillSideTurn:
    turn_id: str
    conversation_id: str
    turn_index: int
    user_text: str
    assistant_text: str
    expected_skill: str
    expected_evidence: List[str]
    expected_route: str
    expected_additional_skills: List[str] = field(default_factory=list)
    policy_trace: Dict[str, Any] = field(default_factory=dict)
    required_response_markers: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SkillSideEvaluation:
    turn_id: str
    conversation_id: str
    turn_index: int
    expected_skill: str
    passed: bool
    expected: Dict[str, Any]
    actual: Dict[str, Any]
    findings: List[Dict[str, str]]
    signals: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def evaluate_interactive_side_turns(turns: Iterable[InteractiveSideTurn]) -> List[InteractiveSideEvaluation]:
    return [evaluate_interactive_side_turn(turn) for turn in turns]


def evaluate_interactive_side_turn(turn: InteractiveSideTurn) -> InteractiveSideEvaluation:
    classification = classify_request(turn.user_text, context=turn.context).to_dict()
    findings: List[Dict[str, str]] = []
    signals: List[Dict[str, Any]] = [
        {
            "category": "classification",
            "message": (
                f"{classification['complexity']}:"
                f"{classification['domain']}:"
                f"{classification['recommended_execution']}"
            ),
        }
    ]

    _expect_equal(findings, "complexity", turn.expected_complexity, str(classification["complexity"]))
    _expect_equal(findings, "domain", turn.expected_domain, str(classification["domain"]))
    _expect_equal(findings, "recommended_execution", turn.expected_execution, str(classification["recommended_execution"]))

    policy_findings = _assistant_policy_findings(str(classification["complexity"]), turn.assistant_text)
    findings.extend(policy_findings)
    signals.append(
        {
            "category": "assistant_policy",
            "complexity": classification["complexity"],
            "checks": _policy_checks_for(str(classification["complexity"])),
            "finding_count": len(policy_findings),
        }
    )

    return InteractiveSideEvaluation(
        turn_id=turn.turn_id,
        passed=not findings,
        expected={
            "complexity": turn.expected_complexity,
            "domain": turn.expected_domain,
            "recommended_execution": turn.expected_execution,
        },
        actual={
            "classification": classification,
            "assistant_text": turn.assistant_text,
        },
        findings=findings,
        signals=signals,
    )


def build_interactive_side_report(evaluations: Iterable[InteractiveSideEvaluation]) -> Dict[str, Any]:
    records = list(evaluations)
    signals = [signal for record in records for signal in record.signals]
    signal_categories = sorted({signal["category"] for signal in signals})
    unexpected_failures = [record.to_dict() for record in records if not record.passed]
    return {
        "summary": {
            "total": len(records),
            "passed": len([record for record in records if record.passed]),
            "failed": len(unexpected_failures),
            "signal_categories": signal_categories,
            "meaningful_signal_count": len(signals),
        },
        "unexpected_failures": unexpected_failures,
    }


def default_skill_side_turns() -> List[SkillSideTurn]:
    """Return multi-turn SIDE assistant cases covering every packaged KH skill."""
    cases = [
        _skill_turn(
            "host-portability",
            1,
            "We need one adapter contract that works for Codex, Antigravity-style, and local workers.",
            "Use a shared adapter contract first, then map each host into it. Capture host capability metadata, normalized request fields, and adapter result evidence before dispatch.",
            "adapter-contract-harness",
            ["adapter_contract", "host_compatibility"],
            "skill_call",
            ["adapter", "host"],
        ),
        _skill_turn(
            "host-portability",
            2,
            "Now design the portable loop and where tool permissions belong.",
            "Model the host loop around portable capabilities: project root, dispatch, permission checks, observability, and side-effect boundaries. Keep Codex, Antigravity-style, and local runtime differences as host metadata.",
            "host-agent-orchestration",
            ["host_capabilities", "portable_loop"],
            "workflow_harness",
            ["portable", "host"],
        ),
        _skill_turn(
            "host-portability",
            3,
            "Before any generated code changes, make a restore point.",
            "Create a snapshot before edits, store compressed file state, and record restore metadata so a failed run can roll back without touching unrelated files.",
            "snapshot-state-harness",
            ["rollback_point", "restore"],
            "skill_call",
            ["snapshot", "restore"],
        ),
        _skill_turn(
            "development-flow",
            1,
            "Build login with tests, review, verification, and branch finishing.",
            "Run this through the lifecycle: design first, create GoalState, choose workspace_strategy such as project-local-worktree or host-worktree before implementation, then failing test, implementation, review gates, verification evidence, and branch finishing.",
            "development-lifecycle-harness",
            ["goal_state", "workspace_strategy", "tdd", "verification"],
            "procedure_policy",
            ["goal", "workspace_strategy", "worktree", "test", "verification"],
            additional_skills=["goal-state-harness"],
        ),
        _skill_turn(
            "development-flow",
            2,
            "Split the login work across independent workers and aggregate results.",
            "Fan out only independent tasks after selecting project-local-worktree or host-worktree for concurrent write workers, keep write scopes bounded, then fan in task results with evidence before deciding whether the workflow can continue.",
            "parallel-orchestration-harness",
            ["workspace_strategy", "fan_out", "fan_in"],
            "skill_call",
            ["worktree", "fan", "evidence"],
        ),
        _skill_turn(
            "development-flow",
            3,
            "Use implementer, spec reviewer, and code quality reviewer roles for each subtask.",
            "Use the subagent review pipeline: implementer completes a bounded task, spec reviewer checks requirements, and quality reviewer checks maintainability before the task is accepted.",
            "subagent-review-pipeline",
            ["implementer", "spec_reviewer", "quality_reviewer"],
            "workflow_harness",
            ["reviewer", "implementer"],
        ),
        _skill_turn(
            "development-flow",
            4,
            "Confirm all roles actually ran and produced artifacts.",
            "Audit role execution by checking role artifacts, status transitions, and parallel wave evidence. Missing role output should block completion.",
            "role-execution-audit-harness",
            ["role_artifacts", "parallel_wave"],
            "skill_call",
            ["role", "artifact"],
        ),
        _skill_turn(
            "development-flow",
            5,
            "Before implementation, isolate this feature so user edits in the current checkout are protected.",
            "Use worktree isolation to choose project-local-worktree or host-worktree, record workspace_strategy, and keep task files in the isolated workspace before making code changes.",
            "worktree-isolation-harness",
            ["workspace_strategy", "worktree_root"],
            "workflow_harness",
            ["worktree", "workspace_strategy"],
        ),
        _skill_turn(
            "development-flow",
            6,
            "Run the written plan task by task and keep the visible task status updated.",
            "Use plan execution to read the plan, write progress.json, run each task through RED, GREEN, review, fix, re-review, commit, and report task_status plus next_task.",
            "plan-execution-harness",
            ["progress.json", "task_status", "next_task"],
            "workflow_harness",
            ["progress.json", "next_task"],
        ),
        _skill_turn(
            "development-flow",
            7,
            "A regression test failed after the last change; debug it before guessing at a fix.",
            "Use systematic debugging to capture the symptom, reproduce the failure, form a hypothesis, identify root_cause, apply the minimal fix, and keep regression evidence.",
            "systematic-debugging-harness",
            ["symptom", "hypothesis", "root_cause", "regression_evidence"],
            "workflow_harness",
            ["root_cause", "regression"],
        ),
        _skill_turn(
            "development-flow",
            8,
            "We are about to say this is done. Verify first and only then claim completion.",
            "Use verification before completion: run the relevant verification commands, capture verification_status, preserve failing output if any, and only make a completion_claim after evidence passes.",
            "verification-before-completion-harness",
            ["verification_status", "completion_claim"],
            "workflow_harness",
            ["verification_status", "completion_claim"],
        ),
        _skill_turn(
            "development-flow",
            9,
            "The branch is ready; decide whether to commit, merge, PR, push, or clean up.",
            "Use branch finishing to inspect status, summarize review_status, create or report commit_sha when appropriate, decide branch_finish_status, and leave next integration steps explicit.",
            "branch-finishing-harness",
            ["branch_finish_status", "review_status", "commit_sha"],
            "workflow_harness",
            ["branch_finish_status", "commit_sha"],
        ),
        _skill_turn(
            "design-deliverables",
            1,
            "This is a non-code equipment planning project; start from design and required outputs.",
            "Start with the architect pipeline: produce the design blueprint, required deliverables, constraints, assumptions, and verification plan before execution.",
            "architect-pipeline",
            ["design_blueprint", "required_deliverables"],
            "workflow_harness",
            ["design", "deliverables"],
        ),
        _skill_turn(
            "design-deliverables",
            2,
            "Before the design stage, clarify the product direction and compare a few approaches.",
            "Use brainstorming harness first: ask one focused question at a time, compare options, capture decisions, and produce a handoff to architect-pipeline.",
            "brainstorming-harness",
            ["brainstorm_handoff", "decision_log", "recommended_option"],
            "workflow_harness",
            ["brainstorm", "handoff"],
        ),
        _skill_turn(
            "design-deliverables",
            3,
            "It may involve engineering, procurement, safety, and compliance reviewers.",
            "Use domain orchestration: define domain roles, persist design artifacts and deliverables, then route through risk, policy, QA/QC, and final decision gates.",
            "domain-orchestration-harness",
            ["domain_design", "risk_gate", "deliverables"],
            "workflow_harness",
            ["risk", "deliverables"],
        ),
        _skill_turn(
            "design-deliverables",
            4,
            "Map requirements to deliverables, evidence keys, and review gates.",
            "Build a traceability matrix that links requirements to deliverables, evidence keys, owner roles, and review gates without exposing internal spreadsheets.",
            "traceability-matrix-harness",
            ["requirements", "evidence_keys", "review_gates"],
            "skill_call",
            ["requirements", "evidence"],
        ),
        _skill_turn(
            "design-deliverables",
            5,
            "Now check the final user-facing document template for missing required sections.",
            "Run deliverable template quality checks for required sections, evidence-backed claims, and completion status before presenting the deliverable.",
            "deliverable-template-quality-harness",
            ["required_sections", "evidence_backing"],
            "skill_call",
            ["sections", "evidence"],
        ),
        _skill_turn(
            "gates-review-qa",
            1,
            "Define what done means and what evidence proves this goal is complete.",
            "Create GoalState with objective, completion criteria, required evidence, current status, blockers, and the next recommended action.",
            "goal-state-harness",
            ["completion_criteria", "evidence_required"],
            "skill_call",
            ["criteria", "evidence"],
        ),
        _skill_turn(
            "gates-review-qa",
            2,
            "Review the implementation before landing and normalize findings.",
            "Run the review gate: collect actionable findings, normalize reviewer status, and block completion if required fixes or missing evidence remain.",
            "review-gate-harness",
            ["findings", "status"],
            "workflow_harness",
            ["findings", "status"],
        ),
        _skill_turn(
            "gates-review-qa",
            3,
            "Now map regression tests and manual checks to QA evidence.",
            "Use the QA gate to connect regression evidence, manual verification mapping, and browser or app checks to the release decision.",
            "qa-gate-harness",
            ["regression_evidence", "manual_mapping"],
            "workflow_harness",
            ["regression", "manual"],
        ),
        _skill_turn(
            "gates-review-qa",
            4,
            "Make sure this followed TDD and no evidence-based completion was skipped.",
            "Use quality gates for failing-test-first evidence, systematic debugging notes, review gate status, and final verification before declaring completion.",
            "quality-gates-harness",
            ["red_green", "review_gate"],
            "workflow_harness",
            ["test", "review"],
        ),
        _skill_turn(
            "state-memory",
            1,
            "Save a handoff so the next session can continue without guessing.",
            "Capture context state with decisions, handoff notes, active files, evidence pointers, and restore instructions so the workflow can resume cleanly.",
            "context-state-harness",
            ["handoff_snapshot", "decision_log"],
            "skill_call",
            ["handoff", "decisions"],
        ),
        _skill_turn(
            "state-memory",
            2,
            "Store only project-scoped memory candidates and clean them up if the chat is deleted.",
            "Use memory state with project or conversation scope, candidate evidence, namespace isolation, and archive/delete cleanup policy.",
            "memory-state-harness",
            ["scope", "cleanup_policy"],
            "skill_call",
            ["scope", "cleanup"],
        ),
        _skill_turn(
            "state-memory",
            3,
            "List the available KH skills and read the one that applies here.",
            "Use the skill catalog to list packaged skills, inspect descriptions, and read the selected SKILL.md without requiring external runtime installation.",
            "skill-catalog",
            ["list_skills", "read_skill"],
            "skill_call",
            ["catalog", "read"],
        ),
        _skill_turn(
            "state-memory",
            4,
            "This long task has progress.json now; make it visible and make sure the next session resumes from KH state.",
            "Use workflow usability to render a progress panel, record token_optimizer_provider, convert progress.json into a Compound handoff, and restore the next session from .kh, docs/kh, and memory candidates.",
            "workflow-usability-harness",
            ["progress_panel", "token_optimizer_provider", "compound_handoff", "session_start_context"],
            "workflow_harness",
            ["progress", "token", "compound", "session"],
            additional_skills=["compound-engineering-harness", "context-state-harness"],
        ),
        _skill_turn(
            "command-safety",
            1,
            "This hook might rewrite commands; define trust, permissions, and non-blocking behavior.",
            "Use command hook policy to record permission precedence, trust checks, integrity verification, and non-blocking fallback behavior.",
            "command-hook-policy-harness",
            ["permission_precedence", "non_blocking_hook"],
            "skill_call",
            ["permission", "hook"],
        ),
        _skill_turn(
            "command-safety",
            2,
            "Compress this huge failing test log but keep the exit code and useful lines.",
            "Run command output compression while preserving exit code, failing test names, key traceback lines, and token-savings metadata.",
            "command-output-harness",
            ["exit_code", "important_lines_preserved"],
            "skill_call",
            ["exit code", "preserv"],
        ),
        _skill_turn(
            "command-safety",
            3,
            "The user asked to delete a directory outside the workspace.",
            "Run guard policy: detect destructive action, check write boundary, require explicit approval, and keep the operation blocked until scope is safe.",
            "guard-policy-harness",
            ["destructive_action_gate", "write_boundary"],
            "skill_call",
            ["destructive", "boundary"],
        ),
        _skill_turn(
            "command-safety",
            4,
            "A Python file and terminal output are too large for context.",
            "Use token optimizer to summarize bulky content, preserve required facts, and report token savings without losing actionable errors.",
            "token-optimizer",
            ["token_savings", "preserved_facts"],
            "skill_call",
            ["token", "preserv"],
            token_usage=compare_token_usage(
                _sample_noisy_log(),
                _sample_optimized_log(),
                strategy="command-output",
                label="side-command-output",
            ),
        ),
        _skill_turn(
            "verification-ops",
            1,
            "Before showing results, verify this Python module in isolation.",
            "Use the harness evaluator for syntax checks, runtime checks, module import verification, and clear failure output before presenting results.",
            "harness-evaluator",
            ["syntax_check", "runtime_check"],
            "skill_call",
            ["syntax", "runtime"],
        ),
        _skill_turn(
            "verification-ops",
            2,
            "Give me a health summary and release readiness score.",
            "Run the health check harness to summarize code quality, test health, static checks, and release readiness evidence.",
            "health-check-harness",
            ["test_health", "release_readiness"],
            "workflow_harness",
            ["health", "release"],
        ),
        _skill_turn(
            "verification-ops",
            3,
            "Validate generated typed artifacts such as documents, spreadsheets, drawings, images, web pages, or data exports are readable.",
            "Use artifact render QA to open or parse generated deliverables, validate structure, and attach artifact manifest evidence.",
            "artifact-render-qa-harness",
            ["render_validation", "artifact_manifest"],
            "skill_call",
            ["artifact", "valid"],
        ),
        _skill_turn(
            "routing-evaluation",
            1,
            "Build a small HTML todo tool and verify it, without naming any KH internals.",
            "Use always-on front-door first: run KH front-door routing before source reads, record runtime_applied_skills, and keep follow-up skills in selected_not_executed until they produce evidence.",
            "always-on-front-door",
            ["runtime_applied_skills", "selected_not_executed_skills"],
            "skill_call",
            ["front-door", "runtime"],
        ),
        _skill_turn(
            "routing-evaluation",
            2,
            "Classify this ordinary project request and decide what KH should do next.",
            "Use automatic intake to record classification, choose the plugin_route, record runtime_applied_skills, and keep selected_not_executed follow-up skills honest until they produce evidence.",
            "automatic-intake-harness",
            ["classification", "plugin_route", "runtime_applied_skills"],
            "skill_call",
            ["intake", "classification"],
        ),
        _skill_turn(
            "routing-evaluation",
            3,
            "KH and Superpowers are both installed, and Browser might help for QA. Which should handle this SaaS task?",
            "Use plugin composition first: choose KH as the workflow controller, delegate browser QA only for visual verification, and ignore any provider self-forcing until its delegated scope is selected.",
            "plugin-composition-policy",
            ["controller", "assistants", "ignored_self_forcing"],
            "skill_call",
            ["controller", "browser", "self-forcing"],
        ),
        _skill_turn(
            "routing-evaluation",
            4,
            "Is this a light answer, a skill call, or a full role DAG?",
            "Use request complexity routing to classify the request, choose a route such as direct answer, skill read, GoalState, or role DAG, and keep reasons in the trace.",
            "request-complexity-router",
            ["complexity", "route"],
            "skill_call",
            ["complexity", "route"],
        ),
        _skill_turn(
            "routing-evaluation",
            5,
            "Before returning formatted SQL, verify it still matches the host-local sql-formatting style contract.",
            "Use the SQL formatting style harness after host-local sql-formatting has produced SQL. Record mechanical_checks for literal preservation, comments, and aliases, and attach style_contract_source before final SQL output.",
            "sql-formatting-style-harness",
            ["mechanical_checks", "style_contract_source"],
            "skill_call",
            ["sql-formatting", "mechanical_checks", "style_contract"],
        ),
        _skill_turn(
            "routing-evaluation",
            6,
            "Run many SIDE-style human scenarios and check routing, evidence, gates, and resume.",
            "Use scenario evaluation with SIDE transcripts, classification checks, evidence expectations, gate decisions, and resume handoff coverage.",
            "scenario-evaluation-harness",
            ["side_transcript", "classification"],
            "skill_call",
            ["side", "classification"],
        ),
        _skill_turn(
            "routing-evaluation",
            7,
            "The work passed review; now capture what the system should learn for next time.",
            "Use compound engineering to record review learning, scoped memory candidates, system updates, and regression checks before finishing.",
            "compound-engineering-harness",
            ["compound_capture", "memory_candidates", "regression_check_plan"],
            "workflow_harness",
            ["compound", "memory"],
        ),
        _skill_turn(
            "routing-evaluation",
            8,
            "We keep repeating this workflow; turn it into a reusable skill folder.",
            "Use workflow skill distillation to identify the repeatable workflow, extract contracts, and scaffold a reusable skill with examples and smoke checks.",
            "workflow-skill-distiller",
            ["repeatable_workflow", "skill_scaffold"],
            "skill_call",
            ["workflow", "skill"],
        ),
        _skill_turn(
            "routing-evaluation",
            8,
            "Show the CEO, advisor, architect, implementer, QA, security, and release roles for this workflow.",
            "Use the orchestration role graph to inspect roles, handoffs, ownership, and required artifacts across CEO, advisors, architect, implementers, reviewers, QA, security, and release.",
            "orchestration-role-graph",
            ["roles", "handoff"],
            "skill_call",
            ["roles", "handoff"],
        ),
    ]
    return cases


def stress_skill_side_turns() -> List[SkillSideTurn]:
    """Return broader live-style KH SIDE transcripts with varied lengths and overlap cases."""
    return default_skill_side_turns() + _stress_skill_side_extras()


def _stress_skill_side_extras() -> List[SkillSideTurn]:
    turns: List[SkillSideTurn] = []
    add = turns.append

    add(_skill_turn(
        "live-command-overlap", 1,
        "Add a hook that rewrites risky commands, but keep it portable across PowerShell and bash.",
        "Use command hook policy with explicit permission precedence, parser limits, and hook audit evidence for both PowerShell and bash.",
        "command-hook-policy-harness", ["permission_precedence", "hook_audit"], "skill_call", ["permission", "hook"],
    ))
    add(_skill_turn(
        "live-command-overlap", 2,
        "The hook sees a recursive delete outside the repo. The user insists it is fine.",
        "Activate the guard and hook policy together: destructive recursive delete outside the boundary must block until the resolved path and approval are safe.",
        "guard-policy-harness", ["destructive_action_gate", "write_boundary", "permission_precedence"], "skill_call", ["destructive", "boundary"], additional_skills=["command-hook-policy-harness"],
    ))
    add(_skill_turn(
        "live-command-overlap", 3,
        "Now compress the failing output but keep the exact failing test and exit code.",
        "Use command output filtering to preserve the failing test, assertion, traceback, and exit code while omitting repeated passing output.",
        "command-output-harness", ["exit_code", "important_lines_preserved"], "skill_call", ["exit code", "preserv"],
        token_usage=compare_token_usage(_sample_noisy_log(), _sample_optimized_log(), strategy="command-output", label="live-command-log"),
    ))
    add(_skill_turn(
        "live-command-overlap", 4,
        "Show me how much context was saved compared with not using the optimizer.",
        "Use token optimizer statistics: compare raw and optimized text, then report token savings, ratio, and strategy as evidence.",
        "token-optimizer", ["token_savings", "preserved_facts"], "skill_call", ["token", "savings"],
        token_usage=compare_token_usage(_sample_noisy_log() * 2, _sample_optimized_log(), strategy="command-output", label="live-token-stats"),
    ))
    add(_skill_turn(
        "live-command-overlap", 5,
        "A generated script includes curl pipe sh and then deletes temp files.",
        "Combine command hook policy and guard policy because installer execution and destructive cleanup both need explicit permission and safety gates.",
        "command-hook-policy-harness", ["permission_precedence", "destructive_action_gate"], "skill_call", ["permission", "destructive"], additional_skills=["guard-policy-harness"],
    ))
    add(_skill_turn(
        "live-command-overlap", 6,
        "The command passed. Keep only the useful summary from a long success log.",
        "Use command output compression for a success log only if the important evidence and command status remain preserved.",
        "command-output-harness", ["important_lines_preserved", "exit_code"], "skill_call", ["preserv", "status"],
        token_usage=compare_token_usage("build line\n" * 300 + "EVIDENCE: package built\n", "EVIDENCE: package built\n", strategy="command-output", label="live-success-log"),
    ))

    add(_skill_turn(
        "live-dev-lifecycle", 1,
        "We are building auth. Start from design, TDD, review, verification, and branch finish.",
        "Run the development lifecycle with design, GoalState, workspace_strategy, TDD, review, verification, and branch finishing evidence before completion.",
        "development-lifecycle-harness", ["goal_state", "workspace_strategy", "work_design", "tdd_red_green", "verification"], "procedure_policy", ["goal", "workspace_strategy", "design", "verification"],
        additional_skills=["goal-state-harness"],
    ))
    add(_skill_turn(
        "live-dev-lifecycle", 2,
        "Before editing, checkpoint the current files.",
        "Create a snapshot state checkpoint with rollback metadata before any generated code changes are applied.",
        "snapshot-state-harness", ["rollback_point", "restore"], "skill_call", ["snapshot", "rollback"],
    ))
    add(_skill_turn(
        "live-dev-lifecycle", 3,
        "Split auth UI, session logic, and route protection into separate workers.",
        "Use parallel orchestration with bounded write scopes, fan-out, fan-in, and aggregation evidence for each worker.",
        "parallel-orchestration-harness", ["fan_out", "fan_in", "bounded_scope"], "skill_call", ["fan", "bounded"],
    ))
    add(_skill_turn(
        "live-dev-lifecycle", 4,
        "Each worker must pass spec review and code-quality review.",
        "Use the subagent review pipeline so implementer output is checked by spec reviewer and code-quality reviewer before acceptance.",
        "subagent-review-pipeline", ["implementer", "spec_reviewer", "quality_reviewer"], "workflow_harness", ["reviewer", "implementer"],
    ))
    add(_skill_turn(
        "live-dev-lifecycle", 5,
        "Prove the reviewers and implementers actually ran.",
        "Audit role execution by requiring role artifacts, status transitions, and parallel wave evidence.",
        "role-execution-audit-harness", ["role_artifacts", "parallel_wave"], "skill_call", ["role", "artifact"],
    ))
    add(_skill_turn(
        "live-dev-lifecycle", 6,
        "Now review the combined diff before landing.",
        "Run the review gate and normalize findings into pass or block status with actionable evidence.",
        "review-gate-harness", ["findings", "status"], "workflow_harness", ["findings", "status"],
    ))
    add(_skill_turn(
        "live-dev-lifecycle", 7,
        "Map regression and manual checks to release readiness.",
        "Use the QA gate to map regression evidence, manual verification, and release decision status.",
        "qa-gate-harness", ["regression_evidence", "manual_mapping"], "workflow_harness", ["regression", "manual"],
    ))
    add(_skill_turn(
        "live-dev-lifecycle", 8,
        "Give a final health and release readiness summary.",
        "Run the health check harness for test health, static quality, and release readiness evidence.",
        "health-check-harness", ["test_health", "release_readiness"], "workflow_harness", ["health", "release"],
    ))

    add(_skill_turn(
        "live-domain-equipment", 1,
        "Plan an equipment design project before execution.",
        "Use the architect pipeline to create design blueprint, constraints, deliverables, and verification plan.",
        "architect-pipeline", ["design_blueprint", "required_deliverables"], "workflow_harness", ["design", "deliverables"],
    ))
    add(_skill_turn(
        "live-domain-equipment", 2,
        "Route engineering, procurement, safety, and compliance roles.",
        "Use domain orchestration to route domain roles and deliverables through risk, policy, QA/QC, and final decision gates.",
        "domain-orchestration-harness", ["domain_design", "risk_gate", "deliverables"], "workflow_harness", ["risk", "deliverables"],
    ))
    add(_skill_turn(
        "live-domain-equipment", 3,
        "Build a matrix from requirements to evidence and review gates.",
        "Use traceability matrix rows linking requirements, deliverables, evidence keys, owners, and review gates.",
        "traceability-matrix-harness", ["requirements", "evidence_keys", "review_gates"], "skill_call", ["requirements", "evidence"],
    ))
    add(_skill_turn(
        "live-domain-equipment", 4,
        "Check whether the final design package has missing sections.",
        "Run deliverable template quality checks for required sections and evidence-backed claims.",
        "deliverable-template-quality-harness", ["required_sections", "evidence_backing"], "skill_call", ["sections", "evidence"],
    ))
    add(_skill_turn(
        "live-domain-equipment", 5,
        "Validate generated drawings and spreadsheets are readable.",
        "Use artifact render QA to validate typed document, spreadsheet, drawing, image, web, or data artifacts and attach manifest evidence.",
        "artifact-render-qa-harness", ["render_validation", "artifact_manifest"], "skill_call", ["artifact", "valid"],
    ))
    add(_skill_turn(
        "live-domain-equipment", 6,
        "Define completion criteria before release.",
        "Use GoalState with completion criteria, required evidence, blocked status, and next action.",
        "goal-state-harness", ["completion_criteria", "evidence_required"], "skill_call", ["criteria", "evidence"],
    ))
    add(_skill_turn(
        "live-domain-equipment", 7,
        "Review the package for safety findings.",
        "Run review gate findings and block release if safety evidence or required fixes are missing.",
        "review-gate-harness", ["findings", "status"], "workflow_harness", ["findings", "block"],
    ))
    add(_skill_turn(
        "live-domain-equipment", 8,
        "Only accept it after inspection and commissioning checks.",
        "Use QA gate evidence for inspection, commissioning checks, and acceptance status.",
        "qa-gate-harness", ["regression_evidence", "manual_mapping"], "workflow_harness", ["inspection", "acceptance"],
    ))

    add(_skill_turn(
        "live-memory-resume", 1,
        "Save decisions and handoff notes for the next session.",
        "Use context state to capture decisions, handoff notes, active files, evidence pointers, and restore instructions.",
        "context-state-harness", ["handoff_snapshot", "decision_log"], "skill_call", ["handoff", "decisions"],
    ))
    add(_skill_turn(
        "live-memory-resume", 2,
        "Store project-scoped memory but keep other chats isolated.",
        "Use memory state with scope isolation, project namespace, memory candidates, and cleanup policy.",
        "memory-state-harness", ["scope", "cleanup_policy"], "skill_call", ["scope", "cleanup"],
    ))
    add(_skill_turn(
        "live-memory-resume", 3,
        "When the next chat starts, decide what evidence is still missing.",
        "Use GoalState to compare objective, required evidence, current evidence, blockers, and next action.",
        "goal-state-harness", ["completion_criteria", "evidence_required"], "skill_call", ["evidence", "next"],
    ))
    add(_skill_turn(
        "live-memory-resume", 4,
        "Before resuming generated edits, restore a checkpoint if needed.",
        "Use snapshot state restore metadata to verify rollback points and checkpoint safety before continuing edits.",
        "snapshot-state-harness", ["rollback_point", "restore"], "skill_call", ["restore", "checkpoint"],
    ))
    add(_skill_turn(
        "live-memory-resume", 5,
        "Find which KH skill applies before answering.",
        "Use skill catalog to list packaged skills and read the applicable SKILL.md before selecting a route.",
        "skill-catalog", ["list_skills", "read_skill"], "skill_call", ["catalog", "read"],
    ))

    add(_skill_turn(
        "live-routing-growth", 1,
        "Is this simple enough for a direct answer or should it enter the workflow?",
        "Use request complexity router to classify complexity, domain, route, and reasons before execution.",
        "request-complexity-router", ["complexity", "route"], "skill_call", ["complexity", "route"],
    ))
    add(_skill_turn(
        "live-routing-growth", 2,
        "Run broad SIDE checks for routing, evidence, gates, and resume.",
        "Use scenario evaluation to run deterministic SIDE scenarios and report classification, evidence, gate, and resume signals.",
        "scenario-evaluation-harness", ["side_transcript", "classification"], "skill_call", ["side", "classification"],
    ))
    add(_skill_turn(
        "live-routing-growth", 3,
        "This review exposed a reusable lesson; make it survive into future sessions.",
        "Use compound engineering to capture the learning, scoped memory candidate, system update plan, and regression check plan.",
        "compound-engineering-harness", ["compound_capture", "memory_candidates"], "workflow_harness", ["compound", "memory"],
    ))
    add(_skill_turn(
        "live-routing-growth", 4,
        "This repeated workflow should become a reusable skill.",
        "Use workflow skill distiller to extract the repeatable workflow and scaffold a skill with examples and smoke checks.",
        "workflow-skill-distiller", ["repeatable_workflow", "skill_scaffold"], "skill_call", ["workflow", "skill"],
    ))
    add(_skill_turn(
        "live-routing-growth", 5,
        "Inspect the selected skill details before executing.",
        "Use the skill catalog to read packaged skill metadata and exact trigger text before applying it.",
        "skill-catalog", ["list_skills", "read_skill"], "skill_call", ["catalog", "read"],
    ))
    add(_skill_turn(
        "live-routing-growth", 6,
        "Verify a small Python harness before claiming it works.",
        "Use harness evaluator for syntax, runtime, and module verification evidence.",
        "harness-evaluator", ["syntax_check", "runtime_check"], "skill_call", ["syntax", "runtime"],
    ))
    add(_skill_turn(
        "live-routing-growth", 7,
        "Compress a repeated scenario trace but keep useful findings.",
        "Use token optimizer to preserve findings while reporting token savings for the trace.",
        "token-optimizer", ["token_savings", "preserved_facts"], "skill_call", ["token", "findings"],
        token_usage=compare_token_usage(("finding line\n" * 500) + "BLOCKER: missing evidence\n", "BLOCKER: missing evidence\n", strategy="command-output", label="scenario-trace"),
    ))

    add(_skill_turn(
        "live-role-graph-long", 1,
        "Show the core roles for a serious implementation workflow.",
        "Use orchestration role graph to show roles, handoffs, ownership, and required artifacts.",
        "orchestration-role-graph", ["roles", "handoff"], "skill_call", ["roles", "handoff"],
    ))
    add(_skill_turn(
        "live-role-graph-long", 2,
        "Add an advisor and CEO checkpoint before execution.",
        "Use the role graph to include advisor and CEO decision roles before implementation ownership begins.",
        "orchestration-role-graph", ["roles", "handoff"], "skill_call", ["advisor", "CEO"],
    ))
    add(_skill_turn(
        "live-role-graph-long", 3,
        "Now split implementation into bounded tasks.",
        "Use parallel orchestration to fan out bounded tasks and aggregate results through fan-in evidence.",
        "parallel-orchestration-harness", ["fan_out", "fan_in"], "skill_call", ["fan", "bounded"],
    ))
    add(_skill_turn(
        "live-role-graph-long", 4,
        "Require red-green evidence for every fix.",
        "Use quality gates to require failing-test-first, green verification, and review gate status.",
        "quality-gates-harness", ["red_green", "review_gate"], "workflow_harness", ["test", "review"],
    ))
    add(_skill_turn(
        "live-role-graph-long", 5,
        "Make the release gate read GoalState evidence.",
        "Use GoalState with completion criteria and evidence required before release status can become complete.",
        "goal-state-harness", ["completion_criteria", "evidence_required"], "skill_call", ["criteria", "evidence"],
    ))
    add(_skill_turn(
        "live-role-graph-long", 6,
        "Review findings should block if QA evidence is missing.",
        "Use review and QA gates together so findings and regression evidence both influence completion.",
        "review-gate-harness", ["findings", "regression_evidence"], "workflow_harness", ["findings", "regression"], additional_skills=["qa-gate-harness"],
    ))
    add(_skill_turn(
        "live-role-graph-long", 7,
        "Audit that all role outputs exist.",
        "Use role execution audit for role artifacts, status transitions, and parallel waves.",
        "role-execution-audit-harness", ["role_artifacts", "parallel_wave"], "skill_call", ["role", "artifact"],
    ))
    add(_skill_turn(
        "live-role-graph-long", 8,
        "Run final health before branch finish.",
        "Use health check harness for test health and release readiness score.",
        "health-check-harness", ["test_health", "release_readiness"], "workflow_harness", ["health", "release"],
    ))
    add(_skill_turn(
        "live-role-graph-long", 9,
        "Save a resume handoff with remaining work.",
        "Use context state to persist handoff snapshot, decisions, and next action.",
        "context-state-harness", ["handoff_snapshot", "decision_log"], "skill_call", ["handoff", "next"],
    ))
    add(_skill_turn(
        "live-role-graph-long", 10,
        "Capture reusable review and QA lessons before finishing this branch.",
        "Use compound engineering to turn review outcomes into scoped learning, memory candidates, and regression checks.",
        "compound-engineering-harness", ["compound_capture", "regression_check_plan"], "workflow_harness", ["compound", "regression"],
    ))
    add(_skill_turn(
        "live-role-graph-long", 11,
        "Turn this repeated review workflow into a skill later.",
        "Use workflow skill distiller to capture repeatable workflow steps, examples, and smoke checks.",
        "workflow-skill-distiller", ["repeatable_workflow", "skill_scaffold"], "skill_call", ["workflow", "skill"],
    ))

    return turns


def evaluate_skill_side_turns(turns: Iterable[SkillSideTurn]) -> List[SkillSideEvaluation]:
    catalog = collect_packaged_skills()
    skills = {skill["name"]: skill for skill in catalog["skills"]}
    return [evaluate_skill_side_turn(turn, skills) for turn in turns]


def evaluate_skill_side_turn(
    turn: SkillSideTurn,
    catalog_skills: Dict[str, Dict[str, Any]] | None = None,
) -> SkillSideEvaluation:
    skills = catalog_skills or {skill["name"]: skill for skill in collect_packaged_skills()["skills"]}
    skill_entry = skills.get(turn.expected_skill)
    findings: List[Dict[str, str]] = []
    signals: List[Dict[str, Any]] = []

    if not skill_entry:
        findings.append(_finding_for("skill_activation", "skill", f"unknown packaged skill: {turn.expected_skill}"))
        expected_level = ""
    else:
        expected_level = str(skill_entry["execution_level"])
        signals.append(
            {
                "category": "catalog",
                "skill": turn.expected_skill,
                "execution_level": expected_level,
            }
        )

    trace = turn.policy_trace or {}
    selected_skills = _as_list(trace.get("selected_skills") or trace.get("selected_skill"))
    expected_skills = [turn.expected_skill] + list(turn.expected_additional_skills)
    missing_skills = [skill for skill in expected_skills if skill not in selected_skills]
    if missing_skills:
        findings.append(
            _finding_for(
                "skill_activation",
                "selected_skills",
                f"expected trace to select: {', '.join(missing_skills)}",
                expected=", ".join(expected_skills),
                actual=", ".join(selected_skills),
            )
        )

    _expect_equal(findings, "route", turn.expected_route, str(trace.get("route", "")))
    _expect_equal(findings, "execution_level", expected_level, str(trace.get("execution_level", "")))

    evidence = set(_as_list(trace.get("evidence")))
    for required in turn.expected_evidence:
        if required not in evidence:
            findings.append(
                _finding_for(
                    "evidence",
                    "evidence",
                    f"missing expected evidence key: {required}",
                    expected=required,
                    actual=", ".join(sorted(evidence)),
                )
            )
    signals.append(
        {
            "category": "evidence",
            "skill": turn.expected_skill,
            "evidence_count": len(evidence),
        }
    )

    normalized_response = " ".join((turn.assistant_text or "").lower().split())
    for marker in turn.required_response_markers:
        if marker.lower() not in normalized_response:
            findings.append(
                _finding_for(
                    "assistant_policy",
                    "assistant_text",
                    f"response missing marker: {marker}",
                )
            )
    signals.append(
        {
            "category": "assistant_policy",
            "skill": turn.expected_skill,
            "route": turn.expected_route,
            "conversation_id": turn.conversation_id,
        }
    )
    token_usage = trace.get("token_usage")
    if isinstance(token_usage, dict):
        signals.append(
            {
                "category": "token_usage",
                "skill": turn.expected_skill,
                "without_token_optimizer": token_usage.get("without_token_optimizer", 0),
                "with_token_optimizer": token_usage.get("with_token_optimizer", 0),
                "estimated_tokens_saved": token_usage.get("estimated_tokens_saved", 0),
                "actual_usage_scope": token_usage.get("actual_usage_scope", ""),
                "token_count_method": token_usage.get("token_count_method", ""),
                "token_count_is_estimate": token_usage.get("token_count_is_estimate", True),
                "billing_tokens_available": token_usage.get("billing_tokens_available", False),
                "actual_tokens_saved": token_usage.get("actual_tokens_saved", 0),
                "actual_token_savings_ratio": token_usage.get("actual_token_savings_ratio", 0.0),
                "actual_bytes_saved": token_usage.get("actual_bytes_saved", 0),
                "actual_byte_savings_ratio": token_usage.get("actual_byte_savings_ratio", 0.0),
            }
        )

    return SkillSideEvaluation(
        turn_id=turn.turn_id,
        conversation_id=turn.conversation_id,
        turn_index=turn.turn_index,
        expected_skill=turn.expected_skill,
        passed=not findings,
        expected={
            "skill": turn.expected_skill,
            "additional_skills": turn.expected_additional_skills,
            "execution_level": expected_level,
            "route": turn.expected_route,
            "evidence": turn.expected_evidence,
        },
        actual={
            "policy_trace": trace,
            "assistant_text": turn.assistant_text,
        },
        findings=findings,
        signals=signals,
    )


def build_skill_side_report(evaluations: Iterable[SkillSideEvaluation]) -> Dict[str, Any]:
    records = list(evaluations)
    catalog = collect_packaged_skills()
    catalog_skills = {skill["name"] for skill in catalog["skills"]}
    observed_skills = {record.expected_skill for record in records}
    conversation_ids = {record.conversation_id for record in records}
    turn_counts = {
        conversation_id: len([record for record in records if record.conversation_id == conversation_id])
        for conversation_id in conversation_ids
    }
    selected_skill_counts: Dict[str, int] = {}
    route_counts: Dict[str, int] = {}
    execution_level_counts: Dict[str, int] = {}
    multi_skill_turn_count = 0
    for record in records:
        trace = record.actual.get("policy_trace", {})
        selected_skills = _as_list(trace.get("selected_skills") or trace.get("selected_skill"))
        if len(selected_skills) > 1:
            multi_skill_turn_count += 1
        for skill in selected_skills:
            selected_skill_counts[skill] = selected_skill_counts.get(skill, 0) + 1
        route = str(trace.get("route", ""))
        if route:
            route_counts[route] = route_counts.get(route, 0) + 1
        execution_level = str(trace.get("execution_level", ""))
        if execution_level:
            execution_level_counts[execution_level] = execution_level_counts.get(execution_level, 0) + 1
    signals = [signal for record in records for signal in record.signals]
    token_usage_records = [
        record.actual["policy_trace"]["token_usage"]
        for record in records
        if isinstance(record.actual.get("policy_trace"), dict)
        and isinstance(record.actual["policy_trace"].get("token_usage"), dict)
    ]
    unexpected_failures = [record.to_dict() for record in records if not record.passed]
    return {
        "summary": {
            "total": len(records),
            "passed": len([record for record in records if record.passed]),
            "failed": len(unexpected_failures),
            "skill_count": len(observed_skills),
            "catalog_skill_count": len(catalog_skills),
            "missing_catalog_skills": sorted(catalog_skills - observed_skills),
            "conversation_count": len(conversation_ids),
            "multi_turn_conversation_count": len([count for count in turn_counts.values() if count >= 2]),
            "min_turns_per_conversation": min(turn_counts.values()) if turn_counts else 0,
            "max_turns_per_conversation": max(turn_counts.values()) if turn_counts else 0,
            "multi_skill_turn_count": multi_skill_turn_count,
            "selected_skill_counts": dict(sorted(selected_skill_counts.items())),
            "route_counts": dict(sorted(route_counts.items())),
            "execution_level_counts": dict(sorted(execution_level_counts.items())),
            "signal_categories": sorted({signal["category"] for signal in signals}),
            "meaningful_signal_count": len(signals),
            "token_usage": aggregate_token_usage_stats(token_usage_records),
        },
        "unexpected_failures": unexpected_failures,
    }


def _assistant_policy_findings(complexity: str, assistant_text: str) -> List[Dict[str, str]]:
    normalized = " ".join((assistant_text or "").strip().lower().split())
    findings: List[Dict[str, str]] = []
    if complexity == "ambiguous":
        if "?" not in assistant_text and not _contains_any(normalized, {"need", "before", "which", "what", "permission"}):
            findings.append(_finding("ambiguous response did not ask for missing context"))
    elif complexity == "high_risk":
        if not _contains_any(normalized, {"urgent", "risk", "call", "emergency", "permission", "do not", "scope"}):
            findings.append(_finding("high-risk response did not include a safety or risk gate"))
    elif complexity == "heavy":
        if not _contains_any(normalized, {"plan", "design", "verify", "test", "evidence", "steps"}):
            findings.append(_finding("heavy response did not describe a planned evidence workflow"))
    elif complexity == "medium":
        if len(normalized.split()) < 12:
            findings.append(_finding("medium response was too thin for structured help"))
    elif complexity == "light":
        if len(normalized.split()) > 120:
            findings.append(_finding("light response was too long for a direct answer"))
    return findings


def _policy_checks_for(complexity: str) -> List[str]:
    return {
        "ambiguous": ["asks_for_missing_context"],
        "high_risk": ["safety_or_risk_gate"],
        "heavy": ["planned_evidence_workflow"],
        "medium": ["structured_help"],
        "light": ["direct_answer"],
    }.get(complexity, ["classification_present"])


def _expect_equal(findings: List[Dict[str, str]], field: str, expected: str, actual: str) -> None:
    if expected and expected != actual:
        findings.append(
            {
                "category": "classification",
                "field": field,
                "expected": expected,
                "actual": actual,
            }
        )


def _finding(message: str) -> Dict[str, str]:
    return {"category": "assistant_policy", "field": "assistant_text", "message": message}


def _finding_for(
    category: str,
    field: str,
    message: str,
    expected: str = "",
    actual: str = "",
) -> Dict[str, str]:
    finding = {"category": category, "field": field, "message": message}
    if expected:
        finding["expected"] = expected
    if actual:
        finding["actual"] = actual
    return finding


def _contains_any(text: str, terms: set[str]) -> bool:
    return any(term in text for term in terms)


def _skill_turn(
    conversation_id: str,
    turn_index: int,
    user_text: str,
    assistant_text: str,
    expected_skill: str,
    evidence: Sequence[str],
    route: str,
    markers: Sequence[str],
    token_usage: Dict[str, Any] | None = None,
    additional_skills: Sequence[str] = (),
) -> SkillSideTurn:
    selected_skills = [expected_skill] + list(additional_skills)
    policy_trace = {
        "selected_skills": selected_skills,
        "route": route,
        "execution_level": _execution_level_for(expected_skill),
        "evidence": list(evidence),
        "conversation_id": conversation_id,
        "turn_index": turn_index,
        "side_mode": "kh_assistant",
    }
    if token_usage:
        policy_trace["token_usage"] = token_usage
    return SkillSideTurn(
        turn_id=f"{conversation_id}-{turn_index:02d}-{expected_skill}",
        conversation_id=conversation_id,
        turn_index=turn_index,
        user_text=user_text,
        assistant_text=assistant_text,
        expected_skill=expected_skill,
        expected_evidence=list(evidence),
        expected_route=route,
        expected_additional_skills=list(additional_skills),
        required_response_markers=list(markers),
        policy_trace=policy_trace,
        context={"conversation_id": conversation_id, "turn_index": turn_index},
    )


def _execution_level_for(skill_name: str) -> str:
    for skill in collect_packaged_skills()["skills"]:
        if skill["name"] == skill_name:
            return str(skill["execution_level"])
    return ""


def _as_list(value: Any) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value]
    if isinstance(value, tuple):
        return [str(item) for item in value]
    if isinstance(value, set):
        return [str(item) for item in sorted(value)]
    return [str(value)]


def _sample_noisy_log() -> str:
    progress = [f"tests/test_bulk.py::test_case_{index} PASSED" for index in range(80)]
    failure = [
        "tests/test_invoice.py::test_total_rounding FAILED",
        "Traceback (most recent call last):",
        "AssertionError: 119999 == 120000",
        "exit code: 1",
    ]
    return "\n".join(progress[:40] + failure + progress[40:])


def _sample_optimized_log() -> str:
    return "\n".join(
        [
            "... [command-output optimized: repeated passed tests omitted; family=test] ...",
            "tests/test_invoice.py::test_total_rounding FAILED",
            "Traceback (most recent call last):",
            "AssertionError: 119999 == 120000",
            "exit code: 1",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate KH interactive SIDE assistant transcripts.")
    parser.add_argument("--summary", action="store_true", help="Print summary JSON.")
    parser.add_argument("--skills", action="store_true", help="Evaluate all packaged skill/harness SIDE turns.")
    parser.add_argument("--stress", action="store_true", help="Use broader live-style SIDE transcript stress fixtures.")
    args = parser.parse_args()

    if args.skills:
        turns = stress_skill_side_turns() if args.stress else default_skill_side_turns()
        report = build_skill_side_report(evaluate_skill_side_turns(turns))
    else:
        report = build_interactive_side_report(evaluate_interactive_side_turns([]))
    if args.summary:
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if not report["unexpected_failures"] else 1


if __name__ == "__main__":
    sys.exit(main())
