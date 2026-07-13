import sys
import unittest

from src.contracts import (
    AdapterRequest,
    AdapterResult,
    ArtifactManifest,
    DesignArtifact,
    DomainProfile,
    DomainRole,
    GoalState,
    HandoffSnapshot,
    HarnessResult,
    SkillManifest,
    WorkDesign,
    WorkflowDispatchResult,
    WorkflowTaskResult,
)
from src.platforms.antigravity_native import (
    AntigravityNativeDispatchResult,
    AntigravityNativeSidecarAdapter,
)


class HarnessResultContractTests(unittest.TestCase):
    def test_harness_result_round_trips_as_dict(self):
        result = HarnessResult(
            success=False,
            stdout="out",
            stderr="boom",
            exit_code=1,
            execution_time=0.25,
            metadata={"adapter": "codex"},
        )

        restored = HarnessResult.from_dict(result.to_dict())

        self.assertEqual(restored, result)


class SkillManifestContractTests(unittest.TestCase):
    def test_skill_manifest_loads_plugin_shape(self):
        manifest = SkillManifest.from_plugin_json({
            "name": "universal-agent-framework",
            "version": "2.5.0",
            "description": "Universal skill harness",
            "entrypoint": "cli.py",
            "requires": ["fastapi", "requests"],
            "skills": [{"name": "sandbox"}],
        })

        self.assertEqual(manifest.name, "universal-agent-framework")
        self.assertEqual(manifest.version, "2.5.0")
        self.assertEqual(manifest.entrypoint, "cli.py")
        self.assertEqual(manifest.requires, ["fastapi", "requests"])
        self.assertEqual(manifest.capabilities, ["sandbox"])


class GoalStateContractTests(unittest.TestCase):
    def test_goal_state_round_trips_as_dict(self):
        goal = GoalState(
            objective="build api",
            success_criteria=["design approved"],
            evidence_required=["tests"],
            evidence=["tests passed"],
            progress_notes=["dispatch started"],
            metadata={"source": "agent_loop"},
        )

        restored = GoalState.from_dict(goal.to_dict())

        self.assertEqual(restored, goal)

    def test_goal_state_can_mark_blocked_from_dict(self):
        goal = GoalState.from_dict({
            "objective": "build api",
            "status": "blocked",
            "blocked_reason": "missing credentials",
        })

        self.assertEqual(goal.status, "blocked")
        self.assertEqual(goal.blocked_reason, "missing credentials")
        self.assertEqual(goal.success_criteria, [])


class HandoffSnapshotContractTests(unittest.TestCase):
    def test_handoff_snapshot_round_trips_as_dict(self):
        snapshot = HandoffSnapshot(
            project_dir="C:/work/demo",
            workflow_id="workflow_demo",
            objective="continue the workflow",
            status="blocked",
            next_recommended_action="collect missing evidence: review passed",
            success_criteria=["review evidence is available"],
            evidence_required=["design_doc", "review passed"],
            evidence=["design_doc"],
            missing_evidence=["review passed"],
            artifact_manifest={"workflow_id": "workflow_demo"},
            memory_context={"record_count": 1},
            goal={"objective": "continue the workflow"},
            metadata={"source": "resume_handoff"},
        )

        self.assertEqual(HandoffSnapshot.from_dict(snapshot.to_dict()), snapshot)


class DomainDesignContractTests(unittest.TestCase):
    def test_domain_profile_round_trips_as_dict(self):
        profile = DomainProfile(
            domain_name="generic",
            objective="Plan a new topic",
            subdomains=["requirements", "risk"],
            roles=[
                DomainRole(
                    name="domain-designer",
                    purpose="Create the mandatory design.",
                    responsibilities=["define artifacts"],
                    stage="design",
                    required_artifacts=["work-design"],
                    produces=["work_design"],
                )
            ],
            required_design_artifact_types=["work-design", "risk-policy-checklist"],
            evidence_required=["work design saved"],
            review_gates=["design review"],
            risk_policy_gates=["risk policy checked"],
        )

        self.assertEqual(DomainProfile.from_dict(profile.to_dict()), profile)

    def test_work_design_round_trips_as_dict(self):
        design = WorkDesign(
            objective="Create an operations plan",
            domain="operations",
            scope="single team",
            assumptions=["source data will be provided"],
            constraints=["no private credentials"],
            subdomains=["process", "metrics"],
            roles_required=["domain-designer", "qa-qc-verifier"],
            deliverables=["process map"],
            evidence_required=["work design saved"],
            risk_policy_checks=["privacy review"],
            review_gates=["design review"],
            design_artifacts=["work-design", "risk-policy-checklist"],
        )

        self.assertEqual(WorkDesign.from_dict(design.to_dict()), design)

    def test_artifact_manifest_round_trips_as_dict(self):
        artifact = DesignArtifact(
            artifact_id="work_design",
            kind="work-design",
            title="Work Design",
            path=".uaf/artifacts/design/work_design.md",
            owner_role="domain-designer",
            domain="generic",
            required_for=["dispatch", "review"],
            status="created",
            checksum="abc123",
        )
        manifest = ArtifactManifest(
            workflow_id="workflow_demo",
            design_artifacts=[artifact],
            evidence=["work design saved"],
        )

        self.assertEqual(ArtifactManifest.from_dict(manifest.to_dict()), manifest)


class AdapterContractTests(unittest.TestCase):
    def test_adapter_request_and_result_are_serializable(self):
        request = AdapterRequest(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="codex",
            metadata={"thread": "local"},
        )
        result = AdapterResult(
            status="accepted",
            message="queued",
            workflow_id="workflow_demo",
            metadata={"tasks": 1},
        )

        self.assertEqual(AdapterRequest.from_dict(request.to_dict()), request)
        self.assertEqual(AdapterResult.from_dict(result.to_dict()), result)
        self.assertEqual(result.to_legacy_messages(), ["[Accepted] queued (ID: workflow_demo)"])
        self.assertFalse(result.is_terminal)
        self.assertEqual(result.execution_state, "claimed_unverified")

    def test_adapter_result_pending_is_an_explicit_nonterminal_outcome(self):
        result = AdapterResult(
            status="pending",
            message="host execution is still running",
            workflow_id="workflow_demo",
            metadata={"resume": True},
        )

        self.assertEqual(AdapterResult.from_dict(result.to_dict()), result)
        self.assertFalse(result.is_terminal)
        self.assertEqual(result.execution_state, "claimed_unverified")


class WorkflowDispatchContractTests(unittest.TestCase):
    def test_workflow_dispatch_result_round_trips_as_dict(self):
        task = WorkflowTaskResult(
            task_id="main_py",
            file_name="main.py",
            role="implementer",
            status="failed",
            message="webhook failed",
            metadata={"error_type": "ConnectError"},
        )
        workflow = WorkflowDispatchResult(
            workflow_id="workflow_demo",
            success=False,
            task_results=[task],
            gate_results=[{"role": "spec-reviewer", "status": "failed"}],
            metadata={"platform_mode": "local"},
        )

        self.assertEqual(WorkflowDispatchResult.from_dict(workflow.to_dict()), workflow)


class AntigravityNativeDispatchContractTests(unittest.TestCase):
    def test_native_dispatch_result_round_trips_as_dict(self):
        task = WorkflowTaskResult(
            task_id="main_py",
            file_name="main.py",
            role="implementer",
            status="success",
            message="generated",
            metadata={"evidence": ["native dispatch completed"]},
        )
        result = AntigravityNativeDispatchResult(
            status="success",
            message="done",
            task_results=[task],
            metadata={"host": "antigravity"},
        )

        self.assertEqual(
            AntigravityNativeDispatchResult.from_dict(result.to_dict()),
            result,
        )

    def test_native_sidecar_adapter_converts_json_stdout_to_dispatch_result(self):
        script = (
            "import json, sys; "
            "request=json.load(sys.stdin); "
            "print(json.dumps({"
            "'status':'success',"
            "'message':'native sidecar completed',"
            "'task_results':[{'task_id':'main_py','file_name':request['files'][0],'role':'implementer','status':'success','message':'generated','metadata':{'evidence':['native dispatch completed']}}],"
            "'metadata':{'host':'fake-antigravity'}"
            "}))"
        )
        adapter = AntigravityNativeSidecarAdapter(command=[sys.executable, "-c", script])
        request = AdapterRequest(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="antigravity",
        )

        result = adapter.dispatch(request)

        self.assertEqual(result.status, "success")
        self.assertEqual(result.message, "native sidecar completed")
        self.assertEqual(result.task_results[0].file_name, "main.py")
        self.assertEqual(result.metadata["host"], "fake-antigravity")
        self.assertEqual(result.metadata["sidecar_exit_code"], 0)

    def test_native_sidecar_adapter_reports_invalid_json_as_failed_result(self):
        adapter = AntigravityNativeSidecarAdapter(
            command=[sys.executable, "-c", "print('not-json')"]
        )
        request = AdapterRequest(
            project_dir="C:/work/demo",
            files=["main.py"],
            design_doc="# design",
            platform_mode="antigravity",
        )

        result = adapter.dispatch(request)

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.task_results, [])
        self.assertEqual(result.metadata["error_type"], "JSONDecodeError")


if __name__ == "__main__":
    unittest.main()
