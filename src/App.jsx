// 版本 6.0 (穩定前端) - 配合後端改動，改為前端篩選達標學生
import React, { useState, useEffect } from 'react';

// =================================================================
// 學生視圖組件
// =================================================================
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

// =================================================================
// 體育大使視圖組件
// =================================================================
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

// =================================================================
// 管理員視圖組件
// =================================================================
function AdminView() {
    const [achievers, setAchievers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [uploadMessage, setUploadMessage] = useState('');
    const [uploadError, setUploadError] = useState('');

    const fetchData = async () => {
        setLoading(true);
        setUploadError(''); 
        try {
            // 呼叫新的 API 接口
            const response = await fetch('/api/all-students'); 
            if (!response.ok) {
              const errData = await response.json();
              throw new Error(errData.detail || '無法獲取學生列表，後端伺服器出錯。');
            }
            const allStudents = await response.json();
            
            // 在前端進行篩選
            const qualifiedStudents = allStudents.filter(student => student.check_in_count >= 10);
            
            setAchievers(qualifiedStudents);

        } catch (err) {
            console.error("獲取列表失敗:", err);
            setUploadError(err.message);
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleFileChange = (event) => {
        setUploadMessage('');
        setUploadError('');
        setFile(event.target.files[0]);
    };

    const handleUpload = async () => {
        if (!file) {
            setUploadError('請先選擇一個 CSV 檔案');
            return;
        }
        setUploading(true);
        setUploadMessage('上傳檔案中...');
        setUploadError('');

        try {
            const formData = new FormData();
            formData.append('file', file);

            const response = await fetch('/api/students/batch-import-file', {
                method: 'POST',
                body: formData,
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.detail || '上傳或處理失敗。');
            }
            setUploadMessage(data.message);
            fetchData(); // 成功上傳後，調用新的 fetchData 函式來刷新列表
        } catch (err) {
            console.error("上傳失敗:", err);
            setUploadError(err.message);
        } finally {
            setUploading(false);
            setFile(null);
            if (document.querySelector('input[type="file"]')) {
                document.querySelector('input[type="file"]').value = '';
            }
        }
    };

    return (
        <div>
            <h2>管理員後台</h2>
            <div style={{ padding: '1rem', border: '1px solid #ddd', borderRadius: '5px', marginBottom: '2rem' }}>
                <h4>
                    匯入學生名單
                    <a href="/template.csv" download="students_template.csv" style={{fontSize: '14px', marginLeft: '1rem', fontWeight: 'normal'}}> (下載 CSV 範本)</a>
                </h4>
                <p>請選擇一個 CSV 檔案。**建議使用 Excel 另存為 "CSV UTF-8" 格式**。</p>
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
// 主應用程式組件
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
