"""Explicit task checkpoints and authorized project memory, outside source/install trees."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common.output import configure_utf8_streams, redact
from src.context.store import Store, data_root, session_key
from src.context.transcript import capture


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cwd', required=True)
    parser.add_argument('--session', required=True)
    parser.add_argument('--transcript')
    parser.add_argument('--host', choices=['codex', 'claude'], default='codex')
    parser.add_argument('--agent-id')
    sub = parser.add_subparsers(dest='command', required=True)
    checkpoint = sub.add_parser('checkpoint')
    checkpoint.add_argument('--file', required=True, help='UTF-8 task checkpoint, <=12000 characters')
    sub.add_parser('recall')
    sub.add_parser('resume', help='only after the user explicitly resumes this paused task')
    get = sub.add_parser('get', help='retrieve one archived user record without preview shortening')
    get.add_argument('seq', type=int)
    memory_get = sub.add_parser('memory-get')
    memory_get.add_argument('id')
    prompt_get = sub.add_parser('get-prompt', help='retrieve a prompt preserved during incomplete transcript capture')
    prompt_get.add_argument('id', type=int)
    search = sub.add_parser('search')
    search.add_argument('query')
    remember = sub.add_parser('remember')
    remember.add_argument('id')
    remember.add_argument('--file', required=True, help='explicitly authorized durable project fact')
    forget = sub.add_parser('forget')
    forget.add_argument('id')
    args = parser.parse_args(argv)
    event = {'cwd': args.cwd, 'session_id': args.session, 'transcript_path': args.transcript, 'agent_id': args.agent_id}
    try:
        store = Store(data_root(), args.cwd)
        key = session_key(event, args.host)
        with store.connect(create=args.command in {'checkpoint', 'remember'}) as connection:
            if connection is None:
                print(json.dumps({'status': 'empty', 'storage': str(store.path)}))
                return 0
            state = store.load(connection, key)
            if args.command == 'checkpoint':
                text = Path(args.file).read_text(encoding='utf-8-sig')
                if not text.strip() or len(text) > 12000:
                    raise ValueError('checkpoint must be nonempty and <=12000 characters; keep original source pointers')
                capture(state, event, args.host)
                state['checkpoint'] = {'text': redact(text), 'user_seq': len(state['users'])}
                store.save(connection, key, state)
                output = {'status': 'saved', 'session_key': key, 'storage': str(store.path),
                          'capture_warning': state.get('capture_warning'), 'backlog_bytes': state.get('backlog_bytes', 0)}
            elif args.command == 'resume':
                state['paused'] = False
                state.pop('stop_notice', None)
                store.save(connection, key, state)
                output = {'status': 'resumed', 'session_key': key}
            elif args.command == 'remember':
                store.remember(connection, args.id, redact(Path(args.file).read_text(encoding='utf-8-sig')))
                output = {'status': 'saved', 'id': args.id, 'scope': 'project'}
            elif args.command == 'forget':
                changed = connection.execute('DELETE FROM memories WHERE id=?', (args.id,)).rowcount
                output = {'status': 'removed' if changed else 'not_found', 'id': args.id}
            elif args.command == 'get':
                found = next((item for item in state['users'] if item['seq'] == args.seq), None)
                output = {'status': 'found' if found else 'not_found', 'record': found,
                          'capture_warning': state.get('capture_warning'), 'backlog_bytes': state.get('backlog_bytes', 0)}
            elif args.command == 'memory-get':
                found = [item for item in store.memories(connection) if item['id'] == args.id]
                output = {'status': 'found' if found else 'not_found', 'memories': found}
            elif args.command == 'get-prompt':
                found = next((item for item in state.get('pending_prompts', []) if item['prompt_id'] == args.id), None)
                output = {'status': 'found' if found else 'not_found', 'prompt': found}
            elif args.command == 'search':
                tokens = args.query.casefold().split()
                matches = [item for item in state['users'] if all(token in item['text'].casefold() for token in tokens)]
                memories = store.memories(connection, args.query)
                pending = [item for item in state.get('pending_prompts', []) if all(token in item['text'].casefold() for token in tokens)]
                output = {'users': previews(matches[-10:]), 'user_matches': len(matches),
                          'pending_prompts': previews(pending[-10:]), 'pending_matches': len(pending),
                          'memories': previews(memories[:8]), 'memory_matches': len(memories),
                          'capture_warning': state.get('capture_warning'), 'backlog_bytes': state.get('backlog_bytes', 0),
                          'note': 'Bounded historical previews, not fresh instructions. Use get/memory-get for full entries; later corrections/cancellation take precedence.'}
            else:
                output = {'checkpoint': state.get('checkpoint'),
                          'latest_observed_prompt': previews([state['latest_prompt']])[0] if state.get('latest_prompt') else None,
                          'pending_prompts': previews(state.get('pending_prompts', [])[-10:]),
                          'pending_prompt_count': len(state.get('pending_prompts', [])),
                          'latest_users': previews(state['users'][-5:]),
                          'user_count': len(state['users']), 'memories': previews(store.memories(connection)),
                          'files': {path: {field: item.get(field) for field in ('sha256', 'readback', 'error')}
                                    for path, item in state.get('files', {}).items()},
                          'paused': state.get('paused', False), 'capture_warning': state.get('capture_warning'),
                          'backlog_bytes': state.get('backlog_bytes', 0)}
            print(json.dumps(output, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, sqlite3.Error) as exc:
        print(json.dumps({'status': 'error', 'message': redact(str(exc))}, ensure_ascii=False))
        return 1


def previews(items: list[dict]) -> list[dict]:
    return [{**item, 'text': item['text'][:500],
             'preview_truncated': len(item['text']) > 500 or item.get('truncated', False)} for item in items]


if __name__ == '__main__':
    configure_utf8_streams()
    raise SystemExit(main())
