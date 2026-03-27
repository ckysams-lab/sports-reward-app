// 版本 1.8 (最終修正版)
import React, { useState, useEffect } from 'react';
import Papa from 'papaparse';

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

function AdminView() {
    const [achievers, setAchievers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [uploadMessage, setUploadMessage] = useState('');

    useEffect(() => {
        const fetchAchievers = async () => {
            setLoading(true);
            try {
                const response = await fetch('/api/achievers');
                const data = await response.json();
                setAchievers(data);
            } catch (err) {
                console.error("獲取列表失敗:", err);
            } finally {
                setLoading(false);
            }
        };
        fetchAchievers();
    }, []);

    const handleFileChange = (event) => {
        setUploadMessage('');
        setFile(event.target.files[0]);
    };

    const handleUpload = () => {
        if (!file) {
            setUploadMessage('請先選擇一個 CSV 檔案');
            return;
        }
        setUploading(true);
        setUploadMessage('解析並上傳中...');

        Papa.parse(file, {
            header: true,
            skipEmptyLines: true,
            complete: async (results) => {
                const students = results.
