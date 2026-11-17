"""Package the independent API skill without KH runtime or user data."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import zipfile


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / 'standalone/api-auth'


def build(destination: Path) -> dict:
    if not destination.is_absolute():
        raise ValueError('ZIP output must be an absolute external path.')
    destination = destination.resolve()
    if destination.is_relative_to(ROOT):
        raise ValueError('Keep installation archives outside project sources.')
    manifest = SKILL / 'bundle.json'
    payload = json.loads(manifest.read_text(encoding='utf-8'))['payload']
    if not isinstance(payload, list) or not payload or any(not isinstance(name, str) for name in payload):
        raise ValueError('Standalone skill needs an explicit file inventory.')
    if len(payload) != len(set(payload)):
        raise ValueError('Standalone file inventory contains duplicates.')
    files = [manifest]
    for name in payload:
        relative = PurePosixPath(name)
        if relative.is_absolute() or '\\' in name or any(part in {'.', '..'} for part in relative.parts):
            raise ValueError('Standalone payload path must stay inside the skill.')
        files.append(SKILL.joinpath(*relative.parts))
    for source in files:
        if not source.is_file() or source.is_symlink() or not source.resolve().is_relative_to(SKILL.resolve()):
            raise ValueError('Skill source is missing or escapes its package.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'x', compression=zipfile.ZIP_DEFLATED) as archive:
        for source in sorted(files):
            archive.write(source, 'api-auth/' + source.relative_to(SKILL).as_posix())
    with zipfile.ZipFile(destination) as archive:
        if archive.testzip() is not None:
            raise ValueError('ZIP integrity check failed.')
    return {'path': str(destination), 'files': len(files),
            'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(build(args.out), ensure_ascii=False))


if __name__ == '__main__':
    main()
