---
name: architect-pipeline
description: Use when designing an application, system, or codebase before implementation requires an architecture blueprint.
---
# Architect Pipeline Skill

This skill uses the Universal Agent Framework's architect module to generate a robust blueprint.

## Instructions
When the user asks you to build an application, design a system, or write a codebase, you MUST follow these steps:
1. Run the architect pipeline using the terminal:
   `python -m src.core.runner --mode architect --project_dir ./workspace --reqs "<User Requirement>" --framework "<Framework Name>"`
2. Read the generated `./workspace/design_doc.md` file carefully.
3. **Parallel Dispatching Note**: The `design_doc.md` must clearly outline all the files that need to be generated. The Orchestrator will parse these files and dispatch multiple parallel Coder agents to build them simultaneously.
4. Follow the exact design patterns, architectures, and library recommendations written in `design_doc.md` when writing your code.
5. If there are license warnings for libraries, do NOT use them and find alternatives.

## UAF implementation targets

- `src.core.architect.SystemArchitect`
- `src.core.runner`
- `src.orchestration.agent_loop`
- `src.skills.pattern_analyzer`
- `src.skills.license_checker`
