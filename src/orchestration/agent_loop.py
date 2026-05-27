import os
import json
import re
import concurrent.futures
from src.core.architect import SystemArchitect
from src.core.snapshot_manager import SnapshotManager
from src.harness.sandbox import CodeSandbox
from src.orchestration.llm_router import LLMRouter
from src.platforms.dispatcher_factory import DispatcherFactory
from src.skills.token_optimizer import minify_code, truncate_logs

class AgentLoop:
    """설계(Architect) -> 분할(Dispatch) -> [병렬] 코딩(Coder) -> 평가(Harness) 루프 엔진"""
    def __init__(self, llm_router: LLMRouter, project_dir: str, platform_mode: str = "local"):
        self.llm = llm_router
        self.project_dir = project_dir
        self.platform_mode = platform_mode
        self.architect = SystemArchitect(project_dir, self.llm)
        self.sandbox = CodeSandbox()
        self.snapshot = SnapshotManager(project_dir)

    def run(self, requirement: str, framework: str, libs: list = None, max_turns: int = 5):
        if libs is None:
            libs = []
            
        print(f"=== 1. [Architect] 설계 파이프라인 시작 ===")
        design_doc_path = self.architect.draft_architecture(requirement, framework, libs)
        with open(design_doc_path, 'r', encoding='utf-8') as f:
            design_content = f.read()
            
        print(f"=== 2. [Dispatcher] 필요 파일 목록 분석 및 스레드 분할 ===")
        dispatch_prompt = "아래 아키텍처를 구현하기 위해 작성해야 할 소스코드 파일들의 이름을 JSON 문자열 배열로만 반환하세요. (예: [\"server.py\", \"index.html\", \"style.css\"])"
        try:
            files_str = self.llm.chat("You output only JSON arrays.", f"{dispatch_prompt}\n\n{design_content}")
            match = re.search(r'\[.*\]', files_str, re.DOTALL)
            target_files = json.loads(match.group()) if match else ["main.py"]
        except:
            target_files = ["main.py"]
            
        print(f"[Dispatcher] {len(target_files)}개의 파일을 병렬 생성합니다: {target_files}")
        
        print(f"=== 3. [Dispatch Execution] 멀티 에이전트 구동 (Mode: {self.platform_mode}) ===")
        dispatcher = DispatcherFactory.get_dispatcher(self.platform_mode)
        
        # [V2 Lite] AgentLoop 내부의 무거운 병렬 처리(Thread) 코드를 모두 폐기하고
        # 오직 Dispatcher (Celery 또는 Antigravity Webhook)로 위임합니다.
        results = dispatcher.execute(self.project_dir, target_files, design_content, self.platform_mode)
            
        for result in results:
            print(f"> {result}")
            
        print(f"=== 4. 오케스트레이션 루프 완료 (비동기 위임) ===")

