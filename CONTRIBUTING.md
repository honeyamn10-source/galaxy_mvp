# Contributing to Galaxy

Thank you for your interest in contributing. By participating you agree to the [Code of Conduct](CODE_OF_CONDUCT.md).

## Getting started

1. Fork the repository and create a feature branch.
2. Read the relevant [phase documentation](README.md#-documentation) for the subsystem you are touching.
3. Keep changes focused — one logical change per pull request.
4. Run applicable tests (`make test`, `make chain-unit-test`, `make contracts-test`) before opening a PR.
5. Update configuration references and docs when behavior or environment variables change.

## Pull request checklist

- Describe the **problem** and the **behavior change** in the PR description.
- Include validation evidence (test output, deployment logs).
- Never commit secrets, `.env` values, or certificates into the repository.
- Preserve third-party licenses and attribution for any imported code.

## Reporting bugs

- Provide reproduction steps and the tested phase/environment.
- For deployment issues, include relevant logs with secrets redacted.
- Do not include live camera feeds, personal data, or real customer information.

## Code of conduct

All contributors must follow the [Code of Conduct](CODE_OF_CONDUCT.md). The maintainers may close or reject contributions that violate it.

---

## License

By contributing, you agree that your contributions are licensed under the [MIT License](LICENSE).