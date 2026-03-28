import os
import json
import csv
import io
from fastapi import FastAPI, HTTPException, UploadFile, File
from pydantic import BaseModel
from typing import List

# 必須匯入 asyncio 版本的 Redis
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
# API Endpoints
# =================================================================
@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 完美運行中"}

@app.get("/api/all-students", response_model=list[Student])
async def get_all_students():
    check_redis()
    all_students = []
    try:
        all_keys = await redis.keys('[0-9]*')
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
            
            if student_data and isinstance(student_data, dict):
                all_students.append(Student(**student_data))
                
        return all_students
        
    except Exception as e:
        print(f"CRITICAL Error in get_all_students: {e}")
        raise HTTPException(status_code=500, detail="獲取全體學生列表時發生錯誤。")

# >> 核心大改版：超強容錯與透視鏡匯入機制 <<
@app.post("/api/students/batch-import-file")
async def batch_import_students_from_file(file: UploadFile = File(...)):
    check_redis()
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="請上傳 CSV 檔案。")

    contents = await file.read()
    
    # 1. 解碼邏輯：確保無論如何都能轉為字串
    decoded_content = None
    for encoding in ['utf-8-sig', 'utf-8', 'big5', 'gbk']:
        try:
            decoded_content = contents.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
            
    if decoded_content is None:
        decoded_content = contents.decode('utf-8-sig', errors='replace')

    # 2. 自動偵測分隔符號 (解決 Mac/Excel 產生 Tab 或分號的問題)
    try:
        dialect = csv.Sniffer().sniff(decoded_content[:1024])
        reader = csv.reader(io.StringIO(decoded_content), dialect)
    except Exception:
        # 偵測失敗則退回預設的逗號分隔
        reader = csv.reader(io.StringIO(decoded_content))
    
    try:
        rows = list(reader)
    except csv.Error as e:
        raise HTTPException(status_code=400, detail=f"CSV 解析錯誤: {e}")

    if not rows or len(rows) < 2:
        raise HTTPException(status_code=400, detail="檔案為空或只有標題行，沒有學生資料。")

    # 3. 獲取並清理標題行 (移除 BOM 與前後空白)
    headers = [str(h).replace('\ufeff', '').strip() for h in rows[0]]
    
    id_idx = name_idx = cls_idx = -1
    
    # 4. 模糊比對尋找欄位 (超強容錯)
    for i, header in enumerate(headers):
        if '學號' in header or 'id' in header.lower(): id_idx = i
        elif '姓名' in header or 'name' in header.lower(): name_idx = i
        elif '班別' in header or 'class' in header.lower() or 'cls' in header.lower(): cls_idx = i
        
    # 5. 透視鏡機制：如果還是找不到，把後端看到的真實情況吐給前端！
    if id_idx == -1 or name_idx == -1 or cls_idx == -1:
        raise HTTPException(
            status_code=400, 
            detail=f"找不到對應的欄位。必須包含'學號', '姓名', '班別'。\n後端實際讀取到的標題為: {headers}"
        )

    pipe = redis.pipeline()
    imported_count = 0
    
    # 6. 開始匯入資料
    for i in range(1, len(rows)):
        row = rows[i]
        if not row or len(row) == 0:
            continue
            
        student_id = row[id_idx] if id_idx < len(row) else ""
        name = row[name_idx] if name_idx < len(row) else ""
        cls = row[cls_idx] if cls_idx < len(row) else ""
        
        student_id_str = str(student_id).strip()
        name_str = str(name).strip()
        cls_str = str(cls).strip()
        
        if student_id_str and name_str and cls_str:
            record = {
                "id": student_id_str, 
                "name": name_str, 
                "cls": cls_str, 
                "check_in_count": 0, 
                "last_check_in_date": ""
            }
            pipe.set(record["id"], json.dumps(record))
            imported_count += 1
            
    if imported_count == 0:
        sample_data = rows[1] if len(rows) > 1 else "無"
        raise HTTPException(
            status_code=400, 
            detail=f"標題正確，但沒有匯入任何資料。第一行資料解析為: {sample_data}"
        )
        
    await pipe.execute()
    return {"message": f"成功匯入 {imported_count} 位學生資料。"}

@app.get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    if not raw_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    student_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    return Student(**student_data)

@app.post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    if not raw_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    student_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    student_data['check_in_count'] += 1
    await redis.set(student_id, json.dumps(student_data))
    return Student(**student_data)

@app.post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    if not raw_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    student_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    if student_data.get('check_in_count', 0) < 10:
        raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
    student_data['check_in_count'] -= 10
    await redis.set(student_id, json.dumps(student_data))
    return Student(**student_data)
    if redis is None:
        raise HTTPException(status_code=503, detail="後端資料庫連接初始化失敗。")

def sanitize_string(text: str) -> str:
    if not isinstance(text, str):
        return text
    # 清除 BOM 及所有空白字元
    return re.sub(r'[\s\ufeff]+', '', text, flags=re.UNICODE)

# =================================================================
# API Endpoints
# =================================================================
@app.get("/api")
def handle_root():
    return {"message": "運動獎勵計劃 API - 完美運行中"}

@app.get("/api/all-students", response_model=list[Student])
async def get_all_students():
    check_redis()
    all_students = []
    try:
        # 現在使用 async redis，await 絕對安全！
        all_keys = await redis.keys('[0-9]*')
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
            
            if student_data and isinstance(student_data, dict):
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
    
    # >> 修正解碼邏輯：先嚴格，後寬容 <<
    decoded_content = None
    for encoding in ['utf-8-sig', 'utf-8', 'big5']:
        try:
            decoded_content = contents.decode(encoding) # 嚴格模式
            break
        except UnicodeDecodeError:
            continue
            
    if decoded_content is None:
        # 如果都失敗，強制用 utf-8-sig 寬容解碼挽救資料
        decoded_content = contents.decode('utf-8-sig', errors='replace')

    reader = csv.DictReader(io.StringIO(decoded_content))
    
    try:
        original_fieldnames = reader.fieldnames
        if not original_fieldnames:
            raise HTTPException(status_code=400, detail="CSV 檔案為空或無法讀取標題。")
        
        clean_fieldnames = [sanitize_string(field) for field in original_fieldnames]
        
        students = []
        for row in reader:
            clean_row = {}
            # >> 修正欄位對齊邏輯：確保 100% 準確匹配 <<
            for original_col, clean_col in zip(original_fieldnames, clean_fieldnames):
                clean_row[clean_col] = row.get(original_col)
            students.append(clean_row)

    except Exception as e:
        raise HTTPException(status_code=400, detail=f"處理 CSV 內容時出錯: {e}")

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

@app.get("/api/students/{student_id}", response_model=Student)
async def get_student(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    if not raw_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    student_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    return Student(**student_data)

@app.post("/api/students/{student_id}/check-in", response_model=Student)
async def check_in(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    if not raw_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    student_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    student_data['check_in_count'] += 1
    await redis.set(student_id, json.dumps(student_data))
    return Student(**student_data)

@app.post("/api/students/{student_id}/redeem", response_model=Student)
async def redeem_reward(student_id: str):
    check_redis()
    raw_data = await redis.get(student_id)
    if not raw_data:
        raise HTTPException(status_code=404, detail="找不到該學生")
    student_data = json.loads(raw_data) if isinstance(raw_data, str) else raw_data
    if student_data.get('check_in_count', 0) < 10:
        raise HTTPException(status_code=400, detail="出席次數不足，無法兌換")
    student_data['check_in_count'] -= 10
    await redis.set(student_id, json.dumps(student_data))
    return Student(**student_data)
