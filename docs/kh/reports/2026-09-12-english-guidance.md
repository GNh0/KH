# KH 3.0.9: English guidance and token comparison

All 31 Markdown files under skills, plus the linked development guide, now express their instructions in English. Requirements, exceptions, source-preservation rules, and optional workflows retain their original scope and strength. Korean request examples, the original business name, and the Korean count suffix remain where their exact text matters.

Code examples, inline code literals, reference targets, all ten skill frontmatters, invocation settings, executable sources, and scoped JSON profiles are preserved. The Korean user guide and historical reports are outside this instruction-translation scope.

## Measured document tokens

Across the same 32 complete documents: **23,379 -> 17,972 tokens**, saving **5,407 tokens (23.13%)**.

| Skill / guide | Files | Before | After | Saved | Reduction |
| --- | ---: | ---: | ---: | ---: | ---: |
| artifact-checks | 1 | 214 | 172 | 42 | 19.63% |
| code-review | 1 | 261 | 198 | 63 | 24.14% |
| context-handoff | 1 | 273 | 215 | 58 | 21.25% |
| csharp-designer-style-harness | 8 | 14,687 | 11,112 | 3,575 | 24.34% |
| kh-maintenance | 4 | 847 | 663 | 184 | 21.72% |
| pb-to-csharp-migration-harness | 6 | 2,788 | 2,179 | 609 | 21.84% |
| sql-formatting | 3 | 2,248 | 1,822 | 426 | 18.95% |
| systematic-debugging | 1 | 229 | 191 | 38 | 16.59% |
| work-execution | 5 | 1,107 | 842 | 265 | 23.94% |
| work-planning | 1 | 284 | 227 | 57 | 20.07% |
| development | 1 | 441 | 351 | 90 | 20.41% |
| **Total** | **32** | **23,379** | **17,972** | **5,407** | **23.13%** |

Every measured file decreased in token count; no increased files were excluded.

## Method and limits

- Baseline: KH 3.0.8 commit [8c26770](https://github.com/GNh0/KH/commit/8c267707cbe47bd06d36cd71ed7fb0e96181269b).
- Tokenizer: tiktoken 0.14.0, public o200k_base encoding; the same encoding is used on both sides.
- Read baseline files from Git and candidate files from the working tree as UTF-8, normalize line endings to LF, and count each complete file independently. Sum those counts. Include frontmatter, examples, tables, links, and retained Korean literals.
- Reduction = (before - after) / before * 100. Group and total rates use token totals, not averages of file percentages.
- Exclude unchanged files, release metadata, this report, and its measurements from both sides. This isolates the same instruction documents before and after translation.
- These are document-token counts, not measured Astra input tokens, billing, latency, or instruction-following accuracy. Actual tasks load only relevant skills/references; their savings depend on what is loaded and on caching.
- The earlier 26% result covered only three SQL rule excerpts. It was a sample, not a prediction for the whole document set.

[Full measurements and normalized-text SHA-256 hashes](2026-09-12-english-guidance-tokens.json). Token-counting method: [OpenAI's tiktoken guide](https://developers.openai.com/cookbook/examples/how_to_count_tokens_with_tiktoken).

## Preservation and review

- Automated baseline comparison preserved all 10 skill frontmatters, all 11 fenced examples, all reference targets, and all original inline code literals.
- Independent source-to-translation review covered all 32 documents. Seven wording issues concerning optional actions and exception scope were corrected and rechecked.
- An independent task used the English SQL skill on nested derived queries, UNION ALL, ordinary and derived JOINs, and BETWEEN. The output preserved aliases, Korean literals, and comments; the preservation checker passed. A lowercase-alias warning was retained because the request explicitly preserved aliases.
- Skill-format and plugin-manifest validators passed. No executable source, fixture, or scoped-profile change is part of the translation.
- The SQL exercise did not execute against SQL Server. No Korean-versus-English agent performance experiment, C# compilation, Designer rendering, or live PB/ORCA execution is claimed.

## Per-file counts

| Document | Before | After | Saved | Reduction |
| --- | ---: | ---: | ---: | ---: |
| [skills/artifact-checks/SKILL.md](../../../skills/artifact-checks/SKILL.md) | 214 | 172 | 42 | 19.63% |
| [skills/code-review/SKILL.md](../../../skills/code-review/SKILL.md) | 261 | 198 | 63 | 24.14% |
| [skills/context-handoff/SKILL.md](../../../skills/context-handoff/SKILL.md) | 273 | 215 | 58 | 21.25% |
| [skills/csharp-designer-style-harness/SKILL.md](../../../skills/csharp-designer-style-harness/SKILL.md) | 1,426 | 1,086 | 340 | 23.84% |
| [skills/csharp-designer-style-harness/references/checks.md](../../../skills/csharp-designer-style-harness/references/checks.md) | 3,219 | 2,371 | 848 | 26.34% |
| [skills/csharp-designer-style-harness/references/coding-style.md](../../../skills/csharp-designer-style-harness/references/coding-style.md) | 2,407 | 1,872 | 535 | 22.23% |
| [skills/csharp-designer-style-harness/references/data-flow.md](../../../skills/csharp-designer-style-harness/references/data-flow.md) | 1,558 | 1,206 | 352 | 22.59% |
| [skills/csharp-designer-style-harness/references/designer.md](../../../skills/csharp-designer-style-harness/references/designer.md) | 989 | 724 | 265 | 26.79% |
| [skills/csharp-designer-style-harness/references/grid-layout.md](../../../skills/csharp-designer-style-harness/references/grid-layout.md) | 1,410 | 1,125 | 285 | 20.21% |
| [skills/csharp-designer-style-harness/references/screen-behavior.md](../../../skills/csharp-designer-style-harness/references/screen-behavior.md) | 1,891 | 1,397 | 494 | 26.12% |
| [skills/csharp-designer-style-harness/references/user-controls.md](../../../skills/csharp-designer-style-harness/references/user-controls.md) | 1,787 | 1,331 | 456 | 25.52% |
| [skills/kh-maintenance/SKILL.md](../../../skills/kh-maintenance/SKILL.md) | 305 | 259 | 46 | 15.08% |
| [skills/kh-maintenance/references/pb-profile-maintenance.md](../../../skills/kh-maintenance/references/pb-profile-maintenance.md) | 164 | 119 | 45 | 27.44% |
| [skills/kh-maintenance/references/scenario-evaluation.md](../../../skills/kh-maintenance/references/scenario-evaluation.md) | 148 | 112 | 36 | 24.32% |
| [skills/kh-maintenance/references/session-audit.md](../../../skills/kh-maintenance/references/session-audit.md) | 230 | 173 | 57 | 24.78% |
| [skills/pb-to-csharp-migration-harness/SKILL.md](../../../skills/pb-to-csharp-migration-harness/SKILL.md) | 551 | 434 | 117 | 21.23% |
| [skills/pb-to-csharp-migration-harness/references/datawindow.md](../../../skills/pb-to-csharp-migration-harness/references/datawindow.md) | 731 | 577 | 154 | 21.07% |
| [skills/pb-to-csharp-migration-harness/references/default-profile.md](../../../skills/pb-to-csharp-migration-harness/references/default-profile.md) | 190 | 146 | 44 | 23.16% |
| [skills/pb-to-csharp-migration-harness/references/orca.md](../../../skills/pb-to-csharp-migration-harness/references/orca.md) | 440 | 334 | 106 | 24.09% |
| [skills/pb-to-csharp-migration-harness/references/sql.md](../../../skills/pb-to-csharp-migration-harness/references/sql.md) | 414 | 319 | 95 | 22.95% |
| [skills/pb-to-csharp-migration-harness/references/validation.md](../../../skills/pb-to-csharp-migration-harness/references/validation.md) | 462 | 369 | 93 | 20.13% |
| [skills/sql-formatting/SKILL.md](../../../skills/sql-formatting/SKILL.md) | 409 | 344 | 65 | 15.89% |
| [skills/sql-formatting/references/checks.md](../../../skills/sql-formatting/references/checks.md) | 444 | 331 | 113 | 25.45% |
| [skills/sql-formatting/references/style.md](../../../skills/sql-formatting/references/style.md) | 1,395 | 1,147 | 248 | 17.78% |
| [skills/systematic-debugging/SKILL.md](../../../skills/systematic-debugging/SKILL.md) | 229 | 191 | 38 | 16.59% |
| [skills/work-execution/SKILL.md](../../../skills/work-execution/SKILL.md) | 462 | 366 | 96 | 20.78% |
| [skills/work-execution/references/delegation.md](../../../skills/work-execution/references/delegation.md) | 142 | 105 | 37 | 26.06% |
| [skills/work-execution/references/preferences.md](../../../skills/work-execution/references/preferences.md) | 229 | 167 | 62 | 27.07% |
| [skills/work-execution/references/secret-handling.md](../../../skills/work-execution/references/secret-handling.md) | 143 | 103 | 40 | 27.97% |
| [skills/work-execution/references/windows-commands.md](../../../skills/work-execution/references/windows-commands.md) | 131 | 101 | 30 | 22.90% |
| [skills/work-planning/SKILL.md](../../../skills/work-planning/SKILL.md) | 284 | 227 | 57 | 20.07% |
| [docs/development.md](../../../docs/development.md) | 441 | 351 | 90 | 20.41% |
