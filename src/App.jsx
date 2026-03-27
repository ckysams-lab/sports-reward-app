// 版本 2.0
import React, { useState, useEffect } from 'react';
import Papa from 'papaparse';

// App, StudentView, AmbassadorView 這些組件保持不變，為確保完整性，此處一併提供
function App() {
  const [role, setRole] = useState('學生');
  // ... (App 組件的 JSX 邏輯與之前相同)
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
function StudentView() { /* ... (與之前版本完全相同) ... */ }
function AmbassadorView() { /* ... (與之前版本完全相同) ... */ }


// --- 管理員視圖 (重點修改錯誤處理邏輯) ---
function AdminView() {
    const [achievers, setAchievers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [uploadMessage, setUploadMessage] = useState('');
    const [uploadError, setUploadError] = useState(''); // 新增一個專門的錯誤狀態

    useEffect(() => {
        // ... (與之前版本相同)
    }, []);

    const handleFileChange = (event) => {
        setUploadMessage('');
        setUploadError('');
        setFile(event.target.files[0]);
    };

    // --- 👇 handleUpload 函數是本次修改的核心 ---
    const handleUpload = () => {
        if (!file) {
            setUploadError('請先選擇一個 CSV 檔案');
            return;
        }
        setUploading(true);
        setUploadMessage('解析並上傳中...');
        setUploadError('');

        Papa.parse(file, {
            header: true,
            skipEmptyLines: true,
            complete: async (results) => {
                // ✨ 1. 檢查解析時是否產生錯誤
                if (results.errors.length > 0) {
                    // 將所有解析錯誤訊息格式化為可讀字串
                    const errorDetails = results.errors.map(e => `第 ${e.row} 行: ${e.message}`).join('; ');
                    setUploadError(`檔案格式錯誤: ${errorDetails}`);
                    setUploading(false);
                    return;
                }

                const students = results.data;
                try {
                    // ✨ 2. 檢查是否有成功解析出的數據
                    if (!students || students.length === 0) {
                        throw new Error("CSV 檔案中沒有找到有效的學生數據。");
                    }

                    const response = await fetch('/api/students/batch-import', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(students)
                    });

                    const data = await response.json();
                    if (!response.ok) {
                        // ✨ 3. 如果後端回傳錯誤，顯示後端的錯誤細節
                        throw new Error(data.detail || '上傳失敗，伺服器未提供詳細原因。');
                    }
                    setUploadMessage(data.message); // 顯示成功的訊息
                    
                } catch (err) {
                    // ✨ 4. 捕捉所有類型的錯誤，並顯示 err.message
                    setUploadError(`上傳失敗: ${err.message}`);
                } finally {
                    setUploading(false);
                    setFile(null);
                }
            },
            error: (err) => {
                // 這個是應對更嚴重的、導致整個解析過程崩潰的錯誤
                setUploadError(`檔案解析失敗: ${err.message}`);
                setUploading(false);
            }
        });
    };

    return (
        <div>
            <h2>管理員後台</h2>
            <div style={{ padding: '1rem', border: '1px solid #ddd', borderRadius: '5px', marginBottom: '2rem' }}>
                <h4>
                    匯入學生名單
                    <a href="/template.csv" download="students_template.csv" style={{fontSize: '14px', marginLeft: '1rem', fontWeight: 'normal'}}>
                        (下載 CSV 範本)
                    </a>
                </h4>
                <p>請選擇一個 CSV 檔案。檔案第一行需包含標題：`學號`, `姓名`, `班別`</p>
                <input type="file" accept=".csv" onChange={handleFileChange} disabled={uploading} />
                <button onClick={handleUpload} disabled={uploading || !file} style={{marginTop: '1rem'}}>
                    {uploading ? '上傳中...' : '上傳並匯入'}
                </button>
                {/* 分開顯示成功和失敗的訊息，更清晰 */}
                {uploadMessage && <p style={{color: 'green'}}>{uploadMessage}</p>}
                {uploadError && <p style={{color: 'red'}}>{uploadError}</p>}
            </div>
            
            <h3>已達成獎勵資格名單</h3>
            {loading ? <p>載入中...</p> : (
                <div className="achievers-list">
                    { /* ... (列表的 JSX 渲染邏輯同 1.7) ... */ }
                </div>
            )}
        </div>
    );
}


// 為了確保完整性，StudentView 和 AmbassadorView 也包含在此
function StudentView() {
  const [studentId, setStudentId] = useState('');
  const [studentData, setStudentData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const handleSearch = async () => {
    if (!studentId) {
      setError('請輸入你的學號');
      return;
    }
    setLoading(true);
    setError('');
    setMessage('');
    setStudentData(null);
    try {
      const response = await fetch(`/api/students/${studentId}`);
      if (!response.ok) throw new Error('找不到學生資料');
      const data = await response.json();
      setStudentData(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleRedeem = async () => {
     setLoading(true);
     setError('');
     setMessage('');
     try {
        const response = await fetch(`/api/students/${studentId}/redeem`, { method: 'POST' });
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || '兌換失敗');
        }
        const data = await response.json();
        setStudentData(data);
        setMessage('兌換成功！');
     } catch (err) {
        setError(err.message);
     } finally {
        setLoading(false);
     }
  };

  return (
    <div>
      <h2>學生查詢頁面</h2>
      <input type="text" value={studentId} onChange={(e) => setStudentId(e.target.value)} placeholder="請輸入你的學號" />
      <button onClick={handleSearch} disabled={loading}>{loading ? '查詢中...' : '查詢'}</button>
      
      {error && <p style={{color: 'red'}}>{error}</p>}
      {message && <p style={{color: 'green'}}>{message}</p>}

      {studentData && (
        <div className="student-info">
          <p>你好，<strong>{studentData.name} ({studentData.cls})</strong>！</p>
          <p>你目前的出席記錄為: <strong>{studentData.check_in_count}</strong> 次。</p>
          {studentData.check_in_count >= 10 ? (
            <div>
              <p style={{color: 'green'}}>恭喜！你可以兌換獎勵！</p>
              <button onClick={handleRedeem} disabled={loading}>{loading ? '處理中...' : '點擊兌換'}</button>
            </div>
          ) : (
            <p>再集齊 {10 - studentData.check_in_count} 次就可以兌換獎勵了！</p>
          )}
        </div>
      )}
    </div>
  );
}

function AmbassadorView() {
    const [studentId, setStudentId] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);

    const handleCheckIn = async () => {
        if (!studentId) {
            setResult({error: '請輸入學生學號'});
            return;
        }
        setLoading(true);
        setResult(null);
        try {
            const response = await fetch(`/api/students/${studentId}/check-in`, { method: 'POST' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || '簽到失敗');
            setResult({success: `簽到成功！ ${data.name} 已出席 ${data.check_in_count} 次。`});
        } catch (err) {
            setResult({error: err.message});
        } finally {
            setLoading(false);
        }
    };
    
    return (
        <div>
            <h2>體育大使簽到處</h2>
            <input type="text" value={studentId} onChange={(e) => setStudentId(e.target.value)} placeholder="請輸入要簽到的學生學號" />
            <button onClick={handleCheckIn} disabled={loading}>{loading ? '簽到中...' : '確認簽到'}</button>

            {result && (
                <div className="result">
                    {result.success && <p style={{color: 'green'}}>{result.success}</p>}
                    {result.error && <p style={{color: 'red'}}>{result.error}</p>}
                </div>
            )}
        </div>
    );
}


export default App;

