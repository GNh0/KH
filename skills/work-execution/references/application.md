# Applying KH to actual development

Skill discovery stays automatic. Inspecting, comparing or maintaining a skill document is not development application. Analysis/query explanation/PBL extraction alone does not apply code-writing checks.

For actual project-file work, the agent registers the owned output files and responsibilities once, before writing. The bundled hook supplies the exact current project/chat/agent scope, data root and epoch when an entrypoint is delivered or explicitly requested. Use those values with `scripts/kh_context.py`, followed by `apply --work <kind> --target <file>`; repeat work/target flags when the change combines responsibilities. This is an internal lifecycle step, not another user approval, checklist or profile file. Do not invent a chat id, search another chat, use a stale epoch or change host trust settings.

```text
python -B <plugin-root>/scripts/kh_context.py --cwd <cwd> --session <session> --transcript <transcript> --host <host> --data-root <exact-context-v1-root> --epoch <epoch> apply --work <kind> --target <owned-file> --reference <actual-comparison-source[#Lstart-Lend]>
```

Include `--agent-id` when supplied. The data root already ends in context-v1; do not append that name again. Keep the scope unchanged across the helper and hooks. If hooks or their scope are unavailable, do not invent activation evidence: perform the explicit source/style audit and report automatic enforcement as unavailable.

Select the actual approved comparison program/source for the changed responsibility before writing. Add `--reference <source>` to apply; repeat it for separately needed source units. `#Lstart-Lend` optionally limits a unit to the relevant complete body. The helper returns path/range information, but registration does not count as reading. Retrieve the current source body after selection through Read/read_file or an explicit Get-Content/cat read identifying that source. Returned identical text from an unrelated path does not count. Unsupported dynamic read commands remain unverified; use a supported explicit read when the gate needs evidence. Numbered and segmented returned bodies can accumulate; changed source invalidates its evidence. An owned output cannot certify itself as a reference. Ordinary SQL formatting alone preserves existing behavior and does not require a new comparison program.

A range/read record cannot prove that a program is approved, implements the same responsibility or covers the complete caller flow. The agent must establish those facts from the user's instructions and actual source under the shared cycle. Do not use a generated draft, a trivial declaration or arbitrary lines to satisfy the observation check. If actual comparison evidence is missing, retrieve it or report the gap; do not invent a baseline.

Each apply call attaches its references to the responsibilities selected in that call, not every responsibility previously registered on the target. Add query, printing or control comparison units with their own `--work` selection. A PB migration requires the actual PB source as a `pb-migrate` reference and separate C#/SQL style sources for the output responsibilities; an output-language example cannot replace PB behavior. Stored references are rechecked against these roles. A selected author's SELECT-only SP cannot establish a SAVE reference. Observed statements and balanced blocks remain partial syntax evidence; verify indirect calls, complete grammar and actual same-responsibility behavior from source.

For control/Designer work, select the actual comparison layout and the target's complete control-definition units separately. Constructor defaults alone do not establish a comparison screen. Current, observed selected control definitions are also passed to the saved-file checker, even without a nearby project file; their hashes invalidate the comparison when those sources change. Only selected/returned ranges supply these definitions, so retrieve the enclosing complete class when a small method fragment lacks its type/constructor context.

Separate control-definition files do not compete as alternative screen programs. A selected definition or new range that is unread or stale remains missing evidence before writing and incomplete in saved checks; omitting its defaults must not turn a known size violation into a pass. Reselect the current unit and read it instead of reusing an older file/range receipt.

Choose responsibilities from the actual change:

For `sql-select`/`sql-save`, follow [SP authorship](../../sql-formatting/references/procedure-authorship.md). Pass the target header name with `--author` and each existing-SP search name with its own `--reference-author`. When selecting SQL files, pass the full set for the selected SP responsibility and read each definition. A later selection replaces that responsibility's SQL sources. Omitting references retains the selection.

| Work | Applies to |
| --- | --- |
| `csharp-code` | C# methods and expression style |
| `csharp-control` | Control/Repository creation or initialization, including code-behind |
| `csharp-designer` | Designer layout and controls; also enforced for a registered .Designer.cs |
| `csharp-grid` | Grid defaults, columns and editor configuration |
| `csharp-data` | Query/save, XML, focus/selection and binding |
| `csharp-report` | Report data, preview and printing |
| `csharp-monitoring` | Repeated queries and rebinding |
| `sql-format` | Formatting existing SQL with lexical/alias preservation, no behavior change |
| `sql-query` | Standalone query generation/edits without a stored-procedure contract |
| `sql-select` | SELECT/report procedure work and SELECT patterns |
| `sql-save` | SAVE/XML writes and validation patterns |
| `pb-edit` | Native PB source edits |
| `pb-migrate` | PB migration plus the actual C#/SQL output responsibilities above |

Combine actual responsibilities: a code-behind editor change needs `csharp-control`, even without a Designer edit. A migration needs `pb-migrate` plus the relevant C#/SQL kinds for its named outputs. SELECT-only work does not require SAVE examples. Pure PB analysis/extraction does not require a C#/SQL application. For combined SELECT/SAVE work, select both SQL kinds. A procedure declaration cannot use only the standalone-query route. Formatting preserves existing tokens/allowed alias changes; new source uses the relevant query/procedure route. Direct snippet formatting has no source-file application and still follows SQL style. Do not choose a narrower kind merely to omit applicable rules. For registered C#, supported known-framework construction and actual control-receiver changes expand control/grid/report reference requirements from the before/after source, including code-behind. Aliases, unresolved types and business intent still require source judgment; automatic inference is bounded and not a full C# type checker. Explicitly selected responsibilities stay declared; inferred responsibilities are recalculated from the current saved/proposed change. Retracting a denied unsaved proposal does not keep that proposal's extra scope.

The helper returns the exact required references, missing sections and absolute file/line ranges. A `#fragment` identifies a required Markdown section, not part of a filesystem name. Read the given ranges; a complete file read also covers its sections and segmented reads may accumulate. This keeps unrelated coding/SQL sections out of the prompt. Inspect the actual comparison program and target flow and follow the shared [source-style cycle](source-style-cycle.md). Registration records intent and captures immutable originals; it does not mark anything read, audited or correct. A skill token, native selection or document read does not identify the actual development files. The agent must apply the owned outputs before writing; enforce checks those exact applications. Unregistered destinations can receive a conditional coverage notice and remain unverified without source inspection, snapshots or Stop denial. A missing apply is not a compliance pass: the main agent must detect it from the actual assignment/tool trace and complete the source-style audit. Do not infer file ownership from a skill-name mention or extend it to excluded work. Only registered files receive code-writing checks; adding another responsibility preserves existing originals and read evidence. New files/responsibilities must be added before writing them.

Use `recall` for current state. Pause remains authoritative; apply cannot resume work. Stop/new-task boundaries retire the old application, while an interrupted repair retains its original files and current scope. Completion status distinguishes observed checks from semantic audit: `checks_complete` / `checks_complete_audit_unverified` never means the source/necessity/regression audit was proved. An unresolved warning remains unresolved on repeated Stop feedback. A successful checker remains partial evidence; the source comparison, necessity review and final regression audit remain the main agent's responsibility.
