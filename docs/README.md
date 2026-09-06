# Documentation map

This directory is the documentation entry point and maintenance contract for `telegram-mcp-readonly`. Read [SCHEMA.md](SCHEMA.md) for file roles and lifecycle rules, then use the section indexes below.

## Sections

| Section | Purpose | Type |
|---------|---------|------|
| [architecture/](architecture/index.md) | Current components, flows, state ownership, and external boundaries | Living |
| [decisions/](decisions/) | Important choices, alternatives, and consequences | Snapshot |
| [plans/](plans/) | Active implementation plans and completed plan snapshots | Lifecycle |
| [runbooks/](runbooks/) | Repeatable operational and recovery procedures | Living |
| [reference/](reference/) | Exact schemas, commands, and configuration contracts | Living |
| [reviews/](reviews/) | Dated audits and review findings | Snapshot |

Living documents change with the behavior they describe. Snapshot documents preserve a conclusion at one point in time and are superseded instead of rewritten.

## Change this source, review that documentation

| Source change | Documentation to review |
|---------------|-------------------------|
| `telegram_mcp/runtime.py` or `telegram_mcp/runner.py` | [architecture/overview.md](architecture/overview.md), root `README.md` transports and configuration |
| `telegram_mcp/shared_service.py` or `runtime/launchd/**` | Root `README.md`, [architecture/overview.md](architecture/overview.md), and [runbooks/operate-shared-readonly-service.md](runbooks/operate-shared-readonly-service.md) |
| `telegram_mcp/tools/**` | [architecture/overview.md](architecture/overview.md), root `README.md` capabilities and security guidance |
| `setup_codex_readonly.py` or `.env.example` | Root `README.md` strict read-only setup and [architecture/overview.md](architecture/overview.md) state ownership |
| `telegram_mcp/install_guard.py` or packaging metadata | Root `README.md` installation warnings and [architecture/overview.md](architecture/overview.md) boundaries |
| `pyproject.toml`, `uv.lock`, or `.pre-commit-config.yaml` | Root `README.md` development commands |
| `.rulesync/**`, `rulesync.jsonc`, `package.json`, or `package-lock.json` | Root `README.md`, [architecture/overview.md](architecture/overview.md), and generated instruction outputs |
| `.github/workflows/**`, `Dockerfile`, or `docker-compose.yml` | Root `README.md` development and deployment guidance |
| Documentation taxonomy or naming | [SCHEMA.md](SCHEMA.md) and every affected section index |

## Maintenance

- Verify claims against code and configuration before updating living documents.
- Keep the root README focused on user setup and contributor entry points; keep system detail in architecture docs.
- Add every substantive document to its section index.
- Check changed relative links directly; do not add a dedicated link-test harness only for Markdown.
- Keep credentials, Telegram session data, personal paths, and downloaded content out of documentation.
