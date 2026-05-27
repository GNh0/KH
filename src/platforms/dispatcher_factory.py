import sys
import json
import os
from src.tasks.workflows import dispatch_project_workflow

class DispatcherFactory:
    @staticmethod
    def get_dispatcher(platform_mode: str):
        if platform_mode.lower() == "antigravity":
            return AntigravityDispatcher()
        return CeleryDispatcher()

class CeleryDispatcher:
    def execute(self, project_dir: str, files: list, design_doc: str, platform_mode: str):
        # [V2 Lite] 스레드풀 대신 Celery 분산 태스크 큐 호출
        print(f"[CeleryDispatcher] {len(files)}개 파일에 대한 분산 워크플로우를 시작합니다...")
        workflow_id = dispatch_project_workflow(project_dir, files, design_doc, platform_mode)
        return [f"[Success] 워크플로우 제출 완료 (ID: {workflow_id}) - 백그라운드 처리 중..."]

class AntigravityDispatcher:
    def execute(self, project_dir: str, files: list, design_doc: str, platform_mode: str):
        # 1. 부모 AI에게 병렬 처리를 위해 전체 파일 목록 전송
        print(f"\n[NATIVE_DISPATCH_REQUIRED] Spawn Subagents for: {json.dumps(files)}")
        
        # 2. [V2 Lite] stdin 락(Lock) 방식 폐기 -> FastAPI Webhook 비동기 대기
        print(">>> WAITING_FOR_WEBHOOK_IPC <<<")
        print("부모 AI님, 서브에이전트들의 작업이 끝나면 아래 엔드포인트로 전송해주세요:")
        print("POST http://localhost:8000/api/webhook/subagent-result")
        print(f"Payload format: {{'project_id': '{os.path.basename(project_dir)}', 'task_id': '...', 'base64_data': '...'}}")
        sys.stdout.flush()
        
        return [f"[Pending] 🚀 FastAPI Webhook을 통해 비동기 응답 대기 중..."]
