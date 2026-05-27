import argparse
import json
import os
import sys
from typing import Any, Dict, List

from src.skills.base import agent_skill
from src.skills.uaf_skill_validator import validate_skill_folders


if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
    sys.stdout.reconfigure(encoding="utf-8")


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PACKAGED_SKILLS_DIR = os.path.join(PROJECT_ROOT, "skills")

DESIGN_REFERENCES_CONSIDERED = {
    "design_references_considered": [
        "Gemini plugin skill-folder conventions",
        "Google Antigravity agent and orchestration patterns",
        "Personal skillbook planning, TDD, verification, and parallel dispatch workflows",
        "Command-operation reusable task and harness patterns",
    ],
    "runtime_rule": "Do not scan or require external skill or host installations at runtime.",
}


def parse_frontmatter(file_path: str, fallback_name: str) -> Dict[str, str]:
    name = fallback_name.replace("_", "-")
    description = ""

    with open(file_path, "r", encoding="utf-8") as handle:
        lines = handle.readlines()

    if not lines or lines[0].strip() != "---":
        return {"name": name, "description": description}

    frontmatter: List[str] = []
    for line in lines[1:]:
        if line.strip() == "---":
            break
        frontmatter.append(line.rstrip("\n"))

    index = 0
    while index < len(frontmatter):
        line = frontmatter[index]
        if line.startswith("name:"):
            name = line.split("name:", 1)[1].strip().strip('"')
        elif line.startswith("description:"):
            value = line.split("description:", 1)[1].strip()
            if value in {">", ">-", "|", "|-"}:
                desc_lines = []
                index += 1
                while index < len(frontmatter):
                    next_line = frontmatter[index]
                    if next_line and not next_line.startswith(" "):
                        index -= 1
                        break
                    desc_lines.append(next_line.strip())
                    index += 1
                description = " ".join(line for line in desc_lines if line).strip()
            else:
                description = value.strip('"')
        index += 1

    return {"name": name, "description": description}


def _scan_skill_folders(skills_dir: str = PACKAGED_SKILLS_DIR, include_path: bool = False) -> List[Dict[str, Any]]:
    if not skills_dir or not os.path.isdir(skills_dir):
        return []

    skills: List[Dict[str, Any]] = []
    for folder_name in sorted(os.listdir(skills_dir)):
        folder_path = os.path.join(skills_dir, folder_name)
        skill_path = os.path.join(folder_path, "SKILL.md")
        if not os.path.isdir(folder_path) or not os.path.isfile(skill_path):
            continue

        metadata = parse_frontmatter(skill_path, folder_name)
        entry: Dict[str, Any] = {
            "name": metadata["name"],
            "description": metadata["description"],
            "source": "uaf_skill_folder",
            "relative_path": f"{folder_name}/SKILL.md",
            "packaged": True,
            "external_runtime_dependency": False,
        }
        if include_path:
            entry["path"] = skill_path
        skills.append(entry)

    return sorted(skills, key=lambda skill: skill["name"])


def collect_packaged_skills(skills_dir: str = PACKAGED_SKILLS_DIR) -> Dict[str, Any]:
    """Return packaged UAF skills and harnesses from skills/<name>/SKILL.md folders."""
    skills = _scan_skill_folders(skills_dir)
    validation = validate_skill_folders(skills_dir)
    return {
        "external_runtime_dependency": False,
        "packaged_skill_folder_available": bool(skills),
        "total_skills_found": len(skills),
        "references_considered": DESIGN_REFERENCES_CONSIDERED,
        "validation": validation.to_dict(),
        "skills": skills,
    }


def read_packaged_skill(skill_name: str, skills_dir: str = PACKAGED_SKILLS_DIR) -> str:
    """Read a packaged UAF skill by frontmatter name."""
    for skill in _scan_skill_folders(skills_dir, include_path=True):
        if skill["name"] != skill_name:
            continue
        with open(skill["path"], "r", encoding="utf-8") as handle:
            content = handle.read()
        return "\n".join([
            "Packaged source: uaf_skill_folder",
            f"Relative path: {skill['relative_path']}",
            "External runtime dependency: false",
            "",
            content,
        ])
    return f"Packaged UAF skill '{skill_name}' not found."


@agent_skill(
    name="list_uaf_skills",
    description="List packaged UAF skill and harness folders.",
)
def list_uaf_skills() -> str:
    return json.dumps(collect_packaged_skills(), ensure_ascii=False)


@agent_skill(
    name="read_uaf_skill",
    description="Read a packaged UAF skill or harness by frontmatter name.",
)
def read_uaf_skill(name: str) -> str:
    return read_packaged_skill(name)


def list_skills() -> None:
    print(json.dumps(collect_packaged_skills(), indent=2, ensure_ascii=False))


def read_skill(skill_name: str) -> None:
    print(read_packaged_skill(skill_name))


def check_skills(skills_dir: str = PACKAGED_SKILLS_DIR) -> int:
    report = validate_skill_folders(skills_dir)
    print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    return 0 if report.success else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="List or read packaged UAF skill and harness folders."
    )
    parser.add_argument("--list", action="store_true", help="List packaged UAF skills in JSON format")
    parser.add_argument("--read", type=str, help="Read a packaged UAF skill by name")
    parser.add_argument("--check", action="store_true", help="Validate packaged UAF skill folders and exit non-zero on errors")
    args = parser.parse_args()

    if args.list:
        list_skills()
    elif args.read:
        read_skill(args.read)
    elif args.check:
        sys.exit(check_skills())
    else:
        parser.print_help()
