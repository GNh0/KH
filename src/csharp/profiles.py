"""Scoped style data; a profile is not a replacement for the target source."""
import json
from pathlib import Path


def load_profile(path: str | Path | None = None) -> dict:
    source = Path(path) if path is not None else Path(__file__).resolve().parents[2] / 'skills/csharp-designer-style-harness/references/default-profile.json'
    if not source.is_absolute():
        raise ValueError("profile path must be absolute")
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not data.get("scope") or not isinstance(data.get("defaults"), dict):
        raise ValueError("profile must declare its scope and defaults")
    return data
