function sanitizePrompt(input) {
  const trimmed = String(input || "").trim().slice(0, 500);
  return trimmed.replace(/[<>\\u0000-\\u001F\\u007F]/g, " ");
}

export function mountAIAssistant(container) {
  const wrap = document.createElement("div");
  wrap.className = "ai-panel";
  wrap.innerHTML = `
    <h3>AI Assistant (Free Endpoint)</h3>
    <p>Uses Cloudflare Worker + optional Hugging Face token.</p>
    <textarea id="ai-prompt" rows="4" placeholder="Ask about architecture, deployment, or incidents..."></textarea>
    <div class="ai-actions">
      <button id="ai-send">Send</button>
    </div>
    <pre id="ai-output">Ready.</pre>
  `;

  container.appendChild(wrap);

  const send = wrap.querySelector("#ai-send");
  const prompt = wrap.querySelector("#ai-prompt");
  const output = wrap.querySelector("#ai-output");

  send.addEventListener("click", async () => {
    const safePrompt = sanitizePrompt(prompt.value);
    if (!safePrompt) {
      output.textContent = "Prompt is required.";
      return;
    }

    send.disabled = true;
    output.textContent = "Running...";

    try {
      const resp = await fetch("/ai/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: safePrompt })
      });

      const data = await resp.json();
      output.textContent = JSON.stringify(data, null, 2);
    } catch (err) {
      output.textContent = `Request failed: ${String(err)}`;
    } finally {
      send.disabled = false;
    }
  });
}
