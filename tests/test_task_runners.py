import asyncio
import tempfile
import unittest
from pathlib import Path

from src.tasks.runners import (
    GeneratedTaskArtifact,
    LLMCodeGenerationAdapter,
    LocalTaskRunner,
    WorkflowTaskInput,
    task_id_for_file,
)


class StaticGenerationAdapter:
    name = "static-test"

    def __init__(self, artifact):
        self.artifact = artifact

    async def generate(self, task):
        return self.artifact


class FailingGenerationAdapter:
    name = "failing-test"

    async def generate(self, task):
        raise RuntimeError("generator crashed")


class FakeLLMRouter:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def chat(self, system_prompt, user_prompt):
        self.calls.append((system_prompt, user_prompt))
        return self.response


class LocalTaskRunnerTests(unittest.TestCase):
    def test_local_runner_writes_generated_file_for_safe_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            artifact = GeneratedTaskArtifact(
                status="success",
                content="print('hello')\n",
                message="generated test file",
                metadata={"source": "unit-test"},
            )
            task = WorkflowTaskInput(
                project_dir=str(project_dir),
                file_name="src/app.py",
                design_doc="# design",
                platform_mode="local",
                role="implementer",
                metadata={"goal": {"objective": "build api"}},
            )

            result = asyncio.run(
                LocalTaskRunner(adapter=StaticGenerationAdapter(artifact)).run(task)
            )
            target_path = project_dir / "src" / "app.py"
            generated_content = target_path.read_text(encoding="utf-8")

        self.assertEqual(result.task_id, "src_app_py")
        self.assertEqual(result.file_name, "src/app.py")
        self.assertEqual(result.role, "implementer")
        self.assertEqual(result.status, "success")
        self.assertEqual(result.metadata["runner"], "local")
        self.assertTrue(result.metadata["artifact_exists"])
        self.assertEqual(generated_content, "print('hello')\n")
        self.assertEqual(result.metadata["generation_adapter"], "static-test")
        self.assertEqual(result.metadata["bytes_written"], len("print('hello')\n".encode("utf-8")))
        self.assertIn("task runner completed", result.metadata["evidence"])
        self.assertIn("code generated", result.metadata["evidence"])

    def test_local_runner_returns_blocked_without_writing_when_adapter_blocks(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            artifact = GeneratedTaskArtifact(
                status="blocked",
                content="print('should not write')\n",
                message="needs more context",
            )
            task = WorkflowTaskInput(
                project_dir=str(project_dir),
                file_name="src/app.py",
                design_doc="# design",
                platform_mode="local",
            )

            result = asyncio.run(
                LocalTaskRunner(adapter=StaticGenerationAdapter(artifact)).run(task)
            )

        self.assertEqual(result.status, "blocked")
        self.assertFalse((project_dir / "src" / "app.py").exists())
        self.assertEqual(result.message, "needs more context")
        self.assertEqual(result.metadata["generation_adapter"], "static-test")
        self.assertEqual(result.metadata["evidence"], [])

    def test_local_runner_reports_adapter_exceptions_as_failed_results(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            task = WorkflowTaskInput(
                project_dir=str(project_dir),
                file_name="src/app.py",
                design_doc="# design",
                platform_mode="local",
            )

            result = asyncio.run(
                LocalTaskRunner(adapter=FailingGenerationAdapter()).run(task)
            )

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.metadata["runner"], "local")
        self.assertEqual(result.metadata["generation_adapter"], "failing-test")
        self.assertEqual(result.metadata["error_type"], "RuntimeError")
        self.assertFalse((project_dir / "src" / "app.py").exists())

    def test_llm_generation_adapter_extracts_fenced_code(self):
        llm = FakeLLMRouter("```python\nprint('from llm')\n```")
        task = WorkflowTaskInput(
            project_dir="C:/work/demo",
            file_name="main.py",
            design_doc="# design",
            platform_mode="local",
        )

        artifact = asyncio.run(LLMCodeGenerationAdapter(llm).generate(task))

        self.assertEqual(artifact.status, "success")
        self.assertEqual(artifact.content, "print('from llm')\n")
        self.assertEqual(artifact.metadata["source"], "llm")
        self.assertIn("main.py", llm.calls[0][1])

    def test_local_runner_can_write_llm_adapter_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            project_dir = Path(tmp) / "demo"
            project_dir.mkdir()
            llm = FakeLLMRouter("```python\nprint('from llm')\n```")
            task = WorkflowTaskInput(
                project_dir=str(project_dir),
                file_name="main.py",
                design_doc="# design",
                platform_mode="local",
            )

            result = asyncio.run(LocalTaskRunner(adapter=LLMCodeGenerationAdapter(llm)).run(task))
            generated_content = (project_dir / "main.py").read_text(encoding="utf-8")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.metadata["generation_adapter"], "llm-local")
        self.assertEqual(generated_content, "print('from llm')\n")

    def test_local_runner_rejects_target_paths_outside_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            task = WorkflowTaskInput(
                project_dir=tmp,
                file_name="../outside.py",
                design_doc="# design",
                platform_mode="local",
            )

            result = asyncio.run(LocalTaskRunner().run(task))

        self.assertEqual(result.status, "failed")
        self.assertEqual(result.file_name, "../outside.py")
        self.assertEqual(result.metadata["runner"], "local")
        self.assertEqual(result.metadata["error_type"], "ValueError")

    def test_task_id_for_file_normalizes_common_path_separators(self):
        self.assertEqual(task_id_for_file("src\\app.py"), "src_app_py")


if __name__ == "__main__":
    unittest.main()
