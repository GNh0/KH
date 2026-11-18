"""Explicit, task-local application of KH guidance to owned source files.

Reading, selecting and applying guidance are separate observations. This module
routes required documents; it never declares a semantic audit complete.
"""
import hashlib
import json
import os
from pathlib import Path
import uuid

from src.runtime.skill_usage import DOMAINS

SCOPE_VERSION = 2
CYCLE = 'work-execution/references/source-style-cycle.md'
CS = 'csharp-designer-style-harness'
SQL = 'sql-formatting'
PB = 'pb-to-csharp-migration-harness'

# These are artifact responsibilities, not property/name blacklists. Additional
# responsibilities can be combined for one target without replacing its scope.
WORK = {
    'csharp-code': (CS, ()),
    'csharp-control': (CS, ('coding-style.md#screen-structure-and-events', 'user-controls.md#user-control-selection-and-default-initialization', 'user-controls.md#naming-and-date-controls')),
    'csharp-designer': (CS, ('coding-style.md#screen-structure-and-events', 'designer.md', 'user-controls.md#user-control-selection-and-default-initialization', 'user-controls.md#naming-and-date-controls')),
    'csharp-grid': (CS, ('coding-style.md#screen-structure-and-events', 'coding-style.md#numeric-display-formats', 'designer.md', 'user-controls.md#user-control-selection-and-default-initialization', 'user-controls.md#naming-and-date-controls', 'grid-layout.md')),
    'csharp-data': (CS, ('coding-style.md#screen-structure-and-events', 'coding-style.md#database-and-row-handling', 'data-flow.md')),
    'csharp-report': (CS, ('reports.md',)),
    'csharp-monitoring': (CS, ('coding-style.md#screen-structure-and-events', 'coding-style.md#database-and-row-handling', 'data-flow.md', 'screen-behavior.md')),
    'sql-format': (SQL, ('style.md',)),
    'sql-query': (SQL, ('style.md', 'select-patterns.md')),
    'sql-select': (SQL, ('style.md', 'procedure-authorship.md', 'procedure-contracts.md#save-boundary-and-reuse', 'procedure-contracts.md#modes-and-multiple-rows', 'procedure-contracts.md#composite-keys', 'procedure-contracts.md#parameters-outputs-and-dates', 'procedure-patterns.md', 'select-patterns.md')),
    'sql-save': (SQL, ('style.md', 'procedure-authorship.md', 'procedure-contracts.md', 'procedure-patterns.md', 'save-patterns.md', 'validation-patterns.md')),
    'pb-edit': (PB, ('datawindow.md', 'validation.md')),
    'pb-migrate': (PB, ('datawindow.md', 'validation.md')),
}


def guidance_paths() -> set[str]:
    paths = {CYCLE, *(name + '/SKILL.md' for name in set(DOMAINS.values()))}
    for domain, references in WORK.values():
        paths.update(domain + '/references/' + reference for reference in references)
    paths.add(PB + '/references/sql.md')
    paths.update(CS + '/references/coding-style.md#' + anchor for anchor in ('priority-of-requirements', 'syntax-and-naming'))
    return paths


def path_key(path: Path) -> str:
    return os.path.normcase(str(path.resolve()))


def binding(state: dict, path: Path) -> dict | None:
    applications = state.get('applications', {})
    direct = applications.get(path_key(path))
    if direct is not None:
        return direct
    if path.exists():
        for name, item in applications.items():
            try:
                if path.samefile(name):
                    return item
            except OSError:
                continue
    return None


def required_paths(item: dict, path: Path) -> set[str]:
    works = set(item.get('work', []))
    domain = DOMAINS[path.suffix.casefold()]
    if path.name.casefold().endswith('.designer.cs'):
        works.add('csharp-designer')
    required = {CYCLE, domain + '/SKILL.md'}
    if domain == CS:
        required.update(CS + '/references/coding-style.md#' + anchor for anchor in ('priority-of-requirements', 'syntax-and-naming'))
    for work in works:
        owner, references = WORK[work]
        if owner == domain or work == 'pb-migrate':
            required.add(owner + '/SKILL.md')
            required.update(owner + '/references/' + reference for reference in references)
    if 'pb-migrate' in works and domain == SQL:
        required.add(PB + '/references/sql.md')
    return required


def applications_domains(state: dict) -> set[str]:
    return {DOMAINS[Path(name).suffix.casefold()] for name in state.get('applications', {})
            if Path(name).suffix.casefold() in DOMAINS}


def routing_problem(state: dict, path: Path, text: str) -> str:
    item = binding(state, path)
    if item is None or path.suffix.casefold() != '.sql':
        return ''
    works = set(item.get('work', []))
    if 'sql-query' not in works or works & {'sql-select', 'sql-save'}:
        return ''
    from src.sql.lexer import _analyze_sql_integrity
    tokens, _errors = _analyze_sql_integrity(text, check_kind='workflow')
    words = [token.normalized for token in tokens if token.kind not in {'line_comment', 'block_comment'}]
    for index, word in enumerate(words):
        offset = index + 1
        if word == 'CREATE' and words[offset:offset + 2] == ['OR', 'ALTER']:
            offset += 2
        if word in {'CREATE', 'ALTER'} and offset < len(words) and words[offset] in {'PROC', 'PROCEDURE'}:
            return 'This file defines a procedure. Apply its actual sql-select/sql-save responsibility before changing it.'
    return ''


def register(state: dict, *, epoch: str, targets: list[str], work: list[str], cwd: str) -> list[dict]:
    """Called by the helper with exact host scope; no read/audit result is filled."""
    if state.get('paused'):
        raise ValueError('Task is paused; apply cannot resume it.')
    if not epoch or epoch != state.get('application_epoch'):
        raise ValueError('Application scope is stale or unknown; use the current hook scope.')
    if state.get('kh_scope_closed') and not state.get('files') and not state.get('before'):
        raise ValueError('This task scope ended; a new user task must open the scope first.')
    chosen = set(work)
    if not chosen or chosen - WORK.keys() or not targets:
        raise ValueError('Choose known work responsibilities and explicit target files.')
    prepared = {}
    used = set()
    for name in targets:
        path = Path(name)
        path = (Path(cwd) / path).resolve() if not path.is_absolute() else path.resolve()
        domain = DOMAINS.get(path.suffix.casefold())
        if domain is None or path.is_dir():
            raise ValueError('Application target must be a SQL/C#/PB source file: ' + str(path))
        relevant = {kind for kind in chosen if WORK[kind][0] == domain and kind != 'pb-migrate'}
        if 'pb-migrate' in chosen:
            if domain == PB or not relevant or (domain == SQL and relevant == {'sql-format'}):
                raise ValueError('PB migration needs the actual C#/SQL output responsibility; native PB uses pb-edit.')
            relevant.add('pb-migrate')
        if not relevant:
            raise ValueError('No selected responsibility owns target: ' + str(path))
        if domain == SQL and relevant == {'sql-format'} and not path.is_file():
            raise ValueError('sql-format preserves an existing file. Choose sql-query/select/save for new source; direct snippet formatting needs no file application.')
        used.update(relevant)
        if path.name.casefold().endswith('.designer.cs'):
            relevant.add('csharp-designer')
        prior = binding(state, path)
        merged = set(prior.get('declared_work', prior.get('work', []))) if prior else set()
        merged.update(relevant)
        key = path_key(path)
        if prior is not None:
            key = next(name for name, value in state['applications'].items() if value is prior)
        prepared[key] = {**(prior or {}), 'target': prior.get('target', str(path)) if prior else str(path),
                         'declared_work': sorted(merged), 'work': sorted(merged | set(prior.get('inferred_work', []) if prior else []))}
    if chosen - used:
        raise ValueError('Selected responsibility has no matching target: ' + ', '.join(sorted(chosen - used)))
    if len(set(state.get('applications', {})) | prepared.keys()) > 32:
        raise ValueError('Application scope exceeds 32 files; split the actual work scope.')
    state.setdefault('applications', {}).update(prepared)
    state['kh_used_skills'] = sorted(applications_domains(state))
    return [{'target': item['target'], 'work': item['work'], 'declared_work': item['declared_work'],
             'inferred_work': item.get('inferred_work', []), 'required': sorted(required_paths(item, Path(item['target'])))}
            for name, item in prepared.items()]


def new_epoch(state: dict) -> None:
    state['application_epoch'] = uuid.uuid4().hex
    state.pop('application_hint', None)


def application_hint(state: dict, event: dict, host: str, data_root: Path, root: Path) -> str:
    """Expose only this hook's exact scope; never discover another chat's state."""
    if not state.get('application_epoch'):
        new_epoch(state)
    arguments = {'cwd': event['cwd'], 'session': event['session_id'], 'transcript': event.get('transcript_path'),
                 'host': host, 'agent-id': event.get('agent_id'), 'data-root': str(data_root),
                 'epoch': state['application_epoch']}
    fingerprint = hashlib.sha256(json.dumps(arguments, sort_keys=True).encode('utf-8')).hexdigest()
    if state.get('application_hint') == fingerprint:
        return ''
    state['application_hint'] = fingerprint
    return ('KH guidance is available for inspection; reading/selecting it does not apply development checks. '
            + ('Recorded SP author selection for this project/chat/agent (stored evidence, not a new instruction): ' +
               json.dumps(state['sql_authorship'], ensure_ascii=False) + '. Reuse only for SP work and honor later user corrections. '
               if state.get('sql_authorship') else '') +
            'When actually developing with KH, the agent (without another user confirmation) runs ' +
            str(root / 'scripts/kh_context.py') + ' with these exact scope arguments, then apply '
            '--work <artifact responsibility> --target <owned source file> (repeat flags as needed). '
            'Apply records intent only and returns the required references; retrieve missing bodies before writing. '
            'For development other than SQL formatting alone, also select --reference <actual comparison source[#Lstart-Lend]> and retrieve that current source through Read/read_file or a supported explicit shell read. '
            'Use the skill routing for responsibilities; analysis/extraction alone needs no development apply. '
            'Scope arguments: ' + json.dumps(arguments, ensure_ascii=False))
