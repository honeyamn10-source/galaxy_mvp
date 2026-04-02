function toCsvRow(values) {
  return values
    .map((value) => {
      const normalized = String(value ?? '');
      if (normalized.includes(',') || normalized.includes('"')) {
        return `"${normalized.replace(/"/g, '""')}"`;
      }
      return normalized;
    })
    .join(',');
}

function triggerDownload(filename, mimeType, content) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

export default function ReportDownload({ events, predictions }) {
  const exportEvents = () => {
    const header = ['created_at', 'event_type', 'device_id', 'confidence', 'status'];
    const rows = (events || []).map((event) => [
      event.created_at || event.timestamp || '',
      event.event?.event_type || event.event_type || '',
      event.event?.device_id || event.device_id || '',
      event.event?.confidence ?? event.confidence ?? '',
      event.status || (event.verified ? 'verified' : 'pending'),
    ]);
    const csv = [toCsvRow(header), ...rows.map((row) => toCsvRow(row))].join('\n');
    triggerDownload(`galaxy-events-${Date.now()}.csv`, 'text/csv;charset=utf-8', csv);
  };

  const exportPredictions = () => {
    const payload = {
      exported_at: new Date().toISOString(),
      item_count: (predictions || []).length,
      items: predictions || [],
    };
    triggerDownload(`galaxy-predictions-${Date.now()}.json`, 'application/json;charset=utf-8', JSON.stringify(payload, null, 2));
  };

  return (
    <section className="panel">
      <div className="panel-header">
        <h2>Report Download</h2>
        <p>Export authority events and predictive risk reports.</p>
      </div>
      <div className="report-buttons">
        <button type="button" className="btn btn-primary" onClick={exportEvents} disabled={!events?.length}>
          Download events CSV
        </button>
        <button type="button" className="btn btn-secondary" onClick={exportPredictions} disabled={!predictions?.length}>
          Download predictions JSON
        </button>
      </div>
    </section>
  );
}
