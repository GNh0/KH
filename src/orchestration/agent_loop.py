import json
import re

from src.contracts import AdapterRequest, GoalState
from src.core.architect import SystemArchitect
from src.core.snapshot_manager import SnapshotManager
from src.harness.sandbox import CodeSandbox
from src.orchestration.llm_router import LLMRouter
from src.orchestration.roles import build_default_role_metadata, format_role_brief
from src.platforms.dispatcher_factory import DispatcherFactory


class AgentLoop:
    """Architect -> dispatch -> bounded workers -> harness loop."""

    def __init__(self, llm_router: LLMRouter, project_dir: str, platform_mode: str = "local"):
        self.llm = llm_router
        self.project_dir = project_dir
        self.platform_mode = platform_mode
        self.architect = SystemArchitect(project_dir, self.llm)
        self.sandbox = CodeSandbox()
        self.snapshot = SnapshotManager(project_dir)
        self.role_metadata = build_default_role_metadata()

    @staticmethod
    def parse_target_files(files_str: str) -> list:
        match = re.search(r"\[.*\]", files_str, re.DOTALL)
        if not match:
            raise ValueError("target file response does not contain a JSON array")

        target_files = json.loads(match.group())
        if not isinstance(target_files, list) or not target_files:
            raise ValueError("target file response must be a non-empty JSON array")
        if not all(isinstance(file_name, str) and file_name.strip() for file_name in target_files):
            raise ValueError("target file response must contain only non-empty strings")
        return target_files

    @staticmethod
    def build_goal_metadata(requirement: str) -> dict:
        goal = GoalState(
            objective=requirement,
            success_criteria=[
                "design document created",
                "target files identified",
                "workflow dispatch completed",
            ],
            evidence_required=[
                "design_doc",
                "target_files",
                "workflow dispatch completed",
            ],
            progress_notes=["goal created by AgentLoop"],
            metadata={"source": "agent_loop"},
        )
        return {"goal": goal.to_dict()}

    def build_dispatch_metadata(self, requirement: str) -> dict:
        metadata = {
            **self.role_metadata,
            **self.build_goal_metadata(requirement),
        }
        if self.platform_mode == "local":
            metadata["llm_router"] = self.llm
        return metadata

    def run(self, requirement: str, framework: str, libs: list = None, max_turns: int = 5):
        if libs is None:
            libs = []

        print("=== 1. [Architect] Drafting design document ===")
        design_doc_path = self.architect.draft_architecture(requirement, framework, libs)
        with open(design_doc_path, "r", encoding="utf-8") as handle:
            design_content = handle.read()

        design_content = (
            f"{design_content}\n\n"
            "## UAF Default Orchestration Role Graph\n"
            f"{format_role_brief()}\n"
        )

        print("=== 2. [Dispatcher] Selecting target files ===")
        dispatch_prompt = (
            "Return only a JSON array of source file paths that should be created "
            "or modified to implement the architecture. Example: "
            "[\"server.py\", \"index.html\", \"style.css\"]."
        )
        files_str = self.llm.chat("You output only JSON arrays.", f"{dispatch_prompt}\n\n{design_content}")
        target_files = self.parse_target_files(files_str)

        print(f"[Dispatcher] Dispatching {len(target_files)} target file(s): {target_files}")

        print(f"=== 3. [Dispatch Execution] Starting worker dispatch (Mode: {self.platform_mode}) ===")
        dispatcher = DispatcherFactory.get_dispatcher(self.platform_mode)

        request = AdapterRequest(
            project_dir=self.project_dir,
            files=target_files,
            design_doc=design_content,
            platform_mode=self.platform_mode,
            metadata=self.build_dispatch_metadata(requirement),
        )
        results = dispatcher.execute_request(request).to_legacy_messages()

        for result in results:
            print(f"> {result}")

        print("=== 4. [Harness] Dispatch loop complete ===")
