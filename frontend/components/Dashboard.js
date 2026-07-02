import React, { useState } from 'react';
import SourcingView from './SourcingView';
import UsersView from './UsersView';
import InvitationsView from './InvitationsView';

// Nav shell. Everyone sees Sourcing; admins also get Users and Invitations.
function Dashboard({ user, onLogout, onAuthError }) {
  const [view, setView] = useState('sourcing');

  const navItems = [
    { key: 'sourcing', label: 'Sourcing' },
    ...(user.is_admin
      ? [
          { key: 'users', label: 'Users' },
          { key: 'invitations', label: 'Invitations' },
        ]
      : []),
  ];

  return (
    <div className="card">
      <div className="account-bar">
        <nav className="nav">
          {navItems.map((item) => (
            <button
              key={item.key}
              className={`nav-item${view === item.key ? ' active' : ''}`}
              onClick={() => setView(item.key)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <span className="account-info">
          🔒 <strong>{user.username}</strong>
          {user.is_admin && <span className="badge">admin</span>}
          <button className="link-btn" onClick={onLogout}>Log out</button>
        </span>
      </div>

      {view === 'sourcing' && <SourcingView onAuthError={onAuthError} />}
      {view === 'users' && (
        <UsersView user={user} onAuthError={onAuthError} onGotoInvite={() => setView('invitations')} />
      )}
      {view === 'invitations' && <InvitationsView onAuthError={onAuthError} />}
    </div>
  );
}

export default Dashboard;
