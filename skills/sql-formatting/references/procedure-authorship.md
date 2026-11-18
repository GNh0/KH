# SP author and comparison-source selection

This is part of SQL-FORMATTING, not another skill or replacement style. Use it before creating or changing a SELECT/SAVE procedure. Query explanation, reading a procedure, and formatting-only preservation do not trigger author setup.

Ask only for missing information. For example: “이번 SP의 AUTHOR에 넣을 이름은 무엇인가요? 작성 스타일은 누구의 기존 SP를 찾아 참고할까요?” If the user chooses their own SPs, reuse the header name as the search name. If they give several search names, search each one. Keep the search names in the task context; the target header contains only its actual author. Reuse explicit answers in the current task, without guessing identities from existing headers or account names.

Search the authorized project/database definitions or the user-designated reference collection by AUTHOR. Select by responsibility from the matches and read the complete bodies: SELECT for 조회, SAVE for 처리. Identify the SP names, their actual header authors and the relevant style decision before drafting. Report a requested name with no matches. If no suitable source is available, ask for another source. A generic example, generated draft or similarly named file cannot establish the author's style.

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

For scoped project-file work, the agent records the header name with `--author` and repeats `--reference-author` once per search name in `kh_context.py apply`. Register each selected definition with `--reference`, including its header and complete batch, then retrieve its current body. Reuse the selection in the same project/chat/agent. If the user corrects a search name, reapply the corrected names with the confirmed header author to the affected targets. A legacy adjacent AUTHOR comment may establish source authorship. Registration alone cannot establish a read or style compliance.

For SP text delivered directly in chat or an authorized database-only task, ask the same questions and compare the approved complete definitions without inventing a local target file merely to run apply. SQL generation and database execution remain separate authorizations.

After writing, audit the exact final body against both the selected author's SPs and SQL-FORMATTING, repair confirmed deviations, and recheck affected behavior. Hooks can check missing selections, current reference author/read evidence and header structure; the question/answer provenance, style compliance, correct first date, program title and necessity remain source/user-evidence judgments.
