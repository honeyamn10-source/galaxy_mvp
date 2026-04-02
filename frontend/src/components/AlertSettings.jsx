import { useEffect, useState } from 'react';

const STORAGE_KEY = 'galaxy_alert_settings_v1';

const DEFAULT_SETTINGS = {
  motionThreshold: 0.75,
  fireThreshold: 0.55,
  smokeThreshold: 0.6,
  intrusionThreshold: 0.5,
  channels: {
    email: true,
    webhook: false,
    dashboard: true,
  },
};

export default function AlertSettings() {
  const [settings, setSettings] = useState(DEFAULT_SETTINGS);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) {
      return;
    }
    try {
      const parsed = JSON.parse(raw);
      setSettings((current) => ({ ...current, ...parsed, channels: { ...current.channels, ...parsed.channels } }));
    } catch {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const updateThreshold = (field) => (event) => {
    const value = Number(event.target.value);
    setSettings((current) => ({ ...current, [field]: Number.isFinite(value) ? value : 0 }));
    setSaved(false);
  };

  const toggleChannel = (channel) => {
    setSettings((current) => ({
      ...current,
      channels: {
        ...current.channels,
        [channel]: !current.channels[channel],
      },
    }));
    setSaved(false);
  };

  const persistSettings = () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Alert Settings</h2>
        <p>Tune per-signal thresholds and notification channels.</p>
      </div>
      <div className="threshold-grid">
        <label>
          Motion threshold
          <input className="form-input" type="number" min="0" max="1" step="0.01" value={settings.motionThreshold} onChange={updateThreshold('motionThreshold')} />
        </label>
        <label>
          Fire threshold
          <input className="form-input" type="number" min="0" max="1" step="0.01" value={settings.fireThreshold} onChange={updateThreshold('fireThreshold')} />
        </label>
        <label>
          Smoke threshold
          <input className="form-input" type="number" min="0" max="1" step="0.01" value={settings.smokeThreshold} onChange={updateThreshold('smokeThreshold')} />
        </label>
        <label>
          Intrusion threshold
          <input className="form-input" type="number" min="0" max="1" step="0.01" value={settings.intrusionThreshold} onChange={updateThreshold('intrusionThreshold')} />
        </label>
      </div>
      <div className="channel-row">
        <button type="button" className={`btn ${settings.channels.email ? 'btn-primary' : 'btn-secondary'}`} onClick={() => toggleChannel('email')}>Email</button>
        <button type="button" className={`btn ${settings.channels.webhook ? 'btn-primary' : 'btn-secondary'}`} onClick={() => toggleChannel('webhook')}>Webhook</button>
        <button type="button" className={`btn ${settings.channels.dashboard ? 'btn-primary' : 'btn-secondary'}`} onClick={() => toggleChannel('dashboard')}>Dashboard</button>
      </div>
      <div className="panel-actions">
        <button className="btn btn-primary" type="button" onClick={persistSettings}>Save alert profile</button>
        {saved ? <span className="muted">Saved</span> : null}
      </div>
    </section>
  );
}
