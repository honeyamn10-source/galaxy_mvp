export default {
  async fetch(request, env) {
    if (request.method === "OPTIONS") {
      return new Response(null, {
        headers: {
          "Access-Control-Allow-Origin": "*",
          "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
          "Access-Control-Allow-Headers": "Content-Type,Authorization"
        }
      });
    }

    const url = new URL(request.url);

    if (url.pathname === "/health") {
      return json({ status: "ok", service: "galaxy-worker" });
    }

    if (url.pathname === "/ai/chat" && request.method === "POST") {
      const payload = await request.json().catch(() => ({}));
      const prompt = sanitizePrompt(payload.prompt);
      if (!prompt) {
        return json({ error: "prompt is required" }, 400);
      }

      if (prompt.length > 500) {
        return json({ error: "prompt too long" }, 400);
      }

      if (env.HF_API_TOKEN) {
        const hfResp = await fetch("https://api-inference.huggingface.co/models/google/flan-t5-base", {
          method: "POST",
          headers: {
            "Authorization": `Bearer ${env.HF_API_TOKEN}`,
            "Content-Type": "application/json"
          },
          body: JSON.stringify({ inputs: prompt })
        });

        const hfData = await hfResp.json();
        return json({ provider: "huggingface", response: hfData });
      }

      return json({
        provider: "none",
        response: "Set HF_API_TOKEN in Worker environment to enable AI inference.",
        echo: prompt
      });
    }

    return json({ error: "not found" }, 404);
  }
};

function sanitizePrompt(input) {
  return String(input || "")
    .replace(/[<>\u0000-\u001F\u007F]/g, " ")
    .trim();
}

function json(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "Content-Type": "application/json",
      "Access-Control-Allow-Origin": "*"
    }
  });
}
