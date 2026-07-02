import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import { useNow, elapsed, formatDuration } from '../lib/time';
import { isActive, STATUS_LABEL } from '../lib/status';
import ProductDetail from './ProductDetail';

function SourcingView({ onAuthError }) {
  const [products, setProducts] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedFile, setSelectedFile] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const now = useNow();
  const pollRef = useRef(null);

  const loadGrid = async () => {
    const { ok, status, data } = await api('/reports');
    if (status === 401) return onAuthError();
    if (ok) setProducts(data);
  };

  useEffect(() => {
    loadGrid();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Poll the grid while any product is still processing (keeps timers/status fresh).
  useEffect(() => {
    const anyActive = products.some((p) => isActive(p.status));
    if (anyActive && !pollRef.current) {
      pollRef.current = setInterval(loadGrid, 3000);
    } else if (!anyActive && pollRef.current) {
      clearInterval(pollRef.current);
      pollRef.current = null;
    }
    return () => {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [products]);

  const handleUpload = async () => {
    if (!selectedFile) return;
    setUploading(true);
    setError(null);
    const form = new FormData();
    form.append('file', selectedFile);
    const { ok, status, data } = await api('/upload-image', { method: 'POST', form });
    setUploading(false);
    if (status === 401) return onAuthError();
    if (ok) {
      setSelectedFile(null);
      await loadGrid();
      setSelectedId(data.id); // jump straight into the live progress view
    } else {
      setError((data && data.detail) || 'Upload failed. Please try again.');
    }
  };

  if (selectedId != null) {
    return (
      <ProductDetail
        id={selectedId}
        onBack={() => { setSelectedId(null); loadGrid(); }}
        onAuthError={onAuthError}
      />
    );
  }

  return (
    <>
      <div className="uploader">
        <label className="dropzone">
          <input type="file" accept="image/*" onChange={(e) => setSelectedFile(e.target.files[0])} />
          <span className="dropzone-icon">📷</span>
          <span className="dropzone-title">Click to choose an image</span>
          <span className="dropzone-hint">PNG, JPG or JPEG</span>
        </label>
        {selectedFile && <span className="file-chip">📎 {selectedFile.name}</span>}
        <button className="btn" onClick={handleUpload} disabled={uploading || !selectedFile}>
          {uploading ? (<><span className="spinner" /> Starting…</>) : 'Upload & Get Report'}
        </button>
      </div>

      {error && (
        <div className="alert"><span>⚠️</span><span><strong>Error:</strong> {error}</span></div>
      )}

      <div className="section">
        <div className="section-title">Your products</div>
        {products.length === 0 ? (
          <p className="muted">No products yet — upload an image to get started.</p>
        ) : (
          <div className="product-grid">
            {products.map((p) => {
              const active = isActive(p.status);
              return (
                <button key={p.id} className="product-card" onClick={() => setSelectedId(p.id)}>
                  <div className="product-thumb">
                    {p.image_url ? (
                      <img src={p.image_url} alt="" onError={(e) => { e.target.style.visibility = 'hidden'; }} />
                    ) : (
                      <span className="history-thumb">🖼️</span>
                    )}
                    {active && <span className="product-timer">⏱ {formatDuration(elapsed(p.started_at || p.created_at, null, now))}</span>}
                  </div>
                  <div className="product-meta">
                    <span className={`status ${p.status === 'done' ? 'ok' : p.status === 'error' ? 'muted' : 'pending'}`}>
                      {STATUS_LABEL[p.status] || p.status}
                    </span>
                    <span className="product-summary">
                      {p.status === 'done' ? (p.summary || 'View report') : p.status === 'error' ? 'Failed — tap for details' : 'In progress…'}
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        )}
      </div>
    </>
  );
}

export default SourcingView;
