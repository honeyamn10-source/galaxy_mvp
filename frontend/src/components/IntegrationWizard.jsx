import { useMemo, useState } from 'react';
import { authFetch } from '../auth';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:1317';

const SECTOR_TEMPLATES = {
  'Smart City & Government': {
    event_types: ['fire', 'intrusion', 'motion'],
    default_alert: { email: true, webhook: true },
    confidence_threshold: 0.7,
    example: 'Fire detection at a city utility kiosk',
  },
  'Industrial & Factories': {
    event_types: ['fire', 'smoke', 'intrusion', 'machine_failure'],
    default_alert: { email: true, webhook: true },
    confidence_threshold: 0.82,
    example: 'Machine failure in a production line',
  },
  'Real Estate & Buildings': {
    event_types: ['intrusion', 'motion', 'fire', 'smoke'],
    default_alert: { email: true, webhook: true },
    confidence_threshold: 0.68,
    example: 'After-hours intrusion in a building lobby',
  },
  'Oil, Gas & Energy': {
    event_types: ['fire', 'smoke', 'intrusion', 'pipeline_leak'],
    default_alert: { email: true, sms: true, webhook: true },
    confidence_threshold: 0.85,
    example: 'Fire detection at a power substation',
  },
  'Logistics & Warehouses': {
    event_types: ['intrusion', 'motion', 'fire', 'smoke'],
    default_alert: { email: true, webhook: true },
    confidence_threshold: 0.72,
    example: 'Dock intrusion after shift close',
  },
  'Transportation & Highways': {
    event_types: ['smoke', 'fire', 'intrusion', 'accident'],
    default_alert: { email: true, webhook: true, sms: true },
    confidence_threshold: 0.8,
    example: 'Smoke inside a highway tunnel',
  },
  'Healthcare (Advanced)': {
    event_types: ['fall_detection', 'intrusion', 'fire', 'smoke'],
    default_alert: { email: true, webhook: true, sms: true },
    confidence_threshold: 0.78,
    example: 'Patient fall detection in a monitored corridor',
  },
  Agriculture: {
    event_types: ['intrusion', 'fire', 'smoke', 'machine_failure'],
    default_alert: { email: true, webhook: true },
    confidence_threshold: 0.74,
    example: 'Smoke in a grain storage area',
  },
  'Retail Stores': {
    event_types: ['intrusion', 'motion', 'fire', 'smoke'],
    default_alert: { email: true, webhook: true },
    confidence_threshold: 0.7,
    example: 'After-hours intrusion at a retail store',
  },
};

const SECTOR_NAMES = Object.keys(SECTOR_TEMPLATES);
const DEFAULT_EDGE_IMAGE = 'galaxy-edge-planet:latest';
const WEBHOOK_TEMPLATE_URL = 'https://webhook.site/your-id';

function normalizeName(value) {
  return String(value || 'device')
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '') || 'device';
}

function buildDockerCommand({ deviceName, apiKey, rtspUrl }) {
  return `docker run -d --restart unless-stopped --name edge-${normalizeName(deviceName)} -e RTSP_URL="${rtspUrl}" -e EDGE_TENANT_API_KEY="${apiKey}" -e EDGE_DEVICE_ID="${deviceName}" ${DEFAULT_EDGE_IMAGE}`;
}

function buildCurlCommand({ apiKey, deviceName, eventTypes, confidenceThreshold }) {
  const firstEvent = eventTypes[0] || 'motion';
  return `curl -X POST https://galaxy-mvp.fly.dev/emit-batch -H "Authorization: Bearer ${apiKey}" -H "Content-Type: application/json" -d '{"count":1,"device_id":"${deviceName}","event_type":"${firstEvent}","confidence":${confidenceThreshold}}'`;
}

export default function IntegrationWizard({ open, onClose, user, onAlertRulesCreated }) {
  const [step, setStep] = useState(1);
  const [sector, setSector] = useState(SECTOR_NAMES[0]);
  const [connectionType, setConnectionType] = useState('rtsp');
  const [rtspUrl, setRtspUrl] = useState('');
  const [deviceName, setDeviceName] = useState('');
  const [deviceId, setDeviceId] = useState('');
  const [description, setDescription] = useState('');
  const [generated, setGenerated] = useState(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');

  const template = useMemo(() => SECTOR_TEMPLATES[sector] || SECTOR_TEMPLATES[SECTOR_NAMES[0]], [sector]);

  if (!open) {
    return null;
  }

  const resetToStep = (nextStep) => {
    setStep(nextStep);
    setMessage('');
    setError('');
  };

  const generateCommand = async () => {
    setLoading(true);
    setError('');
    setMessage('');

    try {
      const targetName = connectionType === 'rtsp' ? deviceName.trim() : deviceId.trim();
      if (!targetName) {
        throw new Error(connectionType === 'rtsp' ? 'Device name is required' : 'Device ID is required');
      }
      if (connectionType === 'rtsp' && !rtspUrl.trim()) {
        throw new Error('RTSP URL is required');
      }

      const keyResponse = await authFetch(`${API_BASE_URL}/auth/api-keys`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          device_id: targetName,
          name: `${sector} - ${targetName}`,
        }),
      });

      const keyData = await keyResponse.json().catch(() => ({}));
      if (!keyResponse.ok) {
        throw new Error(keyData.detail || keyData.message || 'Failed to create API key');
      }

      const apiKey = keyData.api_key;
      const command = connectionType === 'rtsp'
        ? buildDockerCommand({ deviceName: targetName, apiKey, rtspUrl: rtspUrl.trim() })
        : buildCurlCommand({
            apiKey,
            deviceName: targetName,
            eventTypes: template.event_types,
            confidenceThreshold: template.confidence_threshold,
          });

      setGenerated({
        type: connectionType,
        command,
        apiKey,
        deviceName: targetName,
        orgId: user?.org_id || 'unknown-org',
      });
      setStep(4);
      setMessage(`API key created for ${targetName}. Copy the command below.`);
    } catch (err) {
      setError(err.message || 'Unable to generate integration command');
    } finally {
      setLoading(false);
    }
  };

  const copyCommand = async () => {
    if (!generated?.command) {
      return;
    }
    await navigator.clipboard.writeText(generated.command);
    setMessage('Command copied to clipboard.');
  };

  const createAlertRules = async () => {
    if (!generated) {
      return;
    }

    setLoading(true);
    setError('');
    setMessage('');

    const payload = {
      org_id: user?.org_id || 'unknown-org',
      sector,
      device_id: generated.deviceName,
      event_types: template.event_types,
      confidence_threshold: template.confidence_threshold,
      channels: template.default_alert,
      webhook_url: WEBHOOK_TEMPLATE_URL,
      description: description || template.example,
    };

    try {
      const response = await authFetch(`${API_BASE_URL}/notifications/rules`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.detail || data.message || 'Notification rules endpoint unavailable');
      }
      setMessage('Alert rules created from sector template.');
      if (onAlertRulesCreated) {
        onAlertRulesCreated(data);
      }
    } catch (err) {
      setError(err.message || 'Failed to create alert rules');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card wizard-modal">
        <div className="panel-header">
          <h2>Integration Wizard</h2>
          <p>Attach a camera or sensor in a few guided steps.</p>
        </div>

        <div className="wizard-steps">
          <button type="button" className={`wizard-step ${step === 1 ? 'active' : ''}`} onClick={() => resetToStep(1)}>1. Sector</button>
          <button type="button" className={`wizard-step ${step === 2 ? 'active' : ''}`} onClick={() => resetToStep(2)}>2. Connection</button>
          <button type="button" className={`wizard-step ${step === 3 ? 'active' : ''}`} onClick={() => resetToStep(3)}>3. Details</button>
          <button type="button" className={`wizard-step ${step === 4 ? 'active' : ''}`} onClick={() => resetToStep(4)}>4. Command</button>
        </div>

        {step === 1 ? (
          <div className="wizard-section">
            <label className="wizard-field">
              Sector
              <select className="form-input" value={sector} onChange={(event) => setSector(event.target.value)}>
                {SECTOR_NAMES.map((name) => (
                  <option key={name} value={name}>{name}</option>
                ))}
              </select>
            </label>

            <div className="wizard-summary-grid">
              <article className="wizard-summary-card">
                <span className="label">Recommended event types</span>
                <strong>{template.event_types.join(', ')}</strong>
              </article>
              <article className="wizard-summary-card">
                <span className="label">Confidence threshold</span>
                <strong>{template.confidence_threshold}</strong>
              </article>
              <article className="wizard-summary-card">
                <span className="label">Suggested use case</span>
                <strong>{template.example}</strong>
              </article>
            </div>

            <div className="panel-actions">
              <button type="button" className="btn btn-primary" onClick={() => setStep(2)}>Continue</button>
            </div>
          </div>
        ) : null}

        {step === 2 ? (
          <div className="wizard-section">
            <div className="channel-row">
              <button type="button" className={`btn ${connectionType === 'rtsp' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setConnectionType('rtsp')}>Camera (RTSP)</button>
              <button type="button" className={`btn ${connectionType === 'http' ? 'btn-primary' : 'btn-secondary'}`} onClick={() => setConnectionType('http')}>HTTP Sensor</button>
            </div>

            <div className="wizard-note">
              {connectionType === 'rtsp'
                ? 'Use this for cameras, gateways, and Raspberry Pi edge devices.'
                : 'Use this when your system already sends events and cannot run Docker.'}
            </div>

            <div className="panel-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setStep(1)}>Back</button>
              <button type="button" className="btn btn-primary" onClick={() => setStep(3)}>Continue</button>
            </div>
          </div>
        ) : null}

        {step === 3 ? (
          <div className="wizard-section">
            {connectionType === 'rtsp' ? (
              <>
                <label className="wizard-field">
                  RTSP URL
                  <input className="form-input" value={rtspUrl} onChange={(event) => setRtspUrl(event.target.value)} placeholder="rtsp://username:password@camera-ip:554/stream" />
                </label>
                <label className="wizard-field">
                  Device name
                  <input className="form-input" value={deviceName} onChange={(event) => setDeviceName(event.target.value)} placeholder="camera-lobby-01" />
                </label>
              </>
            ) : (
              <>
                <label className="wizard-field">
                  Device ID
                  <input className="form-input" value={deviceId} onChange={(event) => setDeviceId(event.target.value)} placeholder="plc-line-3" />
                </label>
                <label className="wizard-field">
                  Optional description
                  <input className="form-input" value={description} onChange={(event) => setDescription(event.target.value)} placeholder="PLC or sensor bridge description" />
                </label>
              </>
            )}

            <div className="wizard-summary-grid">
              <article className="wizard-summary-card">
                <span className="label">Organization</span>
                <strong>{user?.org_id || 'unknown-org'}</strong>
              </article>
              <article className="wizard-summary-card">
                <span className="label">Alert channels</span>
                <strong>{Object.entries(template.default_alert).filter(([, enabled]) => enabled).map(([channel]) => channel).join(', ')}</strong>
              </article>
            </div>

            <div className="panel-actions">
              <button type="button" className="btn btn-secondary" onClick={() => setStep(2)}>Back</button>
              <button type="button" className="btn btn-primary" onClick={generateCommand} disabled={loading}>Generate</button>
            </div>
          </div>
        ) : null}

        {step === 4 ? (
          <div className="wizard-section">
            {message ? <div className="wizard-note">{message}</div> : null}
            {error ? <div className="wizard-note wizard-error">{error}</div> : null}

            <div className="wizard-command-box">
              <pre>{generated?.command || 'Generate a command to continue.'}</pre>
            </div>

            <div className="wizard-summary-grid">
              <article className="wizard-summary-card">
                <span className="label">Device</span>
                <strong>{generated?.deviceName || 'n/a'}</strong>
              </article>
              <article className="wizard-summary-card">
                <span className="label">Sector</span>
                <strong>{sector}</strong>
              </article>
              <article className="wizard-summary-card">
                <span className="label">API key created</span>
                <strong>{generated?.apiKey ? 'Yes' : 'Pending'}</strong>
              </article>
            </div>

            <div className="panel-actions wizard-actions">
              <button type="button" className="btn btn-secondary" onClick={copyCommand} disabled={!generated?.command}>Copy command</button>
              <button type="button" className="btn btn-secondary" onClick={createAlertRules} disabled={!generated || loading}>Create alert rules</button>
              <button type="button" className="btn btn-primary" onClick={() => resetToStep(1)}>Start over</button>
              <button type="button" className="btn btn-secondary" onClick={onClose}>Close</button>
            </div>

            <div className="wizard-note">
              If your environment cannot run Docker, switch to HTTP Sensor mode and use the curl integration snippet.
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
