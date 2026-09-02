const SECURITY_HEADERS = {
  "Content-Type": "application/json; charset=utf-8",
  "Cache-Control": "no-store",
  "X-Content-Type-Options": "nosniff",
  "Referrer-Policy": "no-referrer",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=()"
};

export default {
  async fetch(request, env) {
    const origin = request.headers.get("Origin");
    const cors = corsHeaders(origin, env.ALLOWED_ORIGINS);

    if (request.method === "OPTIONS") {
      if (!cors["Access-Control-Allow-Origin"]) return json({ error: "origin not allowed" }, 403);
      return new Response(null, { status: 204, headers: cors });
    }

    const url = new URL(request.url);
    if (url.pathname === "/health" && request.method === "GET") {
      return json({ status: "ok", service: "galaxy-worker" }, 200, cors);
    }

    if (url.pathname !== "/ai/chat" || request.method !== "POST") {
      return json({ error: "not found" }, 404, cors);
    }

    if (!authorized(request, env.AI_API_KEY)) {
      return json({ error: "unauthorized" }, 401, cors);
    }

    const contentLength = Number(request.headers.get("Content-Length") || 0);
    if (contentLength > 4096) return json({ error: "request too large" }, 413, cors);

    const payload = await request.json().catch(() => null);
    const prompt = sanitizePrompt(payload?.prompt);
    if (!prompt) return json({ error: "prompt is required" }, 400, cors);
    if (prompt.length > 1000) return json({ error: "prompt too long" }, 400, cors);
    if (!env.HF_API_TOKEN) return json({ error: "AI provider is not configured" }, 503, cors);

    try {
      const response = await fetch(
        env.HF_MODEL_URL || "https://api-inference.huggingface.co/models/google/flan-t5-base",
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${env.HF_API_TOKEN}`,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ inputs: prompt }),
          signal: AbortSignal.timeout(20000)
        }
      );

      if (!response.ok) {
        return json({ error: "AI provider unavailable", status: response.status }, 502, cors);
      }

      return json({ provider: "huggingface", response: await response.json() }, 200, cors);
    } catch (error) {
      const status = error?.name === "TimeoutError" ? 504 : 502;
      return json({ error: status === 504 ? "AI provider timed out" : "AI provider unavailable" }, status, cors);
    }
  }
};

function authorized(request, expected) {
  if (!expected || expected.length < 32) return false;
  const value = request.headers.get("Authorization") || "";
  return value.startsWith("Bearer ") && value.slice(7) === expected;
}

function corsHeaders(origin, configured = "") {
  const allowed = configured.split(",").map((value) => value.trim()).filter(Boolean);
  const headers = {
    "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type,Authorization",
    "Access-Control-Max-Age": "86400",
    Vary: "Origin"
  };
  if (origin && allowed.includes(origin)) headers["Access-Control-Allow-Origin"] = origin;
  return headers;
}

function sanitizePrompt(input) {
  return String(input || "").replace(/[<>\u0000-\u001F\u007F]/g, " ").trim();
}

function json(body, status = 200, extraHeaders = {}) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...SECURITY_HEADERS, ...extraHeaders }
  });
}
