---
name: kh-maintenance
description: Maintain or audit this KH plugin, its SQL/C#/PB checkers, scoped profiles, packaging, and explicitly requested conversation-history scenarios.
---

# KH maintenance

Use this skill for requests about KH's own skills, checkers, package, or conversation audits. Do not run it as a prerequisite for ordinary work.

Apply the current skill-creator guidance to skill changes. Do not turn a single past error or example name into a global prohibition. Distinguish actual source/APIs, user requirements, validated profiles, and checker results.

- Package validation: `python <plugin-root>/scripts/kh_check.py package <absolute-plugin-root>`.
- Type/regression validation for checker changes: [development checks](../../docs/development.md).
- Profile maintenance: [PB/C# profiles](references/pb-profile-maintenance.md).
- Explicit conversation audits: [source-log audits](references/session-audit.md).
- Realistic behavior evaluation: [scenario evaluation](references/scenario-evaluation.md).

Check the skills and paths actually discovered. Do not report test counts, self-ratings, role JSON, or simulations as actual Codex execution. Distinguish source, branch, manifest, and installed cache; keep installation and publication within the actual request.
