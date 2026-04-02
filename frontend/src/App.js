import { useEffect, useState } from 'react';
import Dashboard from './Dashboard';
import Login from './Login';
import { getStoredUser, logout } from './auth';

export default function App() {
  const [ready, setReady] = useState(false);
  const [user, setUser] = useState(null);

  useEffect(() => {
    setUser(getStoredUser());
    setReady(true);
  }, []);

  if (!ready) {
    return null;
  }

  if (!user) {
    return <Login onLogin={setUser} />;
  }

  return <Dashboard user={user} onLogout={() => { logout(); setUser(null); }} />;
}
