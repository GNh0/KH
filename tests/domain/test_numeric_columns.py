import unittest
from src.csharp.checks import check_csharp
from src.csharp.designer import check_designer

DESIGNER = """
private DevExpress.XtraGrid.Columns.GridColumn colList_QTY;
private DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit rpsSpinQTY;
private DevExpress.XtraGrid.GridControl grdList;
this.grdList.RepositoryItems.Add(this.rpsSpinQTY);
this.colList_QTY.ColumnEdit = this.rpsSpinQTY;
"""


class NumericColumnTests(unittest.TestCase):
    def codes(self, source, **kwargs):
        return {i.code for i in check_designer(source, numeric_columns=['colList_QTY'], **kwargs).issues}

    def test_actual_spin_binding_passes(self):
        self.assertNotIn('numeric_column_spin_editor_missing', self.codes(DESIGNER))

    def test_declaration_or_mask_without_column_binding_does_not_pass(self):
        source = DESIGNER.replace('this.colList_QTY.ColumnEdit = this.rpsSpinQTY;', '')
        source += 'this.rpsSpinQTY.Mask.EditMask = "N0";'
        self.assertIn('numeric_column_spin_editor_missing', self.codes(source, original=source))

    def test_wrong_editor_and_missing_member_are_visible(self):
        self.assertIn('numeric_column_spin_editor_missing',
                      self.codes(DESIGNER.replace('RepositoryItemSpinEdit', 'RepositoryItemTextEdit')))
        result = check_designer(DESIGNER, numeric_columns=['colList_MISSING'])
        self.assertIn('numeric_column_target_missing', {i.code for i in result.issues})

    def test_code_behind_can_break_an_existing_designer_binding(self):
        before = 'this.colList_QTY.Width = 80;'
        result = check_csharp(before + ' this.colList_QTY.ColumnEdit = null;',
                              original=before, designer=DESIGNER, original_designer=DESIGNER,
                              numeric_columns=['colList_QTY'])
        self.assertIn('numeric_column_spin_editor_missing', {i.code for i in result.issues})
        valid = check_csharp(before, original=before, designer=DESIGNER,
                             original_designer=DESIGNER, numeric_columns=['colList_QTY'])
        self.assertNotIn('numeric_column_spin_editor_missing', {i.code for i in valid.issues})

    def test_custom_spin_repository_uses_supplied_inheritance(self):
        source = DESIGNER.replace('DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit', 'Widgets.QuantityRepository')
        base = 'namespace Widgets { public class QuantityRepository : DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit {} }'
        self.assertNotIn('numeric_column_spin_editor_missing', self.codes(source, control_sources=[base]))

    def test_style_exemptions_are_reported_without_implying_authorization(self):
        source = DESIGNER + 'this.rpsSpinQTY.Mask.EditMask = "N0";'
        for result in [
            check_designer(source, allowed_property_changes=['rpsSpinQTY.Mask.EditMask']),
            check_csharp(source, allowed_property_changes=['rpsSpinQTY.Mask.EditMask']),
        ]:
            with self.subTest(result=result):
                self.assertEqual(['rpsSpinQTY.Mask.EditMask'], result.metadata['style_exemptions'])
                self.assertTrue(any('do not establish user authorization' in value for value in result.not_checked))
                self.assertNotIn('spin_edit_mask_preference', {i.code for i in result.issues})


if __name__ == '__main__':
    unittest.main()
