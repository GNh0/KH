import asyncio
import json
import base64
import aiosqlite
import os
import time
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from fastapi.security import APIKeyHeader
import uvicorn

app = FastAPI(title="Antigravity Universal Agent API")
# [V2.5] 환경변수로 키 관리 단일화 - workflows.py의 AG_API_KEY와 항상 동기화됨
API_KEY = os.environ.get("AG_API_KEY", "antigravity-secret-key-v2")
api_key_header = APIKeyHeader(name="X-API-Key")

db_conn = None

async def log_rotation_task():
    """[V2.2 개선] 주기적으로 오래된 로그를 정리하여 DB 용량 폭발을 막는 백그라운드 청소부"""
    while True:
        try:
            if db_conn:
                # 예: 최대 1만 개의 최신 로그만 남기고 삭제
                await db_conn.execute("""
                    DELETE FROM webhook_logs 
                    WHERE id NOT IN (
                        SELECT id FROM webhook_logs ORDER BY id DESC LIMIT 10000
                    )
                """)
                await db_conn.commit()
                # VACUUM을 통해 삭제된 더미 공간을 반환하여 실제 파일 용량 다이어트
                await db_conn.execute("VACUUM")
        except Exception as e:
            print(f"Log rotation error: {e}")
        
        await asyncio.sleep(3600)  # 1시간마다(3600초) 백그라운드에서 실행

@app.on_event("startup")
async def startup():
    global db_conn
    # [V2.2 개선] 서버 가동 시 단일 커넥션을 열어두고 영구 재사용 (I/O 병목 제거)
    db_conn = await aiosqlite.connect("webhook_states.db")
    
    # 동시 쓰기(Concurrency) 성능을 획기적으로 높이는 WAL 모드 활성화
    await db_conn.execute("PRAGMA journal_mode=WAL;")
    
    await db_conn.execute("CREATE TABLE IF NOT EXISTS webhook_logs (id INTEGER PRIMARY KEY, project_id TEXT, task_id TEXT, data TEXT, created_at REAL)")
    await db_conn.commit()
    
    # 백그라운드 로그 정리 태스크 가동
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
        decoded_json_str = base64.b64decode(payload.base64_data).decode('utf-8')
        data = json.loads(decoded_json_str)
        
        current_time = time.time()
        
        # [V2.2 개선] 연결을 매번 열지 않고 글로벌 db_conn 재사용
        await db_conn.execute(
            "INSERT INTO webhook_logs (project_id, task_id, data, created_at) VALUES (?, ?, ?, ?)",
            (payload.project_id, payload.task_id, decoded_json_str, current_time)
        )
        await db_conn.commit()
            
        return {"status": "SUCCESS", "message": "Webhook safely recorded with WAL mode", "processed_files": list(data.keys())}
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid payload format: {str(e)}")

@app.get("/api/health")
async def health_check():
    return {"status": "OK", "version": "V2.5"}

def start_server(port=8000):
    uvicorn.run(app, host="0.0.0.0", port=port)

if __name__ == "__main__":
    start_server()
