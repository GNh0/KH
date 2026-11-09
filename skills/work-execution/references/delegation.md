# KH workers and independent review

Use this flow for approved substantial SQL, C#/Designer or PB work when the host permits delegation. The main agent is the controller. A worker already assigned by a controller returns its result to that controller.

Choose the worker whose responsibility owns the change.

- [kh-sql-worker](../../../agents/kh-sql-worker.md) handles SQL procedures and query contracts.
- [kh-csharp-worker](../../../agents/kh-csharp-worker.md) handles WinForms, Designer, DevExpress and reports.
- [kh-pb-worker](../../../agents/kh-pb-worker.md) handles PB source behavior and migration across C#, Designer and SQL.
- [kh-rule-auditor](../../../agents/kh-rule-auditor.md) independently checks the actual changes and evidence.

## Dispatch

Use an advertised native agent type when its definition matches the packaged role. Otherwise pass the complete role instructions in an actual host subagent call, or pass an absolute role-file path and require the child to read it completely before acting. Include the absolute KH package root, target workspace, original requirements and corrections, owned files, approved reference paths, applicable limits, expected result and verification scope. Use the host's actual tool schema. Prefer a fresh context with the necessary source evidence when supported. Inherit the session model unless the user or configured role chooses another model.

The controller owns sequencing and shared state. Give independent workers disjoint edit scopes. Keep one owner for each file, database transaction and external apply operation. Convey existing authorization and limits accurately.

## Review and correction

After the worker finishes, collect the actual diff, baseline/reference paths and verification results. Dispatch the auditor with that evidence and the original requirements. The auditor reads the current source and returns concrete findings, verification gaps and a status.

For confirmed violations, return the affected findings to the responsible worker. Have it repair the responsible code, rerun the affected checks and report the diff. Re-review those findings and regression risks introduced by the repair. Continue while confirmed violations remain and a supported repair is available. Diagnose repeated failures before another attempt. A missing dependency, authorization limit or unavailable runtime remains an explicit unresolved item.

Before completion, the controller checks the combined final change, the caller's behavior and the evidence covering the original scope. A worker's completion, an agent status or a passing local checker alone does not establish that outcome.

## Host and lifecycle boundaries

Creation of a subagent and completion of its work are separate events. Collect the actual tool result or error and track each live agent through completion or interruption. On user stop, interrupt outstanding workers and release finished task-owned resources under the runtime cleanup procedure.

Claude Code can discover the packaged `agents/` definitions through its plugin. Codex plugin skill discovery supplies the skills; custom named-agent installation is a separate host feature. The role-instructions dispatch above works with the available Codex subagent tools without asserting that a plugin upgrade registered a native agent type. If subagent tools are unavailable, carry out the applicable source/style and rule-audit flow in the current agent and report the verification scope accurately.
