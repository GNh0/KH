import json
import re
import urllib.error
import urllib.request

from src.skills.base import agent_skill


@agent_skill(
    name="check_license",
    description="Check a package license from PyPI or a mock internal registry path.",
)
def check_license(package_name: str, registry: str = "pypi") -> str:
    """Fetch package metadata and return a compact license compatibility note."""
    if not re.match(r"^[a-zA-Z0-9_-]+$", package_name):
        return "Security Error: invalid package name. Only letters, numbers, underscore, and hyphen are allowed."

    try:
        if registry.lower() == "pypi":
            url = f"https://pypi.org/pypi/{package_name}/json"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as response:
                data = json.loads(response.read().decode())
                license_info = data.get("info", {}).get("license", "Unknown")
                return (
                    f"[{package_name}] License: {license_info}. "
                    "Review commercial use and maintenance compatibility before adoption."
                )
        return f"Mock: [{package_name}] in {registry} - MIT License"
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            return f"Error: package not found: {package_name}"
        return f"HTTP Error fetching license: {exc}"
    except Exception as exc:
        return f"Error fetching license for {package_name}: {exc}"
