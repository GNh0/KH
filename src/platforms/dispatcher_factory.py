import json
import os
import sys

from src.contracts import AdapterRequest, AdapterResult
from src.orchestration.evidence_producers import collect_metadata_evidence
from src.orchestration.extension_registry import ExtensionRegistry
from src.orchestration.goal_evidence import (
    collect_workflow_goal_evidence,
    evaluate_goal_evidence,
)
from src.orchestration.roles import build_default_role_metadata
from src.orchestration.roles import build_role_gate_results
from src.platforms.antigravity_native import AntigravityNativeSidecarAdapter
from src.tasks.workflows import dispatch_project_workflow


def ensure_role_metadata(metadata: dict) -> dict:
    if metadata and metadata.get("orchestration_roles") and metadata.get("role_graph"):
        return metadata

    role_metadata = build_default_role_metadata()
    role_metadata.update(metadata or {})
    return role_metadata


class DispatcherFactory:
    _registry = None

    @classmethod
    def registry(cls) -> ExtensionRegistry:
        if cls._registry is None:
            registry = ExtensionRegistry()
            registry.register("dispatcher", "local", lambda: LocalDispatcher())
            registry.register("dispatcher", "antigravity", lambda: AntigravityDispatcher())
            cls._registry = registry
        return cls._registry

    @classmethod
    def register_dispatcher(cls, platform_mode: str, factory, overwrite: bool = False) -> None:
        cls.registry().register("dispatcher", platform_mode, factory, overwrite=overwrite)

    @classmethod
    def reset_registry_for_tests(cls) -> None:
        cls._registry = None

    @classmethod
    def get_dispatcher(cls, platform_mode: str):
        return cls.registry().create("dispatcher", platform_mode or "local")


class LocalDispatcher:
    def execute(self, project_dir: str, files: list, design_doc: str, platform_mode: str):
        request = AdapterRequest(
            project_dir=project_dir,
            files=files,
            design_doc=design_doc,
            platform_mode=platform_mode,
            metadata=build_default_role_metadata(),
        )
        return self.execute_request(request).to_legacy_messages()

    def execute_request(self, request: AdapterRequest) -> AdapterResult:
        metadata = ensure_role_metadata(request.metadata)
        print(f"[LocalDispatcher] Starting local workflow for {len(request.files)} files.")
        workflow_result = dispatch_project_workflow(
            request.project_dir,
            request.files,
            request.design_doc,
            request.platform_mode,
            metadata,
        )
        status = "success" if workflow_result.success else "failed"
        message = (
            "workflow completed"
            if workflow_result.success
            else "workflow completed with failures"
        )
        evaluated_goal = workflow_result.metadata.get("goal", metadata.get("goal", {}))
        goal_ledger = workflow_result.metadata.get("goal_ledger", {})
        return AdapterResult(
            status=status,
            message=message,
            workflow_id=workflow_result.workflow_id,
            metadata={
                "file_count": len(request.files),
                "platform_mode": request.platform_mode,
                "orchestration_roles": metadata.get("orchestration_roles", []),
                "role_graph": metadata.get("role_graph", {}),
                "goal": evaluated_goal,
                "goal_ledger": goal_ledger,
                "workflow": workflow_result.to_dict(),
                "task_results": [
                    result.to_dict()
                    for result in workflow_result.task_results
                ],
                "gate_results": workflow_result.gate_results,
            },
        )


CeleryDispatcher = LocalDispatcher


class AntigravityDispatcher:
    def __init__(self, native_adapter=None):
        self.native_adapter = native_adapter

    def execute(self, project_dir: str, files: list, design_doc: str, platform_mode: str):
        request = AdapterRequest(
            project_dir=project_dir,
            files=files,
            design_doc=design_doc,
            platform_mode=platform_mode,
            metadata=build_default_role_metadata(),
        )
        return self.execute_request(request).to_legacy_messages()

    def execute_request(self, request: AdapterRequest) -> AdapterResult:
        metadata = ensure_role_metadata(request.metadata)
        project_id = os.path.basename(request.project_dir)
        native_adapter = self.native_adapter or _antigravity_sidecar_adapter(metadata)
        if native_adapter:
            return self._execute_native(request, metadata, project_id, native_adapter)

        print(f"\n[NATIVE_DISPATCH_REQUIRED] Spawn Subagents for: {json.dumps(request.files)}")
        print(">>> WAITING_FOR_NATIVE_HOST_RESULT <<<")
        print("No Antigravity native adapter is configured.")
        print("Optional external callback bridge: POST /api/webhook/subagent-result")
        print(f"Role graph: {json.dumps(metadata.get('orchestration_roles', []))}")
        sys.stdout.flush()

        return AdapterResult(
            status="pending",
            message="Antigravity native dispatch pending",
            workflow_id=project_id,
            metadata={
                "file_count": len(request.files),
                "platform_mode": request.platform_mode,
                "orchestration_roles": metadata.get("orchestration_roles", []),
                "role_graph": metadata.get("role_graph", {}),
                "goal": metadata.get("goal", {}),
                "native_dispatch": {
                    "status": "pending",
                    "adapter": "",
                    "fallback": "no native adapter configured",
                },
            },
        )

    def _execute_native(self, request: AdapterRequest, metadata: dict, project_id: str, native_adapter=None) -> AdapterResult:
        adapter = native_adapter or self.native_adapter
        adapter_name = getattr(adapter, "name", adapter.__class__.__name__)
        native_result = adapter.dispatch(request)
        task_results = list(native_result.task_results)
        task_success = bool(task_results) and all(
            result.status == "success"
            for result in task_results
        )
        if not request.files:
            task_success = native_result.status == "success"

        workflow_evidence = collect_workflow_goal_evidence(
            design_doc=request.design_doc,
            file_list=request.files,
            workflow_completed=native_result.status == "success",
        )
        workflow_evidence.extend(_task_result_evidence(task_results))
        evaluated_goal = evaluate_goal_evidence(
            metadata.get("goal", {}),
            workflow_evidence=workflow_evidence,
            workflow_success=task_success and native_result.status == "success",
        )
        gate_results = build_role_gate_results(
            [result.to_dict() for result in task_results],
            goal=evaluated_goal,
        )
        status = _adapter_status(native_result.status, task_success, evaluated_goal)
        return AdapterResult(
            status=status,
            message=native_result.message or "Antigravity native dispatch completed",
            workflow_id=project_id,
            metadata={
                "file_count": len(request.files),
                "platform_mode": request.platform_mode,
                "orchestration_roles": metadata.get("orchestration_roles", []),
                "role_graph": metadata.get("role_graph", {}),
                "goal": evaluated_goal or metadata.get("goal", {}),
                "task_results": [result.to_dict() for result in task_results],
                "gate_results": gate_results,
                "native_dispatch": {
                    "status": native_result.status,
                    "adapter": adapter_name,
                    "metadata": dict(native_result.metadata),
                },
            },
        )


def _task_result_evidence(task_results: list) -> list:
    evidence = []
    for result in task_results:
        for item in collect_metadata_evidence(result.metadata):
            if item and item not in evidence:
                evidence.append(item)
    return evidence


def _antigravity_sidecar_adapter(metadata: dict):
    sidecar = metadata.get("antigravity_native_sidecar", {}) or {}
    command = sidecar.get("command", [])
    if not command:
        return None

    kwargs = {
        "command": list(command),
        "cwd": sidecar.get("cwd"),
        "env": dict(sidecar.get("env", {}) or {}),
    }
    if sidecar.get("timeout_seconds") is not None:
        kwargs["timeout_seconds"] = float(sidecar.get("timeout_seconds"))
    return AntigravityNativeSidecarAdapter(**kwargs)


def _adapter_status(native_status: str, task_success: bool, goal: dict) -> str:
    if native_status == "blocked":
        return "blocked"
    if native_status != "success":
        return "failed"
    if goal and goal.get("status") == "blocked":
        return "blocked"
    return "success" if task_success else "failed"
