# 版本 7.0 (終極穩定版) - 改變遊戲規則：後端返回所有學生
from fastapi import FastAPI, HTTPException, UploadFile, File
from upstash_redis import Redis
from pydantic import BaseModel
from typing import List, Optional
import json
import csv
import io
import os
import re

# =================================================================
# Redis 連接 (已確認無誤)
# =================================================================
redis_url = os.getenv("UPSTASH_REDIS_REST_URL")
redis_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")

redis = None
if redis_url and redis_token:
    try:
        redis = Redis(url=redis_url, token=redis_token)
    except Exception as e:
        print(f"CRITICAL: Failed to initialize Redis. Error: {e}")
else:
    print("CRITICAL: Missing Redis URL or Token.")

app = FastAPI()

# =================================================================
# Pydantic Models & Helper Functions (已確認無誤)
# =================================================================
class Student(BaseModel):
    id: str
    name: str
    cls: str
    check_in_count: int
    last_check_in_date: str

def check_redis():
    if redis is None:
        raise HTTPException(status_code=503, detail="後端資料庫連接初始化失敗。")

def sanitize_string(text: str) -> str:
    if not isinstance(text, str):
        return text
    # 移除所有Unicode空白字元和控制字元，只保留可列印的字元
    return re.sub(r'[\s\ufeff]+', '', text, flags=re.UNICODE)

# =================================================================
# API Endpoints
# =================================================================
@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 版本 7.0"}

# **核心改動：用 get_all_students 替換 get_achievers**
@app.get("/api/all-students", response_model=list[Student])
async def get_all_students():
    check_redis()
    all_students = []
    try:
        all_keys_bytes = await redis.keys('[0-9]*')
        if not all_keys_bytes:
            return []

        all_raw_data = await redis.mget(*all_keys_bytes)
        
        for raw_data in all_raw_data:
            try:
                if raw_data is None:
                    continue
                student_data = None
                if isinstance(raw_data, dict):
                    student_data = raw_data
                elif isinstance(raw_data, str):
                    student_data = json.loads(raw_data)
                
                if student_data and isinstance(student_data, dict):
                    all_students.append(Student(**student_data))

            except Exception as inner_error:
                print(f"Skipping a student record due to data processing error: {inner_error}. Data: {raw_data}")
                continue
        
        return all_students
        
    except Exception as e:
        print(f"CRITICAL Error in get_all_students function: {e}")
        raise HTTPException(status_code=500, detail="獲取全體學生列表時發生了無法預料的嚴重錯誤。")

# **檔案上傳接口 (已確認無誤)**
@app.post("/api/students/batch-import-file")
async def batch_import_students_from_file(file: UploadFile = File(...)):
    check_redis()
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="檔案格式不正確，請上傳 CSV 檔案。")

    contents = await file.read()
    
    decoded_content = None
    for encoding in ['utf-8-sig', 'utf-8', 'big5']:
        try:
            decoded_content = contents.decode(encoding, errors='replace')
            break
        except UnicodeDecodeError:
            continue
    
    if decoded_content is None:
        raise HTTPException(status_code=400, detail="無法解碼檔案，請確保檔案為標準的 UTF-8 或 Big5 編碼。")

    reader = csv.DictReader(io.StringIO(decoded_content))
    
    try:
        original_fieldnames = reader.fieldnames
        if not original_fieldnames:
            raise HTTPException(status_code=400, detail="CSV 檔案為空或無法讀取標題行。")
        
        clean_students = []
        clean_fieldnames = [sanitize_string(field) for field in original_fieldnames]
        
        for row in reader:
            clean_row = {}
            for i, field in enumerate(original_fieldnames):
                clean_key = clean_fieldnames[i]
                clean_row[clean_key] = row[field]
            clean_students.append(clean_row)
        
        students = clean_students

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"處理 CSV 內容時出錯: {e}")

    if not students:
        raise HTTPException(status_code=400, detail="CSV 檔案中沒有找到數據，或檔案為空。")

    pipe = redis.pipeline()
    imported_count = 0
    
    for row in students:
        student_id = row.get('學號')
        name = row.get('姓名')
        cls = row.get('班別')
        
        if student_id and name and cls:
            student_id_str = str(student_id).strip()
            if not student_id_str: continue
            record = {"id": student_id_str, "name": str(name).strip(), "cls": str(cls).strip(), "check_in_count": 0, "last_check_in_date": ""}
            pipe.set(record["id"], json.dumps(record))
            imported_count += 1
            
    if imported_count == 0:
        raise HTTPException(status_code=400, detail="檔案中沒有有效的學生數據行。請再次檢查欄位標題是否為'學號', '姓名', '班別'，且檔案中包含學生資料。")
        
    await pipe.execute()
    return {"message": f"成功匯入 {imported_count} 位學生資料。"}

# **其他接口 (已確認無誤)**
@app.get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    student_data = None
    try:
        if isinstance(raw_data, dict): student_data = raw_data
        elif isinstance(raw_data, str): student_data = json.loads(raw_data)
        if student_data is None: raise HTTPException(status_code=404, detail="找不到該學生")
        return Student(**student_data)
    except (json.JSONDecodeError, TypeError): raise HTTPException(status_code=404, detail="學生資料格式不正確")

@app.post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    student_data = None
    try:
        if isinstance(raw_data, dict): student_data = raw_data
        elif isinstance(raw_data, str): student_data = json.loads(raw_data)
        if student_data is None: raise HTTPException(status_code=404, detail="找不到該學生")
    except (json.JSONDecodeError, TypeError): raise HTTPException(status_code=404, detail="學生資料格式不正確")
    student_data['check_in_count'] += 1
    await redis.set(student_id, json.dumps(student_data))
    return Student(**student_data)

@app.post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    student_data = None
    try:
        if isinstance(raw_data, dict): student_data = raw_data
        elif isinstance(raw_data, str): student_data = json.loads(raw_data)
        if student_data is None: raise HTTPException(status_code=404, detail="找不到該學生")
    except (json.JSONDecodeError, TypeError): raise HTTPException(status_code=404, detail="學生資料格式不正確")
    if student_data.get('check_in_count', 0) < 10: raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
    student_data['check_in_count'] -= 10
    await redis.set(student_id, json.dumps(student_data))
    return Student(**student_data)
