# C# Designer Style Harness Usage

## When to use

Use this runtime-backed verifier when a current task supplies one exact C# WinForms/DevExpress/KoneLib code-behind file and one exact `.Designer.cs` file and the requested outcome is deterministic style-contract verification. It is appropriate for analysis-only review, generated-pair acceptance, and a narrowly scoped query-only check. It is not a PB export tool, project build tool, live DevExpress layout loader, database checker, or source editor.

## Inputs to collect

- The absolute source path and its byte SHA-256.
- The absolute Designer path and its byte SHA-256. The paths must be distinct.
- The requested operation family, normally query plus save, or exactly `("query",)` for read-only verification.
- Optional expected or target identities used to prove that named forms, controls, fields, methods, and procedures are present in the exact supplied pair.
- Optional identity exceptions or type-chain evidence may be supplied only to obtain explicit blocked evidence. The standalone public verifier never treats caller-provided provenance, signatures, roots, callbacks, or type claims as authority.
- The packaged contract path `skills/csharp_designer_style_harness/references/style-contract.json` when a structured profile is needed.
- The runtime entrypoint `src.skills.csharp_designer_style_contract.verify_csharp_designer_style`.

Do not substitute a sibling form, backup file, project-wide style scan, cached result, author metadata, or an unhashed text value. A receipt is an address plus expected bytes; the verifier reopens the address and recomputes the digest. Standalone verification has no identity-exception authorization path. A future host integration must validate any opaque host-issued receipt outside this public API.

## Runtime contract

- Execution level: `python-module`.
- Implementation targets:
  - `src.skills.csharp_designer_style_contract.verify_csharp_designer_style` performs the deterministic source/Designer contract check.
  - `src.contracts.HarnessResult` is the structured result boundary.
  - `skills/csharp_designer_style_harness/scripts/smoke_check.py` checks package wiring, target resolution, AST, and demo execution.
  - `skills/csharp_designer_style_harness/scripts/demo.py` runs the real verifier against a passing and a deliberately failing pair and writes demo artifacts.
- This is not `hybrid-harness`. The host owns intake, receipt collection, and interpretation; the callable Python module owns the actual verification logic.
- Verification returns a `HarnessResult`, not a caller boolean. Preserve its metadata, issue codes, paths, hashes, and verification id.

## Execution pattern

1. Perform KH front-door intake and preserve the execution gate and selected skill evidence. A skill catalog read is not application evidence.
2. Read the two exact artifact paths and recompute their byte hashes before the verifier call.
3. Build the two receipts. Normalize optional `sha256:` prefixes only as accepted by the verifier; never alter file bytes.
4. Call `verify_csharp_designer_style(source_receipt, designer_receipt, applicable_operations=..., expected_identities=..., target_identities=..., native_helpers=..., analysis_only=True)`. Do not attempt to manufacture trust with identity exceptions, type-chain evidence, roots, signatures, or callbacks.
5. Check `success`, `status`, `exit_code`, and the structured metadata. Confirm the source hash, Designer hash, packaged contract hash, `verification_binding`, and verification id all bind to this call.
6. Treat issue codes as the remediation list. Missing evidence is blocked, not permission to infer a control, field, event, method, procedure, or target identity.
7. Retain the command result and exact verifier output. A separate build, layout, PB, database, or deployment claim needs a separate check and receipt.

Example:

```python
from pathlib import Path
import hashlib
from src.skills.csharp_designer_style_contract import verify_csharp_designer_style

def receipt(path: Path) -> dict[str, str]:
    return {
        "path": str(path.resolve()),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }

result = verify_csharp_designer_style(
    receipt(Path("Screen.cs")),
    receipt(Path("Screen.Designer.cs")),
    analysis_only=True,
)
print(result.to_dict())
```

## Evidence to produce

- The exact source and Designer paths and the observed byte SHA-256 values.
- The verifier `HarnessResult` with `success`, `status`, `exit_code`, `metadata`, and a non-empty verification id.
- The packaged contract hash and structured issue list from the same result.
- The selected operation family, expected/target identity digests, native-helper digest, type-chain-evidence digest, identity-exception digest, analysis mode, result status, and issue digest from `verification_binding`.
- Smoke command stdout/exit code and demo command stdout/exit code.
- Demo artifact paths, hashes, and the distinct passing/failing case summaries.
- A bounded conclusion: the result verifies the supplied pair against the packaged contract, not a whole project or live runtime.

## Failure handling

- Missing front-door/runtime evidence means the skill is not yet applied; do not report a catalog read as a verifier run.
- Missing, unreadable, non-UTF-8, changed, or hash-mismatched artifacts are blocked before style claims.
- Source and Designer identity mismatches, missing partial/base evidence, missing `InitializeComponent`, noncanonical query/save methods, or Designer ownership violations remain failed issue codes.
- Every standalone identity exception and caller-provided type-chain claim is blocked. A free-form exception, matching filename, receipt path, URI label, signature, callback, or caller assertion cannot create authority.
- A smoke failure blocks package readiness. A demo failure blocks demo evidence even if an isolated verifier call passed.
- The verifier never edits the source tree. Repairs, if separately authorized, require fresh receipts and a new correlated verification run.

## Quality bar

A valid run lets another reviewer identify the exact two files, their observed hashes, the packaged contract hash, the callable verifier, the structured result, the operation family, and the current evidence boundary. A passing result is limited to the exact bytes checked. It does not silently upgrade to project compilation, live Designer loading, PB parity, SQL equivalence, or deployment readiness.
