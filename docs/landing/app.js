const badge = document.getElementById('status-badge');

async function checkStatus() {
  if (!badge) {
    return;
  }

  try {
    const response = await fetch('http://localhost:1317/health', { cache: 'no-store' });
    if (response.ok) {
      badge.textContent = 'System Online';
      badge.className = 'rounded-full bg-emerald-500 px-3 py-1 text-sm font-semibold text-white';
      return;
    }
  } catch (error) {
    // fall through to offline state
  }

  badge.textContent = 'System Offline';
  badge.className = 'rounded-full bg-rose-500 px-3 py-1 text-sm font-semibold text-white';
}

checkStatus();
setInterval(checkStatus, 10000);
