import ast
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from src.skills.pb_designer_ui_contract import (
    parse_designer_source,
    validate_designer_tab_order_contract,
    validate_exact_baseline_property_preservation_contract,
    validate_exact_form_inheritance_contract,
    validate_label_editor_layout_contract,
    validate_numeric_repository_contract,
    validate_pb_field_lineage_contract,
    validate_pb_designer_ui_contract,
    validate_srd_caption_contract,
    validate_static_designer_ownership_contract,
    validate_year_only_dateedit_contract,
)


def issue_codes(result):
    return {issue["code"] for issue in result.issues}


def binary_runtime_receipt(path, digest, types):
    output = json.dumps(
        {"types": types}, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return {
        "receipt_id": "designer-chain-receipt-1",
        "host_id": "host-test-1",
        "runtime_id": "runtime-test-1",
        "producer_kind": "host_tool",
        "tool_call_id": "call-designer-chain-1",
        "tool_result_id": "result-designer-chain-1",
        "binary_path": str(path),
        "binary_sha256": digest,
        "type_chain_output": list(types),
        "type_chain_output_sha256": hashlib.sha256(output).hexdigest(),
        "timestamp": "2026-08-24T00:00:00+00:00",
        "exit_status": 0,
    }


def valid_designer_source():
    return r'''
private DevExpress.XtraEditors.PanelControl pnMain;
private DevExpress.XtraEditors.LabelControl lblAMT;
private DevExpress.XtraEditors.SpinEdit SpinAMT;
private DevExpress.XtraEditors.LabelControl lblBASYYYY;
private DevExpress.XtraEditors.DateEdit ymdBASYYYY;
private DevExpress.XtraGrid.GridControl grdList;
private DevExpress.XtraGrid.Columns.GridColumn colList_AMT;
private DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit rpsSpinAMT;

this.pnMain = new DevExpress.XtraEditors.PanelControl();
this.lblAMT = new DevExpress.XtraEditors.LabelControl();
this.SpinAMT = new DevExpress.XtraEditors.SpinEdit();
this.lblBASYYYY = new DevExpress.XtraEditors.LabelControl();
this.ymdBASYYYY = new DevExpress.XtraEditors.DateEdit();
this.grdList = new DevExpress.XtraGrid.GridControl();
this.colList_AMT = new DevExpress.XtraGrid.Columns.GridColumn();
this.rpsSpinAMT = new DevExpress.XtraEditors.Repository.RepositoryItemSpinEdit();

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
this.grdList.Location = new System.Drawing.Point(10, 150);
this.grdList.Size = new System.Drawing.Size(600, 180);
this.grdList.RepositoryItems.AddRange(new DevExpress.XtraEditors.Repository.RepositoryItem[] {
this.rpsSpinAMT});
this.colList_AMT.FieldName = "AMT";
this.colList_AMT.Caption = "Amount";
this.colList_AMT.ColumnEdit = this.rpsSpinAMT;
this.pnMain.Controls.Add(this.lblAMT);
this.pnMain.Controls.Add(this.SpinAMT);
this.pnMain.Controls.Add(this.lblBASYYYY);
this.pnMain.Controls.Add(this.ymdBASYYYY);
this.Controls.Add(this.pnMain);
this.Controls.Add(this.grdList);
this.Controls.SetChildIndex(this.pnMain, 0);
this.Controls.SetChildIndex(this.grdList, 1);
'''


class NumericRepositoryContractTests(unittest.TestCase):
    def test_requires_exact_field_specific_spin_repository(self):
        result = validate_numeric_repository_contract(valid_designer_source(), ["AMT"])

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["fields"][0]["repository_name"], "rpsSpinAMT")

    def test_rejects_shared_generic_repository_and_gridcolumn_displayformat(self):
        source = valid_designer_source().replace("rpsSpinAMT", "rpsSpinNumeric")
        source += '''
private DevExpress.XtraGrid.Columns.GridColumn colList_QTY;
this.colList_QTY = new DevExpress.XtraGrid.Columns.GridColumn();
this.colList_QTY.FieldName = "QTY";
this.colList_QTY.ColumnEdit = this.rpsSpinNumeric;
this.colList_AMT.DisplayFormat.FormatString = "{0:#,##0}";
'''
        result = validate_numeric_repository_contract(source, ["AMT", "QTY"])

        self.assertFalse(result.success)
        self.assertIn("numeric_repository_not_field_specific", issue_codes(result))
        self.assertIn("numeric_repository_shared", issue_codes(result))
        self.assertIn("numeric_gridcolumn_displayformat_forbidden", issue_codes(result))


class ExactInheritanceContractTests(unittest.TestCase):
    def test_accepts_only_direct_exact_form_or_usercontrol_inheritance(self):
        form = "public partial class SampleForm : System.Windows.Forms.Form { }"
        user_control = "internal partial class SampleView : UserControl { }"

        form_result = validate_exact_form_inheritance_contract(
            form,
            class_name="SampleForm",
            expected_base_type="Form",
        )
        control_result = validate_exact_form_inheritance_contract(
            user_control,
            class_name="SampleView",
            expected_base_type="System.Windows.Forms.UserControl",
        )

        self.assertTrue(form_result.success, form_result.to_dict())
        self.assertTrue(control_result.success, control_result.to_dict())

    def test_rejects_intermediate_or_wrong_base(self):
        result = validate_exact_form_inheritance_contract(
            "public partial class SampleForm : FrmDevBase { }",
            class_name="SampleForm",
            expected_base_type="Form",
        )

        self.assertIn("form_inheritance_not_exact", issue_codes(result))

    def test_accepts_custom_project_base_from_exact_source_artifact(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "FrmDevBase.cs"
            path.write_text(
                "namespace Company.Framework { "
                "public class FrmDevBase : System.Windows.Forms.Form { } }",
                encoding="utf-8",
            )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = validate_exact_form_inheritance_contract(
                "public partial class SampleForm : Company.Framework.FrmDevBase { }",
                class_name="SampleForm",
                expected_base_type="Company.Framework.FrmDevBase",
                base_type_evidence={
                    "artifact": {"kind": "source", "path": str(path), "sha256": digest},
                },
            )

        self.assertTrue(result.success, result.to_dict())
        provenance = result.metadata["base_type_provenance"]
        self.assertEqual("source", provenance["kind"])
        self.assertEqual("parsed_source_type_chain", provenance["type_proof_method"])
        self.assertTrue(provenance["type_proven"])

    def test_rejects_same_custom_base_name_when_source_hash_is_wrong(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "FrmDevBase.cs"
            path.write_text(
                "namespace Company.Framework { "
                "public class FrmDevBase : System.Windows.Forms.Form { } }",
                encoding="utf-8",
            )
            result = validate_exact_form_inheritance_contract(
                "public partial class SampleForm : Company.Framework.FrmDevBase { }",
                class_name="SampleForm",
                expected_base_type="Company.Framework.FrmDevBase",
                base_type_evidence={
                    "artifact": {"kind": "source", "path": str(path), "sha256": "0" * 64},
                },
            )

        self.assertIn("form_base_artifact_sha256_mismatch", issue_codes(result))
        self.assertFalse(result.metadata["base_type_provenance"]["type_proven"])

    def test_rejects_custom_or_binary_base_without_provenance_chain(self):
        missing = validate_exact_form_inheritance_contract(
            "public partial class SampleForm : Company.Framework.FrmDevBase { }",
            class_name="SampleForm",
            expected_base_type="Company.Framework.FrmDevBase",
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Company.Framework.dll"
            path.write_bytes(b"not-a-real-assembly-but-an-exact-binary-artifact")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            name_only = validate_exact_form_inheritance_contract(
                "public partial class SampleForm : Company.Framework.FrmDevBase { }",
                class_name="SampleForm",
                expected_base_type="Company.Framework.FrmDevBase",
                base_type_evidence={
                    "artifact": {"kind": "binary", "path": str(path), "sha256": digest},
                    "type_name": "Company.Framework.FrmDevBase",
                },
            )

        self.assertIn("form_base_provenance_missing", issue_codes(missing))
        self.assertIn("form_binary_type_chain_unproven", issue_codes(name_only))
        self.assertFalse(name_only.metadata["base_type_provenance"]["binary_type_proven_by_name"])

    def test_accepts_custom_project_base_from_trusted_binary_type_chain(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Company.Framework.dll"
            path.write_bytes(b"trusted-company-framework-binary")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = validate_exact_form_inheritance_contract(
                "public partial class SampleForm : Company.Framework.FrmDevBase { }",
                class_name="SampleForm",
                expected_base_type="Company.Framework.FrmDevBase",
                base_type_evidence={
                    "artifact": {"kind": "binary", "path": str(path), "sha256": digest},
                    "verified_type_chain": {
                        "status": "verified",
                        "verifier": "metadata-reader",
                        "artifact_path": str(path),
                        "artifact_sha256": digest,
                        "types": [
                            "Company.Framework.FrmDevBase",
                            "System.Windows.Forms.Form",
                        ],
                    },
                },
                runtime_receipt=binary_runtime_receipt(
                    path,
                    digest,
                    [
                        "Company.Framework.FrmDevBase",
                        "System.Windows.Forms.Form",
                    ],
                ),
            )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(
            "runtime_binary_type_chain",
            result.metadata["base_type_provenance"]["type_proof_method"],
        )

    def test_caller_verified_type_chain_claims_never_authenticate_binary(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Company.Framework.dll"
            path.write_bytes(b"caller-json-spoof")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = validate_exact_form_inheritance_contract(
                "public partial class SampleForm : Company.Framework.FrmDevBase { }",
                class_name="SampleForm",
                expected_base_type="Company.Framework.FrmDevBase",
                base_type_evidence={
                    "artifact": {"kind": "binary", "path": str(path), "sha256": digest},
                    "verified_type_chain": {
                        "status": "verified",
                        "trusted": True,
                        "verifier": "metadata-reader",
                        "artifact_path": str(path),
                        "artifact_sha256": digest,
                        "types": [
                            "Company.Framework.FrmDevBase",
                            "System.Windows.Forms.Form",
                        ],
                    },
                },
            )

        self.assertFalse(result.success)
        self.assertIn("form_binary_runtime_receipt_required", issue_codes(result))

    def test_binary_runtime_receipt_fields_are_adversarially_bound(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Company.Framework.dll"
            path.write_bytes(b"runtime-bound-binary")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            types = [
                "Company.Framework.FrmDevBase",
                "System.Windows.Forms.Form",
            ]
            evidence = {
                "artifact": {"kind": "binary", "path": str(path), "sha256": digest},
                "verified_type_chain": {"trusted": True, "verifier": "forged", "types": types},
            }
            valid = binary_runtime_receipt(path, digest, types)
            for field, value in (
                ("producer_kind", "caller_json"),
                ("tool_call_id", valid["tool_result_id"]),
                ("binary_sha256", "0" * 64),
                ("type_chain_output_sha256", "0" * 64),
                ("timestamp", "2026-08-24T00:00:00"),
                ("exit_status", 1),
            ):
                receipt = dict(valid)
                receipt[field] = value
                result = validate_exact_form_inheritance_contract(
                    "public partial class SampleForm : Company.Framework.FrmDevBase { }",
                    class_name="SampleForm",
                    expected_base_type="Company.Framework.FrmDevBase",
                    base_type_evidence=evidence,
                    runtime_receipt=receipt,
                )
                self.assertFalse(result.success, field)

    def test_rejects_ambiguous_imported_or_central_package_version(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Company.Framework.dll"
            path.write_bytes(b"exact-company-framework-binary")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = validate_exact_form_inheritance_contract(
                "public partial class SampleForm : Company.Framework.FrmDevBase { }",
                class_name="SampleForm",
                expected_base_type="Company.Framework.FrmDevBase",
                base_type_evidence={
                    "artifact": {"kind": "binary", "path": str(path), "sha256": digest},
                    "verified_type_chain": {
                        "status": "verified",
                        "verifier": "metadata-reader",
                        "artifact_path": str(path),
                        "artifact_sha256": digest,
                        "types": [
                            "Company.Framework.FrmDevBase",
                            "System.Windows.Forms.Form",
                        ],
                    },
                    "package": {
                        "source": "central",
                        "id": "Company.Framework",
                        "versions": ["4.2.0", "4.3.0"],
                    },
                },
            )

        self.assertIn("form_base_package_version_ambiguous", issue_codes(result))
        self.assertFalse(result.metadata["base_type_provenance"]["type_proven"])


class LabelEditorLayoutContractTests(unittest.TestCase):
    def test_accepts_aligned_pairs_inside_the_expected_container(self):
        pairs = [
            {"field_name": "AMT", "label_name": "lblAMT", "editor_name": "SpinAMT", "container": "pnMain"},
            {"field_name": "BASYYYY", "label_name": "lblBASYYYY", "editor_name": "ymdBASYYYY", "container": "pnMain"},
        ]

        result = validate_label_editor_layout_contract(valid_designer_source(), pairs)

        self.assertTrue(result.success, result.to_dict())

    def test_rejects_wrong_container_overlap_misalignment_and_clipping(self):
        source = valid_designer_source()
        source = source.replace("this.pnMain.Controls.Add(this.SpinAMT);", "this.Controls.Add(this.SpinAMT);")
        source = source.replace("new System.Drawing.Point(100, 10)", "new System.Drawing.Point(70, 40)")
        source = source.replace("new System.Drawing.Size(140, 23)", "new System.Drawing.Size(600, 100)")
        result = validate_label_editor_layout_contract(
            source,
            [{"field_name": "AMT", "label_name": "lblAMT", "editor_name": "SpinAMT", "container": "pnMain"}],
        )

        codes = issue_codes(result)
        self.assertIn("label_editor_container_mismatch", codes)
        self.assertIn("label_editor_wrong_container", codes)
        self.assertIn("label_editor_vertical_alignment_invalid", codes)
        self.assertIn("label_editor_horizontal_order_or_overlap_invalid", codes)
        self.assertIn("control_out_of_container_bounds", codes)

    def test_parses_tablelayout_pairs_and_rejects_a_shared_cell(self):
        source = r'''
private System.Windows.Forms.TableLayoutPanel tlpMain;
private DevExpress.XtraEditors.LabelControl lblCODE;
private DevExpress.XtraEditors.TextEdit txtCODE;
this.tlpMain = new System.Windows.Forms.TableLayoutPanel();
this.lblCODE = new DevExpress.XtraEditors.LabelControl();
this.txtCODE = new DevExpress.XtraEditors.TextEdit();
this.tlpMain.Size = new System.Drawing.Size(300, 80);
this.tlpMain.Controls.Add(this.lblCODE, 0, 0);
this.tlpMain.Controls.Add(this.txtCODE, 0, 0);
'''
        result = validate_label_editor_layout_contract(source, [("lblCODE", "txtCODE")])

        self.assertIn("label_editor_horizontal_order_invalid", issue_codes(result))
        self.assertIn("tablelayout_cell_overlap", issue_codes(result))


class YearOnlyDateEditContractTests(unittest.TestCase):
    def test_accepts_native_dateedit_with_year_mask_view_display_and_selection(self):
        result = validate_year_only_dateedit_contract(valid_designer_source(), ["BASYYYY"])

        self.assertTrue(result.success, result.to_dict())

    def test_rejects_incomplete_native_dateedit(self):
        source = valid_designer_source()
        source = source.replace('this.ymdBASYYYY.Properties.Mask.EditMask = "yyyy";', "")
        source = source.replace("this.ymdBASYYYY.Properties.Mask.UseMaskAsDisplayFormat = true;", "")
        source = source.replace("this.ymdBASYYYY.Properties.VistaCalendarViewStyle = DevExpress.XtraEditors.VistaCalendarViewStyle.YearView;", "")
        result = validate_year_only_dateedit_contract(source, ["BASYYYY"])

        self.assertIn("year_dateedit_static_contract_incomplete", issue_codes(result))
        missing = next(issue["missing"] for issue in result.issues if issue["code"] == "year_dateedit_static_contract_incomplete")
        self.assertIn("year_mask", missing)
        self.assertIn("year_display", missing)
        self.assertIn("year_selection", missing)

    def test_accepts_only_an_explicitly_proven_wrapper_without_native_properties(self):
        source = r'''
private Company.Controls.YearDateEdit ymdBASYYYY;
this.ymdBASYYYY = new Company.Controls.YearDateEdit();
'''
        rejected = validate_year_only_dateedit_contract(source, ["BASYYYY"])
        accepted = validate_year_only_dateedit_contract(
            source,
            ["BASYYYY"],
            proven_wrappers=[{"type_name": "Company.Controls.YearDateEdit", "proof": "wrapper-contract-sha"}],
        )

        self.assertFalse(rejected.success)
        self.assertTrue(accepted.success, accepted.to_dict())


class CaptionProvenanceContractTests(unittest.TestCase):
    def _write_srd(self, directory):
        path = Path(directory) / "detail.srd"
        source = '''release 7;
datawindow(units=0)
column(band=detail x="100" y="10" height="40" width="160" name=amt )
text(band=detail text="Amount from SRD" x="10" y="10" height="40" width="80" name=t_amt )
'''
        path.write_text(source, encoding="utf-8")
        return path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_rederives_caption_from_exact_temp_srd_path_sha_and_field_mapping(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path, digest = self._write_srd(temp_dir)
            source = valid_designer_source().replace('this.lblAMT.Text = "Amount";', 'this.lblAMT.Text = "Amount from SRD";')
            result = validate_srd_caption_contract(
                source,
                srd_path=path,
                srd_sha256=digest,
                field_mappings=[
                    {"field_name": "AMT", "srd_field_name": "amt", "srd_text_name": "t_amt", "designer_member": "lblAMT"}
                ],
            )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["field_mappings"][0]["caption"], "Amount from SRD")

    def test_rejects_stale_sha_and_does_not_trust_a_supplied_caption(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path, digest = self._write_srd(temp_dir)
            stale = validate_srd_caption_contract(
                valid_designer_source(),
                srd_path=path,
                srd_sha256="0" * 64,
                field_mappings=[{"field_name": "AMT", "srd_text_name": "t_amt", "designer_member": "lblAMT", "caption": "Amount"}],
            )
            mismatched = validate_srd_caption_contract(
                valid_designer_source(),
                srd_path=path,
                srd_sha256=digest,
                field_mappings=[{"field_name": "AMT", "srd_text_name": "t_amt", "designer_member": "lblAMT", "caption": "Amount"}],
            )

        self.assertIn("srd_sha256_mismatch", issue_codes(stale))
        self.assertIn("designer_caption_not_rederived_from_srd", issue_codes(mismatched))


class FieldLineageContractTests(unittest.TestCase):
    def test_binds_pb_field_to_result_bindingfield_grid_and_field_repository(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "lineage.srd"
            path.write_text(
                'column(band=detail x="100" y="10" height="40" width="160" name=amt )\n',
                encoding="utf-8",
            )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = validate_pb_field_lineage_contract(
                valid_designer_source(),
                srd_path=path,
                srd_sha256=digest,
                result_fields=["AMT"],
                field_lineages=[
                    {
                        "field_name": "AMT",
                        "pb_field_name": "amt",
                        "result_field_name": "AMT",
                        "binding_control_name": "SpinAMT",
                        "grid_column_name": "colList_AMT",
                        "numeric": True,
                    }
                ],
            )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["field_lineages"][0]["repository_name"], "rpsSpinAMT")

    def test_rejects_each_broken_lineage_link(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "lineage.srd"
            path.write_text(
                'column(band=detail x="100" y="10" height="40" width="160" name=other_field )\n',
                encoding="utf-8",
            )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            source = valid_designer_source().replace(
                'this.SpinAMT.BindingField = "AMT";',
                'this.SpinAMT.BindingField = "OTHER";',
            ).replace(
                'this.colList_AMT.FieldName = "AMT";',
                'this.colList_AMT.FieldName = "OTHER";',
            )
            result = validate_pb_field_lineage_contract(
                source,
                srd_path=path,
                srd_sha256=digest,
                result_fields=["OTHER"],
                field_lineages=[
                    {
                        "field_name": "AMT",
                        "pb_field_name": "amt",
                        "result_field_name": "AMT",
                        "binding_control_name": "SpinAMT",
                        "grid_column_name": "colList_AMT",
                        "numeric": True,
                    }
                ],
            )

        codes = issue_codes(result)
        self.assertIn("field_lineage_pb_field_missing", codes)
        self.assertIn("field_lineage_result_field_missing", codes)
        self.assertIn("field_lineage_bindingfield_mismatch", codes)
        self.assertIn("field_lineage_grid_fieldname_mismatch", codes)


class BaselinePreservationContractTests(unittest.TestCase):
    def test_preserves_every_sha_bound_baseline_static_property(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Sample.Designer.cs"
            path.write_text(valid_designer_source(), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = validate_exact_baseline_property_preservation_contract(
                valid_designer_source(),
                baseline_designer_path=path,
                baseline_designer_sha256=digest,
            )

        self.assertTrue(result.success, result.to_dict())
        self.assertGreater(len(result.metadata["preserved_properties"]), 10)

    def test_rejects_property_structure_and_sha_drift(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "Sample.Designer.cs"
            path.write_text(valid_designer_source(), encoding="utf-8")
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            changed = valid_designer_source().replace(
                'this.lblAMT.Text = "Amount";',
                'this.lblAMT.Text = "Changed";',
            ).replace(
                "this.pnMain.Controls.Add(this.lblAMT);",
                "this.Controls.Add(this.lblAMT);",
            )
            changed_result = validate_exact_baseline_property_preservation_contract(
                changed,
                baseline_designer_path=path,
                baseline_designer_sha256=digest,
            )
            stale_result = validate_exact_baseline_property_preservation_contract(
                valid_designer_source(),
                baseline_designer_path=path,
                baseline_designer_sha256="0" * 64,
            )

        self.assertIn("baseline_designer_property_changed", issue_codes(changed_result))
        self.assertIn("baseline_control_structure_changed", issue_codes(changed_result))
        self.assertIn("baseline_designer_sha256_mismatch", issue_codes(stale_result))


class ContainmentAndTabOrderTests(unittest.TestCase):
    def test_parses_panel_group_table_add_and_setchildindex(self):
        source = r'''
private DevExpress.XtraEditors.GroupControl grpOne;
private System.Windows.Forms.TableLayoutPanel tlpTwo;
private DevExpress.XtraEditors.TextEdit txtA;
private DevExpress.XtraEditors.TextEdit txtB;
private DevExpress.XtraEditors.TextEdit txtC;
this.grpOne = new DevExpress.XtraEditors.GroupControl();
this.tlpTwo = new System.Windows.Forms.TableLayoutPanel();
this.txtA = new DevExpress.XtraEditors.TextEdit();
this.txtB = new DevExpress.XtraEditors.TextEdit();
this.txtC = new DevExpress.XtraEditors.TextEdit();
this.txtA.Location = new System.Drawing.Point(10, 10);
this.txtA.TabIndex = 0;
this.txtB.Location = new System.Drawing.Point(120, 10);
this.txtB.TabIndex = 1;
this.txtC.TabIndex = 0;
this.grpOne.Controls.Add(this.txtA);
this.grpOne.Controls.Add(this.txtB);
this.tlpTwo.Controls.Add(this.txtC, 1, 0);
this.Controls.Add(this.grpOne);
this.Controls.Add(this.tlpTwo);
this.Controls.SetChildIndex(this.grpOne, 0);
this.Controls.SetChildIndex(this.tlpTwo, 1);
'''
        model = parse_designer_source(source)
        result = validate_designer_tab_order_contract(source)

        self.assertEqual(model.controls["txtA"].parent, "grpOne")
        self.assertEqual(model.controls["txtC"].table_position, (1, 0))
        self.assertEqual(model.controls["grpOne"].child_index, 0)
        self.assertTrue(result.success, result.to_dict())

    def test_rejects_non_spatial_non_contiguous_and_duplicate_tabindex(self):
        source = valid_designer_source().replace("this.SpinAMT.TabIndex = 0;", "this.SpinAMT.TabIndex = 2;")
        source = source.replace("this.ymdBASYYYY.TabIndex = 1;", "this.ymdBASYYYY.TabIndex = 2;")
        result = validate_designer_tab_order_contract(source)

        self.assertIn("input_tabindex_duplicate", issue_codes(result))
        self.assertIn("input_tabindex_spatial_order_invalid", issue_codes(result))


class DesignerOwnershipAndAggregateTests(unittest.TestCase):
    def test_rejects_static_properties_and_collection_wiring_in_code_behind(self):
        code_behind = r'''
private void ConfigureRuntime()
{
    this.SpinAMT.Location = new System.Drawing.Point(5, 5);
    this.colList_AMT.Caption = "Runtime caption";
    this.pnMain.Controls.Add(this.SpinAMT);
}
'''
        result = validate_static_designer_ownership_contract(valid_designer_source(), code_behind)

        self.assertIn("static_designer_property_in_code_behind", issue_codes(result))
        self.assertIn("static_collection_wiring_in_code_behind", issue_codes(result))

    def test_aggregate_contract_passes_with_a_temp_srd(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "detail.srd"
            path.write_text(
                'column(band=detail x="100" y="10" height="40" width="160" name=amt )\n'
                'text(band=detail text="Amount" x="10" y="10" height="40" width="80" name=t_amt )\n',
                encoding="utf-8",
            )
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            result = validate_pb_designer_ui_contract(
                valid_designer_source(),
                numeric_fields=["AMT"],
                label_editor_pairs=[{"field_name": "AMT", "label_name": "lblAMT", "editor_name": "SpinAMT", "container": "pnMain"}],
                year_fields=["BASYYYY"],
                srd_path=path,
                srd_sha256=digest,
                caption_field_mappings=[{"field_name": "AMT", "srd_text_name": "t_amt", "designer_member": "lblAMT"}],
            )

        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["static_properties_owner"], "Designer")

    def test_both_new_python_files_parse_as_ast(self):
        root = Path(__file__).resolve().parents[1]
        for relative_path in (
            "src/skills/pb_designer_ui_contract.py",
            "tests/test_pb_designer_ui_contract.py",
        ):
            ast.parse((root / relative_path).read_text(encoding="utf-8"), filename=relative_path)


if __name__ == "__main__":
    unittest.main()
