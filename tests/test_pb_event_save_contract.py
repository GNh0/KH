import ast
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import src.skills.pb_event_save_contract as contract
from src.skills.pb_event_save_contract import (
    ISSUE_ARTIFACT_SHA256_MISMATCH,
    ISSUE_ARTIFACT_SOURCE_MISMATCH,
    ISSUE_CSHARP_HANDLER_INVENTED,
    ISSUE_CSHARP_HANDLER_DUPLICATE,
    ISSUE_CSHARP_RULE_MOVED_TO_SAVE_SP,
    ISSUE_CSHARP_SUBSCRIPTION_INVENTED,
    ISSUE_CSHARP_SUBSCRIPTION_DUPLICATE,
    ISSUE_DESIGNER_DISPOSAL_INVALID,
    ISSUE_DESIGNER_LIFECYCLE_INVALID,
    ISSUE_DESIGNER_SERIALIZER_ILLEGAL,
    ISSUE_EVENT_INVENTORY_EMPTY,
    ISSUE_APPROVAL_RECEIPT_INVALID,
    ISSUE_APPROVAL_PROVENANCE_INVALID,
    ISSUE_APPROVAL_PROVENANCE_DUPLICATE,
    ISSUE_RECEIPT_CALL_ID_DUPLICATE,
    ISSUE_RECEIPT_ID_DUPLICATE,
    ISSUE_RECEIPT_ID_INVALID,
    ISSUE_OWNERSHIP_LEDGER_EMPTY,
    ISSUE_PB_EVENT_MAPPING_DUPLICATE,
    ISSUE_PB_EVENT_MAPPING_MISSING,
    ISSUE_SAVE_SP_RULE_DUPLICATED_IN_CSHARP,
    ISSUE_STATIC_UI_IN_CODE_BEHIND,
    validate_pb_event_save_contract,
    sha256_text,
)


DESIGNER = """partial class AnyForm
{
    private System.ComponentModel.IContainer components = null;
    private System.Windows.Forms.Button commandControl;

    protected override void Dispose(bool disposing)
    {
        if (disposing && (components != null)) components.Dispose();
        base.Dispose(disposing);
    }

    private void InitializeComponent()
    {
        this.commandControl = new System.Windows.Forms.Button();
        this.commandControl.Name = "commandControl";
        this.commandControl.Click += this.HandleCommand;
        this.Controls.Add(this.commandControl);
    }
}
"""

CSHARP = """partial class AnyForm
{
    public AnyForm() { InitializeComponent(); }
    private void HandleCommand(object sender, EventArgs e)
    {
        ExecuteSave();
    }
}
"""

SAVE_SP = """CREATE PROCEDURE dbo.SaveAny @VALUE INT AS
BEGIN
    IF EXISTS (SELECT 1 FROM AnyTable WHERE ValueColumn = @VALUE)
    BEGIN
        RAISERROR(N'Duplicate value', 16, 1);
        RETURN;
    END
END
"""


class PbEventSaveContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.paths = {
            "pb": self._write("source.sru", "event clicked;\r\nend event\r\n"),
            "designer": self._write("AnyForm.Designer.cs", DESIGNER),
            "csharp": self._write("AnyForm.cs", CSHARP),
            "save_sp": self._write("SaveAny.sql", SAVE_SP),
        }

    def tearDown(self):
        self.temp.cleanup()

    def _write(self, name, source):
        path = self.root / name
        path.write_text(source, encoding="utf-8", newline="")
        return path

    def _write_bytes(self, name, payload):
        path = self.root / name
        path.write_bytes(payload)
        return path

    def _artifact(self, role, source=None):
        path = self.paths[role]
        text = path.read_text(encoding="utf-8") if source is None else source
        return {"path": str(path), "sha256": self._sha(path), "source": text}

    def _sha(self, path):
        return "sha256:" + sha256(Path(path).read_bytes()).hexdigest()

    def _kwargs(self):
        pb_binding = {"source_path": str(self.paths["pb"]), "source_sha256": self._sha(self.paths["pb"])}
        cs_binding = {"source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"])}
        designer_binding = {"source_path": str(self.paths["designer"]), "source_sha256": self._sha(self.paths["designer"])}
        rule_bindings = {
            "csharp": {"path": str(self.paths["csharp"]), "sha256": cs_binding["source_sha256"]},
            "save_sp": {"path": str(self.paths["save_sp"]), "sha256": self._sha(self.paths["save_sp"])},
        }
        return {
            "pb_event_inventory": [{"event_id": "evt-1", "object": "command", "event": "clicked", "confirmed": True, **pb_binding}],
            "event_mappings": [{"pb_event_id": "evt-1", "handler": "HandleCommand", "subscription_id": "sub-1", "csharp_event": "Click"}],
            "csharp_event_handlers": [{"handler": "HandleCommand", **cs_binding}],
            "csharp_event_subscriptions": [{"subscription_id": "sub-1", "owner": "designer", "event": "Click", "handler": "HandleCommand", **designer_binding}],
            "designer_artifact": self._artifact("designer"),
            "csharp_artifact": self._artifact("csharp"),
            "save_sp_artifact": self._artifact("save_sp"),
            "ownership_ledger": [{
                "rule_id": "duplicate-value",
                "owner": "save_sp",
                "artifacts": rule_bindings,
                "save_sp": {
                    "predicate": "EXISTS (SELECT 1 FROM AnyTable WHERE ValueColumn = @VALUE)",
                    "message": "Duplicate value",
                    "guard": "RETURN",
                },
                "csharp": {
                    "predicate": "HasDuplicate(value)",
                    "message": "Duplicate value",
                    "guard": "return",
                },
            }],
        }

    def _replace(self, role, source):
        self.paths[role].write_text(source, encoding="utf-8", newline="")

    def _replace_bytes(self, role, payload):
        self.paths[role].write_bytes(payload)

    def _approved_handler_evidence(self, kwargs, *, handler="ExtraHandler", call_id="call-7", receipt_id="receipt-7"):
        observed_at = "2026-08-24T12:00:00+09:00"
        output_path = self.root / "approval-output.json"
        scope_sha256 = contract.approval_scope_sha256("handler", handler)
        output = {
            "receipt_id": receipt_id,
            "call_id": call_id,
            "approval_id": "approval-7",
            "decision": "approved",
            "kind": "handler",
            "handler": handler,
            "observed_at": observed_at,
            "target_path": str(self.paths["csharp"]),
            "target_sha256": self._sha(self.paths["csharp"]),
            "scope_sha256": scope_sha256,
        }
        output_path.write_text(json.dumps(output, separators=(",", ":")), encoding="utf-8", newline="")
        approval = {
            "kind": "handler",
            "handler": handler,
            "approved": True,
            "approval_id": "approval-7",
            "call_id": call_id,
            "receipt_id": receipt_id,
            "scope_sha256": scope_sha256,
        }
        receipt = {
            **approval,
            "exit_code": 0,
            "observed_at": observed_at,
            "target_path": str(self.paths["csharp"]),
            "target_sha256": self._sha(self.paths["csharp"]),
            "output_path": str(output_path),
            "output_sha256": self._sha(output_path),
            "approval_artifact_path": str(self.paths["csharp"]),
            "approval_artifact_sha256": self._sha(self.paths["csharp"]),
            "approved_handler_scope_sha256": scope_sha256,
        }
        host_receipt = {
            "producer": "pb-event-save-host",
            "kind": "runtime_invoked_tool_receipt",
            "runtime_invoked": True,
            "receipt_id": "host-receipt-7",
            "tool_call_id": call_id,
            "tool_result_id": "result-7",
            "approval_id": "approval-7",
            "target_kind": "handler",
            "handler": handler,
            "scope_sha256": scope_sha256,
            "approval_artifact_path": str(self.paths["csharp"]),
            "approval_artifact_sha256": self._sha(self.paths["csharp"]),
            "output_path": str(output_path),
            "output_sha256": self._sha(output_path),
            "timestamp": observed_at,
            "exit_status": 0,
        }
        kwargs["approved_csharp_events"] = [approval]
        kwargs["approval_execution_receipts"] = [receipt]
        kwargs["approval_host_runtime_receipt"] = host_receipt
        kwargs["approval_invocation_ledger"] = [{
            "producer": "pb-event-save-host",
            "kind": "runtime_invoked_tool_receipt",
            "runtime_invoked": True,
            "receipt_id": "host-receipt-7",
            "tool_call_id": call_id,
            "tool_result_id": "result-7",
        }]

    def test_valid_exact_contract_passes(self):
        result = validate_pb_event_save_contract(**self._kwargs())
        self.assertTrue(result.success, result.to_dict())
        self.assertEqual(result.metadata["contract_id"], "pb-event-save-contract")

    def test_confirmed_pb_event_must_be_mapped(self):
        kwargs = self._kwargs()
        kwargs["event_mappings"] = []
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_PB_EVENT_MAPPING_MISSING, result.issue_codes)

    def test_confirmed_pb_event_cannot_be_mapped_twice(self):
        kwargs = self._kwargs()
        kwargs["event_mappings"] *= 2
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_PB_EVENT_MAPPING_DUPLICATE, result.issue_codes)

    def test_unmapped_handler_is_invented(self):
        source = CSHARP.replace("}\n", "    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n", 1)
        self._replace("csharp", source)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append({"handler": "ExtraHandler", "source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"])})
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_CSHARP_HANDLER_INVENTED, result.issue_codes)

    def test_explicitly_approved_unmapped_handler_is_allowed(self):
        source = CSHARP.replace("\n}\n", "\n    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n")
        self._replace("csharp", source)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append({"handler": "ExtraHandler", "source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"]), "approved": True, "approval_id": "approval-7"})
        self._approved_handler_evidence(kwargs)
        result = validate_pb_event_save_contract(**kwargs)
        self.assertNotIn(ISSUE_CSHARP_HANDLER_INVENTED, result.issue_codes)

    def test_approved_status_json_without_external_receipt_is_untrusted(self):
        source = CSHARP.replace("\n}\n", "\n    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n")
        self._replace("csharp", source)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append({"handler": "ExtraHandler", "source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"])})
        kwargs["approved_csharp_events"] = [{"kind": "handler", "handler": "ExtraHandler", "approved": True, "approval_id": "approval-7", "call_id": "call-7"}]
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_APPROVAL_RECEIPT_INVALID, result.issue_codes)
        self.assertIn(ISSUE_CSHARP_HANDLER_INVENTED, result.issue_codes)

    def test_self_consistent_caller_receipts_without_host_provenance_are_untrusted(self):
        source = CSHARP.replace("\n}\n", "\n    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n")
        self._replace("csharp", source)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append({"handler": "ExtraHandler", "source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"])})
        self._approved_handler_evidence(kwargs)
        kwargs.pop("approval_host_runtime_receipt")
        kwargs.pop("approval_invocation_ledger")
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_APPROVAL_PROVENANCE_INVALID, result.issue_codes)
        self.assertIn(ISSUE_CSHARP_HANDLER_INVENTED, result.issue_codes)

    def test_host_provenance_tampering_is_rejected_by_exact_bindings(self):
        source = CSHARP.replace("\n}\n", "\n    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n")
        self._replace("csharp", source)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append({"handler": "ExtraHandler", "source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"])})
        self._approved_handler_evidence(kwargs)
        kwargs["approval_host_runtime_receipt"]["approval_artifact_sha256"] = "0" * 64
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_APPROVAL_PROVENANCE_INVALID, result.issue_codes)

        self._approved_handler_evidence(kwargs)
        (self.root / "approval-output.json").write_text("tampered", encoding="utf-8", newline="")
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_APPROVAL_RECEIPT_INVALID, result.issue_codes)
        self.assertIn(ISSUE_APPROVAL_PROVENANCE_INVALID, result.issue_codes)

    def test_host_invocation_ledger_rejects_duplicate_result_ids(self):
        source = CSHARP.replace("\n}\n", "\n    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n")
        self._replace("csharp", source)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append({"handler": "ExtraHandler", "source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"])})
        self._approved_handler_evidence(kwargs)
        kwargs["approval_invocation_ledger"].append({
            **kwargs["approval_invocation_ledger"][0],
            "tool_call_id": "other-call-7",
        })
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_APPROVAL_PROVENANCE_DUPLICATE, result.issue_codes)

    def test_runtime_correlated_fixture_preserves_explicit_user_approval(self):
        source = CSHARP.replace("\n}\n", "\n    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n")
        self._replace("csharp", source)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append({"handler": "ExtraHandler", "source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"])})
        self._approved_handler_evidence(kwargs)
        result = validate_pb_event_save_contract(**kwargs)
        self.assertTrue(result.success, result.to_dict())
        self.assertEqual("passed", result.metadata["approvals"][0]["provenance"]["status"])

    def test_callable_produced_runtime_receipt_can_replace_the_ledger(self):
        source = CSHARP.replace("\n}\n", "\n    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n")
        self._replace("csharp", source)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append({"handler": "ExtraHandler", "source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"])})
        self._approved_handler_evidence(kwargs)
        host_receipt = kwargs.pop("approval_host_runtime_receipt")
        kwargs.pop("approval_invocation_ledger")
        kwargs["approval_runtime_receipt_factory"] = lambda: host_receipt
        result = validate_pb_event_save_contract(**kwargs)
        self.assertTrue(result.success, result.to_dict())

    def test_caller_nested_receipt_is_not_an_external_receipt(self):
        source = CSHARP.replace("\n}\n", "\n    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n")
        self._replace("csharp", source)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append({"handler": "ExtraHandler", "source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"])})
        self._approved_handler_evidence(kwargs)
        approval = kwargs["approved_csharp_events"][0]
        receipt = kwargs.pop("approval_execution_receipts")[0]
        approval["execution_receipt"] = receipt
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_APPROVAL_RECEIPT_INVALID, result.issue_codes)

    def test_receipts_require_unique_ids_and_calls(self):
        source = CSHARP.replace("\n}\n", "\n    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n")
        self._replace("csharp", source)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append({"handler": "ExtraHandler", "source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"])})
        self._approved_handler_evidence(kwargs)
        receipt = kwargs["approval_execution_receipts"][0]
        kwargs["approval_execution_receipts"] = [receipt, {**receipt, "receipt_id": "receipt-8"}]
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_RECEIPT_CALL_ID_DUPLICATE, result.issue_codes)
        self.assertIn(ISSUE_CSHARP_HANDLER_INVENTED, result.issue_codes)

        kwargs["approval_execution_receipts"] = [receipt, {**receipt, "call_id": "call-8"}]
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_RECEIPT_ID_DUPLICATE, result.issue_codes)

    def test_receipt_id_is_required(self):
        source = CSHARP.replace("\n}\n", "\n    private void ExtraHandler(object sender, EventArgs e) { ExecuteSave(); }\n}\n")
        self._replace("csharp", source)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append({"handler": "ExtraHandler", "source_path": str(self.paths["csharp"]), "source_sha256": self._sha(self.paths["csharp"])})
        self._approved_handler_evidence(kwargs)
        kwargs["approved_csharp_events"][0].pop("receipt_id")
        kwargs["approval_execution_receipts"][0].pop("receipt_id")
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_RECEIPT_ID_INVALID, result.issue_codes)

    def test_source_discovered_subscription_is_invented(self):
        designer = DESIGNER.replace("this.Controls.Add", "this.commandControl.MouseEnter += this.HandleCommand;\n        this.Controls.Add")
        self._replace("designer", designer)
        result = validate_pb_event_save_contract(**self._kwargs())
        self.assertIn(ISSUE_CSHARP_SUBSCRIPTION_INVENTED, result.issue_codes)

    def test_duplicate_handlers_and_subscriptions_are_rejected_before_lookup(self):
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"].append(dict(kwargs["csharp_event_handlers"][0]))
        kwargs["csharp_event_subscriptions"].append(dict(kwargs["csharp_event_subscriptions"][0]))
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_CSHARP_HANDLER_DUPLICATE, result.issue_codes)
        self.assertIn(ISSUE_CSHARP_SUBSCRIPTION_DUPLICATE, result.issue_codes)

    def test_subscription_in_comment_or_string_is_not_executable(self):
        csharp = CSHARP.replace("ExecuteSave();", '// this.commandControl.MouseEnter += this.HandleCommand;\n        var decoy = "this.commandControl.MouseLeave += this.HandleCommand;";\n        ExecuteSave();')
        self._replace("csharp", csharp)
        result = validate_pb_event_save_contract(**self._kwargs())
        self.assertNotIn(ISSUE_CSHARP_SUBSCRIPTION_INVENTED, result.issue_codes)

    def test_static_control_construction_in_code_behind_is_rejected(self):
        csharp = CSHARP.replace("ExecuteSave();", "this.commandControl = new System.Windows.Forms.Button();\n        ExecuteSave();")
        self._replace("csharp", csharp)
        result = validate_pb_event_save_contract(**self._kwargs())
        self.assertIn(ISSUE_STATIC_UI_IN_CODE_BEHIND, result.issue_codes)

    def test_static_ui_field_and_disposal_in_code_behind_are_rejected(self):
        csharp = CSHARP.replace("    public AnyForm()", "    private System.Windows.Forms.Button rogueButton;\n    public AnyForm()")
        self._replace("csharp", csharp)
        result = validate_pb_event_save_contract(**self._kwargs())
        self.assertIn(ISSUE_STATIC_UI_IN_CODE_BEHIND, result.issue_codes)

    def test_designer_lifecycle_requires_constructor_initialize_component(self):
        self._replace("csharp", CSHARP.replace("InitializeComponent();", ""))
        result = validate_pb_event_save_contract(**self._kwargs())
        self.assertIn(ISSUE_DESIGNER_LIFECYCLE_INVALID, result.issue_codes)

    def test_designer_disposal_is_required_for_components(self):
        designer = DESIGNER.replace(
            "    protected override void Dispose(bool disposing)\n    {\n        if (disposing && (components != null)) components.Dispose();\n        base.Dispose(disposing);\n    }\n\n",
            "",
        )
        self._replace("designer", designer)
        result = validate_pb_event_save_contract(**self._kwargs())
        self.assertIn(ISSUE_DESIGNER_LIFECYCLE_INVALID, result.issue_codes)
        self.assertIn(ISSUE_DESIGNER_DISPOSAL_INVALID, result.issue_codes)

    def test_designer_serializer_operations_must_be_contained_in_initialize_component(self):
        self._replace("designer", DESIGNER + "\n    commandControl.Controls.Add(commandControl);\n")
        result = validate_pb_event_save_contract(**self._kwargs())
        self.assertIn(ISSUE_DESIGNER_SERIALIZER_ILLEGAL, result.issue_codes)

    def test_designer_factory_layout_is_not_serializer_legal(self):
        designer = DESIGNER.replace("new System.Windows.Forms.Button()", "BuildButton()")
        self._replace("designer", designer)
        result = validate_pb_event_save_contract(**self._kwargs())
        self.assertIn(ISSUE_DESIGNER_SERIALIZER_ILLEGAL, result.issue_codes)

    def test_save_sp_owned_predicate_cannot_be_duplicated_in_csharp(self):
        csharp = CSHARP.replace("ExecuteSave();", "if (HasDuplicate(value)) return;\n        ExecuteSave();")
        self._replace("csharp", csharp)
        result = validate_pb_event_save_contract(**self._kwargs())
        self.assertIn(ISSUE_SAVE_SP_RULE_DUPLICATED_IN_CSHARP, result.issue_codes)

    def test_save_sp_message_call_is_duplication(self):
        csharp = CSHARP.replace("ExecuteSave();", 'ShowError("Duplicate value");\n        ExecuteSave();')
        self._replace("csharp", csharp)
        result = validate_pb_event_save_contract(**self._kwargs())
        matching = [issue for issue in result.integration_issues if issue["code"] == ISSUE_SAVE_SP_RULE_DUPLICATED_IN_CSHARP]
        self.assertTrue(any(issue["signature_kind"] == "message" for issue in matching))

    def test_message_in_comment_or_plain_string_is_not_duplication(self):
        csharp = CSHARP.replace("ExecuteSave();", '// ShowError("Duplicate value");\n        const string diagnostic = "Duplicate value";\n        ExecuteSave();')
        self._replace("csharp", csharp)
        result = validate_pb_event_save_contract(**self._kwargs())
        matching = [issue for issue in result.integration_issues if issue["code"] == ISSUE_SAVE_SP_RULE_DUPLICATED_IN_CSHARP]
        self.assertFalse(any(issue["signature_kind"] == "message" for issue in matching))

    def test_predicate_in_comment_or_string_is_not_duplication(self):
        csharp = CSHARP.replace("ExecuteSave();", '// HasDuplicate(value)\n        var diagnostic = "HasDuplicate(value)";\n        ExecuteSave();')
        self._replace("csharp", csharp)
        result = validate_pb_event_save_contract(**self._kwargs())
        matching = [issue for issue in result.integration_issues if issue["code"] == ISSUE_SAVE_SP_RULE_DUPLICATED_IN_CSHARP]
        self.assertFalse(any(issue["signature_kind"] == "predicate" for issue in matching))

    def test_csharp_owned_validation_cannot_be_moved_to_sp(self):
        csharp = CSHARP.replace("ExecuteSave();", "if (IsInvalid(value)) return;\n        ExecuteSave();")
        save_sp = SAVE_SP.replace("END\n", "    IF IsInvalid(@VALUE) = 1 RETURN;\nEND\n", 1)
        self._replace("csharp", csharp)
        self._replace("save_sp", save_sp)
        kwargs = self._kwargs()
        rule = kwargs["ownership_ledger"][0]
        rule["owner"] = "csharp"
        rule["csharp"] = {"predicate": "IsInvalid(value)", "guard": "return"}
        rule["save_sp"] = {"predicate": "IsInvalid(@VALUE)", "guard": "RETURN"}
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_CSHARP_RULE_MOVED_TO_SAVE_SP, result.issue_codes)

    def test_csharp_owned_validation_remains_in_csharp(self):
        csharp = CSHARP.replace("ExecuteSave();", "if (IsInvalid(value)) return;\n        ExecuteSave();")
        self._replace("csharp", csharp)
        kwargs = self._kwargs()
        rule = kwargs["ownership_ledger"][0]
        rule["owner"] = "csharp"
        rule["csharp"] = {"predicate": "IsInvalid(value)", "guard": "return"}
        rule["save_sp"] = {"predicate": "IsInvalid(@VALUE)"}
        result = validate_pb_event_save_contract(**kwargs)
        self.assertTrue(result.success, result.to_dict())

    def test_sha_mismatch_fails_closed(self):
        kwargs = self._kwargs()
        kwargs["designer_artifact"]["sha256"] = "0" * 64
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_ARTIFACT_SHA256_MISMATCH, result.issue_codes)

    def test_supplied_source_must_match_artifact(self):
        kwargs = self._kwargs()
        kwargs["csharp_artifact"]["source"] += "// drift"
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_ARTIFACT_SOURCE_MISMATCH, result.issue_codes)

    def test_crlf_artifact_hash_and_source_are_byte_exact(self):
        payload = DESIGNER.replace("\n", "\r\n").encode("utf-8")
        self._replace_bytes("designer", payload)
        kwargs = self._kwargs()
        kwargs["designer_artifact"] = {
            "path": str(self.paths["designer"]),
            "sha256": self._sha(self.paths["designer"]),
            "source": payload.decode("utf-8"),
        }
        result = validate_pb_event_save_contract(**kwargs)
        self.assertTrue(result.success, result.to_dict())

        kwargs["designer_artifact"]["source"] = payload.decode("utf-8").replace("\r\n", "\n")
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_ARTIFACT_SOURCE_MISMATCH, result.issue_codes)

    def test_artifact_reads_are_bounded(self):
        self._replace_bytes("designer", b"x" * 33)
        with patch.object(contract, "MAX_ARTIFACT_BYTES", 32):
            result = validate_pb_event_save_contract(**self._kwargs())
        self.assertIn("pb_event_save_artifact_unreadable", result.issue_codes)

    def test_claimed_event_and_ownership_inventories_cannot_be_empty(self):
        kwargs = self._kwargs()
        kwargs["pb_event_inventory"] = []
        kwargs["ownership_ledger"] = []
        result = validate_pb_event_save_contract(**kwargs)
        self.assertIn(ISSUE_EVENT_INVENTORY_EMPTY, result.issue_codes)
        self.assertIn(ISSUE_OWNERSHIP_LEDGER_EMPTY, result.issue_codes)

    def test_private_names_do_not_control_policy(self):
        designer = DESIGNER.replace("AnyForm", "Z9").replace("commandControl", "x7").replace("HandleCommand", "m8")
        csharp = CSHARP.replace("AnyForm", "Z9").replace("HandleCommand", "m8")
        self._replace("designer", designer)
        self._replace("csharp", csharp)
        kwargs = self._kwargs()
        kwargs["csharp_event_handlers"][0]["handler"] = "m8"
        kwargs["csharp_event_subscriptions"][0]["handler"] = "m8"
        kwargs["event_mappings"][0]["handler"] = "m8"
        result = validate_pb_event_save_contract(**kwargs)
        self.assertTrue(result.success, result.to_dict())

    def test_issue_codes_and_receipt_metadata_are_stable(self):
        kwargs = self._kwargs()
        kwargs["event_mappings"] = []
        first = validate_pb_event_save_contract(**kwargs)
        second = validate_pb_event_save_contract(**kwargs)
        self.assertEqual(first.issue_codes, second.issue_codes)
        self.assertEqual(first.metadata["receipt_sha256"], second.metadata["receipt_sha256"])

    def test_both_assigned_python_files_parse_as_ast(self):
        module = Path(__file__).parents[1] / "src" / "skills" / "pb_event_save_contract.py"
        ast.parse(module.read_text(encoding="utf-8"))
        ast.parse(Path(__file__).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
