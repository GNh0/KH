import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict

from src.contracts import WorkflowTaskResult


def task_id_for_file(file_name: str) -> str:
    return file_name.replace("/", "_").replace("\\", "_").replace(".", "_")


@dataclass(frozen=True)
class WorkflowTaskInput:
    project_dir: str
    file_name: str
    design_doc: str
    platform_mode: str
    role: str = "implementer"
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def task_id(self) -> str:
        return task_id_for_file(self.file_name)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "project_dir": self.project_dir,
            "file_name": self.file_name,
            "design_doc": self.design_doc,
            "platform_mode": self.platform_mode,
            "role": self.role,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class GeneratedTaskArtifact:
    status: str
    content: str = ""
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)


class DeterministicCodeGenerationAdapter:
    name = "deterministic-local"

    async def generate(self, task: WorkflowTaskInput) -> GeneratedTaskArtifact:
        content = _default_generated_content(task)
        return GeneratedTaskArtifact(
            status="success",
            content=content,
            message="deterministic local code generated",
            metadata={
                "source": "deterministic-local",
                "design_doc_chars": len(task.design_doc or ""),
            },
        )


class LLMCodeGenerationAdapter:
    name = "llm-local"

    def __init__(self, llm_router):
        self.llm = llm_router

    async def generate(self, task: WorkflowTaskInput) -> GeneratedTaskArtifact:
        system_prompt = (
            "You are a focused coding subagent. Return only the complete file "
            "content for the requested target file. Use fenced code blocks only "
            "when useful; do not include explanations outside the file content."
        )
        user_prompt = (
            f"Target file: {task.file_name}\n"
            f"Role: {task.role}\n"
            f"Platform mode: {task.platform_mode}\n\n"
            "Design document:\n"
            f"{task.design_doc}\n"
        )
        response = self.llm.chat(system_prompt, user_prompt)
        content = _extract_generated_content(response, task.file_name)
        if not content.strip():
            return GeneratedTaskArtifact(
                status="blocked",
                content="",
                message="LLM returned empty generated content",
                metadata={"source": "llm"},
            )
        return GeneratedTaskArtifact(
            status="success",
            content=content,
            message="LLM local code generated",
            metadata={
                "source": "llm",
                "response_chars": len(response or ""),
            },
        )


class LocalTaskRunner:
    name = "local"

    def __init__(self, adapter=None):
        self.adapter = adapter or DeterministicCodeGenerationAdapter()

    async def run(self, task: WorkflowTaskInput) -> WorkflowTaskResult:
        adapter_name = getattr(self.adapter, "name", self.adapter.__class__.__name__)
        try:
            target_path = _resolve_target_path(task.project_dir, task.file_name)
            artifact = await self.adapter.generate(task)
            artifact_status = artifact.status or "failed"
            artifact_metadata = dict(artifact.metadata)

            base_metadata = {
                "runner": self.name,
                "generation_adapter": adapter_name,
                "target_path": str(target_path),
                "artifact_exists": target_path.exists(),
                "evidence": [],
            }
            base_metadata.update(artifact_metadata)

            if artifact_status != "success":
                return WorkflowTaskResult(
                    task_id=task.task_id,
                    file_name=task.file_name,
                    role=task.role,
                    status=artifact_status,
                    message=artifact.message or "local code generation did not complete",
                    metadata=base_metadata,
                )

            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(artifact.content, encoding="utf-8")
            bytes_written = len(artifact.content.encode("utf-8"))
            return WorkflowTaskResult(
                task_id=task.task_id,
                file_name=task.file_name,
                role=task.role,
                status="success",
                message=artifact.message or "local runner task completed",
                metadata={
                    "runner": self.name,
                    "generation_adapter": adapter_name,
                    "target_path": str(target_path),
                    "artifact_exists": target_path.exists(),
                    "bytes_written": bytes_written,
                    **artifact_metadata,
                    "evidence": [
                        "task runner completed",
                        "code generated",
                        f"target file accepted:{task.file_name}",
                        f"target file generated:{task.file_name}",
                    ],
                },
            )
        except Exception as exc:
            target_path = None
            try:
                target_path = _resolve_target_path(task.project_dir, task.file_name)
            except Exception:
                pass
            return WorkflowTaskResult(
                task_id=task.task_id,
                file_name=task.file_name,
                role=task.role,
                status="failed",
                message=str(exc),
                metadata={
                    "runner": self.name,
                    "generation_adapter": adapter_name,
                    "target_path": str(target_path) if target_path else "",
                    "artifact_exists": target_path.exists() if target_path else False,
                    "error_type": type(exc).__name__,
                    "evidence": [],
                },
            )


def _resolve_target_path(project_dir: str, file_name: str) -> Path:
    project_root = Path(project_dir).resolve()
    raw_path = Path(file_name)
    candidate = raw_path if raw_path.is_absolute() else project_root / raw_path
    resolved = candidate.resolve()

    root = str(project_root)
    target = str(resolved)
    try:
        common_root = os.path.commonpath([root, target])
    except ValueError as exc:
        raise ValueError(f"target file escapes project root: {file_name}") from exc
    if common_root != root:
        raise ValueError(f"target file escapes project root: {file_name}")
    return resolved


def _default_generated_content(task: WorkflowTaskInput) -> str:
    file_name = task.file_name.replace("\\", "/")
    design_summary = _comment_block(task.design_doc or "No design document provided.")
    if file_name.endswith(".py"):
        return (
            '"""Generated by UAF LocalTaskRunner."""\n\n'
            f"{design_summary}\n\n"
            "def main():\n"
            "    return None\n\n\n"
            "if __name__ == \"__main__\":\n"
            "    main()\n"
        )
    if file_name.endswith(".md"):
        return (
            "# Generated Artifact\n\n"
            "Generated by UAF LocalTaskRunner.\n\n"
            "## Design Context\n\n"
            f"{task.design_doc or 'No design document provided.'}\n"
        )
    return (
        "Generated by UAF LocalTaskRunner.\n\n"
        "Design Context:\n"
        f"{task.design_doc or 'No design document provided.'}\n"
    )


def _comment_block(text: str) -> str:
    lines = [line.rstrip() for line in text.splitlines()]
    if not lines:
        lines = ["No design document provided."]
    return "\n".join(f"# {line}" if line else "#" for line in lines)


def _extract_generated_content(response: str, file_name: str = "") -> str:
    text = response or ""
    markdown_target = file_name.replace("\\", "/").lower().endswith(".md")
    if markdown_target:
        match = re.fullmatch(r"\s*```(?:[A-Za-z0-9_+.-]+)?\s*\n(.*?)```\s*", text, re.DOTALL)
    else:
        match = re.search(r"```(?:[A-Za-z0-9_+.-]+)?\s*\n(.*?)```", text, re.DOTALL)
    if match:
        content = match.group(1)
    else:
        content = text
    if content and not content.endswith("\n"):
        content += "\n"
    return content
