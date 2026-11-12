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
    result = CheckResult(checked=['manifest, skill and agent entrypoints', 'local Markdown links', 'Python AST and internal import targets'],
                         not_checked=['installed plugin cache', 'Codex skill selection', 'host or domain runtime behavior'])
    def error(code, message, path=None):
        result.issues.append(Issue(code, 'error', message, path=str(path) if path else None))
    def check_links(doc, code):
        for href in re.findall(r'\[[^\]]*\]\(([^)]+)\)', doc.read_text(encoding='utf-8-sig')):
            href = href.strip().strip('<>').split('#', 1)[0]
            if not href or re.match(r'[a-z][a-z0-9+.-]*:', href, re.I):
                continue
            target = (doc.parent / href).resolve()
            if not target.is_relative_to(root) or not target.exists():
                error(code, 'Missing or external local reference: ' + href, doc)
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
            check_links(doc, 'skill_link_broken')
    if len(names) != len(set(names)):
        error('skill_name_duplicate', 'Skill names must be unique.')
    agent_names = []
    agent_files = sorted((root / 'agents').glob('*.md'))
    claude_manifest_path = root / '.claude-plugin/plugin.json'
    if claude_manifest_path.is_file():
        try:
            claude_manifest = json.loads(claude_manifest_path.read_text(encoding='utf-8-sig'))
            declared_agents = claude_manifest.get('agents')
            if declared_agents is not None:
                paths = [declared_agents] if isinstance(declared_agents, str) else declared_agents
                if not isinstance(paths, list):
                    raise ValueError('Manifest agents must be a path or an array of file paths.')
                agent_files = []
                for path in paths:
                    entry = (root / path).resolve() if isinstance(path, str) else root
                    if not isinstance(path, str) or not path.startswith('./') or not entry.is_relative_to(root) or entry.suffix != '.md' or not entry.is_file():
                        error('agent_path_invalid', 'Manifest agents must name existing .md files inside the package.', claude_manifest_path)
                        continue
                    agent_files.append(entry)
        except (OSError, ValueError, AttributeError) as exc:
            error('agent_manifest_invalid', str(exc), claude_manifest_path)
    for entry in agent_files:
        text = entry.read_text(encoding='utf-8-sig')
        match = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
        if not match:
            error('agent_frontmatter_missing', 'Agent definitions need YAML frontmatter.', entry)
            continue
        fields = dict(re.findall(r'^([a-z_-]+):\s*(.+)$', match[1], re.M))
        name = fields.get('name', '').strip('"\'')
        description = fields.get('description', '').strip('"\'')
        if name != entry.stem or not description or not text[match.end():].strip():
            error('agent_metadata_invalid', 'Agent name must match its file and include a description and instructions.', entry)
        agent_names.append(name)
        check_links(entry, 'agent_link_broken')
    if len(agent_names) != len(set(agent_names)):
        error('agent_name_duplicate', 'Agent names must be unique.')
    result.not_checked.append('host agent discovery, invocation and review behavior')
    hook_paths = {root / 'hooks/hooks.json'} if (root / 'hooks/hooks.json').exists() else set()
    declared_hooks = manifest.get('hooks')
    if isinstance(declared_hooks, str):
        hook_path = (root / declared_hooks).resolve()
        if not declared_hooks.startswith('./') or not hook_path.is_relative_to(root) or not hook_path.is_file():
            error('hook_path_invalid', 'Declared hook configuration must exist inside the package.', manifest_path)
        else:
            hook_paths.add(hook_path)
    for hook_path in hook_paths:
        try:
            config = json.loads(hook_path.read_text(encoding='utf-8-sig'))
            events = config.get('hooks')
            if not isinstance(events, dict) or not events:
                raise ValueError('Hook configuration needs a nonempty hooks object.')
            for groups in events.values():
                if not isinstance(groups, list):
                    raise ValueError('Hook event groups must be arrays.')
                for group in groups:
                    for handler in group['hooks']:
                        if handler.get('type') != 'command' or not isinstance(handler.get('command'), str):
                            raise ValueError('KH bundled hooks use command handlers.')
                        if not 0 < handler.get('timeout', 0) <= 10:
                            raise ValueError('KH hook commands need an explicit timeout <=10 seconds.')
                        if not (root / 'scripts/kh_hook.py').is_file():
                            raise ValueError('Hook launcher is missing.')
            result.checked.append('bundled hook JSON shape and launcher presence: ' + hook_path.name)
        except (OSError, ValueError, TypeError, KeyError, AttributeError) as exc:
            error('hook_config_invalid', str(exc), hook_path)
    result.not_checked.append('host hook trust, event firing and semantic audit/recall behavior')
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
                elif node.module and node.module.startswith('src.'):
                    modules = [node.module.split('.')]
            for module in modules:
                target = root.joinpath(*module)
                if not target.with_suffix('.py').is_file() and not target.is_dir():
                    error('internal_import_missing', 'Missing internal module: ' + '.'.join(module), source)
    result.metadata.update(plugin=manifest.get('name'), version=manifest.get('version'), skill_names=names,
                           skill_count=len(skill_files), python_files=len(python_files),
                           agent_names=agent_names, agent_count=len(agent_names))
    return result
