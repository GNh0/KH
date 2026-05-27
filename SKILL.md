---
name: universal-agent-framework
description: "A pure-local, highly concurrent, and sandboxed AI coding orchestration framework. Use this skill when the user asks to orchestrate a complex coding project or when you need to parallelize multiple file generations."
---

# Universal Agent Framework (UAF)

This is a local-first, zero-dependency, and hyper-concurrent agentic coding framework. It uses a Pure Python `asyncio` architecture to bypass traditional broker limits and can safely test Python code on Windows via `multiprocessing`-based sandboxing.

## Requirements
- Python 3.9+
- OS: Windows / Linux / macOS
- Dependencies: `uvicorn`, `fastapi`, `httpx` (installed via pip)

## Execution via CLI
Do NOT run internal scripts directly. Always use the built-in `cli.py` orchestrator. The CLI handles background server launching, smart polling, and process garbage collection automatically.

### Commands

**1. Run a Complete Workflow**
To initialize the orchestrator and generate code for a project:
```bash
python cli.py run --project "./my_project_dir" --prompt "Create a scalable FastAPI backend"
```

**2. Advanced Overrides**
You can pass additional arguments to control the environment:
- `--workers <int>`: Cap the concurrent workers (Default: 50). The framework will auto-clamp this to safe limits based on CPU cores.
- `--no-sandbox`: Bypass AST and timeout checks for debugging.
- `--verbose`: Enable debug logging for the webhook server.

Example:
```bash
python cli.py run --project "./my_game" --prompt "Create a simple python snake game" --workers 100 --verbose
```

## Internal Architecture
If you need to extend or debug this framework, here is the structure:
- **`src/contracts.py`**: Shared contracts for Codex, Antigravity, Claude Code, and local adapters (`HarnessResult`, `SkillManifest`, `AdapterRequest`, `AdapterResult`).
- **`cli.py`**: The main entry point. Orchestrates the Server + Agent Loop.
- **`src/orchestration/agent_loop.py`**: The central loop (Architect -> Dispatcher -> Evaluator).
- **`src/orchestration/roles.py`**: Default UAF role graph (`ceo`, `advisor`, `system-architect`, `controller`, `implementer`, reviewers, QA, security, release).
- **`src/tasks/workflows.py`**: The `asyncio` queue-based worker engine. Replaces Celery.
- **`src/harness/sandbox.py`**: A secure code runner. Uses `multiprocessing` for absolute timeout guarantees on Windows.
- **`src/core/snapshot_manager.py`**: State rollback system utilizing pure `gzip` for 90% disk space reduction.
- **`src/api/server.py`**: A FastAPI webhook receiver using `aiosqlite` with WAL mode.
- **`skills/`**: Packaged UAF-native skill and harness catalog. Add a new skill by creating `skills/<skill-folder>/SKILL.md`.

## Integration Contracts
External agents should exchange structured data through the contracts module instead of ad-hoc dictionaries:
- Use `HarnessResult` for sandbox/evaluator execution results.
- Use `SkillManifest` to normalize plugin and skill metadata.
- Use `AdapterRequest` and `AdapterResult` when implementing Codex, Antigravity, Claude Code, or local dispatch adapters.
- Add new UAF skills and harnesses as `skills/<skill-name>/SKILL.md`. The packaged skill folder is the source of truth.
- Use `src.skills.uaf_skill_catalog` to list/read packaged UAF skill folders. External Gemini, Antigravity, RTK, and Superpowers systems are development references only, not runtime dependencies.

## Packaged Harnesses
- **Core role graph**: `orchestration-role-graph` for CEO, advisor, product strategy, development architect, planner, controller, implementer, review, QA, security, and release roles.
- **Antigravity-derived**: `antigravity-agent-orchestration` for agent profiles, subagents, tool permissions, lifecycle hooks, error recovery, and observability.
- **Superpowers-derived**: `development-lifecycle-harness`, `subagent-review-pipeline`, and `quality-gates-harness` for planning, TDD, review roles, debugging, and evidence-based completion.
- **RTK-derived**: `rtk-command-output-harness` and `command-hook-policy-harness` for compact command output, exit-code preservation, token-savings tracking, hook trust, and permission precedence.

## Security Constraints
When utilizing this framework, remember that the sandbox enforces strict checks via AST parsing. If you are generating AI code that requires `os`, `sys`, or `subprocess`, the framework will intentionally block it unless you run it with `--no-sandbox`. 
