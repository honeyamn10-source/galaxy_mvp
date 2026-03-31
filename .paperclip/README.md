# Paperclip Skills For Galaxy MVP

This directory stores Paperclip skill definitions that wrap Galaxy GitHub Actions workflows.

## Skills

- `skills/galaxy-autonomous-loop.yaml`: triggers `.github/workflows/autonomous-loop.yml`
- `skills/galaxy-pages-deploy.yaml`: triggers `.github/workflows/cloudflare-pages.yml`
- `skills/galaxy-worker-deploy.yaml`: triggers `.github/workflows/cloudflare-worker.yml`

## Token Requirement

Set a GitHub Personal Access Token in your environment before running Paperclip-triggered workflow dispatches:

```bash
export GITHUB_TOKEN=<your_pat_with_repo_and_workflow_scopes>
```

## Security Note

Do not commit secrets. Keep tokens in shell environment, Paperclip secret settings, or local non-committed env files.
