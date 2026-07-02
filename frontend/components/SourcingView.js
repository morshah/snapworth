import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';

// The core tool: upload → report → history. Auth is handled by the parent;
// on a 401 we call onAuthError so the app returns to the login screen.
function SourcingView({ onAuthError }) {
  const [selectedFile, setSelectedFile] = useState(null);
  const [loading, setLoading] = useState(false);
  const [reportData, setReportData] = useState(null);
  const [error, setError] = useState(null);
  const [history, setHistory] = useState([]);

  useEffect(() => {
    fetchHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const fetchHistory = async () => {
    const { ok, data } = await api('/reports');
    if (ok) setHistory(data);
  };

  const viewReport = async (id) => {
    const { ok, data } = await api(`/reports/${id}`);
    if (ok) {
      setReportData(data.report);
      setError(null);
    }
  };

  const handleFileChange = (event) => {
    setSelectedFile(event.target.files[0]);
    setReportData(null);
    setError(null);
  };

  const handleUpload = async () => {
    if (!selectedFile) {
      setError('Please select an image to upload.');
      return;
    }
    setLoading(true);
    setError(null);
    setReportData(null);

    const form = new FormData();
    form.append('file', selectedFile);
    const { ok, status, data } = await api('/upload-image', { method: 'POST', form });
    setLoading(false);

    if (status === 401) {
      onAuthError();
      return;
    }
    if (ok) {
      setReportData(data);
      fetchHistory();
    } else {
      setError((data && data.detail) || 'Failed to generate report. Please try again.');
    }
  };

  return (
    <>
      <div className="uploader">
        <label className="dropzone">
          <input type="file" accept="image/*" onChange={handleFileChange} />
          <span className="dropzone-icon">📷</span>
          <span className="dropzone-title">Click to choose an image</span>
          <span className="dropzone-hint">PNG, JPG or JPEG</span>
        </label>

        {selectedFile && <span className="file-chip">📎 {selectedFile.name}</span>}

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
    </>
  );
}

export default SourcingView;
