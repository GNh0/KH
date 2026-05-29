import re
import textwrap
from typing import Any, Dict, Iterable, List

from src.skills.base import agent_skill


@agent_skill(
    name="should_distill_workflow",
    description="Decide whether a repeated workflow is worth turning into a reusable UAF skill.",
)
def should_distill_workflow(
    trigger: str,
    repeated_count: int = 1,
    reusable_across_projects: bool = False,
    has_clear_failure_modes: bool = False,
) -> Dict[str, Any]:
    reasons: List[str] = []
    if repeated_count < 2:
        reasons.append("one-off workflow has not repeated enough")
    if not reusable_across_projects:
        reasons.append("workflow is not reusable across projects")
    if not has_clear_failure_modes:
        reasons.append("failure modes are not clear enough to teach")
    if not (trigger or "").strip().lower().startswith("use when"):
        reasons.append("trigger should start with 'Use when'")

    should_distill = not reasons
    return {
        "should_distill": should_distill,
        "quality_gate": "candidate" if should_distill else "reject",
        "reasons": reasons or ["repeatable workflow with clear trigger and failure modes"],
    }


@agent_skill(
    name="build_skill_scaffold",
    description="Build a portable UAF skill scaffold from a trigger, workflow steps, and implementation targets.",
)
def build_skill_scaffold(
    name: str,
    trigger: str,
    workflow_steps: Iterable[str],
    implementation_targets: Iterable[str],
    execution_level: str = "procedure-policy",
) -> Dict[str, str]:
    skill_name = _normalize_skill_name(name)
    trigger = _normalize_trigger(trigger)
    steps = [step.strip().rstrip(".") for step in workflow_steps if step and step.strip()]
    targets = [target.strip() for target in implementation_targets if target and target.strip()]
    if not steps:
        steps = ["Confirm the trigger applies", "Run the workflow", "Record evidence"]
    if not targets:
        targets = ["skills/<skill-name>/SKILL.md"]

    execution_level = execution_level if execution_level in {"python-module", "hybrid-harness", "procedure-policy"} else "procedure-policy"
    return {
        "SKILL.md": _render_skill_md(skill_name, trigger, steps, targets),
        "references/usage.md": _render_usage(skill_name, trigger, steps, targets, execution_level),
        "examples/minimal-workflow.md": _render_example(skill_name, steps, targets, execution_level),
        "scripts/smoke_check.py": _render_smoke_check(skill_name, targets),
    }


def _normalize_skill_name(name: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9-]+", "-", (name or "").strip().lower()).strip("-")
    return value or "new-uaf-skill"


def _normalize_trigger(trigger: str) -> str:
    value = (trigger or "").strip()
    if value.lower().startswith("use when"):
        return value
    return f"Use when {value[:1].lower()}{value[1:]}" if value else "Use when a repeatable UAF workflow needs a packaged skill."


def _render_skill_md(name: str, trigger: str, steps: List[str], targets: List[str]) -> str:
    step_lines = "\n".join(f"{index}. {step}." for index, step in enumerate(steps, 1))
    target_lines = "\n".join(f"- `{target}`" for target in targets)
    return textwrap.dedent(f"""\
        ---
        name: {name}
        description: {trigger}
        ---

        # {name}

        This skill captures a repeatable UAF workflow as a host-readable skill.

        ## Support files

        - Read `references/usage.md` before applying this skill to real work.
        - Use `examples/minimal-workflow.md` to verify the expected scenario and evidence.
        - Run `python scripts/smoke_check.py` from this skill folder before publishing.

        ## Workflow

        {step_lines}

        ## Required outputs

        - Decision that the trigger applies.
        - Workflow evidence and failure handling notes.
        - Verification command or review result.

        ## Common mistakes

        - Do not create a skill for a one-off story.
        - Do not hide operational steps in README-only text.
        - Do not claim the skill ran unless its workflow evidence exists.

        ## UAF implementation targets

        {target_lines}
        """).strip() + "\n"


def _render_usage(name: str, trigger: str, steps: List[str], targets: List[str], execution_level: str) -> str:
    step_lines = "\n".join(f"{index}. {step}." for index, step in enumerate(steps, 1))
    target_lines = "\n".join(f"  - `{target}`" for target in targets)
    return textwrap.dedent(f"""\
        # {name} Usage Reference

        ## When to use

        {trigger}

        ## Inputs to collect

        - Trigger condition and workflow boundary.
        - User-facing outputs and internal evidence paths.
        - Execution level: `{execution_level}`.
        - Implementation targets:
        {target_lines}

        ## Execution pattern

        {step_lines}

        ## Evidence to produce

        - Skill name and execution level.
        - Inputs used and output files produced.
        - Verification result and remaining gaps.

        ## Failure handling

        - Stop if the trigger does not apply.
        - Withhold completion if expected evidence is missing.
        - Record blocked reasons when required inputs are unavailable.

        ## Quality bar

        A valid use must let another agent reproduce why the skill applied, what ran, what evidence was produced, and what remains unfinished.
        """).strip() + "\n"


def _render_example(name: str, steps: List[str], targets: List[str], execution_level: str) -> str:
    step_lines = "\n".join(f"{index}. {step}." for index, step in enumerate(steps, 1))
    target_lines = "\n".join(f"  - `{target}`" for target in targets)
    return textwrap.dedent(f"""\
        # {name} Minimal Workflow Example

        ## Scenario

        A repeated workflow has a clear trigger and needs to be captured as a reusable UAF skill.

        ## Expected steps

        {step_lines}

        ## Expected evidence

        - `actual_runtime_path`: `skills/{name}/SKILL.md`
        - `execution_level`: `{execution_level}`
        - Implementation targets:
        {target_lines}

        ## Failure cases

        - The workflow is one-off and should not become a skill.
        - The trigger is too vague for discovery.
        - Support files are not referenced from `SKILL.md`.

        ## Done criteria

        - `SKILL.md` has trigger-focused frontmatter.
        - Support files are wired and smoke checked.
        - Catalog validation passes.
        """).strip() + "\n"


def _render_smoke_check(name: str, targets: List[str]) -> str:
    target_repr = "[" + ", ".join(repr(target) for target in targets) + "]"
    return textwrap.dedent(f"""\
        import importlib
        import os
        import sys
        from pathlib import Path

        SKILL_NAME = {name!r}
        REQUIRED_SUPPORT_FILES = [
            "references/usage.md",
            "examples/minimal-workflow.md",
            "scripts/smoke_check.py",
        ]
        IMPLEMENTATION_TARGETS_PATTERN = "## UAF implementation targets"
        IMPLEMENTATION_TARGETS = {target_repr}


        def find_repo_root(skill_root):
            env_root = os.environ.get("UAF_REPO_ROOT", "")
            if env_root:
                candidate = Path(env_root).resolve()
                if (candidate / "src").is_dir() and (candidate / "skills").is_dir():
                    return candidate
            candidates = list(skill_root.parents) + [Path.cwd(), *Path.cwd().parents]
            for candidate in candidates:
                if (candidate / "src").is_dir() and (candidate / "skills").is_dir():
                    return candidate
            return None


        def resolve_target(ref):
            repo_root = find_repo_root(Path(__file__).resolve().parents[1])
            if "<" in ref or ">" in ref:
                return True
            if ref.startswith("skills/"):
                return bool(repo_root and (repo_root / ref).exists())
            if not ref.startswith(("src.", "tests.")):
                return bool(ref)
            if repo_root and str(repo_root) not in sys.path:
                sys.path.insert(0, str(repo_root))
            parts = ref.split(".")
            for index in range(len(parts), 0, -1):
                module_name = ".".join(parts[:index])
                try:
                    module = importlib.import_module(module_name)
                except ModuleNotFoundError:
                    continue
                current = module
                for attr in parts[index:]:
                    if not hasattr(current, attr):
                        return False
                    current = getattr(current, attr)
                return True
            return False


        def main():
            root = Path(__file__).resolve().parents[1]
            assert (root / "SKILL.md").exists(), "missing SKILL.md"
            for rel_path in REQUIRED_SUPPORT_FILES:
                assert (root / rel_path).exists(), f"missing {{rel_path}}"
            content = (root / "SKILL.md").read_text(encoding="utf-8")
            assert IMPLEMENTATION_TARGETS_PATTERN in content
            for target in IMPLEMENTATION_TARGETS:
                assert resolve_target(target), f"unresolved {{target}}"
            print(f"{{SKILL_NAME}} smoke_check ok")


        if __name__ == "__main__":
            main()
        """).strip() + "\n"
