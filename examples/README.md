# Examples

Ready-to-use `.diffcontract.yml` templates for common project types.

- [`.diffcontract.yml`](.diffcontract.yml) — Standard Python project (CI/CD block, feature limits, refactor warning)
- [`strict.yml`](strict.yml) — Security-sensitive project (deny auth/infra, small bugfix allowances)
- [`react.yml`](react.yml) — React/Next.js project (block root config, allow `app/`, `components/`, `lib/`)
- [`django.yml`](django.yml) — Django project (block `settings/`, allow `apps/`, `templates/`, `static/`)
- [`rust.yml`](rust.yml) — Rust workspace (block `Cargo.toml`, allow `crates/`, `src/`, `tests/`)
- [`docs.yml`](docs.yml) — Documentation-only project (block source code, allow `docs/`, `*.md`, `*.rst`)

Each template includes comments explaining what's blocked/allowed. Copy the relevant file to your project root as `.diffcontract.yml`.
