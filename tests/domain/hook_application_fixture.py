"""Intent setup for saved-file unit cases; the real CLI lifecycle has separate tests."""
from pathlib import Path

from src.context.store import Store, data_root, session_key
from src.runtime.guidance import document
from src.runtime.hooks import ROOT, handle
from src.runtime.workflows import register
from src.runtime.source_evidence import select_references


def apply_files(scope, host, work, targets, *, deliver=True):
    store = Store(data_root(), scope['cwd'])
    with store.connect() as connection:
        if connection is None:
            raise ValueError('The fixture must first deliver a real KH entrypoint.')
        key = session_key(scope, host)
        state = store.load(connection, key)
        if set(work) & {'sql-select', 'sql-save'}:
            state['sql_authorship'] = {'author': 'Fixture Writer', 'reference_author': 'Fixture Writer'}
        applied = register(state, epoch=state['application_epoch'], work=work,
                           targets=[str(path) for path in targets], cwd=scope['cwd'])
        reference_directory = Path(scope['cwd']) / '.comparison-fixture'
        reference_directory.mkdir(exist_ok=True)
        refs = []
        suffixes = {Path(path).suffix.casefold() for path in targets} | ({'.sru'} if 'pb-migrate' in work else set())
        for suffix in suffixes:
            layout = suffix == '.cs' and any(Path(path).name.casefold().endswith('.designer.cs') for path in targets)
            reference = reference_directory / ('Reference.Designer.cs' if layout else 'Reference' + suffix)
            body = 'class Reference { public int Read() { return 1; } }\n' if suffix == '.cs' else 'SELECT A.VALUE FROM REFERENCE_ROWS A;\n' if suffix == '.sql' else 'global type reference from window\nend type\n'
            if layout:
                body = 'partial class Reference { private DevExpress.XtraEditors.TextEdit txtItem; void InitializeComponent() { this.txtItem = new DevExpress.XtraEditors.TextEdit(); this.txtItem.Size = new System.Drawing.Size(150, 25); } }\n'
            if suffix == '.sql':
                body = '-- =============================================\n-- AUTHOR: Fixture Writer\n-- CREATE DATE: 2026-11-18\n-- DESCRIPTION: Fixture query 조회\n-- =============================================\nCREATE PROCEDURE dbo.Reference_SELECT AS\n' + body
                if 'sql-save' in work:
                    body += 'UPDATE REFERENCE_ROWS SET VALUE = 1;\n'
            reference.write_text(body, encoding='utf-8')
            refs.append(str(reference))
        select_references(state, applied, refs, scope['cwd'])
        store.save(connection, key, state)
    for reference in refs:
        handle({**scope, 'hook_event_name': 'PostToolUse', 'tool_name': 'Read',
                'tool_input': {'file_path': reference}, 'tool_response': Path(reference).read_text(encoding='utf-8')}, host)
    if deliver:
        for relative in sorted({relative for item in applied for relative in item['required']}):
            path, body, _start, _end = document(ROOT, relative)
            handle({**scope, 'hook_event_name': 'PostToolUse', 'tool_name': 'Read',
                    'tool_input': {'file_path': str(path)}, 'tool_response': body}, host)
    return applied
