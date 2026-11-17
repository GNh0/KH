# Required source-style cycle for code work

This is the shared audit procedure for SQL, PB and C# project code, including Designer and reports. Domain skills and explicit compliance reviews reuse this cycle and current evidence; they do not start another copy of the audit. Review the proposed change, audit each saved implementation unit, then check the combined result. A unit is a coherent method, query branch or related UI change, not every line/tool call. No separate draft file, checklist or audit log is required.

When long work needs continuation across compaction/restart, preserve exact critical constraints, latest corrections and unfinished verification through [context handoff](../../context-handoff/SKILL.md). After restoration, retrieve omitted original evidence and recheck current sources; an older checkpoint cannot revive cancelled work or replace newer instructions.

## Before the first code write

Follow the current domain entrypoint's application route and retrieve the missing references for the actual changed responsibilities. Reading a skill for inspection is not development application. Hook read checks establish availability only; source comparison and semantic judgment below still belong to the agent.

Select an actual existing reference **program, screen or procedure for each changed responsibility** in the user's designated comparison project. If none is designated, use an available approved other project with the same framework. A query/layout example does not establish a printing or save path it does not implement. Read the relevant complete bodies and follow their called preparation/initialization through the point where the result is consumed. A project name, search hit, file opening or fixed first-lines excerpt does not establish this coverage. Do not substitute unapproved generated drafts or user-rejected code for a working reference.

Also inspect the actual target's callers, libraries, initialization and data contracts. Reference code establishes writing style; the target establishes APIs, behavior, control defaults and screen dimensions. Permissions, command availability, validation and query defaults are functional decisions, not style to copy or infer from a screen's apparent purpose. Establish their actual need before changing them. Keep current user instructions above conflicting examples.

Before editing, briefly identify the reference program/files and actual methods/flow in a source-based progress update. Reuse an already stated basis; no repeated checklist or new document is required. Keep source locations and necessary differences in working context. For a changed responsibility, inspect its newly relevant reference first. Read long material in relevant complete bodies, verify their endings and retrieve truncated portions before treating them as inspected.

If the required comparison source is unavailable, do not silently replace it with an invented or self-generated baseline. Obtain the missing source when it determines the implementation; report the remaining scope as unverified. A later explicit user instruction may change the comparison or preservation scope.

## Before applying each implementation unit

Review the proposed code in the actual execution path against the request, existing behavior and the source's allocation of responsibilities. Establish the concrete gap it closes, whether that gap is already covered, and why this location owns the change. Review all behavior introduced or changed by the proposal, including incidental setup copied from an example. Keep only supported changes; revise unsupported choices before writing them. An available API, familiar template or plausible feature purpose is not evidence of need. This review also applies to imported or agent-generated drafts before they replace production code.

Immediately after writing the unit, re-read the actual saved body and its affected callers/initialization. Check both the requested result and incidental behavior changes, including what it now excludes or overrides. Repair and re-audit that unit before proceeding to another responsibility. Do not defer this to a final build or wait for the user to point it out. A later edit reopens the affected unit.

Use host-observed source edit tools when they fit the work. If a required specialized runtime writes source outside hook coverage, perform the same explicit checks with the actual pre-change original and saved candidate, then complete the source audit yourself. A successful MCP write or checker exit code does not establish hook coverage, resolved warnings or compliance.

## After the final code write

Re-read the final saved code, or exact final snippet when no file was requested. Compare every created/changed body and Designer block with the selected source and current rules. Include the combined effects of the implementation units already reviewed. Audit the actual production entrypoint and affected control/event/binding and query/save/report path, including prerequisites performed in other methods. Extra setup in a test/export harness does not prove the production path performs it. Preserve compliant work outside scope.

Compare the latest user requirements, applicable domain rules and saved implementation. Classify relevant rules as verified, violated or unverified; explain material exclusions. Missing evidence is neither a guessed violation nor a pass. Use supported checkers with actual originals, selected control/reference sources and scoped profiles; resolve warnings and not_checked against the real requirement. Do not invent a baseline or weaken a rule to obtain a pass.

Repair only confirmed violations, preserve compliant work, re-read the repair and re-audit affected rules. Repeat until violations are resolved in the verifiable scope. Reuse unaffected observations/tests; a later edit reopens affected evidence. An earlier process omission cannot be erased by a later read or test pass. A reference read, compiler result or internal test count cannot replace the final source comparison.

Finally check whether combined repairs introduced problems in related callers, initialization, bindings, data contracts or previously working behavior. Broaden/repeat tests only for an affected behavior or unresolved risk. Honor stop requests, review-only scope and existing limits on builds, DB writes and external actions; do not replay them merely to obtain a passing result.

At handover, briefly identify the programs/flows actually compared and any material unverified scope. Do not report a complete source comparison from a read log or test pass alone.
