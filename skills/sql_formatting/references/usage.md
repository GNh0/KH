# SQL Formatting Provider Usage

## When to use

Use this packaged provider when a user requests SQL/T-SQL formatting or cleanup, no compatible host-local SQL formatting provider is available, and KH can read this skill package. A compatible host-local provider has precedence. This packaged provider is the fallback execution procedure; `sql-formatting-style-harness` remains the independent verifier.

The provider applies only to formatting-preserving work. Requests for query optimization, scalar-function conversion, schema changes, predicate rewrites, or business-logic changes need a separately scoped workflow and evidence.

## Inputs to collect

- Exact original SQL text or a stable file path.
- User constraints, including formatting-only boundaries and encoding requirements.
- Provider provenance selected by front-door routing.
- The canonical contract at `skills/sql_formatting_style_harness/references/style-contract.md`.
- A complete per-changed-scope semantic/business-role plan when packaged normalization changes aliases.
- A writable candidate destination when file output is requested.
- The verifier entrypoint `src.skills.sql_formatting_style.verify_sql_formatting_style`.

## Runtime binding

- Execution level: `procedure-policy`.
- Implementation targets:
  - `src.skills.sql_formatting_provider.inspect_packaged_sql_formatting_provider` for packaged-provider compatibility.
  - `src.orchestration.kh_front_door.build_kh_front_door` for provider precedence and provider-before-verifier ordering.
  - `src.skills.sql_formatting_style.verify_sql_formatting_style` for candidate verification.
- Verification: run the packaged provider smoke/demo checks and the focused catalog, provider, and quality tests; formatting output still requires a successful source-to-candidate verifier result.

## Execution pattern

1. Confirm provider precedence evidence: compatible host-local first, packaged KH second, otherwise blocked.
2. Record that the execution actor is the host LLM. The package does not contain a full headless formatter.
3. Read the exact source and canonical generic contract. Do not create a local contract copy. Treat source/surrounding `JOIN` layout as authoritative and use the contract's depth-aware `GROUP BY`/`ORDER BY` packing rules.
4. Generate one candidate through the host LLM while preserving SQL behavior-sensitive tokens.
5. If aliases changed, record a complete plan for every changed scope and declaration. Role-family membership must be reviewer-approved semantic input, not an inference from repeated table names or source order.
6. Record whether the candidate came from a live host LLM or a static demo fixture. Never blur those provenance states.
7. Pass original, candidate, and any required alias plan to the verifier.
8. Release the candidate only when verifier success is true; otherwise preserve the source and report the exact issue codes.

For a file-based check, the verifier can run as `python -m src.skills.sql_formatting_style --original <source.sql> --formatted <candidate.sql>`.

## Evidence to produce

- Provider id and provenance source.
- `execution_actor=host-llm` for real formatting work.
- `headless_python_formatter=false`.
- Original and candidate hashes or paths.
- Canonical contract path.
- Complete per-changed-scope alias plan when aliases changed, with `alias_role_plan_validation.status=verified`.
- Verifier success, exit code, issue codes, and verification id.
- A blocked provider status when discovery reports missing or corrupt.

The runnable demo uses a bundled static candidate fixture. It truthfully records `host_llm_executed=false`, `candidate_provenance=bundled-static-demo-fixture`, and then invokes the real verifier. That demonstrates the handoff contract without pretending to execute a host model.

## Failure handling

- If the host-local provider is missing or corrupt, continue only when the packaged provider inspection is compatible.
- If the packaged provider or canonical contract is missing/corrupt, block formatting and do not select a provider.
- If verification fails, do not repair silently in a loop; report the first token/style evidence and require a revised host candidate.
- If packaged normalization changes aliases in any scope without a complete plan, block readiness and retain the source.
- If the request exceeds formatting, separate the change and obtain the evidence required by the canonical contract.

## Quality bar

A valid run lets another reviewer identify the original, the candidate, who produced the candidate, which provider contract was applied, which canonical contract governed it, and the real verifier outcome. Provider and verifier roles must remain distinct, and no second generic style contract may exist under `skills/sql_formatting/`.
