# 版本 3.2 (穩定後端) - 再次加固 get_achievers 錯誤處理
from fastapi import FastAPI, HTTPException
from upstash_redis import Redis
import os
from pydantic import BaseModel, Field
from typing import List, Optional
import json

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
    return {"message": "運動獎勵計劃 API - 版本 3.2"}

@app.get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    data = await redis.get(student_id)
    if not isinstance(data, dict): # 確保返回的是字典
        raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")
    return data

@app.post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    data = await redis.get(student_id)
    if not isinstance(data, dict):
        raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")
    data['check_in_count'] += 1
    await redis.set(student_id, data)
    return data

@app.post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    data = await redis.get(student_id)
    if not isinstance(data, dict):
        raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")
    if data.get('check_in_count', 0) < 10:
        raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
    data['check_in_count'] -= 10
    await redis.set(student_id, data)
    return data

# **FIX: VERSION 3.2**
@app.get("/api/achievers", response_model=list[Student])
async def get_achievers():
    achievers = []
    cursor = 0
    try:
        while True:
            cursor, keys = await redis.scan(cursor, match='[0-9]*')
            if keys:
                for key in keys:
                    data = None # 重置 data
                    try:
                        # 直接處理單個 key，避免 pipeline 的複雜性
                        data = await redis.get(key)
                        # 核心修正：必須嚴格檢查 data 是否為 dict
                        if isinstance(data, dict) and data.get('check_in_count', 0) >= 10:
                            achievers.append(Student(**data))
                    except Exception as inner_error:
                        # 如果單個 key 處理失敗，打印日誌並安全跳過
                        print(f"Skipping key '{key}' due to error. Data: {data}. Error: {inner_error}")
                        continue
            if cursor == 0:
                break
        return achievers
    except Exception as e:
        print(f"CRITICAL Error in get_achievers: {e}")
        raise HTTPException(status_code=500, detail="獲取列表時發生嚴重的內部錯誤")

@app.post("/api/students/batch-import")
async def batch_import_students(students: List[dict]):
    if not students:
        raise HTTPException(status_code=400, detail="學生列表不可為空")
    
    pipe = redis.pipeline()
    imported_count = 0
    
    for row in students:
        student_id = row.get('學號') or row.get('\ufeff學號')
        name = row.get('姓名')
        cls = row.get('班別')
        
        if student_id and name and cls:
            student_id_str = str(student_id).strip()
            if not student_id_str: continue

            record = {
                "id": student_id_str,
                "name": str(name).strip(),
                "cls": str(cls).strip(),
                "check_in_count": 0,
                "last_check_in_date": ""
            }
            # 使用 set(..., json.dumps(...)) 來確保存儲的是 JSON 字符串
            pipe.set(record["id"], json.dumps(record))
            imported_count += 1
            
    if imported_count == 0:
        raise HTTPException(status_code=400, detail="檔案中沒有有效的學生數據行。請檢查欄位標題和檔案編碼。")
        
    await pipe.execute()
    return {"message": f"成功處理 {imported_count} 位學生資料。"}
