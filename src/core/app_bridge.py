from typing import Any, Dict, List, Optional

from src.contracts import AdapterRequest
from src.orchestration.roles import build_default_role_metadata
from src.platforms.dispatcher_factory import DispatcherFactory


def create_app_request(
    project_dir: str,
    files: List[str],
    design_doc: str,
    platform_mode: str = "antigravity",
    app_host: str = "codex",
    thread_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> AdapterRequest:
    role_metadata = build_default_role_metadata()
    role_metadata.update(metadata or {})
    role_metadata["app_context"] = {
        "host": app_host,
        "thread_id": thread_id,
        "entrypoint": "app_bridge",
        "workflow_usability_auto": True,
    }
    role_metadata.setdefault("workflow_usability_auto", True)
    role_metadata.setdefault("token_optimizer_provider", "kh")
    role_metadata.setdefault("token_optimizer_status", "considered_not_needed")
    role_metadata.setdefault("workspace_strategy", "host-worktree")

    return AdapterRequest(
        project_dir=project_dir,
        files=list(files),
        design_doc=design_doc,
        platform_mode=platform_mode,
        metadata=role_metadata,
    )


def dispatch_app_request(request: AdapterRequest) -> Dict[str, Any]:
    dispatcher = DispatcherFactory.get_dispatcher(request.platform_mode)
    return dispatcher.execute_request(request).to_dict()
