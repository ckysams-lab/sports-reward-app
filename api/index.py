import os
import json
import csv
import io
import re
from datetime import datetime, timezone, timedelta
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List

from upstash_redis.asyncio import Redis

# =================================================================
# Redis 連接設定
# =================================================================
redis_url = os.getenv("UPSTASH_REDIS_REST_URL")
redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")

redis = None
if redis_url and redis_token:
    try:
        redis = Redis(url=redis_url, token=redis_token)
    except Exception as e:
        print(f"CRITICAL: Failed to initialize Async Redis. Error: {e}")

app = FastAPI()

class Student(BaseModel):
    id: str
    name: str
    cls: str
    check_in_count: int
    last_check_in_date: str

def check_redis():
    if redis is None:
        raise HTTPException(status_code=503, detail="後端資料庫連接初始化失敗。")

# =================================================================
# 智能解碼器 
# =================================================================
def smart_decode(contents: bytes) -> str:
    encodings = ['utf-8-sig', 'cp950', 'big5hkscs', 'big5', 'utf-8', 'gbk']
    for enc in encodings:
        text = contents.decode(enc, errors='replace')
        if '學號' in text or '姓名' in text or '班別' in text or 'id' in text.lower():
            return text
    for enc in encodings:
        try:
            return contents.decode(enc)
        except UnicodeDecodeError:
            continue
    return contents.decode('utf-8-sig', errors='replace')

# =================================================================
# API Endpoints
# =================================================================
@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 每日限簽一次升級版"}

@app.get("/api/all-students", response_model=list[Student])
async def get_all_students():
    check_redis()
    all_students = []
    try:
        all_keys = await redis.keys('*')
        if not all_keys:
            return []

        all_raw_data = await redis.mget(*all_keys)
        
        for raw_data in all_raw_data:
            if raw_data is None:
                continue
            student_data = None
            if isinstance(raw_data, dict):
                student_data = raw_data
            elif isinstance(raw_data, str):
                try:
                    student_data = json.loads(raw_data)
                except json.JSONDecodeError:
                    continue
            
            if student_data and isinstance(student_data, dict) and 'cls' in student_data:
                all_students.append(Student(**student_data))
                
        return all_students
        
    except Exception as e:
        print(f"CRITICAL Error in get_all_students: {e}")
        raise HTTPException(status_code=500, detail="獲取全體學生列表時發生錯誤。")

@app.post("/api/students/batch-import-file")
async def batch_import_students_from_file(file: UploadFile = File(...)):
    check_redis()
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="請上傳 CSV 檔案。")

    contents = await file.read()
    decoded_content = smart_decode(contents)

    try:
        dialect = csv.Sniffer().sniff(decoded_content[:1024])
        reader = csv.reader(io.StringIO(decoded_content), dialect)
    except Exception:
        reader = csv.reader(io.StringIO(decoded_content))
    
    try:
        rows = list(reader)
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"CSV 解析錯誤: {e}")

    if not rows or len(rows) < 2:
        raise HTTPException(status_code=400, detail="檔案為空或只有標題行，沒有學生資料。")

    headers = [str(h).replace('\ufeff', '').strip() for h in rows[0]]
    id_idx = name_idx = cls_idx = -1
    
    for i, header in enumerate(headers):
        if '學號' in header or 'id' in header.lower(): id_idx = i
        elif '姓名' in header or 'name' in header.lower(): name_idx = i
        elif '班別' in header or 'class' in header.lower() or 'cls' in header.lower(): cls_idx = i
        
    if id_idx == -1 or name_idx == -1 or cls_idx == -1:
        raise HTTPException(
            status_code=400, 
            detail=f"找不到對應的欄位。必須包含'學號', '姓名', '班別'。\n後端實際讀取到的標題為: {headers}"
        )

    pipe = redis.pipeline()
    imported_count = 0
    
    for i in range(1, len(rows)):
        row = rows[i]
        if not row or len(row) == 0:
            continue
            
        student_id = row[id_idx] if id_idx < len(row) else ""
        name = row[name_idx] if name_idx < len(row) else ""
        cls = row[cls_idx] if cls_idx < len(row) else ""
        
        student_id_str = str(student_id).strip()
        name_str = str(name).strip()
        cls_str = str(cls).strip().upper() 
        
        if student_id_str and name_str and cls_str:
            redis_key = f"{cls_str}-{student_id_str}"
            record = {
                "id": student_id_str, 
                "name": name_str, 
                "cls": cls_str, 
                "check_in_count": 0, 
                "last_check_in_date": ""
            }
            pipe.set(redis_key, json.dumps(record))
            imported_count += 1
            
    if imported_count == 0:
        sample_data = rows[1] if len(rows) > 1 else "無"
        raise HTTPException(status_code=400, detail=f"標題正確，但沒有匯入任何資料。第一行資料解析為: {sample_data}")
        
    try:
        await pipe.exec()
    except Exception as e:
        print(f"Pipeline execution failed: {e}")
        raise HTTPException(status_code=500, detail="儲存資料到資料庫時發生內部錯誤。")

    return {"message": f"成功匯入 {imported_count} 位學生資料。"}

@app.get("/api/students/{cls}/{student_id}", response_model=Student)
async def get_student(cls: str, student_id: str):
    check_redis()
    redis_key = f"{cls.upper()}-{student_id}"
    raw_data = await redis.get(redis_key)
    if not raw_data:
        raise HTTPException(status_code=404, detail="找不到該學生，請確認班別與學號是否正確")
    student_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    return Student(**student_data)

# >> 核心修改區域：簽到邏輯 <<
@app.post("/api/students/{cls}/{student_id}/check-in", response_model=Student)
async def check_in(cls: str, student_id: str):
    check_redis()
    redis_key = f"{cls.upper()}-{student_id}"
    raw_data = await redis.get(redis_key)
    
    if not raw_data:
        raise HTTPException(status_code=404, detail="找不到該學生，請確認班別與學號是否正確")
        
    student_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    
    # 1. 取得香港當前時間 (UTC+8)
    hk_timezone = timezone(timedelta(hours=8))
    today_str = datetime.now(hk_timezone).strftime("%Y-%m-%d")
    
    # 2. 檢查今天是否已經簽到過
    if student_data.get('last_check_in_date') == today_str:
        raise HTTPException(status_code=400, detail="該學生今日已經簽到過了，不可重複記錄！")
        
    # 3. 如果沒有簽到過，則增加次數並更新日期為今天
    student_data['check_in_count'] += 1
    student_data['last_check_in_date'] = today_str
    
    await redis.set(redis_key, json.dumps(student_data))
    return Student(**student_data)

@app.post("/api/students/{cls}/{student_id}/redeem", response_model=Student)
async def redeem_reward(cls: str, student_id: str):
    check_redis()
    redis_key = f"{cls.upper()}-{student_id}"
    raw_data = await redis.get(redis_key)
    if not raw_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    student_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    
    if student_data.get('check_in_count', 0) < 10:
        raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
        
    student_data['check_in_count'] -= 10
    await redis.set(redis_key, json.dumps(student_data))
    return Student(**student_data)
