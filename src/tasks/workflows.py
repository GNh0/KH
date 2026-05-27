import asyncio
import base64
import json
import multiprocessing
import os
from typing import List

import httpx

from src.contracts import WorkflowDispatchResult, WorkflowTaskResult
from src.orchestration.roles import build_role_gate_results


def _task_id(file_name: str) -> str:
    return file_name.replace("/", "_").replace("\\", "_").replace(".", "_")


async def code_generation_worker(queue: asyncio.Queue, project_id: str, results: List[WorkflowTaskResult]):
    webhook_url = os.environ.get("AG_WEBHOOK_URL", "http://127.0.0.1:8000/api/webhook/subagent-result")
    api_key = os.environ.get("AG_API_KEY", "antigravity-secret-key-v2")

    async with httpx.AsyncClient() as client:
        while True:
            try:
                task_data = queue.get_nowait()
            except asyncio.QueueEmpty:
                break

            file_name = task_data["file_name"]
            role = task_data.get("role", "implementer")
            task_id = _task_id(file_name)

            print(f"[Worker] '{file_name}' task started as {role}.")

            try:
                # Placeholder execution surface for app/agent runtimes.
                await asyncio.sleep(1.0)

                result_payload = {
                    file_name: {
                        "status": "SUCCESS",
                        "role": role,
                    }
                }
                b64_data = base64.b64encode(json.dumps(result_payload).encode("utf-8")).decode("utf-8")
                payload = {
                    "project_id": project_id,
                    "task_id": task_id,
                    "base64_data": b64_data,
                }

                response = await client.post(
                    webhook_url,
                    json=payload,
                    headers={"X-API-Key": api_key},
                )
                response.raise_for_status()

                results.append(
                    WorkflowTaskResult(
                        task_id=task_id,
                        file_name=file_name,
                        role=role,
                        status="success",
                        message="webhook recorded",
                        metadata={"http_status": response.status_code},
                    )
                )
                print(f"[Worker] '{file_name}' task completed.")
            except Exception as exc:
                results.append(
                    WorkflowTaskResult(
                        task_id=task_id,
                        file_name=file_name,
                        role=role,
                        status="failed",
                        message=str(exc),
                        metadata={"error_type": type(exc).__name__},
                    )
                )
                print(f"[Worker] '{file_name}' failed: {exc}")
            finally:
                queue.task_done()


async def async_project_workflow(
    project_dir: str,
    file_list: list,
    design_doc: str,
    platform_mode: str,
    metadata: dict = None,
) -> WorkflowDispatchResult:
    queue = asyncio.Queue()
    project_id = os.path.basename(project_dir)
    metadata = metadata or {}
    results: List[WorkflowTaskResult] = []

    for file_name in file_list:
        queue.put_nowait({
            "file_name": file_name,
            "design_doc": design_doc,
            "platform_mode": platform_mode,
            "role": "implementer",
            "role_graph": metadata.get("role_graph", {}),
        })

    max_workers_env = int(os.environ.get("AG_MAX_WORKERS", "50"))
    cpu_cores = multiprocessing.cpu_count() or 4
    hard_limit = cpu_cores * 10
    safe_max_workers = min(max_workers_env, hard_limit)
    num_workers = min(safe_max_workers, len(file_list))

    workers = [
        asyncio.create_task(code_generation_worker(queue, project_id, results))
        for _ in range(num_workers)
    ]
    print(f"[Master] starting {num_workers} worker(s) (requested: {max_workers_env} / hard limit: {hard_limit})")

    await queue.join()
    if workers:
        await asyncio.gather(*workers)

    order = {file_name: index for index, file_name in enumerate(file_list)}
    ordered_results = sorted(results, key=lambda result: order.get(result.file_name, len(order)))
    success = len(ordered_results) == len(file_list) and all(
        result.status == "success"
        for result in ordered_results
    )
    gate_results = build_role_gate_results([
        result.to_dict()
        for result in ordered_results
    ])

    print("[Master] async workflow completed.")
    return WorkflowDispatchResult(
        workflow_id=f"workflow_{project_id}",
        success=success,
        task_results=ordered_results,
        gate_results=gate_results,
        metadata={
            "file_count": len(file_list),
            "platform_mode": platform_mode,
            "orchestration_roles": metadata.get("orchestration_roles", []),
        },
    )


def dispatch_project_workflow(
    project_dir: str,
    file_list: list,
    design_doc: str,
    platform_mode: str,
    metadata: dict = None,
) -> WorkflowDispatchResult:
    return asyncio.run(async_project_workflow(project_dir, file_list, design_doc, platform_mode, metadata))
