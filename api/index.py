# 版本 2.3 (加固 achievers 函數並優化 import 邏輯)
from fastapi import FastAPI, HTTPException
from upstash_redis import Redis
import os
from pydantic import BaseModel, Field
from typing import List, Optional
import json

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
    學號: Optional[str] = None
    姓名: Optional[str] = None
    班別: Optional[str] = None
    
    # Pydantic v2 技巧，允許從額外的欄位名稱進行映射
    # 這可以處理因為編碼問題導致的看不見的字元（例如BOM）
    class Config:
        extra = 'allow'

# --- API 端點 ---

@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 版本 2.3"}

# ... (get_student, check_in, redeem 端點與之前相同) ...
@app.get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    student_data = await redis.get(student_id)
    if not student_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    return student_data

@app.post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    # ... (code from 2.2) ...
    pass

@app.post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    # ... (code from 2.2) ...
    pass


# --- 👇 修正後的函數 ---

@app.get("/api/achievers", response_model=list[Student])
async def get_achievers():
    # ✨ 修正 1: 讓函數更強壯，能應對非預期的數據
    achievers = []
    cursor = 0
    while True:
        cursor, keys = await redis.scan(cursor)
        if keys:
            pipe = redis.pipeline()
            for key in keys:
                pipe.get(key)
            results = await pipe.execute()
            
            for data in results:
                # 進行非常嚴格的檢查，確保數據是我們想要的學生格式
                if isinstance(data, dict) and 'check_in_count' in data and data.get('check_in_count', 0) >= 10:
                    try:
                        # 驗證數據是否能構成一個完整的 Student 模型
                        achievers.append(Student(**data))
                    except Exception:
                        # 如果數據格式不對，就靜默跳過，不讓程式崩潰
                        continue
        if cursor == 0:
            break
    return achievers

@app.post("/api/students/batch-import")
async def batch_import_students(students: List[dict]): # ✨ 修正 2: 先接收為通用字典
    if not students:
        raise HTTPException(status_code=400, detail="學生列表不可為空")

    pipe = redis.pipeline()
    imported_count = 0
    
    for student_row in students:
        # ✨ 修正 3: 手動處理可能的欄位名稱，應對編碼問題
        # 檢查常見的欄位名稱變化，例如被 BOM 字元污染的 'ï»¿學號'
        student_id = student_row.get('學號') or student_row.get('\ufeff學號')
        name = student_row.get('姓名')
        cls = student_row.get('班別')

        if student_id and name and cls:
            student_record = {
                "id": str(student_id).strip(),
                "name": str(name).strip(),
                "cls": str(cls).strip(),
                "check_in_count": 0,
                "last_check_in_date": ""
            }
            pipe.set(student_record["id"], student_record)
            imported_count += 1
    
    if imported_count == 0:
        raise HTTPException(status_code=400, detail="上傳的檔案中沒有有效的學生數據行。請檢查欄位標題是否為 '學號', '姓名', '班別'，以及檔案是否為 UTF-8 編碼。")

    await pipe.execute()
    
    return {"message": f"成功處理 {imported_count} 位學生資料。"}

