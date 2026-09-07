"""Create a reviewable, scoped profile from explicitly supplied settings."""
from pathlib import Path
from src.common.files import read_file, write_output
from src.common.results import CheckResult, Issue
import json


def validate_profile(profile: dict) -> CheckResult:
    result = CheckResult(checked=['profile structure and declared scope'],
                         not_checked=['agreement with target project source', 'runtime API availability'])
    if not isinstance(profile, dict):
        return CheckResult(issues=[Issue('profile_not_object', 'error', 'A profile must be a JSON object.')])
    for key in ('name', 'scope', 'defaults'):
        if not profile.get(key):
            result.issues.append(Issue('profile_field_missing', 'error', 'A named, scoped profile with explicit defaults is required.', details={'field': key}))
    if not isinstance(profile.get('scope'), dict) or not isinstance(profile.get('defaults'), dict):
        result.issues.append(Issue('profile_mapping_required', 'error', 'scope and defaults must be JSON objects.'))
    return result


def write_profile(profile: dict, destination: str | Path, *, expected_sha256=None) -> Path:
    """Explicit caller-controlled output; no author search, source edits or install."""
    result = validate_profile(profile)
    if not result.success:
        raise ValueError(result.to_json())
    return write_output(destination, (json.dumps(profile, ensure_ascii=False, indent=2) + '\n').encode('utf-8'), expected_sha256=expected_sha256)


def read_profile(path: str | Path) -> dict:
    profile = json.loads(read_file(path).text())
    result = validate_profile(profile)
    if not result.success:
        raise ValueError(result.to_json())
    return profile
