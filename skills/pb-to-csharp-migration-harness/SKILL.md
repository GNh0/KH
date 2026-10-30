---
name: pb-to-csharp-migration-harness
description: Analyze PowerBuilder/PBL/DataWindow sources or migrate them to C# WinForms, Designer code, and SQL Server procedures with source-grounded behavior mapping.
---

# PB to C# migration

First read the exact PBL/object, base classes, linked DataWindows, and actual event/SQL/report relationships. If only exports are supplied, stay within their evidence scope; do not claim analysis of an unread complete PBL.

For generated/edited PB, C# or SQL, complete the required [source-style cycle](../work-execution/references/source-style-cycle.md): inspect actual comparison-project style before writing, then re-read and audit the final code. Analysis/extraction alone does not require generating code.

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

Before final handover, complete the shared [rule audit](../rule-audit/SKILL.md) for this task's applicable rules.
