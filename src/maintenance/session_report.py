"""Stream explicitly selected Codex JSONL logs into bounded, source-located records.

This is candidate extraction for a human/agent audit, not a preference classifier
or proof that a delegated role executed. Tool results are counted, not printed.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from src.common.output import redact, configure_utf8_streams


def _message_text(payload):
    if isinstance(payload.get('message'), str):
        return payload['message']
    if isinstance(payload.get('content'), str):
        return payload['content']
    return '\n'.join(item.get('text', '') for item in payload.get('content', [])
                     if isinstance(item, dict) and item.get('type') in {'input_text', 'output_text', 'text'})


def inspect_sessions(paths, *, pattern=None, excerpt_chars=240, tool_excerpt_chars=0):
    if not 0 <= tool_excerpt_chars <= 2000:
        raise ValueError('tool_excerpt_chars must be between 0 and 2000')
    paths = list(paths)
    selected = list(dict.fromkeys(Path(p).resolve(strict=True) for p in paths))
    if any(not Path(p).is_absolute() for p in paths):
        raise ValueError('supply exact absolute JSONL paths')
    matcher = re.compile(pattern, re.I) if pattern else None
    report = {'files': [], 'user_candidates': [], 'tool_calls': [], 'limitations': [
        'Candidate excerpts need chronological and project-scope review.',
        'Copied child context and quoted reviews are not new independent requirements.',
        'Images, missing logs and runtime outcomes are not inferred from this extraction.',
        'A tool return or role artifact does not establish agent completion.',
        'Call/return order and excerpts locate evidence; inspect complete relevant inputs and outputs to judge source reads, writes and audits.']}
    for path in selected:
        if not path.is_file():
            raise ValueError('selected input is not a file: ' + str(path))
        before = path.stat()
        counts, calls, returns = Counter(), {}, {}
        session_id, child = None, False
        last_user = None
        with path.open('rb') as stream:
            line_number = 0
            while True:
                offset = stream.tell()
                raw = stream.readline()
                if not raw:
                    break
                line_number += 1
                try:
                    record = json.loads(raw)
                except (ValueError, UnicodeError):
                    counts['malformed_records'] += 1
                    continue
                counts['records'] += 1
                payload = record.get('payload') or {}
                if not isinstance(payload, dict):
                    continue
                kind = record.get('type')
                if kind == 'session_meta':
                    session_id = payload.get('id')
                    child = bool(payload.get('forked_from_id') or payload.get('parent_thread_id') or 'subagent' in str(payload.get('source', '')).lower())
                subtype = payload.get('type')
                if kind == 'response_item' and subtype in {'function_call', 'custom_tool_call'}:
                    call_id = payload.get('call_id') or payload.get('id')
                    calls[call_id or f'line:{line_number}'] = {'path': str(path), 'line': line_number, 'byte_offset': offset,
                        'timestamp': record.get('timestamp'), 'session_id': session_id,
                        'name': payload.get('name'), 'call_id': call_id}
                    if tool_excerpt_chars:
                        argument = payload.get('arguments', payload.get('input', ''))
                        argument = argument if isinstance(argument, str) else json.dumps(argument, ensure_ascii=False)
                        excerpt = redact(argument)
                        calls[call_id or f'line:{line_number}'].update(
                            argument_excerpt=excerpt[:tool_excerpt_chars],
                            argument_truncated=len(excerpt) > tool_excerpt_chars)
                elif kind == 'response_item' and subtype in {'function_call_output', 'custom_tool_call_output'}:
                    returns.setdefault(payload.get('call_id'), []).append({'path': str(path),
                        'line': line_number, 'byte_offset': offset, 'timestamp': record.get('timestamp')})
                is_user = ((kind == 'event_msg' and subtype == 'user_message') or
                           (kind == 'response_item' and subtype == 'message' and payload.get('role') == 'user'))
                if not is_user:
                    continue
                prose = _message_text(payload).strip()
                if not prose or prose.startswith(('<environment_context>', '<user_instructions>', '<turn_aborted>', '<automations_context>')):
                    counts['environment_or_automatic_records'] += 1
                    continue
                if re.fullmatch(r'<(recommended_plugins|external_codex_apps_open_page)>[\s\S]*</\1>', prose):
                    counts['environment_or_automatic_records'] += 1
                    continue
                digest = hashlib.sha256(prose.encode('utf-8')).hexdigest()
                if last_user and digest == last_user[0] and kind != last_user[1] and line_number - last_user[2] <= 5:
                    counts['adjacent_user_mirrors'] += 1
                    last_user = None
                    continue
                last_user = (digest, kind, line_number)
                counts['user_records'] += 1
                if matcher and not matcher.search(prose):
                    continue
                excerpt = redact(prose)
                report['user_candidates'].append({'path': str(path), 'session_id': session_id, 'line': line_number,
                    'byte_offset': offset, 'child_context': child, 'text_sha256': digest,
                    'excerpt': excerpt[:excerpt_chars], 'truncated': len(excerpt) > excerpt_chars})
        for call_id, call in calls.items():
            call['observed_state'] = 'tool_return_recorded' if call_id in returns else 'call_without_observed_return'
            call['result_locations'] = returns.get(call_id, [])
            report['tool_calls'].append(call)
        after = path.stat()
        report['files'].append({'path': str(path), 'session_id': session_id, 'bytes_read': before.st_size,
            'changed_during_read': (before.st_size, before.st_mtime_ns) != (after.st_size, after.st_mtime_ns),
            'child_context': child, 'counts': dict(counts)})
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('paths', nargs='+')
    parser.add_argument('--pattern')
    parser.add_argument('--excerpt-chars', type=int, default=240)
    parser.add_argument('--tool-excerpt-chars', type=int, default=0,
                        help='optional bounded, redacted tool input previews; result bodies stay in the source log')
    args = parser.parse_args(argv)
    if not 0 <= args.excerpt_chars <= 2000:
        parser.error('--excerpt-chars must be between 0 and 2000')
    if not 0 <= args.tool_excerpt_chars <= 2000:
        parser.error('--tool-excerpt-chars must be between 0 and 2000')
    print(json.dumps(inspect_sessions(args.paths, pattern=args.pattern, excerpt_chars=args.excerpt_chars,
                                     tool_excerpt_chars=args.tool_excerpt_chars), ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    configure_utf8_streams()
    raise SystemExit(main())
