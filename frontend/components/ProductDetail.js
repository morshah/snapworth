import React, { useEffect, useRef, useState } from 'react';
import { api, API_BASE_URL } from '../lib/api';
import { isActive, STATUS_LABEL } from '../lib/status';
import { useNow, elapsed, formatDuration } from '../lib/time';
import PriceChart from './PriceChart';

function ProductDetail({ id, onBack, onAuthError }) {
  const [data, setData] = useState(null);
  const [notFound, setNotFound] = useState(false);
  const [overrides, setOverrides] = useState({});
  const timer = useRef(null);
  const activeRef = useRef(null);
  const reportRef = useRef(null);

  const load = async () => {
    const { ok, status, data: payload } = await api(`/reports/${id}`);
    if (status === 401) return onAuthError();
    if (status === 404) return setNotFound(true);
    if (ok) setData(payload);
  };

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
  const report = data?.report;
  const visitingIndex = data?.sites?.find((s) => s.status === 'visiting')?.index ?? -1;

  useEffect(() => {
    if (report && reportRef.current) {
      reportRef.current.scrollIntoView({ behavior: 'smooth', block: 'start' });
    } else if (visitingIndex >= 0 && activeRef.current) {
      activeRef.current.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }, [visitingIndex, !!report]);

  const back = <button className="link-btn" onClick={onBack}>← Back to products</button>;
  if (notFound) return <div>{back}<div className="alert" style={{ marginTop: 16 }}><span>⚠️</span><span>Product not found.</span></div></div>;
  if (!data) return <div>{back}<p className="muted" style={{ marginTop: 16 }}>Loading…</p></div>;

  const overallSecs = elapsed(data.started_at || data.created_at, data.finished_at, now);

  // Keep the site being visited AND the most-recently-finished one open, so its
  // stats stay visible while the next one loads.
  const doneIdx = data.sites.filter((s) => s.status === 'done').map((s) => s.index);
  const lastDone = doneIdx.length ? Math.max(...doneIdx) : -1;
  const isExpanded = (site) =>
    site.index in overrides ? overrides[site.index] : (site.status === 'visiting' || site.index === lastDone);
  const toggle = (site) => setOverrides((o) => ({ ...o, [site.index]: !isExpanded(site) }));

  const stats = data.stats || {};
  const cur = stats.currency ? `${stats.currency} ` : '';
  const gallery = data.sites.flatMap((s) => s.images || []).slice(0, 8);
  const allReviews = data.sites
    .flatMap((s) => (s.reviews || []).map((r) => ({ ...r, source: s.source })))
    .slice(0, 6);

  return (
    <div className="detail">
      {back}

      <div className="detail-head">
        {data.image_url && <img className="detail-image" src={data.image_url} alt="Uploaded product" />}
        <div className="detail-status">
          <span className={`status ${data.status === 'done' ? 'ok' : data.status === 'error' ? 'muted' : 'pending'}`}>
            {STATUS_LABEL[data.status] || data.status}
          </span>
          <span className="detail-timer">{active && <span className="spinner dark" />} ⏱ {formatDuration(overallSecs)}</span>
        </div>
      </div>

      {data.status === 'error' && (
        <div className="alert"><span>⚠️</span><span>{data.error || 'Something went wrong.'}</span></div>
      )}

      {/* Sites found — pills */}
      {data.found_sites.length > 0 && (
        <div className="section">
          <div className="section-title">Sites found <span className="badge">{data.found_sites.length}</span></div>
          <div className="found-pills">
            {data.found_sites.map((s, i) => (
              <a key={i} className="pill" href={s.link || '#'} target="_blank" rel="noopener noreferrer" title={s.title || ''}>
                <span className="pill-source">{s.source || s.title || 'source'}</span>
                {s.price && <span className="pill-price">{s.price}</span>}
              </a>
            ))}
          </div>
        </div>
      )}

      {/* Per-site progress */}
      {data.sites.length > 0 && (
        <div className="section">
          <div className="section-title">Visiting sites</div>
          <div className="site-cards">
            {data.sites.map((site) => {
              const expanded = isExpanded(site);
              const siteSecs = elapsed(site.started_at, site.finished_at, now);
              return (
                <div key={site.index} ref={site.status === 'visiting' ? activeRef : null} className={`site-card ${site.status}`}>
                  <button className="site-head" onClick={() => toggle(site)}>
                    <span className="site-icon">
                      {site.status === 'done' ? '✓' : site.status === 'failed' ? '⚠️' : site.status === 'visiting' ? <span className="spinner dark" /> : '•'}
                    </span>
                    <span className="site-source">{site.source || site.title || `Site ${site.index + 1}`}</span>
                    {site.price && <span className="site-count">{site.price}</span>}
                    {site.images?.length > 0 && <span className="site-count">🖼 {site.images.length}</span>}
                    {site.status === 'visiting' && <span className="site-timer">⏱ {formatDuration(siteSecs)}</span>}
                    {site.status === 'done' && site.started_at && <span className="site-timer muted">{formatDuration(siteSecs)}</span>}
                    <span className="site-toggle">{expanded ? '▾' : '▸'}</span>
                  </button>

                  {expanded && (
                    <div className="site-body">
                      {site.summary && <p className="site-summary">{site.summary}</p>}

                      {site.images?.length > 0 && (
                        <div className="site-gallery">
                          {site.images.map((path, idx) => (
                            <a key={idx} href={API_BASE_URL + path} target="_blank" rel="noopener noreferrer">
                              <img src={API_BASE_URL + path} alt="" onError={(e) => { e.target.parentElement.style.display = 'none'; }} />
                            </a>
                          ))}
                        </div>
                      )}

                      <dl className="kv">
                        {site.price && <><dt>Price</dt><dd>{site.price}</dd></>}
                        {site.manufacturer && <><dt>Manufacturer</dt><dd>{site.manufacturer}</dd></>}
                        {site.seller && <><dt>Seller / wholesaler</dt><dd>{site.seller}</dd></>}
                        {site.rating && <><dt>Rating</dt><dd>⭐ {site.rating}</dd></>}
                        {site.barcodes?.length > 0 && <><dt>Barcodes</dt><dd>{site.barcodes.map((b, i) => <span key={i} className="chip">{b}</span>)}</dd></>}
                      </dl>

                      {site.specs && Object.keys(site.specs).length > 0 && (
                        <dl className="spec-list">
                          {Object.entries(site.specs).map(([k, v]) => (
                            <div className="spec-row" key={k}><dt>{k}</dt><dd>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd></div>
                          ))}
                        </dl>
                      )}

                      {site.reviews?.length > 0 && (
                        <div className="reviews">
                          {site.reviews.slice(0, 3).map((r, i) => (
                            <blockquote key={i} className="review">
                              <span className="review-body">“{r.body}”</span>
                              <span className="review-meta">{r.author || 'Customer'}{r.rating ? ` · ⭐ ${r.rating}` : ''}</span>
                            </blockquote>
                          ))}
                        </div>
                      )}

                      {site.description && <p className="muted site-desc">{site.description}</p>}
                      {site.link && <a href={site.link} target="_blank" rel="noopener noreferrer">Open listing ↗</a>}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Final case for the manager */}
      {report && (
        <div className="report" ref={reportRef}>
          <h2>Product Case</h2>

          {/* KPI dashboard */}
          <div className="kpis">
            <div className="kpi"><span className="kpi-value">{stats.sites_found}</span><span className="kpi-label">Sites found</span></div>
            {stats.price_min != null && <div className="kpi"><span className="kpi-value">{cur}{stats.price_min}–{stats.price_max}</span><span className="kpi-label">Price range</span></div>}
            {stats.price_median != null && <div className="kpi"><span className="kpi-value">{cur}{stats.price_median}</span><span className="kpi-label">Median price</span></div>}
            {stats.avg_rating != null && <div className="kpi"><span className="kpi-value">⭐ {stats.avg_rating}</span><span className="kpi-label">Avg rating</span></div>}
            {stats.total_reviews > 0 && <div className="kpi"><span className="kpi-value">{stats.total_reviews.toLocaleString()}</span><span className="kpi-label">Reviews</span></div>}
          </div>

          {gallery.length > 0 && (
            <div className="report-gallery">
              {gallery.map((path, i) => (
                <a key={i} href={API_BASE_URL + path} target="_blank" rel="noopener noreferrer" className={i === 0 ? 'main' : ''}>
                  <img src={API_BASE_URL + path} alt="" onError={(e) => { e.target.parentElement.style.display = 'none'; }} />
                </a>
              ))}
            </div>
          )}

          <div className="section">
            <div className="section-title">Summary</div>
            <p>{report.summary}</p>
          </div>

          <div className="verdict">
            <span className="verdict-label">Recommendation</span>
            <p>{report.recommendation}</p>
          </div>

          {(report.pros?.length > 0 || report.cons?.length > 0) && (
            <div className="proscons">
              {report.pros?.length > 0 && (
                <div className="pros">
                  <div className="section-title">Reasons to approve</div>
                  <ul className="feature-list">{report.pros.map((p, i) => <li key={i}>{p}</li>)}</ul>
                </div>
              )}
              {report.cons?.length > 0 && (
                <div className="cons">
                  <div className="section-title">Risks / cautions</div>
                  <ul className="con-list">{report.cons.map((c, i) => <li key={i}>{c}</li>)}</ul>
                </div>
              )}
            </div>
          )}

          {stats.price_values?.length > 0 && (
            <div className="section">
              <div className="section-title">Price distribution</div>
              <PriceChart stats={stats} />
            </div>
          )}

          {(report.customer_sentiment || allReviews.length > 0) && (
            <div className="section">
              <div className="section-title">What customers say</div>
              {report.customer_sentiment && <p>{report.customer_sentiment}</p>}
              {allReviews.map((r, i) => (
                <blockquote key={i} className="review">
                  <span className="review-body">“{r.body}”</span>
                  <span className="review-meta">{r.author || 'Customer'}{r.rating ? ` · ⭐ ${r.rating}` : ''}{r.source ? ` · ${r.source}` : ''}</span>
                </blockquote>
              ))}
            </div>
          )}

          {(report.manufacturer || report.barcodes?.length > 0 || report.wholesalers?.length > 0) && (
            <div className="section">
              <div className="section-title">Sourcing</div>
              <dl className="kv">
                {report.manufacturer && <><dt>Manufacturer</dt><dd>{report.manufacturer}</dd></>}
                {report.wholesalers?.length > 0 && <><dt>Wholesalers</dt><dd>{report.wholesalers.join(', ')}</dd></>}
                {report.barcodes?.length > 0 && <><dt>Barcodes</dt><dd>{report.barcodes.map((b, i) => <span key={i} className="chip">{b}</span>)}</dd></>}
              </dl>
            </div>
          )}

          {report.features?.length > 0 && (
            <div className="section">
              <div className="section-title">Features</div>
              <ul className="feature-list">{report.features.map((f, i) => <li key={i}>{f}</li>)}</ul>
            </div>
          )}

          {report.specifications && Object.keys(report.specifications).length > 0 && (
            <div className="section">
              <div className="section-title">Specifications</div>
              <dl className="spec-list">
                {Object.entries(report.specifications).map(([k, v]) => (
                  <div className="spec-row" key={k}><dt>{k}</dt><dd>{typeof v === 'object' ? JSON.stringify(v) : String(v)}</dd></div>
                ))}
              </dl>
            </div>
          )}

          <div className="section">
            <div className="section-title">Pricing</div>
            <p>{report.pricing_summary}</p>
          </div>
        </div>
      )}
    </div>
  );
}

export default ProductDetail;
