import json
import os
import sys

from src.contracts import AdapterRequest, AdapterResult
from src.orchestration.roles import build_default_role_metadata
from src.tasks.workflows import dispatch_project_workflow


def ensure_role_metadata(metadata: dict) -> dict:
    if metadata and metadata.get("orchestration_roles") and metadata.get("role_graph"):
        return metadata

    role_metadata = build_default_role_metadata()
    role_metadata.update(metadata or {})
    return role_metadata


class DispatcherFactory:
    @staticmethod
    def get_dispatcher(platform_mode: str):
        if platform_mode.lower() == "antigravity":
            return AntigravityDispatcher()
        return LocalDispatcher()


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
        workflow_id = dispatch_project_workflow(
            request.project_dir,
            request.files,
            request.design_doc,
            request.platform_mode,
            metadata,
        )
        return AdapterResult(
            status="success",
            message="workflow submitted for background processing",
            workflow_id=workflow_id,
            metadata={
                "file_count": len(request.files),
                "platform_mode": request.platform_mode,
                "orchestration_roles": metadata.get("orchestration_roles", []),
                "role_graph": metadata.get("role_graph", {}),
            },
        )


CeleryDispatcher = LocalDispatcher


class AntigravityDispatcher:
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
        print(f"\n[NATIVE_DISPATCH_REQUIRED] Spawn Subagents for: {json.dumps(request.files)}")
        print(">>> WAITING_FOR_WEBHOOK_IPC <<<")
        print("Parent agent should POST subagent results to:")
        print("POST http://localhost:8000/api/webhook/subagent-result")
        print(f"Payload format: {{'project_id': '{project_id}', 'task_id': '...', 'base64_data': '...'}}")
        print(f"Role graph: {json.dumps(metadata.get('orchestration_roles', []))}")
        sys.stdout.flush()

        return AdapterResult(
            status="pending",
            message="FastAPI webhook response pending",
            workflow_id=project_id,
            metadata={
                "file_count": len(request.files),
                "platform_mode": request.platform_mode,
                "orchestration_roles": metadata.get("orchestration_roles", []),
                "role_graph": metadata.get("role_graph", {}),
            },
        )
