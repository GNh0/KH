---
name: pb-to-csharp-migration-harness
description: Analyze or modify PowerBuilder/PBL/DataWindow sources, or migrate their behavior to requested C#, Designer and SQL targets.
---

# PowerBuilder and migration

Read the [selected personal PB style](../../references/personal-style.md) and exact supplied PBL/export/object, relevant ancestors, linked DataWindows and actual event/SQL/report paths. Supplied exports do not prove analysis of unread PBL contents.

For generated/edited PB, C# or SQL, complete the required [source-style cycle](../work-execution/references/source-style-cycle.md) before writing and after the final write. Inspect actual comparison-project code first, then re-read and audit the finished code.

For PB maintenance, edit the actual object/event in the available project or export workflow. Preserve relevant ancestor calls, event order, DataWindow buffers/states and database contracts. Distinguish an edited export from changes imported and verified in the actual PBL/application.

For analysis or extraction, deliver only the requested scope. PBL extraction uses the bundled `scripts/export_pbl.py` with automatic installed-runtime selection; read [extraction and validation](references/tools.md). For migration, preserve relevant source behavior while following the actual target APIs, SQL/C# skills and employee style. Distinguish display keys from raw components, row states, selected/focused records, save order and report bands.

When scope moves to generated/edited C# or reports, load the [C# entrypoint](../csharp-designer-style-harness/SKILL.md) and its needed references before implementation. For SQL, load the [SQL entrypoint](../sql-formatting/SKILL.md). Analysis-only PB work does not require generating these artifacts.

Prefer applicable target user controls and verified initialization. Missing controls require a behavior-preserving mapping to available target components, not a claim that the source cannot be migrated.

Follow [workspace files](../work-execution/references/workspace-files.md) for temporary analysis exports/probes and cleanup after use. Distinguish static mappings, executed results and unverified UI/DB behavior. Do not require a migration plan for simple SQL extraction.
