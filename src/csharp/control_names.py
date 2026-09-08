"""Agreed semantic names for new WinForms controls; existing names stay scoped."""
import re

from src.common.results import Issue


_KONE_BASES = {
    'u_GridView': 'GridView', 'u_GridControl': 'GridControl',
    'u_SpinEdit': 'SpinEdit', 'u_DateEdit': 'DateEdit', 'u_TextEdit': 'TextEdit',
    'u_ButtonEdit': 'ButtonEdit', 'u_ButtonControl': 'SimpleButton',
    'u_CheckEdit': 'CheckEdit', 'u_GroupControl': 'GroupControl',
    'u_Label': 'LabelControl', 'u_LookUpEdit': 'LookUpEdit',
    'u_GridLookUpEdit': 'GridLookUpEdit', 'u_MemoEdit': 'MemoEdit',
    'u_Panel': 'PanelControl', 'u_TabControl': 'XtraTabControl',
    'u_RadioButton': 'RadioGroup', 'u_PictureEdit': 'PictureEdit',
    'u_rpsTextEdit': 'RepositoryItemTextEdit', 'u_rpsLookUpEdit': 'RepositoryItemLookUpEdit',
    'u_ScrollPanel': 'XtraScrollableControl',
}
_PREFIXES = {
    'TextEdit': 'txt', 'TextBox': 'txt', 'SpinEdit': 'Spin', 'DateEdit': 'ymd',
    'LookUpEdit': 'cbo', 'GridLookUpEdit': 'cbo', 'ButtonEdit': 'btn',
    'SimpleButton': 'btn', 'Button': 'btn', 'CheckEdit': 'Chk', 'MemoEdit': 'memo',
    'PanelControl': 'pn', 'Panel': 'pn', 'GroupControl': 'grp',
    'GridControl': 'grd', 'GridView': 'gvw', 'BandedGridView': 'gvw', 'AdvBandedGridView': 'gvw',
    'TreeList': 'treeList', 'TabControl': 'tab', 'XtraTabControl': 'tab', 'LabelControl': 'lbl',
    'RepositoryItemSpinEdit': 'rpsSpin', 'RepositoryItemLookUpEdit': 'rpscbo',
    'RepositoryItemGridLookUpEdit': 'rpscbo', 'RepositoryItemButtonEdit': 'rpsbtn',
    'RepositoryItemCheckEdit': 'rpschk',
}


def known_control_kind(type_name: str) -> str:
    name = type_name.removeprefix('global::')
    if name.startswith('KoneLib.Controls.') or '.' not in name:
        leaf = name.split('.')[-1]
        return _KONE_BASES.get(leaf, leaf)
    if name.startswith(('DevExpress.', 'System.Windows.Forms.')):
        return name.split('.')[-1]
    return name


def control_name_issue(name: str, type_name: str) -> Issue | None:
    kind = known_control_kind(type_name)
    if kind == 'GridColumn':
        expected = 'col<Role>_<FIELD>'
        valid = re.fullmatch(r'col[A-Z][A-Za-z0-9]*_[A-Z][A-Z0-9_]*', name)
    elif kind == 'RepositoryItemSpinEdit':
        expected = 'rpsSpin<Field> or rps<Role>Spin<Field> for another grid with the same field'
        valid = re.fullmatch(r'rps(?:[A-Z][A-Za-z0-9]*?)?Spin[A-Z][A-Za-z0-9_]*', name)
    elif kind in _PREFIXES:
        prefix = _PREFIXES[kind]
        expected = prefix + '<FieldOrRole>'
        valid = re.fullmatch(re.escape(prefix) + r'[A-Z][A-Za-z0-9_]*', name)
    elif kind.startswith('RepositoryItem'):
        expected = 'rps<SemanticName>'
        valid = name.startswith('rps') and len(name) > 3 and not name[3:].isdigit()
    else:
        return None
    if valid:
        return None
    return Issue('date_control_name_preference' if kind == 'DateEdit' else 'control_name_preference', 'warning',
                 'Use the agreed semantic control name for this new member; keep the actual field/role and all declarations, Name values and references consistent.',
                 details={'control': name, 'type': type_name, 'expected': expected})
