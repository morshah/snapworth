import React, { useEffect, useState } from 'react';
import { api } from '../lib/api';

function UsersView({ user, onAuthError, onGotoInvite }) {
  const [users, setUsers] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const load = async () => {
    const { ok, status, data } = await api('/users');
    if (status === 401) return onAuthError();
    if (ok) setUsers(data);
    else setError((data && data.detail) || 'Could not load users.');
  };

  const act = async (path, opts, confirmMsg) => {
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    setError(null);
    const { ok, status, data } = await api(path, opts);
    if (status === 401) return onAuthError();
    if (ok) load();
    else setError((data && data.detail) || 'Action failed.');
  };

  const toggleAdmin = (u) =>
    act(`/users/${u.id}`, { method: 'PATCH', body: { is_admin: !u.is_admin } });

  const resetPassword = (u) => {
    const pw = window.prompt(`New password for ${u.username} (min 8 chars):`);
    if (pw == null) return;
    act(`/users/${u.id}`, { method: 'PATCH', body: { password: pw } });
  };

  const deleteUser = (u) =>
    act(`/users/${u.id}`, { method: 'DELETE' }, `Delete ${u.username} and all their reports? This cannot be undone.`);

  return (
    <div className="admin">
      <div className="admin-head">
        <h2>Users</h2>
        <button className="btn btn-sm" onClick={onGotoInvite}>+ Invite user</button>
      </div>

      {error && (
        <div className="alert"><span>⚠️</span><span>{error}</span></div>
      )}

      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr><th>User</th><th>Role</th><th>Joined</th><th className="col-actions">Actions</th></tr>
          </thead>
          <tbody>
            {users.map((u) => {
              const isSelf = u.username === user.username;
              return (
                <tr key={u.id}>
                  <td>
                    {u.username}
                    {isSelf && <span className="tag">you</span>}
                  </td>
                  <td>{u.is_admin ? <span className="badge">admin</span> : <span className="muted">member</span>}</td>
                  <td className="muted">{new Date(u.created_at).toLocaleDateString()}</td>
                  <td className="col-actions">
                    <button className="btn-ghost" onClick={() => toggleAdmin(u)} disabled={isSelf} title={isSelf ? "You can't change your own role" : ''}>
                      {u.is_admin ? 'Revoke admin' : 'Make admin'}
                    </button>
                    <button className="btn-ghost" onClick={() => resetPassword(u)}>Reset password</button>
                    <button className="btn-ghost danger" onClick={() => deleteUser(u)} disabled={isSelf} title={isSelf ? "You can't delete yourself" : ''}>
                      Delete
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export default UsersView;
