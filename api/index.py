# 版本 4.2 (穩定後端) - 增加啟動時的環境變數日誌，進行最終診斷
from fastapi import FastAPI, HTTPException, UploadFile, File
from upstash_redis import Redis
from pydantic import BaseModel
from typing import List, Optional
import json
import csv
import io
import os # 匯入 os 模組

# =================================================================
# >> 最終診斷日誌 <<
# 在應用程式啟動時，立刻打印環境變數，檢查 Vercel 是否成功載入
# =================================================================
print("--- [DIAGNOSTIC LOG] ---")
upstash_url = os.getenv("UPSTASH_REDIS_REST_URL")
upstash_token = os.getenv("UPSTASH_REDIS_REST_TOKEN")
print(f"Attempting to connect with URL: {upstash_url}")
print(f"Attempting to connect with Token: {'Token is present' if upstash_token else 'Token is NOT FOUND'}")
print("--- [END DIAGNOSTIC LOG] ---")
# =================================================================

# 只有在環境變數看似存在時，才嘗試建立連接
try:
    redis = Redis.from_env()
except Exception as e:
    print(f"CRITICAL: Failed to initialize Redis. Error: {e}")
    # 建立一個假的 redis 物件，讓應用程式可以啟動，但所有 API 都會失敗
    # 這樣我們才能看到上面的日誌
    redis = None

app = FastAPI()

# (此後的所有程式碼，包括 Student 模型和所有 API 接口，都保持不變)
# ... (為了簡潔，此處省略，請保持您現有的版本 4.1 接口程式碼)
# =================================================================
# Pydantic Models
# =================================================================
class Student(BaseModel):
    id: str
    name: str
    cls: str
    check_in_count: int
    last_check_in_date: str

# =================================================================
# API Endpoints
# =================================================================
@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 版本 4.2"}

# 增加一個檢查，如果 redis 初始化失敗，所有接口都返回特定錯誤
def check_redis():
    if redis is None:
        raise HTTPException(status_code=503, detail="後端資料庫連接失敗，請檢查 Vercel 環境變數。")

@app.get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    check_redis()
    data = await redis.get(student_id)
    if not isinstance(data, dict):
        raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")
    return data

@app.post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    check_redis()
    data = await redis.get(student_id)
    if not isinstance(data, dict):
        raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")
    data['check_in_count'] += 1
    await redis.set(student_id, data)
    return data

@app.post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    check_redis()
    data = await redis.get(student_id)
    if not isinstance(data, dict):
        raise HTTPException(status_code=404, detail="找不到該學生或資料格式不正確")
    if data.get('check_in_count', 0) < 10:
        raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
    data['check_in_count'] -= 10
    await redis.set(student_id, data)
    return data

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
                    data = None
                    try:
                        data = await redis.get(key)
                        if isinstance(data, dict) and data.get('check_in_count', 0) >= 10:
                            achievers.append(Student(**data))
                    except Exception as inner_error:
                        print(f"Skipping key '{key}' due to error. Data: {data}. Error: {inner_error}")
                        continue
            if cursor == 0:
                break
        achievers.sort(key=lambda s: s.check_in_count, reverse=True)
        return achievers
    except Exception as e:
        print(f"CRITICAL Error in get_achievers: {e}")
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
            pipe.set(record["id"], json.dumps(record))
            imported_count += 1
    if imported_count == 0:
        raise HTTPException(status_code=400, detail="檔案中沒有有效的學生數據行。請檢查欄位標題是否為'學號', '姓名', '班別'。")
    await pipe.execute()
    return {"message": f"成功匯入 {imported_count} 位學生資料。"}
