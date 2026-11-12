# Required source-style cycle for code work

Apply this while writing SQL, PB or C# project code, including Designer and reports: review the proposed change before applying it, audit each completed implementation unit, then check the combined result. An implementation unit is a coherent method, query branch or related UI change, not every line or tool call. Use the current working context; no separate draft file, checklist or audit log is required.

When long work needs continuation across compaction/restart, preserve exact critical constraints, latest corrections and unfinished verification through [context handoff](../../context-handoff/SKILL.md). After restoration, retrieve omitted original evidence and recheck current sources; an older checkpoint cannot revive cancelled work or replace newer instructions.

## Before the first code write

Select an actual existing reference **program, screen or procedure for each changed responsibility** in the user's designated comparison project. If none is designated, use an available approved other project with the same framework. A query/layout example does not establish a printing or save path it does not implement. Read the relevant complete bodies and follow their called preparation/initialization through the point where the result is consumed. A project name, search hit, file opening or fixed first-lines excerpt does not establish this coverage. Do not substitute unapproved generated drafts or user-rejected code for a working reference.

Also inspect the actual target's callers, libraries, initialization and data contracts. Reference code establishes writing style; the target establishes APIs, behavior, control defaults and screen dimensions. Permissions, command availability, validation and query defaults are functional decisions, not style to copy or infer from a screen's apparent purpose. Establish their actual need before changing them. Keep current user instructions above conflicting examples.

Before editing, briefly identify the reference program/files and actual methods/flow in a source-based progress update. Reuse an already stated basis; no repeated checklist or new document is required. Keep source locations and necessary differences in working context. For a changed responsibility, inspect its newly relevant reference first. Read long material in relevant complete bodies, verify their endings and retrieve truncated portions before treating them as inspected.

If the required comparison source is unavailable, do not silently replace it with an invented or self-generated baseline. Obtain the missing source when it determines the implementation; report the remaining scope as unverified. A later explicit user instruction may change the comparison or preservation scope.

## Before applying each implementation unit

Review the proposed code in the actual execution path against the request, existing behavior and the source's allocation of responsibilities. Establish the concrete gap it closes, whether that gap is already covered, and why this location owns the change. Review all behavior introduced or changed by the proposal, including incidental setup copied from an example. Keep only supported changes; revise unsupported choices before writing them. An available API, familiar template or plausible feature purpose is not evidence of need. This review also applies to imported or agent-generated drafts before they replace production code.

Immediately after writing the unit, re-read the actual saved body and its affected callers/initialization. Check both the requested result and incidental behavior changes, including what it now excludes or overrides. Repair and re-audit that unit before proceeding to another responsibility. Do not defer this to a final build or wait for the user to point it out. A later edit reopens the affected unit.

## After the final code write

Re-read the final saved code, or exact final snippet when no file was requested. Compare every created/changed body and Designer block with the selected source and current rules. Include the combined effects of the implementation units already reviewed. Audit the actual production entrypoint and affected control/event/binding and query/save/report path, including prerequisites performed in other methods. Extra setup in a test/export harness does not prove the production path performs it. Preserve compliant work outside scope.

Complete the shared [rule audit](../../rule-audit/SKILL.md) using that comparison. Repair only confirmed violations, re-read the repaired code and re-audit the affected rules. Repeat until violations are resolved in the verifiable scope; unresolved evidence is not a pass. A reference read, compiler result or internal test count cannot replace this final source comparison.

Finally check whether the combined repairs introduced problems in related callers, initialization, bindings, data contracts or previously working behavior. A further edit reopens its affected audit and regression checks. Honor existing limits on builds, DB writes and external actions; do not replay them just to obtain a passing result.

At handover, briefly identify the programs/flows actually compared and any material unverified scope. Do not report a complete source comparison from a read log or test pass alone.
