// 版本 3.4 (穩定前端) - 替換 jschardet 為 chardet 並最終修復
import React, { useState, useEffect } from 'react';
import Papa from 'papaparse';
// **FIX: VERSION 3.4 - 替換為更可靠的 chardet 函式庫**
import chardet from 'chardet';

// (學生視圖組件 和 體育大使視圖組件 的程式碼保持不變，此處省略)
// ...

// =================================================================
// 管理員視圖組件 (*** 主要修改區域 ***)
// =================================================================
function AdminView() {
    const [achievers, setAchievers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [uploadMessage, setUploadMessage] = useState('');
    const [uploadError, setUploadError] = useState('');

    useEffect(() => {
        const fetchAchievers = async () => {
            setLoading(true);
            try {
                const response = await fetch('/api/achievers');
                if (!response.ok) {
                  throw new Error('無法獲取列表，後端伺服器出錯。');
                }
                const data = await response.json();
                setAchievers(data);
            } catch (err) {
                console.error("獲取列表失敗:", err);
                setUploadError(err.message);
            } finally {
                setLoading(false);
            }
        };
        fetchAchievers();
    }, []);

    const handleFileChange = (event) => {
        setUploadMessage('');
        setUploadError('');
        setFile(event.target.files[0]);
    };

    const handleError = (errorSource, errorObject) => {
        console.error(`[${errorSource}] 捕獲到錯誤:`, errorObject);
        let errorMessage = "發生未知錯誤。";
        if (errorObject instanceof Error) {
            errorMessage = errorObject.message;
        } else if (typeof errorObject === 'string') {
            errorMessage = errorObject;
        } else {
            errorMessage = JSON.stringify(errorObject);
        }
        setUploadError(`[${errorSource}] ${errorMessage}`);
    };

    const handleUpload = () => {
        if (!file) {
            setUploadError('請先選擇一個 CSV 檔案');
            return;
        }
        setUploading(true);
        setUploadMessage('偵測檔案編碼並解碼中...');
        setUploadError('');

        const reader = new FileReader();
        reader.onload = function(event) {
            try {
                const buffer = event.target.result;
                const uint8array = new Uint8Array(buffer);

                // **FIX: VERSION 3.4 - 使用 chardet.detect()**
                // chardet 需要 Buffer，我們從 Uint8Array 創建它
                const encoding = chardet.detect(Buffer.from(uint8array));
                
                if (!encoding) {
                    throw new Error("無法偵測檔案編碼，請確保檔案為 UTF-8 或 Big5。");
                }
                
                console.log(`偵測到的檔案編碼: ${encoding}`);
                setUploadMessage(`偵測到編碼為 ${encoding}，開始解碼...`);
                
                const decoder = new TextDecoder(encoding);
                const decodedString = decoder.decode(uint8array);

                setUploadMessage('解碼完成，開始解析數據...');
                
                Papa.parse(decodedString, {
                    header: true,
                    skipEmptyLines: true,
                    complete: async (results) => {
                        try {
                            if (results.errors.length > 0) {
                                const errorDetails = results.errors.map(e => `第 ${e.row} 行: ${e.code} - ${e.message}`).join('; ');
                                throw new Error(`檔案格式錯誤: ${errorDetails}`);
                            }
                            if (!results.data || results.data.length === 0) {
                                throw new Error("CSV 檔案中沒有找到有效的學生數據。");
                            }
                            const response = await fetch('/api/students/batch-import', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify(results.data)
                            });
                            const data = await response.json();
                            if (!response.ok) {
                                throw new Error(data.detail || '上傳失敗，伺服器未提供詳細原因。');
                            }
                            setUploadMessage(data.message);
                        } catch (err) {
                            handleError('CompleteCallback', err);
                        }
                    },
                    error: (err) => { handleError('PapaParse', err); }
                });
            } catch (err) {
                handleError('FileReader/Chardet', err);
            } finally {
                setUploading(false);
                setFile(null);
            }
        };
        reader.onerror = function(err) {
            handleError('FileReader', err);
            setUploading(false);
        };
        reader.readAsArrayBuffer(file);
    };

    return (
        <div>
            <h2>管理員後台</h2>
            <div style={{ padding: '1rem', border: '1px solid #ddd', borderRadius: '5px', marginBottom: '2rem' }}>
                <h4>
                    匯入學生名單
                    <a href="/template.csv" download="students_template.csv" style={{fontSize: '14px', marginLeft: '1rem', fontWeight: 'normal'}}> (下載 CSV 範本)</a>
                </h4>
                <p>請選擇一個 CSV 檔案 (系統會自動嘗試偵測 UTF-8 或 Big5 編碼)。</p>
                <input type="file" accept=".csv" onChange={handleFileChange} disabled={uploading} />
                <button onClick={handleUpload} disabled={uploading || !file} style={{marginTop: '1rem'}}>{uploading ? '處理中...' : '上傳並匯入'}</button>
                {uploadMessage && <p style={{color: 'green'}}>{uploadMessage}</p>}
                {uploadError && <p style={{color: 'red'}}>{uploadError}</p>}
            </div>
            <h3>已達成獎勵資格名單</h3>
            {loading ? <p>載入中...</p> : (
                <div className="achievers-list">
                    <table>
                        <thead>
                            <tr><th>學號</th><th>姓名</th><th>班別</th><th>出席次數</th></tr>
                        </thead>
                        <tbody>
                            {achievers.length > 0 ? achievers.map(s => (
                                <tr key={s.id}>
                                    <td>{s.id}</td>
                                    <td>{s.name}</td>
                                    <td>{s.cls}</td>
                                    <td>{s.check_in_count}</td>
                                </tr>
                            )) : (
                                <tr><td colSpan="4" style={{textAlign: 'center', padding: '1rem'}}>目前沒有學生達成資格</td></tr>
                            )}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
}

// =================================================================
// 主應用程式組件 (此處代碼未變更)
// =================================================================
function App() {
  const [role, setRole] = useState('學生');

  return (
    <div className="App">
      <h1>🏅 運動獎勵計劃</h1>
      <div className="role-selector">
        <button onClick={() => setRole('學生')} className={role === '學生' ? 'active' : ''}>學生</button>
        <button onClick={() => setRole('體育大使')} className={role === '體育大使' ? 'active' : ''}>體育大使</button>
        <button onClick={() => setRole('管理員')} className={role === '管理員' ? 'active' : ''}>管理員</button>
      </div>
      <hr />
      {role === '學生' && <StudentView />}
      {role === '體育大使' && <AmbassadorView />}
      {role === '管理員' && <AdminView />}
    </div>
  );
}

export default App;
