import csv
import os
from typing import Any, Dict, List

from src.orchestration.artifacts import build_design_stage
from src.skills.license_checker import check_license
from src.skills.pattern_analyzer import analyze_design_pattern


class SystemArchitect:
    """Generate a functional specification CSV and a compact architecture document."""

    def __init__(self, project_dir: str, llm_router=None):
        self.project_dir = project_dir
        self.llm = llm_router

    def _generate_functional_spec(self, requirements: str) -> str:
        """Ask the configured LLM for CSV content and save it as functional_spec.csv."""
        if not self.llm:
            csv_data = "ID,Category,Feature,Description\nF-001,General,Requested work," + _csv_escape(requirements)
        else:
            system_prompt = "You are an IT service planner and system architect."
            user_prompt = f"""
Analyze the user's requirements and write a detailed functional specification.
Return only CSV content, optionally inside a Markdown csv code block.
The first row must be: ID,Category,Feature,Description
Quote fields when a comma appears inside a value.

[Requirements]
{requirements}
"""
            response = self.llm.chat(system_prompt, user_prompt)
            csv_data = _extract_csv_block(response)

        csv_path = os.path.join(self.project_dir, "functional_spec.csv")
        os.makedirs(self.project_dir, exist_ok=True)
        with open(csv_path, "w", encoding="utf-8-sig", newline="") as handle:
            handle.write(csv_data)
        return f"Functional specification CSV exported: {csv_path}\n\n[Summary]\n{csv_data}"

    def draft_architecture(self, requirements: str, framework: str, libraries: list, scale: str = "large") -> str:
        """Create a Markdown architecture document from requirements, pattern advice, and license checks."""
        doc_path = os.path.join(self.project_dir, "design_doc.md")
        os.makedirs(self.project_dir, exist_ok=True)

        functional_spec_text = self._generate_functional_spec(requirements)
        pattern_strategy = analyze_design_pattern.__skill_meta__.execute(
            framework=framework,
            project_scale=scale,
            maintainability_priority="high",
        )
        license_reports = [
            check_license.__skill_meta__.execute(package_name=library, registry="pypi")
            for library in libraries
        ]

        design_doc = f"""# System Architecture and Functional Specification

## 1. Requirements and Functional Specification
{functional_spec_text}

## 2. Architecture and Design Pattern Policy
{pattern_strategy}

## 3. External Library License Review
{chr(10).join(license_reports) if license_reports else "No external libraries were requested."}

## 4. Developer Agent Guidance
- Follow the architecture design and functional specification.
- Replace libraries that have incompatible licensing or unresolved policy risk.
- Keep business logic separated for maintainability and testing.
"""

        with open(doc_path, "w", encoding="utf-8") as handle:
            handle.write(design_doc)
        return doc_path


def run_architect_pipeline(
    project_dir: str,
    requirements: str,
    framework: str = "generic",
    libraries: List[str] = None,
    scale: str = "large",
    metadata: Dict[str, Any] = None,
    llm_router=None,
) -> Dict[str, Any]:
    """Run the architect pipeline and return design, domain, export, and quality evidence."""
    os.makedirs(project_dir, exist_ok=True)
    architect = SystemArchitect(project_dir, llm_router=llm_router)
    design_doc_path = architect.draft_architecture(
        requirements=requirements,
        framework=framework,
        libraries=list(libraries or []),
        scale=scale,
    )
    with open(design_doc_path, "r", encoding="utf-8") as handle:
        design_doc = handle.read()

    stage_metadata = dict(metadata or {})
    stage_metadata.setdefault("scope", requirements)
    design_stage = build_design_stage(
        project_dir=project_dir,
        workflow_id=str(stage_metadata.get("workflow_id", "architect_pipeline")),
        design_doc=design_doc,
        file_list=list(stage_metadata.get("target_files", [])),
        metadata=stage_metadata,
    )
    return {
        "design_doc_path": design_doc_path,
        "design_doc": design_doc,
        "domain_profile": design_stage.get("domain_profile", {}),
        "work_design": design_stage.get("work_design", {}),
        "manifest": design_stage.get("manifest", {}),
        "deliverable_exports": design_stage.get("deliverable_exports", {}),
        "quality": design_stage.get("deliverable_exports", {}).get("quality", {}),
        "evidence": list(design_stage.get("evidence", [])),
    }


def _extract_csv_block(response: str) -> str:
    text = (response or "").strip()
    if "```csv" in text:
        return text.split("```csv", 1)[1].split("```", 1)[0].strip()
    if "```" in text:
        return text.split("```", 1)[1].split("```", 1)[0].strip()
    return text


def _csv_escape(value: str) -> str:
    escaped = str(value).replace('"', '""')
    return f'"{escaped}"'
