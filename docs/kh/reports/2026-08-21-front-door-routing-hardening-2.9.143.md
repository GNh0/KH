# KH UAF 2.9.143 Front-Door Routing Hardening

## Scope

This release reduces front-door latency and overclassification while preserving governed routing for mutations, production execution, destructive operations, credentials, and other high-impact work.

## Root Causes

- Request intent was inferred from broad keyword matches, so quoted text, negated actions, SQL payloads, and outer execution directives could be confused.
- SQL intent was re-evaluated independently by the classifier and plugin composition layer, allowing the two decisions to diverge.
- Assistant-authored JSON could resemble a host/runtime receipt closely enough to overstate that KH skills had executed.
- Repeated parsing and dynamic term matching increased latency, especially for long or repetitive prompts.

## Structural Changes

- Added a structural request-act parser that separates outer instructions, quoted or fenced payloads, negated clauses, approvals, actions, targets, and scope.
- Shared the parsed request act across classification, front-door, and plugin composition instead of rescanning raw text independently.
- Separated SQL formatting payloads from outer directives such as production execution, preserving high-risk routing when execution is requested.
- Normalized Unicode apostrophes and applied action-scoped negation and explicit approval denial precedence.
- Treats assistant-authored front-door JSON as unverified; only correlated host/runtime/tool evidence may prove execution.
- Removed repeated parsing and dynamic regular-expression compilation from hot paths and retained lazy loading for large-work orchestration.

## Independent QA History

- Initial adversarial matrix: classifier 62/75 and front-door exact 56/75; NO-GO.
- Expanded independent review: 95/103; NO-GO due to remaining provenance, negation, SQL-boundary, and latency defects.
- The final eight structural fixes were followed by 616 passing local regression tests.
- The user explicitly requested release without another independent replay after the final fixes. Therefore, this release does not claim that the final 103-case independent matrix was rerun or passed.

## Latency Evidence

- Warm classification benchmark after the first structural pass: average 22.253 ms, maximum 100.397 ms across 200 runs.
- Latest shared parser/classifier/plugin benchmark: median 5.031 ms for a 752-character repetitive prompt and 39.217 ms for a 6,002-character prompt.
- These are local in-process measurements. They do not include Codex host scheduling, process startup, tool invocation, or model latency.

## Residual Risk

- The final independent adversarial replay was intentionally skipped, so unseen wording may still expose false positives or false negatives.
- Deterministic language parsing remains heuristic across multilingual, nested-quotation, and highly ambiguous prompts.
- Host-native fast-path trust still depends on the host providing correlated typed provenance rather than plain assistant text.
- Performance measurements are machine- and process-dependent and should not be treated as end-user latency guarantees.

## Release Decision

Release 2.9.143 with the verified local regression, packaging, catalog, smoke, and diff checks. Retain the independent NO-GO history as evidence rather than rewriting it as a pass.
