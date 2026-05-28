import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple

from src.contracts import ArtifactManifest, DesignArtifact, DomainProfile, WorkDesign
from src.orchestration.domain_profiles import (
    DomainProfileBuilder,
    render_work_design_markdown,
    work_design_from_profile,
)
from src.orchestration.deliverable_exports import export_office_deliverables
from src.orchestration.runtime_paths import project_artifact_design_dir, project_state_dir


ARTIFACT_EVIDENCE = [
    "work design saved",
    "artifact manifest saved",
    "required design artifacts saved",
]


class ArtifactStore:
    def __init__(self, project_dir: str, thread_id: str = ""):
        self.project_root = Path(project_dir).resolve()
        self.thread_id = thread_id
        self.design_dir = project_artifact_design_dir(str(self.project_root), thread_id=thread_id)
        self.state_dir = project_state_dir(str(self.project_root), thread_id=thread_id)
        self.manifest_path = self.state_dir / "artifact_manifest.json"
        self.events_path = self.state_dir / "artifact_events.jsonl"

    def resolve_project_path(self, path: str) -> Path:
        raw_path = Path(path)
        candidate = raw_path if raw_path.is_absolute() else self.project_root / raw_path
        resolved = candidate.resolve()
        try:
            common_root = os.path.commonpath([str(self.project_root), str(resolved)])
        except ValueError as exc:
            raise ValueError(f"path escapes project root: {path}") from exc
        if common_root != str(self.project_root):
            raise ValueError(f"path escapes project root: {path}")
        return resolved

    def describe_paths(self) -> Dict[str, str]:
        return {
            "artifact_dir": str(self.design_dir),
            "manifest_path": str(self.manifest_path),
            "events_path": str(self.events_path),
        }

    def save_work_design(
        self,
        workflow_id: str,
        work_design: WorkDesign,
        source_design_doc: str = "",
    ) -> Dict[str, Any]:
        content = render_work_design_markdown(work_design)
        if source_design_doc:
            content = f"{content}\n## Source Design Document\n\n{source_design_doc}\n"

        artifact = self._write_design_artifact(
            workflow_id=workflow_id,
            artifact_id="work_design",
            kind="work-design",
            title="Work Design",
            content=content,
            owner_role="domain-designer",
            domain=work_design.domain,
            required_for=["dispatch", "review", "qa", "risk", "final"],
            metadata={"work_design": work_design.to_dict()},
        )
        manifest = self._save_manifest(
            workflow_id=workflow_id,
            artifacts=[artifact],
            evidence=ARTIFACT_EVIDENCE,
            metadata={"work_design": work_design.to_dict()},
        )
        self._append_event("work_design_saved", {"artifact_id": artifact.artifact_id})
        return _stage_result(manifest, self.describe_paths())

    def save_design_artifacts(
        self,
        workflow_id: str,
        domain: str,
        artifact_specs: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        artifacts = [
            self._write_design_artifact(
                workflow_id=workflow_id,
                artifact_id=spec.get("artifact_id", ""),
                kind=spec.get("kind", "design-artifact"),
                title=spec.get("title", spec.get("artifact_id", "Design Artifact")),
                content=spec.get("content", ""),
                owner_role=spec.get("owner_role", "domain-designer"),
                domain=domain,
                required_for=list(spec.get("required_for", ["review"])),
                metadata=dict(spec.get("metadata", {})),
            )
            for spec in artifact_specs
        ]
        manifest = self._merge_manifest(
            workflow_id=workflow_id,
            artifacts=artifacts,
            evidence=ARTIFACT_EVIDENCE,
        )
        for artifact in artifacts:
            self._append_event("design_artifact_saved", {"artifact_id": artifact.artifact_id})
        return _stage_result(manifest, self.describe_paths())

    def save_stage(
        self,
        workflow_id: str,
        domain_profile: DomainProfile,
        work_design: WorkDesign,
        source_design_doc: str,
        artifact_specs: Iterable[Dict[str, Any]],
    ) -> Dict[str, Any]:
        self.save_work_design(workflow_id, work_design, source_design_doc)
        if artifact_specs:
            self.save_design_artifacts(workflow_id, domain_profile.domain_name, artifact_specs)
        manifest = self.load_manifest()
        manifest = ArtifactManifest(
            workflow_id=workflow_id,
            design_artifacts=manifest.design_artifacts,
            evidence=ARTIFACT_EVIDENCE,
            updated_at=_utc_now(),
            metadata={
                "domain_profile": domain_profile.to_dict(),
                "work_design": work_design.to_dict(),
            },
        )
        self._write_manifest(manifest)
        return _stage_result(manifest, self.describe_paths())

    def load_manifest(self) -> ArtifactManifest:
        if not self.manifest_path.exists():
            return ArtifactManifest(workflow_id="")
        return ArtifactManifest.from_dict(
            json.loads(self.manifest_path.read_text(encoding="utf-8"))
        )

    def _write_design_artifact(
        self,
        workflow_id: str,
        artifact_id: str,
        kind: str,
        title: str,
        content: str,
        owner_role: str,
        domain: str,
        required_for: List[str],
        metadata: Dict[str, Any],
    ) -> DesignArtifact:
        safe_artifact_id = _safe_artifact_id(artifact_id)
        self.design_dir.mkdir(parents=True, exist_ok=True)
        artifact_path = self.design_dir / f"{safe_artifact_id}.md"
        content_to_write = content or f"# {title}\n\nNo content provided yet.\n"
        artifact_path.write_text(content_to_write, encoding="utf-8")
        return DesignArtifact(
            artifact_id=safe_artifact_id,
            kind=kind,
            title=title,
            path=str(artifact_path),
            owner_role=owner_role,
            domain=domain,
            required_for=list(required_for),
            status="created",
            checksum=hashlib.sha256(content_to_write.encode("utf-8")).hexdigest(),
            created_at=_utc_now(),
            metadata={
                "workflow_id": workflow_id,
                **dict(metadata),
            },
        )

    def _save_manifest(
        self,
        workflow_id: str,
        artifacts: List[DesignArtifact],
        evidence: List[str],
        metadata: Dict[str, Any],
    ) -> ArtifactManifest:
        manifest = ArtifactManifest(
            workflow_id=workflow_id,
            design_artifacts=artifacts,
            evidence=list(evidence),
            updated_at=_utc_now(),
            metadata=dict(metadata),
        )
        self._write_manifest(manifest)
        return manifest

    def _merge_manifest(
        self,
        workflow_id: str,
        artifacts: List[DesignArtifact],
        evidence: List[str],
    ) -> ArtifactManifest:
        existing = self.load_manifest()
        by_id = {
            artifact.artifact_id: artifact
            for artifact in existing.design_artifacts
        }
        for artifact in artifacts:
            by_id[artifact.artifact_id] = artifact
        merged_evidence = list(existing.evidence)
        for item in evidence:
            if item not in merged_evidence:
                merged_evidence.append(item)
        manifest = ArtifactManifest(
            workflow_id=workflow_id or existing.workflow_id,
            design_artifacts=list(by_id.values()),
            evidence=merged_evidence,
            updated_at=_utc_now(),
            metadata=dict(existing.metadata),
        )
        self._write_manifest(manifest)
        return manifest

    def _write_manifest(self, manifest: ArtifactManifest) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(
            json.dumps(manifest.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    def _append_event(self, event_type: str, payload: Dict[str, Any]) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True)
        event = {
            "event_type": event_type,
            "timestamp": _utc_now(),
            "payload": dict(payload),
        }
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, sort_keys=True))
            handle.write("\n")


def build_design_stage(
    project_dir: str,
    workflow_id: str,
    design_doc: str,
    file_list: Iterable[str],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    metadata = metadata or {}
    profile = _domain_profile_from_metadata(metadata, design_doc)
    deliverables = list(metadata.get("deliverables", [])) or list(file_list or []) or ["final output"]
    work_design = _work_design_from_metadata(metadata, profile, deliverables)
    store = ArtifactStore(project_dir, thread_id=_thread_id_from_metadata(metadata))
    result = store.save_stage(
        workflow_id=workflow_id,
        domain_profile=profile,
        work_design=work_design,
        source_design_doc=design_doc,
        artifact_specs=metadata.get("design_artifacts", []) or [],
    )
    deliverable_exports = export_office_deliverables(
        project_dir=project_dir,
        workflow_id=workflow_id,
        domain_profile=profile,
        work_design=work_design,
        source_design_doc=design_doc,
        file_list=file_list,
        metadata=metadata,
    )
    stage_result = {
        "domain_profile": profile.to_dict(),
        "work_design": work_design.to_dict(),
        **result,
        "deliverable_exports": deliverable_exports,
    }
    stage_result["evidence"] = _unique_evidence(
        list(result.get("evidence", [])) + list(deliverable_exports.get("evidence", []))
    )
    return stage_result


def _domain_profile_from_metadata(metadata: Dict[str, Any], design_doc: str) -> DomainProfile:
    profile_data = metadata.get("domain_profile")
    if isinstance(profile_data, DomainProfile):
        return profile_data
    if isinstance(profile_data, dict):
        merged = dict(profile_data)
        if "roles" not in merged:
            built = DomainProfileBuilder.build(
                objective=merged.get("objective", "") or _objective_from_design_doc(design_doc),
                domain_hint=merged.get("domain_name", ""),
                subdomains=merged.get("subdomains", []),
                artifact_types=merged.get("required_design_artifact_types", []),
            )
            merged = {**built.to_dict(), **merged}
        return DomainProfile.from_dict(merged)
    return DomainProfileBuilder.build(
        objective=metadata.get("objective", "") or _objective_from_design_doc(design_doc),
        domain_hint=metadata.get("domain_hint", ""),
        subdomains=metadata.get("subdomains", []),
        artifact_types=metadata.get("required_design_artifact_types", []),
    )


def _work_design_from_metadata(
    metadata: Dict[str, Any],
    profile: DomainProfile,
    deliverables: List[str],
) -> WorkDesign:
    design_data = metadata.get("work_design")
    if isinstance(design_data, WorkDesign):
        return design_data
    if isinstance(design_data, dict):
        return WorkDesign.from_dict(design_data)
    return work_design_from_profile(
        profile,
        scope=metadata.get("scope", ""),
        assumptions=metadata.get("assumptions", []),
        constraints=metadata.get("constraints", []),
        deliverables=deliverables,
    )


def _objective_from_design_doc(design_doc: str) -> str:
    for line in (design_doc or "").splitlines():
        stripped = line.strip("# ").strip()
        if stripped:
            return stripped
    return "UAF workflow"


def _thread_id_from_metadata(metadata: Dict[str, Any]) -> str:
    app_context = metadata.get("app_context", {}) or {}
    return metadata.get("thread_id", "") or app_context.get("thread_id", "")


def _stage_result(manifest: ArtifactManifest, store_paths: Dict[str, str]) -> Dict[str, Any]:
    return {
        "manifest": manifest.to_dict(),
        "store": dict(store_paths),
        "evidence": list(manifest.evidence),
    }


def _safe_artifact_id(artifact_id: str) -> str:
    if not artifact_id:
        raise ValueError("artifact_id is required")
    if "/" in artifact_id or "\\" in artifact_id or ".." in artifact_id:
        raise ValueError(f"unsafe artifact_id: {artifact_id}")
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", artifact_id.strip()).strip(".-")
    if not safe:
        raise ValueError(f"unsafe artifact_id: {artifact_id}")
    return safe


def _unique_evidence(items: Iterable[str]) -> List[str]:
    result: List[str] = []
    for item in items:
        value = str(item).strip()
        if value and value not in result:
            result.append(value)
    return result


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()
