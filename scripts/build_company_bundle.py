"""Build a separate local-marketplace ZIP without personal Git/GitHub state."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DISPLAY = {
    'artifact-checks': ('Artifact checks', 'Check deliverable content, structure and rendered output'),
    'code-review': ('Code review', 'Review actual changes and project contracts'),
    'context-handoff': ('Context handoff', 'Resume long work from a compact checkpoint'),
    'csharp-designer-style-harness': ('C# and Designer', 'Follow actual C# controls, APIs and employee style'),
    'pb-to-csharp-migration-harness': ('PowerBuilder', 'Analyze and maintain PB or migrate its behavior'),
    'sql-formatting': ('SQL formatting', 'Write and format SQL with selected employee style'),
    'systematic-debugging': ('Systematic debugging', 'Trace actual failure paths and test the cause'),
    'work-execution': ('Work execution', 'Execute approved work with scoped changes'),
    'work-planning': ('Work planning', 'Plan substantial work and unresolved dependencies'),
}


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def build_bundle(output: Path) -> dict:
    if not output.is_absolute() or output.suffix.lower() != '.zip':
        raise ValueError('output must be an absolute ZIP path')
    output = output.resolve()
    for protected in (ROOT / 'src', ROOT / 'skills', ROOT / 'scripts', ROOT / 'company'):
        if output.is_relative_to(protected):
            raise ValueError('write the final ZIP outside implementation/source folders')
    with tempfile.TemporaryDirectory(prefix='company-dev-bundle-') as folder:
        stage = Path(folder) / 'marketplace'
        template = ROOT / 'company'
        for source in sorted(template.rglob('*')):
            if source.is_file() and source.suffix in {'.md', '.json', '.py', '.yaml'} and '__pycache__' not in source.parts:
                if not source.resolve().is_relative_to(template.resolve()):
                    raise ValueError('company template points outside its source root')
                copy_file(source, stage / source.relative_to(template))
        plugin = stage / 'plugins/company-dev'
        for source in sorted((ROOT / 'src').rglob('*.py')):
            relative = source.relative_to(ROOT)
            if relative.parts[1] == 'maintenance' and source.name not in {'__init__.py', 'package_check.py'}:
                continue
            copy_file(source, plugin / relative)
        copy_file(ROOT / 'scripts/kh_check.py', plugin / 'scripts/kh_check.py')
        pb_scripts = Path('skills/pb-to-csharp-migration-harness/scripts')
        for relative in ('export_pbl.py', 'pbl-exporter/Export-PBL.ps1',
                         'pbl-exporter/PblExporter.exe', 'pbl-exporter/bundle.json'):
            copy_file(ROOT / pb_scripts / relative, plugin / pb_scripts / relative)
        for name, (display_name, description) in DISPLAY.items():
            target = plugin / 'skills' / name / 'agents/openai.yaml'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('interface:\n'
                              '  display_name: ' + json.dumps(display_name) + '\n'
                              '  short_description: ' + json.dumps(description) + '\n'
                              '  default_prompt: ' + json.dumps('Use $' + name + ' for this task.') + '\n', encoding='utf-8')
        names = {entry.parent.name for entry in (plugin / 'skills').glob('*/SKILL.md')}
        if names != set(DISPLAY):
            raise ValueError('employee bundle must contain the selected nine skills')
        validation = subprocess.run([sys.executable, '-B', str(plugin / 'scripts/company_check.py'),
                                     'package', str(plugin)], cwd=folder, capture_output=True,
                                    text=True, encoding='utf-8')
        if validation.returncode:
            raise ValueError('generated package validation failed: ' + validation.stdout + validation.stderr)
        files = sorted(path for path in stage.rglob('*') if path.is_file())
        for path in files:
            data = path.read_bytes()
            if any(name.encode(encoding) in data for name in ('GNh0', 'KONEIT')
                   for encoding in ('utf-8', 'utf-16-le')):
                raise ValueError('personal account/path leaked into company package: ' + str(path.relative_to(stage)))
        archive = Path(folder) / 'company-dev.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in files:
                bundle.write(path, path.relative_to(stage).as_posix())
        output.parent.mkdir(parents=True, exist_ok=True)
        copy_file(archive, output)
    return {'output': str(output), 'size_bytes': output.stat().st_size,
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'skill_count': len(DISPLAY),
            'version': json.loads((ROOT / 'company/plugins/company-dev/.codex-plugin/plugin.json').read_text(encoding='utf-8'))['version'],
            'checks': 'generated package references, Python imports and CLI execution',
            'installed_in_codex': False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='absolute final ZIP path')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build_bundle(Path(args.output)), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(json.dumps({'status': 'failed', 'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
