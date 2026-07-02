import React, { useState } from 'react';

// Same-site with the frontend (localhost) so the httpOnly auth cookie is sent.
const API_BASE_URL = 'http://localhost:8000';

// Login / register form. On success the backend sets an httpOnly auth cookie;
// we just receive the username and hand it up via onAuth(username).
function AuthForm({ onAuth }) {
  const [mode, setMode] = useState('login'); // 'login' | 'register'
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const isRegister = mode === 'register';

  const handleSubmit = async (event) => {
    event.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const response = await fetch(`${API_BASE_URL}/${mode}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include', // send/receive the auth cookie
        body: JSON.stringify({ username, password }),
      });

      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.detail || `HTTP error! status: ${response.status}`);
      }
      onAuth(data.username);
    } catch (err) {
      setError(err.message || 'Something went wrong. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="card">
      <form className="auth-form" onSubmit={handleSubmit}>
        <h2>{isRegister ? 'Create an account' : 'Sign in'}</h2>

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
            autoComplete={isRegister ? 'new-password' : 'current-password'}
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
              <span className="spinner" /> Please wait…
            </>
          ) : isRegister ? (
            'Create account'
          ) : (
            'Sign in'
          )}
        </button>

        <div className="auth-toggle">
          {isRegister ? 'Already have an account? ' : "Don't have an account? "}
          <button
            type="button"
            className="link-btn"
            onClick={() => {
              setMode(isRegister ? 'login' : 'register');
              setError(null);
            }}
          >
            {isRegister ? 'Sign in' : 'Register'}
          </button>
        </div>
      </form>
    </div>
  );
}

export default AuthForm;
