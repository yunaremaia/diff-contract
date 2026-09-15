# Security Policy

## Supported Versions

Only the latest released minor version of `diff-contract` is supported with security updates.

| Version | Supported          |
| ------- | ------------------ |
| 0.2.x   | :white_check_mark: |
| < 0.2.0 | :x:                |

### End-of-Life Policy

- Once a new minor version is released, the previous minor version enters a 90-day security support window during which critical fixes may still be backported on a case-by-case basis.
- After the 90-day window, the deprecated version receives no further security patches. users are expected to upgrade with each release cycle.
- Major version bumps (e.g. 1.0.0) reset the timeline; the latest major is the only supported line.

## Reporting a Vulnerability

If you discover a security vulnerability in `diff-contract`, please report it responsibly:

- **Do NOT open a public GitHub issue.**
- Report security issues privately via [GitHub Security Advisories](https://github.com/yunaremaia/diff-contract/security/advisories/new).
- Alternatively, email the maintainer at `yunare@gmail.com` with the subject line `[SECURITY] diff-contract vulnerability`.

### What to Include in Your Report

To help us triage and resolve the issue quickly, please include:

- A description of the vulnerability and its potential security impact.
- Step-by-step instructions to reproduce the issue, including minimal reproduction `.diffcontract.yml` files and sample diffs.
- Any suggested remediations or patches if available.
- The affected version(s) and environment details.

### Disclosure Timeline

We follow a coordinated disclosure process:

1. **Report received** — you submit the report via advisory or email.
2. **Acknowledgment (within 48 hours)** — we confirm receipt and assign a triage owner.
3. **Assessment (up to 7 days)** — we reproduce, score (CVSS-style impact), and decide on a fix schedule.
4. **Fix development** — we work on a patch in a private fork; you may be invited to review if relevant.
5. **Coordinated release** — once a fix ships on PyPI and GitHub, we publish a public security advisory crediting you (unless you prefer to remain anonymous).
6. **Public disclosure** — the advisory and CVE (if applicable) become public; details that could aid exploitation remain restricted until the fix is widely available.

We aim to resolve critical issues within 30 days of acknowledgment. If you do not hear back within 48 hours, please follow up via email.
