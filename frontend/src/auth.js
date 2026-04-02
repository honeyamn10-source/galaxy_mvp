const AUTH_URL = process.env.REACT_APP_AUTH_URL || 'http://localhost:8700';

function decodeJwtPayload(token) {
  const raw = token.split('.')[1] || '';
  const normalized = raw.replace(/-/g, '+').replace(/_/g, '/');
  const padded = normalized + '='.repeat((4 - (normalized.length % 4)) % 4);
  return JSON.parse(atob(padded));
}

function storeTokens(data) {
  sessionStorage.setItem('access_token', data.access_token);
  sessionStorage.setItem('refresh_token', data.refresh_token);
  sessionStorage.setItem('org_id', data.org_id);
  sessionStorage.setItem('role', data.role);
  sessionStorage.setItem('user_id', data.user_id);
}

export async function login(email, password) {
  const response = await fetch(`${AUTH_URL}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || 'Login failed');
  }
  storeTokens(data);
  return data;
}

export async function register(email, password, org_name) {
  const response = await fetch(`${AUTH_URL}/auth/register`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password, org_name }),
  });
  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || 'Registration failed');
  }
  storeTokens(data);
  return data;
}

export function authFetch(url, options = {}) {
  const token = sessionStorage.getItem('access_token');
  const headers = new Headers(options.headers || {});
  if (!headers.has('Content-Type') && options.body) {
    headers.set('Content-Type', 'application/json');
  }
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  return fetch(url, { ...options, headers });
}

export function getStoredUser() {
  const token = sessionStorage.getItem('access_token');
  if (!token) {
    return null;
  }

  try {
    const payload = decodeJwtPayload(token);
    if (payload.exp && payload.exp * 1000 < Date.now()) {
      sessionStorage.clear();
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

export function logout() {
  sessionStorage.clear();
}