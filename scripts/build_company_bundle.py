"""Build a separate local-marketplace ZIP without personal Git/GitHub state."""
import argparse
import hashlib
import io
import json
from pathlib import Path
import re
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
    'runtime-cleanup': ('Runtime cleanup', 'Release finished task-owned processes and runtime resources'),
    'rule-audit': ('Rule audit', 'Audit applied rules and repair confirmed violations'),
}
ROLES = {'kone-sql-worker', 'kone-csharp-worker', 'kone-pb-worker', 'kone-rule-auditor'}


def brand_shared_payload(stage: Path, plugin: Path) -> None:
    """Adapt copied shared modules for KONE without editing the personal plugin."""
    exporter = plugin / 'skills/pb-to-csharp-migration-harness/scripts/pbl-exporter'
    manifest_path = exporter / 'bundle.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for name in ('Export-PBL.ps1', 'PblExporter.exe'):
        if hashlib.sha256((exporter / name).read_bytes()).hexdigest() != manifest['sha256'][name]:
            raise ValueError('bundled PB exporter source hash mismatch: ' + name)
    for path in stage.rglob('*'):
        if not path.is_file() or path.suffix not in {'.py', '.md', '.json', '.yaml', '.ps1'}:
            continue
        original = path.read_text(encoding='utf-8-sig')
        branded = original.replace('scripts.kh_check', 'scripts.kone_check_core')
        branded = re.sub(r'(?<![A-Za-z0-9])KH(?![A-Za-z0-9])', 'KONE', branded)
        branded = re.sub(r'(?<![A-Za-z0-9])kh(?![A-Za-z0-9])', 'kone', branded)
        if branded != original:
            path.write_text(branded, encoding='utf-8', newline='\n')
    manifest['sha256']['Export-PBL.ps1'] = hashlib.sha256((exporter / 'Export-PBL.ps1').read_bytes()).hexdigest()
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


def copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)


def tracked_sources() -> set[Path]:
    """Use the Git index as the distribution inventory, never rglob."""
    git = ['git', '-c', 'safe.directory=' + ROOT.as_posix()]
    top = subprocess.run([*git, 'rev-parse', '--show-toplevel'], cwd=ROOT,
                         capture_output=True, text=True, encoding='utf-8', timeout=30)
    if top.returncode or Path(top.stdout.strip()).resolve() != ROOT.resolve():
        raise ValueError('build the bundle from its Git checkout; no tracked file inventory is available')
    inventory = subprocess.run([*git, 'ls-files', '--cached', '-z'], cwd=ROOT,
                               capture_output=True, text=True, encoding='utf-8', timeout=30)
    if inventory.returncode:
        raise ValueError('cannot read the tracked Git file inventory')
    return {Path(name) for name in inventory.stdout.split('\0') if name}


def build_bundle(output: Path) -> dict:
    if not output.is_absolute() or output.suffix.lower() != '.zip':
        raise ValueError('output must be an absolute ZIP path')
    output = output.resolve()
    for protected in (ROOT / 'src', ROOT / 'skills', ROOT / 'scripts', ROOT / 'company'):
        if output.is_relative_to(protected):
            raise ValueError('write the final ZIP outside implementation/source folders')
    inventory = tracked_sources()

    def copy_source(relative: Path, target: Path) -> None:
        source = ROOT / relative
        if relative not in inventory or not source.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError('bundle input is not a tracked in-repository source: ' + str(relative))
        copy_file(source, target)

    with tempfile.TemporaryDirectory(prefix='kone-dev-bundle-') as folder:
        stage = Path(folder) / 'marketplace'
        template = ROOT / 'company'
        for relative in sorted(inventory):
            source = ROOT / relative
            if relative.is_relative_to(Path('company')) and source.suffix in {'.md', '.json', '.py', '.yaml'} and '__pycache__' not in source.parts:
                if not source.resolve().is_relative_to(template.resolve()):
                    raise ValueError('company template points outside its source root')
                copy_source(relative, stage / source.relative_to(template))
        plugin = stage / 'plugins/kone-dev'
        for relative in sorted(path for path in inventory if path.is_relative_to(Path('src')) and path.suffix == '.py'):
            if relative.parts[1] == 'maintenance' and relative.name not in {'__init__.py', 'package_check.py', 'agents.py'}:
                continue
            copy_source(relative, plugin / relative)
        copy_source(Path('scripts/kh_check.py'), plugin / 'scripts/kone_check_core.py')
        copy_source(Path('scripts/kh_runtime.py'), plugin / 'scripts/kone_runtime.py')
        for shared_skill in ('runtime-cleanup', 'rule-audit'):
            for relative in sorted(inventory):
                if relative.is_relative_to(Path('skills') / shared_skill) and relative.suffix in {'.md', '.yaml'}:
                    copy_source(relative, plugin / relative)
        workspace_reference = Path('skills/work-execution/references/workspace-files.md')
        copy_source(workspace_reference, plugin / workspace_reference)
        style_cycle_reference = Path('skills/work-execution/references/source-style-cycle.md')
        copy_source(style_cycle_reference, plugin / style_cycle_reference)
        reports_reference = Path('skills/csharp-designer-style-harness/references/reports.md')
        copy_source(reports_reference, plugin / reports_reference)
        pb_scripts = Path('skills/pb-to-csharp-migration-harness/scripts')
        for relative in ('export_pbl.py', 'pbl-exporter/Export-PBL.ps1',
                         'pbl-exporter/PblExporter.exe', 'pbl-exporter/bundle.json'):
            copy_source(pb_scripts / relative, plugin / pb_scripts / relative)
        for name, (display_name, description) in DISPLAY.items():
            target = plugin / 'skills' / name / 'agents/openai.yaml'
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text('interface:\n'
                              '  display_name: ' + json.dumps(display_name) + '\n'
                              '  short_description: ' + json.dumps(description) + '\n'
                              '  default_prompt: ' + json.dumps('Use $' + name + ' for this task.') + '\n', encoding='utf-8')
        brand_shared_payload(stage, plugin)
        names = {entry.parent.name for entry in (plugin / 'skills').glob('*/SKILL.md')}
        if names != set(DISPLAY):
            raise ValueError('employee bundle must contain the selected shared skills')
        validation = subprocess.run([sys.executable, '-B', str(plugin / 'scripts/kone_check.py'),
                                     'package', str(plugin)], cwd=folder, capture_output=True,
                                    text=True, encoding='utf-8')
        if validation.returncode:
            raise ValueError('generated package validation failed: ' + validation.stdout + validation.stderr)
        package_result = json.loads(validation.stdout)
        if set(package_result.get('agent_names', [])) != ROLES:
            raise ValueError('employee bundle must contain the selected specialist/reviewer role instructions')
        files = sorted(path for path in stage.rglob('*') if path.is_file())
        for path in files:
            data = path.read_bytes()
            if any(name.encode(encoding) in data for name in ('GNh0', 'KONEIT')
                   for encoding in ('utf-8', 'utf-16-le')):
                raise ValueError('personal account/path leaked into company package: ' + str(path.relative_to(stage)))
        archive = Path(folder) / 'kone-dev.zip'
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
            for path in files:
                bundle.write(path, path.relative_to(stage).as_posix())
        output.parent.mkdir(parents=True, exist_ok=True)
        copy_file(archive, output)
    return {'output': str(output), 'size_bytes': output.stat().st_size,
            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(), 'skill_count': len(DISPLAY),
            'agent_count': len(package_result['agent_names']),
            'version': json.loads((ROOT / 'company/plugins/kone-dev/.codex-plugin/plugin.json').read_text(encoding='utf-8'))['version'],
            'checks': 'generated package references, Python imports and CLI execution',
            'installed_in_codex': False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, help='absolute final ZIP path')
    args = parser.parse_args(argv)
    try:
        print(json.dumps(build_bundle(Path(args.output)), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, UnicodeError, subprocess.SubprocessError) as error:
        print(json.dumps({'status': 'failed', 'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
