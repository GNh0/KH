# Installed Runtime Audit: 01a0321e

## Scope and Verdict

Audited the streamed JSONL session `01a0321e` (781 lines; plugin cache
`kh-uaf` `2.9.143`; session cwd was the TY source checkout) against the
current KH working tree. No front-door, Goal, or Git command was run for this
audit, and no application code was edited.

The supplied `session_skill_audit` summary is directionally correct on the central failure: the session produced a compilable CRUD screen, but generated C#/Designer and SQL/SP style were not governed by their packaged contracts. The primary defect is a routing/coverage gap, not a broken SQL verifier. The session never executed a C# style verifier or `sql-formatting`/`sql-formatting-style-harness` against the generated artifacts.

Release `2.9.144` now packages a PB-independent C#/Designer verifier and matching
tests, but that remediation does not retroactively add a style receipt to this
`2.9.143` session. This report therefore remains negative evidence for the
audited run while current-source remediation is stated separately below.

## A. Confirmed User-Visible Failures

### P1: C# style contract was bypassed

The generated code in the `apply_patch` payload (`JSONL:L373`, final source readback `JSONL:L639`, Designer readback `JSONL:L645`) uses:

```csharp
public partial class SystemAPPKey : FrmDevBase
private void CallViewQuery()
private bool CallSaveQuery()
this.gvwList.Columns.AddRange(... colPGMDIV ...)
gvwList.ShowingEditor += GvwList_ShowingEditor;
```

This conflicts with the packaged method/grid grammar and Designer-ownership rules: `packaged-style-contract.md:82-107, 163-166, 242-248` and `packaged-style-contract.json:43-60, 109-164`. The unverified problems are the query/save method family, grid-column identity, and code-behind static event subscription. `SystemAPPKey` itself is a target identity, not a defect: the current generic verifier explicitly accepts program-key class names and does not impose a universal `Form` suffix.

### P1: Generated SP/SQL style was not applied

The live deployment payload (`JSONL:L555`) generated `CREATE OR ALTER PROCEDURE [dbo].[sp_SYS_SystemAPPKey_SELECT]` and `[dbo].[sp_SYS_SystemAPPKey_SAVE]` with no standard metadata separator and comma-after-parameter formatting:

```sql
CREATE OR ALTER PROCEDURE [dbo].[sp_SYS_SystemAPPKey_SAVE]
    @USERID    VARCHAR(30),
    @USERIP    VARCHAR(50),
    @XML_DATA  TEXT
```

The packaged SQL contract requires the procedure metadata separator and leading commas for later parameters (`skills/sql_formatting_style_harness/references/style-contract.md:51-70`). Procedure names are source/target-bound; there is no universal PB `USP_...` naming requirement. Because the assistant invented these names without a supplied procedure or target naming authority, the valid finding is missing authority and missing governed SQL-style evidence, not failure to use one universal prefix. No provider selection, candidate preparation, `verify_sql_formatting_style`, final SQL hash, or SQL release receipt appears in the session. The SQL harness contract explicitly requires those artifacts (`skills/sql_formatting_style_harness/SKILL.md:20-40, 89-107`).

This finding is about generation style, not SQL semantics. The rollback test's `NOT EXISTS` predicates are not independently called a formatting error because the SQL contract preserves existing/new behavior tokens; the failure is that generated SQL never entered the governed style path.

### P1: Completion was closed without style/QA evidence

The session recorded a DLL artifact as `implementation_and_build_evidence`, while its detail asserted that live DB rollback CRUD also passed (`JSONL:L732` output). It then evaluated and closed the Goal as complete (`JSONL:L751`, `JSONL:L757`) even though the final response explicitly left ERP click and visual QA outstanding (`JSONL:L779`). Build success (`JSONL:L538`, exit 0) and DB rollback success (`JSONL:L691`, all five CRUD/audit flags true, rows/checksum unchanged) do not bind C#/SQL style receipts or prove visual behavior.

## B. Overclassification and Audit False Positives

- The first and repeated front-door decisions classified a simple EA101T CRUD request as `heavy/security`, blocked execution behind large-work preflight, and selected role-DAG-oriented setup (`JSONL:L22`, `JSONL:L146`). `APPKey` was treated as a security subject although the request was ordinary table maintenance. This caused visible delay and irrelevant planning.
- Missing `pb-to-csharp-migration-harness` evidence must not be reported as a PB migration defect. The user did not request PB migration. The current audit scope requires PB artifacts plus a C# target and migration intent before entering that audit (`src/orchestration/session_skill_audit.py:3147-3190`). The C# style mismatch above is real, but its correct label is “generic C#/Designer style gate absent,” not “PB migration failed.”
- The initial Goal errors (`JSONL:L42`, missing criterion mapping; `JSONL:L60`, stale active goal) and zero subagents are runtime/process noise, not application defects. The single-controller decision was explicitly justified by the tightly coupled CRUD state (`JSONL:L139`).
- Global memory lookup and the final PB migration memory citation (`JSONL:L165`, `JSONL:L171`, `JSONL:L779`) were unrelated to this non-PB task. Treat this as scope pollution, not evidence that the generated screen was PB-derived.

## C. Host/Tool Limitations

- The session had no external ERP UI/manual-click evidence; the final response correctly said visual/runtime click QA remained. This limits proof but does not explain the missing style receipts.
- The SQL MCP path could execute live SQL, but it was used directly for deployment (`JSONL:L555`) rather than paired with the packaged host-LLM SQL provider and verifier. This is an execution-choice/routing gap, not an unavailable capability.
- The session used `svn status` in the TY project (`JSONL:L585`); this audit does not treat that as Git evidence and did not rerun it.

## D. Fixed by the Session's Current Result

- The mistaken project SQL files were removed and their project entries deleted after the user's correction (`JSONL:L483`, `JSONL:L489`). The subsequent file check was empty (`JSONL:L584`).
- The first Designer exposed audit columns and used a grid new-item row (`JSONL:L373`). The correction moved to explicit header buttons and hid audit columns; final Designer readback shows `AutoPopulateColumns=false`, hidden audit-column visibility, and `행추가`/`행삭제` buttons (`JSONL:L523`, `JSONL:L645:84-90,170-227`).
- The user's title/resource edit was preserved (`JSONL:L606`, `JSONL:L645:226`). The project compiled and the DLL contained `Konesystem.SYS.SystemAPPKey` (`JSONL:L538`, `JSONL:L586`).
- The transactional DB test passed INSERT/UPDATE/DELETE plus audit-field checks and restored the nine-row EA101T checksum (`JSONL:L691`). These are behavior/build receipts only; they do not repair the style or completion-gate failures.

## E. Current Remediation and Known Residuals

1. **Packaged remediation:** `csharp-designer-style-harness` now verifies one exact hash-bound C# WinForms/DevExpress/KoneLib source/Designer pair independently of PB intent. Current tests cover adversarial method/column/event shapes and confirm that program-key class identities do not require a `Form` suffix.
2. **Routing residual:** ordinary generated or modified C#/Designer and stored-procedure work still needs observed host routing to the generic C# verifier and the SQL provider/verifier. Packaging proves capability, not that the audited session used it.
3. **Completion residual:** completion must bind applicable C# style, SQL style, exact project/build/dependency, DB, and visual/manual evidence. A DLL hash or asserted DB detail cannot expand into proof of UI behavior or generalized equivalence.
4. **Correction residual:** the corrections at `JSONL:L483` and `JSONL:L523` had no style receipt to invalidate or regenerate. Current packaged capability does not recreate that missing historical evidence.
5. **Scope residual:** scoped memory and task-domain citations must remain separate from historical PB material unless PB migration is actually requested.

The broader PB recurring-contract catalog is now **18 Enforced / 15 Weak / 0
Missing** in current static source/test coverage. That count does not make this
non-PB session a PB migration, and it does not repair its missing style receipts.
The `2.9.144` release pass observed `9/9` focused packaging/docs tests green,
including the 45-skill catalog and generic C#/Designer packaging; no runtime,
Designer, project, DB, or UI suite was rerun for this two-report completion.

Current external boundaries remain explicit. Real ORCA/PBL export and readback
are not applicable to `01a` and must not be used to overclassify it, but remain
unverified for the broader PB workflow. The session observed a compile and a
transactional DB rollback exercise, yet generalized exact target `.csproj`
inclusion/build/dependencies and live DB equivalence/deployment receipts remain
unverified. DevExpress Designer load, the actual UI workflow, non-HMAC host
authenticity, and Roslyn-grade semantic proof remain pending. The stable
4,009,987,266-byte `019f` source subsequently completed naturally with exit
code 0 in 139.576642 seconds at 80.582031 MiB peak RSS. Source
open/pass/original passes were 1/1/1, the valid summary was 161,096 bytes, and
temporary residue was zero. The <=69-second objective remains unmet by
70.576642 seconds and non-blocking.

## Prioritized Regression List

| Priority | Regression | Expected result |
| --- | --- | --- |
| P1 | New WinForms/DevExpress CRUD request generates `.cs`/`.Designer.cs` | Run the packaged generic C# verifier on the exact pair; packaging alone cannot substitute for the per-artifact receipt. |
| P1 | Implementation creates or changes a stored procedure | SQL provider plus `sql-formatting-style-harness` runs on the exact candidate; metadata/parameter/layout/style failures block deployment or completion. |
| P1 | Build and DB test pass while visual/style evidence is absent | Goal/completion remains pending; final prose cannot say complete. |
| P2 | Ordinary `APPKey`/CRUD request enters security heavy preflight | Classify as software CRUD unless credentials/authentication behavior is actually requested. |
| P2 | Non-PB C# task is audited as PB migration | Do not require PB receipts; require the generic C# gate instead. |
| P2 | User correction changes generated UI/SQL | Invalidate and rerun all applicable style and completion evidence. |

**Bottom line:** `01a` remains negative evidence: its user-visible style and completion-gate failures are confirmed, while its later UI/file corrections remain real and must not be re-reported as defects. Current source packages the missing generic C#/Designer capability, but automatic per-artifact routing and all applicable external receipts still require observed evidence.
