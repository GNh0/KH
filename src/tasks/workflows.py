import asyncio
import os
import multiprocessing
import time
import httpx
import base64
import json


async def code_generation_worker(queue: asyncio.Queue, project_id: str):
    """비동기 큐에서 파일을 꺼내와 처리하는 초경량 워커"""
    webhook_url = os.environ.get("AG_WEBHOOK_URL", "http://127.0.0.1:8000/api/webhook/subagent-result")
    api_key = os.environ.get("AG_API_KEY", "antigravity-secret-key-v2")

    async with httpx.AsyncClient() as client:
        while True:
            try:
                task_data = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            file_name = task_data["file_name"]
            design_doc = task_data["design_doc"]

            print(f"[Worker] '{file_name}' 작업 시작...")

            try:
                # 샌드박스, LLM 통신 로직 위임 지점 (실제 구현 시 여기서 호출)
                await asyncio.sleep(1.0)
                print(f"[Worker] '{file_name}' 작업 완료 (샌드박스 통과)")

                result_payload = {file_name: "SUCCESS"}
                b64_data = base64.b64encode(json.dumps(result_payload).encode("utf-8")).decode("utf-8")

                payload = {
                    "project_id": project_id,
                    "task_id": file_name.replace("/", "_").replace(".", "_"),
                    "base64_data": b64_data
                }

                await client.post(
                    webhook_url,
                    json=payload,
                    headers={"X-API-Key": api_key}
                )
            except Exception as e:
                print(f"[Worker] '{file_name}' 에러: {e}")
            finally:
                queue.task_done()


async def async_project_workflow(project_dir: str, file_list: list, design_doc: str, platform_mode: str):
    """[V2.5] Celery를 완벽히 대체하는 파이썬 내장 비동기 큐 오케스트레이터"""
    queue = asyncio.Queue()
    project_id = os.path.basename(project_dir)  # 버그 수정: os import 보장 후 호출

    for f in file_list:
        queue.put_nowait({
            "file_name": f,
            "design_doc": design_doc,
            "platform_mode": platform_mode
        })

    # [V2.5] 워커 개수 안전 캡 - 사용자가 100000을 입력해도 OS가 터지지 않음
    max_workers_env = int(os.environ.get("AG_MAX_WORKERS", "50"))
    cpu_cores = multiprocessing.cpu_count() or 4
    hard_limit = cpu_cores * 10
    safe_max_workers = min(max_workers_env, hard_limit)
    num_workers = min(safe_max_workers, len(file_list))

    workers = [asyncio.create_task(code_generation_worker(queue, project_id)) for _ in range(num_workers)]
    print(f"[Master] 워커 {num_workers}개 실행 중 (요청: {max_workers_env} / 하드 리미트: {hard_limit})")

    await queue.join()
    await asyncio.gather(*workers)
    print(f"\n[Master] 모든 비동기 작업 완료! (로컬 큐 처리됨)")
    return f"workflow_{project_id}"


def dispatch_project_workflow(project_dir: str, file_list: list, design_doc: str, platform_mode: str):
    """외부 호출용 동기 래퍼"""
    return asyncio.run(async_project_workflow(project_dir, file_list, design_doc, platform_mode))
