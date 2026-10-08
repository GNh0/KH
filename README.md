# KH for Codex

KH 3.0.21 provides ten focused skills and optional local checks for SQL, C#/Designer and PowerBuilder work. [한국어 및 상세 사용법](README.ko.md)

Use current user instructions, exact source and real project APIs. Small clear requests run directly. Load only the skills useful for the task. LINQ, intermediate tables and builds are disfavored; use them only when avoidance makes implementation difficult or the alternative has an extreme performance disadvantage. A current explicit prohibition still applies.

The skill entrypoints are `work-planning`, `work-execution`, `code-review`, `systematic-debugging`, `sql-formatting`, `csharp-designer-style-harness`, `pb-to-csharp-migration-harness`, `artifact-checks`, `context-handoff` and `kh-maintenance`.

New DevExpress grids use the user-supplied [DataWindowToXml layout defaults](skills/csharp-designer-style-harness/references/grid-layout.md). Column edit modes distinguish ordinary read-only, action-enabled and editable columns. Checks review added cell TextOptions, SpinEdit masks, DisplayFormat and view behavior changes while preserving existing settings when a baseline is supplied.

C# work uses the [user coding style](skills/csharp-designer-style-harness/references/coding-style.md) and [user-control initialization](skills/csharp-designer-style-harness/references/user-controls.md). Prefer suitable controls available in the target project, retain their defaults, and use the agreed semantic names. Match label and single-line input heights to similar controls in the actual screen; preserve constructor label font/alignment, including a self-property Default fallback to Far/Center. Width may grow for content. Optional checks use actual control sources and a same-project Designer to flag proved font/alignment/height mismatches; no universal font/height table is required.

For company distribution with employee-owned styles and no personal GitHub dependency, use the separate [company ZIP bundle](company/README.ko.md). Its checks use project policy rather than enforcing KH's personal syntax and format preferences.

The PB skill includes PblScripter's export script and x86 helper. Its [launcher](skills/pb-to-csharp-migration-harness/references/orca.md) automatically tries installed PB 7.0/10.5/12.5 runtimes and selects one after actual extraction. No external PblScripter installation is needed. Python 3.11+, Windows PowerShell and a compatible licensed PB/ORCA installation are required. Temporary input, failed output and necessary helper builds stay outside source and plugin folders.

For tasks that create auxiliary files, [workspace files](skills/work-execution/references/workspace-files.md) covers cleanup before handover, preserving requested deliverables and recording evidence still needed for continuation. Successful analysis exports remain the caller's cleanup responsibility; temporary storage alone does not imply automatic deletion.

Before implementing screen commands, read the actual same-project event flow and current permitted operations. Optional C# checks accept `--style-reference-csharp` and repeated `--screen-command` arguments, including `print`, to review command phases, excluded subscriptions and save transport differences: XML, loop save calls and output directions. These comparisons do not globally ban row-state acceptance, mode resets, navigation, scalar saves or outputs. Slide-based layouts require the full rendered slide before deriving columns.

Optional Python 3.11+ standard-library checks run from any directory:

```powershell
python -B <plugin-root>/scripts/kh_check.py sql <absolute-original.sql> <absolute-candidate.sql>
python -B <plugin-root>/scripts/kh_check.py csharp <absolute-source.cs> --designer <absolute-screen.Designer.cs>
python -B <plugin-root>/scripts/kh_check.py designer <absolute-after.Designer.cs> --original <absolute-before.Designer.cs> --preserve-property btn.Visible
python -B <plugin-root>/scripts/kh_check.py pb <absolute-export.srw>
python -B <plugin-root>/scripts/kh_check.py artifact <absolute-document.docx>
python -B <plugin-root>/scripts/kh_check.py package <absolute-plugin-root>
```

Results distinguish errors, warnings and incomplete input, and list both `checked` and `not_checked`. No DB, build, API key, server or package installation is needed. Static source/container checks do not establish runtime behavior or visual quality. `sql --normalize-layout` only normalizes supported FROM/JOIN/EXISTS layout to stdout.

Run `python -B -m unittest discover -s tests/domain` from this repository for local tests. The [development checks](docs/development.md) also run pinned Pyright across all active Python modules, with strict checking on input validation and the shared lexers. Node/Pyright are development tools only. See [documentation and migration notes](docs/README.md).

The mandatory intake/front door, Python host loop, simulated role DAG, duplicate Goal/memory/state stores and signed receipt protocols were removed. Use the current Codex host tools within their actual schemas and the user's request. The old root CLI/server/workflow APIs are breaking removals; a few pure helper imports remain under `src/skills`.

The canonical manifest is `.codex-plugin/plugin.json`. The remote marketplace name and `codex-runtime` ref are retained. A modified source tree does not update an installed cache by itself; installation/deployment is a separate requested operation. Historical documents are reference material, not current operating instructions.
