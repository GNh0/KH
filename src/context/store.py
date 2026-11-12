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
