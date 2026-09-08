"""Grid layout defaults from the user-supplied DataWindowToXml.html (2026-09-08)."""

DATAWINDOW_TO_XML_GRIDVIEW_TOP_LEVEL_PROPERTIES = [
    ("#LayoutVersion", ""),
    ("BestFitMaxRowCount", "-1"),
    ("PreviewLineCount", "-1"),
    ("HorzScrollStep", "3"),
    ("FocusRectStyle", "CellFocus"),
    ("ScrollStyle", "LiveVertScroll, LiveHorzScroll"),
    ("PreviewIndent", "-1"),
    ("GroupPanelText", ""),
    ("PreviewFieldName", ""),
    ("VertScrollTipFieldName", ""),
    ("LevelIndent", "-1"),
    ("GroupFooterShowMode", "VisibleIfExpanded"),
    ("NewItemRowText", ""),
    ("SynchronizeClones", "true"),
    ("BorderStyle", "Default"),
    ("ViewCaption", ""),
    ("DetailHeight", "350"),
    ("DetailTabHeaderLocation", "Top"),
    ("ActiveFilterEnabled", "true"),
]

DATAWINDOW_TO_XML_OPTIONS_VIEW_DEFAULTS = {
    "ShowViewCaption": "false",
    "EnableAppearanceEvenRow": "true",
    "ShowGroupPanel": "false",
    "ColumnAutoWidth": "false",
    "ShowFooter": "true",
    "ShowAutoFilterRow": "true",
}

_CSHARP_ENUM_VALUES = {
    "FocusRectStyle": "DevExpress.XtraGrid.Views.Grid.DrawFocusRectStyle.CellFocus",
    "ScrollStyle": "DevExpress.XtraGrid.Views.Grid.ScrollStyleFlags.LiveVertScroll | DevExpress.XtraGrid.Views.Grid.ScrollStyleFlags.LiveHorzScroll",
    "GroupFooterShowMode": "DevExpress.XtraGrid.Views.Grid.GroupFooterShowMode.VisibleIfExpanded",
    "BorderStyle": "DevExpress.XtraEditors.Controls.BorderStyles.Default",
    "DetailTabHeaderLocation": "DevExpress.XtraTab.TabHeaderLocation.Top",
}

DATAWINDOW_TO_CSHARP_GRIDVIEW_DEFAULTS = [
    (name, _CSHARP_ENUM_VALUES.get(name, value or "string.Empty"))
    for name, value in DATAWINDOW_TO_XML_GRIDVIEW_TOP_LEVEL_PROPERTIES
    if not name.startswith('#')
]
