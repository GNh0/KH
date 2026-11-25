import unittest

from src.csharp.designer import check_designer


def naming(source, **kwargs):
    return [i for i in check_designer(source, **kwargs).issues
            if i.code in {'control_name_preference', 'date_control_name_preference', 'control_name_mismatch'}]


class ControlNameTests(unittest.TestCase):
    def test_restored_input_grid_and_repository_names_are_typed_and_semantic(self):
        cases = [('TextEdit', 'textEdit1', 'txtITEMCD'), ('SpinEdit', 'spnQTY', 'SpinQTY'),
                 ('DateEdit', 'deFRDT', 'ymdFRDT'), ('PanelControl', 'pnlSearch', 'pnSearch'),
                 ('GroupControl', 'groupControl1', 'grpSearch'), ('GridControl', 'gridControl1', 'grdList'),
                 ('GridView', 'gridView1', 'gvwList'), ('GridColumn', 'gridColumn1', 'colList_ITEMCD'),
                 ('RepositoryItemSpinEdit', 'repSpinQTY', 'rpsSpinQTY'),
                 ('RepositoryItemLookUpEdit', 'repositoryItemLookUpEdit1', 'rpscboITEMCD'),
                 ('RepositoryItemButtonEdit', 'repositoryItemButtonEdit1', 'rpsbtnITEMCD'),
                 ('RepositoryItemCheckEdit', 'repositoryItemCheckEdit1', 'rpschkUSEYN')]
        for typename, wrong, correct in cases:
            with self.subTest(typename=typename):
                self.assertEqual(1, len(naming(f'private {typename} {wrong};')))
                self.assertEqual([], naming(f'private {typename} {correct};'))

    def test_legacy_names_and_explicit_current_name_requirements_do_not_trigger_global_renames(self):
        source = 'this.gridControl1 = new GridControl(); this.gridControl1.Name = "gridControl1";'
        self.assertEqual([], naming(source, original=source))
        self.assertEqual([], naming(source, allowed_property_changes=['gridControl1.Name']))
        new = source + ' this.gridView1 = new GridView();'
        self.assertEqual(['gridView1'], [i.details['control'] for i in naming(new, original=source)])

    def test_unrelated_data_variables_and_literals_are_not_control_names(self):
        source = 'DataTable dtLIST; string s = "private GridControl gridControl1;"; private Other.GridView view;'
        self.assertEqual([], naming(source))

    def test_user_control_library_name_does_not_change_the_agreed_name_family(self):
        library = 'namespace UiLibrary { public class QuantityInput : DevExpress.XtraEditors.SpinEdit { public QuantityInput() { } } }'
        self.assertEqual(1, len(naming('private UiLibrary.QuantityInput numericQTY;', control_sources=[library])))
        self.assertEqual([], naming('private UiLibrary.QuantityInput SpinQTY;', control_sources=[library]))

    def test_numeric_repository_can_put_grid_role_before_spin(self):
        self.assertEqual([], naming('private RepositoryItemSpinEdit rpsSpinQTY; private RepositoryItemSpinEdit rpsDetailSpinQTY;'))
        self.assertEqual(1, len(naming('private RepositoryItemSpinEdit repDetailSpinQTY;')))


if __name__ == '__main__':
    unittest.main()
