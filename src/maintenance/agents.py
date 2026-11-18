"""Export Codex custom agents from the shared, reviewed KH role definitions."""
import hashlib
import json
from pathlib import Path
import re
import tomllib


def agent_definitions(root: Path) -> dict[str, str]:
    """Build supported TOML files without duplicating the role instructions."""
    root = root.resolve(strict=True)
    manifest = json.loads((root / '.claude-plugin/plugin.json').read_text(encoding='utf-8-sig'))
    definitions = {}
    for relative in manifest['agents']:
        path = (root / relative).resolve(strict=True)
        if not path.is_relative_to(root / 'agents') or path.suffix != '.md':
            raise ValueError('Role must be a packaged agent definition.')
        text = path.read_text(encoding='utf-8-sig')
        header = re.match(r'\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)', text, re.S)
        if header is None:
            raise ValueError('Role frontmatter is missing: ' + str(path))
        fields = dict(re.findall(r'^([a-z_-]+):\s*(.+)$', header[1], re.M))
        name, description = fields.get('name', ''), fields.get('description', '')
        if name != path.stem or not re.fullmatch(r'[a-z][a-z0-9-]+', name) or not description:
            raise ValueError('Role name/description is invalid: ' + str(path))

        def absolute_link(match: re.Match) -> str:
            label, href = match[1], match[2]
            if re.match(r'[a-z][a-z0-9+.-]*:', href, re.I):
                return match[0]
            filename, separator, anchor = href.partition('#')
            target = (path.parent / filename).resolve(strict=True)
            if not target.is_relative_to(root):
                raise ValueError('Role reference escapes its package: ' + href)
            return '[' + label + '](' + target.as_posix() + (separator + anchor if separator else '') + ')'

        instructions = ('KH package root: ' + root.as_posix() + '\n'
                        'Use only the current delegated task and its latest corrections. '
                        'Inspect the linked current skill and source bodies before acting.\n\n' +
                        re.sub(r'\[([^\]]+)\]\(([^)]+)\)', absolute_link, text[header.end():].strip()))
        data = {'name': name, 'description': description, 'developer_instructions': instructions}
        body = '\n'.join(key + ' = ' + json.dumps(value, ensure_ascii=False) for key, value in data.items()) + '\n'
        if tomllib.loads(body) != data:
            raise ValueError('Generated agent TOML did not preserve the definition.')
        if name in definitions:
            raise ValueError('Duplicate role name: ' + name)
        definitions[name] = body
    return definitions


def export_agents(root: Path, output: Path) -> dict:
    """Update only unchanged files owned by this exporter, preserving customization.

    Exporting to a host's agents directory is an explicit installation action.
    A successful export does not prove discovery or execution by that host.
    """
    if not output.is_absolute():
        raise ValueError('Choose an absolute output agents directory.')
    root, output = root.resolve(strict=True), output.resolve()
    if output == root or output.is_relative_to(root):
        raise ValueError('Export outside the KH source/install tree; do not duplicate generated role bodies in the package.')
    definitions = agent_definitions(root)
    receipt = output / '.kh-agent-exports.json'
    if receipt.is_symlink():
        raise ValueError('Export ownership record must not be a symlink.')
    prior = json.loads(receipt.read_text(encoding='utf-8')) if receipt.exists() else {}
    owned = prior.get('files', {})
    if not isinstance(owned, dict):
        raise ValueError('Export ownership record is invalid.')
    for name, body in definitions.items():
        path = output / (name + '.toml')
        if path.is_symlink():
            raise ValueError('Preserving a linked agent file: ' + str(path))
        if path.exists():
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            generated = hashlib.sha256(body.encode('utf-8')).hexdigest()
            if actual != generated and actual != owned.get(path.name):
                raise ValueError('Preserving an existing or customized agent: ' + str(path))
    output.mkdir(parents=True, exist_ok=True)
    files = {}
    for name, body in definitions.items():
        path = output / (name + '.toml')
        path.write_text(body, encoding='utf-8', newline='\n')
        files[path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
    receipt.write_text(json.dumps({'package_root': str(root), 'files': files}, indent=2) + '\n', encoding='utf-8')
    return {'status': 'exported', 'directory': str(output), 'agents': sorted(definitions),
            'host_discovery': 'unverified', 'invocation': 'unverified'}
