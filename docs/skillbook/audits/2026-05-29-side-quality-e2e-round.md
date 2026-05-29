# SIDE Quality and E2E Review Round

Date: 2026-05-29

## Scope

This review round used SIDE-style independent review across:

- broad review of all 27 packaged skills
- token optimizer and command-output stress testing
- orchestration truthfulness and role DAG runtime checks
- practical end-to-end workflow scenarios
- install and upgrade usability review from the main thread

The purpose was to move quality judgment away from the internal 10-point packaging score and toward practical behavior.

## SIDE Findings

### Broad Skill Review

Strengths:

- 27/27 packaged skills are structurally valid.
- Execution levels are explicit: python-module, hybrid-harness, procedure-policy.
- Evidence, blocked state, runtime storage, and "feature exists vs actually executed" language are consistently present.

Weaknesses:

- Several skills overlap in trigger boundary, especially development lifecycle, quality, QA, review, health, host, adapter, parallel, subagent, and role graph.
- Many minimal examples still feel generic instead of proving the unique contract of the skill.
- `development-lifecycle-harness`, `host-agent-orchestration`, `subagent-review-pipeline`, `health-check-harness`, and `harness-evaluator` need sharper boundaries and more concrete examples.

Practical score from SIDE: about 7/10 versus strong open-source skillbooks, despite strong packaging health.

### Token and Command Output Review

Passed:

- Existing command-output tests passed.
- Pytest numeric assertion logs, build errors, and simple agent traces were compressed while preserving core facts.

Failed:

- Pytest multiline diffs could lose expected/actual values.
- Generic successful agent traces could lose `USER_CONSTRAINT`, `DECISION`, and `EVIDENCE` facts.
- Python minification could remove `type: ignore`, `noqa`, `IMPORTANT`, and compatibility comments.
- Non-Python test/build command family detection was narrow.

### Orchestration Review

Passed:

- KH UAF has real local runtime execution for role DAG waves, bounded implementer workers, review/QA/security/release gates, role artifacts, and `role_execution_audit`.
- Direct runtime proof showed two-file workflow success, 12 required roles, parallel role waves, and passed role audit.

Gaps:

- Packaged role demos under-prove full role execution because some demos focus on pre-implementation roles.
- Role artifacts are templated role-stage outputs, not independent reasoning transcripts.
- Runtime overlap evidence was not persisted in role metadata.
- Native/Antigravity paths can preserve role metadata without proving local DAG execution.

### E2E Review

Passed:

- CLI help, catalog, KH-Bench, skill quality, and failure/blocked demos work.
- Product/domain deliverable plumbing creates expected file types.

Failed or weak:

- Offline CLI workflows can mechanically complete while producing smoke/demo files rather than a task-faithful app.
- Markdown generation for README dropped surrounding prose when a fenced command block appeared.
- Product design drawings were too hard-coded and did not reflect supplied dimensions, material, or hole count.
- Novice docs needed a clearer smoke-only warning for offline provider output.

## Changes Applied

- Rewrote `README.ko.md` from mojibake into readable Korean.
- Added Codex upgrade note explaining version-based plugin cache behavior.
- Added explicit offline smoke-only warning to `README.md`, `README.ko.md`, and CLI output.
- Fixed Markdown target extraction so `.md` files preserve embedded fenced blocks unless the whole response is one fenced block.
- Added token/output preservation for pytest multiline diffs, agent trace markers, Python pragmas, and non-Python test/build command families.
- Updated product-design export to parse dimensions, material, hole count, and hole spec from source text, then reflect them in BOM, SVG, and DXF.
- Added role runtime metadata: `started_at_utc`, `finished_at_utc`, `duration_seconds`, `runner_type`, `adapter_name`, and `independent_process`.
- Added `runtime_overlap_wave_count` to role orchestration summary and made audit fail when explicit overlap evidence is present but zero.

## Remaining Queue

P1:

- Add a trigger arbitration matrix so overlapping skills choose a primary skill instead of competing.
- Add full-workflow role demos that run `dispatch_project_workflow()` and prove implementer, reviewer, QA, security, release, role artifacts, and audit.
- Add semantic acceptance checks from the original prompt into goal evidence for real provider runs.

P2:

- Add per-skill examples that contain concrete input, function/CLI call, expected JSON, and blocked case.
- Add health-check threshold/weight documentation.
- Add adapter metadata contract for true external subagent execution versus local Python role tasks.

## Verification Commands

Targeted checks after fixes:

```bash
python -B -m unittest tests.test_command_output_runtime tests.test_builtin_skill_runtime tests.test_plugin_packaging tests.test_docs_branding tests.test_task_runners tests.test_cli_config tests.test_artifact_manifest tests.test_orchestration_roles tests.test_quality_harnesses tests.test_workflows.WorkflowDispatchTests.test_role_execution_audit_requirement_is_satisfied_after_review_roles
python -B -c "import pathlib; [compile(p.read_text(encoding='utf-8'), str(p), 'exec') for p in pathlib.Path('.').rglob('*.py')]; print('compile_ok=1')"
python -B -m src.benchmarks.kh_bench_verified --summary
```

Results:

- Targeted tests: 78 passed.
- No-write Python compile: `compile_ok=1`.
- KH-Bench Verified: 6/6 passed.

