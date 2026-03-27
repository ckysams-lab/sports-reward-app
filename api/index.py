# 版本 1.6
from fastapi import FastAPI, HTTPException
from vercel_kv import KV
import os
from dotenv import load_dotenv
from pydantic import BaseModel

# --- 初始化 ---
# Vercel 會自動注入環境變數，本地測試時可從 .env 檔案讀取
load_dotenv()

app = FastAPI()
kv = KV()

# --- 資料模型 ---
# 用於定義 API 的請求和回應格式，更專業
class Student(BaseModel):
    id: str
    name: str
    cls: str # 'class' 是 python 關鍵字，所以用 cls
    check_in_count: int
    last_check_in_date: str

# --- API 端點 (Endpoints) ---

@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 版本 1.6"}

# 獲取單一學生資料
@app.get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    student_data = await kv.get(student_id)
    if not student_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    return student_data

# 體育大使簽到
@app.post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    student_data = await kv.get(student_id)
    if not student_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    
    # 這裡省略了檢查日期的邏輯以簡化，實際項目中應加上
    student_data['check_in_count'] += 1
    await kv.set(student_id, student_data)
    return student_data

# 學生兌換獎勵
@app.post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    student_data = await kv.get(student_id)
    if not student_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    
    if student_data['check_in_count'] < 10:
        raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
        
    student_data['check_in_count'] -= 10
    await kv.set(student_id, student_data)
    return student_data

# 管理員獲取達標者列表
@app.get("/api/achievers", response_model=list[Student])
async def get_achievers():
    all_student_keys = await kv.keys("*") # 這裡假設學號不含特殊符號
    achievers = []
    for key in all_student_keys:
        student_data = await kv.get(key)
        if student_data and student_data.get('check_in_count', 0) >= 10:
            achievers.append(student_data)
    return achievers

# (可選) 首次匯入學生的工具 API (這是一個一次性工具)
# 在部署後，你可以透過瀏覽器訪問一次 /api/import-students 來匯入
@app.get("/api/import-students")
async def import_students():
    try:
        import pandas as pd
        df = pd.read_csv("students.csv") # 假設 students.csv 和 api 資料夾同級
        count = 0
        for _, row in df.iterrows():
            student_id = str(row['學號'])
            student_record = {
                "id": student_id,
                "name": row['姓名'],
                "cls": row['班別'],
                "check_in_count": 0,
                "last_check_in_date": ""
            }
            await kv.set(student_id, student_record)
            count += 1
        return {"message": f"成功匯入 {count} 位學生"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
