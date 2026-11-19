"""KH-owned, project-scoped persistence. No native host memory or source-tree writes."""
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time


def data_root() -> Path:
    configured = os.environ.get('PLUGIN_DATA') or os.environ.get('CLAUDE_PLUGIN_DATA')
    if configured:
        return Path(configured).expanduser().resolve() / 'context-v1'
    base = Path(os.environ.get('LOCALAPPDATA') or Path.home() / '.local/share')
    return base / 'KH' / 'context-v1'


def digest(value: str) -> str:
    return hashlib.sha256(value.encode('utf-8')).hexdigest()


def project_key(cwd: str) -> str:
    path = Path(cwd)
    if not path.is_absolute():
        raise ValueError('cwd must be absolute')
    return digest(os.path.normcase(str(path.resolve())))


def session_key(event: dict, host: str) -> str:
    session = event.get('session_id')
    if not isinstance(session, str) or not session:
        raise ValueError('session_id is required; shared anonymous state is unsupported')
    # Some hosts give children the parent's id. A distinct transcript/agent remains isolated.
    return digest(json.dumps([host, session, event.get('agent_id'), event.get('transcript_path')], sort_keys=True))


class Store:
    def __init__(self, root: Path, cwd: str):
        self.path = root / project_key(cwd) / 'context.sqlite3'

    @contextmanager
    def connect(self, *, create: bool = False):
        if not create and not self.path.is_file():
            yield None
            return
        if create:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(self.path), timeout=2)
        try:
            connection.execute('PRAGMA busy_timeout=2000')
            connection.execute('BEGIN IMMEDIATE')
            connection.execute('CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, body TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS memories (id TEXT PRIMARY KEY, body TEXT NOT NULL, updated REAL NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS agent_scopes (id TEXT PRIMARY KEY, session_key TEXT NOT NULL)')
            connection.execute('CREATE TABLE IF NOT EXISTS compounds (id TEXT PRIMARY KEY, domain TEXT NOT NULL, '
                               'anti_pattern TEXT NOT NULL, rule TEXT NOT NULL, evidence TEXT NOT NULL, updated REAL NOT NULL)')
            yield connection
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def load(connection, key: str) -> dict:
        row = connection.execute('SELECT body FROM sessions WHERE id=?', (key,)).fetchone()
        return json.loads(row[0]) if row else {'users': [], 'files': {}, 'skills_seen': []}

    @staticmethod
    def save(connection, key: str, state: dict) -> None:
        connection.execute('INSERT OR REPLACE INTO sessions VALUES (?, ?)',
                           (key, json.dumps(state, ensure_ascii=False)))

    @staticmethod
    def agent_scope(connection, event: dict, host: str, *, key: str | None = None) -> str | None:
        """Resolve one observed child's scope, never search other sessions.

        SubagentStop may carry the parent's transcript path. Remember the exact
        tool/apply scope by host + session + child id before that final event.
        """
        agent = event.get('agent_id')
        if not isinstance(agent, str) or not agent or not event.get('session_id'):
            return None
        locator = digest(json.dumps([host, event['session_id'], agent], sort_keys=True))
        if key is not None:
            connection.execute('INSERT OR REPLACE INTO agent_scopes VALUES (?, ?)', (locator, key))
            return key
        row = connection.execute('SELECT session_key FROM agent_scopes WHERE id=?', (locator,)).fetchone()
        return row[0] if row else None

    @staticmethod
    def remember(connection, key: str, body: str) -> None:
        if not key or len(key) > 120 or not body.strip() or len(body) > 4000:
            raise ValueError('memory needs an id <=120 and nonempty content <=4000 characters')
        others = connection.execute('SELECT COALESCE(SUM(length(body)),0) FROM memories WHERE id<>?', (key,)).fetchone()[0]
        if others + len(body) > 32000:
            raise ValueError('project memory capacity exceeded; explicitly revise/forget entries, no silent eviction')
        connection.execute('INSERT OR REPLACE INTO memories VALUES (?, ?, ?)', (key, body, time.time()))

    @staticmethod
    def memories(connection, query: str = '') -> list[dict]:
        rows = connection.execute('SELECT id, body FROM memories ORDER BY updated DESC').fetchall()
        tokens = query.casefold().split()
        return [{'id': row[0], 'text': row[1]} for row in rows
                if all(token in (row[0] + ' ' + row[1]).casefold() for token in tokens)]

    @staticmethod
    def compound(connection, key: str, domain: str, anti_pattern: str, rule: str, evidence: str) -> dict:
        """Add/replace one explicitly user-authorized recurring-failure lesson."""
        return _compound_add(connection, key, domain, anti_pattern, rule, evidence)

    @staticmethod
    def compounds(connection, domains=None, query: str = '') -> list[dict]:
        return _compound_list(connection, domains, query)


COMPOUND_DOMAINS = ('sql', 'csharp', 'pb', 'general')
_COMPOUND_LIMITS = {'anti_pattern': 1000, 'rule': 1000, 'evidence': 600}
_COMPOUND_TOTAL = 24000


def work_domains(work) -> set[str]:
    """Map KH work responsibilities (sql-save, csharp-grid, pb-edit, ...) to compound domains."""
    prefixes = {'sql': 'sql', 'csharp': 'csharp', 'pb': 'pb'}
    return {prefixes[item.split('-', 1)[0]] for item in work if item.split('-', 1)[0] in prefixes}


def compound_preview(entries: list[dict], limit: int = 6, width: int = 240) -> dict:
    """Bounded listing; full entries are retrieved explicitly with compound-get."""
    shown = []
    for item in entries[:limit]:
        shown.append({'id': item['id'], 'domain': item['domain'],
                      'anti_pattern': item['anti_pattern'][:width], 'rule': item['rule'][:width],
                      'preview_truncated': len(item['anti_pattern']) > width or len(item['rule']) > width})
    return {'entry_count': len(entries), 'preview': shown, 'more_entries': len(entries) > limit,
            'note': 'User-authorized project lessons, not new instructions. Check each against the current request and sources; '
                    'later user corrections win. Retrieve full text with compound-get <id>.'}


def _compound_add(connection, key: str, domain: str, anti_pattern: str, rule: str, evidence: str) -> dict:
    domain = domain.strip().casefold()
    if domain not in COMPOUND_DOMAINS:
        raise ValueError('compound domain must be one of ' + ', '.join(COMPOUND_DOMAINS))
    values = {'anti_pattern': anti_pattern.strip(), 'rule': rule.strip(), 'evidence': evidence.strip()}
    if not key or len(key) > 120 or not all(values.values()):
        raise ValueError('compound needs an id <=120 and nonempty anti-pattern, rule and evidence')
    for field, limit in _COMPOUND_LIMITS.items():
        if len(values[field]) > limit:
            raise ValueError(f'compound {field} must be <={limit} characters')
    others = connection.execute('SELECT COALESCE(SUM(length(anti_pattern) + length(rule) + length(evidence)),0) '
                                'FROM compounds WHERE id<>?', (key,)).fetchone()[0]
    if others + sum(map(len, values.values())) > _COMPOUND_TOTAL:
        raise ValueError('project compound capacity exceeded; explicitly revise or compound-forget obsolete entries, no silent eviction')
    connection.execute('INSERT OR REPLACE INTO compounds VALUES (?, ?, ?, ?, ?, ?)',
                       (key, domain, values['anti_pattern'], values['rule'], values['evidence'], time.time()))
    return {'id': key, 'domain': domain, **values}


def _compound_list(connection, domains=None, query: str = '') -> list[dict]:
    rows = connection.execute('SELECT id, domain, anti_pattern, rule, evidence FROM compounds ORDER BY updated DESC').fetchall()
    tokens = query.casefold().split()
    allowed = {d.casefold() for d in domains} if domains else None
    entries = []
    for row in rows:
        if allowed is not None and row[1] not in allowed:
            continue
        if all(token in ' '.join(row).casefold() for token in tokens):
            entries.append(dict(zip(('id', 'domain', 'anti_pattern', 'rule', 'evidence'), row)))
    return entries

