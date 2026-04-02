const PLANS = [
  {
    id: 'starter',
    name: 'Starter',
    price: '$0',
    cadence: 'forever',
    bullets: ['Up to 1,000 events/mo', 'Shared inference capacity', 'Community support'],
  },
  {
    id: 'growth',
    name: 'Growth',
    price: '$49',
    cadence: 'per month',
    bullets: ['Up to 3,000 events/mo', 'Priority LLM routing', 'Webhook automations'],
  },
  {
    id: 'enterprise',
    name: 'Enterprise',
    price: '$199',
    cadence: 'per month',
    bullets: ['10,000+ events/mo', 'Dedicated authority cluster', 'SLA + security review'],
  },
];

export default function PricingModal({ open, currentPlan, onClose, onSelectPlan }) {
  if (!open) {
    return null;
  }

  return (
    <div className="modal-backdrop" role="dialog" aria-modal="true">
      <div className="modal-card">
        <div className="panel-header">
          <h2>Pricing Plans</h2>
          <p>Choose the package that matches your telemetry volume.</p>
        </div>
        <div className="plan-grid">
          {PLANS.map((plan) => {
            const active = plan.id === currentPlan;
            return (
              <article className={`plan-card ${active ? 'active' : ''}`} key={plan.id}>
                <h3>{plan.name}</h3>
                <div className="price">{plan.price} <span>{plan.cadence}</span></div>
                <ul>
                  {plan.bullets.map((bullet) => <li key={bullet}>{bullet}</li>)}
                </ul>
                <button
                  type="button"
                  className={`btn ${active ? 'btn-secondary' : 'btn-primary'}`}
                  onClick={() => onSelectPlan(plan.id)}
                >
                  {active ? 'Current plan' : 'Select'}
                </button>
              </article>
            );
          })}
        </div>
        <div className="panel-actions">
          <button type="button" className="btn btn-secondary" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  );
}
