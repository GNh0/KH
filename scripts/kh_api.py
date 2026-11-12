"""Shared API credential CLI. Conversation-approved account sessions hand off secrets internally."""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.api_auth.manager import Manager
from src.api_auth.profile import fingerprint, validate_profile
from src.api_auth.security import AuthError
from src.api_auth.store import Store
from src.api_auth.transport import StreamLimits, Transport
from src.api_auth.input import clipboard_sequence, clear_owned_clipboard, read_credential
from src.api_auth.streaming import strict_json
from src.common.output import configure_utf8_streams


def handoff(store, service, args, action):
    plan = store.get_plan(args.approved_plan)
    current = store.get(service)
    if plan['service'] != service or plan['stage'] not in {'approved', 'candidate_saved'}:
        raise AuthError('approval_required', 'This plan cannot accept a credential handoff.')
    if plan['revision'] != current['revision'] or plan['profile_hash'] != fingerprint(current['profile']):
        raise AuthError('stale_plan', 'Account/session registration state changed before the handoff.')
    if args.clipboard and (plan['details'].get('clipboard_baseline') is None or args.clipboard_sequence == plan['details']['clipboard_baseline']):
        raise AuthError('clipboard_provenance_required', 'Prepare the scope with --clipboard-source before copying from the approved session. An unchanged or unrelated clipboard is not a handoff.')
    bundle = read_credential(stdin=args.stdin, clipboard=args.clipboard, expected_sequence=args.clipboard_sequence)
    result = None
    try:
        result = action(bundle)
        return result
    finally:
        if args.clipboard:
            saved = store.get(service)
            persisted = any(value and value.get('secret') == bundle['secret'] for value in (saved['active'], saved['pending']))
            if persisted:
                cleared = clear_owned_clipboard(args.clipboard_sequence)
                if result is not None:
                    result['clipboard_cleared_if_still_owned'] = cleared


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--loopback-fixture', action='store_true', help='allow HTTP only to literal loopback addresses for isolated tests')
    sub = parser.add_subparsers(dest='command', required=True)
    configure = sub.add_parser('configure', help='load a non-secret service profile')
    configure.add_argument('--file', required=True)
    init = sub.add_parser('init', help='create a basic OpenAI/Google Cloud service profile')
    init.add_argument('service')
    init.add_argument('--provider', choices=['openai', 'google-cloud'], required=True)
    init.add_argument('--check-url', help='required for Google Cloud: the actual API read-only check URL')
    for command in ('register', 'check', 'status', 'plan'):
        item = sub.add_parser(command)
        item.add_argument('service', nargs='?' if command == 'status' else None)
        if command == 'register':
            item.add_argument('--approved-plan', required=True)
            group = item.add_mutually_exclusive_group(required=True)
            group.add_argument('--stdin', action='store_true', help='credential JSON from a trusted session pipe, never argv')
            group.add_argument('--clipboard', action='store_true', help='consume the exact agent-owned copy from the approved account session')
            item.add_argument('--clipboard-sequence', type=int)
        if command == 'plan':
            item.add_argument('--reason', default='user_request', choices=['user_request', 'expiry_due', 'expired', 'authentication_rejected'])
            item.add_argument('--clipboard-source', action='store_true')
            item.add_argument('--source-url')
            item.add_argument('--session-label')
            item.add_argument('--account-label')
            item.add_argument('--create-key-if-needed', action='store_true', default=None)
    renew = sub.add_parser('renew', help='execute the exact plan after actual user approval')
    renew.add_argument('--approved-plan', required=True)
    source = renew.add_mutually_exclusive_group()
    source.add_argument('--stdin', action='store_true')
    source.add_argument('--clipboard', action='store_true')
    renew.add_argument('--clipboard-sequence', type=int)
    renew.add_argument('--replace-input', action='store_true', help='handoff a replacement obtained through the approved session')
    registration = sub.add_parser('registration-plan', help='review account/session registration scope before acquiring credentials')
    registration.add_argument('service')
    registration.add_argument('--source-url', required=True)
    registration.add_argument('--session-label', required=True)
    registration.add_argument('--account-label', required=True)
    registration.add_argument('--create-key-if-needed', action='store_true')
    registration.add_argument('--clipboard-source', action='store_true')
    sub.add_parser('clipboard-state', help='read the Windows clipboard sequence number without its content')
    authorize = sub.add_parser('authorize', help='record actual conversation approval before account/session credential acquisition')
    authorize.add_argument('--plan', required=True)
    registration_authorize = sub.add_parser('authorize-registration', help='registration-only alias of authorize')
    registration_authorize.add_argument('--plan', required=True)
    metadata = sub.add_parser('record-metadata', help='record verified non-secret metadata for the same registered credential')
    metadata.add_argument('service')
    metadata.add_argument('--expected-revision', type=int, required=True)
    metadata.add_argument('--expires-at', type=float, help='verified Unix expiry timestamp, never inferred from key shape')
    metadata.add_argument('--remote-id', help='observed non-secret remote identifier for this exact key')
    request = sub.add_parser('request', help='call the registered API without returning its credential')
    request.add_argument('service')
    request.add_argument('--method', default='GET', choices=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'])
    request.add_argument('--path', required=True)
    request.add_argument('--api-base', help='reuse this credential at an allowed API base; Google Cloud permits HTTPS Google API hosts')
    request.add_argument('--body-file', help='UTF-8 JSON request body, not an authentication file')
    stream = sub.add_parser('stream', help='stream SSE, NDJSON or UTF-8 HTTP events through the registered credential')
    stream.add_argument('service')
    stream.add_argument('--method', default='GET', choices=['GET', 'POST', 'PUT', 'PATCH', 'DELETE', 'HEAD'])
    stream.add_argument('--path', required=True)
    stream.add_argument('--api-base')
    stream.add_argument('--body-file', help='public JSON request parameters, not credentials')
    stream.add_argument('--protocol', choices=['auto', 'sse', 'ndjson', 'text'], default='auto')
    stream.add_argument('--mapping', help='non-secret event presentation mapping JSON')
    stream.add_argument('--output-dir', help='absolute artifact directory outside project sources')
    stream.add_argument('--timeout-seconds', type=float, default=180)
    stream.add_argument('--idle-timeout', type=float, default=30)
    stream.add_argument('--max-bytes', type=int, default=64 * 1024 * 1024)
    stream.add_argument('--max-event-bytes', type=int, default=8 * 1024 * 1024)
    stream.add_argument('--max-events', type=int, default=10000)
    forget = sub.add_parser('forget', help='remove local credentials; no remote key is revoked')
    forget.add_argument('service')
    forget.add_argument('--confirm-service', required=True)
    reconcile = sub.add_parser('reconcile', help='record an actually verified ambiguous-issuance inventory outcome')
    reconcile.add_argument('--plan', required=True)
    reconcile.add_argument('--outcome', choices=['not-issued', 'orphan-revoked'], required=True)
    reconcile.add_argument('--evidence-reference', required=True, help='non-secret source/request reference, never a credential')
    args = parser.parse_args(argv)
    try:
        if args.command == 'clipboard-state':
            print(json.dumps({'sequence': clipboard_sequence(), 'content_read': False}))
            return 0
        store = Store()
        manager = Manager(store, Transport(loopback=args.loopback_fixture))
        if args.command == 'configure':
            body = Path(args.file).read_text(encoding='utf-8-sig')
            if len(body) > 32000:
                raise AuthError('invalid_profile', 'Profile exceeds the size bound.')
            profile = validate_profile(json.loads(body), loopback=args.loopback_fixture)
            store.configure(profile)
            result = {'status': 'configured', 'service': profile['id']}
        elif args.command == 'init':
            if args.provider == 'openai':
                profile = {'id': args.service, 'provider': 'openai', 'base_url': 'https://api.openai.com/v1', 'check_path': '/models'}
            else:
                if not args.check_url:
                    raise AuthError('service_endpoint_required', 'Specify the Google Cloud API actually used by this task with --check-url; different Cloud APIs have different permissions.')
                parts = urlsplit(args.check_url)
                profile = {'id': args.service, 'provider': 'google-cloud', 'base_url': parts.scheme + '://' + parts.netloc,
                           'check_path': parts.path + ('?' + parts.query if parts.query else ''), 'auth': 'header'}
            profile = validate_profile(profile, loopback=args.loopback_fixture)
            store.configure(profile)
            result = {'status': 'configured', 'service': profile['id']}
        elif args.command == 'register':
            plan = store.get_plan(args.approved_plan)
            if plan['service'] != args.service or plan['details'].get('purpose') != 'registration':
                raise AuthError('approval_required', 'Use the registration plan approved for this exact account/session.')
            result = handoff(store, args.service, args,
                             lambda bundle: manager.register(args.service, bundle, approved_plan=args.approved_plan))
        elif args.command == 'registration-plan':
            result = manager.prepare_registration(args.service, source_url=args.source_url, session_label=args.session_label,
                account_label=args.account_label, create_key=args.create_key_if_needed,
                clipboard_baseline=clipboard_sequence() if args.clipboard_source else None)
        elif args.command == 'authorize-registration':
            result = manager.authorize_registration(args.plan)
        elif args.command == 'authorize':
            result = manager.authorize(args.plan)
        elif args.command == 'record-metadata':
            result = manager.record_metadata(args.service, revision=args.expected_revision, expires_at=args.expires_at, remote_id=args.remote_id)
        elif args.command == 'check':
            result = manager.check(args.service)
        elif args.command == 'status':
            result = manager.status(args.service) if args.service else {'services': [manager.status(name) for name in store.ids()]}
        elif args.command == 'plan':
            result = manager.prepare(args.service, args.reason, clipboard_baseline=clipboard_sequence() if args.clipboard_source else None,
                                     source_url=args.source_url, session_label=args.session_label, account_label=args.account_label,
                                     create_key=args.create_key_if_needed)
        elif args.command == 'renew':
            plan = store.get_plan(args.approved_plan)
            if plan['stage'] in {'done', 'reconciled', 'superseded', 'abandoned'}:
                raise AuthError('plan_consumed', 'This maintenance plan already completed.')
            profile = manager.entry(plan['service'])['profile']
            needs_input = profile['rotation']['mode'] == 'manual' or plan['details'].get('purpose') == 'registration'
            if needs_input and (args.replace_input or (plan['stage'] in {'planned', 'approved'} and not manager.entry(plan['service'])['pending'])):
                result = handoff(store, plan['service'], args, lambda bundle: manager.maintain(args.approved_plan, replacement=bundle))
            else:
                result = manager.maintain(args.approved_plan)
        elif args.command == 'forget':
            if args.confirm_service != args.service:
                raise AuthError('confirmation_required', 'Confirm the exact local service id to remove.')
            with store.lease(args.service):
                result = store.forget(args.service)
        elif args.command == 'reconcile':
            result = manager.reconcile(args.plan, args.outcome, args.evidence_reference)
        elif args.command == 'stream':
            mapping = None
            if args.mapping:
                with Path(args.mapping).open('r', encoding='utf-8-sig') as file:
                    text = file.read(64001)
                if len(text) > 64000:
                    raise AuthError('invalid_stream_mapping', 'Stream mapping exceeds the size bound.')
                mapping = strict_json(text)
            body = None
            if args.body_file:
                with Path(args.body_file).open('r', encoding='utf-8-sig') as file:
                    text = file.read(1024 * 1024 + 1)
                if len(text) > 1024 * 1024:
                    raise AuthError('request_too_large', 'Streaming JSON request exceeds the input bound.')
                body = strict_json(text)
            limits = StreamLimits(args.timeout_seconds, args.idle_timeout, args.max_bytes, args.max_event_bytes, args.max_events)
            result = manager.stream(args.service, args.method, args.path, body, protocol=args.protocol, mapping=mapping,
                output_dir=args.output_dir, limits=limits, selected_base=args.api_base,
                sink=lambda record: print(json.dumps(record, ensure_ascii=False, allow_nan=False), flush=True))
            return 130 if result['status'] == 'cancelled' else 0 if result['status'] in {'completed', 'stream_closed'} else 2
        else:
            body = json.loads(Path(args.body_file).read_text(encoding='utf-8-sig')) if args.body_file else None
            result = manager.request(args.service, args.method, args.path, body, selected_base=args.api_base)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2 if result.get('status') in {'authentication_rejected', 'permission_denied', 'quota_or_rate_limit',
            'service_error', 'request_error', 'redirect_blocked', 'registration_required',
            'renewal_approval_required', 'reconnection_pending', 'revocation_pending', 'maintenance_in_progress'} else 0
    except BrokenPipeError:
        return 1
    except AuthError as error:
        print(json.dumps({'status': error.code, 'message': str(error)}, ensure_ascii=False))
        return 1
    except Exception as error:
        # Never emit input, raw provider responses, credential-bearing exceptions or tracebacks.
        print(json.dumps({'status': 'unverified_error', 'type': type(error).__name__,
                          'message': 'Operation failed. Credential values and raw diagnostics were withheld.'}))
        return 1


if __name__ == '__main__':
    configure_utf8_streams()
    raise SystemExit(main())
