import { useState } from 'react';
import { login, register, resendOtp, verifyOtp } from './auth';

export default function Login({ onLogin }) {
  const [mode, setMode] = useState('login');
  const [form, setForm] = useState({ email: '', password: '', org_name: '' });
  const [otp, setOtp] = useState('');
  const [devOtp, setDevOtp] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [loading, setLoading] = useState(false);

  const updateField = (field) => (event) => {
    setForm((current) => ({ ...current, [field]: event.target.value }));
  };

  const submit = async () => {
    setLoading(true);
    setError('');
    setNotice('');
    try {
      if (mode === 'login') {
        const data = await login(form.email, form.password);
        onLogin(data);
        return;
      }
      const data = await register(form.email, form.password, form.org_name);
      setMode('otp');
      setNotice(data.message || 'OTP sent to your email.');
      setDevOtp(data.dev_otp || '');
    } catch (err) {
      setError(err.message || 'Authentication failed');
    } finally {
      setLoading(false);
    }
  };

  const submitOtp = async () => {
    setLoading(true);
    setError('');
    setNotice('');
    try {
      const data = await verifyOtp(form.email, otp);
      onLogin(data);
    } catch (err) {
      setError(err.message || 'OTP verification failed');
    } finally {
      setLoading(false);
    }
  };

  const resend = async () => {
    setLoading(true);
    setError('');
    setNotice('');
    try {
      const data = await resendOtp(form.email);
      setNotice(data.message || 'A new OTP was sent.');
      setDevOtp(data.dev_otp || '');
    } catch (err) {
      setError(err.message || 'Could not resend OTP');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="dashboard-shell" style={{ minHeight: '100vh', display: 'grid', placeItems: 'center' }}>
      <div className="panel" style={{ maxWidth: 420, width: '100%' }}>
        <div className="panel-header">
          <h2>{mode === 'login' ? 'Sign in' : mode === 'otp' ? 'Verify OTP' : 'Register'}</h2>
          <p>{mode === 'login' ? 'Use your workspace account.' : mode === 'otp' ? 'Enter the code sent to your inbox.' : 'Create a new organization.'}</p>
        </div>
        <div className="event-form">
          {mode === 'register' ? (
            <input className="form-input" placeholder="Organization name" value={form.org_name} onChange={updateField('org_name')} />
          ) : null}
          {mode !== 'otp' ? (
            <>
              <input className="form-input" placeholder="Email address" type="email" value={form.email} onChange={updateField('email')} />
              <input className="form-input" placeholder="Password" type="password" value={form.password} onChange={updateField('password')} />
            </>
          ) : (
            <>
              <input className="form-input" placeholder="Email address" type="email" value={form.email} onChange={updateField('email')} />
              <input className="form-input" placeholder="6-digit OTP" value={otp} onChange={(event) => setOtp(event.target.value)} />
            </>
          )}
          {notice ? <div className="muted" style={{ color: '#e0e0ff' }}>{notice}</div> : null}
          {devOtp ? <div className="muted" style={{ color: '#e0e0ff' }}>Dev OTP: {devOtp}</div> : null}
          {error ? <div className="muted" style={{ color: '#f88' }}>{error}</div> : null}
          {mode !== 'otp' ? (
            <>
              <button className="btn btn-primary" type="button" onClick={submit} disabled={loading}>
                {loading ? 'Please wait...' : mode === 'login' ? 'Sign in' : 'Create account'}
              </button>
              <button
                className="btn"
                type="button"
                onClick={() => {
                  setMode((current) => (current === 'login' ? 'register' : 'login'));
                  setError('');
                  setNotice('');
                }}
              >
                {mode === 'login' ? 'Need an account? Register' : 'Have an account? Sign in'}
              </button>
            </>
          ) : (
            <>
              <button className="btn btn-primary" type="button" onClick={submitOtp} disabled={loading || !otp.trim()}>
                {loading ? 'Verifying...' : 'Verify OTP'}
              </button>
              <button className="btn" type="button" onClick={resend} disabled={loading}>
                Resend OTP
              </button>
              <button className="btn" type="button" onClick={() => setMode('login')}>
                Back to sign in
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}