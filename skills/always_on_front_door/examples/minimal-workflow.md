# Minimal Workflow

## Scenario

The host must distinguish three requests without loading the whole catalog.

### Direct request

User: `What does idempotent mean?`

Expected path: answer directly. Do not run Python, open another skill, or emit routing telemetry.

### Specialist request

User: `Format this SQL without changing its behavior.`

Expected path:

1. Select `sql-formatting` from its description.
2. Read only that skill and any support file it explicitly requires.
3. Preserve the SQL contract and run its packaged verifier.
4. Return the formatted SQL and concise verification result.

The front-door Python runtime is not required merely to select the SQL skill.

### Governed request

User: `Review this production migration, coordinate independent reviewers, and give me auditable release evidence.`

## Expected steps

1. Answer the direct request without Python or another skill read.
2. Read only `sql-formatting` for the specialist request and run its verifier.
3. For the governed request, select the relevant safety, orchestration, review, and verification skills.
4. Run the deterministic front door only when a reproducible routing and authorization packet is useful.
5. Keep applied skills distinct from skills selected for later execution and preserve role outputs and gate evidence.

## Expected evidence

- Direct: `execution_level = host-native-semantic`; no runtime receipt is claimed.
- Specialist: the selected skill path and verifier result are observable.
- Governed: `execution_level = python-module` and `actual_runtime_path = src.orchestration.kh_front_door.build_kh_front_door`.
- Applied, selected-not-executed, blocked, and skipped states remain distinct.

## Implementation targets

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.session_skill_audit.analyze_session_skills`
- `src.orchestration.git_workspace_gate`
- `tests.test_kh_front_door_always_on`

## Failure cases

- Running Python for a clear direct or single-skill request.
- Reading every skill before choosing one.
- Selecting a skill from one example word while ignoring the request's actual objective.
- Claiming a listed skill ran when its behavior or executable target was never used.
- Hiding a better matching host/plugin skill behind KH routing.
- Writing raw routing JSON into the ordinary final answer.

## Done criteria

The user receives the smallest adequate workflow, observable evidence for work that needs it, and no routing overhead that does not improve the result.

## Runtime binding

- execution_level: `host-native-semantic` or `python-module`
- implementation_targets: the five targets listed above
- actual_runtime_path: `src.orchestration.kh_front_door.build_kh_front_door` only when governed runtime mode executes
