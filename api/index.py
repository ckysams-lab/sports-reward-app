# 版本 4.5 (穩定後端) - 終極方案：在 decode 時忽略錯誤，確保檔案一定能被讀取
from fastapi import FastAPI, HTTPException, UploadFile, File
from upstash_redis import Redis
from pydantic import BaseModel
from typing import List, Optional
import json
import csv
import io
import os

# =================================================================
# 診斷日誌與 Redis 初始化
# =================================================================
print("--- [DIAGNOSTIC LOG] ---")
upstash_url = os.getenv("UPSTASH_REDIS_REST_URL")
upstash_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
print(f"URL from env: {upstash_url}")
print(f"Token from env: {'Exists' if upstash_token else 'NOT FOUND'}")
print("--- [END DIAGNOSTIC LOG] ---")

try:
    redis = Redis.from_env()
except Exception as e:
    print(f"CRITICAL: Failed to initialize Redis from env. Error: {e}")
    redis = None

app = FastAPI()

# =================================================================
# Pydantic Models & Helper Functions
# =================================================================
class Student(BaseModel):
    id: str
    name: str
    cls: str
    check_in_count: int
    last_check_in_date: str

def check_redis():
    if redis is None:
        raise HTTPException(status_code=503, detail="後端資料庫連接初始化失敗，請檢查 Vercel 環境變數。")

# =================================================================
# API Endpoints
# =================================================================
@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 版本 4.5"}

@app.get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    student_data = None
    try:
        if isinstance(raw_data, dict):
            student_data = raw_data
        elif isinstance(raw_data, str):
            student_data = json.loads(raw_data)
        
        if student_data is None:
            raise HTTPException(status_code=404, detail="找不到該學生")
            
        return Student(**student_data)
    except (json.JSONDecodeError, TypeError):
         raise HTTPException(status_code=404, detail="學生資料格式不正確")


@app.post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    student_data = None
    try:
        if isinstance(raw_data, dict):
            student_data = raw_data
        elif isinstance(raw_data, str):
            student_data = json.loads(raw_data)

        if student_data is None:
            raise HTTPException(status_code=404, detail="找不到該學生")
    except (json.JSONDecodeError, TypeError):
         raise HTTPException(status_code=404, detail="學生資料格式不正確")

    student_data['check_in_count'] += 1
    await redis.set(student_id, json.dumps(student_data))
    return Student(**student_data)

@app.post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    student_data = None
    try:
        if isinstance(raw_data, dict):
            student_data = raw_data
        elif isinstance(raw_data, str):
            student_data = json.loads(raw_data)

        if student_data is None:
            raise HTTPException(status_code=404, detail="找不到該學生")
    except (json.JSONDecodeError, TypeError):
         raise HTTPException(status_code=404, detail="學生資料格式不正確")

    if student_data.get('check_in_count', 0) < 10:
        raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
    
    student_data['check_in_count'] -= 10
    await redis.set(student_id, json.dumps(student_data))
    return Student(**student_data)

@app.get("/api/achievers", response_model=list[Student])
async def get_achievers():
    check_redis()
    achievers = []
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
                
                if student_data and student_data.get('check_in_count', 0) >= 10:
                    achievers.append(Student(**student_data))

            except Exception as inner_error:
                print(f"Skipping a record due to data processing error: {inner_error}. Data: {raw_data}")
                continue
        
        achievers.sort(key=lambda s: s.check_in_count, reverse=True)
        return achievers
        
    except Exception as e:
        print(f"CRITICAL Error in get_achievers (keys/mget strategy): {e}")
        raise HTTPException(status_code=500, detail="獲取列表時發生嚴重的內部錯誤")

@app.post("/api/students/batch-import-file")
async def batch_import_students_from_file(file: UploadFile = File(...)):
    check_redis()
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="檔案格式不正確，請上傳 CSV 檔案。")

    contents = await file.read()
    
    decoded_content = None
    for encoding in ['utf-8', 'big5', 'utf-8-sig']:
        try:
            # 核心修正：增加 errors='replace'，確保解碼一定成功
            decoded_content = contents.decode(encoding, errors='replace')
            print(f"Successfully decoded file with encoding: {encoding}")
            break
        except Exception:
            continue
    
    if decoded_content is None:
        raise HTTPException(status_code=500, detail="伺服器發生未知的檔案讀取錯誤。")

    reader = csv.DictReader(io.StringIO(decoded_content))
    
    try:
        students = list(reader)
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"CSV 檔案格式錯誤: {e}")

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
        raise HTTPException(status_code=400, detail="檔案中沒有有效的學生數據行。請檢查欄位標題是否為'學號', '姓名', '班別'。")
        
    await pipe.execute()
    return {"message": f"成功匯入 {imported_count} 位學生資料。"}
