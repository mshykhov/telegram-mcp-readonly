# Documentation schema

## Source-of-truth order

1. Executable code, canonical Rulesync source, and repository configuration.
2. Living documentation under `docs/` and the root README.
3. Snapshot decisions, completed plans, and reviews.

When these layers disagree, verify the implementation and update the stale living layer. Do not rewrite a snapshot to make it appear current.

## Required structure

The repository keeps `docs/README.md`, this schema, architecture entry points, and indexed `decisions/`, `plans/`, `runbooks/`, `reference/`, and `reviews/` sections.

## Lifecycles

- Living: architecture, runbooks, reference, indexes, and the root README.
- Lifecycle: an active plan is living; a completed or abandoned plan becomes a snapshot.
- Snapshot: decisions and reviews.

## Naming

- Use lowercase kebab-case Markdown filenames.
- Decisions, plans, and reviews use `YYYY-MM-DD-<topic>.md`.
- Runbooks use an imperative operation name.
- Architecture and reference names describe stable topics without dates.

## Links and indexes

- Use ordinary relative Markdown links, not wikilinks.
- Add or remove a document and its index entry in the same change.
- Link the root README to `docs/README.md`; do not duplicate the architecture overview there.
- Generated `AGENTS.md` and `CLAUDE.md` files are instruction outputs, not documentation-section entries.

## Content

- Write documentation in English to match the existing repository.
- State verified current behavior and identify external boundaries explicitly.
- Keep examples distinguishable from implemented behavior.
- Never include Telegram credentials, session contents, personal absolute paths, or downloaded Telegram content.
