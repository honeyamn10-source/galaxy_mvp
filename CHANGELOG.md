# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Verisioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-09-16

### Added
- Professional README with hero logo, badge row, and architecture diagram
- ADR trail (0001..0005) documenting architectural decisions
- Loopback-only serving enforced across all demos
- Real screenshots captured from loopback UI (docs/screenshots/)
- .editorconfig for consistent formatting
- CI workflow with matrix testing
- Security scanning workflow
- CodeQL analysis workflow
- Dependabot configuration for automated dependency updates
- Stale issue/PR management workflow
- Cloudflare Pages deployment workflow
- Cloudflare Worker deployment workflow

### Changed
- Rewrote all commit history to use professional identity (Bittu Sharma <noreply@users.noreply.github.com>)
- Updated README with TradingAgents/hermes-agent style professional hero section
- Added architecture diagram (SVG + PNG) and landing screenshots

### Security
- Loopback-only serving enforced (ADR-0002 equivalent)
- No unauthenticated remote access
- Permission-led agent collaboration (ADR-0005)
