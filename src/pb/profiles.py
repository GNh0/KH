"""Load a scoped profile without cryptographic authority or author rescanning."""
from pathlib import Path
from src.csharp.profiles import load_profile as _load


def load_profile(path=None):
    return _load(path or Path(__file__).resolve().parents[2] / 'skills/pb-to-csharp-migration-harness/references/default-profile.json')
