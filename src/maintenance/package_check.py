"""Validate local skills, manifest, references and Python import targets without installing."""
import ast
import json
from pathlib import Path
import re
from src.common.results import CheckResult, Issue


def check_package(path: str | Path) -> CheckResult:
    root = Path(path)
    if not root.is_absolute():
        raise ValueError('package path must be absolute')
    root = root.resolve(strict=True)
    result = CheckResult(checked=['manifest and skill entrypoints', 'local Markdown links', 'Python AST and internal import targets'],
                         not_checked=['installed plugin cache', 'Codex skill selection', 'host or domain runtime behavior'])
    def error(code, message, path=None):
        result.issues.append(Issue(code, 'error', message, path=str(path) if path else None))
    manifest_path = root / '.codex-plugin/plugin.json'
    try:
        manifest = json.loads(manifest_path.read_text(encoding='utf-8-sig'))
        if not isinstance(manifest, dict) or not re.fullmatch(r'[a-z0-9]+(?:-[a-z0-9]+)*', manifest.get('name', '')):
            error('plugin_name_invalid', 'Manifest needs a kebab-case plugin name.', manifest_path)
        skill_root = (root / manifest.get('skills', './skills')).resolve()
        if not skill_root.is_relative_to(root) or not skill_root.is_dir():
            error('skill_root_invalid', 'Manifest skills must resolve to a directory in this package.', manifest_path)
            return result
    except (OSError, ValueError, TypeError) as exc:
        error('manifest_invalid', str(exc), manifest_path)
        return result
    names = []
    skill_files = sorted(skill_root.glob('*/SKILL.md'))
    if not skill_files:
        error('skills_missing', 'No skill entrypoints found.', skill_root)
    for entry in skill_files:
        text = entry.read_text(encoding='utf-8-sig')
        match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
        if not match:
            error('skill_frontmatter_missing', 'SKILL.md needs YAML frontmatter.', entry)
            continue
        fields = dict(re.findall(r'^([a-z_-]+):\s*(.+)$', match[1], re.M))
        name = fields.get('name', '').strip('"\'')
        description = fields.get('description', '').strip('"\'')
        if name != entry.parent.name or not description:
            error('skill_metadata_invalid', 'Skill name must match its directory and include a description.', entry)
        names.append(name)
        for doc in entry.parent.rglob('*.md'):
            for href in re.findall(r'\[[^\]]*\]\(([^)]+)\)', doc.read_text(encoding='utf-8-sig')):
                href = href.strip().strip('<>').split('#', 1)[0]
                if not href or re.match(r'[a-z][a-z0-9+.-]*:', href, re.I):
                    continue
                target = (doc.parent / href).resolve()
                if not target.is_relative_to(root) or not target.exists():
                    error('skill_link_broken', 'Missing or external local reference: ' + href, doc)
    if len(names) != len(set(names)):
        error('skill_name_duplicate', 'Skill names must be unique.')
    python_files = [p for folder in ('src', 'scripts') for p in (root / folder).rglob('*.py')]
    for source in python_files:
        try:
            tree = ast.parse(source.read_text(encoding='utf-8-sig'), filename=str(source))
        except (SyntaxError, UnicodeError, OSError) as exc:
            error('python_syntax_invalid', str(exc), source)
            continue
        package_parts = list(source.relative_to(root).parts[:-1])
        for node in ast.walk(tree):
            modules = []
            if isinstance(node, ast.Import):
                modules = [alias.name.split('.') for alias in node.names if alias.name.startswith('src.')]
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = package_parts[:len(package_parts)-node.level+1]
                    modules = [base + node.module.split('.')] if node.module else [base]
                elif (node.module or '').startswith('src.'):
                    modules = [node.module.split('.')]
            for module in modules:
                target = root.joinpath(*module)
                if not target.with_suffix('.py').is_file() and not target.is_dir():
                    error('internal_import_missing', 'Missing internal module: ' + '.'.join(module), source)
    result.metadata.update(plugin=manifest.get('name'), version=manifest.get('version'), skill_names=names,
                           skill_count=len(skill_files), python_files=len(python_files))
    return result
