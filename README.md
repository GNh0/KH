# KH Skills

**SQL, C#/Designer and PowerBuilder skills for Claude and Codex.**

KH 3.0.26 packages ten focused development skills and optional local Python checks in one repository. Both platforms load the same `skills/` and use the same `src/` and `scripts/`; their manifests and marketplace catalogs provide the installation adapters.

[한국어](README.ko.md) · [Skills](#skills) · [Local checks](#optional-local-checks) · [Development](docs/development.md)

## Install

### Claude Code

Run these commands inside a Claude Code session:

```text
/plugin marketplace add GNh0/KH
/plugin install kh-skills@gnho-labs
```

Then invoke a skill by its namespaced command:

```text
/kh-skills:sql-formatting
/kh-skills:csharp-designer-style-harness
/kh-skills:pb-to-csharp-migration-harness
```

For local development, clone this repository and launch `claude --plugin-dir /absolute/path/to/KH`. The Claude manifest is `.claude-plugin/plugin.json`; the marketplace catalog is `.claude-plugin/marketplace.json`.

Claude Code in the terminal and its local Desktop Code sessions share user-level plugin settings. Other Claude surfaces load different plugin components; this repository's optional Python/PB helpers need an environment that can execute their local files. See [Anthropic's plugin documentation](https://code.claude.com/docs/en/plugins) for the current surface and plan requirements.

### Codex

Register the existing repository marketplace:

```sh
codex plugin marketplace add GNh0/KH
```

Open the app's plugin directory, select **KH Skills**, and install it. The existing technical identifiers remain `kh-uaf` and `kh-uaf-marketplace`; both platforms install from the shared `release` branch. Refresh the marketplace before upgrading a previously installed version.

Invoke a skill by name, for example `$sql-formatting`, or ask for the relevant work. Codex discovers skill descriptions and loads the useful guidance. See [OpenAI's plugin packaging documentation](https://developers.openai.com/plugins/build/plugins) for marketplace registration and installation.

### Individual skills

If you do not want the complete plugin, copy only the required folders from `skills/` into your agent's supported skill directory. Keep their referenced resources available: several references and checkers use paths relative to this repository root. The complete plugin is the recommended option for the domain skills.

KH does not provide a model, an agent runtime, or API credits. Your Claude or Codex account and that host's permissions still apply.

## Skills

| Skill | Use it for |
| --- | --- |
| [sql-formatting](skills/sql-formatting/SKILL.md) | SQL/T-SQL layout, alias-preserving edits and source comparison |
| [csharp-designer-style-harness](skills/csharp-designer-style-harness/SKILL.md) | WinForms, DevExpress, project controls and Designer contracts |
| [pb-to-csharp-migration-harness](skills/pb-to-csharp-migration-harness/SKILL.md) | PBL/DataWindow analysis and source-grounded C#/SQL migration |
| [work-planning](skills/work-planning/SKILL.md) | Substantial work with unresolved choices or dependencies |
| [work-execution](skills/work-execution/SKILL.md) | Approved multi-step work, progress and stop/resume handling |
| [code-review](skills/code-review/SKILL.md) | Actual changes, behavior regressions and verification |
| [systematic-debugging](skills/systematic-debugging/SKILL.md) | Reproducing a failure and tracing its actual cause |
| [artifact-checks](skills/artifact-checks/SKILL.md) | Deliverable content, file structure and rendered output |
| [context-handoff](skills/context-handoff/SKILL.md) | A compact checkpoint for continuing an ongoing task |
| [kh-maintenance](skills/kh-maintenance/SKILL.md) | KH's package, checkers, profiles and requested source-log audits |

## How KH works

Start from the current request, original source, actual project APIs and the user's corrections. Small clear changes run directly; planning and review are used when they improve the task. The shared skills use the tools available in the current host.

C# guidance preserves the actual screen's event flow, control defaults, names and save/query contracts. New DevExpress grids use the supplied [DataWindowToXml defaults](skills/csharp-designer-style-harness/references/grid-layout.md), together with the [coding style](skills/csharp-designer-style-harness/references/coding-style.md) and [control initialization](skills/csharp-designer-style-harness/references/user-controls.md). Existing screens are compared against their own baseline.

SQL checks compare supported source tokens and layout; the agent determines business meaning from the query and user instructions. PB work maps the source's events, state, DataWindows and stored-procedure parameters before migration.

LINQ, intermediate tables and builds are disfavored by the included project style. Use them when avoiding them makes implementation difficult or causes an extreme performance disadvantage, with a concrete reason. Current user instructions take precedence.

## Optional local checks

The checkers use the Python 3.11+ standard library. They need no API key, server, database connection or extra Python package. Replace the placeholders with actual absolute paths:

```sh
python -B <KH-root>/scripts/kh_check.py sql <original.sql> <candidate.sql>
python -B <KH-root>/scripts/kh_check.py sql <source.sql> --preserve-aliases
python -B <KH-root>/scripts/kh_check.py csharp <candidate.cs> --original <original.cs> --designer <screen.Designer.cs>
python -B <KH-root>/scripts/kh_check.py designer <after.Designer.cs> --original <before.Designer.cs> --preserve-property btn.Visible
python -B <KH-root>/scripts/kh_check.py pb <source.srw> --encoding cp949
python -B <KH-root>/scripts/kh_check.py artifact <document.docx>
python -B <KH-root>/scripts/kh_check.py package <KH-root>
```

For ordinary checks, exit codes are **0** for the checks performed passing, **1** for errors found, and **2** for incomplete input or scope. Read both `checked` and `not_checked`. Static checks do not establish SQL execution, C# compilation, Designer behavior, complete migration or rendered quality. `sql --normalize-layout` writes supported layout changes to stdout.

The PB skill includes PblScripter's export script and x86 helper. The [bundled launcher](skills/pb-to-csharp-migration-harness/references/orca.md) tries installed PB 7.0/10.5/12.5 runtimes and selects one after actual extraction. It requires Windows PowerShell and a compatible licensed PB/ORCA installation.

For company distribution with employee-owned styles, use the separate [company ZIP bundle](company/README.ko.md). Its project policy differs from KH's personal style defaults; it currently uses the Codex marketplace format.

## Package and validation

```text
.codex-plugin/plugin.json        Codex metadata; existing kh-uaf identity
.agents/plugins/marketplace.json Codex marketplace; release source
.claude-plugin/plugin.json       Claude metadata; kh-skills identity
.claude-plugin/marketplace.json  Claude marketplace; gnho-labs, release source
skills/                         Shared guidance and resources
src/ + scripts/                 Shared optional checkers
```

The two platform manifests have the same release version and point to the same skill tree. To validate a checkout:

```sh
python -B -m unittest discover -s tests/domain
python -B scripts/kh_check.py package /absolute/path/to/KH
claude plugin validate /absolute/path/to/KH/.claude-plugin/plugin.json --strict
claude plugin validate /absolute/path/to/KH/.claude-plugin/marketplace.json --strict
```

[Development checks](docs/development.md) include pinned Pyright and CI. Passing tests and manifest validation establish the package checks performed; model behavior and target environments need their own evaluation. GitHub publication does not update an installed cache automatically.

The old mandatory intake, Python host loop, simulated role DAG and duplicate Goal/memory/state stores were removed. Goal, collaboration, permissions and interruption follow the current host. [Historical documents](docs/README.md) describe earlier versions and are not current operating instructions.
