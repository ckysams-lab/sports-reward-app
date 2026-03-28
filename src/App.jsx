import React, { useState, useEffect } from 'react';

// =================================================================
// 學生視圖組件 (✨ 加入全新視覺化集印卡)
// =================================================================
function StudentView() {
  const [cls, setCls] = useState('');
  const [studentId, setStudentId] = useState('');
  const [studentData, setStudentData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');

  const handleSearch = async () => {
    if (!cls.trim() || !studentId.trim()) {
      setError('請輸入完整的班別及學號');
      return;
    }
    setLoading(true);
    setError('');
    setMessage('');
    setStudentData(null);
    try {
      const response = await fetch(`/api/students/${cls.trim()}/${studentId.trim()}`);
      if (!response.ok) {
          const errData = await response.json();
          throw new Error(errData.detail || '找不到學生資料');
      }
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
        const response = await fetch(`/api/students/${cls.trim()}/${studentId.trim()}/redeem`, { method: 'POST' });
        if (!response.ok) {
            const errData = await response.json();
            throw new Error(errData.detail || '兌換失敗');
        }
        const data = await response.json();
        setStudentData(data);
        setMessage('🎉 兌換成功！你的印花已扣除 10 個，獎勵已發放！');
     } catch (err) {
        setError(err.message);
     } finally {
        setLoading(false);
     }
  };

  return (
    <div>
      <h2>🧑‍🎓 學生查詢頁面</h2>
      <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
          <input type="text" value={cls} onChange={(e) => setCls(e.target.value.toUpperCase())} placeholder="班別 (如: 1A)" style={{ flex: 1, padding: '10px', borderRadius: '5px', border: '1px solid #ccc' }} />
          <input type="number" value={studentId} onChange={(e) => setStudentId(e.target.value)} placeholder="學號 (如: 1)" style={{ flex: 1, padding: '10px', borderRadius: '5px', border: '1px solid #ccc' }} />
      </div>
      <button onClick={handleSearch} disabled={loading} style={{ width: '100%', padding: '12px', backgroundColor: '#0066cc', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', fontWeight: 'bold', fontSize: '16px' }}>
          {loading ? '查詢中...' : '🔍 查詢我的印花'}
      </button>
      
      {error && <p style={{color: 'red', fontWeight: 'bold', marginTop: '10px'}}>{error}</p>}
      {message && <p style={{color: 'green', fontWeight: 'bold', marginTop: '10px'}}>{message}</p>}
      
      {studentData && (
        <div style={{ marginTop: '25px' }}>
          <p style={{ fontSize: '18px', textAlign: 'center' }}>
            你好，<strong>{studentData.name} ({studentData.cls}班 {studentData.id}號)</strong>！
          </p>
          
          {/* ✨ 視覺化集印卡 UI ✨ */}
          <div style={{
              backgroundColor: '#fff9c4', // 暖色系卡片背景
              padding: '20px',
              borderRadius: '15px',
              boxShadow: '0 6px 12px rgba(0,0,0,0.1)',
              textAlign: 'center',
              border: '2px solid #fbc02d'
          }}>
              <h3 style={{ margin: '0 0 15px 0', color: '#f57f17' }}>🏅 運動專屬集印卡 🏅</h3>
              
              <div style={{ display: 'flex', flexWrap: 'wrap', justifyContent: 'center', gap: '12px', marginBottom: '15px' }}>
                  {/* 產生 10 個印花格子 */}
                  {[...Array(10)].map((_, index) => {
                      // 判斷這個格子是否已經集到印花
                      const isStamped = index < studentData.check_in_count;
                      return (
                          <div key={index} style={{
                              width: '50px', 
                              height: '50px', 
                              borderRadius: '50%',
                              backgroundColor: isStamped ? '#ffca28' : '#ffffff',
                              border: isStamped ? '2px solid #ff9800' : '2px dashed #bdbdbd',
                              display: 'flex', 
                              alignItems: 'center', 
                              justifyContent: 'center',
                              fontSize: '28px', 
                              transition: 'all 0.3s ease',
                              boxShadow: isStamped ? '0 2px 5px rgba(0,0,0,0.2)' : 'none'
                          }}>
                              {isStamped ? '⭐' : ''}
                          </div>
                      );
                  })}
              </div>
              
              <p style={{ color: '#555', fontWeight: 'bold', margin: '10px 0' }}>
                  目前共有：<span style={{ color: '#d84315', fontSize: '20px' }}>{studentData.check_in_count}</span> 個印花
              </p>

              {/* 兌換邏輯 */}
              {studentData.check_in_count >= 10 ? (
                <div style={{ marginTop: '20px', padding: '10px', backgroundColor: '#e8f5e9', borderRadius: '10px', border: '1px solid #81c784' }}>
                  <p style={{color: '#2e7d32', fontWeight: 'bold', fontSize: '18px', margin: '0 0 10px 0'}}>🎉 恭喜集滿 10 個印花！</p>
                  <button onClick={handleRedeem} disabled={loading} style={{ padding: '12px 24px', backgroundColor: '#4caf50', color: 'white', border: 'none', borderRadius: '30px', cursor: 'pointer', fontWeight: 'bold', fontSize: '16px', boxShadow: '0 4px 6px rgba(0,0,0,0.2)' }}>
                      {loading ? '處理中...' : '🎁 點擊兌換獎勵'}
                  </button>
                </div>
              ) : (
                <p style={{ color: '#795548', marginTop: '15px' }}>
                  再集齊 <strong>{10 - studentData.check_in_count}</strong> 次就可以兌換獎勵了！加油！🏃‍♂️💨
                </p>
              )}
          </div>
        </div>
      )}
    </div>
  );
}

// =================================================================
// 體育大使視圖組件 (保持不變)
// =================================================================
function AmbassadorView() {
    const [cls, setCls] = useState('');
    const [studentId, setStudentId] = useState('');
    const [loading, setLoading] = useState(false);
    const [result, setResult] = useState(null);

    const handleCheckIn = async () => {
        if (!cls.trim() || !studentId.trim()) {
            setResult({error: '請輸入完整的班別及學號'});
            return;
        }
        setLoading(true);
        setResult(null);
        try {
            const response = await fetch(`/api/students/${cls.trim()}/${studentId.trim()}/check-in`, { method: 'POST' });
            const data = await response.json();
            if (!response.ok) throw new Error(data.detail || '簽到失敗');
            setResult({success: `✅ 簽到成功！ ${data.name} (${data.cls}) 目前已出席 ${data.check_in_count} 次。`});
            setStudentId(''); 
        } catch (err) {
            setResult({error: `❌ 簽到失敗: ${err.message}`});
        } finally {
            setLoading(false);
        }
    };
    
    return (
        <div>
            <h2>📝 體育大使簽到處</h2>
            <div style={{ display: 'flex', gap: '10px', marginBottom: '10px' }}>
                <input type="text" value={cls} onChange={(e) => setCls(e.target.value.toUpperCase())} placeholder="班別 (如: 1A)" style={{ flex: 1, padding: '10px', borderRadius: '5px', border: '1px solid #ccc' }} />
                <input type="number" value={studentId} onChange={(e) => setStudentId(e.target.value)} placeholder="學號 (如: 1)" style={{ flex: 1, padding: '10px', borderRadius: '5px', border: '1px solid #ccc' }} />
            </div>
            <button onClick={handleCheckIn} disabled={loading} style={{ width: '100%', padding: '12px', backgroundColor: '#e65100', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', fontWeight: 'bold', fontSize: '16px' }}>
                {loading ? '簽到處理中...' : '✅ 確認簽到'}
            </button>
            
            {result && (
                <div className="result" style={{ marginTop: '20px', padding: '15px', borderRadius: '8px', backgroundColor: result.success ? '#e8f5e9' : '#ffebee' }}>
                    {result.success && <p style={{color: '#2e7d32', margin: 0, fontWeight: 'bold'}}>{result.success}</p>}
                    {result.error && <p style={{color: '#c62828', margin: 0, fontWeight: 'bold'}}>{result.error}</p>}
                </div>
            )}
        </div>
    );
}

// =================================================================
// 管理員視圖組件 (保持不變)
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
            const response = await fetch('/api/all-students'); 
            if (!response.ok) {
              const errData = await response.json();
              throw new Error(errData.detail || '無法獲取學生列表，後端伺服器出錯。');
            }
            const allStudents = await response.json();
            const qualifiedStudents = allStudents.filter(student => student.check_in_count >= 10);
            qualifiedStudents.sort((a, b) => {
                if (a.cls !== b.cls) return a.cls.localeCompare(b.cls);
                return parseInt(a.id) - parseInt(b.id);
            });
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
            fetchData(); 
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
            <h2>⚙️ 管理員後台</h2>
            <div style={{ padding: '1rem', border: '1px solid #ddd', borderRadius: '5px', marginBottom: '2rem', backgroundColor: '#f9f9f9' }}>
                <h4 style={{ marginTop: 0 }}>
                    📥 匯入學生名單
                    <a href="/template.csv" download="students_template.csv" style={{fontSize: '14px', marginLeft: '1rem', fontWeight: 'normal', color: '#0066cc'}}> (下載 CSV 範本)</a>
                </h4>
                <p style={{ fontSize: '14px', color: '#555' }}>請選擇一個 CSV 檔案。系統會自動重新整理資料庫中對應班別與學號的紀錄。</p>
                <input type="file" accept=".csv" onChange={handleFileChange} disabled={uploading} style={{ marginBottom: '10px' }}/>
                <button onClick={handleUpload} disabled={uploading || !file} style={{ width: '100%', padding: '10px', backgroundColor: '#424242', color: 'white', border: 'none', borderRadius: '5px', cursor: 'pointer', fontWeight: 'bold' }}>{uploading ? '處理中...' : '上傳並匯入'}</button>
                {uploadMessage && <p style={{color: 'green', fontWeight: 'bold', marginTop: '10px'}}>{uploadMessage}</p>}
                {uploadError && <p style={{color: 'red', fontWeight: 'bold', marginTop: '10px'}}>{uploadError}</p>}
            </div>
            
            <h3>🏆 已達成獎勵資格名單 (10次以上)</h3>
            {loading ? <p>載入中...</p> : (
                <div className="achievers-list" style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
                        <thead>
                            <tr style={{ backgroundColor: '#f2f2f2', borderBottom: '2px solid #ddd' }}>
                                <th style={{ padding: '10px' }}>班別</th>
                                <th style={{ padding: '10px' }}>學號</th>
                                <th style={{ padding: '10px' }}>姓名</th>
                                <th style={{ padding: '10px' }}>出席次數</th>
                            </tr>
                        </thead>
                        <tbody>
                            {achievers.length > 0 ? achievers.map(s => (
                                <tr key={`${s.cls}-${s.id}`} style={{ borderBottom: '1px solid #eee' }}>
                                    <td style={{ padding: '10px' }}>{s.cls}</td>
                                    <td style={{ padding: '10px' }}>{s.id}</td>
                                    <td style={{ padding: '10px', fontWeight: 'bold' }}>{s.name}</td>
                                    <td style={{ padding: '10px', color: '#2e7d32', fontWeight: 'bold' }}>{s.check_in_count} 次</td>
                                </tr>
                            )) : (
                                <tr><td colSpan="4" style={{textAlign: 'center', padding: '20px', color: '#777'}}>目前沒有學生達成資格</td></tr>
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
    <div className="App" style={{ maxWidth: '600px', margin: '0 auto', padding: '20px', fontFamily: '"Segoe UI", Tahoma, Geneva, Verdana, sans-serif' }}>
      <h1 style={{ textAlign: 'center', color: '#1565c0', fontSize: '32px', marginBottom: '30px' }}>🏅 運動獎勵計劃</h1>
      
      <div className="role-selector" style={{ display: 'flex', justifyContent: 'center', gap: '10px', marginBottom: '20px' }}>
        <button 
            onClick={() => setRole('學生')} 
            style={{ flex: 1, padding: '12px', backgroundColor: role === '學生' ? '#1976d2' : '#e3f2fd', color: role === '學生' ? 'white' : '#1565c0', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', fontSize: '16px', transition: '0.2s' }}>
            🧑‍🎓 學生
        </button>
        <button 
            onClick={() => setRole('體育大使')} 
            style={{ flex: 1, padding: '12px', backgroundColor: role === '體育大使' ? '#f57c00' : '#fff3e0', color: role === '體育大使' ? 'white' : '#e65100', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', fontSize: '16px', transition: '0.2s' }}>
            📝 體育大使
        </button>
        <button 
            onClick={() => setRole('管理員')} 
            style={{ flex: 1, padding: '12px', backgroundColor: role === '管理員' ? '#424242' : '#f5f5f5', color: role === '管理員' ? 'white' : '#424242', border: 'none', borderRadius: '8px', cursor: 'pointer', fontWeight: 'bold', fontSize: '16px', transition: '0.2s' }}>
            ⚙️ 管理員
        </button>
      </div>
      
      <div style={{ backgroundColor: 'white', padding: '25px', borderRadius: '15px', boxShadow: '0 8px 16px rgba(0,0,0,0.1)' }}>
          {role === '學生' && <StudentView />}
          {role === '體育大使' && <AmbassadorView />}
          {role === '管理員' && <AdminView />}
      </div>
    </div>
  );
}

export default App;
