# Hooks and context retention

KH bundles a shared Python 3.11+ core with separate Codex and Claude hook adapters. Hooks are short-lived commands: no background observer, extra LLM call, automatic formatter, build, database execution or MCP startup. Existing project coding-style and source-necessity audits remain the main agent's responsibility.

## Host registration and trust

Codex explicitly loads `hooks/codex-hooks.json` through `.codex-plugin/plugin.json`. Claude uses the default `hooks/hooks.json`. Codex runs command hooks through the configured shell, with a Windows command override; Claude uses the documented direct executable/args form. Both need Python available (`python` on Windows/Claude, `python3` on Unix Codex).

Review bundled hooks in the host before use. Codex requires trust for each hook/script hash; an upgrade does not silently grant it. Use `/hooks` or the desktop's Review hooks / Settings > Hooks. No cache, trust database or global configuration is edited by KH. See [Codex hooks](https://learn.chatgpt.com/docs/hooks) and [Claude hooks](https://code.claude.com/docs/en/hooks). Standalone copied skills do not install these lifecycle hooks.

`KH_HOOKS_MODE=advisory` keeps feedback without edit/Stop denial; `off` disables the core. Default `enforce` denies supported domain edits while required complete KH bodies have not been observed in tool returns. Retries never count as reading. Unknown/malformed input, Python absence, timeout or unsupported host paths remain unverified, not a claimed pass. Host hook failure semantics can allow an action; these are workflow checks, not a security boundary.

## What is actually checked

- Before recognized SQL/C#/PB writes: the relevant current domain entrypoint and shared source-style cycle must have been returned completely. This establishes observed text availability, not understanding or a full reference-program audit.
- After writes: standalone domain checks on actual saved files, bounded to 32 files of 1 MiB each. For observed writes, before/after line hashes identify changed text plus adjacent context; returned text can be read in numbered or split ranges. Later edits invalidate affected read evidence. An existing file does not need an unrelated whole-file read. Missing change baselines remain unverified. These observations do not prove the coherent-unit/caller audit; domain warnings and missing baselines remain visible. No automatic source rewrite occurs.
- Before completion: missing readback or static errors trigger a bounded continuation request. Repeated identical findings or `stop_hook_active` do not loop forever. The agent must resolve violations, re-audit and check regressions; an unsupported or unresolved finding must be reported. No hook can prove a semantic audit from prose or a checker exit code.

Typed Edit/Write/apply_patch and a limited set of literal shell-write paths are recognized. Arbitrary scripts, dynamically constructed paths, hosted tools and specialized host operations can escape this observation. Source bodies returned with line-number decorations, truncation or encoding differences may need a direct complete UTF-8 read. Known files are rechecked on later events, but this is not whole-repository monitoring. Existing limits on builds/DB/other external actions still apply.

## Compaction and durable memory

`PreCompact` saves current-chat user evidence/source locations and existing curated checkpoint. Codex restores through `PostCompact` (or compact SessionStart), with duplicate suppression. Claude restores through `SessionStart(source=compact)`; its PostCompact event is observational and is not used for context injection. Startup/resume loads the same chat's checkpoint plus explicitly curated project memories. A new chat does not inherit another chat's task checkpoint. Interruption preserves needed continuation data and does not restart the task.

Recovery is a bounded preview with original source locations. It is not a second summary that silently replaces the originals. Latest corrections/cancellations take precedence, a checkpoint records its user-record cursor, and incomplete capture is reported. The latest observed UserPromptSubmit is preserved separately even while a large transcript has pending capture; older uncaptured details still require the original log/checkpoint. Supported Codex/Claude transcript adapters are version-sensitive because host transcript formats are not stable public APIs. Images, attachments, deleted logs and unsupported formats remain unverified.

Codex capture accepts both desktop `response_item/message/role=user` text parts and `event_msg/user_message`. Adjacent mirrored representations share one archive record with both source locations; separate repeated requests remain separate. Adapter upgrades rewind the selected transcript once and backfill in bounded passes, preserving existing archive identifiers, checkpoints and pause state. A fully read log with no supported user records is reported as unverified rather than successfully preserved.

Use [context handoff](../skills/context-handoff/SKILL.md) to save a critical task checkpoint or explicitly requested long-term project fact. Storage is outside project/cache trees and isolated by project/chat; no native global memory is edited. Local archival is not promotion of all historical requests into permanent user preferences.

## References adapted

The implementation is original KH code. Architectural references were inspected, not installed or executed: [ECC d2ef268](https://github.com/affaan-m/ECC/tree/d2ef2680594f9a17526a6e1a2e18b3d242c5d17b) for bounded hook dispatch, state isolation and negative controls; [OpenClaw flush plan](https://github.com/openclaw/openclaw/blob/main/extensions/memory-core/src/flush-plan.ts) for preservation before compaction and original-file protection; [Hermes memory](https://github.com/NousResearch/hermes-agent/blob/main/tools/memory_tool.py) for explicit bounded persistent entries and session-start snapshots. KH does not import their model-calling summarizers, continuous-learning daemons, unrelated MCP probes or generic style policies.

Verification must distinguish local event replay, a real host firing registered hooks, and actual model source/audit behavior. Unit passes or a saved checkpoint alone establish neither host invocation nor complete model compliance.
