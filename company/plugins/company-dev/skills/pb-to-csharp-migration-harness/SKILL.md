---
name: pb-to-csharp-migration-harness
description: Analyze or modify PowerBuilder/PBL/DataWindow sources, or migrate their behavior to requested C#, Designer and SQL targets.
---

# PowerBuilder and migration

Read the [selected personal PB style](../../references/personal-style.md) and exact supplied PBL/export/object, relevant ancestors, linked DataWindows and actual event/SQL/report paths. Supplied exports do not prove analysis of unread PBL contents.

For PB maintenance, edit the actual object/event in the available project or export workflow. Preserve relevant ancestor calls, event order, DataWindow buffers/states and database contracts. Distinguish an edited export from changes imported and verified in the actual PBL/application.

For analysis or extraction, deliver only the requested scope. PBL extraction uses the bundled `scripts/export_pbl.py` with automatic installed-runtime selection; read [extraction and validation](references/tools.md). For migration, preserve relevant source behavior while following the actual target APIs, SQL/C# skills and employee style. Distinguish display keys from raw components, row states, selected/focused records, save order and report bands.

Prefer applicable target user controls and verified initialization. Missing controls require a behavior-preserving mapping to available target components, not a claim that the source cannot be migrated.

Put analysis exports and probes in an explicit task-specific temporary directory outside source trees. Distinguish static mappings, executed results and unverified UI/DB behavior. Do not require a migration plan for simple SQL extraction.
