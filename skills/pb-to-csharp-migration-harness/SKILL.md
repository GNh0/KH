---
name: pb-to-csharp-migration-harness
description: Analyze PowerBuilder/PBL/DataWindow sources or migrate them to C# WinForms, Designer code, and SQL Server procedures with source-grounded behavior mapping.
---

# PB to C# migration

First read the exact PBL/object, base classes, linked DataWindows, and actual event/SQL/report relationships. If only exports are supplied, stay within their evidence scope; do not claim analysis of an unread complete PBL.

- For extraction or library errors, read [ORCA execution](references/orca.md).
- For UI/DataWindow mapping, read [DataWindows and screens](references/datawindow.md). Apply the [user's HTML rules](../csharp-designer-style-harness/references/grid-layout.md) to grid defaults and editing properties.
- Use [migration validation](references/validation.md) for migration plans and generated results.
- For SQL work, use [SELECT/SAVE connections](references/sql.md) and the SQL skill's style.
- Apply the [scoped profile](references/default-profile.json) for existing user style. Read KH maintenance guidance only when extraction of a new profile is requested.
- When generating/editing C#, also read the [user's coding style](../csharp-designer-style-harness/references/coding-style.md). Missing or unfinished implementations in reference screens do not weaken agreed C# rules.

Distinguish raw key components from display keys; do not fix particular ORD/PUR/REC names or component counts. Trace input/query/protection/save/output flow through actual source. Do not require complete migration documents or C# generation for simple SELECT extraction.

If the migration target has no user controls, preserve behavior using available DevExpress or standard controls. Distinguish verified static scope, execution results, and unverified screen/DB behavior in the handover.

Prefer appropriate available user controls and their initialization defaults. Apply [user-control selection and initialization](../csharp-designer-style-harness/references/user-controls.md) without restricting them to KoneLib. Do not overwrite user-control defaults by adding PB properties or familiar DevExpress options without justification.
