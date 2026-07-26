import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/router';
import { api } from '../../lib/api';

// Public page reached via an invite link. Validates the token, then lets the
// invitee set a username + password. On success the auth cookie is set and we
// redirect to the app.
export default function InvitePage() {
  const router = useRouter();
  const { token } = router.query;

  const [checking, setChecking] = useState(true);
  const [valid, setValid] = useState(false);
  const [email, setEmail] = useState(null);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!router.isReady) return;
    (async () => {
      const { ok, data } = await api(`/invite/${token}`);
      if (ok && data.valid) {
        setValid(true);
        setEmail(data.email);
      }
      setChecking(false);
    })();
  }, [router.isReady, token]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    const { ok, data } = await api('/register', {
      method: 'POST',
      body: { username, password, token },
    });
    setSubmitting(false);
    if (ok) {
      router.push('/'); // cookie is set → app shows the dashboard
    } else {
      setError((data && data.detail) || 'Could not create your account.');
    }
  };

  return (
    <div className="page">
      <header className="app-header">
        <h1>Snapworth</h1>
        <p>You've been invited to create an account.</p>
      </header>

      <div className="card">
        {checking ? (
          <p className="muted">Checking your invitation…</p>
        ) : !valid ? (
          <div className="alert">
            <span>⚠️</span>
            <span>This invitation link is invalid or has expired. Ask an administrator for a new one.</span>
          </div>
        ) : (
          <form className="auth-form" onSubmit={handleSubmit}>
            <h2>Create your account</h2>
            {email && <p className="muted">Invitation for {email}</p>}

            <div className="field">
              <label htmlFor="username">Username</label>
              <input
                id="username"
                type="text"
                autoComplete="username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>

            <div className="field">
              <label htmlFor="password">Password</label>
              <input
                id="password"
                type="password"
                autoComplete="new-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>

            {error && (
              <div className="alert">
                <span>⚠️</span>
                <span><strong>Error:</strong> {error}</span>
              </div>
            )}

            <button className="btn" type="submit" disabled={submitting || !username || !password}>
              {submitting ? (
                <>
                  <span className="spinner" /> Creating…
                </>
              ) : (
                'Create account'
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
