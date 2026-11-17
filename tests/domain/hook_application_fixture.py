"""Intent setup for saved-file unit cases; the real CLI lifecycle has separate tests."""
from pathlib import Path

from src.context.store import Store, data_root, session_key
from src.runtime.guidance import document
from src.runtime.hooks import ROOT, handle
from src.runtime.workflows import register


def apply_files(scope, host, work, targets, *, deliver=True):
    store = Store(data_root(), scope['cwd'])
    with store.connect() as connection:
        if connection is None:
            raise ValueError('The fixture must first deliver a real KH entrypoint.')
        key = session_key(scope, host)
        state = store.load(connection, key)
        applied = register(state, epoch=state['application_epoch'], work=work,
                           targets=[str(path) for path in targets], cwd=scope['cwd'])
        store.save(connection, key, state)
    if deliver:
        for relative in sorted({relative for item in applied for relative in item['required']}):
            path, body, _start, _end = document(ROOT, relative)
            handle({**scope, 'hook_event_name': 'PostToolUse', 'tool_name': 'Read',
                    'tool_input': {'file_path': str(path)}, 'tool_response': body}, host)
    return applied
