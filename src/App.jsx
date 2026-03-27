// 版本 1.8
import React, { useState, useEffect } from 'react';
import Papa from 'papaparse'; // 引入新安裝的工具

// ... (App, StudentView, AmbassadorView 組件保持不變) ...

// --- 管理員視圖 (重點修改) ---
function AdminView() {
    const [achievers, setAchievers] = useState([]);
    const [loading, setLoading] = useState(true);
    const [file, setFile] = useState(null);
    const [uploading, setUploading] = useState(false);
    const [uploadMessage, setUploadMessage] = useState('');

    // 獲取達標者列表的邏輯 (不變)
    useEffect(() => {
        const fetchAchievers = async () => {
            // ... (邏輯同 1.7)
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
            header: true, // 將第一行視為標題
            skipEmptyLines: true,
            complete: async (results) => {
                const students = results.data;
                try {
                    const response = await fetch('/api/students/batch-import', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify(students)
                    });
                    const data = await response.json();
                    if (!response.ok) throw new Error(data.detail || '上傳失敗');
                    setUploadMessage(data.message);
                } catch (err) {
                    setUploadMessage(`上傳失敗: ${err.message}`);
                } finally {
                    setUploading(false);
                    setFile(null); // 清空已選檔案
                }
            },
            error: (err) => {
                setUploadMessage(`檔案解析失敗: ${err.message}`);
                setUploading(false);
            }
        });
    };

    return (
        <div>
            <h2>管理員後台</h2>

            {/* --- 新增的上傳區塊 --- */}
            <div style={{ padding: '1rem', border: '1px solid #ddd', borderRadius: '5px', marginBottom: '2rem' }}>
                <h4>匯入學生名單</h4>
                <p>請選擇一個 CSV 檔案。檔案第一行需包含標題：`學號`, `姓名`, `班別`</p>
                <input type="file" accept=".csv" onChange={handleFileChange} disabled={uploading} />
                <button onClick={handleUpload} disabled={uploading || !file} style={{marginTop: '1rem'}}>
                    {uploading ? '上傳中...' : '上傳並匯入'}
                </button>
                {uploadMessage && <p>{uploadMessage}</p>}
            </div>
            
            {/* --- 以下是原有的達標者列表 --- */}
            <h3>已達成獎勵資格名單</h3>
            {loading ? <p>載入中...</p> : (
                // ... (列表的 JSX 渲染邏輯同 1.7)
            )}
        </div>
    );
}

export default App;
