"""Read one employee style; initialization preserves every existing file."""
import argparse
import io
import json
import os
from pathlib import Path
import sys

TOPICS = ('sql', 'csharp', 'pb', 'work')
TEMPLATES = {
    'sql': '# Personal SQL style\n\nUnspecified choices follow approved project examples.\n\n'
           '- Keyword and identifier case:\n- Indentation, parentheses and JOIN layout:\n'
           '- Alias naming and preservation:\n- CTE, subquery and intermediate-table preferences:\n',
    'csharp': '# Personal C# style\n\nUnspecified choices follow approved project examples.\n\n'
              '- Braces, types and expression style:\n- Variable, control and repository names:\n'
              '- Numeric formats:\n- LINQ and intermediate-data preferences:\n- Build preferences:\n',
    'pb': '# Personal PB style\n\nUnspecified choices follow approved project examples.\n\n'
          '- Object, event and DataWindow naming:\n- PowerScript and embedded SQL layout:\n'
          '- Analysis and migration preferences:\n',
    'work': '# Personal work style\n\nUnspecified choices follow the current request.\n\n'
            '- Response language and detail:\n- Preferred deliverable formats:\n',
}


def style_directory(explicit: str | None = None) -> Path:
    selected = explicit or os.environ.get('COMPANY_DEV_STYLE_HOME')
    if selected:
        directory = Path(selected).expanduser()
    else:
        codex_home = os.environ.get('CODEX_HOME')
        directory = (Path(codex_home).expanduser() if codex_home else Path.home() / '.codex') / 'company-dev-style'
    if not directory.is_absolute():
        raise ValueError('personal style directory must be an absolute path')
    directory = directory.resolve()
    if directory.is_relative_to(Path(__file__).resolve().parents[1]):
        raise ValueError('keep personal style files outside the plugin/install directory')
    return directory


def initialize(directory: Path) -> dict:
    directory.mkdir(parents=True, exist_ok=True)
    created, preserved = [], []
    for topic in TOPICS:
        path = directory / (topic + '.md')
        try:
            with path.open('x', encoding='utf-8', newline='\n') as stream:
                stream.write(TEMPLATES[topic])
            created.append(str(path))
        except FileExistsError:
            if not path.is_file():
                raise ValueError('style file is not a regular file: ' + str(path))
            preserved.append(str(path))
    return {'directory': str(directory), 'created': created, 'preserved': preserved}


def read_style(directory: Path, topic: str) -> dict:
    if topic not in TOPICS:
        raise ValueError('unsupported personal style topic')
    path = directory / (topic + '.md')
    return {'topic': topic, 'path': str(path), 'exists': path.is_file(),
            'text': path.read_text(encoding='utf-8-sig') if path.is_file() else '',
            'automatic_style_enforcement': False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init', help='create missing personal files; never overwrite existing files')
    show = commands.add_parser('show', help='read one topic without creating files')
    show.add_argument('topic', choices=TOPICS)
    for command in (init, show):
        command.add_argument('--directory', help='explicit absolute personal directory')
    args = parser.parse_args(argv)
    try:
        directory = style_directory(args.directory)
        result = initialize(directory) if args.command == 'init' else read_style(directory, args.topic)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, UnicodeError) as error:
        print(json.dumps({'status': 'failed', 'error': str(error)}, ensure_ascii=False))
        return 1


if __name__ == '__main__':
    if isinstance(sys.stdout, io.TextIOWrapper):
        sys.stdout.reconfigure(encoding='utf-8')
    raise SystemExit(main())
