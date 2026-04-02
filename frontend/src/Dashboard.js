import React, { useEffect, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import GalaxyView from './GalaxyView';
import './Dashboard.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || 'http://localhost:1317';
const WS_URL = process.env.REACT_APP_WS_URL || 'ws://localhost:1317/websocket';
const EDGE_HEALTH_URL = process.env.REACT_APP_EDGE_HEALTH_URL || 'http://localhost:8100/health';
const PREDICTIVE_BASE_URL = process.env.REACT_APP_PREDICTIVE_URL || 'http://localhost:8300';
const LLM_BASE_URL = process.env.REACT_APP_LLM_URL || 'http://localhost:8600';

function mapWsEvent(rawMessage) {
  try {
    const data = JSON.parse(rawMessage);
    const txResult = data?.result?.data?.value?.TxResult;
    const ev = txResult?.result?.events || {};
    const deviceId = ev['galaxy.device_id']?.[0] || 'unknown-device';
    const eventType = ev['galaxy.event_type']?.[0] || 'unknown';
    const status = ev['galaxy.status']?.[0] || 'pending';

    return {
      id: `${Date.now()}-${Math.random().toString(16).slice(2)}`,
      created_at: new Date().toISOString(),
      envelope_id: ev['galaxy.envelope_id']?.[0] || '',
      event: {
        device_id: deviceId,
        event_type: eventType,
        confidence: 0.9,
      },
      status,
      verified: status === 'verified',
    };
  } catch {
    return null;
  }
}

export default function Dashboard() {
  const [events, setEvents] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [status, setStatus] = useState({ authority: 'unknown', edge: 'unknown', websocket: 'unknown' });
  const [submitting, setSubmitting] = useState(false);
  const [formData, setFormData] = useState({
    device_id: 'demo-01',
    event_type: 'motion',
    confidence: '0.85',
    location: 'Sector-A',
  });
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const wsRef = useRef(null);

  const metrics = useMemo(() => {
    const total = events.length;
    const verified = events.filter((event) => event.status === 'verified' || event.verified).length;
    const pending = total - verified;
    const avgConfidence = total
      ? (events.reduce((sum, event) => sum + Number(event.event?.confidence ?? event.confidence ?? 0), 0) / total).toFixed(2)
      : '0.00';
    const highRisk = predictions.filter((prediction) => prediction.risk_level === 'high').length;

    return { total, verified, pending, avgConfidence, highRisk };
  }, [events, predictions]);

  const fetchEvents = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/galaxy/v1/events?limit=50`);
      if (!response.ok) {
        throw new Error(`authority status ${response.status}`);
      }
      const data = await response.json();
      setEvents(Array.isArray(data.events) ? data.events : []);
      setStatus((current) => ({ ...current, authority: 'ok' }));
    } catch (error) {
      console.error('Failed to fetch events:', error);
      setStatus((current) => ({ ...current, authority: 'error' }));
    }
  };

  const fetchPredictions = async () => {
    try {
      const response = await fetch(`${PREDICTIVE_BASE_URL}/predictions/latest`);
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      setPredictions(Array.isArray(data.items) ? data.items : []);
    } catch (error) {
      console.warn('Failed to fetch predictions:', error);
    }
  };

  const checkHealth = async () => {
    try {
      const authorityResponse = await fetch(`${API_BASE_URL}/health`);
      setStatus((current) => ({ ...current, authority: authorityResponse.ok ? 'ok' : 'error' }));
    } catch {
      setStatus((current) => ({ ...current, authority: 'error' }));
    }

    try {
      const edgeResponse = await fetch(EDGE_HEALTH_URL);
      setStatus((current) => ({ ...current, edge: edgeResponse.ok ? 'ok' : 'error' }));
    } catch {
      setStatus((current) => ({ ...current, edge: 'error' }));
    }
  };

  const submitEvent = async (event) => {
    event.preventDefault();
    setSubmitting(true);

    const payload = {
      submitter: 'dashboard',
      envelope_id: `dashboard-${Date.now()}-${Math.random().toString(16).slice(2)}`,
      origin_peer_id: 'dashboard-web',
      event: {
        device_id: formData.device_id,
        event_type: formData.event_type,
        confidence: Number(formData.confidence),
        location: formData.location || null,
      },
    };

    try {
      const response = await fetch(`${API_BASE_URL}/galaxy/v1/events`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (response.ok) {
        await fetchEvents();
      }
    } catch (error) {
      console.error('Failed to submit event:', error);
    } finally {
      setSubmitting(false);
    }
  };

  const handleChatSend = async () => {
    if (!chatInput.trim()) {
      return;
    }

    const userMessage = chatInput;
    setChatInput('');
    setChatMessages((prev) => [...prev, { role: 'user', text: userMessage }]);
    setChatLoading(true);

    try {
      const response = await fetch(`${LLM_BASE_URL}/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userMessage }),
      });

      if (response.ok) {
        const data = await response.json();
        setChatMessages((prev) => [...prev, { role: 'assistant', text: data.answer }]);
      } else {
        setChatMessages((prev) => [...prev, { role: 'assistant', text: 'LLM service unavailable' }]);
      }
    } catch (error) {
      console.error('Chat request failed:', error);
      setChatMessages((prev) => [...prev, { role: 'assistant', text: 'Connection error. Ensure LLM service is running.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  useEffect(() => {
    fetchEvents();
    fetchPredictions();
    checkHealth();

    const interval = setInterval(() => {
      fetchEvents();
      fetchPredictions();
      checkHealth();
    }, 7000);

    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus((current) => ({ ...current, websocket: 'ok' }));
        ws.send(JSON.stringify({
          jsonrpc: '2.0',
          method: 'subscribe',
          id: 'galaxy-ui',
          params: {
            query: "tm.event='Tx' AND message.action='submit_event'",
          },
        }));
      };

      ws.onmessage = (message) => {
        const mapped = mapWsEvent(message.data);
        if (mapped) {
          setEvents((current) => [mapped, ...current].slice(0, 50));
        }
      };

      ws.onerror = () => {
        setStatus((current) => ({ ...current, websocket: 'error' }));
      };

      ws.onclose = () => {
        setStatus((current) => ({ ...current, websocket: 'error' }));
      };

      return () => {
        ws.close();
      };
    } catch {
      setStatus((current) => ({ ...current, websocket: 'error' }));
      return undefined;
    }
  }, []);

  return (
    <div className="dashboard-shell">
      <header className="hero-banner">
        <div>
          <p className="eyebrow">Galaxy MVP</p>
          <h1>Live event intelligence for edge, swarm, and authority workflows.</h1>
          <p className="hero-copy">
            The dashboard is wired to the authority REST API and websocket, with live event streaming,
            a manual submit form, predictive alerts, and a 3D galaxy visualization.
          </p>
        </div>

        <div className="status-panel">
          <div className="status-row">
            <span className={`status-pill ${status.authority === 'ok' ? 'ok' : 'bad'}`}>Authority {status.authority}</span>
            <span className={`status-pill ${status.edge === 'ok' ? 'ok' : 'bad'}`}>Edge {status.edge}</span>
            <span className={`status-pill ${status.websocket === 'ok' ? 'ok' : 'bad'}`}>WS {status.websocket}</span>
          </div>
          <div className="status-note">REST: {API_BASE_URL}</div>
        </div>
      </header>

      <section className="metric-grid">
        <motion.article className="metric-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }}>
          <strong>{metrics.total}</strong>
          <span>Total events</span>
        </motion.article>
        <motion.article className="metric-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.05 }}>
          <strong>{metrics.verified}</strong>
          <span>Verified</span>
        </motion.article>
        <motion.article className="metric-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }}>
          <strong>{metrics.pending}</strong>
          <span>Pending</span>
        </motion.article>
        <motion.article className="metric-card" initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.15 }}>
          <strong>{metrics.avgConfidence}</strong>
          <span>Avg confidence</span>
        </motion.article>
      </section>

      <section className="grid-layout">
        <div className="panel galaxy-panel">
          <div className="panel-header">
            <h2>3D Galaxy View</h2>
            <p>Recent events are rendered as colored spheres in space.</p>
          </div>
          <GalaxyView events={events.slice(0, 24)} />
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Send Test Event</h2>
            <p>Submit directly to the authority REST API.</p>
          </div>
          <form className="event-form" onSubmit={submitEvent}>
            <input
              className="form-input"
              value={formData.device_id}
              onChange={(e) => setFormData((current) => ({ ...current, device_id: e.target.value }))}
              placeholder="Device ID"
              required
            />
            <select
              className="form-input"
              value={formData.event_type}
              onChange={(e) => setFormData((current) => ({ ...current, event_type: e.target.value }))}
            >
              <option value="motion">Motion</option>
              <option value="fire">Fire</option>
              <option value="smoke">Smoke</option>
              <option value="intrusion">Intrusion</option>
            </select>
            <input
              className="form-input"
              type="number"
              min="0"
              max="1"
              step="0.01"
              value={formData.confidence}
              onChange={(e) => setFormData((current) => ({ ...current, confidence: e.target.value }))}
              placeholder="Confidence"
            />
            <input
              className="form-input"
              value={formData.location}
              onChange={(e) => setFormData((current) => ({ ...current, location: e.target.value }))}
              placeholder="Location"
            />
            <button className="btn btn-primary" type="submit" disabled={submitting}>
              {submitting ? 'Submitting...' : 'Send event'}
            </button>
          </form>
        </div>
      </section>

      <section className="grid-layout single-column">
        <div className="panel">
          <div className="panel-header">
            <h2>Live Events</h2>
            <p>Authority events stream in here in real time.</p>
          </div>
          <div className="event-feed">
            {events.length === 0 ? (
              <p className="empty-state">No events yet. Start the simulator or submit one manually.</p>
            ) : (
              events.map((event) => {
                const eventType = event.event?.event_type || event.event_type || 'unknown';
                const confidence = Number(event.event?.confidence ?? event.confidence ?? 0);
                const statusLabel = event.status || (event.verified ? 'verified' : 'pending');
                return (
                  <article className={`event-card ${eventType}`} key={event.envelope_id || event.id}>
                    <div className="event-card-head">
                      <strong>{eventType}</strong>
                      <span className="mini-badge">{statusLabel}</span>
                    </div>
                    <div>Device: {event.event?.device_id || event.device_id || 'unknown'}</div>
                    <div>Confidence: {confidence.toFixed(2)}</div>
                    <div className="muted">{event.created_at || event.timestamp || 'just now'}</div>
                  </article>
                );
              })
            )}
          </div>
        </div>

        <div className="panel">
          <div className="panel-header">
            <h2>Predictive Alerts</h2>
            <p>Intel from the predictive service.</p>
          </div>
          {predictions.length === 0 ? (
            <p className="empty-state">No predictive alerts yet.</p>
          ) : (
            <div className="event-feed">
              {predictions.slice(0, 10).map((prediction, index) => (
                <article className="event-card prediction" key={prediction.frame_hash || prediction.location || index}>
                  <div className="event-card-head">
                    <strong>{prediction.location || 'unknown-zone'}</strong>
                    <span className="mini-badge">{prediction.risk_level || 'normal'}</span>
                  </div>
                  <div>Confidence: {((prediction.confidence || 0) * 100).toFixed(1)}%</div>
                  <div className="muted">Forecast: {prediction.meta?.forecast_horizon || '1h'}</div>
                </article>
              ))}
            </div>
          )}
        </div>
      </section>

      <section className="panel chat-panel">
        <div className="panel-header">
          <h2>LLM Chat Assistant</h2>
          <p>Ask about the last event, compliance, or system state.</p>
        </div>
        <div className="chat-log">
          {chatMessages.length === 0 ? (
            <p className="empty-state">Ask a question to start the assistant.</p>
          ) : (
            chatMessages.map((message, index) => (
              <div key={index} className={`chat-message ${message.role}`}>
                <strong>{message.role === 'user' ? 'You' : 'LLM'}:</strong> {message.text}
              </div>
            ))
          )}
          {chatLoading ? <div className="muted">Thinking...</div> : null}
        </div>
        <div className="chat-controls">
          <input
            className="form-input"
            value={chatInput}
            onChange={(e) => setChatInput(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleChatSend()}
            placeholder="Ask the assistant..."
          />
          <button className="btn btn-primary" type="button" onClick={handleChatSend} disabled={chatLoading || !chatInput.trim()}>
            Send
          </button>
        </div>
      </section>
    </div>
  );
}
