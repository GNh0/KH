"""Compare recognizable query/save transport with an explicitly supplied project example."""
from collections import Counter
from dataclasses import dataclass
import re

from src.common.results import CheckResult, Issue
from .command_flow import _without_local_functions
from .control_style import direct_statement_spans
from .flow_review import _methods
from .lexer import _scan_csharp


_XML = re.compile(r'\bDataTableToXml\s*\(')
_OUTPUT = re.compile(r'\bParameterDirection\s*\.\s*(?:Output|InputOutput)\b')
_SAVE = re.compile(r'(?<![\w.])(?:(?:this|base)\s*\.\s*)?CallSaveProcedure\s*\(')
_LOOP = re.compile(r'(?<![\w.@])(?:for|foreach|while|do)\b')


@dataclass(frozen=True)
class _Method:
    name: str
    body: str
    offset: int
    fingerprint: tuple[tuple[str, str], ...]


def _bodies(source: str) -> list[_Method]:
    code, _ = _scan_csharp(source)
    found = []
    for match, start, end in _methods(code):
        # Keep offsets, while excluding comments, strings and uncalled locals.
        body = _without_local_functions(code[start:end])
        _, tokens = _scan_csharp(source[match.start():end + 1])
        found.append(_Method(match['name'], body, start,
                             tuple((token[0], token[1]) for token in tokens)))
    return found


def _loop_calls(method: _Method) -> list[int]:
    found: set[int] = set()
    for loop in _LOOP.finditer(method.body):
        spans = direct_statement_spans(method.body[loop.start():])
        if not spans:
            continue
        left, right = spans[0]
        statement = method.body[loop.start() + left:loop.start() + right]
        for call in _SAVE.finditer(statement):
            found.add(method.offset + loop.start() + left + call.start())
    return sorted(found)


def check_save_contract(candidate: str, *, original: str | None = None,
                        style_reference: str | None = None) -> CheckResult:
    """Report review differences, without declaring XML or OUTPUT universally required."""
    result = CheckResult(not_checked=[
        'save XML table/field/key/row-state semantics, branch feasibility, indirect helpers and SQL persistence'])
    metadata: dict[str, object] = {'style_reference_supplied': style_reference is not None,
                                  'compared': False}
    result.metadata['save_contract_comparison'] = metadata
    if style_reference is None:
        result.not_checked.append('save transport comparison; no same-project C# style reference supplied')
        return result

    methods, references = _bodies(candidate), _bodies(style_reference)
    saves = [method for method in methods if method.name == 'CallSaveProcedure']
    reference_saves = [method for method in references if method.name == 'CallSaveProcedure']
    metadata.update(candidate_save_bodies=len(saves), reference_save_bodies=len(reference_saves))
    if len(saves) != 1 or len(reference_saves) != 1:
        result.not_checked.append(
            f'save transport comparison; candidate/reference contain {len(saves)}/{len(reference_saves)} CallSaveProcedure bodies')
        return result

    current, expected = saves[0], reference_saves[0]
    previous = Counter((method.name, method.fingerprint) for method in _bodies(original or ''))
    reference_xml = bool(_XML.search(expected.body))
    metadata.update(compared=True, reference_xml=reference_xml,
                    candidate_xml=bool(_XML.search(current.body)))
    result.checked.append('direct CallSaveProcedure XML serialization, output directions and loop call sites against supplied project source')
    if not previous[(current.name, current.fingerprint)]:
        line = candidate.count('\n', 0, current.offset) + 1
        if reference_xml and not _XML.search(current.body):
            result.issues.append(Issue('save_xml_contract_drift_review', 'warning',
                'The supplied save example serializes DataTable XML, but this save body does not. Trace checked rows, row states, XML and the SP signature before substituting scalar or indirect transport.',
                line=line, details={'method': current.name}))
        outputs, reference_outputs = len(_OUTPUT.findall(current.body)), len(_OUTPUT.findall(expected.body))
        if outputs > reference_outputs:
            result.issues.append(Issue('save_output_contract_drift_review', 'warning',
                'This save adds output parameter directions absent from the supplied example. Verify that the caller needs the returned value; server-owned timestamps with an established requery do not alone require an output or a manual grid update.',
                line=line, details={'method': current.name, 'candidate_count': outputs,
                                    'reference_count': reference_outputs}))

    if reference_xml:
        reference_calls = sum(len(_loop_calls(method)) for method in references)
        candidate_calls = sum(len(_loop_calls(method)) for method in methods)
        metadata.update(reference_loop_save_calls=reference_calls, candidate_loop_save_calls=candidate_calls)
        if candidate_calls > reference_calls:
            for method in methods:
                if previous[(method.name, method.fingerprint)]:
                    previous[(method.name, method.fingerprint)] -= 1
                    continue
                for offset in _loop_calls(method):
                    result.issues.append(Issue('rowwise_save_contract_drift_review', 'warning',
                        'CallSaveProcedure runs inside a loop beyond the supplied XML save example. Compare one selected-row XML save with this per-iteration save, including printing, failure handling and refresh. Keep per-row saving when the actual contract requires it.',
                        line=candidate.count('\n', 0, offset) + 1, details={'method': method.name,
                            'candidate_count': candidate_calls, 'reference_count': reference_calls}))
    return result


def check_select_contract(candidate: str, *, original: str | None = None,
                          style_reference: str | None = None) -> CheckResult:
    """Review query serialization independently of the SAVE transport choice."""
    result = CheckResult(not_checked=[
        'SELECT parameter/field semantics, indirect XML creation, SQL branches and query results'])
    metadata: dict[str, object] = {'style_reference_supplied': style_reference is not None,
                                  'compared': False}
    result.metadata['select_contract_comparison'] = metadata
    if style_reference is None:
        result.not_checked.append('SELECT transport comparison; no same-project C# style reference supplied')
        return result
    selects = [method for method in _bodies(candidate) if method.name == 'CallSelectProcedure']
    references = [method for method in _bodies(style_reference) if method.name == 'CallSelectProcedure']
    metadata.update(candidate_select_bodies=len(selects), reference_select_bodies=len(references))
    if len(selects) != 1 or len(references) != 1:
        result.not_checked.append(
            f'SELECT transport comparison; candidate/reference contain {len(selects)}/{len(references)} CallSelectProcedure bodies')
        return result
    current, expected = selects[0], references[0]
    current_xml, reference_xml = bool(_XML.search(current.body)), bool(_XML.search(expected.body))
    unchanged = any(method.name == current.name and method.fingerprint == current.fingerprint
                    for method in _bodies(original or ''))
    metadata.update(compared=True, candidate_xml=current_xml, reference_xml=reference_xml,
                    unchanged_body_skipped=unchanged)
    result.checked.append('direct CallSelectProcedure XML serialization against the supplied query body, independently of SAVE')
    if current_xml and not reference_xml and not unchanged:
        result.issues.append(Issue('select_xml_contract_drift_review', 'warning',
            'This query adds DataTable XML serialization absent from the supplied SELECT example. A request to use XML in SAVE does not authorize changing SELECT or print lookup transport. Verify the query-specific requirement and SP signature; XML queries remain valid when actually required.',
            line=candidate.count('\n', 0, current.offset) + 1, details={'method': current.name}))
    return result
