import { useMemo, useState } from 'react';

function normalizeDeviceId(value) {
  return value.trim().toLowerCase().replace(/[^a-z0-9-_]/g, '-');
}

export default function DeviceManager({ events }) {
  const discoveredDevices = useMemo(() => {
    const unique = new Map();
    (events || []).forEach((event) => {
      const deviceId = event?.event?.device_id || event?.device_id;
      if (!deviceId || unique.has(deviceId)) {
        return;
      }
      unique.set(deviceId, {
        id: deviceId,
        status: event?.status || (event?.verified ? 'verified' : 'pending'),
      });
    });
    return Array.from(unique.values());
  }, [events]);

  const [devices, setDevices] = useState([]);
  const [newDevice, setNewDevice] = useState('');

  const mergedDevices = useMemo(() => {
    const listed = new Map(devices.map((device) => [device.id, device]));
    discoveredDevices.forEach((device) => {
      if (!listed.has(device.id)) {
        listed.set(device.id, { ...device, active: true, source: 'auto' });
      }
    });
    return Array.from(listed.values()).sort((a, b) => a.id.localeCompare(b.id));
  }, [devices, discoveredDevices]);

  const addDevice = () => {
    const id = normalizeDeviceId(newDevice);
    if (!id || devices.some((device) => device.id === id)) {
      return;
    }
    setDevices((current) => [...current, { id, status: 'pending', active: true, source: 'manual' }]);
    setNewDevice('');
  };

  const toggleDevice = (id) => {
    setDevices((current) => {
      const existing = current.find((device) => device.id === id);
      if (!existing) {
        return [...current, { id, status: 'pending', active: false, source: 'manual' }];
      }
      return current.map((device) => (device.id === id ? { ...device, active: !device.active } : device));
    });
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Device Manager</h2>
        <p>Track active ingestion devices and quickly mute noisy nodes.</p>
      </div>
      <div className="device-controls">
        <input
          className="form-input"
          value={newDevice}
          onChange={(event) => setNewDevice(event.target.value)}
          placeholder="Add device id"
        />
        <button className="btn btn-primary" type="button" onClick={addDevice} disabled={!newDevice.trim()}>
          Add
        </button>
      </div>
      <div className="device-list">
        {mergedDevices.length === 0 ? (
          <p className="empty-state">No devices discovered yet.</p>
        ) : (
          mergedDevices.map((device) => (
            <article className="device-item" key={device.id}>
              <div>
                <strong>{device.id}</strong>
                <div className="muted">Source: {device.source || 'auto'} · State: {device.status}</div>
              </div>
              <button
                className={`btn ${device.active ? 'btn-secondary' : 'btn-primary'}`}
                type="button"
                onClick={() => toggleDevice(device.id)}
              >
                {device.active ? 'Mute' : 'Activate'}
              </button>
            </article>
          ))
        )}
      </div>
    </section>
  );
}
