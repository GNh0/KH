# Applying KH to actual development

Apply KH once to the owned outputs before editing. Skill discovery, documentation review, explanations and pure PB extraction do not register files.

```text
python -B <plugin-root>/scripts/kh_context.py --cwd <cwd> --session <session> --transcript <transcript> --host <host> --data-root <exact-context-v1-root> --epoch <epoch> apply --work <kind> --target <owned-file> --reference <actual-comparison-source[#Lstart-Lend]>
```

1. Use the scope emitted by this host, including `--agent-id` when supplied. The data root already ends in context-v1. Use the current epoch. If hooks are unavailable, perform the explicit audit and report that limitation.
2. Select work kinds and target files for the requested changes. Repeat flags as needed. Register new files or responsibilities before writing. A project file can own several responsibilities.
3. Attach approved reference units to the work kinds selected in this call. Read the complete relevant bodies from their actual paths after selection. Use Read/read_file or an explicit Get-Content/cat command. Segments can accumulate. Re-read changed files and stale or newly selected ranges.
4. Read the returned missing Markdown sections at their file/line ranges. A `#fragment` is a heading. A full read covers its sections. Registration captures the original but does not count as a read.
5. Apply the [source-style cycle](source-style-cycle.md). Compare the final saved code, actual callers and reference implementations. The main agent owns missing coverage and regressions.

| Work | Responsibility |
| --- | --- |
| `csharp-code` | Methods and expressions |
| `csharp-control` / `csharp-designer` | Controls or RepositoryItems, initialization and layout, including code-behind |
| `csharp-grid` / `csharp-data` | Grids/editors or query/save, XML, focus and bindings |
| `csharp-report` / `csharp-monitoring` | Report/printing or repeated queries and rebinding |
| `sql-format` / `sql-query` | Preserve existing tokens and allowed aliases, or develop a standalone query |
| `sql-select` / `sql-save` | SELECT/report or SAVE/XML procedures. Select both when both change. |
| `pb-edit` / `pb-migrate` | Native PB or migration plus target C#/SQL responsibilities |

- **SPs.** Follow [SP authorship](../../sql-formatting/references/procedure-authorship.md). Pass the header name with `--author` and each search name with `--reference-author`. Read an actual authored SP for the same responsibility. Supply the full SQL source selection for that responsibility when replacing it. Omitting reference flags retains the selection.
- **C# screens.** Select the comparison Designer and actual complete control classes separately. Read their initialization and the consuming screen. Only observed selected ranges supply library defaults. Registered Designer files always include Designer work. Recognized control/grid/report changes extend the required references. Retracting a proposed change drops only its inferred scope.
- **PB migrations.** Attach actual PB source to `pb-migrate` and separate C#/SQL style references to their output roles. Formatting a chat snippet uses SQL style directly.
- **Ownership.** Compare against sources independent of the owned candidate. Register only files assigned to this task. Account for unregistered writes even when a notice is the only feedback. Additional registrations preserve existing originals and reads.
- **Lifecycle.** Use `recall` for current state. A pause remains in force. Stop/new-task retires the application, while interrupted repair keeps its original. `checks_complete` and `checks_complete_audit_unverified` record observed checks. Resolve warnings and outstanding semantic checks against the source.
