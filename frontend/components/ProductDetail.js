import React, { useEffect, useRef, useState } from 'react';
import { api } from '../lib/api';
import { isActive, STATUS_LABEL } from '../lib/status';
import { useNow, elapsed, formatDuration } from '../lib/time';

function ProductDetail({ id, onBack, onAuthError }) {
  const [data, setData] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [overrides, setOverrides] = useState({}); // manual expand/collapse per site
  const timer = useRef(null);

  const load = async () => {
    const { ok, status, data: payload } = await api(`/reports/${id}`);
    if (status === 401) return onAuthError();
    if (status === 404) return setNotFound(true);
    if (ok) setData(payload);
  };

  // Poll while the job is active; stop once done/error.
  useEffect(() => {
    load();
    return () => { if (timer.current) clearInterval(timer.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [id]);

  const active = data ? isActive(data.status) : true;
  useEffect(() => {
    if (active && !timer.current) timer.current = setInterval(load, 1500);
    if (!active && timer.current) { clearInterval(timer.current); timer.current = null; }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  const now = useNow(active);

  const back = (
    <button className="link-btn" onClick={onBack}>← Back to products</button>
  );

  if (notFound) {
    return <div>{back}<div className="alert" style={{ marginTop: 16 }}><span>⚠️</span><span>Product not found.</span></div></div>;
  }
  if (!data) {
    return <div>{back}<p className="muted" style={{ marginTop: 16 }}>Loading…</p></div>;
  }

  const overallSecs = elapsed(data.started_at || data.created_at, data.finished_at, now);

  // A site is expanded when it's actively being visited, unless the user toggled it.
  const isExpanded = (site) =>
    site.index in overrides ? overrides[site.index] : site.status === 'visiting';
  const toggle = (site) =>
    setOverrides((o) => ({ ...o, [site.index]: !isExpanded(site) }));

  const report = data.report;

  return (
    <div className="detail">
      {back}

      <div className="detail-head">
        {data.image_url && (
          <img className="detail-image" src={data.image_url} alt="Uploaded product" />
        )}
        <div className="detail-status">
          <span className={`status ${data.status === 'done' ? 'ok' : data.status === 'error' ? 'muted' : 'pending'}`}>
            {STATUS_LABEL[data.status] || data.status}
          </span>
          <span className="detail-timer">
            {active && <span className="spinner dark" />} ⏱ {formatDuration(overallSecs)}
          </span>
        </div>
      </div>

      {data.status === 'error' && (
        <div className="alert"><span>⚠️</span><span>{data.error || 'Something went wrong.'}</span></div>
      )}

      {/* All sites found */}
      {data.found_sites.length > 0 && (
        <div className="section">
          <div className="section-title">Sites found <span className="badge">{data.found_sites.length}</span></div>
          <ul className="found-list">
            {data.found_sites.map((s, i) => (
              <li key={i}>
                <span className="found-source">{s.source || s.title || 'Unknown source'}</span>
                {s.price && <span className="found-price">{s.price}</span>}
                {s.link && <a href={s.link} target="_blank" rel="noopener noreferrer">visit ↗</a>}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Per-site visit progress */}
      {data.sites.length > 0 && (
        <div className="section">
          <div className="section-title">Visiting sites</div>
          <div className="site-cards">
            {data.sites.map((site) => {
              const expanded = isExpanded(site);
              const siteSecs = elapsed(site.started_at, site.finished_at, now);
              return (
                <div key={site.index} className={`site-card ${site.status}`}>
                  <button className="site-head" onClick={() => toggle(site)}>
                    <span className="site-icon">
                      {site.status === 'done' ? '✓' : site.status === 'failed' ? '⚠️' : site.status === 'visiting' ? <span className="spinner dark" /> : '•'}
                    </span>
                    <span className="site-source">{site.source || site.title || `Site ${site.index + 1}`}</span>
                    {site.status === 'visiting' && (
                      <span className="site-timer">⏱ {formatDuration(siteSecs)}</span>
                    )}
                    {site.status === 'done' && site.started_at && (
                      <span className="site-timer muted">{formatDuration(siteSecs)}</span>
                    )}
                    <span className="site-toggle">{expanded ? '▾' : '▸'}</span>
                  </button>
                  {expanded && (
                    <div className="site-body">
                      {site.summary && <p>{site.summary}</p>}
                      {site.price && <p className="muted">Price: {site.price}</p>}
                      {site.image && <img className="site-image" src={site.image} alt="" onError={(e) => { e.target.style.display = 'none'; }} />}
                      {site.link && <a href={site.link} target="_blank" rel="noopener noreferrer">Open listing ↗</a>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Final merged report */}
      {report && (
        <div className="report">
          <h2>Product Intelligence Report</h2>

          <div className="section">
            <div className="section-title">Summary</div>
            <p>{report.summary}</p>
          </div>

          {report.features?.length > 0 && (
            <div className="section">
              <div className="section-title">Features</div>
              <ul className="feature-list">
                {report.features.map((f, i) => <li key={i}>{f}</li>)}
              </ul>
            </div>
          )}

          {report.specifications && Object.keys(report.specifications).length > 0 && (
            <div className="section">
              <div className="section-title">Specifications</div>
              <dl className="spec-list">
                {Object.entries(report.specifications).map(([k, v]) => (
                  <div className="spec-row" key={k}>
                    <dt>{k}</dt>
                    <dd>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          )}

          <div className="section">
            <div className="section-title">Pricing</div>
            <p>{report.pricing_summary}</p>
          </div>

          <div className="section">
            <div className="section-title">Recommendation</div>
            <p>{report.recommendation}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProductDetail;
