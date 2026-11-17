# Applying KH to actual development

Skill discovery stays automatic. Inspecting, comparing or maintaining a skill document is not development application. Analysis/query explanation/PBL extraction alone does not apply code-writing checks.

For actual project-file work, the agent registers the owned output files and responsibilities once, before writing. The bundled hook supplies the exact current project/chat/agent scope, data root and epoch when an entrypoint is delivered or explicitly requested. Use those values with `scripts/kh_context.py`, followed by `apply --work <kind> --target <file>`; repeat work/target flags when the change combines responsibilities. This is an internal lifecycle step, not another user approval, checklist or profile file. Do not invent a chat id, search another chat, use a stale epoch or change host trust settings.

```text
python -B <plugin-root>/scripts/kh_context.py --cwd <cwd> --session <session> --transcript <transcript> --host <host> --data-root <exact-context-v1-root> --epoch <epoch> apply --work <kind> --target <owned-file>
```

Include `--agent-id` when supplied. The data root already ends in context-v1; do not append that name again. Keep the scope unchanged across the helper and hooks. If hooks or their scope are unavailable, do not invent activation evidence: perform the explicit source/style audit and report automatic enforcement as unavailable.

Choose responsibilities from the actual change:

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

Combine actual responsibilities: a code-behind editor change needs `csharp-control`, even without a Designer edit. A migration needs `pb-migrate` plus the relevant C#/SQL kinds for its named outputs. SELECT-only work does not require SAVE examples. Pure PB analysis/extraction does not require a C#/SQL application. For combined SELECT/SAVE work, select both SQL kinds. A procedure declaration cannot use only the standalone-query route. Formatting preserves existing tokens/allowed alias changes; new source uses the relevant query/procedure route. Direct snippet formatting has no source-file application and still follows SQL style. Do not choose a narrower kind merely to omit applicable rules.

The helper returns the exact required references, missing sections and absolute file/line ranges. A `#fragment` identifies a required Markdown section, not part of a filesystem name. Read the given ranges; a complete file read also covers its sections and segmented reads may accumulate. This keeps unrelated coding/SQL sections out of the prompt. Inspect the actual comparison program and target flow and follow the shared [source-style cycle](source-style-cycle.md). Registration records intent and captures immutable originals; it does not mark anything read, audited or correct. Only registered files receive code-writing checks; adding another responsibility preserves existing originals and read evidence. New files/responsibilities must be added before writing them.

Use `recall` for current state. Pause remains authoritative; apply cannot resume work. Stop/new-task boundaries retire the old application, while an interrupted repair retains its original files and current scope. A successful checker remains partial evidence; the source comparison, necessity review and final regression audit remain the main agent's responsibility.
