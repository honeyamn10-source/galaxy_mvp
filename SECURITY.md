# Security Policy

## Supported versions

| Version | Supported          |
| ------- | ------------------ |
| main    | :white_check_mark: |

This is a development repository. Security fixes are applied to the latest commit on `main`; there are no long-term supported release branches.

## Reporting a vulnerability

Please **do not open a public issue** for security vulnerabilities.

Email the maintainer privately with the subject `[galaxy_mvp] Security` and include:

- Description of the vulnerability and potential impact
- Affected service, endpoint, or manifest
- Reproduction steps (fictional/test data only — never real event or camera data)
- Suggested fix, if known

You will receive an acknowledgement within 5 business days and a remediation plan or a written explanation if the finding is not a vulnerability.

## Security notes

- Configuration is environment-based; never hardcode secrets in manifests or commit `.env` files.
- mTLS certificates and CA material must be stored and rotated out of band.
- Compliance regions, PII keys, and retention rules must be validated before processing regulated data.
- The CodeQL workflow should stay green — do not merge PRs that disable or skip security scans.