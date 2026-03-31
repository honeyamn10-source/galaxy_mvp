const aiMount = document.getElementById("ai-assistant-mount");
const aiButton = document.getElementById("open-ai-assistant");

if (aiButton && aiMount) {
  aiButton.addEventListener("click", async () => {
    aiButton.disabled = true;
    aiButton.textContent = "Loading AI Assistant...";

    try {
      const mod = await import("./ai-panel.js");
      mod.mountAIAssistant(aiMount);
      aiButton.remove();
    } catch (err) {
      aiButton.disabled = false;
      aiButton.textContent = "Open AI Assistant";
      aiMount.textContent = `Failed to load assistant: ${String(err)}`;
    }
  });
}

const observer = new IntersectionObserver(
  (entries) => {
    for (const e of entries) {
      if (e.isIntersecting) {
        e.target.classList.add("is-visible");
        observer.unobserve(e.target);
      }
    }
  },
  { threshold: 0.12 }
);

document.querySelectorAll(".card").forEach((el) => observer.observe(el));
