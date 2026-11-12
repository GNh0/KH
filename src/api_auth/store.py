"""Shared user storage outside projects and plugin caches; secret columns are DPAPI blobs."""
from contextlib import contextmanager
import json
import hashlib
import os
from pathlib import Path
import sqlite3
import time
import uuid

from src.api_auth.profile import fingerprint, identifier
from src.api_auth.security import AuthError, UserCipher


def data_directory() -> Path:
    selected = os.environ.get('KH_API_DATA')
    if selected:
        path = Path(selected).expanduser()
        if not path.is_absolute():
            raise AuthError('invalid_storage', 'KH_API_DATA must be absolute.')
        return path
    home = os.environ.get('LOCALAPPDATA')
    if not home:
        raise AuthError('secure_storage_unavailable', 'Windows LOCALAPPDATA is unavailable.')
    return Path(home) / 'KH' / 'api-auth-v1'


class Store:
    def __init__(self, root: Path | None = None):
        self.cipher = UserCipher()
        root = root or data_directory()
        if not root.is_absolute():
            raise AuthError('invalid_storage', 'Credential storage directory must be absolute.')
        for path in [root, *root.parents]:
            if path.exists() and getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                raise AuthError('invalid_storage', 'Credential storage cannot traverse a reparse point.')
        root.mkdir(parents=True, exist_ok=True)
        self.path = root / 'credentials.sqlite3'
        if self.path.is_symlink():
            raise AuthError('invalid_storage', 'Credential database cannot be a symbolic link.')
        with self.connect(write=True) as db:
            db.execute('CREATE TABLE IF NOT EXISTS services (id TEXT PRIMARY KEY, profile TEXT NOT NULL, active BLOB, pending BLOB, revision INTEGER NOT NULL DEFAULT 0)')
            db.execute('CREATE TABLE IF NOT EXISTS plans (id TEXT PRIMARY KEY, service TEXT NOT NULL, body TEXT NOT NULL)')

    @contextmanager
    def connect(self, *, write=False):
        db = sqlite3.connect(str(self.path), timeout=3, isolation_level=None)
        try:
            if write:
                db.execute('BEGIN IMMEDIATE')
            yield db
            if write:
                db.commit()
        except BaseException:
            if write:
                db.rollback()
            raise
        finally:
            db.close()

    def configure(self, profile: dict):
        with self.connect(write=True) as db:
            row = db.execute('SELECT profile, active, pending FROM services WHERE id=?', (profile['id'],)).fetchone()
            if row and json.loads(row[0]) == profile:
                return
            if row and (row[1] or row[2]) and json.loads(row[0]) != profile:
                raise AuthError('profile_in_use', 'A registered credential profile is immutable. Register a new service id for a changed target or authority.')
            db.execute('INSERT INTO services(id,profile) VALUES (?,?) ON CONFLICT(id) DO UPDATE SET profile=excluded.profile,revision=revision+1',
                       (profile['id'], json.dumps(profile, sort_keys=True)))

    def get(self, service: str) -> dict:
        identifier(service)
        with self.connect() as db:
            row = db.execute('SELECT profile,active,pending,revision FROM services WHERE id=?', (service,)).fetchone()
        if row is None:
            raise AuthError('service_not_configured', 'Configure this service before registering a credential.')
        return {'profile': json.loads(row[0]), 'active': self.cipher.open(row[1]) if row[1] else None,
                'pending': self.cipher.open(row[2]) if row[2] else None, 'revision': row[3]}

    def ids(self) -> list[str]:
        with self.connect() as db:
            return [row[0] for row in db.execute('SELECT id FROM services ORDER BY id')]

    def forget(self, service: str) -> dict:
        current = self.get(service)
        followup = []
        if current['active']:
            followup.append({'active_remote_id': current['active'].get('remote_id')})
        if current['pending']:
            followup.append({'pending_remote_id': current['pending'].get('remote_id')})
        with self.connect(write=True) as db:
            rows = db.execute('SELECT id,body FROM plans WHERE service=?', (service,)).fetchall()
            for plan_id, body in rows:
                plan = json.loads(body)
                if plan['stage'] == 'issuing' and not plan.get('operation'):
                    followup.append({'plan_id': plan_id, 'state': 'issuance_unknown', 'blocks_new_issuance': True})
                elif plan['stage'] in {'approved', 'issuing', 'candidate_saved', 'active_saved'}:
                    plan.update(stage='abandoned', abandoned_at=time.time())
                    db.execute('UPDATE plans SET body=? WHERE id=?', (json.dumps(plan), plan_id))
                    followup.append({'plan_id': plan_id, 'state': 'abandoned', 'operation': plan.get('operation'),
                                     'old_remote_id': plan['details'].get('old_remote_id')})
                elif plan['stage'] != 'abandoned':
                    db.execute('DELETE FROM plans WHERE id=?', (plan_id,))
            db.execute('UPDATE services SET active=NULL,pending=NULL,revision=revision+1 WHERE id=?', (service,))
        return {'status': 'local_credential_removed', 'remote_keys_revoked': False,
                'remote_followup': followup, 'note': 'Local deletion does not remove remote keys. Inspect the listed provider resources/operations as needed.'}

    def save(self, service: str, bundle: dict, revision: int, *, pending=False):
        blob = self.cipher.seal(bundle)
        column = 'pending' if pending else 'active'
        with self.connect(write=True) as db:
            result = db.execute('UPDATE services SET ' + column + '=?,revision=revision+1 WHERE id=? AND revision=?',
                                (blob, service, revision))
            if result.rowcount != 1:
                raise AuthError('credential_changed', 'Credential state changed; inspect it before continuing.')

    def promote(self, service: str, revision: int):
        with self.connect(write=True) as db:
            result = db.execute('UPDATE services SET active=pending,pending=NULL,revision=revision+1 WHERE id=? AND revision=? AND pending IS NOT NULL', (service, revision))
            if result.rowcount != 1:
                raise AuthError('credential_changed', 'Pending credential changed before activation.')

    def plan(self, service: str, details: dict, current: dict) -> dict:
        value = {'id': uuid.uuid4().hex, 'service': service, 'profile_hash': fingerprint(current['profile']),
                 'revision': current['revision'], 'expires_at': time.time() + 900, 'stage': 'planned', 'details': details}
        with self.connect(write=True) as db:
            actual = db.execute('SELECT profile,revision FROM services WHERE id=?', (service,)).fetchone()
            if actual is None or actual[1] != current['revision'] or fingerprint(json.loads(actual[0])) != value['profile_hash']:
                raise AuthError('stale_plan', 'Credential state changed while the plan was prepared; prepare a fresh plan.')
            db.execute('INSERT INTO plans VALUES (?,?,?)', (value['id'], service, json.dumps(value)))
        return value

    def get_plan(self, plan_id: str) -> dict:
        if not isinstance(plan_id, str) or len(plan_id) != 32:
            raise AuthError('approval_required', 'Use the exact maintenance plan id that the user approved.')
        with self.connect() as db:
            row = db.execute('SELECT body FROM plans WHERE id=?', (plan_id,)).fetchone()
        if not row:
            raise AuthError('approval_required', 'Maintenance plan was not found.')
        return json.loads(row[0])

    def source_scope(self, service: str) -> dict | None:
        with self.connect() as db:
            rows = db.execute('SELECT body FROM plans WHERE service=? ORDER BY rowid DESC', (service,)).fetchall()
        for row in rows:
            plan = json.loads(row[0])
            if plan['stage'] == 'done' and plan['details'].get('purpose') in {'registration', 'manual_replacement'}:
                return {key: plan['details'][key] for key in ('source_url', 'session_label', 'account_label', 'create_key_if_needed')}
        return None

    def unfinished(self, service: str, *, excluding=None) -> dict | None:
        with self.connect() as db:
            rows = db.execute('SELECT body FROM plans WHERE service=? ORDER BY rowid', (service,)).fetchall()
        for row in rows:
            value = json.loads(row[0])
            if value['id'] != excluding and value['stage'] in {'approved', 'issuing', 'candidate_saved', 'active_saved'}:
                return value
        return None

    def update_plan(self, plan: dict):
        with self.connect(write=True) as db:
            db.execute('UPDATE plans SET body=? WHERE id=?', (json.dumps(plan), plan['id']))

    def approve(self, plan: dict, approval_source: str):
        updated = {**plan, 'stage': plan.get('resume_stage', 'approved'),
                   'approved_at': time.time(), 'approval_source': approval_source}
        with self.connect(write=True) as db:
            if plan.get('resume_of'):
                row = db.execute('SELECT body FROM plans WHERE id=?', (plan['resume_of'],)).fetchone()
                previous = json.loads(row[0]) if row else None
                if previous is None or previous['stage'] != plan['resume_stage']:
                    raise AuthError('stale_plan', 'The maintenance operation changed before its new authority was approved.')
                previous['stage'] = 'superseded'
                db.execute('UPDATE plans SET body=? WHERE id=?', (json.dumps(previous), previous['id']))
            db.execute('UPDATE plans SET body=? WHERE id=?', (json.dumps(updated), plan['id']))
        plan.update(updated)

    def candidate(self, plan: dict, bundle: dict):
        blob = self.cipher.seal(bundle)
        updated = {**plan, 'revision': plan['revision'] + 1, 'stage': 'candidate_saved'}
        with self.connect(write=True) as db:
            result = db.execute('UPDATE services SET pending=?,revision=revision+1 WHERE id=? AND revision=?',
                                (blob, plan['service'], plan['revision']))
            if result.rowcount != 1:
                raise AuthError('credential_changed', 'Credential state changed before the candidate was saved.')
            db.execute('UPDATE plans SET body=? WHERE id=?', (json.dumps(updated), plan['id']))
        plan.update(updated)

    def activate(self, plan: dict):
        updated = {**plan, 'revision': plan['revision'] + 1, 'stage': 'active_saved'}
        with self.connect(write=True) as db:
            result = db.execute('UPDATE services SET active=pending,pending=NULL,revision=revision+1 WHERE id=? AND revision=? AND pending IS NOT NULL',
                                (plan['service'], plan['revision']))
            if result.rowcount != 1:
                raise AuthError('credential_changed', 'Pending credential changed before activation.')
            db.execute('UPDATE plans SET body=? WHERE id=?', (json.dumps(updated), plan['id']))
        plan.update(updated)

    @contextmanager
    def lease(self, service: str):
        import msvcrt
        # Windows releases the byte-range lock if this process exits, without age-based takeover.
        name = 'lease-' + hashlib.sha256(service.encode()).hexdigest() + '.lock'
        handle = (self.path.parent / name).open('a+b')
        try:
            if handle.tell() == 0:
                handle.write(b'0')
                handle.flush()
            handle.seek(0)
            try:
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            except OSError:
                raise AuthError('service_busy', 'Another credential maintenance operation owns this service.') from None
            try:
                yield
            finally:
                handle.seek(0)
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            handle.close()
