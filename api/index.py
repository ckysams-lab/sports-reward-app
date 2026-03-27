# 版本 1.8 (Upstash 最終版)
from fastapi import FastAPI, HTTPException
from upstash_redis import Redis
import os
from pydantic import BaseModel, Field
from typing import List

# --- 初始化 ---
app = FastAPI()
# Redis.from_env() 會自動讀取 Vercel 提供的環境變數
redis = Redis.from_env()

# --- 資料模型 ---
class Student(BaseModel):
    id: str
    name: str
    cls: str
    check_in_count: int
    last_check_in_date: str

class StudentImport(BaseModel):
    學號: str = Field(alias='學號')
    姓名: str = Field(alias='姓名')
    班別: str = Field(alias='班別')

# --- API 端點 ---

@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 版本 1.8"}

@app.get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    student_data = await redis.get(student_id)
    if not student_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    return student_data

@app.post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    student_data = await redis.get(student_id)
    if not student_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    
    # 實際項目應加上日期檢查邏輯
    student_data['check_in_count'] += 1
    await redis.set(student_id, student_data)
    return student_data

@app.post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    student_data = await redis.get(student_id)
    if not student_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    
    if student_data.get('check_in_count', 0) < 10:
        raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
        
    student_data['check_in_count'] -= 10
    await redis.set(student_id, student_data)
    return student_data

@app.get("/api/achievers", response_model=list[Student])
async def get_achievers():
    # 注意: keys('*') 在大型資料庫中效能較差，但對於學校規模是可行的
    all_student_keys = await redis.keys("*")
    if not all_student_keys:
        return []

    pipe = redis.pipeline()
    for key in all_student_keys:
        pipe.get(key)
    
    all_students_data = await pipe.execute()
    
    achievers = []
    for data in all_students_data:
        if data and data.get('check_in_count', 0) >= 10:
            achievers.append(data)
    return achievers

@app.post("/api/students/batch-import")
async def batch_import_students(students: List[StudentImport]):
    if not students:
        raise HTTPException(status_code=400, detail="學生列表不可為空")

    pipe = redis.pipeline()
    for student_data in students:
        student_id = student_data.學號
        student_record = {
            "id": student_id,
            "name": student_data.姓名,
            "cls": student_data.班別,
            "check_in_count": 0,
            "last_check_in_date": ""
        }
        pipe.set(student_id, student_record)
    
    await pipe.execute()
    
    return {"message": f"成功匯入或更新 {len(students)} 位學生資料。"}
