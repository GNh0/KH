import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKAGED_SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")

NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PLACEHOLDER_PATTERN = re.compile(r"\{\{[^{}]+\}\}")
BEHAVIOR_SECTION_PATTERN = re.compile(
    r"^##\s+(Workflow|Instructions|Core Flow|Command lifecycle|Hook workflow|Add a skill|Required default roles)\b",
    re.IGNORECASE | re.MULTILINE,
)
REQUIRED_OUTPUTS_PATTERN = re.compile(r"^##\s+Required outputs\b", re.IGNORECASE | re.MULTILINE)
COMMON_MISTAKES_PATTERN = re.compile(r"^##\s+Common mistakes\b", re.IGNORECASE | re.MULTILINE)
KH_ENTRY_CONTRACT_PATTERN = re.compile(r"^##\s+KH Entry Contract\b", re.IGNORECASE | re.MULTILINE)


@dataclass
class SkillValidationIssue:
    code: str
    message: str
    relative_path: str
    skill_name: str = ""
    severity: str = "error"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "relative_path": self.relative_path,
            "skill_name": self.skill_name,
            "severity": self.severity,
        }


@dataclass
class SkillValidationResult:
    name: str
    relative_path: str
    valid: bool = True
    description: str = ""
    issues: List[SkillValidationIssue] = field(default_factory=list)

    def add_issue(self, code: str, message: str, severity: str = "error") -> None:
        self.valid = False
        self.issues.append(
            SkillValidationIssue(
                code=code,
                message=message,
                relative_path=self.relative_path,
                skill_name=self.name,
                severity=severity,
            )
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "relative_path": self.relative_path,
            "valid": self.valid,
            "description": self.description,
            "issues": [issue.to_dict() for issue in self.issues],
        }


@dataclass
class SkillCatalogValidationReport:
    success: bool
    total_skills: int
    valid_skills: int
    invalid_skills: int
    results: List[SkillValidationResult] = field(default_factory=list)
    issues: List[SkillValidationIssue] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "total_skills": self.total_skills,
            "valid_skills": self.valid_skills,
            "invalid_skills": self.invalid_skills,
            "issues": [issue.to_dict() for issue in self.issues],
            "results": [result.to_dict() for result in self.results],
        }


def _relative_skill_path(skills_dir: str, skill_path: str) -> str:
    return os.path.relpath(skill_path, skills_dir).replace(os.sep, "/")


def parse_skill_frontmatter(content: str) -> Optional[Dict[str, str]]:
    if not content.startswith("---\n"):
        return None

    end_index = content.find("\n---", 4)
    if end_index == -1:
        return None

    frontmatter = content[4:end_index]
    metadata = {"name": "", "description": ""}
    lines = frontmatter.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]
        if line.startswith("name:"):
            metadata["name"] = line.split("name:", 1)[1].strip().strip('"')
        elif line.startswith("description:"):
            value = line.split("description:", 1)[1].strip()
            if value in {">", ">-", "|", "|-"}:
                desc_lines: List[str] = []
                index += 1
                while index < len(lines):
                    next_line = lines[index]
                    if next_line and not next_line.startswith(" "):
                        index -= 1
                        break
                    desc_lines.append(next_line.strip())
                    index += 1
                metadata["description"] = " ".join(line for line in desc_lines if line).strip()
            else:
                metadata["description"] = value.strip('"')
        index += 1

    return metadata


def validate_skill_file(skills_dir: str, folder_name: str, skill_path: str) -> SkillValidationResult:
    relative_path = _relative_skill_path(skills_dir, skill_path)

    with open(skill_path, "r", encoding="utf-8") as handle:
        content = handle.read()

    metadata = parse_skill_frontmatter(content)
    result = SkillValidationResult(
        name=(metadata or {}).get("name", folder_name.replace("_", "-")),
        description=(metadata or {}).get("description", ""),
        relative_path=relative_path,
    )

    if metadata is None:
        result.add_issue("missing_frontmatter", "SKILL.md must start with YAML-style frontmatter.")
        return result

    if not result.name:
        result.add_issue("missing_name", "Frontmatter must include a non-empty name.")
    elif not NAME_PATTERN.match(result.name):
        result.add_issue(
            "invalid_name_format",
            "Skill name must use lowercase letters, numbers, and hyphens.",
        )

    if not result.description:
        result.add_issue("missing_description", "Frontmatter must include a non-empty description.")
    elif not result.description.startswith("Use when "):
        result.add_issue(
            "description_not_trigger_focused",
            "Frontmatter description must start with 'Use when ' and describe trigger conditions.",
        )

    if not re.search(r"^#\s+\S", content, re.MULTILINE):
        result.add_issue("missing_h1", "Skill body must include an H1 heading.")

    if not BEHAVIOR_SECTION_PATTERN.search(content):
        result.add_issue(
            "missing_behavior_section",
            "Skill body must include a behavior section such as Workflow, Instructions, Core Flow, or equivalent.",
        )

    if not KH_ENTRY_CONTRACT_PATTERN.search(content):
        result.add_issue(
            "missing_kh_entry_contract",
            "Skill body must include a '## KH Entry Contract' section that separates routing, selection, and execution evidence.",
        )

    if "## UAF implementation targets" not in content:
        result.add_issue(
            "missing_uaf_targets",
            "Skill body must include a '## UAF implementation targets' section.",
        )

    if not REQUIRED_OUTPUTS_PATTERN.search(content):
        result.add_issue(
            "missing_required_outputs",
            "Skill body must include a '## Required outputs' section.",
        )

    if not COMMON_MISTAKES_PATTERN.search(content):
        result.add_issue(
            "missing_common_mistakes",
            "Skill body must include a '## Common mistakes' section.",
        )

    if PLACEHOLDER_PATTERN.search(content):
        result.add_issue(
            "unresolved_placeholder",
            "Skill body contains an unresolved template placeholder.",
        )

    return result


def validate_skill_folders(skills_dir: str = PACKAGED_SKILLS_DIR) -> SkillCatalogValidationReport:
    if not skills_dir or not os.path.isdir(skills_dir):
        return SkillCatalogValidationReport(
            success=True,
            total_skills=0,
            valid_skills=0,
            invalid_skills=0,
        )

    results: List[SkillValidationResult] = []
    name_to_results: Dict[str, List[SkillValidationResult]] = {}

    for folder_name in sorted(os.listdir(skills_dir)):
        folder_path = os.path.join(skills_dir, folder_name)
        skill_path = os.path.join(folder_path, "SKILL.md")
        if not os.path.isdir(folder_path) or not os.path.isfile(skill_path):
            continue

        result = validate_skill_file(skills_dir, folder_name, skill_path)
        results.append(result)
        if result.name:
            name_to_results.setdefault(result.name, []).append(result)

    for name, matching_results in name_to_results.items():
        if len(matching_results) <= 1:
            continue
        for result in matching_results:
            result.add_issue(
                "duplicate_name",
                f"Skill name '{name}' appears in {len(matching_results)} skill folders.",
            )

    issues = [
        issue
        for result in results
        for issue in result.issues
    ]
    valid_skills = sum(1 for result in results if result.valid)
    invalid_skills = len(results) - valid_skills

    return SkillCatalogValidationReport(
        success=not issues,
        total_skills=len(results),
        valid_skills=valid_skills,
        invalid_skills=invalid_skills,
        results=sorted(results, key=lambda result: result.name),
        issues=issues,
    )
