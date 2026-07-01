import asyncio
import base64
import json
import os
import time

import aiosqlite
import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import APIKeyHeader
from pydantic import BaseModel


app = FastAPI(title="Antigravity Universal Agent API")
API_KEY = os.environ.get("AG_API_KEY", "antigravity-secret-key-v2")
api_key_header = APIKeyHeader(name="X-API-Key")

db_conn = None


async def log_rotation_task():
    """Keep the local webhook log table bounded."""
    while True:
        try:
            if db_conn:
                await db_conn.execute(
                    """
                    DELETE FROM webhook_logs
                    WHERE id NOT IN (
                        SELECT id FROM webhook_logs ORDER BY id DESC LIMIT 10000
                    )
                    """
                )
                await db_conn.commit()
                await db_conn.execute("VACUUM")
        except Exception as exc:
            print(f"Log rotation error: {exc}")

        await asyncio.sleep(3600)


@app.on_event("startup")
async def startup():
    global db_conn
    db_conn = await aiosqlite.connect("webhook_states.db")
    await db_conn.execute("PRAGMA journal_mode=WAL;")
    await db_conn.execute(
        "CREATE TABLE IF NOT EXISTS webhook_logs "
        "(id INTEGER PRIMARY KEY, project_id TEXT, task_id TEXT, data TEXT, created_at REAL)"
    )
    await db_conn.commit()
    asyncio.create_task(log_rotation_task())


@app.on_event("shutdown")
async def shutdown():
    global db_conn
    if db_conn:
        await db_conn.close()


class WebhookPayload(BaseModel):
    project_id: str
    task_id: str
    base64_data: str


def verify_api_key(api_key: str = Depends(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=401, detail="Invalid API Key")
    return api_key


@app.post("/api/webhook/subagent-result")
async def receive_subagent_result(payload: WebhookPayload, api_key: str = Depends(verify_api_key)):
    try:
        decoded_json_str = base64.b64decode(payload.base64_data).decode("utf-8")
        data = json.loads(decoded_json_str)
        current_time = time.time()

        await db_conn.execute(
            "INSERT INTO webhook_logs (project_id, task_id, data, created_at) VALUES (?, ?, ?, ?)",
            (payload.project_id, payload.task_id, decoded_json_str, current_time),
        )
        await db_conn.commit()

        return {
            "status": "SUCCESS",
            "message": "Webhook safely recorded with WAL mode",
            "processed_files": list(data.keys()),
        }

    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Invalid payload format: {exc}") from exc


@app.get("/api/health")
async def health_check():
    return {"status": "OK", "version": "V2.5"}


def start_server(port=8000):
    uvicorn.run(app, host="0.0.0.0", port=port)


if __name__ == "__main__":
    start_server()
