# Security

## Reporting a vulnerability

Please [report vulnerabilities privately](https://github.com/mshykhov/telegram-mcp-readonly/security/advisories/new). Include the affected commit, reproduction steps, and expected impact. Do not attach Telegram credentials, session files, private messages, or unredacted logs.

Security fixes target the current `main` branch.

## Read-only boundary

Strict read-only mode is enabled by default and uses an explicit tool allowlist. Sending, editing, deleting, reacting, and marking messages as read are excluded. New upstream tools do not enter this allowlist automatically.

Attachment downloads write only to the operator-configured download directory. Voice transcription and transcript-cache access are disabled in strict mode. Other exposure modes can enable Telegram writes and external transcription services; use them only deliberately.

A Telegram session still grants account access. Keep `.env`, session files, downloads, and logs private. The shared HTTP service should remain bound to loopback unless authentication and transport security are configured separately.

## Automated checks

Pull requests run tests with coverage, lint, formatting, Docker builds, agent-configuration verification, and CodeQL analysis for Python and GitHub Actions. CodeQL also runs weekly. These checks support the read-only boundary tests; they do not replace them.
