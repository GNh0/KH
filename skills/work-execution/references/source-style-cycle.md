# Required source-style cycle for code work

Apply this before writing and after finishing SQL, PB or C# project code, including Designer and reports. This is one working procedure, not an additional planning form or audit file.

## Before the first code write

Read actual code in the user's designated comparison project. If none is designated, select an available approved **other project** with the same framework and comparable responsibility. Read the relevant complete methods, events, procedures or Designer/control blocks; names, remembered patterns, a generated draft and a style description alone are insufficient. Do not use previously rejected code as the reference.

Also inspect the actual target and its callers, libraries, initialization and data contracts. The comparison project establishes writing style; the actual target establishes supported APIs and required behavior. Control defaults and current-screen dimensions remain target contracts. Keep current user instructions above conflicting examples. Do not copy another project's schema, constants, API names or business rules merely to match its style.

Keep the selected project/files, relevant source locations and applicable patterns in working context. Establish how the requested change fits that pattern and why added code is needed before implementing it. If scope changes to another artifact or responsibility, inspect the corresponding source before writing that part. Retrieve material omissions from truncated reads.

If the required comparison source is unavailable, do not silently replace it with an invented or self-generated baseline. Obtain the missing source when it determines the implementation; report the remaining scope as unverified. A later explicit user instruction may change the comparison or preservation scope.

## After the final code write

Re-read the final saved code, or the exact final snippet when no file was requested, not only the remembered draft or a tool's success result. Compare every created/changed method, procedure and Designer block with the source selected before writing and the current user rules. Review the actual control/event/binding and query/save/report paths affected by the change, while preserving compliant code outside the authorized scope.

Complete the shared [rule audit](../../rule-audit/SKILL.md) using that comparison. Repair only confirmed violations, re-read the repaired code and re-audit the affected rules. Repeat until violations are resolved in the verifiable scope; unresolved evidence is not a pass. A reference read, compiler result or internal test count cannot replace this final source comparison.

Finally check whether the combined repairs introduced problems in related callers, initialization, bindings, data contracts or previously working behavior. A further edit reopens its affected audit and regression checks. Honor existing limits on builds, DB writes and external actions; do not replay them just to obtain a passing result.
