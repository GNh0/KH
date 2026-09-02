# Front Door Audit Usage

## When to use

Do not load this skill to perform ordinary host-native selection. The plugin-level default is:

- direct answer when the request is self-contained
- one matching specialist skill when its description clearly applies
- a small process-plus-domain combination only when both materially change the work

Do not read this skill or run the Python router merely because a request needs a file read, database call, tool, SQL change, or C# edit. The selected domain skill and the host's normal safety policy govern that work.

Use the deterministic runtime only when at least one condition is present:

- the user asks for routing, skill-usage, or audit evidence
- multiple providers genuinely conflict and semantic selection cannot resolve them
- a large workflow needs a reproducible GoalState, orchestration, or evidence packet
- a high-risk operation needs a machine-readable authorization boundary
- KH routing itself is being debugged or regression-tested

This skill is explicit-only in Codex metadata. The user may name it for an audit, or a governed runtime may invoke it after a concrete high-risk/large-work trigger. It must not self-select on every new request.

Execution level: `host-native-semantic` for direct or specialist selection; `python-module` only for governed runtime audit mode.

Implementation targets:

- `src.orchestration.kh_front_door.build_kh_front_door`
- `src.orchestration.request_classifier.classify_request`
- `src.orchestration.session_skill_audit.analyze_session_skills`
- `src.orchestration.git_workspace_gate`
- `tests.test_kh_front_door_always_on`

## Inputs to collect

- `prompt`: exact user request
- `project`: exact target project or current working directory
- `host`: `codex`, `antigravity`, `claude-code`, or `local`
- optional context: active artifact, approved plan, provider availability, and current task state

Do not infer authority from an unrelated prior project, chat, or subagent.

Within a current unfinished task, a pure acknowledgement may reuse its selected path. After task completion, a new task, or a changed target, select again.

## Execution pattern

1. Confirm the explicit audit or governed trigger before reading this reference.
2. Audit the expected direct, specialist, or governed mode from visible context.
3. Treat a read of this skill during an ordinary direct or single-domain request as a routing defect.
4. For governed mode, run the UTF-8-safe command below and retain the runtime receipt internally.

## Windows UTF-8 invocation

For non-ASCII prompts, write UTF-8 without BOM and pass files rather than interpolating the request into a shell command:

```powershell
$promptPath = Join-Path $env:TEMP "kh-front-door-prompt.txt"
$contextPath = Join-Path $env:TEMP "kh-front-door-context.json"
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($promptPath, $exactUserRequest, $utf8NoBom)
$context | ConvertTo-Json -Depth 10 | ForEach-Object {
    [System.IO.File]::WriteAllText($contextPath, $_, $utf8NoBom)
}
python "<skill-folder>\scripts\front_door.py" --prompt-file $promptPath --context-file $contextPath --project "<target>" --host codex --micro-summary --strict-execution-gate
```

Use `--summary` only when a human-readable audit packet is required. Exit code 3 means the intake ran but execution remains gated; it is not a Python crash.

## Evidence to produce

When auditing ordinary semantic selection after the fact, evidence is the observable path:

- direct answer with no unnecessary routing call, or
- the selected skill read followed by behavior or executable output that matches it

For deterministic runtime mode, retain the classification, selected provider, authorization gate, applied-versus-selected skill status, and source path in tool output or an audit artifact. Do not expose raw routing JSON in ordinary answers.

Reading a skill proves inspection, not successful execution. Conversely, ordinary work does not need a synthetic runtime receipt merely to prove that semantic selection occurred.

For governed mode, record `actual_runtime_path = src.orchestration.kh_front_door.build_kh_front_door`.

## Failure handling

- If a selected skill cannot be read, report the missing or stale path once and continue with a safe host-native fallback when possible.
- If the deterministic runtime fails, do not retry broad path scans. Report the concrete command/import/path failure.
- If the request is ambiguous, ask the smallest question that resolves the user decision; do not replace ambiguity with a guessed workflow.
- If a specialist skill was selected incorrectly, correct the selection rather than adding a phrase-specific routing rule.

## Quality bar

The audit succeeds when it proves that common requests incurred no front-door skill read, no Python startup, no catalog scan, no global-memory preflight, no routing narration, and no unrelated skill reads. Deterministic code should validate observable facts and high-risk gates, not attempt to encode all natural-language meaning.
