---
name: pb-to-csharp-migration-harness
description: Analyze PowerBuilder/PBL/DataWindow artifacts or migrate them to WinForms and SQL Server with source-grounded mapping.
---

# PB to C# migration

Execute in the current agent by default. Use the [KH delegation flow](../work-execution/references/delegation.md) only when a bounded specialist task or independent review benefits from a separate agent. An assigned PB worker completes its scope and returns evidence without further delegation.

First read the exact PBL/object, base classes, linked DataWindows, and actual event/SQL/report relationships. If only exports are supplied, stay within their evidence scope; do not claim analysis of an unread complete PBL.

For project-file changes, use the [scoped application](../work-execution/references/application.md): `pb-edit` for native PB edits, or `pb-migrate` together with each named C#/SQL output's actual responsibility. Read its required references and follow the shared [source-style cycle](../work-execution/references/source-style-cycle.md). Analysis/extraction alone needs no development application or code generation.

Put temporary exports, probes, and conversion output outside the source project. Supply an explicit output path for ORCA conversion and follow [workspace files](../work-execution/references/workspace-files.md) for auxiliary files.

- For PBL extraction, use the bundled `scripts/export_pbl.py` (automatic runtime selection) and read [ORCA execution](references/orca.md). An external PblScripter installation is unnecessary; a compatible installed PB/ORCA runtime is still required.
- For UI/DataWindow mapping, read [DataWindows and screens](references/datawindow.md). The [HTML grid rules](../csharp-designer-style-harness/references/grid-layout.md) apply to generated C# grids, not native PB DataWindows or analysis-only work.
- Use [migration validation](references/validation.md) for migration plans and generated results.
- For generated/edited SQL, load the [SQL entrypoint](../sql-formatting/SKILL.md) and [SELECT/SAVE connections](references/sql.md).
- The [scoped profile](references/default-profile.json) describes the C#/WinForms migration target. Use it for that target only; native PB changes follow the actual PB project's event/DataWindow patterns. Read KH maintenance guidance only for requested profile maintenance.
- When generating/editing C# or reports, load the [C# entrypoint](../csharp-designer-style-harness/SKILL.md) and its references for the current artifact. A coding-style excerpt alone does not cover Designer, report or actual-project integration. Missing/unfinished reference implementations do not weaken agreed rules.

Distinguish raw key components from display keys; do not fix particular ORD/PUR/REC names or component counts. Trace input/query/protection/save/output flow through actual source. Do not require complete migration documents or C# generation for simple SELECT extraction.

For C# migration targets, prefer appropriate available user controls and their initialization defaults. Apply [user-control selection and initialization](../csharp-designer-style-harness/references/user-controls.md) without restricting them to KoneLib. If none are available, preserve behavior using available DevExpress or standard controls. Do not overwrite user-control defaults by adding PB properties or familiar DevExpress options without justification.

Distinguish verified static scope, execution results, and unverified screen/DB behavior in the handover.
