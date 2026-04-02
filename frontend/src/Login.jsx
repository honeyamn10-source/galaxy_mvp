import { useState } from 'react';
import { login, register } from './auth';

export default function Login({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ email: '', password: '', org_name: '' });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);

  const updateField = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
  };

  const submit = async () => {
    setLoading(true);
    setError('');
    try {
      const data = mode === 'login'
        ? await login(form.email, form.password)
        : await register(form.email, form.password, form.org_name);
      onLogin(data);
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard-shell" style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
      <div className="panel" style={{ maxWidth: 420, width: '100%' }}>
        <div className="panel-header">
          <h2>{mode === 'login' ? 'Sign in' : 'Register'}</h2>
          <p>{mode === 'login' ? 'Use your workspace account.' : 'Create a new organization.'}</p>
        </div>
        <div className="event-form">
          {mode === 'register' ? (
            <input className="form-input" placeholder="Organization name" value={form.org_name} onChange={updateField('org_name')} />
          ) : null}
          <input className="form-input" placeholder="Email address" type="email" value={form.email} onChange={updateField('email')} />
          <input className="form-input" placeholder="Password" type="password" value={form.password} onChange={updateField('password')} />
          {error ? <div className="muted" style={{ color: '#f88' }}>{error}</div> : null}
          <button className="btn btn-primary" type="button" onClick={submit} disabled={loading}>
            {loading ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
          <button
            className="btn"
            type="button"
            onClick={() => setMode((current) => (current === 'login' ? 'register' : 'login'))}
          >
            {mode === 'login' ? 'Need an account? Register' : 'Have an account? Sign in'}
          </button>
        </div>
      </div>
    </div>
  );
}