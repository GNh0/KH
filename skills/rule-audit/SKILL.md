---
name: rule-audit
description: Audit skill-guided work for applicable rules and omitted required steps, repair confirmed violations within scope, and check introduced regressions before completion.
---

# Rule audit

Audit skill-guided work before handover, or on an explicit compliance request. Use one shared pass scaled to the current task. Include relevant skills/references used and required domain guidance omitted as the scope changed; auditing only the loaded list would miss a skipped prerequisite. Do not load the whole catalog, recursively audit this audit, or audit ordinary conversation. Stop/cancellation overrides inspection and repair.

## Establish the applicable rules

Compare the latest user instructions/corrections, applicable skill requirements and actual project sources under the host's instruction priority. Do not promote examples or suggestions into rules. Distinguish later authorized exceptions from earlier unrequested changes. Keep relevant rules and source locations in working context, including retained user edits and process limits such as prohibited builds, DB changes or file locations. No checklist file, profile, receipt or approval form is required.

## Compare rules with evidence

For code work, audit the required [source-style cycle](../work-execution/references/source-style-cycle.md): was actual comparison-project code inspected before writing, and was the final saved code re-read against that same source after all edits? If the first step was skipped, inspect the missing source and correct the affected implementation; do not erase the earlier process violation or treat a late read as proof it happened before writing.

Inspect the latest artifacts/diff, relevant callers/initialization and execution results. A plan, announced skill use or successful read is not evidence of applying it. Compare the actual changed structure/bodies with the required source pattern; identify prerequisite source or workflow reads that were omitted or materially truncated, retrieve what is needed and recheck the affected implementation. Whole-file imports/style corrections also require inspection beyond unchanged-line suppression.

Mark relevant rules verified, violated or unverified; exclude inapplicable rules with a scope reason. A finding needs the rule source, affected location/action, observed mismatch and required correction. Missing evidence is unverified, not a guessed violation or pass.

Use the applied skill's existing checkers with actual baselines, control sources, active style policy and other required inputs. Read errors, warnings and `not_checked`; resolve warnings from requirements/source evidence. Check unsupported rules directly. Do not invent baselines, weaken rules or add exemptions to obtain a pass.

## Repair only the violations, then re-audit

During authorized implementation, correct findings without making the user repeat the request. For audit/review-only requests, report without editing.

For each confirmed violation, turn the finding into a focused repair instruction:

> Correct the identified violation using its cited rule and source. Preserve compliant work and user edits outside the affected dependency path. Recheck the rule and contracts the repair can affect.

Execute repairs in the current task. Delegation/messaging still requires host/user authorization. Fix the responsible path without unrelated regeneration, reformatting, workarounds or removal of needed behavior.

Inspect each repair's diff and rerun affected checks, including preservation of properties, bindings, result order or other touched contracts. Edits invalidate earlier evidence for affected rules. Keep verified unaffected work; repeat full tests only for a regression reason.

Repeat while violations remain and supported repairs are available. Diagnose persistent findings before retrying unchanged instructions. Finish independent corrections and report unresolved evidence/permission limits without calling them compliant. Do not replay DB writes/deployment or expand external-write authorization just to recheck.

## Final regression check

After resolving the rule violations, review the combined final diff against the pre-repair baseline and trace its effects beyond the edited lines. Check relevant callers, shared helpers, initialization, bindings, data/result contracts and other dependent behavior. Verify both the corrected path and previously working related paths, including failure/cancellation where affected. Choose checks from the actual dependency and behavior changes; a clean rule check alone does not establish regression safety.

Reuse relevant tests and direct behavior checks, broadening verification when shared code, contracts or unresolved risk justify it. Preserve user edits and distinguish unrelated pre-existing defects. Honor existing build, execution and write limits. If the repair introduces a regression, fix its cause within scope, then repeat the affected rule audit and final regression check. Any later edit reopens the checks it can affect. Complete only when both the rule findings and introduced regressions are resolved in the verified scope; report unavailable runtime/DB/UI evidence as unverified rather than claiming no regressions everywhere.

## Handover

Briefly report corrections, final regression checks and material unresolved/unverified scope. A build, exit code or self-rating alone is insufficient. An already performed process violation cannot be erased from the record; address its consequences and report accurately. This is an agent procedure, not a host-enforced completion hook.
