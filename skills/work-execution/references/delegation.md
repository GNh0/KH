# KH selective delegation and independent review

The main agent handles the task by default, including implementation, and owns requirements, sequencing, integration and the final result. Delegate only when a bounded specialist task or independent review has a concrete benefit and the host permits it. A worker already assigned by the main agent completes its scope and returns evidence without further delegation.

## Choose whether to delegate

Useful cases include an independent investigation, specialist analysis whose intermediate output would crowd the main context, an implementation with a clear separate scope, or a fresh review justified by the change's risk, uncertainty or repeated violations. Honor an explicit request for independent review. Keep short tasks and dependent steps in the main agent. A domain name, task size, available role or tool call alone does not justify a subagent.

The main agent can implement the whole change and delegate only its review. Delegating implementation does not automatically require another agent for every step or review. In either mode, the same domain skills, required [source-style cycle](source-style-cycle.md) and [rule audit](../../rule-audit/SKILL.md) apply. A self-audit is not an independent review; report which was actually performed.

When delegation is useful, choose the role that owns that scope.

- [kh-sql-worker](../../../agents/kh-sql-worker.md) handles SQL procedures and query contracts.
- [kh-csharp-worker](../../../agents/kh-csharp-worker.md) handles WinForms, Designer, DevExpress and reports.
- [kh-pb-worker](../../../agents/kh-pb-worker.md) handles PB source behavior and migration across C#, Designer and SQL.
- [kh-rule-auditor](../../../agents/kh-rule-auditor.md) independently checks the actual changes and evidence.

## Dispatch

Use an advertised native agent type when its definition matches the packaged role. Otherwise pass the complete role instructions in an actual host subagent call, or pass an absolute role-file path and require the child to read it completely before acting. Include the absolute KH package root, target workspace, original requirements and corrections, owned files, approved reference paths, applicable limits, expected result and verification scope. Use the host's actual tool schema. Prefer a fresh context with the necessary source evidence when supported. Inherit the session model unless the user or configured role chooses another model.

The main agent owns sequencing and shared state. Give independent workers disjoint edit scopes. Keep one owner for each file, database transaction and external apply operation. Convey existing authorization and limits accurately. The main agent can use domain tools and checkers directly; their availability does not require a worker.

## Review and correction

After the main agent or a worker finishes the change, audit the actual diff, baseline/reference paths and verification results against the original requirements. When independent review is selected, dispatch the auditor with that evidence; no implementation worker is required first. The auditor reads the current source and returns concrete findings, verification gaps and a status.

For confirmed violations, the change owner repairs only the affected code: the main agent fixes its own work directly, or returns the findings to the responsible worker. Rerun affected checks and re-audit the repaired scope; retain the independent reviewer for its affected re-review when one was selected. Continue while confirmed violations remain and a supported repair is available. Diagnose repeated failures before another attempt. A missing dependency, authorization limit or unavailable runtime remains an explicit unresolved item.

Before completion, the main agent checks the combined final change and whether the repairs introduced regressions in related callers, initialization, bindings, data contracts or previously working behavior. Repair introduced problems and repeat the affected audit and regression checks. A worker's completion, an agent status or a passing local checker alone does not establish the original task's outcome.

## Host and lifecycle boundaries

Creation of a subagent and completion of its work are separate events. Collect the actual tool result or error and track each live agent through completion or interruption. On user stop, interrupt outstanding workers and release finished task-owned resources under the runtime cleanup procedure.

Claude Code can discover the packaged `agents/` definitions through its plugin. Codex plugin skill discovery supplies the skills; custom named-agent installation is a separate host feature. The role-instructions dispatch above works with the available Codex subagent tools without asserting that a plugin upgrade registered a native agent type. If subagent tools are unavailable, carry out the applicable source/style and rule-audit flow in the current agent and report the verification scope accurately.
