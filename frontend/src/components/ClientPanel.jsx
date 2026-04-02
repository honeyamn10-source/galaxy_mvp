import { useMemo } from 'react';

const PLANS = {
  starter: { label: 'Starter', colorClass: 'tag-starter' },
  growth: { label: 'Growth', colorClass: 'tag-growth' },
  enterprise: { label: 'Enterprise', colorClass: 'tag-enterprise' },
};

export default function ClientPanel({ user, plan = 'starter', metrics, onManagePlan }) {
  const activePlan = PLANS[plan] || PLANS.starter;
  const usage = useMemo(() => {
    const eventCount = Number(metrics?.total || 0);
    const included = plan === 'enterprise' ? 10000 : plan === 'growth' ? 3000 : 1000;
    const percentage = Math.min(100, Math.round((eventCount / included) * 100));
    return { eventCount, included, percentage };
  }, [metrics, plan]);

  return (
    <section className="panel client-panel">
      <div className="panel-header">
        <h2>Client Control</h2>
        <p>Tenant summary, usage, and plan management.</p>
      </div>
      <div className="client-grid">
        <article className="client-card">
          <span className="label">Organization</span>
          <strong>{user?.org_id || 'unknown-org'}</strong>
          <span className={`plan-tag ${activePlan.colorClass}`}>{activePlan.label}</span>
        </article>
        <article className="client-card">
          <span className="label">Role</span>
          <strong>{user?.role || 'viewer'}</strong>
          <span className="muted">User: {user?.sub || user?.user_id || 'n/a'}</span>
        </article>
        <article className="client-card usage-card">
          <span className="label">Monthly Event Usage</span>
          <strong>{usage.eventCount} / {usage.included}</strong>
          <div className="usage-track" aria-label="plan-usage">
            <div className="usage-fill" style={{ width: `${usage.percentage}%` }} />
          </div>
        </article>
      </div>
      <div className="panel-actions">
        <button type="button" className="btn btn-secondary" onClick={onManagePlan}>Open Pricing</button>
      </div>
    </section>
  );
}
