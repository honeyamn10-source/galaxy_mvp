import React, { useEffect, useState } from 'react';
import './Dashboard.css';

export default function Dashboard() {
  const [events, setEvents] = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [stats, setStats] = useState({
    total: 0,
    verified: 0,
    pending: 0,
    highRisk: 0
  });
  const [connected, setConnected] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [apiKey, setApiKey] = useState(localStorage.getItem('api_key') || '');
  const [dataSource, setDataSource] = useState(localStorage.getItem('data_source') || 'cosmos');
  const [deviceForBalance, setDeviceForBalance] = useState(localStorage.getItem('economy_device_id') || 'planet-01');
  const [tokenInfo, setTokenInfo] = useState({
    wallet: '',
    balance: 0,
    staked: 0
  });
  
  // Chat widget state
  const [chatMessages, setChatMessages] = useState([]);
  const [chatInput, setChatInput] = useState('');
  const [chatLoading, setChatLoading] = useState(false);
  const [chatExpanded, setChatExpanded] = useState(false);

  const normalizeFromCosmos = (payload) => {
    const txs = payload?.tx_responses || [];
    return txs.map((tx) => {
      const attrs = (tx.events || [])
        .flatMap((event) => event.attributes || []);

      const attrMap = attrs.reduce((acc, attr) => {
        acc[attr.key] = attr.value;
        return acc;
      }, {});

      const confidencePct = Number(attrMap.confidence || 85);
      const confidence = Number.isNaN(confidencePct) ? 0.85 : confidencePct > 1 ? confidencePct / 100 : confidencePct;

      return {
        id: tx.txhash,
        created_at: tx.timestamp || new Date().toISOString(),
        device_id: attrMap.device_id || 'unknown-device',
        event_type: attrMap.event_type || 'unknown',
        confidence,
        verified: (attrMap.status || 'pending') === 'verified'
      };
    });
  };

  // Fetch events from selected data source
  const fetchEvents = async () => {
    if (!apiKey && dataSource === 'backend') return;

    try {
      const cosmosAction = encodeURIComponent("message.action='submit_event'");
      const cosmosModule = encodeURIComponent("message.module='galaxy'");
      const request = dataSource === 'cosmos'
        ? fetch(`http://localhost:1317/cosmos/tx/v1beta1/txs?limit=50&events=${cosmosAction}&events=${cosmosModule}`)
        : fetch('http://localhost:8000/events?page=1&page_size=50', {
            headers: {
              'X-API-Key': apiKey
            }
          });

      const response = await request;

      if (response.ok) {
        const data = await response.json();
        const items = dataSource === 'cosmos' ? normalizeFromCosmos(data) : data.items;
        setEvents(items);

        // Calculate stats
        const verified = items.filter(e => e.verified).length;
        const pending = items.filter(e => !e.verified).length;

        setStats((current) => ({
          total: dataSource === 'cosmos' ? (data.pagination?.total ? Number(data.pagination.total) : items.length) : data.total,
          verified,
          pending,
          highRisk: current.highRisk
        }));

        setConnected(true);
      }
    } catch (error) {
      console.error('Failed to fetch events:', error);
      setConnected(false);
    }
  };

  const fetchPredictions = async () => {
    try {
      const response = await fetch('http://localhost:8300/predictions/latest');
      if (!response.ok) {
        return;
      }

      const data = await response.json();
      const items = data.items || [];
      setPredictions(items);

      const highRisk = items.filter((item) => item.risk_level === 'high').length;
      setStats((current) => ({
        ...current,
        highRisk
      }));
    } catch (error) {
      console.warn('Failed to fetch predictions:', error);
    }
  };

  const fetchTokenBalance = async () => {
    if (!deviceForBalance) {
      return;
    }
    try {
      const response = await fetch(`http://localhost:1317/economy/v1/balance/by-device/${encodeURIComponent(deviceForBalance)}`);
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      setTokenInfo({
        wallet: data.wallet || '',
        balance: Number(data.balance || 0),
        staked: Number(data.staked || 0)
      });
    } catch (error) {
      console.warn('Failed to fetch token balance:', error);
    }
  };

  const handleStake = async () => {
    if (!tokenInfo.wallet) {
      return;
    }

    try {
      const response = await fetch('http://localhost:1317/economy/v1/stake', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ wallet: tokenInfo.wallet, amount: 10 })
      });
      if (response.ok) {
        fetchTokenBalance();
      }
    } catch (error) {
      console.warn('Staking request failed:', error);
    }
  };

  const handleChatSend = async () => {
    if (!chatInput.trim()) return;

    const userMessage = chatInput;
    setChatInput('');
    setChatMessages(prev => [...prev, { role: 'user', text: userMessage }]);
    setChatLoading(true);

    try {
      const response = await fetch('http://localhost:8600/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ question: userMessage })
      });

      if (response.ok) {
        const data = await response.json();
        setChatMessages(prev => [...prev, { role: 'assistant', text: data.answer }]);
      } else {
        setChatMessages(prev => [...prev, { role: 'assistant', text: 'Error: LLM service unavailable' }]);
      }
    } catch (error) {
      console.error('Chat request failed:', error);
      setChatMessages(prev => [...prev, { role: 'assistant', text: 'Connection error. Ensure LLM service is running.' }]);
    } finally {
      setChatLoading(false);
    }
  };

  // Poll for new events
  useEffect(() => {
    fetchEvents();
    const interval = setInterval(fetchEvents, 5000); // Refresh every 5 seconds
    return () => clearInterval(interval);
  }, [apiKey, dataSource]);

  useEffect(() => {
    fetchPredictions();
    const interval = setInterval(fetchPredictions, 8000);
    return () => clearInterval(interval);
  }, []);

  useEffect(() => {
    fetchTokenBalance();
    localStorage.setItem('economy_device_id', deviceForBalance);
    const interval = setInterval(fetchTokenBalance, 12000);
    return () => clearInterval(interval);
  }, [deviceForBalance]);

  // WebSocket for real-time updates (optional)
  useEffect(() => {
    if (!apiKey && dataSource === 'backend') return;

    try {
      const wsUrl = dataSource === 'cosmos'
        ? 'ws://localhost:26657/websocket'
        : `ws://localhost:8000/ws?api_key=${encodeURIComponent(apiKey)}`;

      const ws = new WebSocket(wsUrl);

      ws.onopen = () => {
        console.log('WebSocket connected');
        setWsConnected(true);

        if (dataSource === 'cosmos') {
          ws.send(JSON.stringify({
            jsonrpc: '2.0',
            method: 'subscribe',
            id: 'galaxy-ui',
            params: {
              query: "tm.event='Tx' AND message.action='submit_event'"
            }
          }));
        }
      };

      ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        let mapped = data;

        if (dataSource === 'cosmos') {
          const txResult = data?.result?.data?.value?.TxResult;
          const ev = txResult?.result?.events || {};
          mapped = {
            id: `${Date.now()}-${Math.random()}`,
            created_at: new Date().toISOString(),
            device_id: ev['galaxy.device_id']?.[0] || 'unknown-device',
            event_type: ev['galaxy.event_type']?.[0] || 'unknown',
            confidence: 0.9,
            verified: (ev['galaxy.status']?.[0] || 'pending') === 'verified'
          };
        }

        setEvents(prev => {
          const next = [mapped, ...prev.filter(e => e.id !== mapped.id)].slice(0, 50);
          const verified = next.filter(e => e.verified).length;
          setStats(current => ({
            ...current,
            total: Math.max(current.total + 1, next.length),
            verified,
            pending: next.length - verified
          }));
          return next;
        });
      };

      ws.onclose = () => {
        console.log('WebSocket disconnected');
        setWsConnected(false);
      };

      const keepAlive = setInterval(() => {
        if (ws.readyState === WebSocket.OPEN) {
          ws.send('ping');
        }
      }, 25000);

      return () => {
        clearInterval(keepAlive);
        ws.close();
      };
    } catch (error) {
      console.log('WebSocket not available, using polling');
    }
  }, [apiKey, dataSource]);

  const handleSaveApiKey = () => {
    localStorage.setItem('api_key', apiKey);
    fetchEvents();
  };

  const handleDataSourceChange = (value) => {
    localStorage.setItem('data_source', value);
    setDataSource(value);
  };

  if (!apiKey && dataSource === 'backend') {
    return (
      <div className="container auth-page">
        <div className="auth-box">
          <h1>🌌 Galaxy Event Detection</h1>
          <p>Enter your API Key to view real-time events</p>
          <input
            type="password"
            placeholder="API Key (gal_...)"
            value={apiKey}
            onChange={(e) => setApiKey(e.target.value)}
            className="input-field"
          />
          <button onClick={handleSaveApiKey} className="btn btn-primary">
            Connect
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="container">
      <header className="header">
        <h1>🌌 Galaxy Event Detection Dashboard</h1>
        <div className="status">
          <span className={`dot ${connected ? 'online' : 'offline'}`}></span>
          {connected ? `${dataSource.toUpperCase()} ${wsConnected ? '+ Live' : '(Polling)'}` : 'Offline'}
        </div>
      </header>

      <section className="actions" style={{justifyContent: 'flex-start', marginBottom: '1rem'}}>
        <button
          onClick={() => handleDataSourceChange('cosmos')}
          className="btn btn-secondary"
          style={{opacity: dataSource === 'cosmos' ? 1 : 0.6}}
        >
          Cosmos Source
        </button>
        <button
          onClick={() => handleDataSourceChange('backend')}
          className="btn btn-secondary"
          style={{opacity: dataSource === 'backend' ? 1 : 0.6}}
        >
          Legacy Backend Source
        </button>
      </section>

      <section className="stats">
        <div className="stat-card">
          <h3>Total Events</h3>
          <div className="stat-number">{stats.total}</div>
        </div>
        <div className="stat-card verified">
          <h3>Verified</h3>
          <div className="stat-number">{stats.verified}</div>
        </div>
        <div className="stat-card pending">
          <h3>Pending</h3>
          <div className="stat-number">{stats.pending}</div>
        </div>
        <div className="stat-card high-risk">
          <h3>High Risk Alerts</h3>
          <div className="stat-number">{stats.highRisk}</div>
        </div>
      </section>

      <section className="events">
        <h2>Token Economy</h2>
        <div className="actions" style={{justifyContent: 'flex-start', marginBottom: '1rem'}}>
          <input
            type="text"
            value={deviceForBalance}
            onChange={(e) => setDeviceForBalance(e.target.value)}
            className="input-field"
            style={{maxWidth: '260px', marginBottom: 0}}
            placeholder="Device ID for balance"
          />
          <button className="btn btn-secondary" onClick={fetchTokenBalance}>Refresh Balance</button>
          <button className="btn btn-primary" onClick={handleStake} disabled={!tokenInfo.wallet}>Stake 10 GALAXY</button>
        </div>
        <table className="events-table">
          <thead>
            <tr>
              <th>Wallet</th>
              <th>Available Balance</th>
              <th>Staked</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td><code>{tokenInfo.wallet || 'unregistered-device'}</code></td>
              <td>{tokenInfo.balance} ugalaxy</td>
              <td>{tokenInfo.staked} ugalaxy</td>
            </tr>
          </tbody>
        </table>
      </section>

      <section className="events">
        <h2>Predictive Alerts</h2>
        {predictions.length === 0 ? (
          <p className="empty-state">No predictive alerts yet.</p>
        ) : (
          <table className="events-table">
            <thead>
              <tr>
                <th>Zone</th>
                <th>Risk</th>
                <th>Confidence</th>
                <th>Forecast</th>
              </tr>
            </thead>
            <tbody>
              {predictions.slice(0, 10).map((prediction) => (
                <tr key={prediction.frame_hash || prediction.location} className={prediction.risk_level === 'high' ? 'pending' : 'verified'}>
                  <td><strong>{prediction.location || 'unknown-zone'}</strong></td>
                  <td>
                    <span className={`badge ${prediction.risk_level === 'high' ? 'pending' : 'verified'}`}>
                      {prediction.risk_level === 'high' ? 'High Risk' : 'Normal'}
                    </span>
                  </td>
                  <td>{((prediction.confidence || 0) * 100).toFixed(1)}%</td>
                  <td>{prediction.meta?.forecast_horizon || '1h'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="events">
        <h2>Recent Events</h2>
        {events.length === 0 ? (
          <p className="empty-state">No events yet. Waiting for detections...</p>
        ) : (
          <table className="events-table">
            <thead>
              <tr>
                <th>Time</th>
                <th>Device</th>
                <th>Type</th>
                <th>Confidence</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {events.map((event) => (
                <tr key={event.id} className={event.verified ? 'verified' : 'pending'}>
                  <td>{new Date(event.created_at).toLocaleTimeString()}</td>
                  <td><code>{event.device_id}</code></td>
                  <td><strong>{event.event_type}</strong></td>
                  <td>
                    <div className="confidence-bar">
                      <div
                        className="confidence-fill"
                        style={{width: `${event.confidence * 100}%`}}
                      ></div>
                      <span>{(event.confidence * 100).toFixed(1)}%</span>
                    </div>
                  </td>
                  <td>
                    <span className={`badge ${event.verified ? 'verified' : 'pending'}`}>
                      {event.verified ? '✓ Verified' : '⏳ Pending'}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="events">
        <h2>🤖 LLM Chat Assistant</h2>
        <div className="chat-widget" style={{
          border: '1px solid #ddd',
          borderRadius: '8px',
          padding: '1rem',
          backgroundColor: '#f9f9f9',
          maxHeight: chatExpanded ? '500px' : '300px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden'
        }}>
          <div style={{
            flex: 1,
            overflowY: 'auto',
            marginBottom: '1rem',
            paddingRight: '0.5rem'
          }}>
            {chatMessages.length === 0 ? (
              <p style={{color: '#999', fontStyle: 'italic'}}>Ask a question about events, security, or the Galaxy system...</p>
            ) : (
              chatMessages.map((msg, idx) => (
                <div key={idx} style={{
                  marginBottom: '0.75rem',
                  padding: '0.5rem',
                  borderRadius: '4px',
                  backgroundColor: msg.role === 'user' ? '#e3f2fd' : '#f5f5f5'
                }}>
                  <strong>{msg.role === 'user' ? 'You' : 'LLM'}:</strong> {msg.text}
                </div>
              ))
            )}
            {chatLoading && <div style={{color: '#999'}}>LLM thinking...</div>}
          </div>
          <div style={{display: 'flex', gap: '0.5rem'}}>
            <input
              type="text"
              value={chatInput}
              onChange={(e) => setChatInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleChatSend()}
              placeholder="Ask something..."
              className="input-field"
              disabled={chatLoading}
              style={{flex: 1, marginBottom: 0}}
            />
            <button
              onClick={handleChatSend}
              className="btn btn-primary"
              disabled={chatLoading || !chatInput.trim()}
              style={{minWidth: '80px'}}
            >
              Send
            </button>
            <button
              onClick={() => setChatExpanded(!chatExpanded)}
              className="btn btn-secondary"
              style={{minWidth: '60px'}}
            >
              {chatExpanded ? 'Collapse' : 'Expand'}
            </button>
          </div>
        </div>
        <p style={{fontSize: '0.85rem', color: '#666', marginTop: '0.5rem'}}>
          💡 This chat is powered by DeepSeek LLM (6.7B) running locally via Ollama.
        </p>
      </section>

      <section className="actions">
        {dataSource === 'backend' && (
          <button
            onClick={() => {
              localStorage.removeItem('api_key');
              setApiKey('');
            }}
            className="btn btn-secondary"
          >
            Logout
          </button>
        )}
      </section>
    </div>
  );
}
