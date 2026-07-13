# SQL Formatting Provider Minimal Workflow

## Scenario

A user supplies a short T-SQL query and asks for formatting only. `CODEX_HOME` has no compatible host-local SQL formatting skill, so front-door routing selects the packaged `sql-formatting` provider and then `sql-formatting-style-harness`.

## Expected steps

1. Inspect host-local providers and record that none is compatible.
2. Inspect `skills/sql_formatting/SKILL.md` and its support files.
3. Select packaged provenance with `execution_actor=host-llm` and `headless_python_formatter=false`.
4. Read the original query and the canonical `skills/sql_formatting_style_harness/references/style-contract.md`.
5. Let the host LLM produce the formatted candidate.
6. Run `src.skills.sql_formatting_style.verify_sql_formatting_style` with original and candidate.
7. Return the candidate only if the verifier succeeds.

The demo's actual_runtime_path differs at candidate generation: it uses a bundled static fixture and records `host_llm_executed=false`. It still executes the real verifier, proving source -> candidate -> verifier wiring without claiming live model work.

## Expected evidence

- Controller or assistant capability is `sql_formatting`.
- Provider metadata source is `packaged-kh-skill`.
- Immediate skill order is `sql-formatting`, then `sql-formatting-style-harness`.
- Original and candidate artifacts are readable and hashed.
- Candidate provenance distinguishes live host output from a demo fixture.
- Verifier output contains success, exit code, issue list, and contract metadata.
- `execution_level=procedure-policy` records that the host applies the provider procedure.
- `implementation_targets=src.skills.sql_formatting_provider.inspect_packaged_sql_formatting_provider,src.orchestration.kh_front_door.build_kh_front_door,src.skills.sql_formatting_style.verify_sql_formatting_style` records discovery, routing, and verification ownership.
- `verification=provider-smoke+provider-demo+catalog-provider-quality-tests+source-candidate-verifier` records the required evidence path.

## Failure cases

- A corrupt packaged provider produces `blocked_until_sql_formatting_provider`; no selected SQL provider is claimed.
- A missing canonical contract makes the packaged provider corrupt.
- A changed literal, predicate, expression, or comment causes verifier failure.
- Running only the verifier does not satisfy provider execution because the verifier does not generate candidates.
- A copied contract under `skills/sql_formatting/references/style-contract.md` fails provider inspection.

## Done criteria

- The selected provider follows host-local -> packaged KH precedence.
- The source-to-candidate actor and provenance are explicit.
- The canonical contract is referenced, not forked.
- The real verifier passes the candidate.
- Missing/corrupt provider states fail closed and cannot appear as selected provider evidence.
