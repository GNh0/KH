# Optional SQL checks

Run `python <plugin-root>/scripts/kh_check.py sql <absolute-original.sql> <absolute-candidate.sql>` to check preservation of literals, comments, tokens, and alias references, plus style diagnostics. Use `--preserve-aliases` for explicit alias preservation. Results do not prove SQL Server execution.

For a standalone check of new SQL, use `sql <absolute-candidate.sql>`. Passing the same file as both original and candidate is an input error. Without a pre-change original, do not manufacture a baseline from a post-change copy. `comparison_baselines.sql=false` means no preservation comparison against the original was performed.

`--normalize-layout` normalizes supported derived FROM/JOIN queries, JOIN/EXISTS whitespace, and clause line breaks, returning the result on stdout without overwriting files. Codex determines alias business roles from the current query and user instructions. `src.sql.aliases` mechanically applies only explicitly specified scope/alias changes.

Errors include token-preservation failures and violations of explicit alignment contracts under inspection. Warnings identify separate style/disfavored-pattern checks. Mark unsupported syntax or semantic changes as unverified, not successful. There is no separate retry procedure to obtain signatures, provider receipts, or hashes.

Check derived blocks even when they are the first FROM source. Inspect opening/closing parentheses, aliases, inner clauses, and derived JOIN conditions together. In nested FROM/JOIN/EXISTS blocks and UNION branches, align relative to each containing block; retain the I-column rule for ordinary JOINs. Do not apply these rules wholesale to function arguments or APPLY merely because they contain parentheses.
