import React, { useState } from 'react';
import { api } from '../lib/api';

// Login only. Registration is invite-only and happens on /invite/<token>.
function AuthForm({ onAuth }) {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    const { ok, data } = await api('/login', {
      method: 'POST',
      body: { username, password },
    });
    setLoading(false);

    if (ok) {
      onAuth(data); // { username, is_admin }
    } else {
      setError((data && data.detail) || 'Sign in failed. Please try again.');
    }
  };

  return (
    <div className="card">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h2>Sign in</h2>

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
            autoComplete="current-password"
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

        <button className="btn" type="submit" disabled={loading || !username || !password}>
          {loading ? (
            <>
              <span className="spinner" /> Signing in…
            </>
          ) : (
            'Sign in'
          )}
        </button>

        <div className="auth-toggle">
          Access is by invitation only. Ask an administrator for an invite link.
        </div>
      </form>
    </div>
  );
}

export default AuthForm;
