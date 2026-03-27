# 版本 1.8
from fastapi import FastAPI, HTTPException, Body
from upstash_redis import Redis
import os
from pydantic import BaseModel, Field
from typing import List

# --- 初始化 (與之前相同) ---
app = FastAPI()
redis = Redis.from_env()

# --- 資料模型 (部分更新) ---
class Student(BaseModel):
    id: str
    name: str
    cls: str
    check_in_count: int
    last_check_in_date: str

class StudentImport(BaseModel):
    # 欄位名稱對應 CSV 的標題
    學號: str = Field(alias='學號')
    姓名: str = Field(alias='姓名')
    班別: str = Field(alias='班別')

# --- API 端點 ---

# (GET /api, GET /api/students/{student_id}, POST .../check-in, POST .../redeem, GET /api/achievers 等端點保持不變)
# ...

# 【新功能】批量匯入學生的 API 接口
@app.post("/api/students/batch-import")
async def batch_import_students(students: List[StudentImport]):
    if not students:
        raise HTTPException(status_code=400, detail="學生列表不可為空")

    # 使用 pipeline 批量操作，效率更高
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

# (我們不再需要之前那個一次性的 /api/import-students 端點了)
