# 版本 4.3 (穩定後端) - 最終加固 get_achievers，正確處理 JSON 字串
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
    return {"message": "運動獎勵計劃 API - 版本 4.3"}

@app.get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    check_redis()
    data = await redis.get(student_id)
    if not isinstance(data, dict):
        # 嘗試從 JSON 字串解析
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")
        else:
            raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")
    return Student(**data)


@app.post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    check_redis()
    data = await redis.get(student_id)
    if not isinstance(data, dict):
         if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")
         else:
            raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")

    data['check_in_count'] += 1
    await redis.set(student_id, json.dumps(data))
    return Student(**data)

@app.post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    check_redis()
    data = await redis.get(student_id)
    if not isinstance(data, dict):
         if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")
         else:
            raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")

    if data.get('check_in_count', 0) < 10:
        raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
    
    data['check_in_count'] -= 10
    await redis.set(student_id, json.dumps(data))
    return Student(**data)

@app.get("/api/achievers", response_model=list[Student])
async def get_achievers():
    check_redis()
    achievers = []
    cursor = 0
    try:
        while True:
            cursor, keys = await redis.scan(cursor, match='[0-9]*')
            if keys:
                for key in keys:
                    raw_data = None
                    try:
                        raw_data = await redis.get(key)
                        
                        student_data = None
                        if isinstance(raw_data, dict):
                            student_data = raw_data
                        elif isinstance(raw_data, str):
                            student_data = json.loads(raw_data)
                        
                        if student_data and student_data.get('check_in_count', 0) >= 10:
                            achievers.append(Student(**student_data))
                            
                    except (json.JSONDecodeError, TypeError) as parse_error:
                        print(f"Skipping key '{key}' due to data format error. Data: {raw_data}. Error: {parse_error}")
                        continue
                    except Exception as inner_error:
                        print(f"Skipping key '{key}' due to unexpected error. Data: {raw_data}. Error: {inner_error}")
                        continue
            if cursor == 0:
                break
                
        achievers.sort(key=lambda s: s.check_in_count, reverse=True)
        return achievers
    except Exception as e:
        print(f"CRITICAL Error in get_achievers function: {e}")
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
            decoded_content = contents.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    
    if decoded_content is None:
        raise HTTPException(status_code=400, detail="無法解碼檔案，請確保檔案為 UTF-8 或 Big5 編碼。")

    reader = csv.DictReader(io.StringIO(decoded_content))
    
    try:
        students = list(reader)
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"CSV 檔案格式錯誤: {e}")

    if not students:
        raise HTTPException(status_code=400, detail="CSV 檔案中沒有找到數據。")

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
            # 確保存入的是 JSON 字串
            pipe.set(record["id"], json.dumps(record))
            imported_count += 1
            
    if imported_count == 0:
        raise HTTPException(status_code=400, detail="檔案中沒有有效的學生數據行。請檢查欄位標題是否為'學號', '姓名', '班別'。")
        
    await pipe.execute()
    return {"message": f"成功匯入 {imported_count} 位學生資料。"}
