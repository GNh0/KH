"""Narrow literal comparisons for label presentation; not a C# evaluator."""
from decimal import Decimal, InvalidOperation
import re

from .designer_model import _normalized_csharp_value, _parse_size
from .lexer import _scan_csharp, string_literal_value

LABEL_PROPERTIES = frozenset({
    'Font', 'Appearance.Font', 'Appearance.Options.UseFont',
    'Appearance.TextOptions.HAlignment', 'Appearance.TextOptions.VAlignment',
    'Appearance.Options.UseTextOptions', 'AutoSizeMode', 'AutoSize',
    'Size', 'Height', 'Bounds', 'MinimumSize', 'MaximumSize',
    'Appearance.FontSizeDelta', 'Appearance.FontStyleDelta',
})
HEIGHT_PROPERTIES = frozenset({'Size', 'Height', 'Bounds', 'MinimumSize', 'MaximumSize'})


def label_constructor_value(prop: str, value: str) -> str:
    """Read the self-property Default fallback used by actual label controls.

    This establishes the intended fresh-control alignment, not the result of an
    arbitrary conditional or a later runtime assignment.
    """
    enum_type = {'Appearance.TextOptions.HAlignment': 'HorzAlignment',
                 'Appearance.TextOptions.VAlignment': 'VertAlignment'}.get(prop)
    if enum_type is None:
        return value
    expression = re.sub(r'\s+', '', value)
    target = r'(?P<target>(?:base|this)\.' + re.escape(prop) + ')'
    enum = r'(?:global::)?(?:DevExpress\.Utils\.)?' + enum_type
    match = re.fullmatch(target + '==' + enum + r'\.Default\?(' + enum + r'\.\w+):(?P=target)', expression)
    return match[2] if match else value


def _arguments(value: str) -> list[str]:
    code, _ = _scan_csharp(value)
    depth, start, result = 0, 0, []
    for index, char in enumerate(code):
        if char in '([{':
            depth += 1
        elif char in ')]}':
            depth -= 1
        elif char == ',' and depth == 0:
            result.append(value[start:index].strip())
            start = index + 1
    return result + [value[start:].strip()]


def _number(value: str) -> Decimal | None:
    if not re.fullmatch(r'\d+(?:\.\d+)?[fF]?', value.strip()):
        return None
    try:
        return Decimal(value.strip().rstrip('fF'))
    except InvalidOperation:
        return None


def label_value_key(prop: str, value: str) -> tuple | None:
    """Normalize supported literals without guessing helpers or conditional values."""
    value = value.strip().removeprefix('global::')
    if prop in {'Size', 'MinimumSize', 'MaximumSize'}:
        size = _parse_size(value)
        return ('height', size[1]) if size is not None else None
    if prop == 'Height':
        return ('height', int(value)) if re.fullmatch(r'\d+', value) else None
    if prop == 'Bounds':
        match = re.fullmatch(r'new\s+(?:System\.Drawing\.)?Rectangle\s*\(\s*\d+\s*,\s*\d+\s*,\s*\d+\s*,\s*(\d+)\s*\)', value)
        return ('height', int(match[1])) if match else None
    if prop in {'Font', 'Appearance.Font'}:
        match = re.fullmatch(r'new\s+(?:System\.Drawing\.)?Font\s*\((.*)\)', value, re.S)
        if not match:
            return None
        args = _arguments(match[1])
        if len(args) < 2 or len(args) > 6:
            return None
        family, size = string_literal_value(args[0]), _number(args[1])
        if family is None or size is None:
            return None
        style, unit = 'Regular', 'Point'
        if len(args) >= 3:
            third = re.fullmatch(r'(?:System\.Drawing\.)?(FontStyle|GraphicsUnit)\.(\w+)', args[2])
            if not third:
                return None
            if third[1] == 'FontStyle':
                style = third[2]
            elif len(args) == 3:
                unit = third[2]
            else:
                return None
        if len(args) >= 4:
            fourth = re.fullmatch(r'(?:System\.Drawing\.)?GraphicsUnit\.(\w+)', args[3])
            if not fourth:
                return None
            unit = fourth[1]
        # Charset/vertical-font overloads need their actual arguments as evidence.
        extras = tuple(_normalized_csharp_value(a) for a in args[4:])
        return ('font', family, size, style, unit, extras)
    enum = re.fullmatch(r'(?:DevExpress\.(?:Utils|XtraEditors)\.)?(HorzAlignment|VertAlignment|LabelAutoSizeMode)\.(\w+)', value)
    if enum:
        return ('enum', enum[1], enum[2])
    if value in {'true', 'false'}:
        return ('bool', value)
    return None
