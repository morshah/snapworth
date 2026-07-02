import React, { useEffect, useState } from 'react';
import AuthForm from './AuthForm';

const API_BASE_URL = 'http://127.0.0.1:8000'; // Replace with your backend URL
const TOKEN_KEY = 'psa_token';

function ImageUploadForm() {
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [error, setError] = useState(null);
  const [authToken, setAuthToken] = useState(null);
  const [authReady, setAuthReady] = useState(false); // avoids SSR/first-paint flash
  const [history, setHistory] = useState([]);

  // localStorage is browser-only — read it after mount.
  useEffect(() => {
    setAuthToken(localStorage.getItem(TOKEN_KEY));
    setAuthReady(true);
  }, []);

  // Load saved-report history whenever we have a token.
  useEffect(() => {
    if (authToken) fetchHistory(authToken);
    else setHistory([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [authToken]);

  const fetchHistory = async (token) => {
    try {
      const res = await fetch(`${API_BASE_URL}/reports`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) setHistory(await res.json());
    } catch {
      /* history is non-critical — ignore fetch errors */
    }
  };

  const viewReport = async (id) => {
    try {
      const res = await fetch(`${API_BASE_URL}/reports/${id}`, {
        headers: { Authorization: `Bearer ${authToken}` },
      });
      if (res.ok) {
        const data = await res.json();
        setReportData(data.report); // same shape as a fresh upload
        setError(null);
      }
    } catch {
      setError('Could not load that report.');
    }
  };

  const handleAuth = (token) => {
    localStorage.setItem(TOKEN_KEY, token);
    setAuthToken(token);
  };

  const handleLogout = () => {
    localStorage.removeItem(TOKEN_KEY);
    setAuthToken(null);
    setSelectedFile(null);
    setReportData(null);
    setError(null);
  };

  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
    setReportData(null); // Clear previous results
    setError(null);      // Clear previous errors
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select an image to upload.');
      return;
    }

    setLoading(true);
    setError(null);
    setReportData(null);

    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch(`${API_BASE_URL}/upload-image`, {
        method: 'POST',
        body: formData,
        // FormData sets Content-Type automatically; we only add auth.
        headers: { Authorization: `Bearer ${authToken}` },
      });

      // Token rejected/expired — send the user back to the login screen.
      if (response.status === 401) {
        handleLogout();
        setError('Your session expired. Please sign in again.');
        return;
      }

      if (!response.ok) {
        const errorData = await response.json();
        throw new Error(errorData.detail || `HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      setReportData(data);
      fetchHistory(authToken); // refresh history with the newly saved report
    } catch (err) {
      console.error('Upload failed:', err);
      setError(err.message || 'Failed to generate report. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  if (!authReady) return null;

  return (
    <div className="page">
      <header className="app-header">
        <h1>Product Sourcing Intelligence Agent</h1>
        <p>Upload a product photo to find matching listings and generate an AI report.</p>
      </header>

      {!authToken ? (
        <AuthForm onAuth={handleAuth} />
      ) : (
      <div className="card">
        <div className="account-bar">
          <span>🔒 Signed in</span>
          <button className="link-btn" onClick={handleLogout}>Log out</button>
        </div>
        <div className="uploader">
          <label className="dropzone">
            <input type="file" accept="image/*" onChange={handleFileChange} />
            <span className="dropzone-icon">📷</span>
            <span className="dropzone-title">Click to choose an image</span>
            <span className="dropzone-hint">PNG, JPG or JPEG</span>
          </label>

          {selectedFile && (
            <span className="file-chip">📎 {selectedFile.name}</span>
          )}

          <button className="btn" onClick={handleUpload} disabled={loading || !selectedFile}>
            {loading ? (
              <>
                <span className="spinner" /> Processing…
              </>
            ) : (
              'Upload & Get Report'
            )}
          </button>
        </div>

        {error && (
          <div className="alert">
            <span>⚠️</span>
            <span><strong>Error:</strong> {error}</span>
          </div>
        )}

        {reportData && (
          <div className="report">
            <h2>Product Intelligence Report</h2>

            <div className="section">
              <div className="section-title">Summary</div>
              <p>{reportData.report.summary}</p>
            </div>

            <div className="section">
              <div className="section-title">Features</div>
              <ul className="feature-list">
                {reportData.report.features_list.map((feature, index) => (
                  <li key={index}>{feature}</li>
                ))}
              </ul>
            </div>

            <div className="section">
              <div className="section-title">Specifications</div>
              <pre className="specs">{JSON.stringify(reportData.report.specs, null, 2)}</pre>
            </div>

            <div className="section">
              <div className="section-title">Pricing</div>
              <p>{reportData.report.pricing_summary}</p>
            </div>

            <div className="section">
              <div className="section-title">Recommendation</div>
              <p>{reportData.report.recommendation_sentiment}</p>
            </div>

            <div className="section">
              <div className="section-title">
                Images <span className="badge">{reportData.images.length}</span>
              </div>
              <div className="image-grid">
                {reportData.images.map((imgUrl, index) => (
                  <figure key={index}>
                    <img
                      src={imgUrl}
                      alt={`Product ${index + 1}`}
                      onError={(e) => {
                        e.target.onerror = null;
                        e.target.src = '/placeholder-image.png';
                        e.target.alt = 'Image failed to load';
                      }}
                    />
                  </figure>
                ))}
              </div>
            </div>

            {(reportData.pdf_links.length > 0 || reportData.video_links.length > 0) && (
              <div className="section">
                <div className="section-title">Additional Resources</div>
                <ul className="resource-links">
                  {reportData.pdf_links.map((link, index) => (
                    <li key={`pdf-${index}`}>
                      📄 <a href={link} target="_blank" rel="noopener noreferrer">{link}</a>
                    </li>
                  ))}
                  {reportData.video_links.map((link, index) => (
                    <li key={`video-${index}`}>
                      🎬 <a href={link} target="_blank" rel="noopener noreferrer">{link}</a>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}

        {history.length > 0 && (
          <div className="section history">
            <div className="section-title">Recent reports</div>
            <ul className="history-list">
              {history.map((item) => (
                <li key={item.id}>
                  <button className="history-item" onClick={() => viewReport(item.id)}>
                    {item.preview_image_url ? (
                      <img
                        src={item.preview_image_url}
                        alt=""
                        onError={(e) => { e.target.style.visibility = 'hidden'; }}
                      />
                    ) : (
                      <span className="history-thumb">🔍</span>
                    )}
                    <span className="history-text">
                      <span className="history-summary">{item.summary || 'Untitled report'}</span>
                      <span className="history-date">
                        {new Date(item.created_at).toLocaleString()}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
      )}
    </div>
  );
}

export default ImageUploadForm;
