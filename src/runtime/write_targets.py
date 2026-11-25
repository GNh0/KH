"""Bounded, non-executing resolution of common shell source-write destinations."""
import ast
from pathlib import Path
import re

SOURCE_SUFFIX = re.compile(r'\.(?:sql|cs|srd|srw|sru|srf)\b', re.I)
VALUE_LIMIT = 32768


def _destination(value, cwd: Path) -> Path | None:
    if not isinstance(value, (str, Path)) or not str(value) or len(str(value)) > VALUE_LIMIT:
        return None
    path = Path(value)
    return (cwd / path).resolve() if not path.is_absolute() else path.resolve()


class PythonTargets:
    def __init__(self, cwd: Path):
        self.cwd = cwd
        self.values: dict = {}
        self.hints: dict[str, bool] = {}
        self.paths: list[Path] = []
        self.unresolved: list[str] = []
        self.path_names = {'Path', 'pathlib.Path'}
        self.budget = 2048

    def value(self, node):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and len(node.value) <= VALUE_LIMIT:
            return node.value
        if isinstance(node, ast.Name):
            return self.values.get(node.id)
        if isinstance(node, (ast.List, ast.Tuple)):
            return [self.value(item) for item in node.elts]
        if isinstance(node, ast.BinOp):
            left, right = self.value(node.left), self.value(node.right)
            if isinstance(node.op, ast.Add) and isinstance(left, str) and isinstance(right, str) and len(left) + len(right) <= 32768:
                return left + right
            if isinstance(node.op, ast.Div) and isinstance(left, Path) and isinstance(right, (str, Path)) and len(str(left)) + len(str(right)) <= 32768:
                return left / right
        if isinstance(node, ast.JoinedStr):
            values = [self.value(item.value) if isinstance(item, ast.FormattedValue) and item.format_spec is None else
                      item.value if isinstance(item, ast.Constant) else None for item in node.values]
            return ''.join(str(v) for v in values) if all(isinstance(v, (str, Path)) for v in values) and sum(len(str(v)) for v in values) <= 32768 else None
        if isinstance(node, ast.Attribute):
            value = self.value(node.value)
            if isinstance(value, Path) and node.attr in {'parent', 'name', 'stem', 'suffix'}:
                return getattr(value, node.attr)
        if isinstance(node, ast.Call):
            name = ast.unparse(node.func)
            args = [self.value(item) for item in node.args]
            if name in self.path_names and len(args) == 1 and isinstance(args[0], (str, Path)):
                return Path(args[0])
            if name in {item + '.cwd' for item in self.path_names} and not args:
                return self.cwd
            if name == 'str' and len(args) == 1 and isinstance(args[0], (str, Path)):
                return str(args[0])
            if isinstance(node.func, ast.Attribute):
                base = self.value(node.func.value)
                if isinstance(base, Path):
                    if node.func.attr in {'resolve', 'absolute'} and not args:
                        return _destination(base, self.cwd)
                    if node.func.attr == 'joinpath' and all(isinstance(v, (str, Path)) for v in args) and sum(len(str(v)) for v in [base, *args]) <= VALUE_LIMIT:
                        return base.joinpath(*args)
                    if node.func.attr in {'with_name', 'with_suffix'} and len(args) == 1 and isinstance(args[0], str):
                        return getattr(base, node.func.attr)(args[0])
        return None

    def write(self, node, value) -> None:
        path = _destination(value, self.cwd)
        if path is not None:
            self.paths.append(path)
        else:
            # Keep a recognizable source suffix as unresolved evidence, not an invented path.
            if self.hint(node):
                self.unresolved.append('Unresolved Python source destination at line ' + str(getattr(node, 'lineno', '?')))

    def hint(self, node) -> bool:
        return any((isinstance(item, ast.Constant) and isinstance(item.value, str) and SOURCE_SUFFIX.search(item.value)) or
                   (isinstance(item, ast.Name) and self.hints.get(item.id, False)) for item in ast.walk(node))

    def call(self, node) -> None:
        if not isinstance(node, ast.Call):
            return
        if isinstance(node.func, ast.Attribute) and node.func.attr in {'write_text', 'write_bytes'}:
            self.write(node.func.value, self.value(node.func.value))
        else:
            receiver = node.func.value if isinstance(node.func, ast.Attribute) and node.func.attr == 'open' else None
            builtin = ast.unparse(node.func) in {'open', 'io.open'}
            if not builtin and receiver is None:
                return
            offset = 1 if builtin else 0
            mode = self.value(node.args[offset]) if len(node.args) > offset else next(
                (self.value(k.value) for k in node.keywords if k.arg == 'mode'), 'r')
            destination = node.args[0] if builtin and node.args else receiver
            if destination is not None and isinstance(mode, str) and any(letter in mode for letter in 'wax+'):
                self.write(destination, self.value(destination))

    def statements(self, statements: list[ast.stmt]) -> None:
        for statement in statements:
            if self.budget <= 0:
                if any(self.hint(item) for item in statements):
                    self.unresolved.append('Python source-write analysis exceeded its statement budget.')
                return
            self.budget -= 1
            if isinstance(statement, ast.ImportFrom) and statement.module == 'pathlib':
                self.path_names.update(item.asname or item.name for item in statement.names if item.name == 'Path')
            elif isinstance(statement, ast.Import):
                self.path_names.update((item.asname or item.name) + '.Path' for item in statement.names if item.name == 'pathlib')
            elif isinstance(statement, (ast.Assign, ast.AnnAssign)):
                self.call(statement.value)
                value = self.value(statement.value) if statement.value is not None else None
                for target in statement.targets if isinstance(statement, ast.Assign) else [statement.target]:
                    if isinstance(target, ast.Name):
                        self.values[target.id] = value
                        self.hints[target.id] = self.hint(statement.value) if value is None and statement.value is not None else False
                        self.path_names.discard(target.id)
            elif isinstance(statement, ast.Expr):
                self.call(statement.value)
            elif isinstance(statement, ast.With):
                for item in statement.items:
                    self.call(item.context_expr)
                self.statements(statement.body)
            elif isinstance(statement, ast.For):
                values = self.value(statement.iter)
                if isinstance(statement.target, ast.Name) and isinstance(values, list) and len(values) <= 32:
                    previous = self.values.get(statement.target.id)
                    previous_hint = self.hints.get(statement.target.id, False)
                    for value in values:
                        self.values[statement.target.id] = value
                        self.hints[statement.target.id] = self.hint(statement.iter) if value is None else False
                        self.statements(statement.body)
                    self.values[statement.target.id] = previous
                    self.hints[statement.target.id] = previous_hint


def _ps_value(text: str, values: dict, cwd: Path):
    text = text.strip().rstrip(';').strip()
    if len(text) > VALUE_LIMIT:
        return None
    if text.casefold().startswith('(join-path ') and text.endswith(')'):
        text = text[1:-1]
    if text.casefold() in {'(get-location)', '$pwd', '$pwd.path'}:
        return cwd
    if re.fullmatch(r'\$\w+', text):
        return values.get(text.casefold())
    if len(text) > 1 and text[0] == text[-1] and text[0] in "'\"":
        value = text[1:-1]
        if text[0] == '"':
            if '$(' in value or '`' in value:
                return None
            names = re.findall(r'\$\w+', value)
            if any(not isinstance(values.get(name.casefold()), (str, Path)) for name in names):
                return None
            value = re.sub(r'\$\w+', lambda match: str(values[match[0].casefold()]), value)
            if '$' in value or len(value) > VALUE_LIMIT:
                return None
        return value.replace("''", "'") if text[0] == "'" else value
    match = re.fullmatch(r'Join-Path\s+(.+?)\s+(\'(?:[^\']|\'\')*\'|"[^"]*"|\$\w+)', text, re.I)
    if match:
        left, right = _ps_value(match[1], values, cwd), _ps_value(match[2], values, cwd)
        if isinstance(left, (str, Path)) and isinstance(right, (str, Path)):
            return Path(left) / right
    return None


def _shell_statements(text: str) -> list[str]:
    """Separate command positions without treating quoted examples as commands."""
    result = []
    current = []
    quote = ''
    comment = False
    index = 0
    while index < len(text):
        char = text[index]
        if comment:
            if char in '\r\n':
                comment = False
            else:
                index += 1
                continue
        if quote:
            current.append(char)
            if char == quote:
                if quote == "'" and index + 1 < len(text) and text[index + 1] == quote:
                    current.append(text[index + 1])
                    index += 1
                else:
                    quote = ''
            elif char == chr(96) and index + 1 < len(text):
                current.append(text[index + 1])
                index += 1
        elif char in "'\"":
            quote = char
            current.append(char)
        elif char == '#':
            comment = True
        elif char in '\r\n;|':
            result.append(''.join(current).strip())
            current = []
        else:
            current.append(char)
        index += 1
    result.append(''.join(current).strip())
    return result


def _redirect_destination(statement: str) -> str | None:
    quote = ''
    for index, char in enumerate(statement):
        if quote:
            if char == quote:
                quote = ''
        elif char in "'\"":
            quote = char
        elif char == '>':
            match = re.match(r'>?\s*(\$\w+|\'[^\']*\'|"[^"]*")', statement[index + 1:])
            return match[1] if match else None
    return None


def shell_write_targets(command: str, cwd: Path) -> tuple[list[Path], list[str]]:
    """Resolve straight-line Python and simple PowerShell assignments without eval.

    Imports/functions, conditions, filesystem enumeration and arbitrary calls are
    not executed or guessed. Unresolved source-shaped destinations stay explicit.
    """
    if len(command) > 512 * 1024:
        return ([], ['Shell source-write command exceeds bounded destination analysis.']) if (
            SOURCE_SUFFIX.search(command) and re.search(r'Set-Content|Add-Content|Out-File|WriteAllText|WriteAllBytes|\.write_(?:text|bytes)\s*\(', command, re.I)
        ) else ([], [])
    paths: list[Path] = []
    unresolved: list[str] = []
    spans = []
    programs = []
    for match in re.finditer(r"@(['\"])\r?\n(.*?)\r?\n\1@([^\r\n]*)", command, re.S):
        if re.search(r'\bpython[\w.]*', match[3], re.I):
            programs.append(match[2])
            spans.append((match.start(), match.end()))
    for match in re.finditer(r"(?m)^\s*python[\w.]*\s+-\s+<<['\"]?(\w+)['\"]?\r?\n(.*?)^\1\s*$", command, re.S | re.M):
        programs.append(match[2])
        spans.append((match.start(), match.end()))
    for statement in _shell_statements(command):
        match = re.match(r"(?:&\s*)?(?:'[^']*python[^']*'|\"[^\"]*python[^\"]*\"|python[\w.]*)\s+(?:-B\s+)?-c\s+('[^']*'|\"[^\"]*\")\s*$", statement, re.I)
        if match:
            programs.append(match[1][1:-1])
    for program in programs:
        try:
            tree = ast.parse(program)
            if sum(1 for _ in ast.walk(tree)) > 4096:
                if SOURCE_SUFFIX.search(program) and re.search(r'\.write_(?:text|bytes)\s*\(|\bopen\s*\(', program):
                    unresolved.append('Python source-write analysis exceeded 4096 syntax nodes.')
                continue
            resolver = PythonTargets(cwd)
            resolver.statements(tree.body)
            paths.extend(resolver.paths)
            unresolved.extend(resolver.unresolved)
        except (SyntaxError, ValueError, OSError, RecursionError):
            if SOURCE_SUFFIX.search(program) and re.search(r'\.write_(?:text|bytes)\s*\(|\bopen\s*\(', program):
                unresolved.append('Python source-write destinations could not be resolved safely.')
    shell = command
    for start, end in reversed(spans):
        shell = shell[:start] + ' ' * (end - start) + shell[end:]
    values: dict = {}
    hints: dict[str, bool] = {}
    for statement in _shell_statements(shell):
        assignment = re.fullmatch(r'\s*(\$\w+)\s*=\s*(.+)', statement)
        if assignment:
            values[assignment[1].casefold()] = _ps_value(assignment[2], values, cwd)
            hints[assignment[1].casefold()] = bool(SOURCE_SUFFIX.search(assignment[2])) or any(
                hints.get(name.casefold(), False) for name in re.findall(r'\$\w+', assignment[2]))
        write = re.match(r'(?:Set-Content|Add-Content|Out-File)\s+(?:-(?:LiteralPath|FilePath|Path)\s+)?(\$\w+|\'[^\']*\'|"[^"]*")', statement, re.I)
        if not write:
            write = re.match(r'\[(?:System\.)?IO\.File\]::WriteAll(?:Text|Bytes)\s*\(\s*(\$\w+|\'[^\']*\'|"[^"]*")', statement, re.I)
        destination = write[1] if write else _redirect_destination(statement)
        if destination:
            try:
                path = _destination(_ps_value(destination, values, cwd), cwd)
            except (ValueError, OSError):
                path = None
            if path is not None:
                paths.append(path)
            elif hints.get(destination.casefold(), False) or SOURCE_SUFFIX.search(destination):
                unresolved.append('Unresolved PowerShell source destination')
    return list(dict.fromkeys(paths)), list(dict.fromkeys(unresolved))
