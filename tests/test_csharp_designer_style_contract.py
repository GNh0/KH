import ast
import hashlib
import inspect
import json
import tempfile
import unittest
from pathlib import Path

import src.skills.csharp_designer_style_contract as style_contract_module
from src.contracts import HarnessResult
from src.skills.csharp_designer_style import verify_csharp_edit_contract
from src.skills.csharp_designer_style_contract import (
    PACKAGED_CONTRACT_PATH,
    load_packaged_style_contract,
    verify_csharp_designer_style,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPO_ROOT / "src" / "skills" / "csharp_designer_style_contract.py"


VALID_SOURCE = '''
using System;
using System.Data;

public partial class DemoForm : FrmDevBase
{
    public DemoForm() { InitializeComponent(); }

    private DataSet CallSelectProcedure(SelectType selectType)
    {
        try { return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType)); }
        catch (Exception ex) { ShowExcetion(ex); return null; }
    }

    private bool CallSaveProcedure()
    {
        try { return dbClient.ExecSP("sp_DEMO_SAVE", new SqlParameter("@SAVE", true)); }
        catch (Exception ex) { ShowExcetion(ex); return false; }
    }

    private void DemoForm_Load(object sender, EventArgs e)
    {
        DataSet ds = CallSelectProcedure(SelectType.LIST);
        bool saved = CallSaveProcedure();
        grdList.DataSource = ds.Tables[0];
        ClearScreen();
        RefreshList();
    }

    private void ClearScreen() { devFnc.InitControl(grdList); }
    private void RefreshList() { devFnc.GridToPanel(gvwList); }
}
'''


VALID_DESIGNER = '''
using System;
using DevExpress.XtraGrid.Columns;
using DevExpress.XtraGrid.Views.Grid;
using DevExpress.XtraEditors.Repository;

public partial class DemoForm : FrmDevBase
{
    private DevExpress.XtraGrid.GridControl grdList;
    private GridView gvwList;
    private GridColumn colList_PGMDIV;
    private GridColumn colList_QTY;
    private RepositoryItemSpinEdit rpsSpinQTY;
    private DevExpress.XtraEditors.TextEdit txtPGMDIV;
    private DevExpress.XtraEditors.SimpleButton btnSearch;

    private void InitializeComponent()
    {
        this.grdList = new DevExpress.XtraGrid.GridControl();
        this.gvwList = new GridView();
        this.colList_PGMDIV = new GridColumn();
        this.colList_QTY = new GridColumn();
        this.rpsSpinQTY = new RepositoryItemSpinEdit();
        this.txtPGMDIV = new DevExpress.XtraEditors.TextEdit();
        this.btnSearch = new DevExpress.XtraEditors.SimpleButton();
        this.grdList.MainView = this.gvwList;
        this.grdList.RepositoryItems.AddRange(new DevExpress.XtraEditors.Repository.RepositoryItem[] { this.rpsSpinQTY });
        this.colList_PGMDIV.FieldName = "PGMDIV";
        this.colList_PGMDIV.Name = "colList_PGMDIV";
        this.colList_PGMDIV.VisibleIndex = 1;
        this.colList_QTY.FieldName = "QTY";
        this.colList_QTY.Name = "colList_QTY";
        this.colList_QTY.VisibleIndex = 2;
        this.colList_QTY.ColumnEdit = this.rpsSpinQTY;
        this.gvwList.Columns.AddRange(new GridColumn[] { this.colList_PGMDIV, this.colList_QTY });
        this.txtPGMDIV.BindingField = "PGMDIV";
        this.txtPGMDIV.TabIndex = 0;
        this.btnSearch.TabIndex = 1;
        this.Load += new EventHandler(this.DemoForm_Load);
    }
}
'''


def _write_pair(root: Path, source: str = VALID_SOURCE, designer: str = VALID_DESIGNER):
    root.mkdir(parents=True, exist_ok=True)
    source_path = root / "DemoForm.cs"
    designer_path = root / "DemoForm.Designer.cs"
    source_path.write_text(source, encoding="utf-8", newline="")
    designer_path.write_text(designer, encoding="utf-8", newline="")
    return (
        {"path": str(source_path), "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest()},
        {"path": str(designer_path), "sha256": hashlib.sha256(designer_path.read_bytes()).hexdigest()},
    )


def _issues(result):
    return {item["code"] for item in result.metadata["issues"]}


class CSharpDesignerStyleContractTests(unittest.TestCase):
    def test_edit_guard_blocks_no_modifier_type_method_removal(self):
        original = """
public class DemoForm
{
    void ImportantHelper()
    {
        RefreshList();
    }
}
"""
        candidate = """
public class DemoForm
{
}
"""

        result = verify_csharp_edit_contract(original, candidate)

        self.assertFalse(result.success)
        self.assertIn("target_local_helper_removed", _issues(result))
        self.assertIn(
            "ImportantHelper`0()",
            {
                item.get("evidence", {}).get("signature")
                for item in result.metadata["issues"]
            },
        )

    def test_edit_guard_does_not_inventory_local_functions_or_control_flow(self):
        original = """
public class DemoForm
{
    void RunWork()
    {
        void ImportantHelper()
        {
            RefreshList();
        }

        if (IsReady())
        {
            ImportantHelper();
        }
    }
}
"""
        candidate = """
public class DemoForm
{
    void RunWork()
    {
        while (IsReady())
        {
            RefreshList();
        }
    }
}
"""

        result = verify_csharp_edit_contract(original, candidate)

        self.assertTrue(result.success, result.to_dict())

    def test_edit_guard_exempts_no_modifier_event_handler_signature(self):
        original = """
public class DemoForm
{
    void btnSave_Click(object sender, EventArgs e)
    {
        SaveData();
    }
}
"""
        candidate = """
public class DemoForm
{
}
"""

        result = verify_csharp_edit_contract(original, candidate)

        self.assertTrue(result.success, result.to_dict())

    def test_edit_guard_blocks_suffix_named_zero_parameter_helper_removal(self):
        original = """
private void ApplyDefaults_Changed()
{
    ApplyDefaults();
}
"""

        result = verify_csharp_edit_contract(original, "")

        self.assertFalse(result.success)
        self.assertIn("target_local_helper_removed", _issues(result))

    def test_edit_guard_exempts_real_event_signature_and_designer_wiring(self):
        signature_handler = """
private void btnSave_Click(object sender, EventArgs e)
{
    SaveData();
}
"""
        wired_handler = """
private void CustomRefresh_Changed()
{
    RefreshList();
}
"""
        designer = """
this.btnRefresh.Click += new System.EventHandler(this.CustomRefresh_Changed);
"""

        signature_result = verify_csharp_edit_contract(signature_handler, "")
        wired_result = verify_csharp_edit_contract(
            wired_handler,
            "",
            designer_source=designer,
        )

        self.assertTrue(signature_result.success, signature_result.to_dict())
        self.assertTrue(wired_result.success, wired_result.to_dict())

    def test_valid_canonical_pair_returns_harness_result_with_exact_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp))
            result = verify_csharp_designer_style(
                source,
                designer,
                native_helpers=["ClearScreen", "RefreshList"],
                expected_identities={
                    "procedures": ["sp_DEMO_SELECT", "sp_DEMO_SAVE"],
                    "controls": ["grdList", "colList_QTY"],
                    "fields": ["grdList", "colList_QTY"],
                    "methods": ["CallSelectProcedure", "CallSaveProcedure"],
                },
            )

        self.assertIsInstance(result, HarnessResult)
        self.assertTrue(result.success, result.metadata["issues"])
        self.assertEqual(result.exit_code, 0)
        self.assertEqual(result.metadata["source_receipt"]["actual_sha256"], f"sha256:{source['sha256']}")
        self.assertEqual(result.metadata["designer_receipt"]["actual_sha256"], f"sha256:{designer['sha256']}")
        self.assertFalse(result.metadata["writes_performed"])
        self.assertEqual(result.metadata["discovery"]["root_search"], False)

    def test_adversarial_noncanonical_methods_column_and_codebehind_event_are_blocked(self):
        bad_source = VALID_SOURCE.replace(
            "private DataSet CallSelectProcedure(SelectType selectType)",
            "private DataSet CallViewQuery(SelectType selectType)\n    { return null; }\n\n    private DataSet CallSelectProcedure(SelectType selectType)",
        ).replace(
            "private bool CallSaveProcedure()",
            "private bool CallSaveQuery() { return false; }\n\n    private bool CallSaveProcedure()",
        ).replace(
            "private void DemoForm_Load",
            "private void Wire() { this.Load += DemoForm_Load; }\n\n    private void DemoForm_Load",
        )
        bad_designer = VALID_DESIGNER.replace("colList_PGMDIV", "colPGMDIV")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), bad_source, bad_designer)
            result = verify_csharp_designer_style(source, designer)

        codes = {item["code"] for item in result.metadata["issues"]}
        self.assertFalse(result.success)
        self.assertIn("noncanonical_method_family", codes)
        self.assertIn("grid_column_name_noncanonical", codes)
        self.assertIn("codebehind_event_subscription", codes)

    def test_identity_exception_is_never_authorized_in_standalone_mode(self):
        bad_designer = VALID_DESIGNER.replace("colList_PGMDIV", "colPGMDIV")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root, designer=bad_designer)
            identity = {"scope": "designer", "identity": "colPGMDIV", "reason": "target control"}
            plain = verify_csharp_designer_style(
                source,
                designer,
                identity_exceptions=[identity],
            )
            forged = verify_csharp_designer_style(
                source,
                designer,
                identity_exceptions=[{**identity, "provenance": {"kind": "host_runtime", "signature": "caller-owned"}}],
            )

        for result in (plain, forged):
            self.assertIn("identity_exception_not_supported_standalone", _issues(result))
            self.assertIn("grid_column_name_noncanonical", _issues(result))
        self.assertNotEqual(plain.metadata["verification_id"], forged.metadata["verification_id"])

    def test_receipt_mismatch_is_reported_without_writes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root)
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))
            bad_source = dict(source)
            bad_source["sha256"] = "0" * 64
            result = verify_csharp_designer_style(bad_source, designer)
            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))

        self.assertFalse(result.success)
        self.assertIn("artifact_sha256_mismatch", {item["code"] for item in result.metadata["issues"]})
        self.assertEqual(before, after)

    def test_receipts_require_absolute_existing_paths(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root)
            relative_source = dict(source)
            relative_source["path"] = "DemoForm.cs"
            missing_designer = dict(designer)
            missing_designer["path"] = str(root / "missing.Designer.cs")
            result = verify_csharp_designer_style(relative_source, missing_designer)

        codes = _issues(result)
        self.assertIn("artifact_receipt_path_not_absolute", codes)
        self.assertIn("artifact_receipt_path_missing", codes)

    def test_user_fake_provenance_and_boolean_provenance_are_rejected(self):
        bad_designer = VALID_DESIGNER.replace("colList_PGMDIV", "colPGMDIV")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), designer=bad_designer)
            result = verify_csharp_designer_style(
                source,
                designer,
                identity_exceptions=[
                    {
                        "scope": "designer",
                        "identity": "colPGMDIV",
                        "reason": "legacy target",
                        "provenance": {"kind": "target", "locator": "user://fake", "sha256": True},
                    }
                ],
            )

        self.assertIn("identity_exception_not_supported_standalone", _issues(result))
        self.assertIn("grid_column_name_noncanonical", _issues(result))

    def test_forged_host_receipt_cannot_authorize_identity_exception(self):
        bad_designer = VALID_DESIGNER.replace("colList_PGMDIV", "colPGMDIV")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root, designer=bad_designer)
            identity = {"scope": "designer", "identity": "colPGMDIV", "reason": "legacy target"}
            receipt_path = root / "caller-evidence.json"
            receipt_path.write_text(json.dumps({"identity_exceptions": [identity]}), encoding="utf-8")
            result = verify_csharp_designer_style(
                source,
                designer,
                identity_exceptions=[{
                    **identity,
                    "provenance": {
                        "kind": "host_runtime",
                        "receipt_path": str(receipt_path.resolve()),
                        "sha256": hashlib.sha256(receipt_path.read_bytes()).hexdigest(),
                        "signature": "caller-generated-signature",
                    },
                }],
            )

        self.assertIn("identity_exception_not_supported_standalone", _issues(result))
        self.assertIn("grid_column_name_noncanonical", _issues(result))

    def test_standalone_does_not_interpret_identity_exception_receipt_paths(self):
        bad_designer = VALID_DESIGNER.replace("colList_PGMDIV", "colPGMDIV")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root, designer=bad_designer)
            identity = {"scope": "designer", "identity": "colPGMDIV", "reason": "legacy target"}
            relative_result = verify_csharp_designer_style(
                source,
                designer,
                identity_exceptions=[{**identity, "provenance": {"receipt_path": "host-evidence.json"}}],
            )
            absolute_result = verify_csharp_designer_style(
                source,
                designer,
                identity_exceptions=[{**identity, "provenance": {"receipt_path": str((root / "host-evidence.json").resolve())}}],
            )

        self.assertIn("identity_exception_not_supported_standalone", _issues(relative_result))
        self.assertIn("identity_exception_not_supported_standalone", _issues(absolute_result))
        self.assertIn("grid_column_name_noncanonical", _issues(relative_result))
        self.assertIn("grid_column_name_noncanonical", _issues(absolute_result))

    def test_lexical_masker_does_not_let_string_comment_markers_hide_code(self):
        noise = '''
    private const string RegularNoise = "// this.Load += FakeEvent;";
    private const string VerbatimNoise = @"// new GridColumn();";
    private const string RawNoise = """// grdList.Columns.Add(new GridColumn());""";
    private const string InterpolatedNoise = $"// this.CustomEvent += FakeHandler;";
'''
        source_text = VALID_SOURCE.replace("public partial class DemoForm : FrmDevBase\n{", "public partial class DemoForm : FrmDevBase\n{" + noise)
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertTrue(result.success, result.metadata["issues"])

    def test_string_double_slash_does_not_hide_later_real_event_subscription(self):
        injected = '''
    private void WireRuntimeEvent()
    {
        string marker = "// this is data, not a comment";
        this.gvwList.CustomDrawCell += DemoForm_Load;
    }
'''
        source_text = VALID_SOURCE.replace("    private void DemoForm_Load", injected + "    private void DemoForm_Load")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertIn("codebehind_event_subscription", _issues(result))

    def test_event_unsubscription_and_comment_or_string_noise_do_not_count_as_subscription(self):
        injected = '''
    private const string EventNoise = "this.gvwList.CustomDrawCell += DemoForm_Load";
    // this.gvwList.CustomDrawCell += DemoForm_Load;
    private void UnwireRuntimeEvent()
    {
        this.gvwList.CustomDrawCell -= DemoForm_Load;
    }
'''
        source_text = VALID_SOURCE.replace("    private void DemoForm_Load", injected + "    private void DemoForm_Load")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertNotIn("codebehind_event_subscription", _issues(result))

    def test_arbitrary_usercontrol_and_caller_declared_base_chain_are_rejected(self):
        bad_source = VALID_SOURCE.replace("FrmDevBase", "UserControl")
        bad_designer = VALID_DESIGNER.replace("FrmDevBase", "UserControl")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root, bad_source, bad_designer)
            bad = verify_csharp_designer_style(source, designer)
            chained_source = VALID_SOURCE.replace(
                "public partial class DemoForm : FrmDevBase",
                "public class CustomFormBase : FrmDevBase { }\n\npublic partial class DemoForm : CustomFormBase",
            )
            chained_designer = VALID_DESIGNER.replace("public partial class DemoForm : FrmDevBase", "public partial class DemoForm : CustomFormBase")
            chained_root = root / "chained"
            chained_root.mkdir()
            chained, chained_designer_receipt = _write_pair(chained_root, chained_source, chained_designer)
            chained_result = verify_csharp_designer_style(chained, chained_designer_receipt)

        self.assertIn("base_type_not_packaged", _issues(bad))
        self.assertIn("base_type_not_packaged", _issues(chained_result))

    def test_source_designer_base_mismatch_and_decoy_partial_classes_are_rejected(self):
        mismatched_source = VALID_SOURCE.replace("DemoForm : FrmDevBase", "DemoForm : UserControl")
        decoy_source = VALID_SOURCE.replace(
            "public partial class DemoForm : FrmDevBase",
            "public partial class DecoyForm : FrmDevBase { }\n\npublic partial class DemoForm : FrmDevBase",
        )
        decoy_designer = VALID_DESIGNER.replace(
            "public partial class DemoForm : FrmDevBase",
            "public partial class DecoyForm : FrmDevBase { }\n\npublic partial class DemoForm : FrmDevBase",
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            mismatch_pair = _write_pair(root / "mismatch", mismatched_source, VALID_DESIGNER)
            decoy_pair = _write_pair(root / "decoy", decoy_source, decoy_designer)
            mismatch = verify_csharp_designer_style(*mismatch_pair)
            decoy = verify_csharp_designer_style(*decoy_pair)

        self.assertIn("partial_base_type_mismatch", _issues(mismatch))
        self.assertIn("base_type_not_packaged", _issues(mismatch))
        self.assertIn("partial_class_set_ambiguous", _issues(decoy))

    def test_caller_type_chain_evidence_is_never_authoritative_standalone(self):
        source_text = VALID_SOURCE.replace("DemoForm : FrmDevBase", "DemoForm : CustomBinaryBase")
        designer_text = VALID_DESIGNER.replace("DemoForm : FrmDevBase", "DemoForm : CustomBinaryBase")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root, source_text, designer_text)
            result = verify_csharp_designer_style(
                source,
                designer,
                type_chain_evidence={"kind": "binary", "derived": "CustomBinaryBase", "base": "FrmDevBase"},
            )

        self.assertIn("type_chain_evidence_not_supported_standalone", _issues(result))
        self.assertIn("base_type_not_packaged", _issues(result))

    def test_codebehind_ui_mutation_catches_initialized_fields_runtime_creation_column_add_and_any_event(self):
        injected = '''
    private GridColumn badColumn = new GridColumn();

    private void BuildRuntimeUi()
    {
        new GridControl();
        grdList.Columns.Add(new GridColumn());
        colList_QTY.Caption = "Quantity";
        this.CustomEvent += DemoForm_Load;
    }
'''
        source_text = VALID_SOURCE.replace("    private void DemoForm_Load", injected + "    private void DemoForm_Load")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        codes = _issues(result)
        self.assertIn("control_declaration_in_codebehind", codes)
        self.assertIn("grid_runtime_creation_in_codebehind", codes)
        self.assertIn("grid_registration_in_codebehind", codes)
        self.assertIn("static_ui_assignment_in_codebehind", codes)
        self.assertIn("codebehind_event_subscription", codes)

    def test_expected_identities_require_parsed_tokens_and_real_procedure_calls(self):
        source_text = VALID_SOURCE.replace(
            "    public DemoForm() { InitializeComponent(); }",
            '    public DemoForm() { InitializeComponent(); }\n    // ghostControl, ghostField, GhostMethod, and sp_GHOST_SELECT\n    private const string FakeIdentity = "ghostControl ghostField GhostMethod sp_GHOST_SELECT";'
        )
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(
                source,
                designer,
                expected_identities={
                    "controls": ["ghostControl"],
                    "procedures": ["sp_GHOST_SELECT"],
                    "fields": ["ghostField"],
                    "methods": ["GhostMethod"],
                },
            )

        codes = _issues(result)
        self.assertIn("stale_or_missing_control_identity", codes)
        self.assertIn("stale_or_missing_procedure_identity", codes)
        self.assertIn("stale_or_missing_field_identity", codes)
        self.assertIn("stale_or_missing_method_identity", codes)

    def test_db_and_sql_parameter_names_and_constructor_shapes_are_validated(self):
        injected = '''
    private void Parameters()
    {
        new DbParameter("bad", 1);
        new DbParameter("@ONLY");
        new SqlParameter("@bad", 1);
        new SqlParameter("@GOOD", 1);
    }
'''
        source_text = VALID_SOURCE.replace("    private void DemoForm_Load", injected + "    private void DemoForm_Load")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        codes = _issues(result)
        self.assertIn("db_parameter_name_invalid", codes)
        self.assertIn("db_parameter_shape_invalid", codes)
        self.assertIn("sql_parameter_name_invalid", codes)
        self.assertNotIn("sql_parameter_shape_invalid", codes)

    def test_method_names_in_strings_do_not_satisfy_declaration_or_call_contract(self):
        query_block = '''    private DataSet CallSelectProcedure(SelectType selectType)
    {
        try { return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType)); }
        catch (Exception ex) { ShowExcetion(ex); return null; }
    }

'''
        source_text = VALID_SOURCE.replace(query_block, '    private const string FakeMethod = "CallSelectProcedure(SelectType.LIST)";\n\n')
        source_text = source_text.replace("        DataSet ds = CallSelectProcedure(SelectType.LIST);", "        DataSet ds = null;")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer, applicable_operations=["query"])

        self.assertIn("canonical_method_missing", _issues(result))

    def test_sp_and_parameter_strings_or_declarations_do_not_count_as_call_sites(self):
        original = '''    private DataSet CallSelectProcedure(SelectType selectType)
    {
        try { return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType)); }
        catch (Exception ex) { ShowExcetion(ex); return null; }
    }
'''
        replacement = '''    private DataSet CallSelectProcedure(SelectType selectType)
    {
        try
        {
            string procedure = "sp_DEMO_SELECT";
            string parameterExample = "new DbParameter(\\\"@SELECT\\\", selectType)";
            DbParameter declaredOnly;
            return null;
        }
        catch (Exception ex) { ShowExcetion(ex); return null; }
    }
'''
        source_text = VALID_SOURCE.replace(original, replacement)
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer, applicable_operations=["query"])

        codes = _issues(result)
        self.assertIn("stored_procedure_invocation_missing", codes)
        self.assertIn("db_parameter_callsite_missing", codes)

    def test_local_fake_sp_method_and_detached_parameter_do_not_satisfy_runtime_call(self):
        fake_call = VALID_SOURCE.replace(
            'return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType));',
            'return this.ExecSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType));',
        ).replace(
            "    private DataSet CallSelectProcedure(SelectType selectType)",
            "    private DataSet ExecSP(string name, DbParameter parameter) { return null; }\n\n    private DataSet CallSelectProcedure(SelectType selectType)",
        )
        detached_parameter = VALID_SOURCE.replace(
            'try { return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType)); }',
            'try { DbParameter parameter = new DbParameter("@SELECT", selectType); return dbClient.GetDataSetFromSP("sp_DEMO_SELECT"); }',
        )
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fake_pair = _write_pair(root / "fake", fake_call)
            detached_pair = _write_pair(root / "detached", detached_parameter)
            fake = verify_csharp_designer_style(*fake_pair, applicable_operations=["query"])
            detached = verify_csharp_designer_style(*detached_pair, applicable_operations=["query"])

        self.assertIn("stored_procedure_invocation_missing", _issues(fake))
        self.assertIn("db_parameter_callsite_missing", _issues(fake))
        self.assertNotIn("stored_procedure_invocation_missing", _issues(detached))
        self.assertIn("db_parameter_callsite_missing", _issues(detached))

    def test_catch_blocks_require_packaged_error_reporting(self):
        source_text = VALID_SOURCE.replace("ShowExcetion(ex)", "Console.WriteLine(ex)")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertIn("catch_error_reporting_missing", _issues(result))

    def test_self_declared_empty_error_reporter_does_not_satisfy_catch_contract(self):
        source_text = VALID_SOURCE.replace(
            "    private DataSet CallSelectProcedure(SelectType selectType)",
            "    private void ShowExcetion(Exception ex) { }\n\n    private DataSet CallSelectProcedure(SelectType selectType)",
        )
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertIn("catch_error_reporting_missing", _issues(result))

    def test_self_declared_clear_helper_is_not_native_authority(self):
        source_text = VALID_SOURCE.replace(
            "    private void ClearScreen() { devFnc.InitControl(grdList); }",
            "    private void ClearScreen() { ClearLocalState(); }\n    private void ClearLocalState() { }",
        ).replace("        ClearScreen();", "        ClearLocalState();")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer, native_helpers=["ClearLocalState"])

        self.assertIn("native_helper_self_declared", _issues(result))

    def test_self_declared_packaged_helper_name_does_not_fake_native_delegation(self):
        source_text = VALID_SOURCE.replace(
            "    private void ClearScreen() { devFnc.InitControl(grdList); }",
            "    private void ClearScreen() { InitControl(grdList); }\n    private void InitControl(object value) { }",
        )
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer, native_helpers=["ClearScreen"])

        self.assertIn("native_helper_self_declared", _issues(result))

    def test_public_verifier_has_no_caller_controlled_authentication_surface(self):
        signature = inspect.signature(verify_csharp_designer_style)
        self.assertNotIn("trusted_runtime_roots", signature.parameters)
        self.assertNotIn("provenance_authenticator", signature.parameters)
        self.assertFalse(hasattr(style_contract_module, "_HOST_CONTEXT_SEAL"))
        self.assertFalse(hasattr(style_contract_module, "_create_authenticated_host_context"))
        self.assertFalse(hasattr(style_contract_module, "_verify_csharp_designer_style_authenticated"))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root)
            with self.assertRaises(TypeError):
                verify_csharp_designer_style(
                    source,
                    designer,
                    trusted_runtime_roots=[root],
                    provenance_authenticator=lambda _raw, _signature: True,
                )

    def test_real_program_key_screen_identity_does_not_require_form_suffix(self):
        source_text = VALID_SOURCE.replace("DemoForm", "SA900100")
        designer_text = VALID_DESIGNER.replace("DemoForm", "SA900100")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text, designer_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertNotIn("form_class_noncanonical", _issues(result))

    def test_local_shadow_of_packaged_base_is_rejected(self):
        source_text = "public class FrmDevBase { }\n" + VALID_SOURCE
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertIn("packaged_base_type_locally_shadowed", _issues(result))
        self.assertIn("base_type_not_packaged", _issues(result))

    def test_escaped_local_shadow_of_packaged_base_is_rejected(self):
        source_text = "public class @FrmDevBase { }\n" + VALID_SOURCE
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertIn("packaged_base_type_locally_shadowed", _issues(result))
        self.assertIn("base_type_not_packaged", _issues(result))

    def test_packaged_base_aliases_and_qualified_name_tricks_are_rejected(self):
        cases = (
            ("alias", "using FrmDevBase = External.FrmDevBase;\n" + VALID_SOURCE, VALID_DESIGNER, "packaged_base_type_aliased"),
            ("escaped_alias", "using @FrmDevBase = External.FrmDevBase;\n" + VALID_SOURCE, VALID_DESIGNER, "packaged_base_type_aliased"),
            (
                "qualified",
                VALID_SOURCE.replace("DemoForm : FrmDevBase", "DemoForm : External.FrmDevBase"),
                VALID_DESIGNER.replace("DemoForm : FrmDevBase", "DemoForm : External.FrmDevBase"),
                "base_type_not_packaged",
            ),
        )
        for name, source_text, designer_text, expected_issue in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                source, designer = _write_pair(Path(tmp), source_text, designer_text)
                result = verify_csharp_designer_style(source, designer)
            self.assertIn(expected_issue, _issues(result))
            self.assertIn("base_type_not_packaged", _issues(result))

    def test_fake_database_and_error_reporter_receivers_are_rejected(self):
        source_text = VALID_SOURCE.replace("dbClient.", "fakeDb.").replace(
            "ShowExcetion(ex)",
            "fakeReporter.ShowExcetion(ex)",
        )
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        codes = _issues(result)
        self.assertIn("stored_procedure_invocation_missing", codes)
        self.assertIn("catch_error_reporting_missing", codes)

    def test_local_fake_db_named_dbclient_is_rejected(self):
        source_text = VALID_SOURCE.replace(
            "public partial class DemoForm : FrmDevBase\n{",
            "public partial class DemoForm : FrmDevBase\n{\n    private FakeDb dbClient;",
        )
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertIn("approved_receiver_locally_shadowed", _issues(result))
        self.assertIn("stored_procedure_invocation_missing", _issues(result))

    def test_local_fake_logger_named_logger_is_rejected(self):
        source_text = VALID_SOURCE.replace(
            "public partial class DemoForm : FrmDevBase\n{",
            "public partial class DemoForm : FrmDevBase\n{\n    private FakeLogger logger;",
        ).replace("ShowExcetion(ex)", "logger.Error(ex)")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertIn("approved_receiver_locally_shadowed", _issues(result))
        self.assertIn("catch_error_reporting_missing", _issues(result))

    def test_escaped_dbclient_and_logger_receiver_shadows_are_rejected(self):
        cases = (
            (
                "db",
                VALID_SOURCE.replace(
                    "public partial class DemoForm : FrmDevBase\n{",
                    "public partial class DemoForm : FrmDevBase\n{\n    private FakeDb @dbClient;",
                ).replace("dbClient.", "@dbClient."),
                {"approved_receiver_locally_shadowed", "stored_procedure_invocation_missing"},
            ),
            (
                "logger",
                VALID_SOURCE.replace(
                    "public partial class DemoForm : FrmDevBase\n{",
                    "public partial class DemoForm : FrmDevBase\n{\n    private FakeLogger @logger;",
                ).replace("ShowExcetion(ex)", "@logger.Error(ex)"),
                {"approved_receiver_locally_shadowed", "catch_error_reporting_missing"},
            ),
        )
        for name, source_text, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as tmp:
                source, designer = _write_pair(Path(tmp), source_text)
                result = verify_csharp_designer_style(source, designer)
            self.assertTrue(expected <= _issues(result), result.metadata["issues"])

    def test_local_delegate_and_local_function_reporters_are_rejected(self):
        original = '''    private DataSet CallSelectProcedure(SelectType selectType)
    {
        try { return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType)); }
        catch (Exception ex) { ShowExcetion(ex); return null; }
    }
'''
        replacements = (
            '''    private DataSet CallSelectProcedure(SelectType selectType)
    {
        Action<Exception> @ShowMessageError = value => { };
        try { return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType)); }
        catch (Exception ex) { @ShowMessageError(ex); return null; }
    }
''',
            '''    private DataSet CallSelectProcedure(SelectType selectType)
    {
        void LogError(Exception value) { }
        try { return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType)); }
        catch (Exception ex) { LogError(ex); return null; }
    }
''',
        )
        for index, replacement in enumerate(replacements):
            with self.subTest(index=index), tempfile.TemporaryDirectory() as tmp:
                source, designer = _write_pair(Path(tmp), VALID_SOURCE.replace(original, replacement))
                result = verify_csharp_designer_style(source, designer, applicable_operations=["query"])
            self.assertIn("approved_error_reporter_locally_shadowed", _issues(result))
            self.assertIn("catch_error_reporting_missing", _issues(result))

    def test_radio_group_and_nested_appearance_mutation_are_designer_owned(self):
        injected = '''
    private DevExpress.XtraEditors.RadioGroup radGB = new DevExpress.XtraEditors.RadioGroup();

    private void ConfigureRuntimeAppearance()
    {
        colList_QTY.AppearanceHeader.TextOptions.HAlignment = DevExpress.Utils.HorzAlignment.Center;
    }
'''
        source_text = VALID_SOURCE.replace("    private void DemoForm_Load", injected + "    private void DemoForm_Load")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        codes = _issues(result)
        self.assertIn("control_declaration_in_codebehind", codes)
        self.assertIn("grid_runtime_creation_in_codebehind", codes)
        self.assertIn("static_ui_assignment_in_codebehind", codes)

    def test_interpolation_holes_remain_executable_code_for_all_string_forms(self):
        snippets = (
            '$"{CallViewQuery()}"',
            '$@"{CallViewQuery()}"',
            '$"""{CallViewQuery()}"""',
            '$$"""{{CallViewQuery()}}"""',
        )
        for index, expression in enumerate(snippets):
            with self.subTest(index=index, expression=expression):
                injected = f'''\n    private string ForbiddenInInterpolation{index}()\n    {{\n        return {expression};\n    }}\n'''
                source_text = VALID_SOURCE.replace("    private void DemoForm_Load", injected + "    private void DemoForm_Load")
                with tempfile.TemporaryDirectory() as tmp:
                    source, designer = _write_pair(Path(tmp), source_text)
                    result = verify_csharp_designer_style(source, designer)
                self.assertIn("noncanonical_method_family", _issues(result))

    def test_non_ui_worker_event_may_remain_in_codebehind(self):
        injected = '''
    private WorkerService worker;

    private void WireWorker()
    {
        worker.Completed += WorkerCompleted;
    }

    private void WorkerCompleted(object sender, EventArgs e) { }
'''
        source_text = VALID_SOURCE.replace("    private void DemoForm_Load", injected + "    private void DemoForm_Load")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertNotIn("codebehind_event_subscription", _issues(result))

    def test_nested_fake_object_named_dbclient_cannot_authorize_sp_calls(self):
        source_text = VALID_SOURCE.replace("dbClient.", "fake.dbClient.")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertIn("stored_procedure_invocation_missing", _issues(result))

    def test_designer_component_event_must_not_be_wired_in_codebehind(self):
        designer_text = VALID_DESIGNER.replace(
            "    private DevExpress.XtraEditors.SimpleButton btnSearch;",
            "    private DevExpress.XtraEditors.SimpleButton btnSearch;\n    private System.ComponentModel.BackgroundWorker backgroundWorker1;",
        )
        injected = '''
    private void WireComponent()
    {
        backgroundWorker1.DoWork += BackgroundWorker1_DoWork;
    }

    private void BackgroundWorker1_DoWork(object sender, EventArgs e) { }
'''
        source_text = VALID_SOURCE.replace("    private void DemoForm_Load", injected + "    private void DemoForm_Load")
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text, designer_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertIn("codebehind_event_subscription", _issues(result))

    def test_designer_without_any_expected_event_is_valid(self):
        designer_text = VALID_DESIGNER.replace(
            "        this.Load += new EventHandler(this.DemoForm_Load);\n",
            "",
        )
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), designer=designer_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertNotIn("designer_event_ownership_missing", _issues(result))

    def test_parameter_variable_constructed_before_and_passed_to_exact_call_is_valid(self):
        source_text = VALID_SOURCE.replace(
            'try { return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType)); }',
            '''try
        {
            DbParameter selectParameter = new DbParameter("@SELECT", selectType);
            return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", selectParameter);
        }''',
        )
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer)

        self.assertTrue(result.success, result.metadata["issues"])
        self.assertNotIn("db_parameter_callsite_missing", _issues(result))

    def test_parameter_variable_reassigned_to_null_before_call_is_rejected(self):
        source_text = VALID_SOURCE.replace(
            'try { return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType)); }',
            '''try
        {
            DbParameter selectParameter = new DbParameter("@SELECT", selectType);
            selectParameter = null;
            return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", selectParameter);
        }''',
        )
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer, applicable_operations=["query"])

        self.assertIn("db_parameter_callsite_missing", _issues(result))

    def test_parameter_variable_reassigned_to_another_variable_before_call_is_rejected(self):
        source_text = VALID_SOURCE.replace(
            'try { return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", new DbParameter("@SELECT", selectType)); }',
            '''try
        {
            DbParameter selectParameter = new DbParameter("@SELECT", selectType);
            DbParameter replacementParameter = new DbParameter("@SELECT", selectType);
            selectParameter = replacementParameter;
            return dbClient.GetDataSetFromSP("sp_DEMO_SELECT", selectParameter);
        }''',
        )
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp), source_text)
            result = verify_csharp_designer_style(source, designer, applicable_operations=["query"])

        self.assertIn("db_parameter_callsite_missing", _issues(result))

    def test_applicable_operations_reject_empty_and_unknown_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            source, designer = _write_pair(Path(tmp))
            empty = verify_csharp_designer_style(source, designer, applicable_operations=[])
            bogus = verify_csharp_designer_style(source, designer, applicable_operations=["query", "bogus"])

        self.assertIn("applicable_operations_invalid", _issues(empty))
        self.assertIn("applicable_operations_invalid", _issues(bogus))

    def test_metadata_identifiers_bind_source_designer_and_contract_hashes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source, designer = _write_pair(root)
            first = verify_csharp_designer_style(source, designer)
            ghost = verify_csharp_designer_style(
                source,
                designer,
                expected_identities={"methods": ["GhostMethod"]},
            )
            source_path = Path(source["path"])
            source_path.write_text(source_path.read_text(encoding="utf-8") + "\n", encoding="utf-8", newline="")
            updated_source = {
                "path": str(source_path),
                "sha256": hashlib.sha256(source_path.read_bytes()).hexdigest(),
            }
            second = verify_csharp_designer_style(updated_source, designer)

        self.assertRegex(first.metadata["verification_id"], r"^csharp-style-[0-9a-f]{32}$")
        self.assertRegex(first.metadata["contract_sha256"], r"^sha256:[0-9a-f]{64}$")
        self.assertEqual(first.metadata["contract_sha256"], first.metadata["contract_receipt"]["sha256"])
        required_binding_keys = {
            "source_sha256",
            "designer_sha256",
            "contract_sha256",
            "applicable_operations",
            "expected_identities_digest",
            "target_identities_digest",
            "native_helpers_digest",
            "type_chain_evidence_digest",
            "identity_exceptions_digest",
            "analysis_only",
            "success",
            "status",
            "issues_digest",
        }
        self.assertTrue(required_binding_keys <= set(first.metadata["verification_binding"]))
        self.assertNotEqual(first.metadata["verification_id"], ghost.metadata["verification_id"])
        self.assertNotEqual(
            first.metadata["verification_binding"]["expected_identities_digest"],
            ghost.metadata["verification_binding"]["expected_identities_digest"],
        )
        self.assertNotEqual(first.metadata["verification_id"], second.metadata["verification_id"])

    def test_packaged_contract_is_fixed_and_module_is_ast_valid(self):
        contract = load_packaged_style_contract()
        usage = (REPO_ROOT / "skills" / "csharp_designer_style_harness" / "references" / "usage.md").read_text(encoding="utf-8")
        contract_text = PACKAGED_CONTRACT_PATH.read_text(encoding="utf-8")
        self.assertTrue(contract["authority"]["pb_independent"])
        self.assertEqual(contract["style"]["query_method"], "CallSelectProcedure")
        self.assertEqual(contract["style"]["save_method"], "CallSaveProcedure")
        self.assertEqual(PACKAGED_CONTRACT_PATH, REPO_ROOT / "skills" / "csharp_designer_style_harness" / "references" / "style-contract.json")
        self.assertNotIn("trusted_runtime_roots", usage)
        self.assertNotIn("provenance_authenticator", usage)
        self.assertNotIn("trusted_runtime_roots", contract_text)
        self.assertNotIn("provenance_authenticator", contract_text)
        ast.parse(MODULE_PATH.read_text(encoding="utf-8"))
        json.loads(PACKAGED_CONTRACT_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
