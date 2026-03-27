# 版本 3.1 (穩定後端) - 修正 get_achievers 錯誤
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
    return {"message": "運動獎勵計劃 API - 版本 3.1"}

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

# **FIX: VERSION 3.1**
@app.get("/api/achievers", response_model=list[Student])
async def get_achievers():
    achievers = []
    cursor = 0
    try:
        while True:
            # 使用 match='[0-9]*' 來篩選可能為學號的 key，增加掃描效率和安全性
            cursor, keys = await redis.scan(cursor, match='[0-9]*')
            if not keys:
                if cursor == 0:
                    break
                else:
                    continue

            # 一次性獲取所有 key 的數據，提高效率
            pipeline = redis.pipeline()
            for key in keys:
                pipeline.get(key)
            
            all_data = await pipeline.execute()

            for data in all_data:
                # 確保取回的 data 是 dict 類型，並且 check_in_count >= 10
                if isinstance(data, dict) and data.get('check_in_count', 0) >= 10:
                    try:
                        # 使用 Pydantic 模型進行驗證，確保資料結構正確
                        achievers.append(Student(**data))
                    except Exception as validation_error:
                        # 如果資料驗證失敗，打印日誌並跳過，避免程式崩潰
                        print(f"Skipping invalid student data: {data}. Error: {validation_error}")
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
    
    pipe = redis.pipeline()
    imported_count = 0
    
    for row in students:
        student_id = row.get('學號') or row.get('\ufeff學號') # 處理BOM字元
        name = row.get('姓名')
        cls = row.get('班別')
        
        if student_id and name and cls:
            # 確保 ID 是字串且去除前後空格
            student_id_str = str(student_id).strip()
            if not student_id_str: continue # 如果學號為空字串則跳過

            record = {
                "id": student_id_str,
                "name": str(name).strip(),
                "cls": str(cls).strip(),
                "check_in_count": 0,
                "last_check_in_date": ""
            }
            pipe.set(record["id"], json.dumps(record)) # 存儲為 JSON 字串
            imported_count += 1
            
    if imported_count == 0:
        raise HTTPException(status_code=400, detail="檔案中沒有有效的學生數據行。請檢查欄位標題和檔案編碼。")
        
    await pipe.execute()
    return {"message": f"成功處理 {imported_count} 位學生資料。"}
