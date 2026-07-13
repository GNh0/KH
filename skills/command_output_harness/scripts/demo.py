import argparse
import json
import sys
from pathlib import Path


SKILL_NAME = "command-output-harness"
REQUIRED_TOKEN_USAGE_FIELDS = (
    "estimated_payload_tokens_before",
    "estimated_payload_tokens_after",
    "estimated_payload_tokens_saved",
    "estimated_payload_token_savings_ratio",
    "billing_tokens_available",
    "billing_counterfactual_available",
)
REQUIRED_SPECIFICITY_FIELDS = (
    "skill",
    "scenario_id",
    "scenario_function",
    "profile",
    "skill_specific_probe",
    "unique_markers",
)


def _repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in current.parents:
        if (parent / "src").is_dir() and (parent / "skills").is_dir():
            return parent
    raise RuntimeError("repository root not found")


def _contract_errors(payload, expected_skill_name):
    errors = []
    usage = payload.get("success_case", {}).get("payload", {}).get("metadata", {}).get("token_usage", {})
    missing = [field for field in REQUIRED_TOKEN_USAGE_FIELDS if field not in usage]
    if missing:
        errors.append(f"missing required token demo fields: {', '.join(missing)}")
    else:
        before = usage["estimated_payload_tokens_before"]
        after = usage["estimated_payload_tokens_after"]
        saved = usage["estimated_payload_tokens_saved"]
        ratio = usage["estimated_payload_token_savings_ratio"]
        if not all(isinstance(value, int) and not isinstance(value, bool) for value in [before, after, saved]):
            errors.append("canonical token demo counts must be integers")
        elif before - after != saved or saved <= 0:
            errors.append("canonical token demo counts must report a positive consistent delta")
        if not isinstance(ratio, (int, float)) or isinstance(ratio, bool) or not 0 < ratio <= 1:
            errors.append("estimated_payload_token_savings_ratio must be between zero and one")
        if usage["billing_tokens_available"] is not False:
            errors.append("billing_tokens_available must remain false")
        if usage["billing_counterfactual_available"] is not False:
            errors.append("billing_counterfactual_available must remain false")

    specificity = payload.get("demo_specificity", {})
    missing_specificity = [field for field in REQUIRED_SPECIFICITY_FIELDS if field not in specificity]
    if missing_specificity:
        errors.append(f"missing required demo_specificity fields: {', '.join(missing_specificity)}")
    else:
        scenario_id = payload.get("scenario_id", "")
        profile = specificity.get("profile", {})
        semantic_probe = profile.get("semantic_probe", "") if isinstance(profile, dict) else ""
        unique_markers = specificity.get("unique_markers", [])
        if specificity.get("skill") != expected_skill_name:
            errors.append("demo_specificity skill mismatch")
        if specificity.get("scenario_id") != scenario_id:
            errors.append("demo_specificity scenario mismatch")
        if not str(specificity.get("scenario_function", "")).endswith("_scenario"):
            errors.append("demo_specificity scenario_function invalid")
        if not isinstance(unique_markers, list) or any(
            marker not in unique_markers for marker in [expected_skill_name, scenario_id, semantic_probe]
        ):
            errors.append("demo_specificity unique_markers incomplete")
    return errors


def main(default_skill_name=SKILL_NAME, argv=None) -> int:
    if default_skill_name != SKILL_NAME:
        print(f"demo skill mismatch: expected {SKILL_NAME}, got {default_skill_name}", file=sys.stderr)
        return 2
    sys.path.insert(0, str(_repo_root()))
    from src.skills.demo_scenarios import run_skill_demo

    parser = argparse.ArgumentParser(description=f"Run the {SKILL_NAME} demo.")
    parser.add_argument("--output-dir", default="")
    parser.add_argument("--host", default="local", choices=["local", "codex", "antigravity-style", "claude-code"])
    args = parser.parse_args(argv)
    output_dir = Path(args.output_dir) if args.output_dir else Path.cwd() / ".kh-demo" / SKILL_NAME
    payload = run_skill_demo(SKILL_NAME, output_dir=output_dir, repo_root=_repo_root(), host=args.host)
    errors = _contract_errors(payload, SKILL_NAME)
    if errors:
        print("; ".join(errors), file=sys.stderr)
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(SKILL_NAME))
