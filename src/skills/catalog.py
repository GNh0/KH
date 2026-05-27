import importlib
from typing import Dict, List

from src.skills.base import SKILL_REGISTRY


BUILTIN_SKILL_MODULES = [
    "src.skills.file_ops",
    "src.skills.license_checker",
    "src.skills.pattern_analyzer",
    "src.skills.token_optimizer",
    "src.skills.antigravity_bridge",
]


def load_builtin_skills() -> List[Dict[str, str]]:
    for module_name in BUILTIN_SKILL_MODULES:
        importlib.import_module(module_name)
    return list_registered_skills()


def list_registered_skills() -> List[Dict[str, str]]:
    skills = []
    for name, skill in sorted(SKILL_REGISTRY.items()):
        skills.append({
            "name": name,
            "description": skill.description,
        })
    return skills
