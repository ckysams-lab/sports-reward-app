# 版本 2.2 (修正 500 和 422 錯誤)
from fastapi import FastAPI, HTTPException
from upstash_redis import Redis
import os
from pydantic import BaseModel, Field
from typing import List, Optional

# --- 初始化 ---
app = FastAPI()
redis = Redis.from_env()

# --- 資料模型 ---
class Student(BaseModel):
    id: str
    name: str
    cls: str
    check_in_count: int
    last_check_in_date: str

class StudentImport(BaseModel):
    # Optional 允許欄位為空，我們會在後續邏輯中過濾掉
    學號: Optional[str] = Field(alias='學號', default=None)
    姓名: Optional[str] = Field(alias='姓名', default=None)
    班別: Optional[str] = Field(alias='班別', default=None)

# --- API 端點 ---

@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 版本 2.2"}

# ... (get_student, check_in, redeem 端點與之前相同)
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

# --- 👇 修正後的函數 ---

@app.get("/api/achievers", response_model=list[Student])
async def get_achievers():
    # ✨ 修正 1: 使用 SCAN 指令代替危險的 KEYS 指令
    cursor = 0
    all_student_keys = []
    while True:
        cursor, keys = await redis.scan(cursor)
        all_student_keys.extend(keys)
        if cursor == 0:
            break

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
    imported_count = 0
    
    # ✨ 修正 2: 過濾掉無效的或空的學生數據
    for student_data in students:
        if student_data.學號 and student_data.姓名 and student_data.班別:
            student_id = student_data.學號
            student_record = {
                "id": student_id,
                "name": student_data.姓名,
                "cls": student_data.班別,
                "check_in_count": 0,
                "last_check_in_date": ""
            }
            pipe.set(student_id, student_record)
            imported_count += 1
    
    if imported_count == 0:
        raise HTTPException(status_code=400, detail="上傳的檔案中沒有有效的學生數據行。")

    await pipe.execute()
    
    return {"message": f"成功處理 {imported_count} 位學生資料。"}
