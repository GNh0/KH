from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class GoalState:
    objective: str
    status: str = "active"
    success_criteria: List[str] = field(default_factory=list)
    evidence_required: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    progress_notes: List[str] = field(default_factory=list)
    blocked_reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "status": self.status,
            "success_criteria": list(self.success_criteria),
            "evidence_required": list(self.evidence_required),
            "evidence": list(self.evidence),
            "progress_notes": list(self.progress_notes),
            "blocked_reason": self.blocked_reason,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GoalState":
        return cls(
            objective=data.get("objective", ""),
            status=data.get("status", "active"),
            success_criteria=list(data.get("success_criteria", [])),
            evidence_required=list(data.get("evidence_required", [])),
            evidence=list(data.get("evidence", [])),
            progress_notes=list(data.get("progress_notes", [])),
            blocked_reason=data.get("blocked_reason", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class MemoryScope:
    kind: str
    namespace: str
    project_id: str = ""
    thread_id: Optional[str] = None
    root_path: str = ""
    status: str = "active"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "namespace": self.namespace,
            "project_id": self.project_id,
            "thread_id": self.thread_id,
            "root_path": self.root_path,
            "status": self.status,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryScope":
        return cls(
            kind=data.get("kind", ""),
            namespace=data.get("namespace", ""),
            project_id=data.get("project_id", ""),
            thread_id=data.get("thread_id"),
            root_path=data.get("root_path", ""),
            status=data.get("status", "active"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class MemoryRecord:
    record_id: str
    kind: str
    content: str
    scope: str
    source: str = ""
    confidence: str = "medium"
    created_at: str = ""
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "record_id": self.record_id,
            "kind": self.kind,
            "content": self.content,
            "scope": self.scope,
            "source": self.source,
            "confidence": self.confidence,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryRecord":
        return cls(
            record_id=data.get("record_id", ""),
            kind=data.get("kind", ""),
            content=data.get("content", ""),
            scope=data.get("scope", ""),
            source=data.get("source", ""),
            confidence=data.get("confidence", "medium"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class MemoryEvent:
    event_type: str
    record_id: str = ""
    scope: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "record_id": self.record_id,
            "scope": self.scope,
            "payload": dict(self.payload),
            "timestamp": self.timestamp,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MemoryEvent":
        return cls(
            event_type=data.get("event_type", ""),
            record_id=data.get("record_id", ""),
            scope=data.get("scope", ""),
            payload=dict(data.get("payload", {})),
            timestamp=data.get("timestamp", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class HarnessResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    execution_time: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time": self.execution_time,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HarnessResult":
        return cls(
            success=bool(data.get("success", False)),
            stdout=data.get("stdout", ""),
            stderr=data.get("stderr", ""),
            exit_code=int(data.get("exit_code", 0)),
            execution_time=float(data.get("execution_time", 0.0)),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class SkillManifest:
    name: str
    description: str
    version: str = ""
    entrypoint: str = ""
    capabilities: List[str] = field(default_factory=list)
    environment: Dict[str, str] = field(default_factory=dict)
    requires: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "entrypoint": self.entrypoint,
            "capabilities": list(self.capabilities),
            "environment": dict(self.environment),
            "requires": list(self.requires),
        }

    @classmethod
    def from_plugin_json(cls, data: Dict[str, Any]) -> "SkillManifest":
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", ""),
            entrypoint=data.get("entrypoint", ""),
            capabilities=[skill.get("name", "") for skill in data.get("skills", []) if skill.get("name")],
            environment=dict(data.get("environment", {})),
            requires=list(data.get("requires", [])),
        )


@dataclass(frozen=True)
class AdapterRequest:
    project_dir: str
    files: List[str]
    design_doc: str
    platform_mode: str = "local"
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_dir": self.project_dir,
            "files": list(self.files),
            "design_doc": self.design_doc,
            "platform_mode": self.platform_mode,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdapterRequest":
        return cls(
            project_dir=data.get("project_dir", ""),
            files=list(data.get("files", [])),
            design_doc=data.get("design_doc", ""),
            platform_mode=data.get("platform_mode", "local"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class AdapterResult:
    status: str
    message: str
    workflow_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status,
            "message": self.message,
            "workflow_id": self.workflow_id,
            "metadata": dict(self.metadata),
        }

    def to_legacy_messages(self) -> List[str]:
        label = self.status[:1].upper() + self.status[1:]
        suffix = f" (ID: {self.workflow_id})" if self.workflow_id else ""
        return [f"[{label}] {self.message}{suffix}"]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AdapterResult":
        return cls(
            status=data.get("status", ""),
            message=data.get("message", ""),
            workflow_id=data.get("workflow_id"),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class WorkflowTaskResult:
    task_id: str
    file_name: str
    role: str
    status: str
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "file_name": self.file_name,
            "role": self.role,
            "status": self.status,
            "message": self.message,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowTaskResult":
        return cls(
            task_id=data.get("task_id", ""),
            file_name=data.get("file_name", ""),
            role=data.get("role", ""),
            status=data.get("status", ""),
            message=data.get("message", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class WorkflowDispatchResult:
    workflow_id: str
    success: bool
    task_results: List[WorkflowTaskResult] = field(default_factory=list)
    gate_results: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "success": self.success,
            "task_results": [result.to_dict() for result in self.task_results],
            "gate_results": [dict(result) for result in self.gate_results],
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkflowDispatchResult":
        return cls(
            workflow_id=data.get("workflow_id", ""),
            success=bool(data.get("success", False)),
            task_results=[
                WorkflowTaskResult.from_dict(result)
                for result in data.get("task_results", [])
            ],
            gate_results=[dict(result) for result in data.get("gate_results", [])],
            metadata=dict(data.get("metadata", {})),
        )
