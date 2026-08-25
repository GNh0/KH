import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from src.skills import pb_to_csharp_migration as migration
from tests import test_pb_to_csharp_migration_harness as migration_tests


GRID_COLUMNS = [
    {"field_name": "AMT", "caption": "Amount", "data_type": "decimal(18, 2)"},
    {"field_name": "QTY", "caption": "Quantity", "data_type": "decimal(18, 2)"},
]


def designer_source():
    _, grid_designer = migration_tests.valid_devexpress_grid_designer(
        "TestBrowseForm",
        columns=GRID_COLUMNS,
    )
    return migration_tests.extend_designer_initialize_component(
        grid_designer,
        r'''
    private DevExpress.XtraEditors.PanelControl pnMain;
    private DevExpress.XtraEditors.LabelControl lblAMT;
    private DevExpress.XtraEditors.SpinEdit SpinAMT;
    private DevExpress.XtraEditors.LabelControl lblBASYYYY;
    private DevExpress.XtraEditors.DateEdit ymdBASYYYY;
    this.pnMain = new DevExpress.XtraEditors.PanelControl();
    this.lblAMT = new DevExpress.XtraEditors.LabelControl();
    this.SpinAMT = new DevExpress.XtraEditors.SpinEdit();
    this.lblBASYYYY = new DevExpress.XtraEditors.LabelControl();
    this.ymdBASYYYY = new DevExpress.XtraEditors.DateEdit();
    this.ClientSize = new System.Drawing.Size(640, 360);
    this.pnMain.Location = new System.Drawing.Point(10, 10);
    this.pnMain.Size = new System.Drawing.Size(600, 120);
    this.lblAMT.Location = new System.Drawing.Point(10, 10);
    this.lblAMT.Size = new System.Drawing.Size(80, 23);
    this.lblAMT.Text = "Amount";
    this.SpinAMT.Location = new System.Drawing.Point(100, 10);
    this.SpinAMT.Size = new System.Drawing.Size(140, 23);
    this.SpinAMT.TabIndex = 0;
    this.SpinAMT.BindingField = "AMT";
    this.lblBASYYYY.Location = new System.Drawing.Point(260, 10);
    this.lblBASYYYY.Size = new System.Drawing.Size(80, 23);
    this.lblBASYYYY.Text = "Base year";
    this.ymdBASYYYY.Location = new System.Drawing.Point(350, 10);
    this.ymdBASYYYY.Size = new System.Drawing.Size(100, 23);
    this.ymdBASYYYY.TabIndex = 1;
    this.ymdBASYYYY.Properties.Mask.EditMask = "yyyy";
    this.ymdBASYYYY.Properties.Mask.UseMaskAsDisplayFormat = true;
    this.ymdBASYYYY.Properties.VistaCalendarInitialViewStyle = DevExpress.XtraEditors.VistaCalendarInitialViewStyle.YearView;
    this.ymdBASYYYY.Properties.VistaCalendarViewStyle = DevExpress.XtraEditors.VistaCalendarViewStyle.YearView;
    this.pnMain.Controls.Add(this.lblAMT);
    this.pnMain.Controls.Add(this.SpinAMT);
    this.pnMain.Controls.Add(this.lblBASYYYY);
    this.pnMain.Controls.Add(this.ymdBASYYYY);
    this.Controls.Add(this.pnMain);
    this.Controls.Add(this.grdList);
    this.Controls.SetChildIndex(this.pnMain, 0);
    this.Controls.SetChildIndex(this.grdList, 1);
''',
    )


class PublicPbDesignerUiContractIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.srd_path = self.root / "detail.srd"
        self.srd_path.write_text(
            'column(band=detail x="100" y="10" height="40" width="160" name=amt )\n'
            'text(band=detail text="Amount" x="10" y="10" height="40" width="80" name=t_amt )\n',
            encoding="utf-8",
        )
        self.srd_sha256 = hashlib.sha256(self.srd_path.read_bytes()).hexdigest()
        self.baseline_path = self.root / "TestBrowseForm.Designer.cs"
        self.baseline_path.write_text(designer_source(), encoding="utf-8")
        self.baseline_sha256 = hashlib.sha256(self.baseline_path.read_bytes()).hexdigest()

    def tearDown(self):
        self.temp_dir.cleanup()

    def contract(self, **overrides):
        contract = {
            "form_class_name": "TestBrowseForm",
            "expected_base_type": "System.Windows.Forms.Form",
            "numeric_fields": ["AMT", "QTY"],
            "field_lineages": [
                {
                    "field_name": "AMT",
                    "pb_field_name": "amt",
                    "result_field_name": "AMT",
                    "binding_control_name": "SpinAMT",
                    "grid_column_name": "colList_AMT",
                    "numeric": True,
                }
            ],
            "label_editor_pairs": [
                {
                    "field_name": "AMT",
                    "label_name": "lblAMT",
                    "editor_name": "SpinAMT",
                    "container": "pnMain",
                }
            ],
            "year_fields": ["BASYYYY"],
            "srd_path": self.srd_path,
            "srd_sha256": self.srd_sha256,
            "caption_field_mappings": [
                {
                    "field_name": "AMT",
                    "srd_text_name": "t_amt",
                    "designer_member": "lblAMT",
                }
            ],
            "input_names": ["SpinAMT", "ymdBASYYYY"],
        }
        contract.update(overrides)
        return contract

    def verify(self, designer=None, contract=None, **kwargs):
        return migration_tests.verify_migration_generated_csharp_style(
            "",
            designer_source_text=designer or designer_source(),
            result_fields=["AMT", "QTY"],
            designer_ui_contract=contract or self.contract(),
            expected_grid_role="list",
            expected_grid_columns=GRID_COLUMNS,
            layout_load_artifact_text=migration_tests.generate_devexpress_grid_xml(GRID_COLUMNS),
            **kwargs,
        )

    @staticmethod
    def ui_issue_codes(result):
        return {
            issue["code"]
            for issue in result.metadata["designer_ui_contract"]["issues"]
        }

    def test_valid_contract_passes_public_verifier_with_exact_inputs_and_receipt(self):
        result = self.verify(
            baseline_designer_path=self.baseline_path,
            baseline_designer_sha256=self.baseline_sha256,
        )

        self.assertTrue(result.success, result.to_dict())
        receipt = result.metadata["designer_ui_contract"]
        self.assertEqual(
            {"success", "stdout", "stderr", "exit_code", "issues", "metadata", "input_contract"},
            set(receipt),
        )
        self.assertEqual(["AMT", "QTY"], receipt["input_contract"]["result_fields"])
        self.assertEqual(
            self.baseline_sha256,
            receipt["input_contract"]["baseline_designer"]["expected_sha256"],
        )

    def test_base_type_evidence_is_forwarded_into_designer_verifier(self):
        evidence = {"artifact": {"kind": "source", "path": "unused", "sha256": "unused"}}
        with mock.patch.object(
            migration,
            "validate_pb_designer_ui_contract",
            wraps=migration.validate_pb_designer_ui_contract,
        ) as verifier:
            result = self.verify(
                contract=self.contract(base_type_evidence=evidence),
            )

        self.assertTrue(result.success, result.to_dict())
        self.assertIs(verifier.call_args.kwargs["base_type_evidence"], evidence)

    def test_wrong_base_type_blocks_public_verifier(self):
        result = self.verify(contract=self.contract(expected_base_type="UserControl"))

        self.assertFalse(result.success)
        self.assertIn("form_inheritance_not_exact", self.ui_issue_codes(result))

    def test_crosswired_lineage_and_caption_block_public_verifier(self):
        broken = designer_source().replace(
            'this.SpinAMT.BindingField = "AMT";',
            'this.SpinAMT.BindingField = "OTHER";',
        ).replace(
            'this.lblAMT.Text = "Amount";',
            'this.lblAMT.Text = "Wrong caption";',
        )

        result = self.verify(designer=broken)

        self.assertFalse(result.success)
        codes = self.ui_issue_codes(result)
        self.assertIn("field_lineage_bindingfield_mismatch", codes)
        self.assertIn("designer_caption_not_rederived_from_srd", codes)

    def test_overlap_and_clipping_block_public_verifier(self):
        broken = designer_source().replace(
            "this.SpinAMT.Location = new System.Drawing.Point(100, 10);",
            "this.SpinAMT.Location = new System.Drawing.Point(70, 40);",
        ).replace(
            "this.SpinAMT.Size = new System.Drawing.Size(140, 23);",
            "this.SpinAMT.Size = new System.Drawing.Size(600, 100);",
        )

        result = self.verify(designer=broken)

        self.assertFalse(result.success)
        codes = self.ui_issue_codes(result)
        self.assertIn("label_editor_horizontal_order_or_overlap_invalid", codes)
        self.assertIn("control_out_of_container_bounds", codes)

    def test_year_only_dateedit_violation_blocks_public_verifier(self):
        broken = designer_source().replace(
            'this.ymdBASYYYY.Properties.Mask.EditMask = "yyyy";',
            "",
        ).replace(
            "this.ymdBASYYYY.Properties.Mask.UseMaskAsDisplayFormat = true;",
            "",
        )

        result = self.verify(designer=broken)

        self.assertFalse(result.success)
        self.assertIn("year_dateedit_static_contract_incomplete", self.ui_issue_codes(result))

    def test_shared_numeric_repository_blocks_public_verifier(self):
        broken = designer_source().replace(
            "this.colList_QTY.ColumnEdit = this.rpsSpinQTY;",
            "this.colList_QTY.ColumnEdit = this.rpsSpinAMT;",
        )

        result = self.verify(designer=broken)

        self.assertFalse(result.success)
        self.assertIn("numeric_repository_shared", self.ui_issue_codes(result))

    def test_stale_baseline_blocks_public_verifier(self):
        result = self.verify(
            baseline_designer_path=self.baseline_path,
            baseline_designer_sha256="0" * 64,
        )

        self.assertFalse(result.success)
        self.assertIn("baseline_designer_sha256_mismatch", self.ui_issue_codes(result))

    def test_orchestration_forwards_designer_ui_contract_receipt(self):
        sql = migration_tests.sp_metadata_header("Designer UI contract integration") + """
CREATE PROCEDURE DBO.SP_GENERALIZED_SELECT
    @WORKTYPE VARCHAR(20)
AS
BEGIN
    SELECT @WORKTYPE AS WORKTYPE;
END
"""
        csharp, _ = migration_tests.valid_csharp_contract_sources(form_class="TestBrowseForm")
        profile_path, profile_hash = migration_tests.write_packaged_profile(self.root)
        with migration_tests.patch_runtime_profile_path(profile_path):
            result = migration_tests.orchestrate_pb_migration_validation(
                csharp_source_text=csharp,
                designer_source_text=designer_source(),
                original_sql_text=sql,
                formatted_sql_text=sql,
                source_evidence=[
                    migration_tests.pasted_sql_evidence(
                        "SELECT @WORKTYPE AS WORKTYPE;",
                        evidence_role="body_fragment",
                    )
                ],
                profile_id="pb-csharp-offline-generalized",
                profile_version="1.0",
                profile_hash=profile_hash,
                program_key="TestBrowse",
                result_fields=["AMT", "QTY"],
                designer_ui_contract=self.contract(),
                expected_grid_role="list",
                expected_grid_columns=GRID_COLUMNS,
                layout_load_artifact_text=migration_tests.generate_devexpress_grid_xml(GRID_COLUMNS),
            )

        self.assertTrue(result.success, result.to_dict())
        self.assertTrue(result.metadata["evidence"]["csharp"]["designer_ui_contract"]["success"])


if __name__ == "__main__":
    unittest.main()
