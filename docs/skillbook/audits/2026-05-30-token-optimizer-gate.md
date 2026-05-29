# Token Optimizer Gate Audit

Date: 2026-05-30
Target session: `019e7441-eecf-7e23-b9ee-9aefa1c8fdf6`
Target project: `C:\Users\User\Documents\Codex\SaaS Project`

## Why

The PipePilot SaaS implementation session was a large, subagent-heavy workflow. It used worktrees, TDD, spec review, code quality review, sandbox retries, commits, and task-by-task progress tracking. That is the kind of workflow where KH must use `token-optimizer` as a context budget gate, while preserving answer quality.

## Measurement

The audit read the parent rollout and direct child/subagent rollouts from the local Codex state store and applied the new `summarize_agent_transcript` path.

Sample:

- Threads measured: 21
- Codex DB `tokens_used` total for sampled threads: `60,359,338`
- Raw JSONL rollout tokens, estimated: `2,062,828`
- Normalized message/tool transcript tokens, estimated: `329,191`

Quality-preserving transcript optimization:

- Without token optimizer: `329,191`
- With token optimizer: `297,076`
- Estimated tokens saved: `32,115`
- Savings ratio: `9.76%`
- Evidence families present: `123`
- Evidence families missing after optimization: `0`

Raw JSONL avoidance:

- Raw JSONL without optimizer: `2,062,828`
- Optimized transcript: `297,076`
- Estimated tokens saved: `1,765,752`
- Savings ratio: `85.60%`

## Interpretation

The quality-preserving transcript savings are intentionally modest. Agent development transcripts contain dense evidence that must not be removed:

- task status and next task
- RED/GREEN and failing-first evidence
- command, exit code, and sandbox retry reason
- worktree or workspace strategy
- spec review and code quality review findings
- reviewer severity and file references
- commit SHA or commit evidence

For these workflows, a `9-15%` savings range can still be correct if it preserves the evidence needed to continue safely. The much larger `85%+` savings comes from avoiding raw rollout JSONL dumps, which include repeated metadata and host instructions that should not be loaded into working context.

## Result

`token-optimizer` now has an agent transcript path that can save context while preserving lifecycle quality evidence. The gate should report `token_optimizer_status` as `used`, `considered_not_needed`, `passthrough`, or `blocked`.

If preserving the evidence would leave little to compress, the correct outcome is `passthrough` or low savings, not lower answer quality.
