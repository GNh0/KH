# KH UAF 2.9.144 Release Checkpoint

Date: 2026-08-25
Release: 2.9.144
functional_release_ready=true
bounded_memory_gate_passed=true
performance_stretch_69s_met=false
real_corpus_natural_exit=true

## Verdict

2.9.144 is functionally release-ready at the source and regression-test
boundary. Final independent review found no P0, P1, or P2 finding, and the exact
four-module session aggregate passes 399/399 in 60.344 seconds.

The stable 4,009,987,266-byte source completed naturally with exit code 0 in
139.576642 seconds. Peak RSS was 80.582031 MiB; source open, source pass, and
original-source pass diagnostics were each 1; the final summary was a valid
161,096-byte document; and temporary residue was zero. Duplicate-key input
fails closed as P0 `input_integrity`, and UTF-8 byte bounds are verified.

The <=69-second objective remains unmet by 70.576642 seconds and must not be
reported as passed. Under the current release policy it is a deferred stretch
target, not a 2.9.144 release blocker.

The three manifests are synchronized at 2.9.144, and the marketplace plugin
source ref remains `codex-runtime`. Installed-cache/new-task behavior has not
been verified for this release.

## Completed Fixes

- PB/C# contracts
- SQL contracts and checks
- Generic C#/Designer contract coverage
- Routing production SQL runner
- Registry receipts and global sequence handling
- Memory approval exact binding and compact projection
- Bounded, JSON/SQLite-backed session audit and postmortem state
- Documentation and version updates

## Functional Evidence

| Exact module or group | Result |
| --- | ---: |
| Final independent review | No P0/P1/P2 |
| Exact four-module aggregate | 399/399 in 60.344 seconds |
| Duplicate-key handling | Fail-closed P0 `input_integrity` verified |
| UTF-8 output bounds | Byte bounds verified |

The aggregate is the current semantic release evidence for the audit and
postmortem runtime. Documentation-only release-wrap changes do not invalidate
that result and do not require another aggregate run.

## Focused Release Validation

| Check | Result |
| --- | ---: |
| Manifest and marketplace JSON parsing | 4/4 valid |
| Manifest versions | 3/3 at 2.9.144 |
| Marketplace plugin source ref | `codex-runtime` |
| `tests.test_plugin_packaging` | 27/27 in 1.816 seconds |
| Packaged skill catalog | 45/45 valid; 0 issues |
| Packaged skill quality | 45/45 valid; lowest score 10.0; 0 gaps |
| PB-to-C# packaged smoke | Passed; 36/36 targets resolved; 0 issues |
| Generic C#/Designer packaged smoke | Passed; 6/6 targets resolved; 0 issues |
| Release-fact assertions | 9/9 present |
| `git diff --check` | Passed |

## Performance Evidence

| Measurement | Result | Interpretation |
| --- | ---: | --- |
| Source size | 4,009,987,266 bytes | Stable real corpus |
| Process result | Natural exit code 0 | Audit completed successfully |
| Wall time | 139.576642 seconds | <=69 seconds missed by 70.576642 seconds |
| Peak RSS | 80.582031 MiB | Bounded-memory requirement passed |
| Physical source diagnostics | `source_open_count/source_passes/original_source_passes = 1/1/1` | One original source pass |
| Final summary | Valid, 161,096 bytes | Public summary contract completed |
| Temporary residue | 0 bytes | Deterministic cleanup passed |

The accepted run proves natural completion, bounded memory, one original source
pass, valid summary output, and deterministic cleanup. The remaining
performance work is a scalar-only events/facts redesign to pursue the unmet
<=69-second stretch while retaining raw payload only where authenticated
correlation or replay semantics require it.

## Residual Boundaries

- Real ORCA/PBL export and readback remain environment-dependent. They gate
  claims about a particular migration, not the package source release.
- Exact target project inclusion, build dependencies, live database
  equivalence/deployment, DevExpress Designer loading, and interactive UI
  behavior require target-environment receipts where those claims apply.
- Non-HMAC host authenticity and Roslyn-grade semantic proof remain outside the
  current focused evidence.
- Installed-plugin behavior requires an upgrade followed by a new-task runtime
  test; source and manifests alone do not prove it.
- The 4 GB <=69-second objective remains unresolved and non-blocking.

## Post-Source-Release Operations

1. Upgrade the installed runtime and verify behavior in a new task.
2. Schedule the scalar-only event/fact redesign and another stable-corpus
   benchmark against the non-blocking <=69-second stretch.

## Checkpoint Boundary

This checkpoint claims functional source readiness, bounded memory, one
original source pass, natural completion, valid summary output, and
deterministic cleanup. It does not claim the <=69-second stretch passed,
runtime upgrade, or installed new-task verification.
