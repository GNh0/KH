# Minimal C# Designer Verification Workflow

## Scenario

A user supplies an exact `OrderForm.cs` and `OrderForm.Designer.cs` pair and asks whether the pair follows the packaged WinForms/DevExpress/KoneLib Designer contract. The requested mode is analysis-only. The host must preserve the exact paths and must not edit the two files as part of this check.

## Expected steps

1. Select `csharp-designer-style-harness` directly from the visible request and skill metadata, then open only the supplied pair. Run the governed KH front door only for an explicit routing audit or an already-governed high-risk workflow; ordinary pair verification needs no routing preflight.
2. Read both files as bytes, compute SHA-256 for each, and confirm the paths are distinct. Use the exact receipts in the verifier call.
3. Call `src.skills.csharp_designer_style_contract.verify_csharp_designer_style` with the two receipts and `analysis_only=True`. Use `applicable_operations=("query",)` only when the user explicitly requests a query-only surface.
4. Inspect the returned `HarnessResult`. Keep the success flag, status, exit code, verification id, artifact hashes, packaged contract hash, and issue codes together.
5. Run `python skills/csharp_designer_style_harness/scripts/smoke_check.py` from the repository or the skill directory. Run `python skills/csharp_designer_style_harness/scripts/demo.py --output-dir <tmp>` and retain its JSON plus artifact receipts.
6. Report only the exact pair's contract result. Do not turn a passing offline check into a claim about project build, live layout load, PB parity, database equivalence, or deployment.

## Expected evidence

- `routing_mode=direct-domain` for ordinary pair verification. When governed routing was actually selected, keep its correlated front-door receipt or explicit blocked reason separately.
- `actual_runtime_path=src.skills.csharp_designer_style_contract.verify_csharp_designer_style`.
- `implementation_targets=src.skills.csharp_designer_style_contract.verify_csharp_designer_style,src.contracts.HarnessResult,tests.test_csharp_designer_style_contract` records the runtime and focused-test ownership.
- `execution_level=python-module`, because the callable Python verifier is the executable authority and the host procedure only gathers and interprets receipts.
- `source_path`, `source_sha256`, `designer_path`, and `designer_sha256` bound to the same verifier result.
- `contract_sha256`, a non-empty `verification_id`, `success`, `status`, `exit_code`, and structured `issues` from `HarnessResult`.
- `smoke_exit_code=0` with target resolution and AST evidence.
- `demo_exit_code=0`, a passing case, a distinct blocked/failure case, and artifact paths below the requested output directory.

## Failure cases

- In governed mode, a blocked front door stops verifier claims. In ordinary direct-domain mode, reading this file alone is still not execution evidence; the exact artifact-bound verifier must run.
- One receipt points to a missing, changed, unreadable, or non-UTF-8 file. Report the exact issue and request a fresh artifact receipt.
- The pair has a missing partial/base contract, noncanonical query/save method, code-behind static UI construction, generic identity, or Designer binding/event mismatch. Preserve the failure issue codes and do not weaken the packaged contract.
- An identity exception lacks exact scope, reason, locator, or provenance SHA-256. Keep the result blocked.
- Smoke or demo output is missing, malformed, or nonzero. Report the failed command separately from the verifier result.

## Done criteria

- The exact pair was reopened and hash-bound during the verifier call.
- The runtime result is a structured `HarnessResult`, not a caller-supplied boolean.
- The smoke script resolves all declared implementation targets and completes AST parsing.
- The demo writes only below `<tmp>`, exercises both success and failure paths, and emits valid JSON/artifact receipts.
- The final report distinguishes inspected, applied, blocked, and verified states and contains no broader build, PB, database, or deployment claim.
