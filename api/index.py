# 版本 3.0 (穩定後端)
from fastapi import FastAPI, HTTPException
from upstash_redis import Redis
import os
from pydantic import BaseModel, Field
from typing import List, Optional

app = FastAPI()
redis = Redis.from_env()

class Student(BaseModel):
    id: str
    name: str
    cls: str
    check_in_count: int
    last_check_in_date: str

class StudentImport(BaseModel):
    學號: Optional[str] = None
    姓名: Optional[str] = None
    班別: Optional[str] = None
    class Config:
        extra = 'allow'

@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 版本 3.0"}

@app.get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    data = await redis.get(student_id)
    if not data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    return data

@app.post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    data = await redis.get(student_id)
    if not data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    data['check_in_count'] += 1
    await redis.set(student_id, data)
    return data

@app.post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    data = await redis.get(student_id)
    if not data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    if data.get('check_in_count', 0) < 10:
        raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
    data['check_in_count'] -= 10
    await redis.set(student_id, data)
    return data

@app.get("/api/achievers", response_model=list[Student])
async def get_achievers():
    achievers = []
    cursor = 0
    try:
        while True:
            cursor, keys = await redis.scan(cursor)
            if keys:
                for key in keys:
                    try:
                        data = await redis.get(key)
                        if isinstance(data, dict) and data.get('check_in_count', 0) >= 10:
                            achievers.append(Student(**data))
                    except Exception:
                        continue
            if cursor == 0:
                break
        return achievers
    except Exception as e:
        print(f"Error in get_achievers: {e}")
        raise HTTPException(status_code=500, detail="獲取列表時發生內部錯誤")

@app.post("/api/students/batch-import")
async def batch_import_students(students: List[dict]):
    if not students:
        raise HTTPException(status_code=400, detail="學生列表不可為空")
    pipe, imported_count = redis.pipeline(), 0
    for row in students:
        student_id = row.get('學號') or row.get('\ufeff學號')
        name, cls = row.get('姓名'), row.get('班別')
        if student_id and name and cls:
            record = {
                "id": str(student_id).strip(),
                "name": str(name).strip(),
                "cls": str(cls).strip(),
                "check_in_count": 0,
                "last_check_in_date": ""
            }
            pipe.set(record["id"], record)
            imported_count += 1
    if imported_count == 0:
        raise HTTPException(status_code=400, detail="檔案中沒有有效的學生數據行。請檢查欄位標題和檔案編碼。")
    await pipe.execute()
    return {"message": f"成功處理 {imported_count} 位學生資料。"}
