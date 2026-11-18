# SP author and comparison-source selection

This is part of SQL-FORMATTING, not another skill or replacement style. Use it before creating or changing a SELECT/SAVE procedure. Query explanation, reading a procedure, and formatting-only preservation do not trigger author setup.

At the first actual SP task in the current project/chat, ask the user for the author name. Then ask whether to follow that author's SPs or another reference author, and obtain that name. Already explicit answers in the current project/task may be reused; do not ask the same question for every file. Do not guess from the Windows account, Git author, existing header or an unrelated chat. If the answer is missing, ask before drafting or applying SP changes. This information request is required even when code changes were already authorized; it is not another permission request.

Locate that reference author's actual SPs in the user-authorized project/database sources. Inspect their AUTHOR headers and complete same-responsibility bodies and callers: SELECT work needs relevant SELECT examples, SAVE work needs relevant SAVE examples. If none are available or authorship cannot be verified, ask for a different reference author or approved source. Do not use a generic example, generated draft or merely similarly named file as the author's code. Selecting a source or matching its AUTHOR does not prove that its style was followed.

Read the selected SPs before drafting. Compare parameter/caller flow, operation branches, XML preparation, JOIN/alias roles, writes and outputs against those bodies. The user's explicit rules and SQL-FORMATTING still govern spaces/alignment, aliases, JOIN forms, value substitutions and unnecessary code. An author's older exceptions do not override those rules. Use the author's source to choose unspecified details while preserving the actual target's behavior.

Every worked-on SP must contain this header with actual values:

```sql
-- =============================================
-- AUTHOR:      {작성자명}
-- CREATE DATE: {첫작성일}
-- DESCRIPTION: {프로그램명} 처리OR조회
-- =============================================
```

Replace the placeholders; `처리OR조회` means choose `처리` for the actual processing purpose or `조회` for retrieval. Derive the program title from the real screen/request. Use the real first creation date in the project's date notation, not each modification date. For an existing SP, verify its original attribution/date and preserve them unless the user directs a correction; recover missing original facts from actual source/history or ask rather than inventing them.

A new local `.sql` file may be an export/patch for an existing database object. `ALTER` never establishes first creation, and `CREATE OR ALTER` alone does not distinguish it. Preserve verified original facts; if the exact definition/schema is unavailable, leave that attribution explicitly unverified and retrieve the real evidence instead of rewriting it to the current worker.

For scoped project-file work, record the user's two selections once through the existing `kh_context.py apply` call with `--author <작성자명> --reference-author <참조작성자명>`. Pass the same name twice when the user chose their own style. These values stay in that project/chat/agent context and can be reused by later apply calls there; a later selection for another file does not reassign earlier files. They are not host-global identity or automatically shared to another chat. Register actual selected SP units through `--reference`, covering their author headers and complete batches, then read those current bodies. Legacy references may establish authorship with an adjacent explicit AUTHOR comment even without the new framed header. Registration records the agent's selection, not proof that the user was asked or a semantic audit passed.

For SP text delivered directly in chat or an authorized database-only task, ask the same questions and compare the approved complete definitions without inventing a local target file merely to run apply. SQL generation and database execution remain separate authorizations.

After writing, audit the exact final body against both the selected author's SPs and SQL-FORMATTING, repair confirmed deviations, and recheck affected behavior. Hooks can check missing selections, current reference author/read evidence and header structure; the question/answer provenance, style compliance, correct first date, program title and necessity remain source/user-evidence judgments.
