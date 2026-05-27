import json
import os
import sys

from src.contracts import AdapterRequest, AdapterResult
from src.tasks.workflows import dispatch_project_workflow


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
        )
        return self.execute_request(request).to_legacy_messages()

    def execute_request(self, request: AdapterRequest) -> AdapterResult:
        print(f"[LocalDispatcher] Starting local workflow for {len(request.files)} files.")
        workflow_id = dispatch_project_workflow(
            request.project_dir,
            request.files,
            request.design_doc,
            request.platform_mode,
        )
        return AdapterResult(
            status="success",
            message="workflow submitted for background processing",
            workflow_id=workflow_id,
            metadata={"file_count": len(request.files), "platform_mode": request.platform_mode},
        )


CeleryDispatcher = LocalDispatcher


class AntigravityDispatcher:
    def execute(self, project_dir: str, files: list, design_doc: str, platform_mode: str):
        request = AdapterRequest(
            project_dir=project_dir,
            files=files,
            design_doc=design_doc,
            platform_mode=platform_mode,
        )
        return self.execute_request(request).to_legacy_messages()

    def execute_request(self, request: AdapterRequest) -> AdapterResult:
        project_id = os.path.basename(request.project_dir)
        print(f"\n[NATIVE_DISPATCH_REQUIRED] Spawn Subagents for: {json.dumps(request.files)}")
        print(">>> WAITING_FOR_WEBHOOK_IPC <<<")
        print("Parent agent should POST subagent results to:")
        print("POST http://localhost:8000/api/webhook/subagent-result")
        print(f"Payload format: {{'project_id': '{project_id}', 'task_id': '...', 'base64_data': '...'}}")
        sys.stdout.flush()

        return AdapterResult(
            status="pending",
            message="FastAPI webhook response pending",
            workflow_id=project_id,
            metadata={"file_count": len(request.files), "platform_mode": request.platform_mode},
        )
