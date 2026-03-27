# 版本 2.9 (用最穩定的方式重寫 get_achievers 函數)
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
    class Config:
        extra = 'allow'

# --- API 端點 ---

@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 版本 2.9"}

@get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    student_data = await redis.get(student_id)
    if not student_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    return student_data

@post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    student_data = await redis.get(student_id)
    if not student_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    student_data['check_in_count'] += 1
    await redis.set(student_id, student_data)
    return student_data

@post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    student_data = await redis.get(student_id)
    if not student_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    if student_data.get('check_in_count', 0) < 10:
        raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
    student_data['check_in_count'] -= 10
    await redis.set(student_id, student_data)
    return student_data

# --- 👇 最終修正的函數 ---
@app.get("/api/achievers", response_model=list[Student])
async def get_achievers():
    achievers = []
    cursor = 0
    try:
        while True:
            # 1. 使用 scan 獲取一批 keys
            cursor, keys = await redis.scan(cursor)
            
            # 2. 如果這批 keys 不為空，才進行處理
            if keys:
                # 3. ✨ 放棄 pipeline，改用最簡單的 for 循環，逐一處理
                for key in keys:
                    try:
                        # 4. ✨ 對每一個 key 都單獨獲取和檢查
                        data = await redis.get(key)
                        if isinstance(data, dict) and data.get('check_in_count', 0) >= 10:
                            # 5. ✨ 驗證模型，確保是完整的學生資料
                            achievers.append(Student(**data))
                    except Exception:
                        # 如果單一 key 的獲取或驗證失敗，就跳過這個 key，繼續處理下一個
                        # 這能確保程式絕對不會因單筆「髒數據」而崩潰
                        continue
            
            # 6. 如果 scan 回傳的 cursor 為 0，代表所有 key 都已遍歷完畢
            if cursor == 0:
                break
        return achievers
    except Exception as e:
        # 如果在 scan 循環的任何環節發生意外，返回一個空的列表和 500 錯誤
        # 這樣可以避免前端 JSON 解析失敗
        print(f"Error in get_achievers: {e}") # 在伺服器日誌中打印錯誤
        raise HTTPException(status_code=500, detail="獲取列表時發生內部錯誤")

@app.post("/api/students/batch-import")
async def batch_import_students(students: List[dict]):
    if not students:
        raise HTTPException(status_code=400, detail="學生列表不可為空")

    pipe = redis.pipeline()
    imported_count = 0
    
    for student_row in students:
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
