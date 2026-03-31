# Paperclip Integration For Galaxy MVP

This guide integrates Paperclip as a governance and orchestration layer for Galaxy MVP autonomous workflows.

## 1) Install Paperclip

Run from repository root:

```bash
npx -y paperclipai onboard --yes
npx -y paperclipai run
```

Expected local endpoints:

- UI: http://localhost:3100
- API health: http://127.0.0.1:3100/api/health

Notes:

- Paperclip uses embedded PostgreSQL by default in `~/.paperclip/instances/default/db`.
- If startup fails with stale shared-memory errors, stop old Paperclip processes and retry `npx -y paperclipai run`.

## 2) Configure GitHub Token

Paperclip needs a GitHub PAT with `repo` and `workflow` scopes to dispatch workflows.

### Create PAT

1. Open GitHub settings.
2. Go to Developer settings > Personal access tokens.
3. Create token with scopes: `repo`, `workflow`.
4. Copy token once and store securely.

### Set token locally

```bash
export GITHUB_TOKEN=<your_pat>
```

Optional local env file:

```bash
cp .paperclip/.env.example .paperclip/.env
# edit .paperclip/.env and set real token
set -a
source .paperclip/.env
set +a
```

Security:

- Never commit PAT values.
- Prefer environment variables or Paperclip secret settings.

## 3) Create Company: Galaxy AI Systems

Use the Paperclip UI at http://localhost:3100:

1. Open Companies.
2. Click New Company.
3. Name: `Galaxy AI Systems`.
4. Save.

## 4) Wrap GitHub Actions As Paperclip Skills

Skill definitions live in `.paperclip/skills/`:

- `.paperclip/skills/galaxy-autonomous-loop.yaml`
- `.paperclip/skills/galaxy-pages-deploy.yaml`
- `.paperclip/skills/galaxy-worker-deploy.yaml`

Each skill defines:

- Name and description
- Inputs (goal description, branch, optional ticket/release notes)
- GitHub API dispatch call to corresponding workflow file

Dispatch endpoint used:

```text
POST /repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches
```

## 5) Hire Agents (Employees)

In Paperclip UI:

1. Open `Galaxy AI Systems`.
2. Create employee: `Galaxy DevOps Engineer`.
3. Role: `Engineer`.
4. Attach skills:
   - `galaxy-autonomous-loop`
   - `galaxy-pages-deploy`
   - `galaxy-worker-deploy`
5. Set budget (example):
   - hourly: `20`
   - daily cap: `150`

## 6) Create A Sample Goal

Example goal:

`Improve the Cloudflare Pages deployment speed by 20%`

In Paperclip UI:

1. Create goal under `Galaxy AI Systems`.
2. Assign to `Galaxy DevOps Engineer`.
3. Set due date and budget constraints.
4. Start execution.

## 7) Test The Integration

### In Paperclip UI

- Confirm goal creates a task.
- Confirm the assigned employee starts execution.
- Confirm audit/event log entries are produced.

### In GitHub Actions

- Open repository Actions tab.
- Confirm workflow run exists for one of:
  - `autonomous-loop.yml`
  - `cloudflare-pages.yml`
  - `cloudflare-worker.yml`
- Verify run result and logs.

### Optional local API check

```bash
python3 - <<'PY'
import urllib.request
print(urllib.request.urlopen('http://127.0.0.1:3100/api/health', timeout=10).read().decode())
PY
```

## 8) Add New Skills Later

1. Add a new YAML file in `.paperclip/skills/`.
2. Point `workflow_id` to the target `.github/workflows/*.yml` file.
3. Define `inputs` needed by the workflow dispatch.
4. Attach the new skill to the relevant employee in Paperclip UI.

## 9) Troubleshooting

### Paperclip UI does not load

```bash
npx -y paperclipai doctor
npx -y paperclipai run
```

### Embedded PostgreSQL startup error

- Error may mention stale lock/shared memory.
- Restart Paperclip runtime and ensure only one instance is running.

### Workflow dispatch fails

- Validate `GITHUB_TOKEN` exists in environment.
- Verify PAT scopes include `repo` and `workflow`.
- Confirm workflow file names match exactly.
- Ensure workflow supports dispatch if custom inputs are required.

### No task/audit entries in Paperclip

- Verify company and employee were created in correct workspace.
- Confirm employee has the required skill bindings.
- Check Paperclip logs under `~/.paperclip/instances/default/logs`.

## Operational Notes

- Paperclip governs planning, budgeting, and audit trails.
- Galaxy GitHub Actions remain execution workers for CI/CD and deployment.
- This separation preserves strong control-plane governance over automation.
