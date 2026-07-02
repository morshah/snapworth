import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';
import AuthForm from './AuthForm';
import Dashboard from './Dashboard';

// Root: bootstraps auth from the httpOnly cookie via /me, then shows either the
// login screen or the dashboard.
function App() {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState(null); // { username, is_admin } | null

  useEffect(() => {
    (async () => {
      const { ok, data } = await api('/me');
      if (ok) setUser(data);
      setReady(true);
    })();
  }, []);

  const handleLogout = async () => {
    await api('/logout', { method: 'POST' });
    setUser(null);
  };

  if (!ready) return null; // avoid first-paint flash

  return (
    <div className="page">
      <header className="app-header">
        <h1>Product Sourcing Intelligence Agent</h1>
        <p>Upload a product photo to find matching listings and generate an AI report.</p>
      </header>

      {user ? (
        <Dashboard
          user={user}
          onLogout={handleLogout}
          onAuthError={() => setUser(null)}
        />
      ) : (
        <AuthForm onAuth={setUser} />
      )}
    </div>
  );
}

export default App;
