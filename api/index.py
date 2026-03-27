# 版本 5.1 (終極穩定版) - 清理CSV標題前後的空格，徹底解決欄位匹配問題
from fastapi import FastAPI, HTTPException, UploadFile, File
from upstash_redis import Redis
from pydantic import BaseModel
from typing import List, Optional
import json
import csv
import io
import os

# (Redis 連接, Pydantic 模型, Helper 函式都已確認無誤)
# ...
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
class Student(BaseModel):
    id: str; name: str; cls: str; check_in_count: int; last_check_in_date: str
def check_redis():
    if redis is None: raise HTTPException(status_code=503, detail="後端資料庫連接初始化失敗。")

# =================================================================
# API Endpoints
# =================================================================
@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 版本 5.1"}

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
    
    # >> 核心修正：手動清理欄位標題 (fieldnames) 的前後空格 <<
    try:
        reader.fieldnames = [field.strip() for field in reader.fieldnames]
    except Exception as e:
        # 如果 reader.fieldnames 是 None (例如檔案是空的)，這裡可能會出錯
        raise HTTPException(status_code=400, detail=f"讀取 CSV 欄位標題時出錯: {e}")

    try:
        students = list(reader)
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"CSV 檔案內容格式錯誤: {e}")

    if not students:
        raise HTTPException(status_code=400, detail="CSV 檔案中沒有找到數據，或檔案為空。")

    pipe = redis.pipeline()
    imported_count = 0
    
    for row in students:
        # 現在，即使原始標題是 " 學號 "，row.get('學號') 也能正確工作
        student_id = row.get('學號')
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
            pipe.set(record["id"], json.dumps(record))
            imported_count += 1
            
    if imported_count == 0:
        raise HTTPException(status_code=400, detail="檔案中沒有有效的學生數據行。請再次檢查欄位標題是否為'學號', '姓名', '班別'，且檔案中包含學生資料。")
        
    await pipe.execute()
    return {"message": f"成功匯入 {imported_count} 位學生資料。"}

# (此後的其他接口，都與版本 5.0 保持一致，已確認無誤)
@app.get("/api/achievers", response_model=list[Student])
async def get_achievers():
    check_redis()
    achievers = []
    try:
        all_keys_bytes = await redis.keys('[0-9]*')
        if not all_keys_bytes: return []
        all_raw_data = await redis.mget(*all_keys_bytes)
        for raw_data in all_raw_data:
            try:
                if raw_data is None: continue
                student_data = None
                if isinstance(raw_data, dict): student_data = raw_data
                elif isinstance(raw_data, str): student_data = json.loads(raw_data)
                if student_data and isinstance(student_data, dict) and student_data.get('check_in_count', 0) >= 10:
                    achievers.append(Student(**student_data))
            except Exception as inner_error:
                print(f"Skipping a record due to processing error: {inner_error}. Data: {raw_data}")
                continue
        achievers.sort(key=lambda s: s.check_in_count, reverse=True)
        return achievers
    except Exception as e:
        print(f"CRITICAL Error in get_achievers function: {e}")
        raise HTTPException(status_code=500, detail="獲取列表時發生了無法預料的嚴重錯誤。")

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
