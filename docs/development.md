# KH development checks

Runtime checkers use only the Python 3.11+ standard library. Skill instructions are Markdown. Type-checking tools are needed only during development.

Run from the repository root.

```powershell
python -B -m unittest discover -s tests/domain
npx --yes pyright@1.1.413 --project pyrightconfig.json
python -B scripts/kh_check.py package <absolute-plugin-root>
npx --yes @anthropic-ai/claude-code@2.1.293 plugin validate .claude-plugin/plugin.json --strict
npx --yes @anthropic-ai/claude-code@2.1.293 plugin validate .claude-plugin/marketplace.json --strict
```

Pyright covers `src`, `scripts`, and all executable PB-skill scripts. In addition to `standard` mode, C#/PB lexers and measurement-input validation modules use `strict`. Do not disable whole rules or assume external input is `Any` to remove errors. GitHub's `KH checks` workflow runs Windows/Python 3.11 and 3.14 unit tests plus type/package checks. Distinguish configuration presence from an actual passing run.

Use static typing to find inconsistent function contracts; separately validate external input such as JSON at runtime. [Python type annotations are not automatically enforced at runtime](https://docs.python.org/3/library/typing.html), and [TypeScript annotations are erased from output code](https://www.typescriptlang.org/docs/handbook/2/basic-types.html). Changing programming languages alone does not resolve faulty parser assumptions, false positives/negatives, or business semantics. For new counterexamples, preserve source/target artifacts and expected behavior, verify the actual failure, then fix it.

Zero type errors and passing unit tests do not replace C# compilation, Designer execution, real PB/ORCA environments, or SQL Server results. For independent usage evaluation, provide the task request and minimal required source, not the implementer's intended answer.

## GitHub publication

This repository's existing publication flow uses a source/version commit on `release` and a separate publication commit with the identical file tree on `main`. The marketplace registration reads `main`'s `.agents/plugins/marketplace.json`, whose plugin source points to `release`. Preserve that structure and verify both remote refs, the manifest version and tree equality after pushing. Keep unrelated working-tree files out of the commits. Publishing only the source branch is not the completed existing release flow.

GitHub publication does not establish an installed plugin update. Inspect an installed version only when requested; do not write an app's installation cache as a release-verification workaround.

## Shared Claude and Codex package

The shared skill tree is installed through two platform adapters. Codex retains the `kh-uaf` plugin and `kh-uaf-marketplace` catalog, while Claude uses `kh-skills@gnho-labs`. Both manifests carry the same release version. Keep the domain guidance and checker implementations in one place; host-specific metadata does not establish identical model behavior.

Validate both Claude files explicitly: validating the repository root auto-selects its marketplace catalog. The CLI version is pinned for CI. For an installation check, use a temporary `CLAUDE_CONFIG_DIR` so validation does not modify the user's installed plugins or settings.
