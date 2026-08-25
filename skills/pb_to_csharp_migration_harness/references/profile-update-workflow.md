# Packaged Profile Update Workflow

This is an explicit maintenance workflow. It never runs during normal generation.

Normal PB-to-C# generation uses the packaged fixed profile as its sole style authority. A migration request never authorizes unapproved external style discovery, private identity lookup, source-control metadata lookup, arbitrary-root traversal, or style extraction from the target/PB source.

## Trigger Boundary

Run this workflow only after the user explicitly requests an update to the packaged style profile and authorizes the exact candidate artifacts. A normal migration request, a missing identifier, a failed verifier, or low confidence is not authorization.

The runtime maintenance entry point is `src.skills.pb_to_csharp_profile_maintenance.build_profile_update_candidate`. Compatibility wrappers in the migration module delegate to this entry point; they do not restore discovery.

## Accepted Candidate Set

The runtime accepts exactly two artifacts:

1. one absolute code-behind `.cs` path;
2. one absolute `.Designer.cs` path.

The paths must be non-empty, unique, absolute, and listed explicitly in `artifact_allowlist`. A directory, source root, wildcard, recursive scan result, sibling project, backup tree, or source-control metadata result is not an accepted candidate set. Supplying `csharp_root` blocks the operation.

## Mandatory Pre-Read Contract

All checks below run before either file is read:

- `explicit_user_authorization` is exactly `true` for this candidate set;
- `profile_id` and `profile_version` are non-empty;
- `artifact_allowlist` contains exactly the two absolute artifacts described above;
- `expected_sha256` contains exactly one valid SHA-256 value for each allowlisted path and no extra path;
- `independent_provenance` contains one record per path with non-empty `source_system`, `capture_id`, `captured_by`, and `independent_reviewer`;
- for each provenance record, `captured_by` and `independent_reviewer` are different;
- `custody_records` contains one record per path with non-empty `custodian`, `receipt_id`, and `acquired_at`;
- every custodian is different from every provenance capturer and reviewer;
- `uniqueness_decision.status` is `unique`, `copied_header` is `false`, and `ambiguous` is `false`;
- the uniqueness decision names the exact allowlisted paths and a non-empty `reviewed_by` who is independent of all capturers, reviewers, and custodians.

Any missing, extra, duplicate, relative, ambiguous, or cross-role value blocks before content access.

## Post-Read Validation

Only after the pre-read contract passes may the runtime read the two files. It then:

1. reads raw bytes from each exact allowlisted path;
2. recomputes SHA-256 and requires an exact match with `expected_sha256`;
3. decodes each artifact as UTF-8 with optional BOM;
4. requires exactly one `// AUTHOR: ...` header and exactly one `// ARTIFACT-ID: ...` header in each file;
5. rejects missing or repeated headers;
6. rejects reused `ARTIFACT-ID` values across the pair;
7. extracts a candidate summary of method names, grid/view/column names, binding fields, and `rpsSpin` repositories.

The AUTHOR header is inspected only inside the exact authorized artifacts after provenance, custody, uniqueness, and hash checks. It is never a search key and never authorizes discovery.

## Output Boundary

The function returns an unsanitized `candidate_ready` record with artifact receipts when every check passes. It does not update the packaged contract, does not write a profile, and sets `runtime_generation_eligible=false` and `write_status=candidate_only`.

An independently reviewed sanitization and contract-update step is still required before changing the packaged profile. Concrete paths, identity data, identifiers, hashes, source excerpts, and fingerprints must never be copied into packaged runtime references.

## Explicitly Unsupported Inputs

Database queries, PBL exports, PblScripter, ORCA, SQL definitions, arbitrary scans, and source-control metadata are not inputs to `build_profile_update_candidate`. They may be used in a separately authorized behavior-analysis workflow, but they cannot teach or override the packaged style profile through this maintenance API.

No database credential, server name, connection string, private source root, or version-control metadata is read by this workflow.

## Sanitization Gate

Before a candidate can become a future packaged contract, an independent maintainer must remove:

- absolute or user-specific paths;
- private identity and account values;
- database, server, project, program, procedure, table, column, and concrete control identifiers;
- source hashes, timestamps, counts, snapshots, and artifact fingerprints;
- raw C#, Designer, SQL, PB, or PBL-derived excerpts;
- credentials, machine configuration, and license information.

Only generalized rules may be proposed. Normal generation continues to use the currently packaged immutable profile until a separately reviewed release replaces it.

## Required Maintenance Evidence

- explicit authorization receipt;
- exact two-path allowlist;
- expected and recomputed SHA-256 receipts;
- independent provenance records;
- independent custody records;
- exact-set uniqueness decision;
- one AUTHOR and one unique ARTIFACT-ID header per artifact;
- `candidate_ready` or fail-closed issue list;
- sanitization review performed outside normal generation;
- smoke, quality, and privacy results for any later packaged-contract edit.
