import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';

function InvitationsView({ onAuthError }) {
  const [invites, setInvites] = useState([]);
  const [email, setEmail] = useState('');
  const [grantsAdmin, setGrantsAdmin] = useState(false);
  const [error, setError] = useState(null);
  const [copiedId, setCopiedId] = useState(null);
  const [origin, setOrigin] = useState('');

  useEffect(() => {
    setOrigin(window.location.origin);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const load = async () => {
    const { ok, status, data } = await api('/invitations');
    if (status === 401) return onAuthError();
    if (ok) setInvites(data);
    else setError((data && data.detail) || 'Could not load invitations.');
  };

  const createInvite = async (e) => {
    e.preventDefault();
    setError(null);
    const { ok, status, data } = await api('/invitations', {
      method: 'POST',
      body: { email: email || null, grants_admin: grantsAdmin },
    });
    if (status === 401) return onAuthError();
    if (ok) {
      setEmail('');
      setGrantsAdmin(false);
      load();
    } else {
      setError((data && data.detail) || 'Could not create invitation.');
    }
  };

  const revoke = async (id) => {
    if (!window.confirm('Revoke this invitation?')) return;
    const { status } = await api(`/invitations/${id}`, { method: 'DELETE' });
    if (status === 401) return onAuthError();
    load();
  };

  const linkFor = (token) => `${origin}/invite/${token}`;

  const copyLink = async (inv) => {
    try {
      await navigator.clipboard.writeText(linkFor(inv.token));
      setCopiedId(inv.id);
      setTimeout(() => setCopiedId(null), 1500);
    } catch {
      window.prompt('Copy this invite link:', linkFor(inv.token));
    }
  };

  const statusOf = (inv) => {
    if (inv.accepted_at) return { label: 'Accepted', cls: 'ok' };
    if (new Date(inv.expires_at) < new Date()) return { label: 'Expired', cls: 'muted' };
    return { label: 'Pending', cls: 'pending' };
  };

  return (
    <div className="admin">
      <div className="admin-head">
        <h2>Invitations</h2>
      </div>

      <form className="invite-form" onSubmit={createInvite}>
        <input
          type="email"
          placeholder="Email (optional, for your reference)"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <label className="checkbox">
          <input type="checkbox" checked={grantsAdmin} onChange={(e) => setGrantsAdmin(e.target.checked)} />
          Admin
        </label>
        <button className="btn btn-sm" type="submit">Create invite</button>
      </form>

      {error && (
        <div className="alert"><span>⚠️</span><span>{error}</span></div>
      )}

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr><th>For</th><th>Status</th><th>Expires</th><th className="col-actions">Invite link</th></tr>
          </thead>
          <tbody>
            {invites.map((inv) => {
              const st = statusOf(inv);
              const pending = st.label === 'Pending';
              return (
                <tr key={inv.id}>
                  <td>{inv.email || <span className="muted">—</span>}{inv.grants_admin && <span className="badge">admin</span>}</td>
                  <td><span className={`status ${st.cls}`}>{st.label}</span></td>
                  <td className="muted">{new Date(inv.expires_at).toLocaleDateString()}</td>
                  <td className="col-actions">
                    {pending ? (
                      <>
                        <button className="btn-ghost" onClick={() => copyLink(inv)}>
                          {copiedId === inv.id ? 'Copied!' : 'Copy link'}
                        </button>
                        <button className="btn-ghost danger" onClick={() => revoke(inv.id)}>Revoke</button>
                      </>
                    ) : (
                      <button className="btn-ghost danger" onClick={() => revoke(inv.id)}>Delete</button>
                    )}
                  </td>
                </tr>
              );
            })}
            {invites.length === 0 && (
              <tr><td colSpan={4} className="muted" style={{ textAlign: 'center', padding: '16px' }}>No invitations yet.</td></tr>
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default InvitationsView;
