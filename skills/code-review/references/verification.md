# Verification scope and target acceptance

Choose evidence for the changed responsibility and honor the user's execution limits. No fixed build/test sequence applies to every task. A missing required environment is unverified, not a guessed success or permission to change another system.

| Change | Evidence that answers its actual risk |
| --- | --- |
| SQL layout | Actual original/candidate comparison, identifiers and literals, supported layout at every affected query depth |
| SQL behavior | Caller and schema contracts, row keys/cardinality, missing and duplicate rows, requested filters and persisted values; authorized DB execution when needed |
| C#/Designer | Current controls and initialization, paired code/Designer, caller/events/bindings and reference-program comparison; compilation or screen execution only when authorized and relevant |
| PB migration | Complete source events/DataWindows, actual export/runtime and mapped C#/SQL contracts; static comparison alone does not prove migration parity |
| Hook/runtime | Unselected work, selected scope, failure/partial writes, cancellation, continuation and next-task isolation; distinguish event replay from native host firing |
| Package/delivery | A self-contained installed/extracted copy, discovered entrypoints and actual target version; publication and CI do not establish installation |
| Recovery/memory | Latest correction/cancellation after restoration, project/chat boundaries, full retrieval of shortened previews, and preservation of existing durable entries |

For behavior changes, establish the expected result from the user's requirement and the actual pre-change contract. Include a valid case, a permitted alternative, a failure and insufficient evidence where relevant. Keep the production path in the fixture: preparation added only by the test must not certify preparation absent from the real entrypoint. Keep failures and omitted scope visible; neither a successful exit code nor test counts establish necessity or business correctness.

Re-read the final diff and follow every introduced behavior through its owner, including incidental initialization, permissions, fallback values and state transitions. Establish why the change is needed and whether the existing path already handles it. Correct only confirmed violations, repeat affected checks, then check the combined repairs for regressions. A new warning must be resolved from the actual request/source; changing syntax or a fixture merely to hide it is not a repair.

At handover, state the result, material findings and the evidence's limits. If application/installation was requested, verify that target separately when authorized. A local static pass, repository CI, manual main-agent audit, independent reviewer and real target execution are different evidence. Do not label one as another or expand production-write/build authority to obtain a pass.
