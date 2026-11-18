"""Explicit task checkpoints and authorized project memory, outside source/install trees."""
import argparse
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.common.output import configure_utf8_streams, redact
from src.context.store import Store, data_root, session_key
from src.context.transcript import capture, discard_host_records, recent_users
from src.runtime.workflows import WORK, register, binding


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cwd', required=True)
    parser.add_argument('--session', required=True)
    parser.add_argument('--transcript')
    parser.add_argument('--host', choices=['codex', 'claude'], default='codex')
    parser.add_argument('--agent-id')
    parser.add_argument('--data-root', type=Path, help='exact context-v1 root supplied by the current hook')
    parser.add_argument('--epoch', help='current hook application epoch; required for apply')
    sub = parser.add_subparsers(dest='command', required=True)
    checkpoint = sub.add_parser('checkpoint')
    checkpoint.add_argument('--file', required=True, help='UTF-8 task checkpoint, <=12000 characters')
    sub.add_parser('recall')
    sub.add_parser('resume', help='only after the user explicitly resumes this paused task')
    apply = sub.add_parser('apply', help='apply KH development guidance to owned files; inspection alone does not apply it')
    apply.add_argument('--work', choices=sorted(WORK), action='append', required=True)
    apply.add_argument('--target', action='append', required=True)
    apply.add_argument('--reference', action='append', default=[], help='actual comparison source, optionally #Lstart-Lend; selection does not establish a read or approval')
    apply.add_argument('--author', help='name for the target SP AUTHOR header')
    apply.add_argument('--reference-author', action='append', help='search existing SP AUTHOR headers for this name; repeat once per user-selected name')
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
        if args.data_root is not None and not args.data_root.is_absolute():
            raise ValueError('data-root must be the absolute context-v1 root from the current hook')
        store = Store(args.data_root.resolve() if args.data_root else data_root(), args.cwd)
        key = session_key(event, args.host)
        with store.connect(create=args.command in {'checkpoint', 'remember'}) as connection:
            if connection is None:
                if args.command == 'apply':
                    raise ValueError('No current KH hook scope. Read the owned entrypoint and use its exact scope arguments.')
                print(json.dumps({'status': 'empty', 'storage': str(store.path)}))
                return 0
            state = store.load(connection, key)
            discard_host_records(state)
            if args.command == 'checkpoint':
                text = Path(args.file).read_text(encoding='utf-8-sig')
                if not text.strip() or len(text) > 12000:
                    raise ValueError('checkpoint must be nonempty and <=12000 characters; keep original source pointers')
                capture(state, event, args.host)
                state['checkpoint'] = {'text': redact(text), 'user_seq': max((item['seq'] for item in state['users']), default=0)}
                store.save(connection, key, state)
                output = {'status': 'saved', 'session_key': key, 'storage': str(store.path),
                          'capture_warning': state.get('capture_warning'), 'backlog_bytes': state.get('backlog_bytes', 0)}
            elif args.command == 'apply':
                applied = register(state, epoch=args.epoch, targets=args.target, work=args.work, cwd=args.cwd)
                if args.author is not None or args.reference_author is not None:
                    if not any(set(item['work']) & {'sql-select', 'sql-save'} for item in applied):
                        raise ValueError('Author selection belongs to actual SP work, not formatting-only or non-SP work.')
                    from src.sql.procedure_authorship import selected_authors
                    state['sql_authorship'] = selected_authors(args.author, args.reference_author)
                for item in applied:
                    if set(item['work']) & {'sql-select', 'sql-save'}:
                        application = binding(state, Path(item['target']))
                        if application is not None and state.get('sql_authorship') and (
                                args.author is not None or 'sql_authorship' not in application):
                            application['sql_authorship'] = dict(state['sql_authorship'])
                        item['sql_authorship'] = (application or {}).get('sql_authorship')
                from src.runtime.source_evidence import select_references, reference_problem
                select_references(state, applied, args.reference, args.cwd, work=args.work)
                from src.runtime.check_context import SourceBaselines, companion
                from src.runtime.hooks import line_hashes, snapshot, current_prerequisites
                from src.runtime.guidance import document
                baselines = SourceBaselines(store.path.parent / 'checks' / key, state)
                if state.get('check_epoch_closed'):
                    state.pop('check_epoch_closed', None)
                for item in applied:
                    path = Path(item['target'])
                    attempted_hashes = {}
                    # Applying owns this file's intent even when a specialized
                    # writer has no recognizable PreToolUse path. Existing first
                    # originals and active repair/readback evidence are retained.
                    try:
                        peer = companion(path)
                        sources = [path, peer] if peer is not None else [path]
                        if str(path) in state.get('application_errors', {}):
                            expected = state.get('application_failure_hashes', {}).get(str(path), {})
                            for source in sources:
                                current_sha, _current = snapshot(source)
                                if expected.get(str(source)) is None or current_sha != expected[str(source)]:
                                    raise ValueError('The initial original or companion remains unverified or changed after application failed; do not adopt the current candidate as its original.')
                        if str(path) not in state.get('files', {}) and str(path) not in state.get('before', {}):
                            sha, body = snapshot(path)
                            for source in sources:
                                attempted_hashes[str(source)] = snapshot(source)[0]
                            for source in sources:
                                baselines.capture(source)
                            state.setdefault('before', {})[str(path)] = line_hashes(body)
                            state.setdefault('before_sha256', {})[str(path)] = sha
                        state.get('application_errors', {}).pop(str(path), None)
                        state.get('application_failure_hashes', {}).pop(str(path), None)
                    except (OSError, ValueError, UnicodeError, RuntimeError) as exc:
                        state.setdefault('application_errors', {})[str(path)] = redact(str(exc))
                        state.setdefault('application_failure_hashes', {}).setdefault(str(path), attempted_hashes)
                seen = current_prerequisites('\n', state)
                for item in applied:
                    item['missing'] = sorted(set(item['required']) - seen)
                    locations = {}
                    for relative in item['required']:
                        file, _body, start, end = document(Path(__file__).resolve().parents[1], relative)
                        locations[relative] = {'file': str(file), 'line_start': start, 'line_end': end}
                    item['read_locations'] = locations
                    item['comparison_sources'] = [{key: ref.get(key) for key in ('path', 'start', 'end', 'work', 'read_sha256')}
                        for ref in (next(value for value in state['applications'].values() if value['target'] == item['target'])).get('references', [])]
                    item['comparison_evidence_missing'] = reference_problem(state, Path(item['target']))
                store.save(connection, key, state)
                output = {'status': 'error' if state.get('application_errors') else 'applied',
                          'session_key': key, 'storage': str(store.path), 'files': applied,
                          'sql_authorship': state.get('sql_authorship'),
                          'original_errors': state.get('application_errors', {}),
                          'note': 'Intent only. Read the required current references; this is not a source/semantic audit pass.'}
                store.agent_scope(connection, event, args.host, key=key)
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
                output = {'users': previews(recent_users(matches, 10)), 'user_matches': len(matches),
                          'pending_prompts': previews(pending[-10:]), 'pending_matches': len(pending),
                          'memories': previews(memories[:8]), 'memory_matches': len(memories),
                          'capture_warning': state.get('capture_warning'), 'backlog_bytes': state.get('backlog_bytes', 0),
                          'note': 'Bounded historical previews, not fresh instructions. Source offsets order records within the same log; ids are insertion identifiers and unlinked event order is unverified. Use get/memory-get for full entries; later corrections/cancellation take precedence.'}
            else:
                from src.runtime.hooks import current_prerequisites
                from src.runtime.workflows import required_paths
                from src.runtime.source_evidence import reference_problem
                available = current_prerequisites('\n', state)
                output = {'checkpoint': state.get('checkpoint'),
                          'completion_status': state.get('completion_status', 'no_current_completion_claim'),
                          'semantic_audit_verified': False,
                          'audit_note': 'Static checks and observed reference/readback evidence do not establish semantic necessity, source approval, full comparison or regression audit.',
                          'sql_authorship': state.get('sql_authorship'),
                          'requested_skills': state.get('requested_skills', []),
                          'available_prerequisites': sorted(available),
                          'application_original_errors': state.get('application_errors', {}),
                          'applied_files': {item.get('target', path): {'work': item.get('work', []),
                              'declared_work': item.get('declared_work', item.get('work', [])),
                              'inferred_work': item.get('inferred_work', []),
                              'missing_references': sorted(required_paths(item, Path(item.get('target', path))) - available),
                              'comparison_evidence_missing': reference_problem(state, Path(item.get('target', path))),
                              'sql_authorship': item.get('sql_authorship', state.get('sql_authorship')),
                              'comparison_sources': [{key: ref.get(key) for key in ('path', 'start', 'end', 'work', 'source_sha256', 'read_sha256')}
                                  for ref in item.get('references', [])]}
                              for path, item in state.get('applications', {}).items()},
                          'latest_observed_prompt': previews([state['latest_prompt']])[0] if state.get('latest_prompt') else None,
                          'pending_prompts': previews(state.get('pending_prompts', [])[-10:]),
                          'pending_prompt_count': len(state.get('pending_prompts', [])),
                          'latest_users': previews(recent_users(state['users'], 5)),
                          'user_order_note': 'Source offsets order records within the same log; ids are insertion identifiers and unlinked event order is unverified.',
                          'user_count': len(state['users']), 'memories': previews(store.memories(connection)),
                          'files': {path: {field: item.get(field) for field in ('sha256', 'readback', 'error', 'check', 'check_context', 'checker_generation')}
                                    for path, item in (state.get('files') or state.get('last_file_checks', {})).items()},
                          'file_checks_active': bool(state.get('files')) and not state.get('check_epoch_closed', False),
                          'last_file_checks_outcome': state.get('last_file_checks_outcome'),
                          'last_file_warning': state.get('last_file_warning'),
                          'paused': state.get('paused', False), 'capture_warning': state.get('capture_warning'),
                          'backlog_bytes': state.get('backlog_bytes', 0)}
            print(json.dumps(output, ensure_ascii=False, indent=2))
        return 1 if output.get('status') == 'error' else 0
    except (OSError, ValueError, RuntimeError, sqlite3.Error) as exc:
        print(json.dumps({'status': 'error', 'message': redact(str(exc))}, ensure_ascii=False))
        return 1


def previews(items: list[dict]) -> list[dict]:
    return [{**item, 'text': item['text'][:500],
             'preview_truncated': len(item['text']) > 500 or item.get('truncated', False)} for item in items]


if __name__ == '__main__':
    configure_utf8_streams()
    raise SystemExit(main())
