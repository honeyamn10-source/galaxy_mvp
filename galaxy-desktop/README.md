# Galaxy Desktop (Tauri Skeleton)

## Dev prerequisites

- Node.js 20+
- Rust toolchain
- Tauri system dependencies
- Docker running on host

## Run in dev mode

```bash
cd galaxy-desktop
npm install
npm run tauri dev
```

The app embeds the dashboard at http://localhost:8000 and exposes tray actions:
- Start Stack
- Stop Stack
- Open Dashboard
- Quit
