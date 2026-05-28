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
class HandoffSnapshot:
    project_dir: str = ""
    workflow_id: str = ""
    objective: str = ""
    status: str = "unknown"
    next_recommended_action: str = ""
    success_criteria: List[str] = field(default_factory=list)
    evidence_required: List[str] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    artifact_manifest: Dict[str, Any] = field(default_factory=dict)
    memory_context: Dict[str, Any] = field(default_factory=dict)
    goal: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_dir": self.project_dir,
            "workflow_id": self.workflow_id,
            "objective": self.objective,
            "status": self.status,
            "next_recommended_action": self.next_recommended_action,
            "success_criteria": list(self.success_criteria),
            "evidence_required": list(self.evidence_required),
            "evidence": list(self.evidence),
            "missing_evidence": list(self.missing_evidence),
            "artifact_manifest": dict(self.artifact_manifest),
            "memory_context": dict(self.memory_context),
            "goal": dict(self.goal),
            "generated_at": self.generated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "HandoffSnapshot":
        return cls(
            project_dir=data.get("project_dir", ""),
            workflow_id=data.get("workflow_id", ""),
            objective=data.get("objective", ""),
            status=data.get("status", "unknown"),
            next_recommended_action=data.get("next_recommended_action", ""),
            success_criteria=list(data.get("success_criteria", [])),
            evidence_required=list(data.get("evidence_required", [])),
            evidence=list(data.get("evidence", [])),
            missing_evidence=list(data.get("missing_evidence", [])),
            artifact_manifest=dict(data.get("artifact_manifest", {})),
            memory_context=dict(data.get("memory_context", {})),
            goal=dict(data.get("goal", {})),
            generated_at=data.get("generated_at", ""),
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
class DomainRole:
    name: str
    purpose: str
    responsibilities: List[str] = field(default_factory=list)
    stage: str = ""
    required_artifacts: List[str] = field(default_factory=list)
    produces: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "purpose": self.purpose,
            "responsibilities": list(self.responsibilities),
            "stage": self.stage,
            "required_artifacts": list(self.required_artifacts),
            "produces": list(self.produces),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainRole":
        return cls(
            name=data.get("name", ""),
            purpose=data.get("purpose", ""),
            responsibilities=list(data.get("responsibilities", [])),
            stage=data.get("stage", ""),
            required_artifacts=list(data.get("required_artifacts", [])),
            produces=list(data.get("produces", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class DomainProfile:
    domain_name: str
    objective: str
    subdomains: List[str] = field(default_factory=list)
    roles: List[DomainRole] = field(default_factory=list)
    required_design_artifact_types: List[str] = field(default_factory=list)
    evidence_required: List[str] = field(default_factory=list)
    review_gates: List[str] = field(default_factory=list)
    risk_policy_gates: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain_name": self.domain_name,
            "objective": self.objective,
            "subdomains": list(self.subdomains),
            "roles": [role.to_dict() for role in self.roles],
            "required_design_artifact_types": list(self.required_design_artifact_types),
            "evidence_required": list(self.evidence_required),
            "review_gates": list(self.review_gates),
            "risk_policy_gates": list(self.risk_policy_gates),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DomainProfile":
        return cls(
            domain_name=data.get("domain_name", ""),
            objective=data.get("objective", ""),
            subdomains=list(data.get("subdomains", [])),
            roles=[
                role if isinstance(role, DomainRole) else DomainRole.from_dict(role)
                for role in data.get("roles", [])
            ],
            required_design_artifact_types=list(data.get("required_design_artifact_types", [])),
            evidence_required=list(data.get("evidence_required", [])),
            review_gates=list(data.get("review_gates", [])),
            risk_policy_gates=list(data.get("risk_policy_gates", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class WorkDesign:
    objective: str
    domain: str
    scope: str = ""
    assumptions: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    subdomains: List[str] = field(default_factory=list)
    roles_required: List[str] = field(default_factory=list)
    deliverables: List[str] = field(default_factory=list)
    evidence_required: List[str] = field(default_factory=list)
    risk_policy_checks: List[str] = field(default_factory=list)
    review_gates: List[str] = field(default_factory=list)
    design_artifacts: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "objective": self.objective,
            "domain": self.domain,
            "scope": self.scope,
            "assumptions": list(self.assumptions),
            "constraints": list(self.constraints),
            "subdomains": list(self.subdomains),
            "roles_required": list(self.roles_required),
            "deliverables": list(self.deliverables),
            "evidence_required": list(self.evidence_required),
            "risk_policy_checks": list(self.risk_policy_checks),
            "review_gates": list(self.review_gates),
            "design_artifacts": list(self.design_artifacts),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "WorkDesign":
        return cls(
            objective=data.get("objective", ""),
            domain=data.get("domain", ""),
            scope=data.get("scope", ""),
            assumptions=list(data.get("assumptions", [])),
            constraints=list(data.get("constraints", [])),
            subdomains=list(data.get("subdomains", [])),
            roles_required=list(data.get("roles_required", [])),
            deliverables=list(data.get("deliverables", [])),
            evidence_required=list(data.get("evidence_required", [])),
            risk_policy_checks=list(data.get("risk_policy_checks", [])),
            review_gates=list(data.get("review_gates", [])),
            design_artifacts=list(data.get("design_artifacts", [])),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class DesignArtifact:
    artifact_id: str
    kind: str
    title: str
    path: str
    owner_role: str = ""
    domain: str = ""
    required_for: List[str] = field(default_factory=list)
    status: str = "created"
    checksum: str = ""
    created_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "kind": self.kind,
            "title": self.title,
            "path": self.path,
            "owner_role": self.owner_role,
            "domain": self.domain,
            "required_for": list(self.required_for),
            "status": self.status,
            "checksum": self.checksum,
            "created_at": self.created_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DesignArtifact":
        return cls(
            artifact_id=data.get("artifact_id", ""),
            kind=data.get("kind", ""),
            title=data.get("title", ""),
            path=data.get("path", ""),
            owner_role=data.get("owner_role", ""),
            domain=data.get("domain", ""),
            required_for=list(data.get("required_for", [])),
            status=data.get("status", "created"),
            checksum=data.get("checksum", ""),
            created_at=data.get("created_at", ""),
            metadata=dict(data.get("metadata", {})),
        )


@dataclass(frozen=True)
class ArtifactManifest:
    workflow_id: str
    design_artifacts: List[DesignArtifact] = field(default_factory=list)
    evidence: List[str] = field(default_factory=list)
    updated_at: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "design_artifacts": [artifact.to_dict() for artifact in self.design_artifacts],
            "evidence": list(self.evidence),
            "updated_at": self.updated_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ArtifactManifest":
        return cls(
            workflow_id=data.get("workflow_id", ""),
            design_artifacts=[
                artifact if isinstance(artifact, DesignArtifact) else DesignArtifact.from_dict(artifact)
                for artifact in data.get("design_artifacts", [])
            ],
            evidence=list(data.get("evidence", [])),
            updated_at=data.get("updated_at", ""),
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
