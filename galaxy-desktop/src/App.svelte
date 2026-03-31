<script>
  import { invoke } from "@tauri-apps/api/tauri";

  let status = "Checking Docker and starting stack...";
  const dashboardUrl = "http://localhost:8000";

  async function startStack() {
    status = "Starting Galaxy stack...";
    try {
      const result = await invoke("start_stack");
      status = result;
    } catch (err) {
      status = `Failed to start stack: ${err}`;
    }
  }

  async function stopStack() {
    status = "Stopping Galaxy stack...";
    try {
      const result = await invoke("stop_stack");
      status = result;
    } catch (err) {
      status = `Failed to stop stack: ${err}`;
    }
  }

  async function openDashboard() {
    try {
      await invoke("open_dashboard");
    } catch (err) {
      status = `Cannot open dashboard: ${err}`;
    }
  }

  startStack();
</script>

<main>
  <header>
    <h1>Galaxy Desktop</h1>
    <p>{status}</p>
  </header>

  <section class="actions">
    <button on:click={startStack}>Start Stack</button>
    <button on:click={stopStack}>Stop Stack</button>
    <button on:click={openDashboard}>Open Dashboard</button>
  </section>

  <section class="frame-wrap">
    <iframe title="Galaxy Dashboard" src={dashboardUrl}></iframe>
  </section>
</main>

<style>
  :global(body) {
    margin: 0;
    font-family: "Inter", system-ui, sans-serif;
    background: #0b1020;
    color: #e5e7eb;
  }

  main {
    min-height: 100vh;
    display: grid;
    grid-template-rows: auto auto 1fr;
    gap: 12px;
    padding: 14px;
    background: radial-gradient(circle at 20% 0%, rgba(34, 197, 94, 0.2), transparent 35%), #0b1020;
  }

  h1 {
    margin: 0;
    font-size: 1.3rem;
  }

  p {
    margin: 6px 0 0;
    color: #cbd5e1;
  }

  .actions {
    display: flex;
    gap: 10px;
    flex-wrap: wrap;
  }

  button {
    border: 0;
    border-radius: 10px;
    padding: 10px 12px;
    font-weight: 600;
    cursor: pointer;
    background: #22c55e;
    color: #03230f;
  }

  .frame-wrap {
    border: 1px solid #334155;
    border-radius: 12px;
    overflow: hidden;
    min-height: 300px;
  }

  iframe {
    width: 100%;
    height: 100%;
    min-height: 65vh;
    border: 0;
    background: #ffffff;
  }
</style>
