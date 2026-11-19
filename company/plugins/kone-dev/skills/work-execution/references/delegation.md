# Optional specialist work and independent review

The current main agent implements and integrates work by default. Do not dispatch a worker merely because SQL, C# or PB is involved. Use a bounded specialist task or independent review when it has a concrete benefit and the current host/user permits delegation.

| Scope | Role instructions |
| --- | --- |
| SQL procedures and query/save contracts | [SQL worker](../../../agents/kone-sql-worker.md) |
| C#, Designer and reports | [C# worker](../../../agents/kone-csharp-worker.md) |
| PB analysis and migration | [PB worker](../../../agents/kone-pb-worker.md) |
| Independent review | [Rule auditor](../../../agents/kone-rule-auditor.md) |

For hosts without a matching native agent type, pass the full role instructions or their absolute file path through the actual subagent tool, with the plugin root, target workspace, original requirements/corrections, owned scope, approved references and existing authorization limits. Use the host's real schema. Inherit the session model unless the user or applicable configuration chooses another model. A file in agents/ does not itself register a Codex native agent type.

Workers audit their own final assigned result before returning. The main agent then checks integration and requirement coverage. An independent auditor can review main-authored work without an implementation worker first. A self-audit is not an independent review.

Repair confirmed violations within scope, re-read the repaired result and repeat the affected audit. When an independent reviewer was selected, retain it for the affected re-review. A later edit invalidates the evidence for its affected scope. Before completion, check the combined final result for introduced regressions in related callers, controls and data contracts.

These are task instructions, not an automatic completion hook. Do not claim a review occurred from packaged role definitions or a checker exit code. If subagents are unavailable, perform the applicable source comparison and rule audit in the main agent and report the verified scope.

Track launched work through completion or interruption. Stop delegated work on a user stop and release no-longer-needed task-owned runtime resources.
